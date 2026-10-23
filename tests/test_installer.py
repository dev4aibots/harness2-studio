from __future__ import annotations

import hashlib
import json
import sys
import threading
from pathlib import Path

import pytest

from h2studio.services import installer

TREE = [
    {"type": "blob", "path": "harness2/__init__.py", "sha": "a" * 40, "size": 10},
    {"type": "blob", "path": "harness2/cli/demo.py", "sha": "b" * 40, "size": 20},
    {"type": "blob", "path": "pyproject.toml", "sha": "c" * 40, "size": 30},
    {"type": "blob", "path": "third_party/patches/x.diff", "sha": "d" * 40, "size": 40},
    {"type": "blob", "path": "assets/video.mp4", "sha": "e" * 40, "size": 50},
    {"type": "blob", "path": "harness2/__pycache__/x.pyc", "sha": "f" * 40, "size": 5},
    {"type": "blob", "path": "dependencies/README.md", "sha": "1" * 40, "size": 6},
    {"type": "blob", "path": "runs/demo/x.json", "sha": "2" * 40, "size": 7},
    {"type": "tree", "path": "harness2", "sha": "3" * 40},
]


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def test_filter_tree_keeps_code_and_drops_assets_and_scratch() -> None:
    files = installer.filter_tree(TREE)
    paths = [f.path for f in files]
    assert "harness2/__init__.py" in paths
    assert "pyproject.toml" in paths
    assert "third_party/patches/x.diff" in paths
    assert "dependencies/README.md" in paths
    assert all(not p.startswith(("assets/", "runs/")) for p in paths)
    assert all("__pycache__" not in p for p in paths)
    assert all(isinstance(f.sha, str) and len(f.sha) == 40 for f in files)


def test_filter_tree_rejects_traversal_and_absolute_paths() -> None:
    bad = [
        {"type": "blob", "path": "../etc/passwd", "sha": "a" * 40, "size": 1},
        {"type": "blob", "path": "/etc/passwd", "sha": "b" * 40, "size": 1},
        {"type": "blob", "path": "harness2/../../x", "sha": "c" * 40, "size": 1},
    ]
    with pytest.raises(installer.InstallError):
        installer.filter_tree(bad)


