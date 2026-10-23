from __future__ import annotations

from pathlib import Path

from h2studio.services import envfile, h2, models, runs


def test_build_run_argv_maps_every_flag(tmp_path: Path) -> None:
    opts = h2.Options(
        bench="wb",
        subset="code",
        substrate="cx",
        k=3,
        seed=7,
        modes=("parallel", "sequential"),
        split="test",
        split_file=str(tmp_path / "split.json"),
        workers=4,
        only_domains="a,b",
        max_tasks=2,
        dry_run=True,
    )
    argv = h2.build("run", opts)
    assert argv[:4] == ["--bench", "wb", "--subset", "code"]
    assert argv[argv.index("--substrate") + 1] == "cx"
    assert argv[argv.index("--k") + 1] == "3"
    assert argv[argv.index("--seed") + 1] == "7"
    assert argv[argv.index("--mode") + 1] == "parallel,sequential"
    assert argv[argv.index("--split") + 1] == "test"
    assert argv[argv.index("--workers") + 1] == "4"
    assert "--dry-run" in argv


def test_defaults_stay_quiet() -> None:
    argv = h2.build("run", h2.Options())
    assert argv == ["--bench", "jb", "--substrate", "oc", "--k", "1", "--mode", "parallel"]
    assert h2.build("check", h2.Options(bench="lab")) == ["--bench", "lab", "--substrate", "oc"]


def test_report_and_judge_shapes() -> None:
    rep = h2.build("report", h2.Options(report_k="1,2,3"))
    assert rep[rep.index("--k") + 1] == "1,2,3"
    jud = h2.build("judge", h2.Options(bases=True))
    assert jud[-1] == "--bases"


def test_validation_rejects_impossible_forms() -> None:
    for opts in (
        h2.Options(bench="jb", subset="code"),
        h2.Options(k=0),
        h2.Options(modes=()),
        h2.Options(modes=("bogus",)),
        h2.Options(split="test"),
        h2.Options(workers=0),
        h2.Options(max_tasks=0),
        h2.Options(port=70000),
        h2.Options(substrate="zz"),
    ):
        try:
            h2.validate(opts)
        except h2.ConfigError:
            continue
        raise AssertionError(f"expected ConfigError for {opts}")


def test_parse_check_real_output() -> None:
    text = (
        "FAIL: HARNESS2_SOLVER_MODEL is required for executor rollouts\n"
        "OK: python 3.12\n"
        "Setup incomplete: 9 issue(s). See docs/BENCHMARKS.md.\n"
    )
    issues, summary = h2.parse_check(text)
    assert [i.level for i in issues] == ["FAIL", "OK"]
    assert summary is not None and summary.startswith("Setup incomplete")


def test_env_roundtrip_quotes_and_comments(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_text('# keep me\nexport A="x y"\nB=1 # trailing\nC=\n')
    assert h2.read_env(p) == {"A": "x y", "B": "1", "C": ""}


def test_envfile_set_values_preserves_comments(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_text("# header\nA=old\n\n# note\nB=2\n")
    envfile.set_values(p, {"A": "new", "C": "3"})
    text = p.read_text()
    assert "# header" in text and "# note" in text
    assert "A=new" in text and "B=2" in text and "C=3" in text
    assert text.count("A=") == 1 and text.count("C=") == 1


def test_envfile_creates_file(tmp_path: Path) -> None:
    p = tmp_path / "sub" / ".env"
    envfile.set_values(p, {"X": "1"})
    assert "X=1" in p.read_text()


def test_model_parse_dedupes() -> None:
    got = models.parse("opencode/a-free\nalpha/b\n\nbad\nopencode/a-free\n")
    assert [m.id for m in got] == ["opencode/a-free", "alpha/b"]
    assert got[0].free and not got[1].free


def test_runs_scan_and_summarize(tmp_path: Path) -> None:
    d = tmp_path / "runs" / "demo"
    (d / "harnesses" / "base").mkdir(parents=True)
    (d / "demo.json").write_text('{"domain":"accounting","tasks":[{"task":"t1","status":"ok"}],"done":1}')
    (d / "harnesses" / "base" / "systemprompt.md").write_text("hello")
    arts = runs.scan(tmp_path / "runs")
    assert len(arts) == 1
    assert arts[0].kind == "demo"
    row = runs.summarize(arts[0])
    assert row["domain"] == "accounting" and row["tasks"] == "1/1 ok"


def test_harness_components(tmp_path: Path) -> None:
    base = tmp_path / "task" / "harnesses" / "base"
    (base / "skills" / "x").mkdir(parents=True)
    (base / "guardrails.md").write_text("g")
    hs = runs.harnesses(tmp_path / "task")
    assert [h.label for h in hs] == ["base"]
    assert hs[0].files["C2"].name == "guardrails.md"
    assert "C6" in hs[0].files
    assert runs.component_text(base / "skills") == "x"


def test_build_bridge_argv_carries_model_host_port() -> None:
    argv = h2.build("bridge", h2.Options(model="gemini-2.5-pro", host="0.0.0.0", port=8899))
    assert argv == ["--model", "gemini-2.5-pro", "--host", "0.0.0.0", "--port", "8899"]


def test_build_bridge_omits_blank_options() -> None:
    assert h2.build("bridge", h2.Options()) == []
