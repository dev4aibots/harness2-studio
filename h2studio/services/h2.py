"""Harness² command construction and process streaming.

The GUI never shells out through a shell string: every command is an argv list
built here, validated here, and tested here. Views only render results.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

BENCHES = {"jb": "JobBench", "lab": "LAB", "wb": "WorkBuddy"}
SUBSETS = ("office", "web", "code")
SUBSTRATES = {"oc": "OpenCode", "cx": "Codex"}
MODES = ("parallel", "sequential")

# One console entry point per real CLI module shipped by harness2 0.1.0.
MODULES = {
    "setup": "harness2.cli.setup",
    "check": "harness2.cli.check",
    "run": "harness2.cli.run_sweep",
    "judge": "harness2.cli.judge",
    "report": "harness2.cli.report",
    "demo": "harness2.cli.demo",
    "bridge": "harness2.cli.bridge",
}

ISSUE_RE = re.compile(r"^(FAIL|WARN|OK):\s*(.+)$")
SUMMARY_RE = re.compile(r"^Setup (incomplete|complete):\s*(.+)$")


class ConfigError(ValueError):
    """Invalid form input; the message is shown verbatim in the UI."""


@dataclass(frozen=True)
class Install:
    """A located Harness² checkout plus the interpreter that can run it."""

    repo: Path
    python: Path

    @property
    def runs_default(self) -> Path:
        return self.repo / "runs"

    @property
    def env_file(self) -> Path:
        return self.repo / ".env"

    def exists(self) -> bool:
        return (self.repo / "pyproject.toml").is_file() and self.python.is_file()


def discover(repo: str | Path, python: str | Path | None = None) -> Install:
    """Resolve a checkout, preferring an explicit interpreter over the venv."""
    root = Path(repo).expanduser().resolve()
    interp = Path(python).expanduser() if python else root / ".venv" / "bin" / "python"
    if not interp.is_file():
        # Windows layout, for a forkable UI that runs on any OS.
        alt = root / ".venv" / "Scripts" / "python.exe"
        interp = alt if alt.is_file() else interp
    return Install(root, interp)


@dataclass
class Options:
    """Every user-facing knob of the seven Harness² commands."""

    bench: str = "jb"
    subset: str | None = None
    substrate: str = "oc"
    k: int = 1
    seed: int | None = None
    modes: Sequence[str] = ("parallel",)
    split: str = "all"
    split_file: str | None = None
    workers: int = 1
    only_domains: str | None = None
    max_tasks: int | None = None
    dry_run: bool = False
    bases: bool = False
    report_k: str = "1"
    output: str | None = None
    demo_mode: str = "both"
    model: str | None = None
    host: str | None = None
    port: int | None = None


def _add(argv: list[str], flag: str, value) -> None:
    if value is not None and value != "":
        argv += [flag, str(value)]


def build(action: str, opts: Options) -> list[str]:
    """Build the argv tail for one command. Raises ConfigError on bad input."""
    if action not in MODULES:
        raise ConfigError(f"unknown action: {action}")
    if opts.bench not in BENCHES:
        raise ConfigError(f"benchmark must be one of {sorted(BENCHES)}")

    validate(opts)

    if action == "setup":
        argv = [opts.bench]
        _add(argv, "--subset", opts.subset)
        _add(argv, "--substrate", opts.substrate)
        if opts.dry_run:
            argv.append("--dry-run")
        return argv

    if action == "check":
        argv = ["--bench", opts.bench]
        _add(argv, "--subset", opts.subset)
        _add(argv, "--substrate", opts.substrate)
        return argv

    if action in ("run", "judge"):
        argv = ["--bench", opts.bench]
        _add(argv, "--subset", opts.subset)
        _add(argv, "--substrate", opts.substrate)
        _add(argv, "--k", opts.k)
        _add(argv, "--seed", opts.seed)
        _add(argv, "--mode", ",".join(opts.modes))
        _add(argv, "--split", None if opts.split == "all" else opts.split)
        _add(argv, "--split-file", opts.split_file)
        _add(argv, "--workers", opts.workers if opts.workers != 1 else None)
        _add(argv, "--only-domains", opts.only_domains)
        _add(argv, "--max-tasks", opts.max_tasks)
        if opts.dry_run and action == "run":
            argv.append("--dry-run")
        if opts.bases and action == "judge":
            argv.append("--bases")
        return argv

    if action == "report":
        argv = ["--bench", opts.bench]
        _add(argv, "--subset", opts.subset)
        _add(argv, "--substrate", opts.substrate)
        _add(argv, "--k", opts.report_k)
        _add(argv, "--seed", opts.seed)
        _add(argv, "--mode", ",".join(opts.modes))
        return argv

    if action == "demo":
        argv = []
        _add(argv, "--output", opts.output)
        _add(argv, "--k", opts.k)
        _add(argv, "--mode", opts.demo_mode)
        return argv

    argv = []  # bridge
    _add(argv, "--model", opts.model)
    _add(argv, "--host", opts.host)
    _add(argv, "--port", opts.port)
    return argv


def validate(opts: Options) -> None:
    if opts.subset and opts.bench != "wb":
        raise ConfigError("subsets exist only for WorkBuddy-Bench (wb)")
    if opts.subset and opts.subset not in SUBSETS:
        raise ConfigError(f"subset must be one of {SUBSETS}")
    if opts.substrate not in SUBSTRATES:
        raise ConfigError(f"substrate must be one of {sorted(SUBSTRATES)}")
    if not isinstance(opts.k, int) or opts.k < 1:
        raise ConfigError("k must be an integer >= 1")
    bad = [m for m in opts.modes if m not in MODES]
    if not opts.modes or bad:
        raise ConfigError(f"mode must be a non-empty subset of {MODES}")
    if opts.split not in ("all", "train", "test"):
        raise ConfigError("split must be all, train, or test")
    if opts.split == "test" and not opts.split_file:
        raise ConfigError("split=test requires a split file")
    if opts.workers < 1:
        raise ConfigError("workers must be >= 1")
    if opts.max_tasks is not None and opts.max_tasks < 1:
        raise ConfigError("max-tasks must be >= 1")
    if opts.port is not None and not (0 < opts.port < 65536):
        raise ConfigError("port must be 1-65535")


def full_argv(install: Install, action: str, opts: Options) -> list[str]:
    return [str(install.python), "-m", MODULES[action], *build(action, opts)]


def merged_env(install: Install, overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Process env + .env + explicit overrides; shell wins, per harness2 config.py."""
    env = dict(os.environ)
    for key, value in read_env(install.env_file).items():
        env.setdefault(key, value)
    if overrides:
        env.update({k: v for k, v in overrides.items() if v is not None})
    return env


