"""Contract tests for every CLI connector and every harness component.

These are the "A-to-Z" checks: every action module, benchmark, subset,
substrate, mode, split rule and C1–C8 path is exercised without launching a
model. Network and process behaviour is covered separately.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from h2studio.services import envfile, h2, models, runs


def _posix_mode(path: Path) -> int | None:
    """The 0o600 assertion is a POSIX guarantee; on Windows chmod only toggles read-only."""
    return None if os.name == "nt" else path.stat().st_mode & 0o777


def test_every_cli_module_has_an_argv_builder(tmp_path: Path) -> None:
    install = h2.Install(tmp_path, Path(sys.executable))
    for action, module in h2.MODULES.items():
        opts = h2.Options()
        argv = h2.full_argv(install, action, opts)
        assert argv[:3] == [sys.executable, "-m", module], action
        if action != "bridge":  # every bridge flag has a valid default
            assert argv[3:], action


def test_every_benchmark_subset_and_substrate_is_reachable() -> None:
    for bench in h2.BENCHES:
        for substrate in h2.SUBSTRATES:
            for mode in h2.MODES:
                subset = "office" if bench == "wb" else None
                opts = h2.Options(bench=bench, substrate=substrate, modes=(mode,), subset=subset)
                argv = h2.build("run", opts)
                assert argv[argv.index("--bench") + 1] == bench
                assert argv[argv.index("--substrate") + 1] == substrate
                assert argv[argv.index("--mode") + 1] == mode
                if subset:
                    assert argv[argv.index("--subset") + 1] == subset


def test_every_workbuddy_subset() -> None:
    for subset in h2.SUBSETS:
        argv = h2.build("run", h2.Options(bench="wb", subset=subset))
        assert argv[argv.index("--subset") + 1] == subset


def test_split_and_seed_matrix() -> None:
    for split in ("all", "train"):
        argv = h2.build("run", h2.Options(split=split, seed=0))
        assert argv[argv.index("--seed") + 1] == "0"
        assert ("--split" in argv) is (split != "all")
    with pytest.raises(h2.ConfigError):
        h2.build("run", h2.Options(split="test"))


def test_every_component_maps_to_a_real_path(tmp_path: Path) -> None:
    task = tmp_path / "run" / "task-1"
    harness = task / "harnesses" / "base"
    harness.mkdir(parents=True)
    for key, _title, rel in runs.COMPONENTS:
        path = harness / rel
        if rel.endswith("/") or key in {"C5", "C6", "C7", "C8"}:
            path.mkdir(parents=True, exist_ok=True)
            (path / "README.md").write_text(f"{key}\n", encoding="utf-8")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{key} content\n", encoding="utf-8")
    assert runs.harness_tasks(tmp_path) == [task]
    versions = runs.harnesses(task)
    assert [v.label for v in versions] == ["base"]
    for key, _title, _rel in runs.COMPONENTS:
        assert key in versions[0].files, key
        text = runs.component_text(versions[0].component_path(key))
        assert text and "missing" not in text.lower()


def test_every_artifact_kind_is_recognized(tmp_path: Path) -> None:
    cases = {
        "demo.json": {"done": 2, "failed": 0},
        "judged.json": [{"graded": True, "score": 1}],
        "base_judged.json": [{"graded": True, "score": 0.5}],
        "summary.json": {"k": 2, "bench": "jb"},
    }
    for name, payload in cases.items():
        target = tmp_path / "run" / "task" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
    found = runs.scan(tmp_path)
    assert {a.kind for a in found} == {"demo", "judged", "base-judged", "summary"}
    for art in found:
        assert art.error is None
        assert runs.summarize(art)["kind"] == art.kind


def test_env_file_preserves_comments_and_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# keep this\nGOOGLE_CLOUD_PROJECT=old\nOTHER=untouched\n", encoding="utf-8"
    )
    envfile.set_values(path, {"HARNESS2_SOLVER_MODEL": "provider/model"})
    text = path.read_text()
    assert "# keep this" in text
    assert "GOOGLE_CLOUD_PROJECT=old" in text
    assert "OTHER=untouched" in text
    assert "HARNESS2_SOLVER_MODEL=provider/model" in text
    assert _posix_mode(path) in (None, 0o600)


def test_env_template_is_created_once(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    assert envfile.write_template(path) is True
    first = path.read_text()
    assert "HARNESS2_SOLVER_MODEL=" in first
    assert first.count("HARNESS2_SOLVER_MODEL") == 1
    assert _posix_mode(path) in (None, 0o600)
    path.write_text("# user edited\n")
    assert envfile.write_template(path) is False
    assert path.read_text() == "# user edited\n"


def test_env_precedence_shell_wins(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("A=file\nB=file\n", encoding="utf-8")
    install = h2.Install(tmp_path, Path(sys.executable))
    monkeypatch.setenv("A", "shell")
    env = h2.merged_env(install, {"B": "override"})
    assert env["A"] == "shell"
    assert env["B"] == "override"


def test_model_catalog_parses_opencode_rows() -> None:
    raw = "opencode/model-a\nopencode/model-b\n\n"
    parsed = models.parse(raw)
    assert [m.id for m in parsed] == ["opencode/model-a", "opencode/model-b"]
