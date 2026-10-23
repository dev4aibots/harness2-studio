"""Full output history, filterable and exportable."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
from typing import ClassVar

from ..widgets import Console, Pill, Segmented
from .base import View


class ConsoleView(View):
    FILTERS: ClassVar[dict[str, str]] = {"all": "All output", "errors": "Problems", "commands": "Commands"}

    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.lines: list[tuple[str, str]] = list(app.log.buffer)[-4000:]
        self.filter = "all"
        self._placeholder = False

        bar = tk.Frame(self, bg=t.c["surface"])
        bar.pack(fill="x", padx=20, pady=(16, 8))
        Segmented(bar, t, list(self.FILTERS.items()), "all", self._set_filter).pack(side="left")
        self.copy_btn = Pill(bar, "Copy", self._copy, t, "tonal", height=32, pad=12)
        self.copy_btn.pack(side="right", padx=(8, 0))
        self.save_btn = Pill(bar, "Save log", self._save, t, "outlined", height=32, pad=12)
        self.save_btn.pack(side="right", padx=(8, 0))
        self.clear_btn = Pill(bar, "Clear", self._clear, t, "text", height=32, pad=12)
        self.clear_btn.pack(side="right")

        self.console = Console(self, t, height=30)
        self.console.pack(fill="both", expand=True, padx=20, pady=(0, 18))

        app.log.subscribe(self._on_log)
        self.bind("<Destroy>", self._on_destroy)
        self._render_log()

    def _render_log(self) -> None:
        self.console.clear()
        shown = 0
        for line, tag in self.lines:
            if self._passes(tag):
                self.console.append(line, tag)
                shown += 1
        self._placeholder = shown == 0
        if self._placeholder:
            self.console.append("No output yet. Run a command to stream stdout and stderr here.", "dim")
        self._sync_actions()

    def _sync_actions(self) -> None:
        has_lines = bool(self.lines)
        for button in (self.copy_btn, self.save_btn, self.clear_btn):
            button.set_enabled(has_lines)

    def _set_filter(self, key: str) -> None:
        self.filter = key
        self._render_log()

    def _passes(self, tag: str) -> bool:
        if self.filter == "errors":
            return tag in ("err", "warn", "cmd")
        if self.filter == "commands":
            return tag == "cmd"
        return True

    def _on_log(self, line: str, tag: str) -> None:
        self.lines.append((line, tag))
        if len(self.lines) > 4000:
            del self.lines[:1000]
        if self._passes(tag):
            if self._placeholder:
                self.console.clear()
                self._placeholder = False
            self.console.append(line, tag)
        self._sync_actions()

    def _clear(self) -> None:
        self.lines.clear()
        self._render_log()

    def _copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.console.dump())
        self.app.toast("Console copied")

    def _save(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".log", initialfile="harness2.log")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.console.dump())
            self.app.toast(f"Saved {path}")

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self.app.log.unsubscribe(self._on_log)
