# Harness A/B: measured results

Same model, same tools, same loop, same tasks, temperature 0. The only variable is the system prompt: the Harness² v0 baseline (empty) versus the C1–C8 pack in `harness-pack/base`.

Filtered to models containing `super-vl`.

## Design

- Tasks: semantic mutations of a real Python repository, each with its own failing tests.
- Grading: the grader restores `tests/` from a pristine snapshot, then runs the suite. Editing tests cannot produce a pass.
- Rollouts: k varies by arm; the Runs column is the exact count. pass@k counts a task as solved if any attempt passed.
- Sandbox: commands limited to a read/test whitelist, 20 turns, 60 s per command.

## Target

The bar is Claude Opus 5.5's published SWE-Bench Pro score, **0.899**, read from the LLM
Stats leaderboard on 2026-10-23 (62 models, all self-reported, 0 independently verified).
It is a fixed number to climb toward, not an equivalence: this benchmark is 13 local
debugging tasks on one repository, not SWE-Bench Pro. Crossing the bar here means the
harness reached the target that was set for it, not that it matches Opus on real software
work. See [OPUS-BASELINE.md](OPUS-BASELINE.md) for the published numbers themselves.

## Summary

| Model | Harness | Runs | Passes | Pass@1 | 95% CI | Pass@k | Avg turns | Avg prompt tok | Avg completion tok |
|---|---|---|---|---|---|---|---|---|---|
| nvidia/nemotron-3.5-super-vl-120b-a12b | baseline | 13 | 13 | 100% | [77%, 100%] | 13/13 | 15.2 | 138,288 | 3,439 |
| nvidia/nemotron-3.5-super-vl-120b-a12b | ours | 39 | 39 | 100% | [91%, 100%] | 13/13 | 14.9 | 165,025 | 6,098 |

## Per task

| Task | baseline r1 | baseline r2 | ours r1 | ours r2 |
|---|---|---|---|---|
| blob-sha-length | pass | - | pass | pass |
| env-template-overwrite | pass | - | pass | pass |
| hard-all-six | pass | - | pass | pass |
| hard-cli-three | pass | - | pass | pass |
| hard-env-and-cli | pass | - | pass | pass |
| hard-installer-and-cli | pass | - | pass | pass |
| hard-installer-two | pass | - | pass | pass |
| hard-quartet | pass | - | pass | pass |
| hard-three-files | pass | - | pass | pass |
| include-everything | pass | - | pass | pass |
| models-dedupe-lost | pass | - | pass | pass |
| run-argv-drops-k | pass | - | pass | pass |
| summary-status-filter | pass | - | pass | pass |
## Delta

- **nvidia/nemotron-3.5-super-vl-120b-a12b**: pass@1 13/13 → 39/39 (+0 points); pass@2 13/13 → 13/13 (+0 points).
  Efficiency: 15.2 → 14.9 turns per task; 138,288 → 165,025 prompt tokens per rollout.

## By difficulty

| Model | Class | Baseline pass@2 | Harness pass@2 | Delta |
|---|---|---|---|---|
| nvidia/nemotron-3.5-super-vl-120b-a12b | single bug | 6/6 | 6/6 | +0 pts |
| nvidia/nemotron-3.5-super-vl-120b-a12b | multi bug | 7/7 | 7/7 | +0 pts |

## What this does and does not show

- It shows whether this harness helps **this model** on **these six tasks**. Six tasks is a small sample: one task is 17 points of pass@1, so treat the direction as the result and the magnitude as noisy.
- It does not show that the same harness helps Opus 5.5, and it is not comparable to Opus's published SWE-bench Pro score. See [OPUS-BASELINE.md](OPUS-BASELINE.md).
- The baseline is the benchmark's own v0: an empty harness. That is a fair control for 'does harness content help at all', not for 'is this better than a strong competing harness'.

