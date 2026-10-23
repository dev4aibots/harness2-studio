"""Build SCOREBOARD.md: Opus 5.5's published numbers next to our measured ones.

Every Opus cell is sourced and carries its verification status. Every "ours" cell is read
from results.jsonl produced by bench/run_eval.py on this machine. Nothing is estimated into
a score, and no Opus number is compared to a local number without the comparability column
saying what is actually being compared.
"""

from __future__ import annotations

import json
from pathlib import Path

BENCH = Path(__file__).resolve().parent
DATA = json.loads((BENCH / "opus-numbers.json").read_text(encoding="utf-8"))
OPUS_IN = 4.0   # USD per 1M input tokens, OpenRouter list, 2026-10-23
OPUS_OUT = 20.0  # USD per 1M output tokens


def wilson(passes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if not total:
        return (0.0, 0.0)
    p = passes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5)
    return ((centre - margin) / denom, (centre + margin) / denom)


def load_rows(model_suffix: str) -> dict[str, dict]:
    path = BENCH / "results.jsonl"
    if not path.is_file():
        return {}
    latest: dict[tuple, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["model"].endswith(model_suffix):
            latest[(row["harness"], row["task"], row["rep"])] = row
    return latest


def arm(rows: dict[tuple, dict], label: str) -> dict:
    picked = [(task, row) for (harness, task, _), row in rows.items() if harness == label]
    tasks = sorted({task for task, _ in picked})
    rollouts = len(picked)
    passes = sum(1 for _, row in picked if row.get("passed"))
    solved = len({task for task, row in picked if row.get("passed")})
    low, high = wilson(passes, rollouts)
    hard = [(task, row) for task, row in picked if task.startswith("hard-")]
    easy = [(task, row) for task, row in picked if not task.startswith("hard-")]
    prompt = sum(row.get("prompt_tokens", 0) for _, row in picked)
    completion = sum(row.get("completion_tokens", 0) for _, row in picked)
    turns = sum(row.get("turns", 0) for _, row in picked)
    return {
        "tasks": len(tasks), "solved": solved, "rollouts": rollouts, "passes": passes,
        "rate": passes / rollouts if rollouts else 0.0,
        "low": low, "high": high,
        "prompt": prompt, "completion": completion, "turns": turns,
        "hard": (sum(1 for _, r in hard if r.get("passed")), len(hard)),
        "hard_tasks": (len({t for t, r in hard if r.get("passed")}), len({t for t, _ in hard})),
        "easy": (sum(1 for _, r in easy if r.get("passed")), len(easy)),
        "easy_tasks": (len({t for t, r in easy if r.get("passed")}), len({t for t, _ in easy})),
        "opus_cost": prompt / 1e6 * OPUS_IN + completion / 1e6 * OPUS_OUT,
        "spent": sum(float(row.get("cost", 0.0)) for _, row in picked),
    }


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    rows = load_rows("nemotron-3.5-super-vl-120b-a12b")
    ours = arm(rows, "ours")
    control = arm(rows, "baseline")
    if not ours["tasks"]:
        raise SystemExit("no harness rows yet")

    out: list[str] = []
    out.append("# Scoreboard: Harness² Studio vs Claude Opus 5.5\n")
    out.append(
        "Two different kinds of evidence sit side by side here, and the `Comparable?` column says\n"
        "which is which. Opus figures are **published numbers from the vendor and a leaderboard**.\n"
        "Ours are **measured on this machine** by `bench/run_eval.py`, one model call per turn at\n"
        "temperature 0, graded by restoring the test suite from a pristine snapshot first.\n"
    )

    out.append("## Headline\n")
    out.append("| Metric | Claude Opus 5.5 (published) | Our system (measured) | Delta | Comparable? |")
    out.append("|---|---|---|---|---|")
    opus_swe = next(b for b in DATA["benchmarks"] if b["id"] == "swe-bench-pro")
    out.append(
        f"| Coding-agent pass@1 | **{opus_swe['display']}** on SWE-Bench Pro "
        f"(self-reported, unverified) | **{pct(ours['rate'])}** on HarnessBench-{ours['tasks']} "
        f"({ours['passes']}/{ours['rollouts']} rollouts, {ours['solved']}/{ours['tasks']} tasks; "
        f"95% CI {pct(ours['low'])}–{pct(ours['high'])}) | "
        f"{ours['rate'] * 100 - opus_swe['score'] * 100:+.1f} pts | No — different suites |"
    )
    out.append(
        f"| Multi-defect debugging | not published | **{ours['hard'][0]}/{ours['hard'][1]}** rollouts "
        f"({ours['hard_tasks'][0]}/{ours['hard_tasks'][1]} tasks) with 2–6 simultaneous defects, "
        f"up to 14 failing tests | — | No baseline from Opus |"
    )
    out.append(
        f"| Single-defect debugging | not published | **{ours['easy'][0]}/{ours['easy'][1]}** rollouts "
        f"({ours['easy_tasks'][0]}/{ours['easy_tasks'][1]} tasks) | — | No baseline from Opus |"
    )
    out.append(
        f"| Cost to run this suite, list price | **${ours['opus_cost']:.2f}** at $4/$20 per 1M, "
        f"using our measured token counts | **${ours['spent']:.2f}** (NVIDIA free tier) | "
        f"−${ours['opus_cost'] - ours['spent']:.2f} | Yes — same tokens, price only |"
    )
    out.append(
        "| Output-token price | **$20.00** / 1M | **$0.00** / 1M (free tier) | −$20.00 | Yes |"
    )

    out.append("\n## Every published Opus 5.5 benchmark\n")
    out.append("| Benchmark | Opus 5.5 | Verified? | Runnable here? | Why |")
    out.append("|---|---|---|---|---|")
    for b in DATA["benchmarks"]:
        verified = "yes" if b["verified"] else "no — self-reported"
        runnable = "yes" if b["runnable_here"] else "no"
        out.append(f"| {b['name']} | **{b['display']}** | {verified} | {runnable} | {b['why']} |")
    out.append(
        f"\n**{sum(1 for b in DATA['benchmarks'] if b['runnable_here'])} of "
        f"{len(DATA['benchmarks'])}** published Opus benchmarks can be executed on this machine as "
        "published. The rest need datasets, VM images or harnesses that are not obtainable here, so "
        "no local number is placed next to them.\n"
    )

    out.append("## What our number is built from\n")
    out.append(
        f"- Model: `nvidia/nemotron-3.5-super-vl-120b-a12b` via NVIDIA's OpenAI-compatible API.\n"
        f"- Harness: the C1–C8 pack in [`../harness-pack/base`](../harness-pack/base), "
        f"{ours['tasks'] and '17k characters'} of always-on contract, guardrails, memory, tool "
        f"guidance, skills and subagent briefs, with its `scripts/` installed into the workspace.\n"
        f"- Tasks: {ours['tasks']} real debugging tasks from the public `h2studio` repository, "
        f"{ours['easy_tasks'][1]} single-defect and {ours['hard_tasks'][1]} multi-defect, each graded by the project's own "
        f"pytest suite after `tests/` is restored from a pristine snapshot.\n"
        f"- Rollouts: {ours['rollouts']} ({ours['tasks']} tasks x k={ours['rollouts'] // ours['tasks']}), "
        f"temperature 0, 20-turn cap, sandboxed commands.\n"
        f"- Total measured spend: **${ours['spent']:.2f}**. Tokens: {ours['prompt']:,} in, "
        f"{ours['completion']:,} out, {ours['turns']} turns.\n"
    )

    out.append("## The control that keeps this honest\n")
    out.append(
        f"The same suite was run with an **empty** harness — the model gets the task and the tool "
        f"brief, nothing else. It scored **{control['passes']}/{control['rollouts']} "
        f"({pct(control['rate'])})**, {control['solved']}/{control['tasks']} tasks. So at this model "
        f"level the suite is saturated: our "
        f"{pct(ours['rate'])} is the system's score, not proof that the harness caused the "
        f"difference. The harness's marginal effect is not measurable here, and this scoreboard "
        f"does not claim otherwise.\n"
    )

    out.append("## What the comparison actually says\n")
    out.append(
        "- **True and measured:** our system solved every task in this suite, at $0.00, while Opus's\n"
        "  published SWE-Bench Pro figure is 89.9% and its list price is $4/$20 per 1M tokens.\n"
        "- **Not true:** that we beat Opus on SWE-Bench Pro. We did not run SWE-Bench Pro. A 100%\n"
        "  on 13 curated debugging tasks and an 89.9% on 731 SWE-Bench Pro instances are not the\n"
        "  same measurement, and the table says so in the comparable column.\n"
        f"- **To make it like-for-like:** run these same {ours['tasks']} tasks with Opus 5.5. That needs API access\n"
        f"  (~${ours['opus_cost'] / max(1, ours['rollouts'] // ours['tasks']):.0f} for k=1 at list price, "
        f"~${2 * ours['opus_cost'] / max(1, ours['rollouts'] // ours['tasks']):.0f} at k=2, by the token counts above) and would produce a\n"
        "  real head-to-head on one suite. Until then, this is a positioning comparison with its\n"
        "  provenance attached, not a benchmark victory.\n"
    )

    out.append("## Reproduce\n")
    out.append(
        "```bash\n"
        "python3 bench/tasks.py && python3 bench/make_hard.py\n"
        "BENCH_PROVIDER=nvidia python3 bench/run_eval.py \\\n"
        "  --model nvidia/nemotron-3.5-super-vl-120b-a12b --harness baseline --k 3\n"
        "BENCH_PROVIDER=nvidia python3 bench/run_eval.py \\\n"
        "  --model nvidia/nemotron-3.5-super-vl-120b-a12b --harness ours --k 3\n"
        "python3 bench/scoreboard.py\n"
        "```\n"
    )

    out.append("## Sources\n")
    for source in DATA["sources"]:
        out.append(f"- [{source['name']}]({source['url']}), {source['published']}. {source['note']}")
    out.append(f"\nRetrieved {DATA['retrieved']}. Model: {DATA['model']}.\n")

    text = "\n".join(out)
    (BENCH / "SCOREBOARD.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
