"""Build and grade benchmark tasks from a real repository with a real test suite.

Each task is a pristine copy of the package with one semantic mutation applied, plus the
failing tests it produces. Grading restores the test files from a pristine snapshot before
running them, so editing the tests cannot turn a failure into a pass.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ("tests/test_services.py", "tests/test_installer.py", "tests/test_workflows.py")
TASK_SUFFIXES = ("*.py", "*.toml", "*.md")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"}


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SKIP_DIRS or n.endswith(".egg-info")}


def snapshot(dest: Path) -> Path:
    """Copy only what the tests need: the package, the tests, the manifest."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copytree(ROOT / "h2studio", dest / "h2studio", ignore=_ignore)
    shutil.copytree(ROOT / "tests", dest / "tests", ignore=_ignore)
    for name in ("pyproject.toml", "README.md"):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, dest / name)
    return dest


def pytest_run(workspace: Path, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUSERBASE"] = env.get("PYTHONUSERBASE", str(Path.home() / ".local"))
    env["LANG"] = "C.UTF-8"
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *extra]
    return subprocess.run(
        args, cwd=workspace, capture_output=True, text=True, timeout=300, env=env, check=False
    )


MUTATIONS: list[dict] = [
    {
        "id": "blob-sha-length",
        "path": "h2studio/services/installer.py",
        "old": 'return hashlib.sha1(b"blob %d\\0" % len(data) + data).hexdigest()',
        "new": 'return hashlib.sha1(b"blob %d\\0" % (len(data) + 1) + data).hexdigest()',
        "issue": "Checksum verification rejects every download: the computed git blob hash does not match the hash reported by the tree API for any file.",
    },
    {
        "id": "unsafe-path-skip",
        "path": "h2studio/services/installer.py",
        "old": """        if not _safe_path(path):
            raise InstallError(
                f"Upstream tree contains an unsafe path: {path!r}. Refusing to install."
            )""",
        "new": """        if not _safe_path(path):
            continue""",
        "issue": "An upstream tree containing a path traversal entry is silently skipped instead of refused. Unsafe trees must fail loudly, not install partially.",
    },
    {
        "id": "include-everything",
        "path": "h2studio/services/installer.py",
        "old": """        if path not in INCLUDE_FILES and not path.startswith(INCLUDE_PREFIXES):
            continue""",
        "new": """        if path not in INCLUDE_FILES:
            continue""",
        "issue": "The installer now drops every file under a prefix directory, so the package itself is never installed.",
    },
    {
        "id": "commit-sha-truncated",
        "path": "h2studio/services/installer.py",
        "old": '        sha = str(data["sha"])',
        "new": '        sha = str(data["sha"])[:7]',
        "issue": "The recorded commit is shortened to seven characters, so the installer cannot fetch a tree for it.",
    },
    {
        "id": "models-dedupe-lost",
        "path": "h2studio/services/models.py",
        "old": "        if not provider or not name or line in seen:",
        "new": "        if not provider or not name:",
        "issue": "Duplicate model rows now appear twice in the model picker, once per provider alias.",
    },
    {
        "id": "env-template-overwrite",
        "path": "h2studio/services/envfile.py",
        "old": "    if path.exists():\n        return False",
        "new": "    if path.exists() and False:\n        return False",
        "issue": "Writing the environment template overwrites an existing .env, destroying credentials the user already configured.",
    },
    {
        "id": "run-argv-drops-k",
        "path": "h2studio/services/h2.py",
        "old": '        _add(argv, "--k", opts.k)',
        "new": '        _add(argv, "--k", None)',
        "issue": "The sweep command no longer forwards the sample budget, so every run silently uses the default k instead of the requested one.",
    },
    {
        "id": "summary-status-filter",
        "path": "h2studio/services/runs.py",
        "old": '            ok = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") in ("ok", "done", "complete"))',
        "new": '            ok = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "done")',
        "issue": "Completed task counts always read zero: only the rarely used status is counted as success.",
    },
    {
        "id": "windows-drive-accepted",
        "path": "h2studio/services/installer.py",
        "old": '    if ":" in path:  # Windows drive/ADS/stream syntax',
        "new": '    if "::" in path:  # Windows drive/ADS/stream syntax',
        "issue": "An upstream path containing a Windows drive letter or alternate data stream is now treated as safe and installed.",
    },
    {
        "id": "model-line-without-slash",
        "path": "h2studio/services/models.py",
        "old": '        if not line or "/" not in line or line.startswith("#"):',
        "new": '        if not line or line.startswith("#"):',
        "issue": "Rows without a provider prefix are parsed as models, producing entries with an empty provider and a broken picker.",
    },
]


def build(tasks_dir: Path, keep_only: int = 8) -> list[dict]:
    pristine = snapshot(tasks_dir / "_pristine")
    baseline = pytest_run(pristine)
    if baseline.returncode != 0:
        raise SystemExit(f"pristine suite is not green:\n{baseline.stdout[-2000:]}")

    tasks: list[dict] = []
    for spec in MUTATIONS:
        if len(tasks) >= keep_only:
            break
        work = tasks_dir / spec["id"]
        snapshot(work)
        target = work / spec["path"]
        source = target.read_text(encoding="utf-8")
        if spec["old"] not in source:
            print(f"[skip] {spec['id']}: anchor not found in {spec['path']}")
            shutil.rmtree(work, ignore_errors=True)
            continue
        target.write_text(source.replace(spec["old"], spec["new"], 1), encoding="utf-8")
        result = pytest_run(work)
        failed = [
            line.split(" - ")[0].strip()
            for line in result.stdout.splitlines()
            if line.startswith("FAILED ")
        ]
        if result.returncode == 0 or not failed:
            print(f"[skip] {spec['id']}: mutation did not fail the suite")
            shutil.rmtree(work, ignore_errors=True)
            continue
        manifest = {
            "id": spec["id"],
            "issue": spec["issue"],
            "failed_tests": failed,
            "mutated_file": spec["path"],
        }
        (work / "TASK.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        tasks.append(manifest)
        print(f"[task] {spec['id']}: {len(failed)} failing test(s)")
    return tasks


def grade(workspace: Path, pristine: Path) -> tuple[bool, str]:
    """Restore the tests, then run them against whatever the agent changed."""
    shutil.rmtree(workspace / "tests", ignore_errors=True)
    shutil.copytree(pristine / "tests", workspace / "tests", ignore=_ignore)
    result = pytest_run(workspace, extra=("-q",))
    tail = (result.stdout or result.stderr).strip().splitlines()[-6:]
    return result.returncode == 0, "\n".join(tail)


if __name__ == "__main__":
    made = build(ROOT / "bench" / "tasks")
    print(json.dumps(made, indent=2))
