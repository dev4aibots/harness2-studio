"""Comment-preserving .env editing.

Harness² ships no .env.example, so the UI owns creating one. Rewrites must keep
user comments and ordering intact: this is a file people hand-edit too.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

HEADER = (
    "# Harness2 environment - written by Harness2 Studio.\n"
    "# Shell variables still win; this file only fills gaps (config.load_dotenv).\n"
)

TEMPLATE = HEADER + """\
# Executor: provider/model syntax for your coding agent.
HARNESS2_SOLVER_MODEL=

# Improver: defaults to the executor when blank.
HARNESS2_IMPROVER_MODEL=

# Judge: a separate model scores finished artifacts.
HARNESS2_JUDGE_MODEL=
# JobBench can judge through any OpenAI-compatible endpoint:
# HARNESS2_JUDGE_BASE_URL=http://127.0.0.1:7585/v1
# HARNESS2_JUDGE_API_KEY=

# Where runs are written (default: <repo>/runs).
# HARNESS2_RUNS_DIR=runs

# Vertex AI, needed for LAB/WorkBuddy judging and the Codex bridge.
# GOOGLE_CLOUD_PROJECT=
# GOOGLE_CLOUD_LOCATION=global
"""


def write_template(path: Path) -> bool:
    """Create a commented starter .env once; never overwrite an existing file."""
    path = Path(path)
    if path.exists():
        return False
    _atomic_write(path, TEMPLATE)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return True


def parse(path: Path) -> dict[str, str]:
    from .h2 import read_env

    return read_env(path)


def set_values(path: Path, values: dict[str, str]) -> None:
    """Replace keys in place, append new ones, never duplicate a key."""
    path = Path(path)
    existing: list[str] = []
    try:
        existing = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        existing = []

    pending = {k: v for k, v in values.items() if v is not None}
    out: list[str] = []
    seen: set[str] = set()

    if not existing:
        out.extend(HEADER.splitlines())

    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        body = stripped.removeprefix("export ")
        key = body.partition("=")[0].strip()
        if key in pending:
            out.append(f"{key}={pending[key]}")
            seen.add(key)
        else:
            out.append(line)

    missing = [k for k in pending if k not in seen]
    if missing and out and out[-1].strip():
        out.append("")
    for key in missing:
        out.append(f"{key}={pending[key]}")

    _atomic_write(path, "\n".join(out) + "\n")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".env.", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