def read_env(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines exactly as harness2.config.load_dotenv does."""
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not all(c.isalnum() or c == "_" for c in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        out[key] = value
    return out


@dataclass
class Issue:
    level: str
    message: str


def parse_check(text: str) -> tuple[list[Issue], str | None]:
    """Split `harness2-check` output into issues and a one-line summary."""
    issues: list[Issue] = []
    summary: str | None = None
    for line in text.splitlines():
        m = ISSUE_RE.match(line.strip())
        if m:
            issues.append(Issue(m.group(1), m.group(2)))
            continue
        s = SUMMARY_RE.match(line.strip())
        if s:
            summary = f"Setup {s.group(1)}: {s.group(2)}"
    return issues, summary


@dataclass
class Stream:
    """A running child process, streamed line by line into a callback."""

    argv: list[str]
    cwd: Path
    env: dict[str, str]
    on_line: Callable[[str], None]
    on_done: Callable[[int], None] = lambda code: None
    _proc: subprocess.Popen | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    def start(self) -> Stream:
        self._proc = subprocess.Popen(
            self.argv,
            cwd=str(self.cwd),
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            start_new_session=True,  # own process group, so stop() can take the tree
        )
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()
        return self

    def _pump(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            self.on_line(line.rstrip("\n"))
        code = proc.wait()
        self.on_done(code)

    def stop(self) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(proc.pid), 15)
            else:
                proc.terminate()
        except OSError:
            pass
        threading.Thread(target=self._escalate, args=(proc,), daemon=True).start()

    @staticmethod
    def _escalate(proc: subprocess.Popen) -> None:
        """Give the process tree 3 s to exit cleanly, then force it."""
        try:
            proc.wait(timeout=3)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(proc.pid), 9)
            else:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                               capture_output=True, check=False)
        except OSError:
            pass

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


def which_opencode() -> str | None:
    return shutil.which("opencode")
