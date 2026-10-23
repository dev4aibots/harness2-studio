#!/usr/bin/env python3
"""Dev tool: render every view and capture the real window in both themes."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h2studio.app import NAV, App

OUT = Path("/tmp/opencode/shots")
OUT.mkdir(parents=True, exist_ok=True)


def shot(app: App, wid: str, name: str, settle: float = 0.6) -> None:
    app.update()
    time.sleep(settle)
    target = OUT / f"{name}.png"
    proc = subprocess.run(["import", "-window", wid, str(target)], capture_output=True, check=False)
    if proc.returncode != 0:
        print("capture failed", name, proc.stderr.decode()[:200])
    else:
        print("captured", target, target.stat().st_size)


def main() -> int:
    app = App()
    if app.theme.mode != "dark":
        app.toggle_theme()
    app.geometry("1440x900+30+30")
    app.update()
    time.sleep(0.8)
    wid = hex(app.winfo_id())

    for key, _label, _sub in NAV:
        app.show(key)
        shot(app, wid, key, 1.2 if key in ("harness", "runs", "models") else 0.5)

    app.show("run")
    app.views["run"].bench.select("wb")
    shot(app, wid, "run-wb")

    app.open_palette()
    time.sleep(0.6)
    shot(app, wid, "palette", settle=0.2)
    if app._palette is not None:
        app._palette.close()
    app.update()

    app.toggle_theme()
    app.update()
    time.sleep(0.5)
    app.show("home")
    shot(app, wid, "home-light")
    app.show("run")
    app.views["run"].bench.select("wb")
    shot(app, wid, "run-light")
    app.show("harness")
    shot(app, wid, "harness-light")

    if app.theme.mode != "dark":
        app.toggle_theme()
    app.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
