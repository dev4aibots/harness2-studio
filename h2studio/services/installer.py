"""Install or update the upstream Harness² source without git.

The installer is deliberately boring: ask GitHub for the current tree, download
only source/doc/test files, verify every blob against its git object hash, write
a manifest, then create a venv and prove the package imports. No shell strings,
no third-party dependencies, no execution of remote code beyond ``--help``.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO = "google-research/harness2"
API = "https://api.github.com/repos/{repo}"
RAW = "https://raw.githubusercontent.com/{repo}/{sha}/{path}"
CDN = "https://cdn.jsdelivr.net/gh/{repo}@{sha}/{path}"
MARKER = ".harness2-studio.json"
BACKUPS = ".harness2-studio-backups"

INCLUDE_PREFIXES = ("harness2/", "scripts/", "docs/", "tests/", "third_party/", "dependencies/")
INCLUDE_FILES = {"pyproject.toml", "README.md", "LICENSE", "MANIFEST.in", "CONTRIBUTING.md"}
EXCLUDE_PARTS = ("__pycache__/", ".pyc", "assets/", "runs/", ".venv/", ".git/", ".github/")

Progress = Callable[[str, int, int, str], None]
ByteProgress = Callable[[int], None]


class InstallError(RuntimeError):
    """Actionable installation failure shown verbatim in the UI."""


class IntegrityError(InstallError):
    """A downloaded file did not match the git blob hash."""


class InstallCancelled(InstallError):
    """The user stopped the install; partial files remain resumable."""


@dataclass(frozen=True)
class RemoteFile:
    path: str
    sha: str
    size: int


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    date: str
    message: str


@dataclass(frozen=True)
class FileRecord:
    sha: str
    size: int


@dataclass
class Marker:
    schema: int
    repo: str
    commit: str
    commit_date: str
    installed_at: str
    version: str
    files: dict[str, FileRecord] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    new: list[RemoteFile]
    unchanged: list[RemoteFile]
    modified: list[RemoteFile]


@dataclass
class InstallResult:
    installed: int
    backed_up: list[str]
    version: str
    venv: Path | None
    marker: Marker


def git_blob_sha(data: bytes) -> str:
    """Git's object hash for a blob: sha1('blob <len>\\0' + data)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def part_path(target: Path) -> Path:
    return target.with_name(target.name + ".part")


RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *{f"com{i}" for i in range(1, 10)},
    *{f"lpt{i}" for i in range(1, 10)},
}


def _safe_path(path: str) -> bool:
    if not path or path.startswith(("/", "\\")):
        return False
    if "\\" in path:
        return False
    if ":" in path:  # Windows drive/ADS/stream syntax
        return False
    if any(ord(ch) < 32 for ch in path):
        return False
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    for part in parts:
        stem = part.split(".", 1)[0].strip().lower()
        if stem in RESERVED_NAMES:
            return False
        if part.endswith((" ", ".")):
            return False
    return True