def test_git_blob_sha_matches_git_object_hash() -> None:
    assert installer.git_blob_sha(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    assert installer.git_blob_sha(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_plan_classifies_new_unchanged_modified(tmp_path: Path) -> None:
    dest = tmp_path / "repo"
    (dest / "harness2").mkdir(parents=True)
    unchanged = b"same\n"
    modified = b"local edit\n"
    (dest / "harness2" / "a.py").write_bytes(unchanged)
    (dest / "harness2" / "b.py").write_bytes(modified)
    marker = installer.Marker(
        schema=1,
        repo="google-research/harness2",
        commit="old",
        commit_date="",
        installed_at="",
        version="0.1.0",
        files={
            "harness2/a.py": installer.FileRecord(sha=blob_sha(unchanged), size=len(unchanged)),
            "harness2/b.py": installer.FileRecord(sha=blob_sha(b"original\n"), size=10),
        },
    )
    installer.write_marker(dest, marker)
    files = [
        installer.RemoteFile("harness2/a.py", blob_sha(unchanged), len(unchanged)),
        installer.RemoteFile("harness2/b.py", blob_sha(b"upstream\n"), 9),
        installer.RemoteFile("harness2/c.py", blob_sha(b"new\n"), 4),
    ]
    plan = installer.plan_files(dest, files, marker)
    assert [f.path for f in plan.new] == ["harness2/c.py"]
    assert [f.path for f in plan.unchanged] == ["harness2/a.py"]
    assert [f.path for f in plan.modified] == ["harness2/b.py"]


class FakeFetcher:
    def __init__(self, blobs: dict[str, bytes]):
        self.blobs = blobs
        self.calls: list[tuple[str, int]] = []

    def fetch(self, url: str, start: int = 0) -> tuple[int, bytes]:
        self.calls.append((url, start))
        path = url.split("/")[-1]
        data = self.blobs[path]
        if start:
            return 206, data[start:]
        return 200, data


def test_download_resumes_partial_and_verifies(tmp_path: Path) -> None:
    data = b"hello world\n" * 100
    sha = blob_sha(data)
    target = tmp_path / "f.py"
    part = installer.part_path(target)
    part.write_bytes(data[:250])
    fetcher = FakeFetcher({"f.py": data})
    installer.download_file(
        fetcher, ["https://raw.test/sha/f.py"], target, sha,
        cancel=threading.Event(), progress=lambda _n: None,
    )
    assert target.read_bytes() == data
    assert not part.exists()
    assert fetcher.calls and fetcher.calls[0][1] == 250


def test_download_rejects_corrupt_bytes(tmp_path: Path) -> None:
    target = tmp_path / "f.py"
    fetcher = FakeFetcher({"f.py": b"not what was promised"})
    with pytest.raises(installer.IntegrityError):
        installer.download_file(
            fetcher, ["https://raw.test/sha/f.py"], target, "a" * 40,
            cancel=threading.Event(), progress=lambda _n: None,
        )
    assert not target.exists()


def test_install_writes_files_and_marker_and_backs_up_modified(tmp_path: Path) -> None:
    dest = tmp_path / "repo"
    blobs = {"a.py": b"alpha\n", "b.py": b"beta upstream\n"}
    files = [
        installer.RemoteFile("harness2/a.py", blob_sha(blobs["a.py"]), len(blobs["a.py"])),
        installer.RemoteFile("harness2/b.py", blob_sha(blobs["b.py"]), len(blobs["b.py"])),
    ]
    (dest / "harness2").mkdir(parents=True)
    (dest / "harness2" / "b.py").write_bytes(b"my own edit\n")
    installer.write_marker(dest, installer.Marker(
        schema=1, repo="google-research/harness2", commit="old", commit_date="",
        installed_at="", version="0.1.0",
        files={"harness2/b.py": installer.FileRecord(sha=blob_sha(b"old upstream\n"), size=12)},
    ))
    fetcher = FakeFetcher(blobs)
    progress: list[tuple] = []
    result = installer.install_files(
        dest, files, fetcher=fetcher, repo="google-research/harness2", sha="newsha",
        cancel=threading.Event(), progress=lambda *a: progress.append(a), workers=2,
        make_environment=False,
    )
    assert (dest / "harness2/a.py").read_bytes() == b"alpha\n"
    assert (dest / "harness2/b.py").read_bytes() == b"beta upstream\n"
    backups = list((dest / ".harness2-studio-backups").rglob("b.py"))
    assert backups and backups[0].read_bytes() == b"my own edit\n"
    marker = installer.read_marker(dest)
    assert marker is not None and marker.commit == "newsha"
    assert marker.files["harness2/a.py"].sha == files[0].sha
    assert result.backed_up == ["harness2/b.py"]
    assert any(p[0] == "download" for p in progress)


def test_latest_commit_parses_github_json() -> None:
    payload = json.dumps({
        "sha": "abc123",
        "commit": {"author": {"date": "2026-10-14T02:22:49Z"}, "message": "Fix arXiv link\n\nbody"},
    }).encode()
    info = installer.parse_commit(payload)
    assert info.sha == "abc123"
    assert info.date.startswith("2026-10-14")
    assert info.message == "Fix arXiv link"


def test_install_error_is_actionable_on_network_failure(tmp_path: Path) -> None:
    class Broken:
        def fetch(self, url: str, start: int = 0):
            raise OSError("getaddrinfo failed")
    with pytest.raises(installer.InstallError) as exc:
        installer.download_file(
            Broken(), ["https://raw.test/x/f.py"], tmp_path / "f.py", "a" * 40,
            cancel=threading.Event(), progress=lambda _n: None,
        )
    assert "network" in str(exc.value).lower()


def test_unmanaged_nonempty_destination_is_refused(tmp_path: Path) -> None:
    dest = tmp_path / "repo"
    dest.mkdir()
    (dest / "notes.txt").write_text("someone else's work")
    with pytest.raises(installer.InstallError):
        installer.assert_installable(dest)


def test_optional_package_groups_do_not_duplicate() -> None:
    packages = installer.extra_packages(("render", "bridge"))
    assert "openpyxl>=3.1,<4" in packages
    assert "litellm[proxy]==1.95.0" in packages
    assert len(packages) == len(set(packages))
    command = installer.pip_command("/repo/.venv/bin/python", ("render",))
    assert command[:4] == ["/repo/.venv/bin/python", "-m", "pip", "install"]
    assert "--no-input" in command
    with pytest.raises(installer.InstallError):
        installer.pip_command("/repo/.venv/bin/python", ())



def test_download_reports_a_filesystem_error_not_a_network_error(tmp_path: Path) -> None:
    data = b"payload\n"
    locked = tmp_path / "locked"
    locked.mkdir()
    target = locked / "nested" / "f.py"
    fetcher = FakeFetcher({"f.py": data})
    try:
        locked.chmod(0o500)
        with pytest.raises(installer.InstallError) as exc:
            installer.download_file(
                fetcher, ["https://raw.test/sha/f.py"], target, blob_sha(data),
                cancel=threading.Event(), progress=lambda _n: None,
            )
        message = str(exc.value)
        assert "Cannot write" in message or "Permission denied" in message
        assert "Network error" not in message
    finally:
        locked.chmod(0o700)


def test_filesystem_root_is_refused() -> None:
    with pytest.raises(installer.InstallError):
        installer.assert_installable(Path("/"))


def test_download_promotes_a_complete_part_without_network(tmp_path: Path) -> None:
    data = b"finished but never renamed\n"
    target = tmp_path / "f.py"
    installer.part_path(target).write_bytes(data)

    class Exploding:
        def fetch(self, url: str, start: int = 0):
            raise AssertionError("a complete part must not be re-downloaded")

    installer.download_file(
        Exploding(), ["https://raw.test/sha/f.py"], target, blob_sha(data),
        cancel=threading.Event(), progress=lambda _n: None,
    )
    assert target.read_bytes() == data
    assert not installer.part_path(target).exists()


def test_download_recovers_when_the_server_rejects_the_range(tmp_path: Path) -> None:
    data = b"real bytes\n"
    target = tmp_path / "f.py"
    installer.part_path(target).write_bytes(b"x" * 4)

    class RangeHostile:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def fetch(self, url: str, start: int = 0):
            self.calls.append(start)
            if start:
                return 416, b""
            return 200, data

    fetcher = RangeHostile()
    installer.download_file(
        fetcher, ["https://raw.test/sha/f.py"], target, blob_sha(data),
        cancel=threading.Event(), progress=lambda _n: None,
    )
    assert target.read_bytes() == data
    assert fetcher.calls == [4, 0]


def test_truncated_body_falls_through_to_the_next_mirror(tmp_path: Path) -> None:
    from http.client import IncompleteRead

    data = b"complete payload\n"
    target = tmp_path / "f.py"

    class Flaky:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def fetch(self, url: str, start: int = 0):
            self.urls.append(url)
            if url.endswith("/f.py") and "cdn" not in url:
                raise IncompleteRead(b"partial", 100)
            return 200, data

    fetcher = Flaky()
    installer.download_file(
        fetcher, ["https://raw.test/sha/f.py", "https://cdn.test/sha/f.py"], target,
        blob_sha(data), cancel=threading.Event(), progress=lambda _n: None,
    )
    assert target.read_bytes() == data
    assert len(fetcher.urls) == 2


def test_tree_rejects_windows_escape_and_reserved_names() -> None:
    for path in ("harness2/C:/Users/x/evil", "harness2/con.py", "harness2/aux", "harness2/x./y", "harness2/x /y"):
        with pytest.raises(installer.InstallError):
            installer.filter_tree([{"type": "blob", "path": path, "sha": "a" * 40, "size": 1}])


def test_cancel_stops_before_environment_work(tmp_path: Path) -> None:
    dest = tmp_path / "repo"
    files = [installer.RemoteFile("harness2/a.py", blob_sha(b"x\n"), 2)]
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(installer.InstallCancelled):
        installer.install_files(
            dest, files, fetcher=FakeFetcher({"a.py": b"x\n"}), sha="s",
            cancel=cancel, progress=None, workers=1, make_environment=False,
        )


def test_cancel_between_download_and_environment(tmp_path: Path) -> None:
    dest = tmp_path / "repo"
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(installer.InstallCancelled):
        installer.install_files(
            dest, [], fetcher=FakeFetcher({}), sha="s",
            cancel=cancel, progress=None, make_environment=True, python=sys.executable,
        )
    assert not (dest / ".venv").exists()


def test_streaming_resumes_after_a_dropped_connection(tmp_path: Path) -> None:
    from http.client import IncompleteRead

    data = b"0123456789" * 500
    target = tmp_path / "f.py"

    class Reader:
        def __init__(self, payload: bytes, drop_after: int | None = None) -> None:
            self.payload = payload
            self.pos = 0
            self.drop_after = drop_after
            self.closed = False

        def read(self, size: int = -1) -> bytes:
            if self.drop_after is not None and self.pos >= self.drop_after:
                raise IncompleteRead(self.payload[self.pos : self.pos + 10], 100)
            end = len(self.payload) if size < 0 else min(len(self.payload), self.pos + size)
            if self.drop_after is not None:
                end = min(end, self.drop_after)
            chunk = self.payload[self.pos : end]
            self.pos = end
            return chunk

        def close(self) -> None:
            self.closed = True

    class Streaming:
        def __init__(self) -> None:
            self.starts: list[int] = []

        def open(self, url: str, start: int = 0, cancel=None):
            self.starts.append(start)
            if len(self.starts) == 1:
                return 200, Reader(data, drop_after=1500)
            return 206, Reader(data[start:])

    fetcher = Streaming()
    installer.download_file(
        fetcher, ["https://raw.test/sha/f.py", "https://cdn.test/sha/f.py"], target,
        blob_sha(data), cancel=threading.Event(), progress=lambda _n: None,
    )
    assert target.read_bytes() == data
    assert fetcher.starts == [0, 1500]
    assert not installer.part_path(target).exists()


def test_clean_eof_short_body_keeps_the_part_for_resume(tmp_path: Path) -> None:
    data = b"x" * 4000
    target = tmp_path / "f.py"

    class Reader:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload
            self.pos = 0

        def read(self, size: int = -1) -> bytes:
            chunk = self.payload[self.pos : self.pos + size]
            self.pos += len(chunk)
            return chunk

        def close(self) -> None:
            pass

    class ShortHostile:
        def open(self, url: str, start: int = 0, cancel=None):
            return 200, Reader(data[:600])

    with pytest.raises(installer.InstallError) as exc:
        installer.download_file(
            ShortHostile(), ["https://raw.test/sha/f.py", "https://cdn.test/sha/f.py"],
            target, blob_sha(data), cancel=threading.Event(), progress=lambda _n: None,
            expected_size=len(data),
        )
    assert "short body" in str(exc.value)
    part = installer.part_path(target)
    assert part.is_file() and part.stat().st_size == 600
    assert not target.exists()
