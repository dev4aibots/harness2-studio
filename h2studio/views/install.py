"""Install: fetch, verify, and update the upstream Harness² checkout."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, ttk

from ..services import installer
from ..widgets import Card, Pill, ProgressBar, Scroller
from .base import View

PHASE_LABEL = {
    "check": "Checking GitHub",
    "backup": "Preserving local edits",
    "download": "Downloading source",
    "environment": "Creating the Python environment",
    "verify": "Verifying the import",
    "extras": "Installing optional packages",
}
PHASE_WEIGHT = {
    "check": (0.00, 0.05),
    "backup": (0.05, 0.10),
    "download": (0.10, 0.82),
    "environment": (0.82, 0.94),
    "verify": (0.94, 1.00),
}
TONE = {
    "success": ("success_container", "success"),
    "warning": ("surface_high", "warning"),
    "error": ("error_container", "on_error_container"),
    "primary": ("primary_container", "on_primary_container"),
    "neutral": ("surface_high", "on_surface_variant"),
}


class InstallView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.latest = self._cached_latest()
        self.check_error = ""
        self.active_task: str | None = None
        self._last_phase: str | None = None
        self._last_bucket = -1
        self.extras_labels: dict[str, tk.Label] = {}
        self._buttons: list[Pill] = []
        self._extras_buttons: dict[str, Pill] = {}

        start = app.state.install_dest or str(app.install.repo)
        self.dest_var = tk.StringVar(value=start)
        self.python_var = tk.StringVar(value=app.state.python or sys.executable)

        scroll = Scroller(self, t)
        scroll.pack(fill="both", expand=True)
        root = tk.Frame(scroll.inner, bg=t.c["surface"])
        root.pack(fill="both", expand=True, padx=28, pady=24)

        hero = Card(root, t, pad=26)
        hero.pack(fill="x")
        tk.Label(hero.content, text="The official source, kept current",
                 bg=t.c["surface_container"], fg=t.c["on_surface"],
                 font=t.font("title_lg"), anchor="w").pack(fill="x")
        tk.Label(
            hero.content,
            text=("Studio downloads google-research/harness2 directly from GitHub, verifies every file "
                  "against its published hash, and creates a private Python environment. No git, no "
                  "global installs. Updating replaces only changed files and backs up local edits first."),
            bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("body"),
            anchor="w", justify="left", wraplength=860,
        ).pack(fill="x", pady=(6, 16))

        path_row = tk.Frame(hero.content, bg=t.c["surface_container"])
        path_row.pack(fill="x", pady=(0, 8))
        tk.Label(path_row, text="Folder", width=9, anchor="w", bg=t.c["surface_container"],
                 fg=t.c["on_surface_variant"], font=t.font("label")).pack(side="left")
        self.path_entry = ttk.Entry(path_row, textvariable=self.dest_var)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.browse_btn = Pill(path_row, "Browse", self._browse_dir, t, "outlined", height=34, pad=12)
        self.browse_btn.pack(side="left", padx=(0, 6))
        self.use_btn = Pill(path_row, "Use this folder", self._adopt, t, "tonal", height=34, pad=12)
        self.use_btn.pack(side="left")
        self._buttons += [self.browse_btn, self.use_btn]

        py_row = tk.Frame(hero.content, bg=t.c["surface_container"])
        py_row.pack(fill="x", pady=(0, 12))
        tk.Label(py_row, text="Python", width=9, anchor="w", bg=t.c["surface_container"],
                 fg=t.c["on_surface_variant"], font=t.font("label")).pack(side="left")
        self.python_entry = ttk.Entry(py_row, textvariable=self.python_var)
        self.python_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.python_btn = Pill(py_row, "Choose", self._browse_python, t, "outlined", height=34, pad=12)
        self.python_btn.pack(side="left")
        self._buttons.append(self.python_btn)
        tk.Label(hero.content, text="Harness² needs Python 3.12 or 3.13. Studio creates .venv inside the folder.",
                 bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("caption"),
                 anchor="w").pack(fill="x", pady=(0, 10))

        actions = tk.Frame(hero.content, bg=t.c["surface_container"])
        actions.pack(fill="x")
        self.check_btn = Pill(actions, "Check for updates", self._check, t, "outlined")
        self.check_btn.pack(side="left", padx=(0, 8))
        self.install_btn = Pill(actions, "Install latest", self._install, t, "filled")
        self.install_btn.pack(side="left", padx=(0, 8))
        self.verify_btn = Pill(actions, "Verify", self._verify, t, "tonal")
        self.verify_btn.pack(side="left", padx=(0, 8))
        self.open_btn = Pill(actions, "Open folder", self._open, t, "text")
        self.open_btn.pack(side="left")
        self._buttons += [self.check_btn, self.install_btn, self.verify_btn]

        status_row = tk.Frame(hero.content, bg=t.c["surface_container"])
        status_row.pack(fill="x", pady=(16, 0))
        self.status_label = tk.Label(status_row, text="Not installed", font=t.font("label"),
                                     padx=10, pady=5)
        self.status_label.pack(side="left")
        self.meta_label = tk.Label(hero.content, text="", bg=t.c["surface_container"],
                                   fg=t.c["on_surface_variant"], font=t.font("caption"),
                                   anchor="w", justify="left", wraplength=860)
        self.meta_label.pack(fill="x", pady=(8, 0))

        progress = Card(root, t, title="Activity", subtitle="Long work streams here; the exact output goes to Console.")
        progress.pack(fill="x", pady=(18, 0))
        self.phase_label = tk.Label(progress.content, text="Nothing running",
                                    bg=t.c["surface_container"], fg=t.c["on_surface"],
                                    font=t.font("title"), anchor="w")
        self.phase_label.pack(fill="x")
        self.bar = ProgressBar(progress.content, t)
        self.bar.pack(fill="x", pady=(8, 6))
        detail_row = tk.Frame(progress.content, bg=t.c["surface_container"])
        detail_row.pack(fill="x")
        self.detail_label = tk.Label(detail_row, text=(
            "Install downloads about 850 KB of source. The first check asks GitHub for the current commit."),
            bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("caption"),
            anchor="w", justify="left", wraplength=700)
        self.detail_label.pack(side="left", fill="x", expand=True)
        self.cancel_btn = Pill(detail_row, "Cancel", self._cancel, t, "danger", height=32, pad=12)
        self.cancel_btn.pack_forget()
        tk.Label(progress.content, text="Downloads resume from the partial file; every file is hash-checked.",
                 bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("caption"),
                 anchor="w").pack(fill="x", pady=(8, 0))

        lower = tk.Frame(root, bg=t.c["surface"])
        lower.pack(fill="x", pady=(18, 20))
        lower.grid_columnconfigure(0, weight=1)
        lower.grid_columnconfigure(1, weight=1)

        facts = Card(lower, t, title="What gets installed")
        facts.grid(row=0, column=0, sticky="nsew")
        for text in (
            "Source, docs and tests — about 850 KB, no demo videos.",
            "Every blob checked against GitHub's SHA-1 and written atomically.",
            "A private .venv; no global packages are touched.",
            "Local edits backed up to .harness2-studio-backups before updates.",
            "Your runs/ folder and .env are never overwritten by an update.",
        ):
            row = tk.Frame(facts.content, bg=t.c["surface_container"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text="•", bg=t.c["surface_container"], fg=t.c["primary"],
                     font=t.font("body")).pack(side="left", anchor="n")
            tk.Label(row, text=text, bg=t.c["surface_container"], fg=t.c["on_surface"],
                     font=t.font("body"), anchor="w", justify="left", wraplength=510).pack(
                side="left", fill="x", expand=True, padx=(8, 0))

        extras = Card(lower, t, title="Optional packages",
                      subtitle="Only needed for WorkBuddy rendering and the Codex bridge.")
        extras.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        for group, title, detail in (
            ("render", "Render extras", "openpyxl + python-pptx for Office artifacts"),
            ("bridge", "Bridge extras", "litellm, FastAPI and google-auth for Codex"),
        ):
            row = tk.Frame(extras.content, bg=t.c["surface_container"])
            row.pack(fill="x", pady=(0, 10))
            left = tk.Frame(row, bg=t.c["surface_container"])
            left.pack(side="left", fill="x", expand=True)
            tk.Label(left, text=title, bg=t.c["surface_container"], fg=t.c["on_surface"],
                     font=t.font("label"), anchor="w").pack(fill="x")
            tk.Label(left, text=detail, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("caption"), anchor="w").pack(fill="x")
            status = tk.Label(left, text="Checking…", bg=t.c["surface_container"],
                              fg=t.c["on_surface_variant"], font=t.font("caption"), anchor="w")
            status.pack(fill="x", pady=(2, 0))
            self.extras_labels[group] = status
            button = Pill(row, "Install", lambda g=group: self._install_extras(g), t,
                          "outlined", height=32, pad=12)
            button.pack(side="right", anchor="n")
            self._extras_buttons[group] = button
            self._buttons.append(button)

        tk.Label(extras.content, text="pip runs only inside this checkout's .venv. Network and disk space apply.",
                 bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("caption"),
                 anchor="w", justify="left", wraplength=480).pack(fill="x", pady=(4, 0))

        self.dest_var.trace_add("write", lambda *_a: self._refresh_status())
        self._refresh_status()
        self._set_running_ui()
        self.after(500, self._auto_check)
        self.after(120, self._refresh_extras)

    # -- small helpers --------------------------------------------------
    def _cached_latest(self):
        raw = dict(self.app.state.upstream) if isinstance(self.app.state.upstream, dict) else {}
        if raw.get("repo") != installer.REPO or not raw.get("sha"):
            return None
        try:
            return installer.CommitInfo(
                sha=str(raw["sha"]), date=str(raw.get("date", "")),
                message=str(raw.get("message", "")),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _store_latest(self, commit) -> None:
        self.app.state.upstream = {
            "repo": installer.REPO,
            "sha": commit.sha,
            "date": commit.date,
            "message": commit.message,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            self.app.state.save()
        except OSError:
            pass

    def _dest(self) -> Path:
        raw = self.dest_var.get().strip() or str(self.app.install.repo)
        return Path(raw).expanduser()

    def _alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _is_checkout(self, dest: Path) -> bool:
        pyproject = dest / "pyproject.toml"
        if not pyproject.is_file():
            return False
        try:
            text = pyproject.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return 'name = "harness2"' in text or "name = 'harness2'" in text

    def _set_status(self, text: str, tone: str) -> None:
        bg, fg = TONE.get(tone, TONE["neutral"])
        self.status_label.configure(text=text, bg=self.theme.c[bg], fg=self.theme.c[fg])

    def _phase(self, title: str, detail: str = "", fraction: float | None = None) -> None:
        self.phase_label.configure(text=title)
        if detail:
            self.detail_label.configure(text=detail)
        if fraction is not None:
            self.bar.set(fraction)

    def _refresh_status(self) -> None:
        dest = self._dest()
        exists = dest.is_dir()
        checkout = self._is_checkout(dest)
        marker = installer.read_marker(dest) if exists else None
        nonempty = False
        if exists:
            try:
                nonempty = next(dest.iterdir(), None) is not None
            except OSError:
                nonempty = False

        if checkout and marker and self.latest:
            if marker.commit and marker.commit != self.latest.sha:
                self._set_status("Update available", "primary")
            else:
                self._set_status("Up to date", "success")
        elif checkout and marker:
            self._set_status("Installed", "success")
        elif checkout:
            self._set_status("Existing checkout", "warning")
        elif exists and nonempty:
            self._set_status("Folder not empty", "warning")
        else:
            self._set_status("Not installed", "neutral")

        parts: list[str] = []
        if marker:
            installed = marker.commit[:8] if marker.commit else "unknown commit"
            parts.append(f"Installed {installed} · version {marker.version or 'unknown'}"
                         + (f" · {marker.installed_at[:10]}" if marker.installed_at else ""))
        if self.latest:
            parts.append(f"Latest {self.latest.sha[:8]} · {self.latest.date[:10]} · {self.latest.message}")
        if self.check_error:
            parts.append(f"Last check failed: {self.check_error}")
        if checkout and not marker:
            parts.append("This checkout was not installed by Studio. Updating adopts it and keeps backups.")
        elif exists and nonempty and not checkout:
            parts.append("Choose an empty folder, or a folder that already contains a Harness² checkout.")
        elif not exists:
            parts.append("The folder will be created. Press Install latest to begin.")
        self.meta_label.configure(text="\n".join(parts))

        update = bool(marker and self.latest and marker.commit and marker.commit != self.latest.sha)
        self.install_btn.set_text("Update latest" if update else "Install latest")
        venv = installer.venv_python(dest)
        self.verify_btn.set_enabled(checkout and venv.is_file() and not self.app.task_running())
        self.use_btn.set_enabled(checkout and not self.app.task_running())
        for button in self._extras_buttons.values():
            button.set_enabled(checkout and venv.is_file() and not self.app.task_running())

    def _set_running_ui(self) -> None:
        busy = self.app.task_running()
        for button in self._buttons:
            button.set_enabled(not busy)
        state = "disabled" if busy else "normal"
        try:
            self.path_entry.configure(state=state)
            self.python_entry.configure(state=state)
        except tk.TclError:
            pass
        cancellable = {"install", "extras-render", "extras-bridge"}
        if self.active_task in cancellable and busy:
            self.cancel_btn.set_enabled(True)
            self.cancel_btn.pack(side="right", padx=(10, 0))
        else:
            self.cancel_btn.pack_forget()
        self._refresh_status()
        if not busy:
            self.install_btn.set_enabled(True)

    def _fraction(self, phase: str, done: int, total: int) -> float:
        lo, hi = PHASE_WEIGHT.get(phase, (0.0, 1.0))
        portion = 1.0 if total <= 0 else max(0.0, min(1.0, done / total))
        if phase in {"check", "environment", "verify"} and done >= total:
            portion = 1.0
        return lo + (hi - lo) * portion

    def _on_progress(self, phase: str, done: int, total: int, detail: str) -> None:
        title = PHASE_LABEL.get(phase, phase.title())
        if phase in {"download", "backup"}:
            title = f"{title} · {done}/{total}"
        self._phase(title, detail or "Working…", self._fraction(phase, done, total))
        bucket = int(self._fraction(phase, done, total) * 10)
        if phase != self._last_phase or bucket != self._last_bucket:
            self._last_phase, self._last_bucket = phase, bucket
            self.app.log.emit(f"[install] {title} · {detail}" if detail else f"[install] {title}", "dim")

    # -- upstream check -------------------------------------------------
    def _auto_check(self) -> None:
        if not self._alive() or not self.winfo_ismapped():
            return
        if os.environ.get("H2STUDIO_OFFLINE") == "1" or self.latest is not None:
            return
        if self.app.task_running():
            return
        self._check(manual=False)

    def _check(self, manual: bool = True) -> None:
        if self.app.task_running():
            self.app.toast("Wait for the running task to finish")
            return
        if manual:
            self.app.log.emit("$ check latest Harness² upstream", "cmd")
        self.active_task = "check"
        self._set_running_ui()
        self._phase("Checking GitHub", "Reading the latest commit on main and its file list…", 0.03)
        self.app._set_state("Checking", "primary")
        token = os.environ.get("GITHUB_TOKEN", "")

        def work(_report, _cancel):
            return installer.latest_commit(installer.UrllibFetcher(token=token))

        def handler(event: str, payload) -> None:
            if event == "progress":
                return
            self.active_task = None
            if event == "done":
                self.latest = payload
                self.check_error = ""
                self._store_latest(payload)
                self.app.log.emit(
                    f"OK: latest upstream {payload.sha[:8]} · {payload.date[:10]} · {payload.message}", "ok"
                )
                self._phase("Check complete", f"Latest commit {payload.sha[:8]} · {payload.message}", 0.05)
                self.app.toast("Upstream is reachable")
            else:
                self.check_error = str(payload)
                self.app.log.emit(f"FAIL: could not check upstream: {payload}", "err")
                self._phase("Could not check", "Use the existing checkout, or retry when GitHub is reachable.",
                            0.0)
                self.app.toast("GitHub check failed")
                self.app._set_state("Idle", "neutral")
            self._set_running_ui()

        self.app.start_task("check", work, handler)

    # -- install / verify ----------------------------------------------
    def _install(self) -> None:
        if self.app.task_running():
            self.app.toast("Wait for the running task to finish")
            return
        dest = self._dest()
        python = Path(self.python_var.get().strip() or sys.executable).expanduser()
        if not python.is_file():
            self.app.toast("Choose a Python interpreter that exists")
            return
        try:
            installer.check_python_version(python)
            installer.assert_installable(dest)
        except installer.InstallError as exc:
            self.app.log.emit(f"FAIL: {exc}", "err")
            self.app.toast(str(exc))
            return

        self.active_task = "install"
        self._last_phase, self._last_bucket = None, -1
        self._phase("Starting install", f"Target {dest}", 0.0)
        self.app.log.emit("", "out")
        self.app.log.emit(f"$ install Harness² into {dest}", "cmd")
        self.app.log.emit(f"# interpreter {python}", "dim")
        self._set_running_ui()
        self.app._set_state("Installing", "primary")

        def work(report, cancel):
            from ..app import TaskCancelled

            try:
                return installer.install(
                    dest, progress=report, cancel=cancel, python=str(python), make_environment=True,
                )
            except installer.InstallCancelled as exc:
                raise TaskCancelled(str(exc)) from None

        def handler(event: str, payload) -> None:
            if event == "progress":
                self._on_progress(*payload)
                return
            self.active_task = None
            if event == "done":
                self._phase("Installed", f"Version {payload.version or 'unknown'} · {payload.installed} files updated",
                            1.0)
                self.app.log.emit(
                    f"OK: Harness² installed at {dest} · {payload.installed} files · version "
                    f"{payload.version or 'unknown'}", "ok"
                )
                if payload.backed_up:
                    self.app.log.emit(
                        f"OK: preserved {len(payload.backed_up)} local edit(s) under "
                        f"{dest / installer.BACKUPS}", "ok"
                    )
                self.app.toast("Harness² installed")
                self._refresh_status()
                self.app._set_state("Idle", "neutral")
                self.app.after(500, lambda p=dest: self.app.adopt_install(p))
            elif event == "cancelled":
                self._phase("Cancelled", "Partial downloads are kept; press Install latest to resume.", 0.0)
                self.app.log.emit("WARN: install cancelled; partial files resume next time", "warn")
                self.app._set_state("Idle", "neutral")
                self.app.toast("Install cancelled")
            else:
                self._phase("Install failed", str(payload), 0.0)
                self.app.log.emit(f"FAIL: install: {payload}", "err")
                self.app._set_state("Failed", "error")
                self.app.toast("Install failed — see Console")
            self._set_running_ui()

        self.app.start_task("install", work, handler)

    def _verify(self) -> None:
        if self.app.task_running():
            self.app.toast("Wait for the running task to finish")
            return
        dest = self._dest()
        venv = installer.venv_python(dest)
        if not venv.is_file():
            self.app.toast("No environment yet — install first")
            return
        self.active_task = "verify"
        self._set_running_ui()
        self._phase("Verifying", "Importing harness2 and reading the demo CLI help…", 0.5)
        self.app._set_state("Verifying", "primary")

        def work(_report, _cancel):
            return installer.verify_install(dest, venv)

        def handler(event: str, payload) -> None:
            if event == "progress":
                return
            self.active_task = None
            if event == "done":
                self._phase("Verified", f"harness2 {payload} imports successfully", 1.0)
                self.app.log.emit(f"OK: verified harness2 {payload} at {dest}", "ok")
                self.app.toast("Install verified")
                self.app._set_state("Idle", "neutral")
            else:
                self._phase("Verify failed", str(payload), 0.0)
                self.app.log.emit(f"FAIL: verify: {payload}", "err")
                self.app.toast("Verify failed — see Console")
                self.app._set_state("Failed", "error")
            self._set_running_ui()

        self.app.start_task("verify", work, handler)

    # -- optional packages ---------------------------------------------
    def _refresh_extras(self) -> None:
        if not self._alive():
            return
        dest = self._dest()
        venv = installer.venv_python(dest)
        if not venv.is_file():
            for label in self.extras_labels.values():
                label.configure(text="Install the environment first")
            return
        for label in self.extras_labels.values():
            label.configure(text="Checking…")
        self.app.after_bg(
            lambda: installer.missing_extras(dest, venv),
            self._apply_extras,
        )

    def _apply_extras(self, result) -> None:
        if not self._alive():
            return
        if isinstance(result, Exception):
            for group in self.extras_labels:
                self.extras_labels[group].configure(text=f"Check failed: {result}")
            return
        display = {"pptx": "python-pptx", "google.auth": "google-auth"}
        for group, label in self.extras_labels.items():
            missing = result.get(group, [])
            if missing:
                label.configure(text="Missing: " + ", ".join(display.get(m, m) for m in missing),
                                fg=self.theme.c["warning"])
            else:
                label.configure(text="Installed", fg=self.theme.c["success"])

    def _install_extras(self, group: str) -> None:
        if self.app.task_running():
            self.app.toast("Wait for the running task to finish")
            return
        dest = self._dest()
        venv = installer.venv_python(dest)
        if not venv.is_file():
            self.app.toast("Install the environment first")
            return
        key = f"extras-{group}"
        self.active_task = key
        self._last_phase, self._last_bucket = None, -1
        self._phase(f"Installing {group} packages", "Starting pip inside .venv…", 0.5)
        self.app.log.emit("", "out")
        self.app.log.emit(f"$ pip install {group} extras", "cmd")
        self._set_running_ui()
        self.app._set_state("Installing", "primary")

        def work(report, cancel):
            from ..app import TaskCancelled

            try:
                return installer.install_extras(
                    dest, venv=venv, groups=(group,), progress=report, cancel=cancel,
                )
            except installer.InstallCancelled as exc:
                raise TaskCancelled(str(exc)) from None

        def handler(event: str, payload) -> None:
            if event == "progress":
                _phase, _done, _total, detail = payload
                self.detail_label.configure(text=detail[-300:])
                if detail and not detail.startswith(("Requirement", "Collecting", "Using", "  ")):
                    self.app.log.emit(f"[pip] {detail}", "dim")
                return
            self.active_task = None
            if event == "done":
                self._phase(f"{group.title()} packages installed", str(payload), 1.0)
                self.app.log.emit(f"OK: installed {payload}", "ok")
                self.app.toast("Optional packages installed")
                self.app._set_state("Idle", "neutral")
            elif event == "cancelled":
                self._phase("Cancelled", "Rerun to continue installing optional packages.", 0.0)
                self.app.log.emit("WARN: package install cancelled", "warn")
                self.app._set_state("Idle", "neutral")
            else:
                self._phase("Package install failed", str(payload), 0.0)
                self.app.log.emit(f"FAIL: extras: {payload}", "err")
                self.app._set_state("Failed", "error")
                self.app.toast("Package install failed — see Console")
            self._set_running_ui()
            self._refresh_extras()

        self.app.start_task(key, work, handler)

    # -- buttons --------------------------------------------------------
    def _cancel(self) -> None:
        if self.active_task:
            self.app.cancel_task(self.active_task)
            self.cancel_btn.set_enabled(False)
            self._phase("Stopping…", "Stopping after the current file; partial work is kept.", None)

    def _adopt(self) -> None:
        dest = self._dest()
        if not self._is_checkout(dest):
            self.app.toast("That folder has no Harness² pyproject.toml")
            return
        self.app.adopt_install(dest)

    def _open(self) -> None:
        dest = self._dest()
        if dest.exists():
            self.app.open_path(dest)
        else:
            self.app.toast("The folder does not exist yet")

    def _browse_dir(self) -> None:
        initial = self._dest()
        chosen = filedialog.askdirectory(
            parent=self, title="Choose a Harness² folder",
            initialdir=str(initial if initial.exists() else initial.parent),
        )
        if chosen:
            self.dest_var.set(chosen)

    def _browse_python(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self, title="Choose a Python 3.12 or 3.13 interpreter",
            initialdir=str(Path(self.python_var.get()).parent),
        )
        if chosen:
            self.python_var.set(chosen)

    def refresh(self) -> None:
        if self._alive():
            self._refresh_status()
            self._set_running_ui()
            if not self.app.task_running():
                self._refresh_extras()
