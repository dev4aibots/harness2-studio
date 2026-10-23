#!/usr/bin/env python3
"""Dependency-free GUI smoke run for the GUI interpreter (no pytest needed)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h2studio.app import NAV, App


def main() -> int:
    app = App()
    app.geometry("1360x860+40+40")
    try:
        for key, _label, _sub in NAV:
            app.show(key)
            app.update_idletasks()
        assert set(app.views) == {k for k, _l, _s in NAV}, app.views.keys()
        before = app.theme.mode
        app.toggle_theme()
        app.update_idletasks()
        assert app.theme.mode != before
        app.show("run")
        app.update_idletasks()
        assert "run" in app.views
        app.toggle_theme()
        app.update_idletasks()
        print(f"SMOKE OK: {len(NAV)} views, theme toggle x2")
        return 0
    finally:
        app.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
