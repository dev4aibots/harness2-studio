#!/usr/bin/env python3
"""Launch Harness2 Studio.

    python3 run.py            # normal launch
    python3 run.py --check    # import + construct + destroy, no window shown
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        from h2studio.app import App
    except ModuleNotFoundError as exc:
        if exc.name == "tkinter":
            raise SystemExit(
                f"{sys.executable} has no tkinter.\n"
                "Use a Python build with Tk (python.org, or install python3-tk), e.g.:\n"
                "  python3.12 run.py"
            ) from None
        raise

    app = App()
    if "--check" in argv:
        app.update_idletasks()
        app.destroy()
        print("GUI constructed and destroyed cleanly")
        return 0
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

