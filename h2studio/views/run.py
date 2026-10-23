"""Run: the full sweep surface, with the exact argv always visible."""

from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..services import h2
from ..widgets import Card, Console, Pill, Segmented, Toggle
from .base import View

PYTHON = "/home/dev/.local/python312/bin/python3.12"
REPO = Path(__file__).resolve().parents[1] / "harness2"


def _format_argv(prefix: str, tokens: list[str]) -> str:
    """One flag per line: a 40-flag command must stay readable, not clip."""
    lines: list[str] = []
    current = [prefix]
    for tok in tokens:
        if tok.startswith("--") and len(current) > 1:
            lines.append(" ".join(current))
            current = [tok]
        else:
            current.append(tok)
    lines.append(" ".join(current))
    return "\n    ".join(lines)


class RunView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.vars: dict[str, tk.StringVar] = {}
        self.running = False
        saved = dict(app.state.last_form or {})

        body = tk.Frame(self, bg=t.c["surface"])
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=4)
        body.grid_rowconfigure(0, weight=1)

        form = Card(body, t, title="Sweep", subtitle="Every flag maps 1:1 to harness2 run_sweep.")
        form.grid(row=0, column=0, sticky="nsew")
        f = form.content

        self.bench = Segmented(f, t, [("jb", "JobBench"), ("lab", "LAB"), ("wb", "WorkBuddy")],
                               app.state.last_bench, lambda _v: self._bench_changed())
        self.bench.pack(anchor="w")
        self.subset_bar = tk.Frame(f, bg=t.c["surface_container"])
        tk.Label(self.subset_bar, text="Subset", bg=t.c["surface_container"],
                 fg=t.c["on_surface_variant"], font=t.font("label")).pack(side="left", padx=(0, 8))
        self.subset = Segmented(self.subset_bar, t, [("all", "All"), ("office", "Office"), ("web", "Web"), ("code", "Code")],
                                "all", lambda _v: self._changed())
        self.subset.pack(side="left")
        row = tk.Frame(f, bg=t.c["surface_container"])
        row.pack(fill="x", pady=(8, 0))
        tk.Label(row, text="Executor", bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                 font=t.font("label")).pack(side="left", padx=(0, 8))
        self.substrate = Segmented(row, t, [("oc", "OpenCode"), ("cx", "Codex")],
                                   app.state.last_substrate, lambda _v: self._changed())
        self.substrate.pack(side="left")

        grid = tk.Frame(f, bg=t.c["surface_container"])
        grid.pack(fill="x", pady=(10, 0))
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1, uniform="f")

        self._entry(grid, "k (recursion)", "k", saved.get("k", "1"), 0, 0)
        self._entry(grid, "seed", "seed", saved.get("seed", ""), 0, 1, hint="blank = sorted")
        self._entry(grid, "workers", "workers", saved.get("workers", "1"), 0, 2)
        self._entry(grid, "max tasks", "max_tasks", saved.get("max_tasks", ""), 1, 0, hint="blank = all")
        self._entry(grid, "only domains", "only_domains", saved.get("only_domains", ""), 1, 1, hint="comma list")
        self._entry(grid, "split file", "split_file", saved.get("split_file", ""), 1, 2, hint="test split only")

        modes = tk.Frame(f, bg=t.c["surface_container"])
        modes.pack(fill="x", pady=(10, 0))
        self.tog_p = Toggle(modes, "parallel", True, lambda _v: self._changed(), t, bg=t.c["surface_container"])
        self.tog_p.pack(side="left", padx=(0, 8))
        self.tog_s = Toggle(modes, "sequential", False, lambda _v: self._changed(), t, bg=t.c["surface_container"])
        self.tog_s.pack(side="left", padx=(0, 8))
        self.tog_dry = Toggle(modes, "dry run", False, lambda _v: self._changed(), t, bg=t.c["surface_container"])
        self.tog_dry.pack(side="left", padx=(8, 8))
        self.tog_bases = Toggle(modes, "judge bases", False, lambda _v: self._changed(), t, bg=t.c["surface_container"])
        self.tog_bases.pack(side="left")

        preview = tk.Frame(f, bg=t.c["surface_high"], highlightthickness=1,
                           highlightbackground=t.c["outline_variant"])
        preview.pack(fill="x", pady=(12, 0))
        self.preview = tk.Label(preview, text="", bg=t.c["surface_high"], fg=t.c["on_surface_variant"],
                                font=t.font("mono_sm"), anchor="w", justify="left", padx=10, pady=8,
                                wraplength=520)
        self.preview.pack(fill="x")

        actions = tk.Frame(f, bg=t.c["surface_container"])
        actions.pack(fill="x", pady=(12, 0))
        self.start_btn = Pill(actions, "Start sweep", self._start, t, "filled")
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = Pill(actions, "Stop", self.app.stop_action, t, "danger", height=38, pad=14)
        self.stop_btn.pack(side="left", padx=(0, 8))
        self.stop_btn.set_enabled(False)
        Pill(actions, "Judge", self._judge, t, "tonal", height=38, pad=14).pack(side="left", padx=(0, 8))
        Pill(actions, "Report", self._report, t, "outlined", height=38, pad=14).pack(side="left", padx=(0, 8))
        Pill(actions, "Auto-Improve", self._auto_improve, t, "filled", height=38, pad=14).pack(side="left")

        self.warning = tk.Label(f, text="", bg=t.c["surface_container"], fg=t.c["warning"],
                                font=t.font("caption"), anchor="w", justify="left", wraplength=520)
        self.warning.pack(fill="x", pady=(8, 0))

        right = tk.Frame(body, bg=t.c["surface"])
        right.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        out = Card(right, t, title="Output")
        out.grid(row=0, column=0, sticky="nsew")
        self.console = Console(out.content, t, height=20)
        self.console.pack(fill="both", expand=True)
        if not self.app.log.buffer:
            self.console.append("No output yet. Start a sweep, judge, report — or run the demo below.", "dim")

        demo = Card(right, t, title="Demo", subtitle="Credential-free. Proves the pipeline without touching a model.")
        demo.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        drow = tk.Frame(demo.content, bg=t.c["surface_container"])
        drow.pack(fill="x")
        self.demo_out = tk.StringVar(value="runs/demo")
        self.demo_k = tk.StringVar(value="2")
        self.demo_mode = Segmented(drow, t, [("both", "Both"), ("parallel", "Parallel"), ("sequential", "Sequential")], "both")
        self.demo_mode.pack(side="left")
        for label, var, width in (("folder", self.demo_out, 16), ("k", self.demo_k, 4)):
            tk.Label(drow, text=label, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("label")).pack(side="left", padx=(14, 4))
            ttk.Entry(drow, textvariable=var, width=width).pack(side="left")
        Pill(drow, "Run demo", self._demo, t, "filled", height=32, pad=12).pack(side="right")

        for var in self.vars.values():
            var.trace_add("write", lambda *_a: self._changed())
        app.log.subscribe(self._on_log)
        self.bind("<Destroy>", self._on_destroy)
        self._poll()
        self._bench_changed()
        self.on_primary = self._start

    # -- form -----------------------------------------------------------
    def _entry(self, parent, label: str, key: str, default: str, r: int, c: int, hint: str = "") -> None:
        t = self.theme
        wrap = tk.Frame(parent, bg=t.c["surface_container"])
        wrap.grid(row=r, column=c, sticky="ew", padx=(0, 10), pady=(6, 0))
        tk.Label(wrap, text=label, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                 font=t.font("label"), anchor="w").pack(fill="x")
        var = tk.StringVar(value=default)
        self.vars[key] = var
        ttk.Entry(wrap, textvariable=var, width=12).pack(fill="x", pady=(2, 0))
        if hint:
            tk.Label(wrap, text=hint, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("caption"), anchor="w").pack(fill="x")

    def _bench_changed(self) -> None:
        self.app.state.last_bench = self.bench.value
        if self.bench.value == "wb":
            self.subset_bar.pack(fill="x", pady=(8, 0), after=self.bench)
        else:
            self.subset_bar.pack_forget()
        self._changed()

    def _opts(self) -> h2.Options:
        def num(key: str, cast=int):
            raw = self.vars[key].get().strip()
            if not raw:
                return None
            try:
                return cast(raw)
            except ValueError:
                raise h2.ConfigError(f"{key.replace('_', '-')} must be a whole number") from None

        modes = tuple(m for m, on in (("parallel", self.tog_p.value), ("sequential", self.tog_s.value)) if on)
        subset = self.subset.value if (self.bench.value == "wb" and self.subset.value != "all") else None
        return h2.Options(
            bench=self.bench.value,
            subset=subset,
            substrate=self.substrate.value,
            k=num("k") or 1,
            seed=num("seed"),
            modes=modes,
            split="test" if self.vars["split_file"].get().strip() else "all",
            split_file=self.vars["split_file"].get().strip() or None,
            workers=num("workers") or 1,
            only_domains=self.vars["only_domains"].get().strip() or None,
            max_tasks=num("max_tasks"),
            dry_run=self.tog_dry.value,
            bases=self.tog_bases.value,
            report_k=str(num("k") or 1),
        )

    def _changed(self) -> None:
        t = self.theme
        error = None
        opts: h2.Options | None = None
        try:
            opts = self._opts()
            tokens = h2.build("run", opts)
            shown = _format_argv("python -m harness2.cli.run_sweep", tokens)
        except h2.ConfigError as exc:
            error = str(exc)
            shown = f"invalid: {exc}"
        self.preview.configure(text=shown, fg=t.c["error"] if error else t.c["on_surface_variant"])
        self.start_btn.set_enabled(error is None and not self.running)

        warn = ""
        if error is None and opts is not None:
            if opts.k > 1:
                warn = f"k={opts.k} costs {4 * opts.k} executor rollouts + {3 * opts.k} improver sessions per task."
            elif opts.max_tasks is None and not opts.dry_run:
                warn = "No task cap: this runs every task in the split. Use dry run first."
        self.warning.configure(text=warn)

    # -- actions --------------------------------------------------------
    def _start(self) -> None:
        try:
            opts = self._opts()
        except h2.ConfigError as exc:
            self.app.toast(str(exc))
            return
        self.app.state.last_form = {k: v.get() for k, v in self.vars.items()}
        try:
            self.app.state.save()
        except OSError:
            pass
        if self.app.run_action("run", opts, label=f"sweep {opts.bench}"):
            self.running = True
            self._changed()

    def _judge(self) -> None:
        try:
            opts = self._opts()
        except h2.ConfigError as exc:
            self.app.toast(str(exc))
            return
        self.app.run_action("judge", opts, label="judge")

    def _report(self) -> None:
        try:
            opts = self._opts()
        except h2.ConfigError as exc:
            self.app.toast(str(exc))
            return
        self.app.run_action("report", opts, label="report")

    def _demo(self) -> None:
        try:
            k = int(self.demo_k.get().strip() or "2")
        except ValueError:
            self.app.toast("demo k must be an integer")
            return
        opts = h2.Options(output=self.demo_out.get().strip() or "runs/demo", k=k, demo_mode=self.demo_mode.value)
        self.app.run_action("demo", opts, label="demo")

    def _auto_improve(self) -> None:
        """Run the full auto-improvement loop from the UI."""
        if self.app.stream and self.app.stream.running:
            self.app.toast("A command is already running")
            return
        def runner() -> None:
            try:
                proc = subprocess.Popen(
                    [PYTHON, str(REPO / "scripts" / "auto_improve.py")],
                    cwd=REPO,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    if line:
                        self.app.queue.put(("line", line))
                proc.wait()
                self.app.queue.put(("done", proc.returncode))
            except Exception as exc:  # noqa: BLE001
                self.app.queue.put(("line", f"FAIL: {exc}"))
                self.app.queue.put(("done", 1))

        self.app.log.emit("", "out")
        self.app.log.emit("$ python3 scripts/auto_improve.py", "cmd")
        self.app.log.emit("# cwd " + str(REPO), "dim")
        self._set_state("Running", "primary")
        threading.Thread(target=runner, daemon=True).start()

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        running = bool(self.app.stream and self.app.stream.running)
        if running != self.running:
            self.running = running
            self.stop_btn.set_enabled(running)
            self._changed()
        self.after(600, self._poll)

    def _on_log(self, line: str, tag: str) -> None:
        self.console.append(line, tag)

    def refresh(self) -> None:
        self._changed()

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self.app.log.unsubscribe(self._on_log)
