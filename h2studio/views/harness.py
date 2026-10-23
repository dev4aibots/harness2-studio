"""Harness: the eight components, per version, with a real diff against base."""

from __future__ import annotations

import shutil
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..services import runs
from ..widgets import Card, Chip, Pill, Toggle, make_text_tabbable
from .base import View


class HarnessView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.tasks: list[Path] = []
        self.versions: list[runs.Harness] = []
        self.current: runs.Harness | None = None
        self.base: runs.Harness | None = None
        self.texts: dict[str, tk.Text] = {}
        self.editing = False

        body = tk.Frame(self, bg=t.c["surface"])
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=4)
        body.grid_rowconfigure(0, weight=1)

        left = Card(body, t, title="Tasks", subtitle="Directories that own a harnesses/ tree.")
        left.grid(row=0, column=0, sticky="nsew")
        self.tree = ttk.Treeview(left.content, columns=("run",), show="tree headings",
                                 selectmode="browse")
        self.tree.heading("#0", text="Task")
        self.tree.heading("run", text="Run")
        self.tree.column("#0", width=130)
        self.tree.column("run", width=130, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_task)
        self.empty = tk.Frame(left.content, bg=t.c["surface_container"])
        tk.Label(self.empty, text="No harnesses yet", bg=t.c["surface_container"], fg=t.c["on_surface"],
                 font=t.font("title"), anchor="w").pack(fill="x", pady=(18, 4))
        tk.Label(self.empty, text="Run a sweep or the demo to create a harnesses/ tree this view can inspect.",
                 bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("body"),
                 anchor="w", justify="left", wraplength=240).pack(fill="x")

        right = tk.Frame(body, bg=t.c["surface"])
        right.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        bar = tk.Frame(right, bg=t.c["surface"])
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(bar, text="Version", bg=t.c["surface"], fg=t.c["on_surface_variant"],
                 font=t.font("label")).pack(side="left", padx=(0, 8))
        self.version_box = ttk.Combobox(bar, state="readonly", width=18)
        self.version_box.pack(side="left")
        self.version_box.bind("<<ComboboxSelected>>", lambda _e: self._load_version())
        self.diff = Toggle(bar, "diff vs base", False, lambda _v: self._diff_changed(), t, bg=t.c["surface"])
        self.diff.pack(side="left", padx=(14, 0))
        self.edit = Toggle(bar, "allow editing", False, lambda _v: self._toggle_edit(), t, bg=t.c["surface"])
        self.edit.pack(side="left", padx=(8, 0))
        self.save_btn = Pill(bar, "Save", self._save, t, "filled", height=30, pad=10)
        self.save_btn.pack(side="right")
        self.save_btn.set_enabled(False)
        Pill(bar, "Open folder", self._open, t, "outlined", height=30, pad=10).pack(side="right", padx=(0, 8))
        self.warn = Chip(bar, t, "read-only", "neutral")
        self.warn.pack(side="right", padx=(0, 10))

        self.nb = ttk.Notebook(right)
        self.nb.grid(row=1, column=0, sticky="nsew")
        self.path_label = tk.Label(right, text="", bg=t.c["surface"], fg=t.c["on_surface_variant"],
                                   font=t.font("caption"), anchor="w")
        self.path_label.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.nb.bind("<<NotebookTabChanged>>", lambda _e: self._update_path())
        for key, title, rel in runs.COMPONENTS:
            frame = tk.Frame(self.nb, bg=t.c["surface_low"])
            text = tk.Text(frame, wrap="none", bd=0, highlightthickness=0, bg=t.c["surface_low"],
                           fg=t.c["on_surface"], insertbackground=t.c["on_surface"],
                           font=t.font("mono_sm"), padx=12, pady=10, state="disabled")
            y = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=y.set)
            make_text_tabbable(text)
            y.pack(side="right", fill="y")
            text.pack(side="left", fill="both", expand=True)
            self.nb.add(frame, text=f"{key} {title}")
            self.texts[key] = text

        self.refresh()

    # -- data -----------------------------------------------------------
    def refresh(self) -> None:
        if getattr(self, "editing", False):
            return  # never discard an edit in flight
        root = self.app.install.runs_default
        self.tasks = runs.harness_tasks(root)
        self.tree.delete(*self.tree.get_children())
        for path in self.tasks:
            run_name = path.parent.name
            self.tree.insert("", "end", iid=str(path), text=path.name,
                             values=(run_name,), open=False)
        if self.tasks:
            self.empty.pack_forget()
            self.tree.pack(fill="both", expand=True)
        else:
            self.tree.pack_forget()
            self.empty.pack(fill="both", expand=True)
        if self.tasks and not self.tree.selection():
            self.tree.selection_set(str(self.tasks[0]))
            self.tree.focus(str(self.tasks[0]))
            self._on_task()

    def _on_task(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        task = Path(sel[0])
        self.versions = runs.harnesses(task)
        labels = [h.label for h in self.versions]
        self.version_box.configure(values=labels)
        if not labels:
            self.version_box.set("")
            self.current = None
            self._render()
            return
        pick = "base" if "base" in labels else labels[0]
        self.version_box.set(pick)
        self._load_version()

    def _load_version(self) -> None:
        label = self.version_box.get()
        self.current = next((h for h in self.versions if h.label == label), None)
        self.base = next((h for h in self.versions if h.label == "base"), None)
        self._render()

    # -- rendering ------------------------------------------------------
    def _render(self) -> None:
        show_diff = self.diff.value
        self.editable: dict[str, bool] = {}
        for key, _title, _rel in runs.COMPONENTS:
            widget = self.texts[key]
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            if self.current is None:
                widget.insert("1.0", "Select a task to inspect its harness versions.")
                widget.configure(state="disabled")
                self.editable[key] = False
                continue
            path = self.current.component_path(key)
            text = runs.component_text(path)
            self.editable[key] = bool(path and path.is_file() and not show_diff and len(text) < 200_000)
            if show_diff and self.base is not None and self.current.label != "base":
                old = runs.component_text(self.base.component_path(key))
                new = runs.component_text(path)
                widget.insert("1.0", runs.unified_diff(old, new, f"base/{_rel}", f"{self.current.label}/{_rel}") or "(identical)")
            else:
                widget.insert("1.0", text)
            widget.configure(state="normal" if (self.editing and self.editable[key]) else "disabled")
        self._update_path()
        self._update_chip()

    def _update_path(self) -> None:
        if self.current is None:
            self.path_label.configure(text="(no task selected)")
            return
        key = self._current_key()
        path = self.current.component_path(key) if key else None
        self.path_label.configure(text=str(path) if path else "(component not shipped in this version)")

    def _toggle_edit(self) -> None:
        self.editing = self.edit.value
        self._update_chip()
        self._render()

    def _diff_changed(self) -> None:
        if self.diff.value and self.editing:
            self.edit._value = False
            self.edit.variant = "outlined"
            self.edit._label = self.edit._base
            self.edit._resize(None)
            self.edit._draw()
            self.editing = False
            self.app.toast("Editing disabled while showing a diff")
        self._update_chip()
        self._render()

    def _update_chip(self) -> None:
        key = self._current_key()
        can_write = bool(self.editing and key is not None and self.editable.get(key, False))
        self.warn.configure(text="editing" if self.editing else "read-only",
                            bg=self.theme.c["error_container"] if self.editing else self.theme.c["surface_high"],
                            fg=self.theme.c["on_error_container"] if self.editing else self.theme.c["on_surface_variant"])
        if hasattr(self, "save_btn"):
            self.save_btn.set_enabled(can_write)

    # -- actions --------------------------------------------------------
    def _current_key(self) -> str | None:
        try:
            idx = self.nb.index(self.nb.select())
        except tk.TclError:
            return None
        return runs.COMPONENTS[idx][0]

    def _save(self) -> None:
        if not self.editing or self.current is None:
            self.app.toast("Enable editing first")
            return
        key = self._current_key()
        if key is None:
            return
        if not self.editable.get(key, False):
            self.app.toast("Read-only here: turn off the diff to edit the raw file")
            return
        path = self.current.component_path(key)
        if path is None or path.is_dir():
            self.app.toast("This component is a directory; edit files inside it")
            return
        backup = path.with_suffix(path.suffix + f".bak-{int(time.time())}")
        try:
            shutil.copy2(path, backup)
            path.write_text(self.texts[key].get("1.0", "end-1c"), encoding="utf-8")
        except OSError as exc:
            self.app.toast(f"Save failed: {exc}")
            return
        self.app.toast(f"Saved (backup {backup.name})")

    def _open(self) -> None:
        if self.current is not None:
            self.app.open_path(self.current.path)
