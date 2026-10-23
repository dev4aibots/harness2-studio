"""GUI smoke test: construct the real app, visit every view, switch theme.

Skipped automatically where tkinter or a display is unavailable, so CI on a
headless box stays honest instead of pretending to cover the UI.
"""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")


def _tk_display_available() -> bool:
    """Probe for a real display instead of inferring one from environment variables.

    GitHub's Windows and macOS runners ship tkinter but no usable window server, so
    ``os.name`` alone is not enough: constructing a root is the only honest test.
    """
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


if not _tk_display_available():
    pytest.skip("no display available for Tk", allow_module_level=True)


def test_app_constructs_and_every_view_renders() -> None:
    from h2studio.app import NAV, App

    app = App()
    try:
        for key, _label, _sub in NAV:
            app.show(key)
            app.update_idletasks()
        assert set(app.views) == {key for key, _label, _sub in NAV}
    finally:
        app.destroy()


def test_theme_toggle_rebuilds_without_error() -> None:
    from h2studio.app import App

    app = App()
    try:
        before = app.theme.mode
        app.toggle_theme()
        app.update_idletasks()
        assert app.theme.mode != before
        app.show("run")
        app.update_idletasks()
        assert "run" in app.views
    finally:
        app.destroy()
