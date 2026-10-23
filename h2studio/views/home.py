"""Home: install truth, environment truth, and the fastest path to a first run."""

from __future__ import annotations

import subprocess
import tkinter as tk

from ..services import h2
from ..theme import SPACE
from ..widgets import Card, Chip, Pill, Scroller, StatCard
from .base import View


class HomeView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        scroll = Scroller(self, t)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        pad = tk.Frame(root, bg=t.c["surface"])
        pad.pack(fill="both", expand=True, padx=28, pady=24)

        hero = Card(pad, t, pad=SPACE["xl"])
        hero.pack(fill="x")
        tk.Label(hero.content, text="A control room for recursive agent harnessing",
                 bg=t.c["surface_container"], fg=t.c["on_surface"],
                 font=t.font("title_lg"), anchor="w").pack(fill="x")
        tk.Label(
            hero.content,
            text=("Harness² improves the harness around a frozen model. This app drives the real "
                  "CLIs — setup, sweep, judge, report — and edits the eight components without "
                  "hiding what happens."),
            bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("body"),
            anchor="w", justify="left", wraplength=820,
        ).pack(fill="x", pady=(6, 14))

        row = tk.Frame(hero.content, bg=t.c["surface_container"])
        row.pack(fill="x")
        Pill(row, "Run demo", self._demo, t, "filled").pack(side="left", padx=(0, 8))
        Pill(row, "Check environment", self._check, t, "tonal").pack(side="left", padx=(0, 8))
        Pill(row, "Open runs folder", lambda: self.app.open_path(self.app.install.runs_default), t, "outlined").pack(side="left")
        tk.Label(hero.content, text="Ctrl+1–9 switch views · F5 refresh · Esc stop · Ctrl+Enter start",
                 bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("caption"),
                 anchor="w").pack(fill="x", pady=(10, 0))

        self.setup_card = Card(pad, t, title="Get set up",
                               subtitle="Live checks, in the order that avoids wasted runs.")
        self.setup_card.pack(fill="x", pady=(18, 0))
        self.setup_body = self.setup_card.content

        stats = tk.Frame(pad, bg=t.c["surface"])
        self.stats = stats
        stats.pack(fill="x", pady=(20, 0))
        for i in range(4):
            stats.grid_columnconfigure(i, weight=1, uniform="stat")
        self.card_install = StatCard(stats, t, "Install", "…")
        self.card_python = StatCard(stats, t, "Interpreter", "…")
        self.card_env = StatCard(stats, t, "Model wiring", "…")
        self.card_runs = StatCard(stats, t, "Artifacts", "…")
        for i, card in enumerate((self.card_install, self.card_python, self.card_env, self.card_runs)):
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))

        comp = Card(pad, t, title="The eight components", subtitle="C1–C8, exactly the files Harness² edits.")
        comp.pack(fill="x", pady=(20, 0))
        chips = tk.Frame(comp.content, bg=t.c["surface_container"])
        chips.pack(fill="x")
        for i, (key, title, rel) in enumerate(
            (
                ("C1", "System prompt", "systemprompt.md"),
                ("C2", "Guardrails", "guardrails.md"),
                ("C3", "Memory", "LongTermMEMORY.md"),
                ("C4", "Tool guidance", "tool_guidance.md"),
                ("C5", "Subagents", "sub_agents/"),
                ("C6", "Skills", "skills/"),
                ("C7", "Scripts", "scripts/"),
                ("C8", "Plugins", "plugin/"),
            )
        ):
            cell = tk.Frame(chips, bg=t.c["surface_container"])
            cell.grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 18), pady=4)
            tk.Label(cell, text=key, bg=t.c["surface_container"], fg=t.c["primary"],
                     font=t.font("label")).pack(side="left")
            tk.Label(cell, text=f"  {title}", bg=t.c["surface_container"], fg=t.c["on_surface"],
                     font=t.font("body")).pack(side="left")
            tk.Label(cell, text=f"  {rel}", bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("caption")).pack(side="left")

        self.recent_card = Card(pad, t, title="Recent commands", subtitle="Rerun the exact argv this app used.")
        self.recent_card.pack(fill="x", pady=(20, 24))

    def refresh(self) -> None:
        t = self.theme
        inst = self.app.install
        if inst.exists():
            self.card_install.update_value("Ready", f"{inst.repo.name} · {inst.repo}")
        else:
            self.card_install.update_value("Missing", f"No checkout at {inst.repo}")

        version = "—"
        if inst.python.is_file():
            try:
                version = subprocess.run([str(inst.python), "-V"], capture_output=True, text=True,
                                         timeout=3, check=False).stdout.strip() or "ok"
            except (OSError, subprocess.SubprocessError):
                version = "unusable"
        self.card_python.update_value(version.split()[-1] if version.startswith("Python") else version,
                                      str(inst.python))

        env = h2.read_env(inst.env_file)
        wired = [k for k in ("HARNESS2_SOLVER_MODEL", "HARNESS2_IMPROVER_MODEL", "HARNESS2_JUDGE_MODEL") if env.get(k)]
        self.card_env.update_value(f"{len(wired)}/3", ", ".join(wired) or "set models in Models")

        arts = self.app.artifacts()
        self.card_runs.update_value(str(len(arts)), "demo, summary, judged")

        self._render_setup(inst, env, len(arts))

        for child in self.recent_card.content.winfo_children():
            child.destroy()
        recent = self.app.state.recent or ["(nothing yet — run the demo)"]
        for cmd in recent[:6]:
            row = tk.Frame(self.recent_card.content, bg=t.c["surface_container"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=cmd, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("mono_sm"), anchor="w", justify="left").pack(side="left", fill="x", expand=True)
            Pill(row, "Copy", lambda c=cmd: self._copy(c), t, "text", height=26, pad=8).pack(side="right")

    def _render_setup(self, inst, env, artifact_count: int) -> None:
        t = self.theme
        for child in self.setup_body.winfo_children():
            child.destroy()
        steps: list[tuple[str, str, str, object]] = []
        checkout = (inst.repo / "pyproject.toml").is_file()
        if not checkout:
            steps.append(("Install or locate the source",
                          "Download the official checkout, or point Studio at an existing one.",
                          "Open Install", lambda: self.app.show("install")))
        elif not inst.exists():
            steps.append(("Create the Python environment",
                          "The checkout exists but its interpreter is missing. Install can rebuild it.",
                          "Open Install", lambda: self.app.show("install")))
        if not env.get("HARNESS2_SOLVER_MODEL"):
            steps.append(("Connect the executor model",
                          "Set HARNESS2_SOLVER_MODEL in .env so real sweeps can run.",
                          "Open Models", lambda: self.app.show("models")))
        if artifact_count == 0:
            steps.append(("Prove the pipeline with the free demo",
                          "No credentials, no cost, no network. Writes a real artifact under runs/.",
                          "Run demo", self._demo))
        if not steps:
            self.setup_card.pack_forget()
            return
        self.setup_card.pack(fill="x", pady=(18, 0), before=self.stats)
        for i, (title, detail, action, command) in enumerate(steps, 1):
            row = tk.Frame(self.setup_body, bg=t.c["surface_container"])
            row.pack(fill="x", pady=3)
            Chip(row, t, str(i), "primary").pack(side="left", anchor="n")
            text = tk.Frame(row, bg=t.c["surface_container"])
            text.pack(side="left", fill="x", expand=True, padx=(10, 8))
            tk.Label(text, text=title, bg=t.c["surface_container"], fg=t.c["on_surface"],
                     font=t.font("body_lg"), anchor="w").pack(fill="x")
            tk.Label(text, text=detail, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("caption"), anchor="w", justify="left", wraplength=640).pack(fill="x")
            Pill(row, action, command, t, "outlined", height=32, pad=12).pack(side="right", anchor="n")
        Pill(self.setup_body, "Read the field guide", lambda: self.app.show("guide"), t,
             "text", height=30, pad=8).pack(anchor="w", pady=(6, 0))

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.app.toast("Copied")

    def _demo(self) -> None:
        self.app.show("run")
        self.app.run_action("demo", h2.Options(output="runs/demo", k=2), label="demo")

    def _check(self) -> None:
        self.app.show("setup")
