"""Material 3 tokens for Tk, seeded on Google Blue.

Tk cannot blur, cast real shadows, or antialias arbitrary shapes. Rather than
fake elevation badly, the app uses M3 "outlined" surfaces: a 1px outline-variant
border on a surface-container fill. Everything else (state layers, pill buttons,
type scale) is reproduced faithfully.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

LIGHT = {
    "primary": "#0B57D0",
    "on_primary": "#FFFFFF",
    "primary_container": "#D3E3FD",
    "on_primary_container": "#041E49",
    "secondary_container": "#C2E7FF",
    "on_secondary_container": "#001D35",
    "surface": "#F9F9FF",
    "surface_low": "#F3F3FA",
    "surface_container": "#EDEDF4",
    "surface_high": "#E8E7EE",
    "surface_highest": "#E2E2E9",
    "on_surface": "#1A1B20",
    "on_surface_variant": "#3F424A",
    "outline": "#74777F",
    "outline_variant": "#B8BBC7",
    "error": "#BA1A1A",
    "error_container": "#FFDAD6",
    "on_error_container": "#410002",
    "success": "#146C2E",
    "success_container": "#C4EED0",
    "warning": "#8F4C00",
    "scrim": "#000000",
}

DARK = {
    "primary": "#ADC7FF",
    "on_primary": "#002E68",
    "primary_container": "#004493",
    "on_primary_container": "#D8E2FF",
    "secondary_container": "#004A77",
    "on_secondary_container": "#C2E7FF",
    "surface": "#111318",
    "surface_low": "#1A1B20",
    "surface_container": "#1E1F25",
    "surface_high": "#282A2F",
    "surface_highest": "#33353A",
    "on_surface": "#E2E2E9",
    "on_surface_variant": "#CDD0DB",
    "outline": "#8E9099",
    "outline_variant": "#4B4E59",
    "error": "#FFB4AB",
    "error_container": "#93000A",
    "on_error_container": "#FFDAD6",
    "success": "#6DD58C",
    "success_container": "#0F5223",
    "warning": "#FFB95C",
    "scrim": "#000000",
}

# M3 type scale in px; negative Tk sizes mean pixels, not points.
# HD pass (ui-ux-pro-max: "base 16px, clear hierarchy, no body text under 12px"):
# every body size is >= 13px, the body base is 16px, and the ramp steps 1.20-1.25x.
SCALE = {
    "display": (-40, "normal"),
    "headline": (-28, "bold"),
    "title_lg": (-24, "normal"),
    "title": (-18, "bold"),
    "body_lg": (-17, "normal"),
    "body": (-16, "normal"),
    "label_lg": (-15, "bold"),
    "label": (-14, "bold"),
    "caption": (-13, "normal"),
}

SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
RADIUS = {"chip": 8, "card": 12, "dialog": 24, "field": 8}

UI_FAMILIES = ("Google Sans", "Product Sans", "Roboto", "Noto Sans", "Cantarell",
               "DejaVu Sans", "Liberation Sans", "Arial", "Helvetica")
MONO_FAMILIES = ("Google Sans Mono", "JetBrains Mono", "Roboto Mono", "DejaVu Sans Mono",
                 "Liberation Mono", "Courier New")


def _font_resolves(root: tk.Misc, family: str, size: int = -14) -> bool:
    """Return True if Tk can actually render *family* (not the 10px fixed fallback).

    Tk's :meth:`font.families` only reports core X11 fonts, but Xft/fontconfig can
    resolve many more (Roboto, JetBrains Mono, …). We test by creating a real Font
    and checking that it did not fall back to ``fixed`` at 10 px.
    """
    try:
        f = tkfont.Font(root=root, family=family, size=size)
        actual = (f.actual("family"), f.actual("size"))
        return actual != ("fixed", 10)
    except tk.TclError:
        return False


def pick_family(root: tk.Misc, candidates: tuple[str, ...], mono: bool = False) -> str:
    """Resolve a real font family, never a named-font alias.

    Tk's :meth:`font.families` only reports core X11 fonts, but Xft/fontconfig can
    resolve many more (Roboto, JetBrains Mono, …). We test each candidate by
    actually creating it, then fall back by shape before the Tk default.
    """
    for name in candidates:
        if _font_resolves(root, name):
            return name
    probe = ("liberation mono", "dejavu sans mono", "courier new") if mono else (
        "liberation sans", "dejavu sans", "arial", "helvetica")
    for name in probe:
        if _font_resolves(root, name):
            return name
    try:
        return tkfont.nametofont("TkFixedFont" if mono else "TkDefaultFont").actual("family")
    except tk.TclError:
        return "fixed"


class Theme:
    """Holds the active palette and the named fonts; rebuild on mode switch."""

    def __init__(self, root: tk.Misc, mode: str = "dark", scale: float = 1.0) -> None:
        self.root = root
        self.mode = mode if mode in ("light", "dark") else "dark"
        self.scale = max(0.8, min(2.0, float(scale or 1.0)))
        self.c = dict(DARK if self.mode == "dark" else LIGHT)
        self.ui = pick_family(root, UI_FAMILIES, mono=False)
        self.mono = pick_family(root, MONO_FAMILIES, mono=True)
        self.fonts: dict[str, tkfont.Font] = {}
        for key, (size, weight) in SCALE.items():
            self.fonts[key] = tkfont.Font(root=root, family=self.ui, size=round(size * self.scale), weight=weight)
        self.fonts["mono"] = tkfont.Font(root=root, family=self.mono, size=round(-14 * self.scale))
        self.fonts["mono_sm"] = tkfont.Font(root=root, family=self.mono, size=round(-13 * self.scale))

    def toggle(self) -> None:
        self.mode = "light" if self.mode == "dark" else "dark"
        self.c = dict(DARK if self.mode == "dark" else LIGHT)

    def font(self, key: str) -> tkfont.Font:
        return self.fonts[key]

    def apply(self) -> None:
        c = self.c
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=c["surface"], foreground=c["on_surface"], font=self.fonts["body"])
        style.configure("TFrame", background=c["surface"])
        style.configure("Surface.TFrame", background=c["surface_container"])
        style.configure("Low.TFrame", background=c["surface_low"])

        style.configure("TLabel", background=c["surface"], foreground=c["on_surface"], font=self.fonts["body"])
        style.configure("Muted.TLabel", foreground=c["on_surface_variant"])
        style.configure("Title.TLabel", font=self.fonts["title_lg"], background=c["surface"])
        style.configure("Headline.TLabel", font=self.fonts["headline"], background=c["surface"])
        style.configure("Caption.TLabel", font=self.fonts["caption"], foreground=c["on_surface_variant"])

        style.configure(
            "TEntry",
            fieldbackground=c["surface_low"],
            foreground=c["on_surface"],
            insertcolor=c["on_surface"],
            bordercolor=c["outline"],
            lightcolor=c["outline"],
            darkcolor=c["outline"],
            padding=8,
            relief="flat",
        )
        style.map("TEntry", bordercolor=[("focus", c["primary"])], lightcolor=[("focus", c["primary"])])

        style.configure(
            "TCombobox",
            fieldbackground=c["surface_low"],
            background=c["surface_low"],
            foreground=c["on_surface"],
            arrowcolor=c["on_surface_variant"],
            arrowsize=14,
            bordercolor=c["outline"],
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", c["surface_low"])],
            foreground=[("readonly", c["on_surface"])],
            bordercolor=[("focus", c["primary"])],
        )
        self.root.option_add("*TCombobox*Listbox.background", c["surface_high"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["on_surface"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["primary_container"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", c["on_primary_container"])

        style.configure(
            "Treeview",
            background=c["surface"],
            fieldbackground=c["surface"],
            foreground=c["on_surface"],
            rowheight=round(34 * self.scale),
            borderwidth=0,
            font=self.fonts["body"],
        )
        style.configure(
            "Treeview.Heading",
            background=c["surface_container"],
            foreground=c["on_surface_variant"],
            font=self.fonts["label"],
            relief="flat",
            padding=(8, 8),
        )
        style.map("Treeview.Heading", background=[("active", c["surface_high"])])
        style.map("Treeview", background=[("selected", c["primary_container"])], foreground=[("selected", c["on_primary_container"])])

        style.configure("TCheckbutton", background=c["surface"], foreground=c["on_surface"], font=self.fonts["body"])
        style.map("TCheckbutton", background=[("active", c["surface"])])
        style.configure("TRadiobutton", background=c["surface"], foreground=c["on_surface"])

        style.configure(
            "TScrollbar",
            background=c["outline"],
            troughcolor=c["surface"],
            bordercolor=c["surface"],
            arrowcolor=c["on_surface_variant"],
            arrowsize=10,
            width=14,
            relief="flat",
        )
        style.map("TScrollbar", background=[("active", c["outline"])])

        style.configure("TSeparator", background=c["outline_variant"])
        style.configure("TPanedwindow", background=c["surface"])
        style.configure("Sash", background=c["outline_variant"], sashthickness=6)

        # Arrowless scrollbars: M3 thumbs, no 1990s arrow buttons.
        style.layout("Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.layout("Horizontal.TScrollbar", [
            ("Horizontal.Scrollbar.trough", {"sticky": "ew", "children": [
                ("Horizontal.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])

        style.configure("TNotebook", background=c["surface"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure(
            "TNotebook.Tab",
            background=c["surface"],
            foreground=c["on_surface_variant"],
            padding=(14, 8),
            font=self.fonts["label"],
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", c["surface_high"])],
            foreground=[("selected", c["primary"])],
            expand=[("selected", (0, 0, 0, 0))],
        )
