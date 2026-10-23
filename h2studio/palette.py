"""Command palette: an in-window overlay, so it captures and focuses correctly.

A Toplevel with ``overrideredirect`` is invisible to some window managers and to
screen capture; an overlay Frame inside the app is also closer to how Google's
own quick switchers behave.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .theme import Theme

ROWS = 8
ROW_HEIGHT = 36


class CommandPalette(tk.Frame):
    """Type to filter, Up/Down to move, Enter to run, Esc to close."""

    def __init__(self, app, theme: Theme, actions: list[tuple[str, str, Callable[[], None]]]) -> None:
        self.theme = theme
        self.app = app
        self.actions = actions
        self.results = actions[:ROWS]
        self.index = 0
        self.row_widgets: list[tuple[tk.Frame, tk.Label, tk.Label]] = []
        c = theme.c

        super().__init__(app, bg=c["outline"], bd=0, highlightthickness=0)
        shell = tk.Frame(self, bg=c["surface_high"])
        shell.pack(fill="both", expand=True, padx=1, pady=1)

        head = tk.Frame(shell, bg=c["surface_high"])
        head.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(head, text="Search actions", bg=c["surface_high"], fg=c["on_surface_variant"],
                 font=theme.font("label"), anchor="w").pack(side="left")
        tk.Label(head, text="Esc", bg=c["surface_high"], fg=c["on_surface_variant"],
                 font=theme.font("caption")).pack(side="right")

        entry_wrap = tk.Frame(shell, bg=c["surface_low"], highlightthickness=2,
                              highlightbackground=c["outline"], highlightcolor=c["primary"])
        entry_wrap.pack(fill="x", padx=12, pady=(6, 10))
        self.var = tk.StringVar()
        self.entry = tk.Entry(entry_wrap, textvariable=self.var, bd=0, highlightthickness=0,
                              bg=c["surface_low"], fg=c["on_surface"],
                              insertbackground=c["on_surface"], font=theme.font("body_lg"))
        self.entry.pack(fill="x", padx=10, pady=10)

        self.rows = tk.Frame(shell, bg=c["surface_high"])
        self.rows.pack(fill="both", expand=True, padx=12)
        self._build_rows()
        self.none = tk.Label(self.rows, text="No matching action", bg=c["surface_high"],
                             fg=c["on_surface_variant"], font=theme.font("body"),
                             anchor="w", padx=10, pady=12)

        self.hint = tk.Label(shell, text="Up / Down move    Enter run    Esc close",
                             bg=c["surface_high"], fg=c["on_surface_variant"],
                             font=theme.font("caption"), anchor="w")
        self.hint.pack(fill="x", padx=16, pady=(6, 10))

        self.place(relx=0.5, y=88, anchor="n", width=640, height=470)
        self._render()
        self._slide(0)
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Down>", lambda _e: self._move(1))
        self.entry.bind("<Up>", lambda _e: self._move(-1))
        self.entry.bind("<Return>", lambda _e: self._run())
        self.entry.bind("<Escape>", self._escape)
        self._escape_id = self.app.bind("<Escape>", self._escape, add="+")
        self._click_id = self.app.bind("<Button-1>", self._outside_click, add="+")
        self.entry.focus_set()

    def _slide(self, step: int) -> None:
        """64 ms settle into place; the only entrance motion in the app."""
        if not self.winfo_exists():
            return
        self.place_configure(y=88 + 2 * min(step, 4))
        if step < 4:
            self.after(16, lambda: self._slide(step + 1))

    # -- rows -----------------------------------------------------------
    def _build_rows(self) -> None:
        for _ in range(ROWS):
            row = tk.Frame(self.rows, bg=self.theme.c["surface_high"], cursor="hand2")
            row.pack(fill="x", pady=1)
            title = tk.Label(row, text="", bg=self.theme.c["surface_high"],
                             fg=self.theme.c["on_surface"], font=self.theme.font("body"),
                             anchor="w", padx=10, pady=8)
            title.pack(side="left", fill="x", expand=True)
            hint = tk.Label(row, text="", bg=self.theme.c["surface_high"],
                            fg=self.theme.c["on_surface_variant"], font=self.theme.font("caption"),
                            anchor="e", padx=10)
            hint.pack(side="right")
            row.bind("<Enter>", lambda _e, r=row: self._hover(r))
            row.bind("<Button-1>", lambda _e, r=row: self._click(r))
            title.bind("<Button-1>", lambda _e, r=row: self._click(r))
            hint.bind("<Button-1>", lambda _e, r=row: self._click(r))
            self.row_widgets.append((row, title, hint))

    def _filter(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self.results = self.actions[:ROWS]
        else:
            scored = []
            for title, hint, fn in self.actions:
                hay = f"{title} {hint}".lower()
                pos = hay.find(q)
                if pos >= 0:
                    scored.append((pos, title, hint, fn))
            scored.sort(key=lambda row: (row[0], row[1]))
            self.results = [(t, h, f) for _p, t, h, f in scored[:ROWS]]
        self.index = 0
        self._render()

    def _render(self) -> None:
        for row, _title, _hint in self.row_widgets:
            row.pack_forget()
        for i, (row, title, hint) in enumerate(self.row_widgets):
            if i >= len(self.results):
                continue
            t, h, _fn = self.results[i]
            title.configure(text=t)
            hint.configure(text=h)
            row.pack(fill="x", pady=1)
        if self.results:
            self.none.pack_forget()
        else:
            self.none.pack(fill="x")
        self._paint()

    def _paint(self) -> None:
        c = self.theme.c
        for i, (row, title, hint) in enumerate(self.row_widgets):
            if i >= len(self.results):
                continue
            active = i == self.index
            bg = c["primary_container"] if active else c["surface_high"]
            fg = c["on_primary_container"] if active else c["on_surface"]
            hint_fg = c["on_primary_container"] if active else c["on_surface_variant"]
            row.configure(bg=bg)
            title.configure(bg=bg, fg=fg)
            hint.configure(bg=bg, fg=hint_fg)

    def _hover(self, row: tk.Frame) -> None:
        for i, (candidate, _t, _h) in enumerate(self.row_widgets):
            if candidate is row and i < len(self.results):
                self.index = i
                self._paint()
                return

    def _click(self, row: tk.Frame) -> None:
        self._hover(row)
        self._run()

    def _move(self, delta: int) -> str:
        if self.results:
            self.index = (self.index + delta) % len(self.results)
            self._paint()
        return "break"

    def _on_key(self, event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        self._filter(self.var.get())

    # -- actions --------------------------------------------------------
    def _run(self) -> None:
        if not self.results:
            return
        fn = self.results[min(self.index, len(self.results) - 1)][2]
        self.close()
        self.app.after(10, fn)

    def _escape(self, _e=None) -> str:
        self.close()
        return "break"

    def _outside_click(self, event) -> None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self:
                return
            widget = getattr(widget, "master", None)
        self.close()

    def close(self) -> None:
        if not self.winfo_exists():
            return
        for sequence, funcid in (("<Escape>", self._escape_id), ("<Button-1>", self._click_id)):
            try:
                self.app.unbind(sequence, funcid)
            except tk.TclError:
                pass
        if getattr(self.app, "_palette", None) is self:
            self.app._palette = None
        self.destroy()
