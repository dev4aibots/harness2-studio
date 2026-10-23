"""OpenCode: call OpenCode agents directly from inside Harness² Studio.

Use this to let OpenCode improve your harnesses, write code, debug failures,
or run any agent task — all without leaving the Studio UI.
"""

from __future__ import annotations

import subprocess
import threading
import tkinter as tk

from ..widgets import Card, Console, Pill
from .base import View


class OpenCodeView(View):
    """A full OpenCode agent terminal embedded inside Studio."""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme

        body = tk.Frame(self, bg=t.c["surface"])
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(1, weight=1)

        # -- left: prompt / controls ------------------------------------
        left = Card(body, t, title="OpenCode Agent")
        left.grid(row=0, column=0, sticky="nsew")
        lf = left.content

        tk.Label(lf, text="Prompt", bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                 font=t.font("label"), anchor="w").pack(fill="x", pady=(0, 4))
        self.prompt = tk.Text(lf, height=6, wrap="word", bd=0, highlightthickness=1,
                              bg=t.c["surface_low"], fg=t.c["on_surface"],
                              insertbackground=t.c["on_surface"], font=t.font("body"),
                              padx=10, pady=8)
        self.prompt.pack(fill="x", pady=(0, 8))
        self.prompt.insert("1.0", "Improve the Harness² C1 system prompt based on the latest failures. "
                                  "Make it more rigorous, add more edge case handling, "
                                  "and ensure every function has type annotations and docstrings.")

        opts = tk.Frame(lf, bg=t.c["surface_container"])
        opts.pack(fill="x", pady=(0, 8))
        tk.Label(opts, text="Working directory", bg=t.c["surface_container"],
                 fg=t.c["on_surface_variant"], font=t.font("caption"), anchor="w").pack(side="left")
        self.cwd_var = tk.StringVar(value=str(self.app.install.repo))
        self.cwd_entry = tk.Entry(opts, textvariable=self.cwd_var, font=t.font("body"),
                                  bg=t.c["surface_low"], fg=t.c["on_surface"], insertbackground=t.c["on_surface"])
        self.cwd_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

        tk.Label(opts, text="Model", bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                 font=t.font("caption"), anchor="w").pack(side="left", padx=(10, 4))
        self.model_var = tk.StringVar(value="opencode/opus-5.5")
        self.model_entry = tk.Entry(opts, textvariable=self.model_var, font=t.font("body"),
                                    bg=t.c["surface_low"], fg=t.c["on_surface"], insertbackground=t.c["on_surface"])
        self.model_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        actions = tk.Frame(lf, bg=t.c["surface_container"])
        actions.pack(fill="x", pady=(8, 0))
        self.run_btn = Pill(actions, "Run OpenCode", self._run_opencode, t, "filled")
        self.run_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = Pill(actions, "Stop", self._stop_opencode, t, "danger", height=34, pad=14)
        self.stop_btn.pack(side="left", padx=(0, 8))
        self.stop_btn.set_enabled(False)

        self.auto_var = tk.BooleanVar(value=True)
        self.auto_cb = tk.Checkbutton(lf, text="Auto-approve permissions", variable=self.auto_var,
                                      bg=t.c["surface_container"], fg=t.c["on_surface"],
                                      selectcolor=t.c["surface_low"], activebackground=t.c["surface_container"],
                                      activeforeground=t.c["on_surface"], font=t.font("caption"))
        self.auto_cb.pack(fill="x", pady=(4, 0))

        # -- right: output console --------------------------------------
        right = Card(body, t, title="OpenCode Output", subtitle="Live agent stream")
        right.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        self.console = Console(right.content, t, height=30)
        self.console.pack(fill="both", expand=True)

        # -- state ------------------------------------------------------
        self.opencode_proc: subprocess.Popen | None = None
        self.app.log.subscribe(self._on_log)
        self.bind("<Destroy>", self._on_destroy)

        self._refresh_opencode_available()

    def _refresh_opencode_available(self) -> None:
        import shutil
        oc = shutil.which("opencode")
        if oc:
            self.console.append(f"OpenCode found at: {oc}", "ok")
        else:
            self.console.append("OpenCode not found on PATH", "err")

    def _on_log(self, line: str, tag: str) -> None:
        self.console.append(line, tag)

    def _on_destroy(self, event) -> None:
        if event.widget is not self:
            return
        self.app.log.unsubscribe(self._on_log)
        if self.opencode_proc is not None:
            try:
                self.opencode_proc.terminate()
            except (OSError, ProcessLookupError):
                pass

    # -- actions --------------------------------------------------------
    def _run_opencode(self) -> None:
        if self.opencode_proc is not None:
            self.app.toast("OpenCode already running")
            return

        prompt = self.prompt.get("1.0", "end-1c").strip()
        if not prompt:
            self.app.toast("Prompt is empty")
            return

        cwd = self.cwd_var.get().strip()
        model = self.model_var.get().strip()
        auto = self.auto_var.get()

        import shutil
        oc = shutil.which("opencode")
        if oc is None:
            self.app.toast("OpenCode not found on PATH")
            self.console.append("OpenCode not found on PATH", "err")
            return

        cmd = [oc, "--auto" if auto else "", "--prompt", prompt]
        cmd = [c for c in cmd if c]  # remove empty strings

        self.app.log.emit("", "out")
        self.app.log.emit("$ " + " ".join(cmd), "cmd")
        self.app.log.emit(f"# cwd {cwd}", "dim")

        self.console.append(f"Running OpenCode: {' '.join(cmd)}", "cmd")
        self.console.append(f"Working directory: {cwd}", "dim")
        self.console.append(f"Model: {model}", "dim")
        self.console.append("-" * 60, "dim")

        self.run_btn.set_enabled(False)
        self.stop_btn.set_enabled(True)

        env = dict(self.app.state.env if hasattr(self.app.state, "env") else {})
        env.update({
            "OPENCODE_MODEL": model,
            "HARNESS2_SOLVER_MODEL": self.app.state.models_draft.get("HARNESS2_SOLVER_MODEL", "")
            if hasattr(self.app.state, "models_draft") else "",
        })

        def runner() -> None:
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                )
                self.opencode_proc = proc
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    if line:
                        self.app.queue.put(("line", line))
                proc.wait()
                self.app.queue.put(("done", proc.returncode))
            except Exception as exc:  # noqa: BLE001
                self.app.queue.put(("line", f"FAIL: {exc}"))
                self.app.queue.put(("done", 1))

        threading.Thread(target=runner, daemon=True).start()

    def _stop_opencode(self) -> None:
        if self.opencode_proc is not None:
            try:
                self.opencode_proc.terminate()
                self.console.append("Stopping OpenCode...", "warn")
            except (OSError, ProcessLookupError) as exc:
                self.console.append(f"Cannot stop: {exc}", "err")
        self.run_btn.set_enabled(True)
        self.stop_btn.set_enabled(False)

    def _finish(self, code: int) -> None:
        self.opencode_proc = None
        self.run_btn.set_enabled(True)
        self.stop_btn.set_enabled(False)
        tag = "ok" if code == 0 else "err"
        self.app.log.emit(f"[OpenCode exit {code}]", tag)
        self.console.append(f"[OpenCode exit {code}]", tag)
        self.app.toast("OpenCode finished" if code == 0 else f"OpenCode exited {code}")
