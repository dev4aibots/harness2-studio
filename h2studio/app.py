"""Harness2 Studio application shell.

One window, one theme, one log bus, one active child process. Views are created
lazily and rebuilt on theme change; they never own global state.
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path

from . import theme as theming
from .palette import CommandPalette
from .services import h2, runs
from .services import state as state_mod
from .widgets import ConfirmDialog, Pill

APP_NAME = "Harness² Studio"
NAV = [
    ("home", "Home", "Status, quick actions, recent commands"),
    ("install", "Install", "Download or update the official Harness² source"),
    ("setup", "Setup", "Install benchmarks and verify the environment"),
    ("run", "Run", "Sweep, judge, and report with full control"),
    ("harness", "Harness", "Inspect and edit the eight components"),
    ("runs", "Runs", "Browse artifacts, tasks, and scores"),
    ("tracker", "Tracker", "Benchmark results and improvement tracker"),
    ("models", "Models", "Wire any coding agent through .env"),
    ("opencode", "OpenCode", "Call OpenCode agents from inside Studio"),
    ("console", "Console", "Full streamed output history"),
    ("guide", "Guide", "Plain-language walkthrough of every feature"),
]

# The Guide opens on the topic that matches whatever screen you were reading.
GUIDE_FOR_VIEW = {
    "home": "overview",
    "install": "install",
    "setup": "benchmarks",
    "run": "sweep",
    "harness": "harness",
    "runs": "runs",
    "tracker": "runs",
    "models": "models",
    "opencode": "models",
    "console": "troubleshooting",
    "guide": "overview",
}


class TaskCancelled(Exception):
    """A long task stopped because the user asked it to."""


class LogBus:
    """Process output buffer with late subscribers, so every view sees history."""

    def __init__(self) -> None:
        self.buffer: list[tuple[str, str]] = []
        self.subs: list[Callable[[str, str], None]] = []

    def emit(self, line: str, tag: str = "out") -> None:
        self.buffer.append((line, tag))
        if len(self.buffer) > 4000:
            del self.buffer[:1000]
        for sub in list(self.subs):
            sub(line, tag)

    def subscribe(self, cb: Callable[[str, str], None], hydrate: bool = True) -> None:
        self.subs.append(cb)
        if hydrate:
            for line, tag in self.buffer[-800:]:
                cb(line, tag)

    def unsubscribe(self, cb) -> None:
        if cb in self.subs:
            self.subs.remove(cb)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__(className="harness2-studio")
        self.state = state_mod.State().load()
        self.theme = theming.Theme(self, self.state.theme, self._initial_scale())
        self.theme.apply()
        self.log = LogBus()
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stream: h2.Stream | None = None
        self.current_action: str | None = None
        self.install = h2.discover(self.state.repo, self.state.python or None)
        self.views: dict[str, tk.Frame] = {}
        self.nav_items: dict[str, tuple[tk.Frame, tk.Label]] = {}
        self.active = "home"
        self._tasks: dict[str, tuple[threading.Event, Callable[[str, object], None]]] = {}

        self.title(APP_NAME)
        self.geometry(self.state.geometry)
        self.minsize(1180, 740)
        self.configure(bg=self.theme.c["surface"])
        try:
            self._icon = tk.PhotoImage(file=str(Path(__file__).resolve().parent / "assets" / "icon.png"))
            self.iconphoto(True, self._icon)
        except (OSError, tk.TclError):
            self._icon = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_shell()
        self._bind_keys()
        self.show("home")
        self.after(50, self._drain)

    # -- shell ----------------------------------------------------------
    def _build_shell(self) -> None:
        c = self.theme.c
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.rail = tk.Frame(self, bg=c["surface_low"], width=236)
        self.rail.grid(row=0, column=0, rowspan=3, sticky="nsw")
        self.rail.grid_propagate(False)
        self._build_rail()

        self.top = tk.Frame(self, bg=c["surface"], height=72)
        self.top.grid(row=0, column=1, sticky="ew")
        self.top.grid_propagate(False)
        self._build_top()

        self.content = tk.Frame(self, bg=c["surface"])
        self.content.grid(row=1, column=1, sticky="nsew")

        self.footer = tk.Frame(self, bg=c["surface_low"], height=30)
        self.footer.grid(row=2, column=1, sticky="ew")
        self.footer.grid_propagate(False)
        self.status_label = tk.Label(self.footer, text="Idle", bg=c["surface_low"],
                                    fg=c["on_surface_variant"], font=self.theme.font("caption"))
        self.status_label.pack(side="left", padx=14)
        self.path_label = tk.Label(self.footer, text=str(self.install.repo), bg=c["surface_low"],
                                   fg=c["on_surface_variant"], font=self.theme.font("caption"))
        self.path_label.pack(side="right", padx=14)

    def _build_rail(self) -> None:
        c = self.theme.c
        brand = tk.Frame(self.rail, bg=c["surface_low"])
        brand.pack(fill="x", padx=18, pady=(20, 10))
        dots = tk.Canvas(brand, width=26, height=26, bg=c["surface_low"], highlightthickness=0)
        dots.pack(side="left")
        for i, color in enumerate(("#4285F4", "#EA4335", "#FBBC05", "#34A853")):
            x = 4 + (i % 2) * 11
            y = 4 + (i // 2) * 11
            dots.create_oval(x, y, x + 9, y + 9, fill=color, outline="")
        tk.Label(brand, text="Harness²", bg=c["surface_low"], fg=c["on_surface"],
                 font=self.theme.font("title")).pack(side="left", padx=(8, 0))

        tk.Label(self.rail, text="STUDIO", bg=c["surface_low"], fg=c["on_surface_variant"],
                 font=self.theme.font("caption")).pack(anchor="w", padx=20, pady=(0, 12))

        for key, label, _sub in NAV:
            row = tk.Frame(self.rail, bg=c["surface_low"], cursor="hand2")
            row.pack(fill="x", padx=10, pady=1)
            accent = tk.Frame(row, bg=c["surface_low"], width=3)
            accent.pack(side="left", fill="y")
            row.accent = accent
            text = tk.Label(row, text=label, bg=c["surface_low"], fg=c["on_surface"],
                            font=self.theme.font("body_lg"), anchor="w", padx=14, pady=9,
                            takefocus=1, highlightthickness=2,
                            highlightbackground=c["surface_low"], highlightcolor=c["primary"])
            text.pack(side="left", fill="x", expand=True)
            text.bind("<Return>", lambda _e, k=key: self.show(k))
            text.bind("<space>", lambda _e, k=key: self.show(k))
            for widget in (row, text):
                widget.bind("<Button-1>", lambda _e, k=key: self.show(k))
            self.nav_items[key] = (row, text)

        tk.Frame(self.rail, bg=c["surface_low"]).pack(fill="both", expand=True)

        self.install_chip = tk.Label(self.rail, text="checking install…", bg=c["surface_container"],
                                     fg=c["on_surface_variant"], font=self.theme.font("caption"),
                                     justify="left", anchor="w", padx=10, pady=8, wraplength=190)
        self.install_chip.pack(fill="x", padx=14, pady=(0, 16))
        self._update_install_chip()

    def _update_install_chip(self) -> None:
        c = self.theme.c
        if self.install.exists():
            text = f"harness2 ready\n{self.install.repo}"
            bg, fg = c["success_container"], c["success"]
        else:
            text = f"checkout missing\n{self.install.repo}"
            bg, fg = c["error_container"], c["on_error_container"]
        self.install_chip.configure(text=text, bg=bg, fg=fg)

    def _build_top(self) -> None:
        c = self.theme.c
        left = tk.Frame(self.top, bg=c["surface"])
        left.pack(side="left", fill="y", padx=(24, 0), pady=14)
        self.title_label = tk.Label(left, text="", bg=c["surface"], fg=c["on_surface"],
                                    font=self.theme.font("headline"), anchor="w")
        self.title_label.pack(anchor="w")
        self.subtitle_label = tk.Label(left, text="", bg=c["surface"], fg=c["on_surface_variant"],
                                       font=self.theme.font("body"), anchor="w")
        self.subtitle_label.pack(anchor="w")

        right = tk.Frame(self.top, bg=c["surface"])
        right.pack(side="right", fill="y", padx=20, pady=16)
        self.state_chip = tk.Label(right, text="Idle", bg=c["surface_high"],
                                   fg=c["on_surface_variant"], font=self.theme.font("caption"),
                                   padx=10, pady=5)
        self.state_chip.pack(side="right", padx=(10, 0))
        self.guide_btn = Pill(right, "Guide", self._open_guide, self.theme,
                              variant="text", height=32, pad=12)
        self.guide_btn.pack(side="right", padx=(4, 0))
        self.theme_btn = Pill(right, "Light" if self.theme.mode == "dark" else "Dark",
                              self.toggle_theme, self.theme, variant="outlined", height=32, pad=12)
        self.theme_btn.pack(side="right")

    def _open_guide(self) -> None:
        previous = self.active
        self.show("guide")
        guide = self.views.get("guide")
        if guide is not None and hasattr(guide, "focus_topic"):
            guide.focus_topic(GUIDE_FOR_VIEW.get(previous, "overview"))

    # -- navigation -----------------------------------------------------
    def show(self, key: str) -> None:
        if key not in {k for k, _l, _s in NAV}:
            return
        subtitle = next(sub for k, _l, sub in NAV if k == key)
        label = next(lbl for k, lbl, _s in NAV if k == key)
        self.active = key
        self.title_label.configure(text=label)
        self.subtitle_label.configure(text=subtitle)
        for k, (row, text) in self.nav_items.items():
            selected = k == key
            bg = self.theme.c["surface_high"] if selected else self.theme.c["surface_low"]
            fg = self.theme.c["on_surface"] if selected else self.theme.c["on_surface_variant"]
            row.configure(bg=bg)
            text.configure(bg=bg, fg=fg, font=self.theme.font("title" if selected else "body_lg"),
                           highlightbackground=bg)
            accent = getattr(row, "accent", None)
            if accent is not None:
                accent.configure(bg=self.theme.c["primary"] if selected else bg)
        view = self.views.get(key)
        if view is None:
            view = self._make_view(key)
            self.views[key] = view
        for child in self.content.winfo_children():
            child.pack_forget()
        view.pack(fill="both", expand=True)
        if hasattr(view, "refresh"):
            view.refresh()

    def _make_view(self, key: str) -> tk.Frame:
        from .views import (
            console,
            guide,
            harness,
            home,
            install,
            models,
            opencode_view,
            run,
            setup,
        )
        from .views import runs as runs_view
        from .views import tracker as tracker_view

        factory = {
            "home": home.HomeView,
            "install": install.InstallView,
            "setup": setup.SetupView,
            "run": run.RunView,
            "harness": harness.HarnessView,
            "runs": runs_view.RunsView,
            "tracker": tracker_view.TrackerView,
            "models": models.ModelsView,
            "opencode": opencode_view.OpenCodeView,
            "console": console.ConsoleView,
            "guide": guide.GuideView,
        }[key]
        return factory(self.content, self)

    # -- theme ----------------------------------------------------------
    def _initial_scale(self) -> float:
        """Honour a saved UI scale, otherwise scale with the display DPI.

        96 DPI stays at 100 %; a 4K laptop at 192 DPI opens at 200 % with
        natively rendered type instead of a blurry compositor upscale.
        """
        saved = float(self.state.ui_scale or 0)
        if saved >= 0.8:
            return saved
        try:
            dpi = float(self.winfo_fpixels("1i"))
        except tk.TclError:
            return 1.0
        return max(1.0, min(2.0, round(dpi / 96, 2)))

    def toggle_theme(self) -> None:
        if not self._safe_to_rebuild():
            return
        self.theme.toggle()
        self.state.theme = self.theme.mode
        try:
            self.state.save()
        except OSError:
            pass
        self._rebuild_ui()

    def _safe_to_rebuild(self) -> bool:
        if self._tasks:
            self.toast("Wait for the running task to finish or cancel it")
            return False
        harness = self.views.get("harness")
        if harness is not None and getattr(harness, "editing", False):
            self.toast("Save or leave edit mode before switching theme or scale")
            return False
        return True

    def _rebuild_ui(self) -> None:
        self._snapshot_drafts()
        self.theme.apply()
        for child in self.winfo_children():
            child.destroy()
        self.views.clear()
        self.nav_items.clear()
        self.configure(bg=self.theme.c["surface"])
        self._build_shell()
        self.show(self.active)

    def _snapshot_drafts(self) -> None:
        run_view = self.views.get("run")
        if run_view is not None and hasattr(run_view, "vars"):
            self.state.last_form = {k: v.get() for k, v in run_view.vars.items()}
        try:
            self.state.save()
        except OSError:
            pass

    def zoom(self, delta: float) -> None:
        if not self._safe_to_rebuild():
            return
        scale = round(min(2.0, max(0.85, self.theme.scale + delta)), 2)
        if abs(scale - self.theme.scale) < 0.001:
            return
        self.state.ui_scale = scale
        self.theme = theming.Theme(self, self.theme.mode, scale)
        self._rebuild_ui()
        self.toast(f"UI scale {int(scale * 100)}%")

    # -- process --------------------------------------------------------
    def run_action(self, action: str, opts: h2.Options, label: str | None = None) -> bool:
        if self.stream and self.stream.running:
            self.toast("A command is already running")
            return False
        if not self.install.exists():
            self.toast("Harness² checkout not found")
            self.log.emit(f"FAIL: no harness2 checkout at {self.install.repo}", "err")
            return False
        try:
            argv = h2.full_argv(self.install, action, opts)
        except h2.ConfigError as exc:
            self.toast(str(exc))
            self.log.emit(f"FAIL: {exc}", "err")
            return False
        env = h2.merged_env(self.install)
        self.current_action = action
        try:
            state_mod.remember_command(" ".join(argv))
            self.state.recent = state_mod.State().load().recent
        except OSError:
            pass
        self.log.emit("", "out")
        self.log.emit("$ " + " ".join(argv), "cmd")
        self.log.emit(f"# cwd {self.install.repo}  ({label or action})", "dim")
        self._set_state("Running", "primary")
        try:
            self.stream = h2.Stream(
                argv=argv,
                cwd=self.install.repo,
                env=env,
                on_line=lambda line: self.queue.put(("line", line)),
                on_done=lambda code: self.queue.put(("done", code)),
            ).start()
        except OSError as exc:
            self.stream = None
            self._set_state("Idle", "neutral")
            self.log.emit(f"FAIL: cannot start: {exc}", "err")
            self.toast(f"Cannot start: {exc}")
            return False
        return True

    def stop_action(self) -> None:
        if self.stream and self.stream.running:
            self.stream.stop()
            self.log.emit("^C stop requested", "warn")

    def _drain(self) -> None:
        """Move worker-thread output onto the Tk main loop; Tk is not thread-safe."""
        if not self.winfo_exists():
            return
        try:
            while True:
                try:
                    kind, payload = self.queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    if kind == "line":
                        self.log.emit(str(payload), classify(str(payload)))
                    elif kind == "done":
                        self._finish(int(payload))
                    elif kind == "bg":
                        callback, result = payload
                        if callable(callback):
                            callback(result)
                    elif kind == "task":
                        key, event, result = payload
                        entry = self._tasks.get(key)
                        if entry is None:
                            continue
                        _cancel, handler = entry
                        if event in {"done", "error", "cancelled"}:
                            # Pop first: handlers call task_running() to re-enable controls.
                            self._tasks.pop(key, None)
                        handler(str(event), result)
                except Exception as exc:  # noqa: BLE001 - one bad callback must not stop the pump
                    try:
                        self.log.emit(f"WARN: ui callback ({kind}): {exc}", "warn")
                    except Exception:  # noqa: BLE001, S110 - even the logger can fail
                        pass
        finally:
            if self.winfo_exists():
                self.after(50, self._drain)

    def _finish(self, code: int) -> None:
        self._set_state("Done" if code == 0 else "Failed", "success" if code == 0 else "error")
        tag = "ok" if code == 0 else "err"
        self.log.emit(f"[exit {code}]", tag)
        self.toast("Finished" if code == 0 else f"Exited with {code}")
        for view in self.views.values():
            if hasattr(view, "refresh"):
                try:
                    view.refresh()
                except Exception as exc:  # noqa: BLE001 - one panel must not kill the app
                    self.log.emit(f"WARN: refresh {type(view).__name__}: {exc}", "warn")

    def _set_state(self, text: str, tone: str) -> None:
        c = self.theme.c
        bg = {"primary": c["primary_container"], "success": c["success_container"],
              "error": c["error_container"], "neutral": c["surface_high"]}.get(tone, c["surface_high"])
        fg = {"primary": c["on_primary_container"], "success": c["success"],
              "error": c["on_error_container"], "neutral": c["on_surface_variant"]}.get(tone, c["on_surface_variant"])
        self.state_chip.configure(text=text, bg=bg, fg=fg)

    # -- helpers --------------------------------------------------------
    def toast(self, message: str) -> None:
        c = self.theme.c
        lab = tk.Label(self, text=message, bg=c["on_surface"], fg=c["surface"],
                       font=self.theme.font("label"), padx=16, pady=9)
        lab.place(relx=0.5, rely=1.02, anchor="s")

        def slide(step: int = 0) -> None:
            if not lab.winfo_exists():
                return
            rely = 1.02 - 0.055 * min(step, 4) / 4
            lab.place_configure(rely=rely)
            if step < 4:
                self.after(24, lambda: slide(step + 1))

        slide()
        self.after(2600, lab.destroy)

    def open_path(self, path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif os.uname().sysname == "Darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # noqa: BLE001 - xdg-open/open failures vary by platform
            self.toast(f"Cannot open: {exc}")

    def artifacts(self) -> list[runs.Artifact]:
        root = h2.read_env(self.install.env_file).get("HARNESS2_RUNS_DIR") or str(self.install.runs_default)
        path = self.install.repo / root if not os.path.isabs(root) else root
        return runs.scan(path)

    def _bind_keys(self) -> None:
        for idx, (key, _l, _s) in enumerate(NAV, start=1):
            if idx > 9:
                continue  # Tk only supports Control-Key-1 through Control-Key-9
            self.bind_all(f"<Control-Key-{idx}>", lambda _e, k=key: self.show(k))
        self.bind_all("<Control-k>", lambda _e: self.open_palette())
        self.bind_all("<Control-K>", lambda _e: self.open_palette())
        self.bind_all("<Control-equal>", lambda _e: self.zoom(0.1))
        self.bind_all("<Control-plus>", lambda _e: self.zoom(0.1))
        self.bind_all("<Control-minus>", lambda _e: self.zoom(-0.1))
        self.bind_all("<Control-0>", lambda _e: self.zoom(1.0 - self.theme.scale))
        self.bind_all("<Control-r>", lambda _e: self.show("run"))
        self.bind_class("Entry", "<Control-a>", self._select_all_entry)
        self.bind_class("Text", "<Control-a>", self._select_all_text)
        self.bind_all("<Control-Return>", lambda _e: self._trigger_primary())
        self.bind_all("<F5>", lambda _e: self._refresh_active())
        self.bind_all("<Escape>", lambda _e: self._on_escape())

    @staticmethod
    def _select_all_entry(event) -> str:
        event.widget.select_range(0, "end")
        event.widget.icursor("end")
        return "break"

    @staticmethod
    def _select_all_text(event) -> str:
        event.widget.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _on_escape(self) -> None:
        if not (self.stream and self.stream.running):
            return
        ConfirmDialog(self, self.theme, "Stop the running command?",
                      "This sends SIGTERM to the whole process group, then SIGKILL after 3 seconds. "
                      "Partial results stay on disk and the same command resumes.",
                      "Stop", self.stop_action)

    def _trigger_primary(self) -> None:
        view = self.views.get(self.active)
        action = getattr(view, "on_primary", None)
        if callable(action):
            action()

    # -- command palette -----------------------------------------------
    def open_palette(self) -> None:
        existing = getattr(self, "_palette", None)
        if existing is not None and existing.winfo_exists():
            existing.close()
            self._palette = None
            return
        self._palette = CommandPalette(self, self.theme, self._palette_actions())

    def _palette_actions(self):
        acts = [(f"Go to {label}", sub, lambda k=key: self.show(k)) for key, label, sub in NAV]
        acts += [
            ("Run demo", "credential-free pipeline check", self._palette_demo),
            ("Check environment", "harness2-check on current benchmark", self._palette_check),
            ("Refresh view", "F5", self._refresh_active),
            ("Toggle theme", "light / dark", self.toggle_theme),
            ("Open runs folder", str(self.install.runs_default), lambda: self.open_path(self.install.runs_default)),
            ("Copy diagnostics", "repo, interpreter, wired keys", self._copy_diagnostics),
        ]
        return acts

    def _palette_demo(self) -> None:
        self.show("run")
        self.run_action("demo", h2.Options(output="runs/demo", k=2), label="demo")

    def _palette_check(self) -> None:
        self.show("setup")

    def after_bg(self, work, done) -> None:
        """Run slow, non-Tk work off the UI thread and deliver the result on it."""
        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001 - handed to the caller on the UI thread
                result = exc
            self.queue.put(("bg", (done, result)))

        threading.Thread(target=runner, daemon=True).start()

    # -- cancellable background tasks ----------------------------------
    def start_task(self, key: str, work, handler: Callable[[str, object], None]):
        """Run ``work(report, cancel)`` off-thread; stream progress to ``handler``.

        ``report(phase, done, total, detail)`` is thread-safe and coalesced on the
        Tk loop. The handler receives ``("progress", tuple)``, then exactly one of
        ``done`` (return value), ``error`` (exception), or ``cancelled``.
        """
        if key in self._tasks:
            self.toast("That task is already running")
            return None
        cancel = threading.Event()
        self._tasks[key] = (cancel, handler)

        def runner() -> None:
            def report(phase: str, done: int, total: int, detail: str = "") -> None:
                self.queue.put(("task", (key, "progress", (phase, done, total, detail))))

            try:
                result = work(report, cancel)
            except TaskCancelled:
                self.queue.put(("task", (key, "cancelled", None)))
            except Exception as exc:  # noqa: BLE001 - shown on the UI thread
                self.queue.put(("task", (key, "error", exc)))
            else:
                self.queue.put(("task", (key, "done", result)))

        threading.Thread(target=runner, daemon=True, name=f"studio-{key}").start()
        return cancel

    def cancel_task(self, key: str) -> None:
        entry = self._tasks.get(key)
        if entry is None:
            return
        entry[0].set()
        self.toast("Stopping after the current file…")

    def task_running(self, key: str | None = None) -> bool:
        if key is None:
            return bool(self._tasks)
        return key in self._tasks

    def adopt_install(self, path) -> bool:
        """Point the whole app at a verified checkout and rebuild every panel."""
        import sys

        target = Path(path).expanduser().resolve()
        candidate = h2.discover(target, self.state.python or None)
        if not candidate.exists():
            fallback = h2.discover(target, sys.executable)
            if fallback.exists():
                candidate = fallback
        if not candidate.exists():
            self.toast("That folder is not a Harness² checkout")
            self.log.emit(f"FAIL: not a Harness² checkout: {target}", "err")
            return False
        self.install = candidate
        self.state.repo = str(target)
        self.state.install_dest = str(target)
        try:
            self.state.save()
        except OSError as exc:
            self.log.emit(f"WARN: could not save the checkout path: {exc}", "warn")
        self.log.emit(f"OK: using Harness² at {target}", "ok")
        self._rebuild_ui()
        self.toast("Harness² checkout updated")
        return True

    def _copy_diagnostics(self) -> None:
        env = h2.read_env(self.install.env_file)
        wired = sorted(k for k in env if k.startswith(("HARNESS2_", "GOOGLE_CLOUD_")))
        text = "\n".join([
            f"repo: {self.install.repo}",
            f"python: {self.install.python}",
            f"runs: {self.install.runs_default}",
            f"env keys: {', '.join(wired) or 'none'}",
            f"artifacts: {len(self.artifacts())}",
        ])
        self.clipboard_clear()
        self.clipboard_append(text)
        self.toast("Diagnostics copied")

    def _refresh_active(self) -> None:
        view = self.views.get(self.active)
        if view is not None and hasattr(view, "refresh"):
            view.refresh()

    def _on_close(self) -> None:
        self.state.geometry = self.geometry()
        try:
            self.state.save()
        except OSError:
            pass
        for cancel, _handler in list(self._tasks.values()):
            cancel.set()
        self.stop_action()
        self.after(200, self.destroy)


def main() -> None:
    import sys

    app = App()
    if "--check" in sys.argv[1:]:
        app.update_idletasks()
        app.destroy()
        print("Harness² Studio constructed and destroyed cleanly")
        return
    app.mainloop()


def classify(line: str) -> str:
    low = line.lower().strip()
    if low.startswith(("fail:", "error", "traceback", "exception")):
        return "err"
    if low.startswith(("warn", "warning")):
        return "warn"
    if low.startswith(("ok:", "setup complete", "success")) or " completed" in low:
        return "ok"
    if low.startswith(("[", "#")):
        return "dim"
    return "out"
