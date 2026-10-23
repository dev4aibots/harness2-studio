"""Live prerequisite checks. Pure functions, so the UI cannot lie about them."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .h2 import Install


@dataclass(frozen=True)
class Requirement:
    label: str
    ok: bool
    detail: str
    blocking: bool = True


def _which(name: str) -> Requirement:
    path = shutil.which(name)
    return Requirement(name, bool(path), path or "not on PATH")


def _dir(path: Path, label: str) -> Requirement:
    return Requirement(label, path.exists(), str(path), blocking=False)


def _docker() -> Requirement:
    if not shutil.which("docker"):
        return Requirement("docker", False, "not on PATH")
    try:
        ok = subprocess.run(["docker", "info"], capture_output=True, timeout=3, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    return Requirement("docker daemon", ok, "running" if ok else "installed but not running")


def check(install: Install, bench: str) -> list[Requirement]:
    deps = install.repo / "dependencies"
    items: list[Requirement] = [
        Requirement("python 3.12+", install.python.is_file(),
                    str(install.python) if install.python.is_file() else "missing venv interpreter"),
        _which("git"),
        _which("uv"),
        _which("node"),
        _dir(deps / "opencode" / "packages" / "opencode" / "src" / "index.ts", "OpenCode 1.14.18 checkout"),
        _dir(deps / "tools" / "node_modules" / ".bin" / "bun", "bun (benchmark runtime)"),
    ]
    if bench == "jb":
        items += [
            _dir(deps / "job-bench-eval", "job-bench-eval checkout"),
            _dir(deps / "job-bench-eval" / "dataset" / "main", "JobBench dataset"),
        ]
    elif bench == "lab":
        items += [
            _dir(deps / "harvey-labs", "harvey-labs checkout"),
            _which("pandoc"),
            _which("pdftoppm"),
        ]
    elif bench == "wb":
        items += [_dir(deps / "workbuddy-bench", "workbuddy-bench checkout"), _docker()]
    return items


def summary(items: list[Requirement]) -> tuple[int, int]:
    ok = sum(1 for i in items if i.ok)
    return ok, len(items)
