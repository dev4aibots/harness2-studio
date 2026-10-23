"""Setup: install a benchmark, verify the environment, read the real failures."""

from __future__ import annotations

import re
import tkinter as tk

from ..services import h2, requirements
from ..widgets import Card, Chip, Console, Pill, Segmented
from .base import View

ISSUE = re.compile(r"^(FAIL|WARN|OK):\s*(.+)$")


class SetupView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.collecting = False
        self.issues: list[tuple[str, str]] = []

        self.install_banner = tk.Frame(self, bg=t.c["error_container"])
        tk.Label(self.install_banner, text="Harness² source not found. Install it before running benchmark setup.",
                 bg=t.c["error_container"], fg=t.c["on_error_container"], font=t.font("body"),
                 anchor="w").pack(side="left", padx=14, pady=10)
        Pill(self.install_banner, "Open Install", lambda: app.show("install"), t,
             "outlined", height=32, pad=12).pack(side="right", padx=10, pady=6)
        self.install_banner.pack(fill="x", padx=20, pady=(12, 0))

        top = tk.Frame(self, bg=t.c["surface"])
        self.top = top
        top.pack(fill="x", padx=20, pady=(16, 8))

        pick = Card(top, t, title="Target", subtitle="One benchmark per command, exactly as the CLIs require.")
        pick.pack(side="left", fill="both", expand=True)
        self.bench = Segmented(pick.content, t, [("jb", "JobBench"), ("lab", "LAB"), ("wb", "WorkBuddy")],
                               app.state.last_bench, self._bench_changed)
        self.bench.pack(anchor="w")
        row = tk.Frame(pick.content, bg=t.c["surface_container"])
        row.pack(fill="x", pady=(10, 0))
        tk.Label(row, text="Executor", bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                 font=t.font("label")).pack(side="left", padx=(0, 10))
        self.substrate = Segmented(row, t, [("oc", "OpenCode"), ("cx", "Codex")],
                                   app.state.last_substrate, self._substrate_changed)
        self.substrate.pack(side="left")
        self.subset_wrap = tk.Frame(row, bg=t.c["surface_container"])
        tk.Label(self.subset_wrap, text="Subset", bg=t.c["surface_container"],
                 fg=t.c["on_surface_variant"], font=t.font("label")).pack(side="left", padx=(20, 10))
        self.subset = Segmented(self.subset_wrap, t, [("office", "Office"), ("web", "Web"), ("code", "Code")], "office")
        self.subset.pack(side="left")
        self.subset_wrap.pack(side="left")
        tk.Label(pick.content,
                 text="JobBench needs its dataset checkout. WorkBuddy needs Docker and workbuddy-bench. "
                      "LAB needs harvey-labs plus pandoc and poppler. The checklist on the right is live.",
                 bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("body"),
                 anchor="w", justify="left", wraplength=430).pack(fill="x", pady=(16, 0))
        self._bench_changed(app.state.last_bench, initial=True)

        req_card = Card(top, t, title="Prerequisites")
        req_card.pack(side="left", fill="both", expand=True, padx=(16, 0))
        self.req_body = req_card.content

        actions = tk.Frame(self, bg=t.c["surface"])
        actions.pack(fill="x", padx=20, pady=(0, 8))
        Pill(actions, "Install benchmark", self._install, t, "filled").pack(side="left", padx=(0, 8))
        Pill(actions, "Check environment", self._check, t, "tonal").pack(side="left", padx=(0, 8))
        Pill(actions, "Dry run install", self._dry, t, "outlined").pack(side="left")

        body = tk.Frame(self, bg=t.c["surface"])
        body.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        issue_card = Card(body, t, title="Verification", subtitle="Parsed from harness2-check, verbatim.")
        issue_card.grid(row=0, column=0, sticky="nsew")
        self.issue_list = tk.Frame(issue_card.content, bg=t.c["surface_container"])
        self.issue_list.pack(fill="both", expand=True)

        out_card = Card(body, t, title="Output")
        out_card.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        self.console = Console(out_card.content, t, height=18)
        self.console.pack(fill="both", expand=True)

        app.log.subscribe(self._on_log)
        self.bind("<Destroy>", self._on_destroy)
        self.refresh()

    # -- state ----------------------------------------------------------
    def _bench_changed(self, bench: str, initial: bool = False) -> None:
        self.app.state.last_bench = bench
        if bench == "wb":
            self.subset_wrap.pack(side="left")
        else:
            self.subset_wrap.pack_forget()
        if not initial:
            self._render_requirements()

    def _substrate_changed(self, value: str) -> None:
        self.app.state.last_substrate = value

    def _opts(self) -> h2.Options:
        subset = self.subset.value if self.bench.value == "wb" else None
        return h2.Options(bench=self.bench.value, subset=subset, substrate=self.substrate.value)

    # -- actions --------------------------------------------------------
    def _install(self) -> None:
        self.issues.clear()
        self._render_issues()
        self.app.run_action("setup", self._opts(), label=f"install {self.bench.value}")

    def _dry(self) -> None:
        opts = self._opts()
        opts.dry_run = True
        self.app.run_action("setup", opts, label="dry-run install")

    def _check(self) -> None:
        self.issues.clear()
        self._render_issues()
        self.collecting = True
        self.app.run_action("check", self._opts(), label="verify")

    # -- live output ----------------------------------------------------
    def _on_log(self, line: str, tag: str) -> None:
        self.console.append(line, tag)
        if not self.collecting:
            return
        m = ISSUE.match(line.strip())
        if m:
            self.issues.append((m.group(1), m.group(2)))
            self._render_issues()
        elif line.startswith("Setup "):
            self.collecting = False

    def _render_issues(self) -> None:
        t = self.theme
        for child in self.issue_list.winfo_children():
            child.destroy()
        if not self.issues:
            tk.Label(self.issue_list, text="Run “Check environment” to see real failures, not a green checkmark.",
                     bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("body"),
                     anchor="w", justify="left", wraplength=420).pack(fill="x", pady=6)
            return
        for level, message in self.issues[:40]:
            row = tk.Frame(self.issue_list, bg=t.c["surface_container"])
            row.pack(fill="x", pady=2)
            tone = {"FAIL": "error", "WARN": "warning", "OK": "success"}.get(level, "neutral")
            Chip(row, t, level, tone).pack(side="left", anchor="n")
            tk.Label(row, text=message, bg=t.c["surface_container"], fg=t.c["on_surface"],
                     font=t.font("body"), anchor="w", justify="left", wraplength=400).pack(
                side="left", fill="x", expand=True, padx=(8, 0))

    def _render_requirements(self) -> None:
        t = self.theme
        for child in self.req_body.winfo_children():
            child.destroy()
        items = requirements.check(self.app.install, self.bench.value)
        ok, total = requirements.summary(items)
        head = tk.Frame(self.req_body, bg=t.c["surface_container"])
        head.pack(fill="x")
        tk.Label(head, text=f"{ok}/{total} ready", bg=t.c["surface_container"], fg=t.c["on_surface"],
                 font=t.font("title")).pack(side="left")
        Pill(head, "Re-check", self._render_requirements, t, "text", height=28, pad=8).pack(side="right")
        for item in items:
            row = tk.Frame(self.req_body, bg=t.c["surface_container"])
            row.pack(fill="x", pady=1)
            Chip(row, t, "OK" if item.ok else "MISSING", "success" if item.ok else "error").pack(side="left")
            tk.Label(row, text=item.label, bg=t.c["surface_container"], fg=t.c["on_surface"],
                     font=t.font("body")).pack(side="left", padx=(8, 0))
            detail = item.detail
            if "/" in detail and len(detail) > 46:
                detail = "…/" + "/".join(detail.rstrip("/").split("/")[-3:])
            tk.Label(row, text=detail, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("caption"), anchor="e").pack(side="right")

    def refresh(self) -> None:
        if self.app.install.exists():
            self.install_banner.pack_forget()
        else:
            self.install_banner.pack(fill="x", padx=20, pady=(12, 0), before=self.top)
        self._render_requirements()
        self._render_issues()

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self.app.log.unsubscribe(self._on_log)
