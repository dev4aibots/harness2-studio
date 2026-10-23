"""Model discovery for the model pickers.

The list comes from the user's own `opencode models`, so any provider they have
authenticated shows up. No hardcoded catalogue, no invented model IDs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from .h2 import find_opencode, sandbox_env

FALLBACK = ("opencode/",)

_CACHE: list[Model] | None = None


@dataclass(frozen=True)
class Model:
    id: str
    provider: str
    name: str

    @property
    def free(self) -> bool:
        return "free" in self.id


def parse(text: str) -> list[Model]:
    out: list[Model] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "/" not in line or line.startswith("#"):
            continue
        provider, _, name = line.partition("/")
        if not provider or not name or line in seen:
            continue
        seen.add(line)
        out.append(Model(id=line, provider=provider, name=name))
    return out


def list_models(refresh: bool = False) -> list[Model]:
    """Ask the local opencode CLI; degrade to an empty list, never raise."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    exe = find_opencode()
    if not exe:
        _CACHE = []
        return _CACHE
    try:
        proc = subprocess.run(
            [exe, "models"],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
            env=sandbox_env(dict(os.environ)),
        )
        _CACHE = parse(proc.stdout)
    except (OSError, subprocess.SubprocessError):
        _CACHE = []
    return _CACHE


def by_provider(models: list[Model]) -> dict[str, list[Model]]:
    groups: dict[str, list[Model]] = {}
    for m in models:
        groups.setdefault(m.provider, []).append(m)
    return dict(sorted(groups.items()))
