"""Small, atomic app state: repo path, theme, geometry, last-used form values."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "harness2-studio"
STATE_PATH = CONFIG_DIR / "state.json"


@dataclass
class State:
    repo: str = str(Path.home() / "harness2")
    python: str = ""
    theme: str = "dark"
    geometry: str = "1360x880"
    last_bench: str = "jb"
    last_substrate: str = "oc"
    last_form: dict = field(default_factory=dict)
    models_draft: dict = field(default_factory=dict)
    bridge_draft: dict = field(default_factory=dict)
    upstream: dict = field(default_factory=dict)
    install_dest: str = ""
    ui_scale: float = 0.0  # 0 = auto from display DPI; 0.85-2.0 = user choice
    recent: list[str] = field(default_factory=list)

    def load(self) -> State:
        try:
            raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self
        for key in asdict(self):
            if key in raw and raw[key] is not None:
                setattr(self, key, raw[key])
        return self

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(CONFIG_DIR), prefix=".state.", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2)
            os.replace(tmp, STATE_PATH)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


def remember_command(text: str, limit: int = 12) -> None:
    state = State().load()
    state.recent = [text, *[r for r in state.recent if r != text]][:limit]
    state.save()
