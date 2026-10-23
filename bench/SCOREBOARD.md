# Scoreboard: Harness² Studio vs Claude Opus 5.5

Two different kinds of evidence sit side by side here, and the `Comparable?` column says
which is which. Opus figures are **published numbers from the vendor and a leaderboard**.
Ours are **measured on this machine** by `bench/run_eval.py`, one model call per turn at
temperature 0, graded by restoring the test suite from a pristine snapshot first.

## Headline

| Metric | Claude Opus 5.5 (published) | Our system (measured) | Delta | Comparable? |
|---|---|---|---|---|
| Coding-agent pass@1 | **89.9%** on SWE-Bench Pro (self-reported, unverified) | **100.0%** on HarnessBench-13 (39/39 rollouts, 13/13 tasks; 95% CI 91.0%–100.0%) | +10.1 pts | No — different suites |
| Multi-defect debugging | not published | **21/21** rollouts (7/7 tasks) with 2–6 simultaneous defects, up to 14 failing tests | — | No baseline from Opus |
| Single-defect debugging | not published | **18/18** rollouts (6/6 tasks) | — | No baseline from Opus |
| Cost to run this suite, list price | **$30.50** at $4/$20 per 1M, using our measured token counts | **$0.00** (NVIDIA free tier) | −$30.50 | Yes — same tokens, price only |
| Output-token price | **$20.00** / 1M | **$0.00** / 1M (free tier) | −$20.00 | Yes |

## Every published Opus 5.5 benchmark

| Benchmark | Opus 5.5 | Verified? | Runnable here? | Why |
|---|---|---|---|---|
| SWE-Bench Pro | **89.9%** | no — self-reported | no | Instance images and the 731-instance dataset are not obtainable from this machine (Hugging Face throttled to ~141 B/s, codeload timed out). |
| Terminal-Bench 4.0 | **66.4%** | no — self-reported | no | Every task is a Docker image pulled from a registry; the pull budget on this connection exceeds the run budget. |
| Terminal-Bench-Science 0.1 | **58.7%** | no — self-reported | no | Same registry-bound task images as Terminal-Bench. |
| FrontierCode v1.1 (Main) | **54.4%** | no — self-reported | no | Internal benchmark; no public dataset or harness. |
| CursorBench 4.0 | **57.8%** | no — self-reported | no | Proprietary to Cursor; no public instances. |
| AutomationBench | **40.0%** | no — self-reported | no | Benchmark harness and task environment are not published. |
| GDPval-AA v2.1 | **1846 Elo** | no — self-reported | no | Occupational-task evaluation graded by human experts; not machine-runnable. |
| Humanity's Last Exam (with tools) | **67.7%** | no — self-reported | no | Gated dataset; the public split has been contaminated and is not a valid substitute. |
| OSWorld 2.1 | **81.8% (partial)** | no — self-reported | no | Requires VM images and a desktop-control harness. |
| SWE-bench Multilingual | **93.9%** | no — self-reported | no | Dataset download is throttled; repositories span nine languages with per-language toolchains. |

**0 of 10** published Opus benchmarks can be executed on this machine as published. The rest need datasets, VM images or harnesses that are not obtainable here, so no local number is placed next to them.

## What our number is built from

- Model: `nvidia/nemotron-3.5-super-vl-120b-a12b` via NVIDIA's OpenAI-compatible API.
- Harness: the C1–C8 pack in [`../harness-pack/base`](../harness-pack/base), 17k characters of always-on contract, guardrails, memory, tool guidance, skills and subagent briefs, with its `scripts/` installed into the workspace.
- Tasks: 13 real debugging tasks from the public `h2studio` repository, 6 single-defect and 7 multi-defect, each graded by the project's own pytest suite after `tests/` is restored from a pristine snapshot.
- Rollouts: 39 (13 tasks x k=3), temperature 0, 20-turn cap, sandboxed commands.
- Total measured spend: **$0.00**. Tokens: 6,435,957 in, 237,811 out, 582 turns.

## The control that keeps this honest

The same suite was run with an **empty** harness — the model gets the task and the tool brief, nothing else. It scored **13/13 (100.0%)**, 13/13 tasks. So at this model level the suite is saturated: our 100.0% is the system's score, not proof that the harness caused the difference. The harness's marginal effect is not measurable here, and this scoreboard does not claim otherwise.

## What the comparison actually says

- **True and measured:** our system solved every task in this suite, at $0.00, while Opus's
  published SWE-Bench Pro figure is 89.9% and its list price is $4/$20 per 1M tokens.
- **Not true:** that we beat Opus on SWE-Bench Pro. We did not run SWE-Bench Pro. A 100%
  on 13 curated debugging tasks and an 89.9% on 731 SWE-Bench Pro instances are not the
  same measurement, and the table says so in the comparable column.
- **To make it like-for-like:** run these same 13 tasks with Opus 5.5. That needs API access
  (~$10 for k=1 at list price, ~$20 at k=2, by the token counts above) and would produce a
  real head-to-head on one suite. Until then, this is a positioning comparison with its
  provenance attached, not a benchmark victory.

## Reproduce

```bash
python3 bench/tasks.py && python3 bench/make_hard.py
BENCH_PROVIDER=nvidia python3 bench/run_eval.py \
  --model nvidia/nemotron-3.5-super-vl-120b-a12b --harness baseline --k 3
BENCH_PROVIDER=nvidia python3 bench/run_eval.py \
  --model nvidia/nemotron-3.5-super-vl-120b-a12b --harness ours --k 3
python3 bench/scoreboard.py
```

## Sources

- [Anthropic: Claude Opus 5.5 launch page](https://www.anthropic.com/claude-opus-5-5), 2026-09-22. Vendor run: max effort, adaptive thinking, production safeguards. Anthropic reports a +/-2.6 point standard error on Terminal-Bench 4.0 and notes that the public leaderboard's Claude Code harness scores Opus 5 at 51.8% where its own setup reproduces 52.3%.
- [LLM Stats: SWE-Bench Pro leaderboard](https://llm-stats.com/benchmarks/swe-bench-pro), 2026-10-23. 62 models, 0 independently verified, 62 self-reported. Scale's standardized public set tops out near 61.5%, roughly 28 points below the self-reported top row.

Retrieved 2026-10-23. Model: Claude Opus 5.5.
