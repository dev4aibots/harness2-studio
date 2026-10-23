#!/usr/bin/env python3
"""Opt-in network end-to-end: install upstream from scratch and run the demo.

This downloads ~850 KB from GitHub and needs Python 3.12/3.13. It is not part of
CI; run it when changing the installer or before a release.

    python3.12 tools/install_e2e.py --dest /tmp/h2-install-e2e
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h2studio.services import installer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, help="install folder (default: a temp dir)")
    parser.add_argument("--keep", action="store_true", help="keep the folder and print its path")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    temp = args.dest is None
    dest = (args.dest or Path(tempfile.mkdtemp(prefix="harness2-install-e2e-"))).expanduser()
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"destination is not empty: {dest}")
    seen: set[tuple[str, int]] = set()

    def progress(phase: str, done: int, total: int, detail: str) -> None:
        bucket = (phase, 0 if total == 0 else int(done / total * 10))
        if bucket not in seen:
            seen.add(bucket)
            print(f"[{phase}] {done}/{total} {detail[:100]}", flush=True)

    started = time.time()
    result = installer.install(
        dest, progress=progress, cancel=threading.Event(),
        python=sys.executable, workers=args.workers, make_environment=True,
    )
    elapsed = time.time() - started
    marker = installer.read_marker(dest)
    assert marker is not None and marker.commit, "missing install marker"
    assert result.installed > 100, f"unexpected file count {result.installed}"
    assert (dest / "pyproject.toml").is_file(), "missing pyproject"

    demo_out = dest / "runs" / "install-e2e"
    proc = subprocess.run(
        [str(installer.venv_python(dest)), "-m", "harness2.cli.demo",
         "--k", "1", "--mode", "both", "--output", str(demo_out)],
        cwd=dest, capture_output=True, text=True, timeout=180, check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout[-2000:], proc.stderr[-2000:], file=sys.stderr)
        raise SystemExit(f"demo failed with {proc.returncode}")
    data = json.loads((demo_out / "demo.json").read_text())
    assert data.get("failed") == 0, data
    print(f"INSTALL E2E OK: {result.installed} files · version {result.version} · "
          f"{elapsed:.1f}s · demo {data['done']} tasks / {data['failed']} failed")
    print(f"checkout: {dest}")
    if temp and not args.keep:
        shutil.rmtree(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
