"""Tk widgets that carry the Material 3 feel Tk lacks natively.

Rules applied here (from the M3 spec, not invented):
- elevation is faked as surface step + 1px outline, never as a drop shadow;
- state layers are precomputed color blends at 8% hover / 12% press;
- every control keeps a visible 2px focus ring;
- pointer targets are >= 32px tall.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from tkinter import ttk
from typing import ClassVar

from .theme import SPACE, Theme


def blend(a: str, b: str, t: float) -> str:
    a, b = a.lstrip("#"), b.lstrip("#")
    ar, ag, ab = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
    br, bg, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    return f"#{round(ar + (br - ar) * t):02x}{round(ag + (bg - ag) * t):02x}{round(ab + (bb - ab) * t):02x}"


def parent_bg(widget: tk.Misc, fallback: str) -> str:
    try:
        return str(widget.cget("bg"))
    except (tk.TclError, AttributeError):
        return fallback


class Pill(tk.Canvas):
    """Rounded Material button/segmented option with correct fill and border."""

    VARIANTS: ClassVar[dict[str, tuple[str | None, str, str | None]]] = {
        "filled": ("primary", "on_primary", None),
        "tonal": ("secondary_container", "on_secondary_container", None),
        "outlined": (None, "primary", "outline"),
        "quiet": (None, "on_surface", "outline"),
        "text": (None, "primary", None),
        "danger": ("error_container", "on_error_container", None),
    }

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        theme: Theme,
        variant: str = "filled",
        icon: str = "",
        height: int = 40,
        pad: int = 20,
        width: int | None = None,
        bg: str | None = None,
    ) -> None:
        self.theme = theme
        self._surface = bg or parent_bg(parent, theme.c["surface"])
        super().__init__(parent, highlightthickness=0, bd=0, bg=self._surface, takefocus=1, height=height)
        self.variant = variant
        self.command = command
        self.icon = icon
        self._height = height
        self._pad = pad
        self._enabled = True
        self._hover_t = 0.0
        self._hover_target = False
        self._anim_id = None
        self._press = False
        self._label = text
        self.configure(cursor="hand2")
        self._resize(width)
        self._draw()
        for seq, cb in (
            ("<Enter>", self._on_enter),
            ("<Leave>", self._on_leave),
            ("<ButtonPress-1>", self._on_press),
            ("<ButtonRelease-1>", self._on_release),
            ("<Return>", lambda _e: self._fire()),
            ("<space>", lambda _e: self._fire()),
            ("<FocusIn>", lambda _e: self._draw()),
            ("<FocusOut>", lambda _e: self._draw()),
            ("<Configure>", lambda _e: self._draw()),
        ):
            self.bind(seq, cb)

    # -- geometry -------------------------------------------------------
    def _label_text(self) -> str:
        return f"{self.icon}  {self._label}" if self.icon else self._label

    def _resize(self, width: int | None) -> None:
        w = width or self.theme.font("label_lg").measure(self._label_text()) + self._pad * 2
        self.configure(width=max(w, 56))

    def set_text(self, text: str) -> None:
        self._label = text
        self._resize(None)
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    # -- palette --------------------------------------------------------
    def _palette(self) -> tuple[str, str, str | None]:
        bg_role, fg_role, border_role = self.VARIANTS[self.variant]
        c = self.theme.c
        if not self._enabled:
            return c["surface_high"], blend(c["surface_high"], c["on_surface"], 0.65), c["outline_variant"]
        bg = c[bg_role] if bg_role else self._surface
        fg = c[fg_role]
        border = c[border_role] if border_role else None
        target = c["on_primary"] if self.variant == "filled" else c["on_surface"]
        if self._hover_t:
            bg = blend(bg, target, 0.08 * self._hover_t)
        if self._press:
            bg = blend(bg, target, 0.12)
        return bg, fg, border

    # -- drawing --------------------------------------------------------
    def _draw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), int(float(str(self["width"]) or 0)), 2)
        h = max(self.winfo_height(), self._height, 2)
        inset = 3  # reserves room for a focus ring that never overlaps the fill
        x1, y1, x2, y2 = inset, inset, w - inset, h - inset
        radius = (y2 - y1) / 2 if self.variant in ("filled", "tonal", "danger") else 10
        bg, fg, border = self._palette()

        self._shape(x1, y1, x2, y2, radius, fill=bg, border=border)
        if self.focus_get() is self:
            self._shape(0.5, 0.5, w - 0.5, h - 0.5, radius + inset, fill=None,
                        border=self.theme.c["on_surface"], width=2)
        self.create_text(w / 2, h / 2, text=self._label_text(), fill=fg, font=self.theme.font("label_lg"))

    def _shape(self, x1, y1, x2, y2, r, fill: str | None, border: str | None, width: int = 1) -> None:
        r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
        if fill:
            self.create_rectangle(x1 + r, y1, x2 - r, y2, outline="", fill=fill)
            self.create_rectangle(x1, y1 + r, x2, y2 - r, outline="", fill=fill)
            for cx, cy in ((x1, y1), (x2 - 2 * r, y1), (x1, y2 - 2 * r), (x2 - 2 * r, y2 - 2 * r)):
                self.create_arc(cx, cy, cx + 2 * r, cy + 2 * r, start=0, extent=359.9,
                                style="pieslice", outline=fill, fill=fill)
        if border:
            self.create_line(x1 + r, y1, x2 - r, y1, fill=border, width=width)
            self.create_line(x1 + r, y2, x2 - r, y2, fill=border, width=width)
            self.create_line(x1, y1 + r, x1, y2 - r, fill=border, width=width)
            self.create_line(x2, y1 + r, x2, y2 - r, fill=border, width=width)
            for cx, cy, start in ((x1, y1, 90), (x2 - 2 * r, y1, 0), (x1, y2 - 2 * r, 180), (x2 - 2 * r, y2 - 2 * r, 270)):
                self.create_arc(cx, cy, cx + 2 * r, cy + 2 * r, start=start, extent=90,
                                style="arc", outline=border, width=width)

    # -- events ---------------------------------------------------------
    def _on_enter(self, _e=None):
        self._set_hover(True)

    def _on_leave(self, _e=None):
        self._press = False
        self._set_hover(False)

    def _set_hover(self, on: bool) -> None:
        if self._hover_target == on:
            return
        self._hover_target = on
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except tk.TclError:
                pass
            self._anim_id = None
        self._step_hover()

    def _step_hover(self) -> None:
        if not self.winfo_exists():
            return
        target = 1.0 if self._hover_target else 0.0
        delta = 0.1 if target > self._hover_t else -0.1
        self._hover_t = max(0.0, min(1.0, self._hover_t + delta))
        self._draw()
        if abs(self._hover_t - target) > 0.001:
            self._anim_id = self.after(16, self._step_hover)

    def _on_press(self, _e=None):
        if not self._enabled:
            return
        self._press = True
        self.focus_set()
        self._draw()

    def _on_release(self, _e=None):
        was = self._press
        self._press = False
        self._draw()
        if was and self._enabled:
            self._fire()

    def _fire(self):
        if self._enabled:
            self.command()


class Toggle(Pill):
    """Checkbox replacement: filled when on, outlined when off, state in the label."""

    def __init__(self, parent, text: str, value: bool, command: Callable[[bool], None], theme: Theme, bg: str | None = None):
        self._value = value
        self._base = text
        self._on_change = command
        super().__init__(parent, f"{'✓ ' if value else ''}{text}", self._toggle, theme,
                         variant="filled" if value else "outlined", height=32, pad=14, bg=bg)

    def _toggle(self) -> None:
        self._value = not self._value
        self.variant = "filled" if self._value else "outlined"
        self._label = f"{'✓ ' if self._value else ''}{self._base}"
        self._resize(None)
        self._draw()
        self._on_change(self._value)

    @property
    def value(self) -> bool:
        return self._value


class Card(tk.Frame):
    """M3 outlined card: surface-container fill, 1px outline-variant."""

    def __init__(self, parent: tk.Misc, theme: Theme, pad: int = SPACE["lg"], title: str = "", subtitle: str = ""):
        super().__init__(parent, bg=theme.c["surface_container"], highlightthickness=1,
                         highlightbackground=theme.c["outline_variant"], highlightcolor=theme.c["outline_variant"])
        self.theme = theme
        self.body = tk.Frame(self, bg=theme.c["surface_container"])
        self.body.pack(fill="both", expand=True, padx=pad, pady=pad)
        if title:
            tk.Label(self.body, text=title, bg=theme.c["surface_container"], fg=theme.c["on_surface"],
                     font=theme.font("title"), anchor="w").pack(fill="x")
        if subtitle:
            tk.Label(self.body, text=subtitle, bg=theme.c["surface_container"], fg=theme.c["on_surface_variant"],
                     font=theme.font("caption"), anchor="w", justify="left", wraplength=760).pack(fill="x", pady=(2, 0))
        self.content = tk.Frame(self.body, bg=theme.c["surface_container"])
        self.content.pack(fill="both", expand=True, pady=(SPACE["sm"], 0))


class ProgressBar(tk.Canvas):
    """Determinate 10px M3 progress indicator; no fake animation when idle."""

    def __init__(self, parent: tk.Misc, theme: Theme, height: int = 10):
        super().__init__(parent, height=height, highlightthickness=0, bd=0,
                         bg=parent_bg(parent, theme.c["surface_container"]))
        self.theme = theme
        self._fraction = 0.0
        self._height = height
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, fraction: float) -> None:
        self._fraction = max(0.0, min(1.0, float(fraction)))
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 2)
        h = max(self.winfo_height(), self._height, 2)
        r = h / 2
        self._bar(0, 0, w, h, r, self.theme.c["surface_high"])
        if self._fraction > 0:
            self._bar(0, 0, max(h, w * self._fraction), h, r, self.theme.c["primary"])

    def _bar(self, x1, y1, x2, y2, r, fill) -> None:
        if x2 <= x1:
            return
        self.create_rectangle(x1 + r, y1, x2 - r, y2, outline="", fill=fill)
        self.create_rectangle(x1, y1 + r, x2, y2 - r, outline="", fill=fill)
        for cx, cy in ((x1, y1), (x2 - 2 * r, y1), (x1, y2 - 2 * r), (x2 - 2 * r, y2 - 2 * r)):
            self.create_arc(cx, cy, cx + 2 * r, cy + 2 * r, start=0, extent=359.9,
                            style="pieslice", outline=fill, fill=fill)


class Chip(tk.Label):
    def __init__(self, parent, theme: Theme, text: str, tone: str = "neutral"):
        palette = {
            "neutral": (theme.c["surface_high"], theme.c["on_surface_variant"]),
            "primary": (theme.c["primary_container"], theme.c["on_primary_container"]),
            "success": (theme.c["success_container"], theme.c["success"]),
            "error": (theme.c["error_container"], theme.c["on_error_container"]),
            "warning": (theme.c["surface_high"], theme.c["warning"]),
        }[tone]
        super().__init__(parent, text=f" {text} ", bg=palette[0], fg=palette[1],
                         font=theme.font("caption"), padx=6, pady=3)


class StatCard(Card):
    def __init__(self, parent, theme: Theme, label: str, value: str, hint: str = ""):
        super().__init__(parent, theme, pad=SPACE["md"])
        self.value = tk.Label(self.content, text=value, bg=theme.c["surface_container"],
                              fg=theme.c["on_surface"], font=theme.font("headline"), anchor="w")
        self.value.pack(fill="x")
        tk.Label(self.content, text=label, bg=theme.c["surface_container"], fg=theme.c["on_surface_variant"],
                 font=theme.font("label"), anchor="w").pack(fill="x")
        self.hint = tk.Label(self.content, text=hint, bg=theme.c["surface_container"],
                             fg=theme.c["on_surface_variant"], font=theme.font("caption"), anchor="w",
                             justify="left", wraplength=220)
        self.hint.pack(fill="x", pady=(2, 0))

    def update_value(self, value: str, hint: str | None = None) -> None:
        self.value.configure(text=value)
        if hint is not None:
            self.hint.configure(text=hint)


class Segmented(tk.Frame):
    """Exclusive choice rendered as pills; parent background is inherited."""

    def __init__(self, parent, theme: Theme, options: Iterable[tuple[str, str]], value: str,
                 command: Callable[[str], None] | None = None):
        bg = parent_bg(parent, theme.c["surface"])
        super().__init__(parent, bg=bg)
        self.theme = theme
        self.command = command
        self.value = value
        self.buttons: dict[str, Pill] = {}
        for key, label in options:
            b = Pill(self, label, lambda k=key: self.select(k), theme,
                     variant="filled" if key == value else "quiet", height=32, pad=14, bg=bg)
            b.pack(side="left", padx=(0, SPACE["sm"]))
            self.buttons[key] = b

    def select(self, key: str, notify: bool = True) -> None:
        self.value = key
        for k, b in self.buttons.items():
            b.variant = "filled" if k == key else "quiet"
            b._draw()
        if notify and self.command:
            self.command(key)


class Console(tk.Frame):
    """Streaming log with tags, bounded lines, honest autoscroll."""

    TAGS: ClassVar[dict[str, tuple[str, str]]] = {
        "cmd": ("primary", "bold"),
        "out": ("on_surface", "normal"),
        "dim": ("on_surface_variant", "normal"),
        "ok": ("success", "bold"),
        "err": ("error", "bold"),
        "warn": ("warning", "bold"),
    }

    def __init__(self, parent, theme: Theme, height: int = 14):
        super().__init__(parent, bg=theme.c["surface_low"], highlightthickness=1,
                         highlightbackground=theme.c["outline_variant"])
        self.theme = theme
        self.text = tk.Text(
            self, height=height, wrap="none", bd=0, highlightthickness=1,
            highlightbackground=theme.c["surface_low"], highlightcolor=theme.c["primary"],
            bg=theme.c["surface_low"], fg=theme.c["on_surface"],
            insertbackground=theme.c["on_surface"], font=theme.font("mono"),
            padx=12, pady=10, state="disabled",
        )
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        for tag, (role, weight) in self.TAGS.items():
            font = theme.font("mono")
            self.text.tag_configure(tag, foreground=theme.c[role],
                                    font=(font.actual("family"), font.actual("size"), weight))

    def append(self, line: str, tag: str = "out") -> None:
        at_bottom = self.text.yview()[1] > 0.995
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n", tag)
        if int(self.text.index("end-1c").split(".")[0]) > 4000:
            self.text.delete("1.0", "600.0")
        self.text.configure(state="disabled")
        if at_bottom:
            self.text.see("end")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def dump(self) -> str:
        return self.text.get("1.0", "end-1c")


class ConfirmDialog(tk.Toplevel):
    """M3-style confirmation for destructive actions; focus starts on Cancel."""

    def __init__(self, app, theme: Theme, title: str, message: str, confirm_label: str,
                 on_confirm: Callable[[], None]):
        super().__init__(app)
        self.theme = theme
        self.on_confirm = on_confirm
        self.transient(app)
        self.configure(bg=theme.c["outline_variant"])
        self.title(title)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        shell = tk.Frame(self, bg=theme.c["surface_container"])
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        body = tk.Frame(shell, bg=theme.c["surface_container"])
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text=title, bg=theme.c["surface_container"], fg=theme.c["on_surface"],
                 font=theme.font("title"), anchor="w").pack(fill="x")
        tk.Label(body, text=message, bg=theme.c["surface_container"], fg=theme.c["on_surface_variant"],
                 font=theme.font("body"), anchor="w", justify="left", wraplength=420).pack(fill="x", pady=(6, 16))
        row = tk.Frame(body, bg=theme.c["surface_container"])
        row.pack(fill="x")
        cancel = Pill(row, "Cancel", self.close, theme, "outlined", bg=theme.c["surface_container"])
        cancel.pack(side="right")
        confirm = Pill(row, confirm_label, self._confirm, theme, "danger", bg=theme.c["surface_container"])
        confirm.pack(side="right", padx=(0, 8))

        width, height = 480, 200
        x = app.winfo_rootx() + (app.winfo_width() - width) // 2
        y = app.winfo_rooty() + (app.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.bind("<Escape>", lambda _e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        cancel.focus_set()

    def _confirm(self) -> None:
        self.close()
        self.on_confirm()

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def make_text_tabbable(text: tk.Text) -> None:
    """Tk Text swallows Tab (keyboard trap). Route it back to the focus order."""
    def next_focus(_e=None):
        target = text.tk_focusNext()
        if target is not None:
            target.focus_set()
        return "break"

    def prev_focus(_e=None):
        target = text.tk_focusPrev()
        if target is not None:
            target.focus_set()
        return "break"

    text.bind("<Tab>", next_focus)
    text.bind("<Shift-Tab>", prev_focus)
    text.bind("<ISO_Left_Tab>", prev_focus)


class Scroller(tk.Frame):
    """Vertically scrollable container that keeps its width honest."""

    def __init__(self, parent, theme: Theme, bg: str | None = None):
        surface = bg or theme.c["surface"]
        super().__init__(parent, bg=surface)
        self.canvas = tk.Canvas(self, bg=surface, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=surface)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        for widget in (self.canvas, self.inner):
            widget.bind("<Enter>", self._bind_wheel, add="+")
            widget.bind("<Leave>", self._maybe_unbind, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(seq)

    def _bind_wheel(self, _e=None):
        self.canvas.bind_all("<MouseWheel>", self._wheel)
        self.canvas.bind_all("<Button-4>", lambda _e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda _e: self.canvas.yview_scroll(1, "units"))

    def _maybe_unbind(self, event):
        """Children fire Leave on their parent; only unbind when the pointer truly left."""
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self:
                return
            widget = getattr(widget, "master", None)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(seq)

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units")


class SearchableDropdown(ttk.Frame):
    """A Combobox with search-as-you-type filtering and effort preset."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        values: list[str],
        default: str = "",
        width: int = 30,
        effort: bool = False,
        command: Callable[[str], None] | None = None,
    ):
        super().__init__(parent, bg=theme.c["surface_container"])
        self.theme = theme
        self.all_values = list(values)
        self.command = command

        row = tk.Frame(self, bg=theme.c["surface_container"])
        row.pack(fill="x")

        self.var = tk.StringVar(value=default)
        self.combo = ttk.Combobox(
            self,
            textvariable=self.var,
            values=self.all_values,
            width=width,
            state="normal",
        )
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.bind("<KeyRelease>", self._on_key)
        self.combo.bind("<<ComboboxSelected>>", self._on_select)

        if effort:
            self.effort_var = tk.StringVar(value="medium")
            self.effort = ttk.OptionMenu(
                self, self.effort_var, "medium", "low", "medium", "high", width=8
            )
            self.effort.pack(side="left", padx=(6, 0))

        self.var.trace_add("write", self._on_var_change)

    def _on_key(self, _e=None) -> None:
        typed = self.var.get()
        if not typed:
            filtered = self.all_values
        else:
            t = typed.lower()
            filtered = [v for v in self.all_values if t in v.lower()]
        self.combo.configure(values=filtered)
        if filtered:
            self.combo.event_generate("<Down>")

    def _on_var_change(self, *_a) -> None:
        if self.command:
            self.command(self.var.get())

    def _on_select(self, _e=None) -> None:
        if self.command:
            self.command(self.var.get())

    def get(self) -> str:
        return self.var.get()

    def get_effort(self) -> str:
        return getattr(self, "effort_var", tk.StringVar(value="medium")).get()

    def set(self, value: str) -> None:
        self.var.set(value)
        self.combo.configure(values=self.all_values)


