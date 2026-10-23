#!/usr/bin/env python3
"""Behavioural self-test for the fixes the reviewers demanded.

Every assertion drives a real widget; nothing is mocked.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="h2studio-selftest-")

from h2studio.app import App
from h2studio.services import h2


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok  " if condition else "FAIL"
    print(f"[{status}] {name}{(' — ' + detail) if detail else ''}")
    if not condition:
        raise SystemExit(1)


def main() -> int:
    app = App()
    try:
        # 1. Invalid numeric input is surfaced, not raised.
        app.show("run")
        run = app.views["run"]
        run.vars["k"].set("abc")
        run._changed()
        check("non-numeric k stays in the error channel", run.preview.cget("text").startswith("invalid"))
        run.vars["k"].set("1")
        run._changed()

        # 2. Missing checkout blocks cleanly.
        good_install = app.install
        app.install = h2.discover("/tmp/definitely-not-harness2")
        ok = app.run_action("demo", h2.Options())
        check("missing checkout refuses to launch", ok is False)
        check("missing checkout explains itself", "FAIL" in app.log.buffer[-1][0])
        app.install = good_install

        # 3. Harness saving is impossible until editing is unlocked.
        app.show("harness")
        hv = app.views["harness"]
        check("read-only harness keeps Save disabled", hv.save_btn._enabled is False)

        # 4. Harness editor refuses to persist a rendered diff.
        app.show("harness")
        hv = app.views["harness"]
        if hv.current is not None and "C1" in hv.current.files:
            target = hv.current.files["C1"]
            original = target.read_text()
            hv.editing = True
            hv.diff._toggle()  # on
            check("diff mode marks component read-only", hv.editable.get("C1") is False)
            hv._save()
            check("diff view never overwrites the file", target.read_text() == original)
            hv.diff._toggle()  # off

        # 5. Console replays history and shows a placeholder when empty.
        app.log.emit("selftest-line", "out")
        app.show("console")
        check("console replays the log buffer", "selftest-line" in app.views["console"].console.dump())

        # 6. Palette exposes its full row set.
        app.open_palette()
        check("palette renders eight rows", sum(1 for r in app._palette.row_widgets if r[0].winfo_manager()) == 8)
        app._palette.close()

        # 7. Zoom regenerates fonts.
        base_size = abs(app.theme.font("body").cget("size"))
        app.zoom(0.1)
        check("zoom grows the type scale", abs(app.theme.font("body").cget("size")) > base_size)

        # 8. Models draft survives a rebuild instead of being silently reloaded.
        app.show("models")
        mv = app.views["models"]
        mv.vars["HARNESS2_SOLVER_MODEL"].set("opencode/draft-test")
        app.toggle_theme()
        app.show("models")
        check("unsaved model draft survives theme rebuild",
              app.views["models"].vars["HARNESS2_SOLVER_MODEL"].get() == "opencode/draft-test")

        # 9. Palette runs the selected action with Enter.
        app.show("home")
        app.open_palette()
        pal = app._palette
        pal.var.set("toggle theme")
        pal._filter(pal.var.get())
        check("palette filters actions", len(pal.results) >= 1)
        mode_before = app.theme.mode
        pal._run()
        for _ in range(20):
            app.update()
            time.sleep(0.01)
        check("palette executes the action", app.theme.mode != mode_before)

        # 10. Async model discovery never blocks and eventually reports.
        app.show("models")
        for _ in range(200):
            app.update()
            if "…" not in app.views["models"].count_chip.cget("text"):
                break
            time.sleep(0.02)
        check("model discovery completes off-thread",
              "…" not in app.views["models"].count_chip.cget("text"),
              app.views["models"].count_chip.cget("text"))

        print("\nSELFTEST PASS")
        return 0
    finally:
        app.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
