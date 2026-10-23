"""Read-only indexing of a Harness² runs tree.

Nothing here invents a schema: artifacts are recognised by filename, and only
documented keys are surfaced. Unknown JSON is still shown, raw, in the UI.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ARTIFACTS = {
    "demo.json": "demo",
    "judged.json": "judged",
    "base_judged.json": "base-judged",
    "summary.json": "summary",
}

# C1..C8 as the paper names them, mapped to the files Harness² actually writes.
COMPONENTS = (
    ("C1", "System prompt", "systemprompt.md"),
    ("C2", "Guardrails", "guardrails.md"),
    ("C3", "Memory", "LongTermMEMORY.md"),
    ("C4", "Tool guidance", "tool_descriptions/tool_guidance.md"),
    ("C5", "Subagents", "sub_agents"),
    ("C6", "Skills", "skills"),
    ("C7", "Scripts", "scripts"),
    ("C8", "Plugins", "plugin"),
)


@dataclass
class Artifact:
    path: Path
    kind: str
    mtime: float
    data: Any = None
    error: str | None = None

    @property
    def label(self) -> str:
        return f"{self.kind} · {self.path.parent.name or self.path.name}"

    @property
    def run_dir(self) -> Path:
        return self.path.parent


@dataclass
class Harness:
    label: str
    path: Path
    files: dict[str, Path] = field(default_factory=dict)

    def component_path(self, key: str) -> Path | None:
        return self.files.get(key)


def scan(root: Path, limit: int = 3000) -> list[Artifact]:
    """Find known artifacts under `root`, newest first. Bounded, never recursive-huge."""
    root = Path(root)
    if not root.is_dir():
        return []
    found: list[Artifact] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if len(found) >= limit:
            break
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", ".venv", "__pycache__"}]
        for name in filenames:
            kind = ARTIFACTS.get(name)
            if not kind:
                continue
            path = Path(dirpath) / name
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            art = Artifact(path=path, kind=kind, mtime=mtime)
            try:
                art.data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                art.error = f"{type(exc).__name__}: {exc}"
            found.append(art)
    found.sort(key=lambda a: a.mtime, reverse=True)
    return found


def harness_tasks(root: Path, limit: int = 400) -> list[Path]:
    """Task directories that own a real harness set (a `base` version).

    The improver also writes `context/`, `selection/`, and library copies that
    contain harness-shaped folders; those are scratch, not tasks, and listing
    them would bury the actual run.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    skip = {"context", "selection", "reflection", "library", "sources", "base"}
    out: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(root):
        if len(out) >= limit:
            break
        dirnames[:] = [
            d for d in dirnames
            if d not in {".git", "node_modules", ".venv", "__pycache__", "harnesses"} and d not in skip
        ]
        h = Path(dirpath) / "harnesses"
        if h.is_dir() and (h / "base").is_dir():
            out.append(Path(dirpath))
    return sorted(out)


def harnesses(task_dir: Path) -> list[Harness]:
    """Every harness version under `<task>/harnesses/<label>`."""
    base = Path(task_dir) / "harnesses"
    if not base.is_dir():
        return []
    out: list[Harness] = []
    for child in sorted(base.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        h = Harness(label=child.name, path=child)
        for key, _title, rel in COMPONENTS:
            candidate = child / rel
            if candidate.exists():
                h.files[key] = candidate
        out.append(h)
    return out


def component_text(path: Path | None, cap: int = 200_000) -> str:
    """Read a component for display; directories render as a file listing."""
    if path is None:
        return "(this harness version does not ship this component)"
    try:
        if path.is_dir():
            entries = sorted(p.name for p in path.iterdir())
            return "\n".join(entries) if entries else "(empty directory)"
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(unreadable: {exc})"
    return text[:cap] + ("\n… (truncated)" if len(text) > cap else "")


def summarize(art: Artifact) -> dict[str, Any]:
    """A few documented keys, defensively, for list rows."""
    data = art.data
    out: dict[str, Any] = {"kind": art.kind, "dir": art.path.parent.name}
    if isinstance(data, dict):
        for key in ("task", "task_id", "domain", "status", "bench", "benchmark", "k", "mode", "modes", "seed"):
            if key in data and not isinstance(data[key], (dict, list)):
                out[key] = data[key]
        tasks = data.get("tasks")
        if isinstance(tasks, list):
            ok = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") in ("ok", "done", "complete"))
            out["tasks"] = f"{ok}/{len(tasks)} ok"
        for key in ("done", "failed"):
            if key in data:
                out[key] = data[key]
    elif isinstance(data, list):
        out["rows"] = len(data)
        graded = 0
        for row in data:
            if isinstance(row, dict) and row.get("graded"):
                graded += 1
        out["graded"] = f"{graded}/{len(data)}"
    return out


def unified_diff(old: str, new: str, old_name: str = "base", new_name: str = "candidate") -> str:
    import difflib

    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=old_name,
            tofile=new_name,
        )
    )
