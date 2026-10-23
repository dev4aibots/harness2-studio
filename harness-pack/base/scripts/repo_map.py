#!/usr/bin/env python3
"""Print a compact map of a repository: layout, key files, and a symbol outline.

Read-only and dependency-free. Use it before reading individual files so the first
pass over an unfamiliar codebase costs one tool call instead of twenty.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", "target",
    ".next", "coverage", ".idea", ".gradle", "vendor",
}
KEY_FILES = {
    "README.md", "README", "pyproject.toml", "setup.py", "package.json", "go.mod",
    "Cargo.toml", "Makefile", "justfile", "Dockerfile", "docker-compose.yml",
    "tsconfig.json", "AGENTS.md", "CLAUDE.md",
}

SYMBOL_PATTERNS = (
    re.compile(r"^(?:async\s+)?def\s+([A-Za-z_]\w*)"),
    re.compile(r"^class\s+([A-Za-z_]\w*)"),
    re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)"),
    re.compile(r"^(?:export\s+)?(?:const|let)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\("),
    re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"),
    re.compile(r"^(?:pub\s+)?(?:struct|enum|trait|fn)\s+([A-Za-z_]\w*)"),
    re.compile(r"^(?:public|private|protected)?\s*(?:static\s+)?(?:class|interface|enum)\s+([A-Za-z_]\w*)"),
)

SOURCE_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb",
    ".c", ".h", ".cc", ".cpp", ".cs", ".swift", ".php", ".scala",
}


def walk(root: Path, max_files: int) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(out) >= max_files:
            break
        if not path.is_file():
            continue
        if SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        out.append(path)
    return out


def outline(path: Path, limit: int) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    hits: list[str] = []
    for number, line in enumerate(lines, 1):
        for pattern in SYMBOL_PATTERNS:
            match = pattern.match(line)
            if match:
                hits.append(f"    {number:>5} {match.group(1)}")
                break
        if len(hits) >= limit:
            hits.append("    ...")
            break
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Map a repository layout and symbols.")
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--max-files", type=int, default=400, help="file cap for the walk")
    parser.add_argument("--per-file", type=int, default=25, help="symbols shown per file")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"repo_map: not a directory: {root}")
        return 2

    files = walk(root, args.max_files)
    rel = [p.relative_to(root) for p in files]

    print(f"# {root.name}  ({len(files)} files)")
    key = sorted(str(r) for r in rel if r.name in KEY_FILES or r.parent == Path("."))
    for name in key[:20]:
        print(f"  {name}")

    source = [p for p in files if p.suffix in SOURCE_SUFFIXES]
    print(f"\n# outline  ({len(source)} source files)")
    for path in source[:40]:
        hits = outline(path, args.per_file)
        if hits:
            print(f"  {path.relative_to(root)}")
            print("\n".join(hits))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
