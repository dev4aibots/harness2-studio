"""Shared base for all views."""

from __future__ import annotations

import tkinter as tk


class View(tk.Frame):
    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=app.theme.c["surface"])
        self.app = app
        self.theme = app.theme

    def refresh(self) -> None:  # views that hold live data override this
        pass
