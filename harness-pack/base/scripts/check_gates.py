#!/usr/bin/env python3
"""Detect a project's gates, run them, and print one table of observed results.

Never invents a gate and never hides a failure: a gate that cannot run is reported as
`skip` with the reason. Exit code is 0 only when every gate passed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

TAIL = 12


def _node_scripts(root: Path) -> dict:
    manifest = root / "package.json"
    if not manifest.is_file():
        return {}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def gates(root: Path) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    py = sys.executable

    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file() or (root / "tests").is_dir():
        if shutil.which("ruff") or (root / "pyproject.toml").is_file():
            out.append(("lint", [py, "-m", "ruff", "check", "."]))
        out.append(("test", [py, "-m", "pytest", "-q"]))

    scripts = _node_scripts(root)
    if scripts:
        if "lint" in scripts:
            out.append(("lint", ["npm", "run", "lint", "--silent"]))
        if "typecheck" in scripts:
            out.append(("types", ["npm", "run", "typecheck", "--silent"]))
        if "test" in scripts:
            out.append(("test", ["npm", "test", "--silent"]))

    if (root / "go.mod").is_file() and shutil.which("go"):
        out.append(("lint", ["go", "vet", "./..."]))
        out.append(("test", ["go", "test", "./..."]))

    if (root / "Cargo.toml").is_file() and shutil.which("cargo"):
        out.append(("lint", ["cargo", "clippy", "--quiet"]))
        out.append(("test", ["cargo", "test", "--quiet"]))

    return out


def run(name: str, argv: list[str], root: Path, timeout: int) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            argv, cwd=root, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return "skip", f"{argv[0]} not installed"
    except subprocess.TimeoutExpired:
        return "fail", f"timed out after {timeout}s"
    output = (proc.stdout + proc.stderr).strip().splitlines()
    tail = " | ".join(line.strip() for line in output[-TAIL:] if line.strip())
    return ("pass" if proc.returncode == 0 else "fail"), tail or f"exit {proc.returncode}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the project's gates and print the result.")
    parser.add_argument("root", nargs="?", default=".", help="project root")
    parser.add_argument("--timeout", type=int, default=900, help="per-gate timeout in seconds")
    parser.add_argument("--list", action="store_true", help="print gates without running them")
    parser.add_argument("--only", default="", help="run gates whose name contains this")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    selected = [g for g in gates(root) if args.only in g[0]]
    if not selected:
        print(f"check_gates: no gates detected under {root}")
        return 2

    if args.list:
        for name, argv in selected:
            print(f"{name}: {' '.join(argv)}")
        return 0

    print(f"{'gate':<6} {'result':<5} evidence")
    failures = 0
    for name, argv in selected:
        result, evidence = run(name, argv, root, args.timeout)
        failures += result == "fail"
        print(f"{name:<6} {result:<5} {evidence[:160]}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
