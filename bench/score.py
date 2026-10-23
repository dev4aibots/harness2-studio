"""Score an arm against the web-fixed target and show exactly where it falls short."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BENCH = Path(__file__).resolve().parent
TARGET = 0.899  # Claude Opus 5.5, SWE-Bench Pro, self-reported leaderboard, 2026-10-23


def wilson(passes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a binomial rate. With 13 tasks the interval is wide; say so."""
    if total == 0:
        return (0.0, 0.0)
    p = passes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5)
    return ((centre - margin) / denom, (centre + margin) / denom)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--harness", default="ours")
    parser.add_argument("--k", type=int, default=0, help="keep only the newest k reps")
    args = parser.parse_args()

    rows = []
    for line in (BENCH / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["model"] == args.model and row["harness"] == args.harness:
            rows.append(row)
    latest: dict[str, dict] = {}
    for row in rows:
        latest[row["task"]] = row  # later records supersede earlier ones

    tasks = sorted(latest)
    if not tasks:
        print("no rows for that model/harness")
        return 2
    passes = sum(1 for r in latest.values() if r.get("passed"))
    rate = passes / len(tasks)
    print(f"{args.model} / {args.harness}: {passes}/{len(tasks)} = {rate:.1%}")
    low, high = wilson(passes, len(tasks))
    print(f"target (Opus 5.5, SWE-Bench Pro, self-reported): {TARGET:.1%}   gap: {rate - TARGET:+.1%}")
    print(f"95% interval: [{low:.1%}, {high:.1%}]   lowers bound clears target: {low >= TARGET}")
    print()
    for task in tasks:
        row = latest[task]
        mark = "pass" if row.get("passed") else ("err " if row.get("error") else "FAIL")
        print(f"  {mark}  {task:<26} turns={row.get('turns', '-'):<3} {row.get('tail', '')[:90]}")

    failed = [t for t in tasks if not latest[t].get("passed")]
    if failed:
        print("\nFailed transcript excerpts:\n")
        for task in failed:
            row = latest[task]
            print(f"== {task}")
            for step in row.get("transcript", [])[-6:]:
                if "tool" in step:
                    print(f"  [{step['tool']}] {str(step.get('args'))[:120]}")
                else:
                    print(f"  says: {str(step.get('text'))[:160]}")
            print()
    return 0 if rate >= TARGET else 1


if __name__ == "__main__":
    raise SystemExit(main())
