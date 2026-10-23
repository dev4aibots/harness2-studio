"""Tracker: benchmark results and improvement tracker.

Shows every completed run with its score, compares against the previous run
to surface exactly what improved or regressed, and points at the guide topic
that explains how to improve each component.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..services import runs
from ..widgets import Card, Pill
from .base import View

# Map each component key to the guide topic that explains how to improve it.
GUIDE_FOR_COMPONENT = {
    "C1": "harness",
    "C2": "harness",
    "C3": "harness",
    "C4": "harness",
    "C5": "harness",
    "C6": "harness",
    "C7": "harness",
    "C8": "harness",
}


class TrackerView(View):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        t = self.theme
        self.items: list[runs.Artifact] = []

        body = tk.Frame(self, bg=t.c["surface"])
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(0, weight=1)

        # -- left: run list -------------------------------------------
        left = Card(body, t, title="Benchmark runs")
        left.grid(row=0, column=0, sticky="nsew")
        bar = tk.Frame(left.content, bg=t.c["surface_container"])
        bar.pack(fill="x", pady=(0, 6))
        Pill(bar, "Refresh", self.refresh, t, "text", height=28, pad=8).pack(side="right")
        self.caption = tk.Label(bar, text="", bg=t.c["surface_container"],
                                fg=t.c["on_surface_variant"], font=t.font("caption"))
        self.caption.pack(side="left")

        self.tree = ttk.Treeview(left.content, columns=("score", "failed", "bench", "k", "when"),
                                 show="tree headings", height=20)
        self.tree.heading("#0", text="Run / task")
        self.tree.heading("score", text="Score")
        self.tree.heading("failed", text="Failed")
        self.tree.heading("bench", text="Bench")
        self.tree.heading("k", text="k")
        self.tree.heading("when", text="Finished")
        self.tree.column("#0", width=200)
        self.tree.column("score", width=70, anchor="center")
        self.tree.column("failed", width=70, anchor="center")
        self.tree.column("bench", width=90, anchor="w")
        self.tree.column("k", width=40, anchor="center")
        self.tree.column("when", width=130, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        self.empty = tk.Frame(left.content, bg=t.c["surface_container"])
        tk.Label(self.empty, text="No benchmark runs yet",
                 bg=t.c["surface_container"], fg=t.c["on_surface"],
                 font=t.font("title"), anchor="w").pack(fill="x", pady=(18, 4))
        tk.Label(self.empty, text="Start a sweep on the Run view, then come back here to see results.",
                 bg=t.c["surface_container"], fg=t.c["on_surface_variant"], font=t.font("body"),
                 anchor="w", justify="left", wraplength=340).pack(fill="x")
        Pill(self.empty, "Open Run view", self._open_run, t, "tonal").pack(anchor="w", pady=(12, 0))

        # -- right: detail + improvement tracker ----------------------
        right = tk.Frame(body, bg=t.c["surface"])
        right.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # current run header
        head = Card(right, t, title="Current run", subtitle="Most recent benchmark result")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.run_label = tk.Label(head.content, text="—", bg=t.c["surface_container"],
                                  fg=t.c["on_surface"], font=t.font("headline"), anchor="w")
        self.run_label.pack(fill="x")
        self.run_detail = tk.Label(head.content, text="", bg=t.c["surface_container"],
                                   fg=t.c["on_surface_variant"], font=t.font("caption"),
                                   anchor="w", justify="left", wraplength=460)
        self.run_detail.pack(fill="x", pady=(2, 0))

        # comparison vs previous
        cmp_card = Card(right, t, title="Change vs previous run", subtitle="Green = improved, red = regressed")
        cmp_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.cmp_score = tk.Label(cmp_card.content, text="—", bg=t.c["surface_container"],
                                  fg=t.c["on_surface_variant"], font=t.font("headline"), anchor="w")
        self.cmp_score.pack(fill="x")
        self.cmp_detail = tk.Label(cmp_card.content, text="", bg=t.c["surface_container"],
                                   fg=t.c["on_surface_variant"], font=t.font("caption"),
                                   anchor="w", justify="left", wraplength=460)
        self.cmp_detail.pack(fill="x", pady=(2, 0))

        # improvement tracker
        imp = Card(right, t, title="What to improve next", subtitle="Exact component to edit, based on results")
        imp.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        right.grid_rowconfigure(2, weight=1)
        self.imp_text = tk.Text(imp.content, wrap="word", bd=0, highlightthickness=0,
                                bg=t.c["surface_container"], fg=t.c["on_surface"],
                                font=t.font("body"), padx=12, pady=10, state="disabled")
        y = ttk.Scrollbar(imp.content, orient="vertical", command=self.imp_text.yview)
        self.imp_text.configure(yscrollcommand=y.set)
        y.pack(side="right", fill="y")
        self.imp_text.pack(side="left", fill="both", expand=True)

        # go-to-harness button
        bar2 = tk.Frame(right, bg=t.c["surface"])
        bar2.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.to_harness = Pill(bar2, "Open in Harness view", self._go_harness, t, "filled",
                               height=34, pad=16)
        self.to_harness.pack(side="left")
        self.to_harness.set_enabled(False)

        self.refresh()

    # -- data ---------------------------------------------------------
    def refresh(self) -> None:
        self.items = self.app.artifacts()
        # only show runs that have a score of some kind
        scored = [a for a in self.items if a.kind in ("judged", "demo", "summary")]
        self.tree.delete(*self.tree.get_children())
        for art in scored:
            data = art.data or {}
            if isinstance(data, list):
                data = data[0] if data else {}
            run_dir = art.path.parent.name
            score = data.get("score", data.get("done", "—"))
            failed = data.get("failed", "—")
            bench = data.get("bench", "?")
            k = data.get("k", "—")
            when = self._fmt_time(art.mtime)
            self.tree.insert("", "end", iid=str(art.path), text=run_dir,
                             values=(score, failed, bench, k, when))
        self.caption.configure(text=f"{len(scored)} run(s)")
        if scored:
            self.empty.pack_forget()
            self.tree.pack(fill="both", expand=True)
            self.tree.selection_set(str(scored[0].path))
            self._select()
        else:
            self.tree.pack_forget()
            self.empty.pack(fill="both", expand=True)
        self._clear_detail()

    def _fmt_time(self, mtime: float) -> str:
        import time
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))

    # -- selection ----------------------------------------------------
    def _select(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        art = next((a for a in self.items if str(a.path) == sel[0]), None)
        if art is None:
            return
        t = self.theme
        data = art.data or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        run_dir = art.path.parent.name
        self.run_label.configure(text=run_dir)

        # build detail line
        parts = []
        if data.get("bench"):
            parts.append(f"bench: {data['bench']}")
        if data.get("k") is not None:
            parts.append(f"k: {data['k']}")
        if data.get("mode"):
            parts.append(f"mode: {data['mode']}")
        if "score" in data:
            parts.append(f"score: {data['score']}")
        if "done" in data:
            parts.append(f"done: {data['done']}")
        if "failed" in data:
            parts.append(f"failed: {data['failed']}")
        self.run_detail.configure(text="   ·   ".join(parts) if parts else "no score data")

        # comparison vs previous scored run
        idx = next((i for i, a in enumerate(self.items) if str(a.path) == sel[0]), -1)
        prev = None
        for j in range(idx + 1, len(self.items)):
            p = self.items[j]
            if p.kind in ("judged", "demo", "summary") and str(p.path) != str(art.path):
                prev = p
                break
        if prev is not None:
            pd = prev.data or {}
            if isinstance(pd, list):
                pd = pd[0] if pd else {}
            cur_score = data.get("score", data.get("done", 0))
            prev_score = pd.get("score", pd.get("done", 0))
            try:
                delta = float(cur_score) - float(prev_score)
            except (TypeError, ValueError):
                delta = None
            if delta is not None:
                if delta > 0:
                    self.cmp_score.configure(text=f"+{delta:.2f}", fg=t.c["success"])
                    self.cmp_detail.configure(text=f"Improved by {delta:.2f} points vs {prev.path.parent.name}")
                elif delta < 0:
                    self.cmp_score.configure(text=f"{delta:.2f}", fg=t.c["error"])
                    self.cmp_detail.configure(text=f"Regressed by {abs(delta):.2f} points vs {prev.path.parent.name}")
                else:
                    self.cmp_score.configure(text="0.00", fg=t.c["on_surface_variant"])
                    self.cmp_detail.configure(text=f"Unchanged vs {prev.path.parent.name}")
            else:
                self.cmp_score.configure(text="—", fg=t.c["on_surface_variant"])
                self.cmp_detail.configure(text="Cannot compare (no numeric score in previous run)")
        else:
            self.cmp_score.configure(text="—", fg=t.c["on_surface_variant"])
            self.cmp_detail.configure(text="No previous run to compare against")

        # improvement tracker
        self._build_improvement(data)
        self.to_harness.set_enabled(True)

    def _build_improvement(self, data) -> None:
        """Analyze the result and tell the user exactly what to improve."""
        if isinstance(data, list):
            data = data[0] if data else {}
        lines: list[str] = []
        failed = data.get("failed", 0)
        score = data.get("score", 0)

        # Determine which component(s) to suggest
        suggestions = []

        if failed and failed > 0:
            suggestions.append(
                f"{failed} task(s) failed. Open Harness view and inspect C1 (system prompt) — "
                "the executor's instructions are the first thing to fix.")
            suggestions.append(
                "Guide: 'Inspect and edit C1–C8' explains how to edit each component.")
        if score is not None and isinstance(score, (int, float)) and score < 0.7:
            suggestions.append(
                f"Score is {score:.2f} — below 0.70. Prioritize C3 (memory) and C4 (tool guidance) "
                "so the executor retains context and uses tools correctly.")
            suggestions.append(
                "Guide: 'Run a sweep' covers tuning k and seed for more attempts.")
        if suggestions:
            lines.extend(suggestions)
        else:
            lines.append("No obvious regressions. All tasks passing and score is healthy.")
            lines.append("Try raising k (recursion) on the Run view to let the improver iterate more.")
            lines.append("Or switch to a stronger executor model on the Models view.")

        lines.append("")
        lines.append("Quick actions:")
        lines.append("• Edit C1–C8 → Harness view")
        lines.append("• Adjust k / subset / executor → Run view")
        lines.append("• Change models / effort → Models view")
        lines.append("• Read the how-to → Guide (button above)")

        text = "\n".join(lines)
        self.imp_text.configure(state="normal")
        self.imp_text.delete("1.0", "end")
        self.imp_text.insert("1.0", text)
        self.imp_text.configure(state="disabled")

    def _clear_detail(self) -> None:
        t = self.theme
        self.run_label.configure(text="—")
        self.run_detail.configure(text="")
        self.cmp_score.configure(text="—", fg=t.c["on_surface_variant"])
        self.cmp_detail.configure(text="")
        self.imp_text.configure(state="normal")
        self.imp_text.delete("1.0", "end")
        self.imp_text.insert("1.0", "Select a run to see its score and improvement suggestions.")
        self.imp_text.configure(state="disabled")
        self.to_harness.set_enabled(False)

    # -- actions ------------------------------------------------------
    def _open_run(self) -> None:
        self.app.show("run")

    def _go_harness(self) -> None:
        self.app.show("harness")