class ProgressTracker(Card):
    """Progress tracker showing improvement rounds and score trajectory."""

    def __init__(self, parent: tk.Misc, theme: Theme):
        super().__init__(parent, theme, title="Improvement Progress", subtitle="Round-by-round score trajectory")
        self.bars: list[tk.Frame] = []
        self.labels: list[tk.Label] = []

    def add_round(self, round_num: int, score: float, target: float = 0.98) -> None:
        row = tk.Frame(self.content, bg=self.theme.c["surface_container"])
        row.pack(fill="x", pady=2)

        lbl = tk.Label(
            row,
            text=f"Round {round_num}",
            bg=self.theme.c["surface_container"],
            fg=self.theme.c["on_surface_variant"],
            font=self.theme.font("caption"),
            width=12,
            anchor="w",
        )
        lbl.pack(side="left")

        bar = tk.Frame(row, bg=self.theme.c["surface_high"], height=12)
        bar.pack(side="left", fill="x", expand=True, padx=(6, 6))

        fill = tk.Frame(bar, bg=self.theme.c["primary"], height=10)
        fill.place(x=0, y=0, width=max(2, score * bar.winfo_reqwidth()), height=10)

        score_lbl = tk.Label(
            row,
            text=f"{score:.2f}",
            bg=self.theme.c["surface_container"],
            fg=self.theme.c["success"] if score >= target else self.theme.c["on_surface_variant"],
            font=self.theme.font("caption"),
            width=6,
            anchor="e",
        )
        score_lbl.pack(side="right")

        self.bars.append(bar)
        self.labels.append(score_lbl)

    def reset(self) -> None:
        for widget in self.content.winfo_children():
            widget.destroy()
        self.bars.clear()
        self.labels.clear()


