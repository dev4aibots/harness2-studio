"""Turn results.jsonl into RESULTS.md: pass rates, per-task matrix, and the limits."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parent


def wilson(passes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if not total:
        return (0.0, 0.0)
    p = passes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5)
    return ((centre - margin) / denom, (centre + margin) / denom)


def load() -> list[dict]:
    path = BENCH / "results.jsonl"
    if not path.is_file():
        raise SystemExit("bench/results.jsonl does not exist yet")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        rows.append(row)
    # A rerun supersedes an earlier attempt with the same key.
    deduped: dict[tuple, dict] = {}
    for row in rows:
        deduped[(row["model"], row["harness"], row["task"], row["rep"])] = row
    return list(deduped.values())


def main() -> int:
    rows = load()
    arms = defaultdict(list)
    for row in rows:
        arms[(row["model"], row["harness"])].append(row)

    tasks = sorted({r["task"] for r in rows})
    lines: list[str] = []
    lines.append("# Harness A/B: measured results\n")
    lines.append(
        "Same model, same tools, same loop, same tasks, temperature 0. The only variable is the "
        "system prompt: the Harness² v0 baseline (empty) versus the C1–C8 pack in "
        "`harness-pack/base`.\n"
    )
    lines.append("## Design\n")
    lines.append(
        "- Tasks: semantic mutations of a real Python repository, each with its own failing tests.\n"
        "- Grading: the grader restores `tests/` from a pristine snapshot, then runs the suite. "
        "Editing tests cannot produce a pass.\n"
        "- Rollouts: k=2 per task per arm; pass@2 counts a task as solved if either attempt passed.\n"
        "- Sandbox: commands limited to a read/test whitelist, 20 turns, 60 s per command.\n"
    )

    lines.append("## Target\n")
    lines.append(
        "The bar is Claude Opus 5.5's published SWE-Bench Pro score, **0.899**, read from the LLM\n"
        "Stats leaderboard on 2026-10-23 (62 models, all self-reported, 0 independently verified).\n"
        "It is a fixed number to climb toward, not an equivalence: this benchmark is 13 local\n"
        "debugging tasks on one repository, not SWE-Bench Pro. Crossing the bar here means the\n"
        "harness reached the target that was set for it, not that it matches Opus on real software\n"
        "work. See [OPUS-BASELINE.md](OPUS-BASELINE.md) for the published numbers themselves.\n"
    )

    lines.append("## Summary\n")
    lines.append("| Model | Harness | Runs | Passes | Pass@1 | 95% CI | Pass@2 | Avg turns | Avg prompt tok | Avg completion tok |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    summary = {}
    for (model, harness), group in sorted(arms.items()):
        runs = len(group)
        passes = sum(1 for r in group if r.get("passed"))
        per_task: dict[str, list[bool]] = defaultdict(list)
        for r in group:
            per_task[r["task"]].append(bool(r.get("passed")))
        solved = sum(1 for v in per_task.values() if any(v))
        avg_turns = sum(r.get("turns", 0) for r in group) / runs if runs else 0
        avg_in = sum(r.get("prompt_tokens", 0) for r in group) / runs if runs else 0
        avg_out = sum(r.get("completion_tokens", 0) for r in group) / runs if runs else 0
        summary[(model, harness)] = (passes, runs, solved, len(per_task))
        low, high = wilson(passes, runs)
        lines.append(
            f"| {model} | {harness} | {runs} | {passes} | {passes / runs:.0%} | "
            f"[{low:.0%}, {high:.0%}] | {solved}/{len(per_task)} | {avg_turns:.1f} | "
            f"{avg_in:,.0f} | {avg_out:,.0f} |"
        )

    lines.append("\n## Per task\n")
    harnesses = sorted({h for _, h in arms})
    header = "| Task | " + " | ".join(f"{h} r{i}" for h in harnesses for i in (1, 2)) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (1 + 2 * len(harnesses)))
    cell = {(r["harness"], r["task"], r["rep"]): ("pass" if r.get("passed") else ("err" if r.get("error") else "fail"))
            for r in rows}
    for task in tasks:
        values = [cell.get((h, task, i), "-") for h in harnesses for i in (1, 2)]
        lines.append(f"| {task} | " + " | ".join(values) + " |")

    lines.append("## Delta\n")
    models = sorted({m for m, _ in arms})
    for model in models:
        if (model, "baseline") in summary and (model, "ours") in summary:
            b = summary[(model, "baseline")]
            o = summary[(model, "ours")]
            dp = (o[0] / o[1] - b[0] / b[1]) * 100
            ds = (o[2] / o[3] - b[2] / b[3]) * 100
            bg = arms[(model, "baseline")]
            og = arms[(model, "ours")]
            bt = sum(r.get("turns", 0) for r in bg) / len(bg)
            ot = sum(r.get("turns", 0) for r in og) / len(og)
            bi = sum(r.get("prompt_tokens", 0) for r in bg) / len(bg)
            oi = sum(r.get("prompt_tokens", 0) for r in og) / len(og)
            lines.append(
                f"- **{model}**: pass@1 {b[0]}/{b[1]} → {o[0]}/{o[1]} "
                f"({dp:+.0f} points); pass@2 {b[2]}/{b[3]} → {o[2]}/{o[3]} ({ds:+.0f} points)."
            )
            lines.append(
                f"  Efficiency: {bt:.1f} → {ot:.1f} turns per task; "
                f"{bi:,.0f} → {oi:,.0f} prompt tokens per rollout."
            )

    lines.append("\n## By difficulty\n")
    lines.append("| Model | Class | Baseline pass@2 | Harness pass@2 | Delta |")
    lines.append("|---|---|---|---|---|")
    for model in models:
        for label, pred in (("single bug", lambda t: not t.startswith("hard-")),
                            ("multi bug", lambda t: t.startswith("hard-"))):
            cells = {}
            for arm in ("baseline", "ours"):
                group = [r for r in arms.get((model, arm), []) if pred(r["task"])]
                per: dict[str, list[bool]] = defaultdict(list)
                for r in group:
                    per[r["task"]].append(bool(r.get("passed")))
                cells[arm] = (sum(1 for v in per.values() if any(v)), len(per))
            b, o = cells["baseline"], cells["ours"]
            if not b[1] or not o[1]:
                continue
            delta = (o[0] / o[1] - b[0] / b[1]) * 100
            lines.append(f"| {model} | {label} | {b[0]}/{b[1]} | {o[0]}/{o[1]} | {delta:+.0f} pts |")

    lines.append("\n## What this does and does not show\n")
    lines.append(
        "- It shows whether this harness helps **this model** on **these six tasks**. "
        "Six tasks is a small sample: one task is 17 points of pass@1, so treat the direction as "
        "the result and the magnitude as noisy.\n"
        "- It does not show that the same harness helps Opus 5.5, and it is not comparable to "
        "Opus's published SWE-bench Pro score. See [OPUS-BASELINE.md](OPUS-BASELINE.md).\n"
        "- The baseline is the benchmark's own v0: an empty harness. That is a fair control for "
        "'does harness content help at all', not for 'is this better than a strong competing "
        "harness'.\n"
    )

    out = BENCH / "RESULTS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
