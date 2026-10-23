"""Runs: artifacts as they exist on disk, with the raw JSON one click away."""

from __future__ import annotations

import json
import re
import time
import tkinter as tk
from tkinter import ttk

from ..services import h2, runs
from ..widgets import Card, Chip, Pill, make_text_tabbable
from .base import View


class RunsView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.items: list[runs.Artifact] = []
        self.current: runs.Artifact | None = None

        body = tk.Frame(self, bg=t.c["surface"])
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(0, weight=1)

        left = Card(body, t, title="Artifacts")
        left.grid(row=0, column=0, sticky="nsew")
        bar = tk.Frame(left.content, bg=t.c["surface_container"])
        bar.pack(fill="x", pady=(0, 6))
        Pill(bar, "Refresh", self.refresh, t, "text", height=28, pad=8).pack(side="right")
        self.caption = tk.Label(bar, text="", bg=t.c["surface_container"],
                                fg=t.c["on_surface_variant"], font=t.font("caption"))
        self.caption.pack(side="left")

        self.tree = ttk.Treeview(left.content, columns=("kind", "when"), show="tree headings", height=18)
        self.tree.heading("#0", text="Location")
        self.tree.heading("kind", text="Kind")
        self.tree.heading("when", text="Modified")
        self.tree.column("#0", width=220)
        self.tree.column("kind", width=90, anchor="w")
        self.tree.column("when", width=130, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        self.empty = tk.Frame(left.content, bg=t.c["surface_container"])
        tk.Label(self.empty, text="No artifacts yet", bg=t.c["surface_container"], fg=t.c["on_surface"],
                 font=t.font("title"), anchor="w").pack(fill="x", pady=(18, 4))
        tk.Label(self.empty, text="Run the credential-free demo to create a runs tree this view can read.",
                 bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("body"),
                 anchor="w", justify="left", wraplength=360).pack(fill="x")
        Pill(self.empty, "Run demo", self._demo, t, "tonal").pack(anchor="w", pady=(12, 0))

        right = Card(body, t, title="Detail")
        right.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        head = tk.Frame(right.content, bg=t.c["surface_container"])
        head.pack(fill="x")
        self.headline = tk.Label(head, text="", bg=t.c["surface_container"], fg=t.c["on_surface"],
                                 font=t.font("title"), anchor="w")
        self.headline.pack(side="left")
        Pill(head, "Copy JSON", self._copy, t, "text", height=28, pad=8).pack(side="right")
        Pill(head, "Open folder", self._open, t, "outlined", height=28, pad=8).pack(side="right", padx=(0, 8))
        self.chips = tk.Frame(right.content, bg=t.c["surface_container"])
        self.chips.pack(fill="x", pady=(6, 6))
        self.text = tk.Text(right.content, wrap="none", bd=0, highlightthickness=0,
                            bg=t.c["surface_low"], fg=t.c["on_surface"], font=t.font("mono_sm"),
                            padx=10, pady=8)
        y = ttk.Scrollbar(right.content, orient="vertical", command=self.text.yview)
        x = ttk.Scrollbar(right.content, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.text.tag_configure("jkey", foreground=t.c["primary"])
        self.text.tag_configure("jstr", foreground=t.c["success"])
        self.text.tag_configure("jnum", foreground=t.c["warning"])
        make_text_tabbable(self.text)
        y.pack(side="right", fill="y")
        x.pack(side="bottom", fill="x")
        self.text.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self) -> None:
        self.items = self.app.artifacts()
        self.tree.delete(*self.tree.get_children())
        for art in self.items:
            rel = art.path.parent.name or str(art.path.parent)
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(art.mtime))
            self.tree.insert("", "end", iid=str(art.path), text=rel, values=(art.kind, when))
        self.caption.configure(text=f"{len(self.items)} artifact(s)")
        if self.items:
            self.empty.pack_forget()
            self.tree.pack(fill="both", expand=True)
        else:
            self.tree.pack_forget()
            self.empty.pack(fill="both", expand=True)
        if self.items and not self.tree.selection():
            self.tree.selection_set(str(self.items[0].path))
            self._select()

    def _demo(self) -> None:
        self.app.show("run")
        self.app.run_action("demo", h2.Options(output="runs/demo", k=2), label="demo")

    def _select(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        self.current = next((a for a in self.items if str(a.path) == sel[0]), None)
        if self.current is None:
            return
        t = self.theme
        self.headline.configure(text=f"{self.current.kind} · {self.current.path.name}")
        for child in self.chips.winfo_children():
            child.destroy()
        if self.current.error:
            Chip(self.chips, t, "unreadable", "error").pack(side="left", padx=(0, 8))
        summary = runs.summarize(self.current)
        for key, value in summary.items():
            if key == "kind":
                continue
            tone = "neutral"
            if key == "failed":
                tone = "error" if value else "success"
            elif key == "tasks":
                tone = "primary"
            Chip(self.chips, t, f"{key}: {value}", tone).pack(side="left", padx=(0, 8))
        self.text.delete("1.0", "end")
        if self.current.error:
            self.text.insert("1.0", self.current.error)
        else:
            self._insert_json(json.dumps(self.current.data, indent=2, default=str)[:200_000])

    def _insert_json(self, raw: str) -> None:
        self.text.insert("1.0", raw)
        for m in re.finditer(r'"(?:[^"\\]|\\.)*"(?=\s*:)', raw):
            self.text.tag_add("jkey", f"1.0 + {m.start()} chars", f"1.0 + {m.end()} chars")
        for m in re.finditer(r':\s*("(?:[^"\\]|\\.)*")', raw):
            self.text.tag_add("jstr", f"1.0 + {m.start(1)} chars", f"1.0 + {m.end(1)} chars")
        for m in re.finditer(r':\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null)', raw):
            self.text.tag_add("jnum", f"1.0 + {m.start(1)} chars", f"1.0 + {m.end(1)} chars")

    def _copy(self) -> None:
        if self.current is None:
            return
        self.clipboard_clear()
        self.clipboard_append(json.dumps(self.current.data, indent=2, default=str))
        self.app.toast("JSON copied")

    def _open(self) -> None:
        if self.current is not None:
            self.app.open_path(self.current.path.parent)