class ComparisonWidget(Card):
    """Side-by-side comparison of two runs."""

    def __init__(self, parent: tk.Misc, theme: Theme):
        super().__init__(parent, theme, title="Run Comparison", subtitle="Compare two benchmark runs side by side")

        self.left = tk.Frame(self.content, bg=theme.c["surface_container"])
        self.left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.right = tk.Frame(self.content, bg=theme.c["surface_container"])
        self.right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        self._setup_side(self.left, "Run A")
        self._setup_side(self.right, "Run B")

    def _setup_side(self, parent: tk.Misc, label: str) -> None:
        tk.Label(
            parent,
            text=label,
            bg=parent.cget("bg"),
            fg=self.theme.c["on_surface"],
            font=self.theme.font("title"),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        self.score_lbl = tk.Label(
            parent,
            text="—",
            bg=parent.cget("bg"),
            fg=self.theme.c["on_surface"],
            font=self.theme.font("headline"),
            anchor="w",
        )
        self.score_lbl.pack(fill="x", pady=(0, 2))

        self.detail_lbl = tk.Label(
            parent,
            text="",
            bg=parent.cget("bg"),
            fg=self.theme.c["on_surface_variant"],
            font=self.theme.font("caption"),
            anchor="w",
            justify="left",
            wraplength=200,
        )
        self.detail_lbl.pack(fill="x")

    def set_left(self, score: float, detail: str) -> None:
        for child in self.left.winfo_children():
            if isinstance(child, tk.Label) and child.cget("text") == "—":
                child.configure(text=f"{score:.2f}")
                break
        # Find the detail label (second label in left frame)
        labels = [w for w in self.left.winfo_children() if isinstance(w, tk.Label)]
        if len(labels) >= 2:
            labels[1].configure(text=detail)

    def set_right(self, score: float, detail: str) -> None:
        labels = [w for w in self.right.winfo_children() if isinstance(w, tk.Label)]
        if len(labels) >= 2:
            labels[0].configure(text=f"{score:.2f}")
            labels[1].configure(text=detail)


class ImprovementDashboard(Card):
    """Dashboard showing what to improve based on run results."""

    def __init__(self, parent: tk.Misc, theme: Theme):
        super().__init__(parent, theme, title="Improvement Tracker", subtitle="Exact component to edit based on results")
        self.text = tk.Text(
            self.content,
            wrap="word",
            bd=0,
            highlightthickness=0,
            bg=theme.c["surface_container"],
            fg=theme.c["on_surface"],
            font=theme.font("body"),
            padx=12,
            pady=10,
            state="disabled",
        )
        y = ttk.Scrollbar(self.content, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=y.set)
        y.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

    def set_recommendations(self, lines: list[str]) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert(
            "1.0",
            "Run a sweep to see improvement recommendations.",
        )
        self.text.configure(state="disabled")