def filter_tree(entries: Iterable[dict]) -> list[RemoteFile]:
    """Select installable blobs and reject anything that could escape the root."""
    chosen: dict[str, RemoteFile] = {}
    for entry in entries:
        if entry.get("type") != "blob":
            continue
        path = str(entry.get("path", ""))
        if not _safe_path(path):
            raise InstallError(
                f"Upstream tree contains an unsafe path: {path!r}. Refusing to install."
            )
        if any(part in path for part in EXCLUDE_PARTS):
            continue
        if path not in INCLUDE_FILES and not path.startswith(INCLUDE_PREFIXES):
            continue
        sha = str(entry.get("sha", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise InstallError(f"Upstream tree has an invalid blob hash for {path}.")
        chosen[path] = RemoteFile(path=path, sha=sha, size=int(entry.get("size") or 0))
    if "pyproject.toml" not in chosen or not any(p.startswith("harness2/") for p in chosen):
        raise InstallError("Upstream tree does not look like Harness² (missing pyproject or package).")
    return sorted(chosen.values(), key=lambda f: f.path)


def parse_commit(payload: bytes | str) -> CommitInfo:
    try:
        data = json.loads(payload)
        sha = str(data["sha"])
        commit = data["commit"]
        date = str(commit["author"]["date"])
        message = str(commit.get("message", "")).splitlines()[0]
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise InstallError(f"GitHub returned an unexpected commit payload: {exc}") from None
    return CommitInfo(sha=sha, date=date, message=message)


def repo_version(dest: Path) -> str:
    pyproject = dest / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else ""


def marker_path(dest: Path) -> Path:
    return dest / MARKER


def read_marker(dest: Path) -> Marker | None:
    path = marker_path(dest)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        files = {
            str(name): FileRecord(sha=str(rec["sha"]), size=int(rec.get("size") or 0))
            for name, rec in (data.get("files") or {}).items()
        }
        return Marker(
            schema=int(data.get("schema", 1)),
            repo=str(data.get("repo", REPO)),
            commit=str(data.get("commit", "")),
            commit_date=str(data.get("commit_date", "")),
            installed_at=str(data.get("installed_at", "")),
            version=str(data.get("version", "")),
            files=files,
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_marker(dest: Path, marker: Marker) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": marker.schema,
        "repo": marker.repo,
        "commit": marker.commit,
        "commit_date": marker.commit_date,
        "installed_at": marker.installed_at,
        "version": marker.version,
        "files": {name: {"sha": rec.sha, "size": rec.size} for name, rec in sorted(marker.files.items())},
    }
    tmp = marker_path(dest).with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, marker_path(dest))


def assert_installable(dest: Path) -> None:
    """Only touch an empty directory, an existing managed install, or a real checkout."""
    if not dest.exists():
        return
    if not dest.is_dir():
        raise InstallError(f"{dest} is a file, not a folder. Choose another destination.")
    if dest == Path(dest.anchor):
        raise InstallError("Refusing to install into a filesystem root. Choose a subfolder.")
    if marker_path(dest).is_file():
        return
    children = list(dest.iterdir())
    if not children:
        return
    pyproject = dest / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if re.search(r'name\s*=\s*"harness2"', text):
            return  # adopt an existing, unmanaged checkout
    raise InstallError(
        f"{dest} is not empty and is not a Harness² checkout. Choose an empty folder "
        "or an existing Harness² directory."
    )


def plan_files(dest: Path, files: Sequence[RemoteFile], marker: Marker | None) -> Plan:
    new: list[RemoteFile] = []
    unchanged: list[RemoteFile] = []
    modified: list[RemoteFile] = []
    known = marker.files if marker else {}
    for remote in files:
        local = dest / remote.path
        if not local.is_file():
            new.append(remote)
            continue
        try:
            local_sha = git_blob_sha(local.read_bytes())
        except OSError:
            modified.append(remote)
            continue
        if local_sha == remote.sha:
            unchanged.append(remote)
        elif remote.path in known and known[remote.path].sha == local_sha:
            modified.append(remote)  # pristine copy of the previous release
        else:
            modified.append(remote)  # user edit, or unmanaged checkout
    return Plan(new=new, unchanged=unchanged, modified=modified)


def file_urls(repo: str, sha: str, path: str) -> list[str]:
    quoted = quote(path)
    return [
        RAW.format(repo=repo, sha=sha, path=quoted),
        CDN.format(repo=repo, sha=sha, path=quoted),
    ]


def _backup(dest: Path, path: str, stamp: str) -> None:
    source = dest / path
    if not source.is_file():
        return
    target = dest / BACKUPS / stamp / path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def download_file(
    fetcher,
    urls: Sequence[str],
    target: Path,
    expected_sha: str,
    *,
    cancel: threading.Event | None = None,
    progress: ByteProgress | None = None,
    before_replace: Callable[[], None] | None = None,
    expected_size: int | None = None,
) -> None:
    """Download with Range resume, trying each mirror before failing.

    A complete ``.part`` file is promoted without another request, so a crash
    between write and replace cannot strand a finished download. A body shorter
    than the tree's announced size keeps its bytes for a Range resume; a
    full-length body that fails the hash is corrupt, so it deletes the part and
    tries the next mirror. Timeouts and connection drops never abort the whole
    install while a mirror remains.
    """
    if cancel is not None and cancel.is_set():
        raise InstallCancelled("Install cancelled.")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        part = part_path(target)
        start = part.stat().st_size if part.is_file() else 0
    except OSError as exc:
        raise InstallError(f"Cannot write to {target.parent}: {exc}. Choose a writable folder.") from None

    def close_reader(reader) -> None:
        closer = getattr(reader, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:  # noqa: BLE001, S110 - a close failure cannot change the outcome
                pass

    if start:
        try:
            if git_blob_sha(part.read_bytes()) == expected_sha:
                if before_replace is not None:
                    before_replace()
                os.replace(part, target)
                return
        except OSError as exc:
            raise InstallError(f"Cannot read the partial file for {target.name}: {exc}") from None

    opener = getattr(fetcher, "open", None)
    last_error: Exception | None = None
    integrity_error: IntegrityError | None = None
    for url in urls:
        attempt = 0
        while attempt < 2:
            attempt += 1
            _check_cancel(cancel)

            if opener is not None:
                # Streaming path: bytes land in .part as they arrive, so a
                # connection drop keeps everything already downloaded.
                try:
                    status, reader = opener(url, start, cancel)
                except (OSError, HTTPException) as exc:
                    last_error = exc
                    break
                if status == 416:
                    close_reader(reader)
                    try:
                        part.unlink(missing_ok=True)
                    except OSError:
                        pass
                    if start:
                        start = 0
                        continue
                    last_error = OSError("HTTP 416")
                    break
                if status == 206 and not (start and part.is_file()):
                    close_reader(reader)
                    start = 0
                    continue
                if status not in (200, 206):
                    close_reader(reader)
                    last_error = OSError(f"HTTP {status}")
                    break
                mode = "ab" if (status == 206 and start and part.is_file()) else "wb"
                written = start if mode == "ab" else 0
                dropped = False
                try:
                    with part.open(mode) as handle:
                        while True:
                            chunk = reader.read(65_536)
                            if not chunk:
                                break
                            handle.write(chunk)
                            written += len(chunk)
                            start = written  # a drop resumes from the last byte on disk
                            if progress is not None:
                                progress(written)
                            _check_cancel(cancel)
                    if expected_size is not None and written < expected_size:
                        # A clean EOF before the announced size is still a drop:
                        # keep the bytes and resume from them on the next mirror.
                        dropped = True
                        last_error = OSError(f"short body ({written}/{expected_size} bytes)")
                except (OSError, HTTPException) as exc:
                    last_error = exc
                    dropped = True  # partial bytes stay on disk for the next attempt
                finally:
                    close_reader(reader)
                if dropped:
                    break
            else:
                try:
                    status, data = fetcher.fetch(url, start)
                except (OSError, HTTPException) as exc:
                    last_error = exc
                    break
                if status == 416:
                    try:
                        part.unlink(missing_ok=True)
                    except OSError:
                        pass
                    if start:
                        start = 0
                        continue
                    last_error = OSError("HTTP 416")
                    break
                if status == 206 and not (start and part.is_file()):
                    # A server answered a range we cannot use; restart the request.
                    start = 0
                    continue
                if status not in (200, 206):
                    last_error = OSError(f"HTTP {status}")
                    break
                try:
                    payload = part.read_bytes() + data if (status == 206 and start and part.is_file()) else data
                except OSError as exc:
                    raise InstallError(f"Cannot read the partial file for {target.name}: {exc}") from None
                if progress is not None:
                    progress(len(payload))
                try:
                    part.write_bytes(payload)
                except OSError as exc:
                    raise InstallError(
                        f"Cannot write {target}: {exc}. Check permissions and free disk space, then retry."
                    ) from None
                start = len(payload)
                if expected_size is not None and len(payload) < expected_size:
                    last_error = OSError(f"short body ({len(payload)}/{expected_size} bytes)")
                    break  # keep the partial file and resume with the next mirror

            try:
                digest = git_blob_sha(part.read_bytes())
            except OSError as exc:
                raise InstallError(f"Cannot read the download for {target.name}: {exc}") from None
            if digest != expected_sha:
                try:
                    part.unlink(missing_ok=True)
                except OSError:
                    pass
                integrity_error = IntegrityError(
                    f"Integrity check failed for {target.name}; the download did not match GitHub."
                )
                last_error = integrity_error
                break  # try the next mirror with a clean part
            try:
                if before_replace is not None:
                    before_replace()
                os.replace(part, target)
            except OSError as exc:
                raise InstallError(
                    f"Cannot write {target}: {exc}. Check permissions and free disk space, then retry."
                ) from None
            return
    if integrity_error is not None:
        raise integrity_error
    if last_error is not None:
        raise InstallError(
            f"Network error while downloading {target.name}: {last_error}. "
            "Check your connection or proxy, then retry; partial downloads resume."
        ) from None
    raise InstallError(f"Could not download {target.name} from any mirror.")


def install_files(
    dest: Path,
    files: Sequence[RemoteFile],
    *,
    fetcher,
    repo: str = REPO,
    sha: str,
    commit_date: str = "",
    cancel: threading.Event | None = None,
    progress: Progress | None = None,
    workers: int = 6,
    make_environment: bool = False,
    python: str | None = None,
) -> InstallResult:
    assert_installable(dest)
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise InstallError(f"Cannot create {dest}: {exc}. Choose a writable folder.") from None
    marker = read_marker(dest)
    plan = plan_files(dest, files, marker)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    modified = {r.path for r in plan.modified}
    if progress:
        progress(
            "backup", len(plan.modified), len(plan.modified),
            "local edits are copied just before their file is replaced" if modified else "nothing to preserve",
        )

    todo = plan.new + plan.modified
    done = 0
    lock = threading.Lock()
    if progress:
        progress("download", 0, len(todo), "Starting download")

    def target_for(path: str) -> Path:
        candidate = (dest / path).resolve()
        root = dest.resolve()
        if candidate != root and root not in candidate.parents:
            raise InstallError(f"Refusing to write outside the checkout: {candidate}")
        return candidate

    def work(remote: RemoteFile) -> RemoteFile:
        if cancel is not None and cancel.is_set():
            raise InstallCancelled("Install cancelled.")
        target = target_for(remote.path)
        preserve = (lambda p=remote.path: _backup(dest, p, stamp)) if remote.path in modified else None
        download_file(
            fetcher,
            file_urls(repo, sha, remote.path),
            target,
            remote.sha,
            cancel=cancel,
            progress=None,
            before_replace=preserve,
            expected_size=remote.size or None,
        )
        return remote

    try:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(work, remote): remote for remote in todo}
            for future in as_completed(futures):
                remote = future.result()
                with lock:
                    done += 1
                    if progress:
                        progress("download", done, len(todo), remote.path)
    except InstallCancelled:
        raise
    except InstallError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalise worker failures for the UI
        raise InstallError(f"Download failed: {exc}") from None

    version = repo_version(dest)
    new_marker = Marker(
        schema=1,
        repo=repo,
        commit=sha,
        commit_date=commit_date,
        installed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        version=version,
        files={f.path: FileRecord(sha=f.sha, size=f.size) for f in files},
    )
    write_marker(dest, new_marker)

    venv = None
    if make_environment:
        if progress:
            progress("environment", 0, 1, "Creating the Python environment")
        venv = ensure_environment(dest, python or sys.executable, progress=progress, cancel=cancel)
        if progress:
            progress("environment", 1, 1, "Environment ready")

    return InstallResult(
        installed=len(todo),
        backed_up=sorted(r.path for r in plan.modified),
        version=version,
        venv=venv,
        marker=new_marker,
    )


def venv_python(dest: Path) -> Path:
    if os.name == "nt":
        return dest / ".venv" / "Scripts" / "python.exe"
    return dest / ".venv" / "bin" / "python"


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise InstallCancelled("Install cancelled.")


def _run_command(command: list[str], *, timeout: float, cancel: threading.Event | None = None) -> subprocess.CompletedProcess:
    """Run a short command, but let Cancel terminate it promptly."""
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        raise InstallError(f"Could not start {' '.join(command[:3])}: {exc}") from None
    deadline = time.monotonic() + timeout
    while True:
        try:
            out, err = proc.communicate(timeout=0.25)
            return subprocess.CompletedProcess(command, proc.returncode or 0, out, err)
        except subprocess.TimeoutExpired:
            if cancel is not None and cancel.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise InstallCancelled("Install cancelled.") from None
            if time.monotonic() > deadline:
                proc.kill()
                raise InstallError(f"Command timed out after {int(timeout)}s: {' '.join(command[:3])}")
        except OSError as exc:
            raise InstallError(f"Command failed: {exc}") from None


def ensure_environment(
    dest: Path,
    python: str,
    *,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    """Create a venv without pip and make the checkout importable from anywhere."""
    _check_cancel(cancel)
    vpy = venv_python(dest)
    if not vpy.is_file():
        command = [python, "-m", "venv", str(dest / ".venv")]
        proc = _run_command(command, timeout=300, cancel=cancel)
        if proc.returncode != 0:
            # ensurepip is optional on some Linux distributions; we do not need pip.
            proc = _run_command(
                [python, "-m", "venv", "--without-pip", str(dest / ".venv")],
                timeout=300, cancel=cancel,
            )
        if proc.returncode != 0:
            raise InstallError(
                "Could not create .venv. Install the venv module for your Python "
                "(Debian/Ubuntu: sudo apt install python3.12-venv) and retry."
            )
    _check_cancel(cancel)
    if not vpy.is_file():
        raise InstallError(f"Python environment exists but has no interpreter at {vpy}.")
    out = _run_command(
        [str(vpy), "-c", "import site; print(site.getsitepackages()[0])"],
        timeout=30, cancel=cancel,
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise InstallError("The new environment is unusable; remove .venv and retry.")
    pth = Path(out.stdout.strip()) / "harness2-studio.pth"
    try:
        pth.parent.mkdir(parents=True, exist_ok=True)
        pth.write_text(str(dest) + "\n", encoding="utf-8")
    except OSError as exc:
        raise InstallError(f"Cannot write the environment file {pth}: {exc}") from None
    _check_cancel(cancel)
    check_python_version(vpy)
    _check_cancel(cancel)
    return vpy


def check_python_version(python: Path | str) -> tuple[int, int]:
    try:
        out = subprocess.run(
            [str(python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InstallError(f"Python at {python} is unusable: {exc}") from None
    if out.returncode != 0:
        raise InstallError(f"Python at {python} is unusable: {out.stderr.strip()}")
    try:
        major, minor = (int(part) for part in out.stdout.strip().split(".", 1))
    except ValueError:
        raise InstallError(f"Could not read the Python version from {python}: {out.stdout!r}") from None
    if (major, minor) < (3, 12) or (major, minor) >= (3, 14):
        raise InstallError(
            f"Harness² needs Python 3.12 or 3.13; {python} is {major}.{minor}. "
            "Point the app at a supported interpreter or install one."
        )
    return major, minor


def verify_install(dest: Path, venv: Path | None = None) -> str:
    vpy = venv or venv_python(dest)
    if not vpy.is_file():
        raise InstallError(f"No environment at {vpy}. Run Install first.")
    try:
        proc = subprocess.run(
            [str(vpy), "-m", "harness2.cli.demo", "--help"],
            cwd=dest, capture_output=True, text=True, timeout=45, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InstallError(f"Could not verify the installation: {exc}") from None
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise InstallError(
            "Harness² is downloaded but does not import yet. "
            + (detail[-1] if detail else "Run Verify again for details.")
        )
    version = repo_version(dest)
    return version or "unknown"


EXTRAS: dict[str, tuple[str, ...]] = {
    "render": ("openpyxl>=3.1,<4", "python-pptx>=1,<2"),
    "bridge": ("litellm[proxy]==1.95.0", "fastapi==0.139.2", "google-auth==2.56.3"),
}
EXTRA_MODULES: dict[str, tuple[str, ...]] = {
    "render": ("openpyxl", "pptx"),
    "bridge": ("litellm", "fastapi", "google.auth"),
}


def extra_packages(groups: Sequence[str]) -> list[str]:
    packages: list[str] = []
    for group in groups:
        for package in EXTRAS.get(group, ()):
            if package not in packages:
                packages.append(package)
    return packages


def pip_command(venv: Path | str, groups: Sequence[str]) -> list[str]:
    packages = extra_packages(groups)
    if not packages:
        raise InstallError("No optional package group selected.")
    return [str(venv), "-m", "pip", "install", "--disable-pip-version-check",
            "--no-input", *packages]


def missing_extras(dest: Path, venv: Path | None = None, groups: Sequence[str] = ("render", "bridge")) -> dict[str, list[str]]:
    """Return import names that are absent, per optional group."""
    vpy = venv or venv_python(dest)
    if not vpy.is_file():
        return {group: list(EXTRA_MODULES[group]) for group in groups}
    names = [name for group in groups for name in EXTRA_MODULES[group]]
    script = (
        "import importlib.util as u, json; "
        f"print(json.dumps([m for m in {names!r} if u.find_spec(m) is None]))"
    )
    try:
        proc = subprocess.run([str(vpy), "-c", script], cwd=dest, capture_output=True,
                              text=True, timeout=30, check=False)
        missing = set(json.loads(proc.stdout.strip() or "[]")) if proc.returncode == 0 else set(names)
    except (OSError, subprocess.SubprocessError, ValueError):
        missing = set(names)
    return {group: [m for m in EXTRA_MODULES[group] if m in missing] for group in groups}


def install_extras(
    dest: Path,
    *,
    venv: Path | None = None,
    groups: Sequence[str] = ("render",),
    cancel: threading.Event | None = None,
    progress: Progress | None = None,
) -> str:
    """Install optional packages. Streams pip lines through progress detail."""
    vpy = venv or venv_python(dest)
    if not vpy.is_file():
        raise InstallError(f"No environment at {vpy}. Run Install first.")
    check = subprocess.run([str(vpy), "-m", "pip", "--version"], cwd=dest,
                           capture_output=True, text=True, timeout=30, check=False)
    if check.returncode != 0:
        raise InstallError(
            "pip is not available inside .venv. Install it with: "
            f"{vpy} -m ensurepip --upgrade"
        )
    command = pip_command(vpy, groups)
    if progress:
        progress("extras", 0, 1, "$ " + " ".join(command))
    try:
        proc = subprocess.Popen(
            command, cwd=dest, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=(os.name == "posix"),
        )
    except OSError as exc:
        raise InstallError(f"Could not start pip: {exc}") from None
    tail: list[str] = []

    def kill_tree() -> None:
        if proc.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(proc.pid), 15)
            else:
                proc.terminate()
        except OSError:
            proc.terminate()

    def watch_cancel() -> None:
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                kill_tree()
                return
            time.sleep(0.2)

    if cancel is not None:
        threading.Thread(target=watch_cancel, daemon=True).start()
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            tail = [*tail[-20:], line]
            if progress:
                progress("extras", 0, 1, line)
        if cancel is not None and cancel.is_set():
            kill_tree()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            raise InstallCancelled("Package install cancelled; rerun to continue.")
    code = proc.wait()
    if code != 0:
        detail = tail[-1] if tail else f"pip exited {code}"
        raise InstallError(f"pip could not install {', '.join(groups)}: {detail}")
    return ", ".join(extra_packages(groups))


@dataclass
class UrllibFetcher:
    """HTTPS with a short timeout and an optional GitHub token (never logged)."""

    timeout: float = 25.0
    token: str = ""

    def _headers(self, url: str, start: int) -> dict[str, str]:
        headers = {"User-Agent": "harness2-studio/1.1 (+https://github.com/google-research/harness2)"}
        if self.token and "api.github.com" in url:
            headers["Authorization"] = f"Bearer {self.token}"
        if start:
            headers["Range"] = f"bytes={start}-"
        return headers

    def fetch(self, url: str, start: int = 0) -> tuple[int, bytes]:
        request = Request(url, headers=self._headers(url, start))
        with urlopen(request, timeout=self.timeout) as response:
            return int(response.status), response.read()

    def open(self, url: str, start: int = 0, cancel=None):
        """Streaming open: (status, reader). HTTP 4xx returns the code, never raises."""
        request = Request(url, headers=self._headers(url, start))
        try:
            response = urlopen(request, timeout=self.timeout)
        except HTTPError as exc:
            return int(exc.code), io.BytesIO(b"")
        return int(response.status), response


def latest_commit(fetcher, repo: str = REPO) -> CommitInfo:
    url = f"{API.format(repo=repo)}/commits/main"
    try:
        status, data = fetcher.fetch(url)
    except (OSError, HTTPException) as exc:
        raise InstallError(f"Network error while checking GitHub: {exc}") from None
    if status != 200:
        raise InstallError(f"GitHub returned HTTP {status} while checking the latest commit.")
    return parse_commit(data)


def remote_tree(fetcher, sha: str, repo: str = REPO) -> list[RemoteFile]:
    url = f"{API.format(repo=repo)}/git/trees/{sha}?recursive=1"
    try:
        status, data = fetcher.fetch(url)
    except (OSError, HTTPException) as exc:
        raise InstallError(f"Network error while reading the file list: {exc}") from None
    if status != 200:
        raise InstallError(f"GitHub returned HTTP {status} while reading the file list.")
    try:
        payload = json.loads(data)
    except ValueError as exc:
        raise InstallError(f"GitHub returned an unreadable file list: {exc}") from None
    if payload.get("truncated"):
        raise InstallError("GitHub truncated the file list; retry or use git clone.")
    return filter_tree(payload.get("tree") or [])


def install(
    dest: Path,
    *,
    fetcher=None,
    repo: str = REPO,
    sha: str | None = None,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
    python: str | None = None,
    make_environment: bool = True,
    workers: int = 6,
) -> InstallResult:
    """High-level install/update: resolve latest, plan, download, verify."""
    fetcher = fetcher or UrllibFetcher(token=os.environ.get("GITHUB_TOKEN", ""))
    dest = dest.expanduser().resolve()
    assert_installable(dest)
    _check_cancel(cancel)
    if progress:
        progress("check", 0, 1, "Reading the latest Harness² release")
    commit = latest_commit(fetcher, repo)
    files = remote_tree(fetcher, commit.sha, repo)
    _check_cancel(cancel)
    if progress:
        progress("check", 1, 1, f"{commit.sha[:8]} · {len(files)} files")
    result = install_files(
        dest, files, fetcher=fetcher, repo=repo, sha=commit.sha,
        commit_date=commit.date, cancel=cancel, progress=progress,
        workers=workers, make_environment=make_environment, python=python,
    )
    if make_environment:
        _check_cancel(cancel)
        if progress:
            progress("verify", 0, 1, "Running the import check")
        verify_install(dest, result.venv)
        if progress:
            progress("verify", 1, 1, "Import check passed")
    return result
