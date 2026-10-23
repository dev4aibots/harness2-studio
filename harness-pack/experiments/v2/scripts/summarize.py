#!/usr/bin/env python3
"""Summarise a large file by structure instead of reading it into context.

Prints size, headings, definitions, imports, and TODO markers, capped by --lines.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
DEFINITION = re.compile(
    r"^(?:async\s+)?(?:def|class|function|func|fn|struct|interface|enum)\s+([A-Za-z_]\w*)"
)
IMPORT = re.compile(r"^(?:import|from|require|use)\s+\S+")
MARKER = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")


def main() -> int:
    parser = argparse.ArgumentParser(description="Structural summary of a file.")
    parser.add_argument("path", help="file to summarise")
    parser.add_argument("--lines", type=int, default=60, help="output line cap")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_file():
        print(f"summarize: not a file: {path}")
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    out: list[str] = [f"# {path}  ({len(lines)} lines, {len(text)} chars)"]

    headings = [(len(m.group(1)), m.group(2).strip()) for m in map(HEADING.match, lines) if m]
    for level, title in headings[:20]:
        out.append(f"{'  ' * (level - 1)}- {title}")

    defs = [f"  {i:>5} {m.group(1)}" for i, m in enumerate(map(DEFINITION.match, lines), 1) if m]
    if defs:
        out.append(f"## definitions ({len(defs)})")
        out.extend(defs[:30])

    imports = [line.strip() for line in lines if IMPORT.match(line)]
    if imports:
        out.append(f"## imports ({len(imports)})")
        out.extend(f"  {line}" for line in imports[:15])

    markers = [f"  {i:>5} {line.strip()[:100]}" for i, line in enumerate(lines, 1) if MARKER.search(line)]
    if markers:
        out.append(f"## markers ({len(markers)})")
        out.extend(markers[:15])

    print("\n".join(out[: args.lines]))
    if len(out) > args.lines:
        print(f"... {len(out) - args.lines} more lines; raise --lines to see them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
