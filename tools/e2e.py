#!/usr/bin/env python3
"""End-to-end: drive the real harness2-demo from the GUI and verify artifacts."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h2studio.app import App

OUT = "runs/ui-e2e"


def pump(app: App, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def main() -> int:
    app = App()
    try:
        app.show("run")
        view = app.views["run"]
        view.demo_out.set(OUT)
        view.demo_k.set("1")
        view._demo()
        deadline = time.time() + 180
        while time.time() < deadline:
            app.update()
            if app.stream is not None and not app.stream.running:
                break
            time.sleep(0.05)
        pump(app, 1.5)

        text = "\n".join(line for line, _tag in app.log.buffer)
        assert "[exit 0]" in text, "demo did not exit cleanly:\n" + text[-2000:]
        artifact = app.install.repo / OUT / "demo.json"
        assert artifact.is_file(), f"missing artifact {artifact}"
        data = json.loads(artifact.read_text())
        assert data.get("failed") == 0, data
        print(f"E2E OK: demo via GUI -> {artifact} ({data['done']} tasks, {data['failed']} failed)")
        return 0
    finally:
        app.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
