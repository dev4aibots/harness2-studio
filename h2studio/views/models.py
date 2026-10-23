"""Models: wire any coding agent through .env, in the format Harness² parses.

Every model row shows the provider/model dropdown (searchable by typing) plus
an effort dropdown (low / medium / high) that maps to
``HARNESS2_<ROLE>_REASONING_EFFORT``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..services import envfile, h2
from ..services import models as model_service
from ..widgets import Card, Chip, Pill, Scroller
from .base import View

# (env key, label, hint, is_model)
FIELDS = (
    ("HARNESS2_SOLVER_MODEL", "Executor model", "provider/model, e.g. opencode/deepseek-v4.1-flash-free", True),
    ("HARNESS2_IMPROVER_MODEL", "Improver model", "defaults to the executor when blank", True),
    ("HARNESS2_JUDGE_MODEL", "Judge model", "bare id; Vertex prefix added by adapter", True),
    ("HARNESS2_JUDGE_BASE_URL", "Judge base URL", "OpenAI-compatible endpoint, e.g. http://127.0.0.1:7585/v1", False),
    ("HARNESS2_JUDGE_API_KEY", "Judge API key", "stored in .env only", False),
    ("HARNESS2_RUNS_DIR", "Runs directory", "defaults to <repo>/runs", False),
    ("GOOGLE_CLOUD_PROJECT", "GCP project", "needed only for the Vertex judge", False),
    ("GOOGLE_CLOUD_LOCATION", "GCP location", "defaults to global", False),
)

EFFORT_LEVELS = ("low", "medium", "high")


class ModelsView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.vars: dict[str, tk.StringVar] = {}
        self.effort_vars: dict[str, tk.StringVar] = {}
        self.boxes: dict[str, ttk.Combobox] = {}

        scroll = Scroller(self, t)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        pad = tk.Frame(root, bg=t.c["surface"])
        pad.pack(fill="both", expand=True, padx=28, pady=24)

        head = tk.Frame(pad, bg=t.c["surface"])
        head.pack(fill="x")
        tk.Label(head, text="Any agent, one contract", bg=t.c["surface"], fg=t.c["on_surface"],
                 font=t.font("headline")).pack(side="left")
        self.count_chip = Chip(head, t, "models: …", "neutral")
        self.count_chip.pack(side="right")

        card = Card(pad, t, title="Environment", subtitle=f"Written to {app.install.env_file}")
        card.pack(fill="x", pady=(14, 0))
        grid = card.content
        grid.grid_columnconfigure(0, weight=1, uniform="f")
        grid.grid_columnconfigure(1, weight=1, uniform="f")

        values: list[str] = []
        for i, (key, label, hint, is_model) in enumerate(FIELDS):
            wrap = tk.Frame(grid, bg=t.c["surface_container"])
            wrap.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 16), pady=(0, 12))

            row_top = tk.Frame(wrap, bg=t.c["surface_container"])
            row_top.pack(fill="x")
            tk.Label(row_top, text=label, bg=t.c["surface_container"], fg=t.c["on_surface"],
                     font=t.font("label"), anchor="w").pack(side="left")
            if is_model:
                self.effort_vars[key] = tk.StringVar(value="medium")
                effort = ttk.OptionMenu(row_top, self.effort_vars[key], "medium", *EFFORT_LEVELS)
                effort.configure(width=10)
                effort.pack(side="right")

            var = tk.StringVar()
            self.vars[key] = var
            if is_model:
                box = ttk.Combobox(wrap, textvariable=var, values=values)
                box.pack(fill="x", pady=(2, 0))
                self.boxes[key] = box
            elif key.endswith("API_KEY"):
                box = ttk.Entry(wrap, textvariable=var, show="•")
                box.pack(fill="x", pady=(2, 0))
            else:
                ttk.Entry(wrap, textvariable=var).pack(fill="x", pady=(2, 0))
            tk.Label(wrap, text=hint, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("caption"), anchor="w").pack(fill="x")

        actions = tk.Frame(pad, bg=t.c["surface"])
        actions.pack(fill="x", pady=(16, 0))
        Pill(actions, "Save .env", self._save, t, "filled").pack(side="left", padx=(0, 8))
        Pill(actions, "Reload", self._load, t, "outlined").pack(side="left", padx=(0, 8))
        Pill(actions, "Discover models", self._discover, t, "tonal").pack(side="left", padx=(0, 8))
        Pill(actions, "Create template", self._template, t, "text").pack(side="left", padx=(0, 8))
        Pill(actions, "Verify environment", lambda: self.app.show("setup"), t, "text").pack(side="left")
        self.status = tk.Label(actions, text="", bg=t.c["surface"], fg=t.c["on_surface_variant"],
                               font=t.font("caption"))
        self.status.pack(side="right")

        note = Card(pad, t, title="Why this file", subtitle="Harness² reads .env with shell precedence.")
        note.pack(fill="x", pady=(18, 0))
        tk.Label(note.content, text=(
            "Solver and improver use OpenCode's provider/model syntax. The judge is separate: JobBench "
            "accepts HARNESS2_JUDGE_BASE_URL plus a key, so a local gateway can stand in for Vertex. "
            "LAB and WorkBuddy are Vertex-shaped upstream. Effort (low/medium/high) sets the reasoning "
            "budget each model gets per turn — higher = smarter but slower and costlier."),
            bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("body"),
            justify="left", anchor="w", wraplength=860).pack(fill="x")

        bridge = Card(pad, t, title="Bridge · Codex executor",
                      subtitle="Serve a Responses API on Vertex AI. Long-running; stop it before a sweep.")
        bridge.pack(fill="x", pady=(18, 0), before=note)
        brow = tk.Frame(bridge.content, bg=t.c["surface_container"])
        brow.pack(fill="x")
        draft = app.state.bridge_draft or {}
        current_env = envfile.parse(app.install.env_file)
        self.bridge_model = tk.StringVar(
            value=draft.get("model") or current_env.get("HARNESS2_SOLVER_MODEL", ""))
        self.bridge_host = tk.StringVar(value=draft.get("host", "127.0.0.1"))
        self.bridge_port = tk.StringVar(value=draft.get("port", ""))
        for label, var, width, hint in (
            ("Model", self.bridge_model, 34, "Vertex model id"),
            ("Host", self.bridge_host, 14, "0.0.0.0 for containers"),
            ("Port", self.bridge_port, 7, "blank = free port"),
        ):
            wrap = tk.Frame(brow, bg=t.c["surface_container"])
            wrap.pack(side="left", padx=(0, 12))
            tk.Label(wrap, text=label, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("label"), anchor="w").pack(fill="x")
            ttk.Entry(wrap, textvariable=var, width=width).pack(fill="x", pady=(2, 0))
            tk.Label(wrap, text=hint, bg=t.c["surface_container"], fg=t.c["on_surface_variant"],
                     font=t.font("caption"), anchor="w").pack(fill="x")
        Pill(brow, "Start bridge", self._start_bridge, t, "tonal", height=32, pad=12).pack(
            side="right", anchor="s")

        self._load(first=True)
        self.bind("<Destroy>", self._on_destroy)
        self._discover_async()

    # -- data -----------------------------------------------------------
    def _load(self, first: bool = False, discard_draft: bool = False) -> None:
        env = envfile.parse(self.app.install.env_file)
        draft = {} if (discard_draft or not first) else (self.app.state.models_draft or {})
        for key, _label, _hint, _is_model in FIELDS:
            self.vars[key].set(draft.get(key, env.get(key, "")))
        # effort defaults live only in state, not .env
        for key, _label, _hint, is_model in FIELDS:
            if is_model:
                self.effort_vars[key].set(draft.get(f"{key}_EFFORT", "medium"))
        exists = self.app.install.env_file.is_file()
        self.status.configure(text="loaded" if exists else "no .env yet")

    def _discover_async(self, refresh: bool = False) -> None:
        if not self.winfo_exists():
            return
        self.count_chip.configure(text="models: …")
        self.app.after_bg(lambda: model_service.list_models(refresh=refresh), self._apply_models)

    def _apply_models(self, result) -> None:
        if not self.winfo_exists() or isinstance(result, Exception):
            return
        values = [m.id for m in result]
        for box in self.boxes.values():
            box.configure(values=values)
        self.count_chip.configure(text=f"models: {len(values)}")

    def _discover(self) -> None:
        self._discover_async(refresh=True)
        self.app.toast("Discovering models…")

    # -- actions --------------------------------------------------------
    def _start_bridge(self) -> None:
        raw = self.bridge_port.get().strip()
        try:
            port = int(raw) if raw else None
        except ValueError:
            self.app.toast("Port must be a whole number")
            return
        opts = h2.Options(
            model=self.bridge_model.get().strip() or None,
            host=self.bridge_host.get().strip() or None,
            port=port,
        )
        self.app.state.bridge_draft = {
            "model": self.bridge_model.get().strip(),
            "host": self.bridge_host.get().strip(),
            "port": raw,
        }
        try:
            self.app.state.save()
        except OSError:
            pass
        self.app.show("console")
        self.app.run_action("bridge", opts, label="bridge")

    def _template(self) -> None:
        created = envfile.write_template(self.app.install.env_file)
        if created:
            self._load()
            self.app.log.emit(f"OK: wrote a commented .env template to {self.app.install.env_file}", "ok")
            self.app.toast("Starter .env created")
        else:
            self.app.toast(".env already exists — edit it here")

    def _save(self) -> None:
        values = {k: v.get().strip() for k, v in self.vars.items()}
        # persist effort into draft so it survives .env reloads
        effort = {f"{k}_EFFORT": v.get() for k, v in self.effort_vars.items()}
        try:
            envfile.set_values(self.app.install.env_file, values)
        except OSError as exc:
            self.app.toast(f"Save failed: {exc}")
            return
        self.app.state.models_draft = {**effort}
        try:
            self.app.state.save()
        except OSError:
            pass
        self.status.configure(text="saved")
        self.app.toast("Saved .env")

    def refresh(self) -> None:
        cached = model_service._CACHE
        count = len(cached) if cached is not None else "…"
        self.count_chip.configure(text=f"models: {count}")

    def _on_destroy(self, event) -> None:
        if event.widget is not self:
            return
        draft = {k: v.get() for k, v in self.vars.items()}
        effort = {f"{k}_EFFORT": v.get() for k, v in self.effort_vars.items()}
        env = envfile.parse(self.app.install.env_file)
        if any(draft.get(k, "") != env.get(k, "") for k in draft):
            self.app.state.models_draft = {**draft, **effort}
            try:
                self.app.state.save()
            except OSError:
                pass
