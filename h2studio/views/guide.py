"""Guide: the same product, explained without assuming a research background."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..guide_content import TOPICS, by_key
from ..widgets import Card, Chip, Pill, Scroller
from .base import View


class GuideView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.current = "overview"
        self.rows: dict[str, tuple[tk.Frame, tk.Label]] = {}
        self.wrapped: list[tk.Label] = []
        self._search = tk.StringVar()

        pad = tk.Frame(self, bg=t.c["surface"])
        pad.pack(fill="both", expand=True, padx=24, pady=20)
        pad.grid_columnconfigure(1, weight=1)
        pad.grid_rowconfigure(1, weight=1)

        head = tk.Frame(pad, bg=t.c["surface"])
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        left = tk.Frame(head, bg=t.c["surface"])
        left.pack(side="left")
        tk.Label(left, text="Field guide", bg=t.c["surface"], fg=t.c["on_surface"],
                 font=t.font("title_lg"), anchor="w").pack(anchor="w")
        tk.Label(left, text="Every feature, in order, with the exact screen that does the work.",
                 bg=t.c["surface"], fg=t.c["on_surface_variant"], font=t.font("body"),
                 anchor="w").pack(anchor="w", pady=(2, 0))
        self.where = Chip(head, t, "Start here", "primary")
        self.where.pack(side="right", pady=(4, 0))

        side = Card(pad, t, title="Topics")
        side.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        side.configure(width=268)
        side.grid_propagate(False)
        side.pack_propagate(False)
        tk.Label(side.content, text="Search topics", bg=t.c["surface_container"],
                 fg=t.c["on_surface_variant"], font=t.font("caption"), anchor="w").pack(fill="x")
        search = ttk.Entry(side.content, textvariable=self._search)
        search.pack(fill="x", pady=(2, 8))
        self._search.trace_add("write", lambda *_a: self._filter())
        self.topic_scroll = Scroller(side.content, t, bg=t.c["surface_container"])
        self.topic_scroll.pack(fill="both", expand=True)
        self.topic_list = tk.Frame(self.topic_scroll.inner, bg=t.c["surface_container"])
        self.topic_list.pack(fill="both", expand=True)
        for topic in TOPICS:
            row = tk.Frame(self.topic_list, bg=t.c["surface_container"], cursor="hand2")
            row.pack(fill="x", pady=1)
            text = tk.Label(row, text=topic.title, bg=t.c["surface_container"],
                            fg=t.c["on_surface_variant"], font=t.font("body"), anchor="w",
                            justify="left", wraplength=198, padx=8, pady=6,
                            takefocus=1, highlightthickness=2,
                            highlightbackground=t.c["surface_container"],
                            highlightcolor=t.c["primary"])
            text.pack(fill="x")
            for widget in (row, text):
                widget.bind("<Button-1>", lambda _e, k=topic.key: self.focus_topic(k))
            text.bind("<Return>", lambda _e, k=topic.key: self.focus_topic(k))
            text.bind("<space>", lambda _e, k=topic.key: self.focus_topic(k))
            self.rows[topic.key] = (row, text)
        self.empty = tk.Label(self.topic_list, text="No topic matches.", bg=t.c["surface_container"],
                              fg=t.c["on_surface_variant"], font=t.font("caption"), anchor="w")

        self.scroll = Scroller(pad, t)
        self.scroll.grid(row=1, column=1, sticky="nsew")
        self.body = tk.Frame(self.scroll.inner, bg=t.c["surface"])
        self.body.pack(fill="both", expand=True)
        self.body.bind("<Configure>", self._rewrap)

        self.focus_topic("overview")

    def refresh(self) -> None:
        pass

    def focus_topic(self, key: str) -> None:
        topic = by_key(key)
        self.current = topic.key
        self.where.configure(text=topic.kicker)
        self._render(topic)
        self._paint_rows()
        self.scroll.canvas.yview_moveto(0)
        if self._search.get():
            self._search.set("")

    def _paint_rows(self) -> None:
        t = self.theme
        for key, (row, label) in self.rows.items():
            selected = key == self.current
            bg = t.c["secondary_container"] if selected else t.c["surface_container"]
            row.configure(bg=bg)
            label.configure(bg=bg, fg=t.c["on_secondary_container"] if selected else t.c["on_surface_variant"],
                            font=t.font("label" if selected else "body"),
                            highlightbackground=bg)

    def _filter(self) -> None:
        needle = self._search.get().strip().lower()
        visible = 0
        for topic in TOPICS:
            self.rows[topic.key][0].pack_forget()
        for topic in TOPICS:
            row, _label = self.rows[topic.key]
            haystack = " ".join((topic.title, topic.kicker, topic.summary, *topic.steps)).lower()
            if not needle or needle in haystack:
                row.pack(fill="x", pady=1)
                visible += 1
        if visible == 0:
            self.empty.pack(fill="x", pady=8)
        else:
            self.empty.pack_forget()

    def _render(self, topic) -> None:
        t = self.theme
        for child in self.body.winfo_children():
            child.destroy()
        self.wrapped.clear()
        card = Card(self.body, t, pad=26)
        card.pack(fill="x", pady=(0, 18))
        Chip(card.content, t, topic.kicker, "primary").pack(anchor="w")
        tk.Label(card.content, text=topic.title, bg=t.c["surface_container"], fg=t.c["on_surface"],
                 font=t.font("headline"), anchor="w", justify="left",
                 wraplength=720).pack(fill="x", pady=(8, 10))
        self.wrapped.append(card.content.winfo_children()[-1])
        for para in topic.summary.split("\n\n"):
            label = tk.Label(card.content, text=para, bg=t.c["surface_container"],
                             fg=t.c["on_surface_variant"], font=t.font("body"), anchor="w",
                             justify="left", wraplength=720)
            label.pack(fill="x", pady=(0, 8))
            self.wrapped.append(label)

        steps = tk.Frame(card.content, bg=t.c["surface_container"])
        steps.pack(fill="x", pady=(8, 4))
        tk.Label(steps, text="Do this", bg=t.c["surface_container"], fg=t.c["on_surface"],
                 font=t.font("title"), anchor="w").pack(fill="x", pady=(0, 6))
        for i, text in enumerate(topic.steps, 1):
            row = tk.Frame(steps, bg=t.c["surface_container"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=str(i), bg=t.c["secondary_container"], fg=t.c["on_secondary_container"],
                     font=t.font("label"), width=2).pack(side="left", anchor="n")
            label = tk.Label(row, text=text, bg=t.c["surface_container"], fg=t.c["on_surface"],
                             font=t.font("body"), anchor="w", justify="left", wraplength=670)
            label.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self.wrapped.append(label)

        note = tk.Frame(card.content, bg=t.c["surface_high"])
        note.pack(fill="x", pady=(14, 0))
        tk.Label(note, text="Good to know", bg=t.c["surface_high"], fg=t.c["on_surface"],
                 font=t.font("label"), anchor="w").pack(fill="x", padx=14, pady=(10, 2))
        note_label = tk.Label(note, text=topic.note, bg=t.c["surface_high"],
                              fg=t.c["on_surface_variant"], font=t.font("body"), anchor="w",
                              justify="left", wraplength=670)
        note_label.pack(fill="x", padx=14, pady=(0, 12))
        self.wrapped.append(note_label)

        action = tk.Frame(card.content, bg=t.c["surface_container"])
        action.pack(fill="x", pady=(16, 0))
        Pill(action, topic.action, lambda v=topic.view: self.app.show(v), t, "filled").pack(side="left")
        Pill(action, "Open console", lambda: self.app.show("console"), t, "text").pack(side="left", padx=(8, 0))
        self._rewrap()

    def _rewrap(self, event=None) -> None:
        width = event.width if event is not None else self.body.winfo_width()
        wrap = max(300, min(760, width - 120))
        for label in self.wrapped:
            try:
                label.configure(wraplength=wrap)
            except tk.TclError:
                pass
