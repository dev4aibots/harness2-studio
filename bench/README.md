# Bench: does the harness actually help?

A controlled A/B. One loop, one tool set, one model, six tasks. The only variable is the system
prompt:

- **baseline** = Harness²'s own v0 harness, which is empty. The model gets the tool brief and nothing
  else.
- **ours** = the C1–C8 pack in [`../harness-pack/base`](../harness-pack/base).

Results: [RESULTS.md](RESULTS.md). Published Opus 5.5 numbers and why they are not directly
comparable: [OPUS-BASELINE.md](OPUS-BASELINE.md).

## Method

1. **Tasks** come from a real repository with a real test suite. `tasks.py` applies one semantic
   mutation per task, runs the suite, and keeps the mutation only if it turns at least one test red.
   Six mutations survived; the rest were dropped rather than shipped as no-ops.
2. **Grading** restores `tests/` from a pristine snapshot before running the suite, so editing tests
   cannot produce a pass. This is the anti-cheat that matters: without it, an agent that deletes the
   failing test scores 100%.
3. **The sandbox** allows a read/test command whitelist, 20 turns, 60 seconds per command, and no
   network. `rm`, `git`, `pip` and redirection are refused.
4. **Determinism**: temperature 0. Free-tier models still vary, which is why k=2 and pass@2 are
   reported next to pass@1.

## Reproduce

```bash
python3 bench/tasks.py                       # rebuild the six single-bug task workspaces
python3 bench/make_hard.py                   # compose the three multi-bug tasks
BENCH_PROVIDER=nvidia \
  python3 bench/run_eval.py --model nvidia/nemotron-3-ultra-550b-a55b --harness baseline --k 2
BENCH_PROVIDER=nvidia \
  python3 bench/run_eval.py --model nvidia/nemotron-3-ultra-550b-a55b --harness ours --k 2
python3 bench/report.py                      # writes RESULTS.md
```

Providers supported in `agent.py`: `nvidia`, `gemini`, `openrouter`. The provider is chosen with
`BENCH_PROVIDER`; keys come from the environment.

## Files

| File | Role |
|---|---|
| `agent.py` | the loop: provider call, tool execution, sandbox, turn budget |
| `tasks.py` | snapshot, mutation, verification, grading |
| `run_eval.py` | arm runner, spend cap, JSONL results |
| `report.py` | RESULTS.md from the JSONL |
| `results.jsonl` | one row per rollout, including cost and token counts |
| `tasks/<id>/` | the mutated workspace and its `TASK.json` manifest |

## Limits, stated up front

- **Six tasks.** One task is 17 points of pass@1. The direction is the result; the magnitude is
  noisy.
- **One model.** This measures one model's response to the harness, not a general law.
- **Empty baseline.** The control answers "does harness content help at all", not "is this better
  than a strong competing harness". A second arm against a mature third-party prompt is the obvious
  next experiment.
- **Mutation tasks.** These are debugging tasks: reproduce, locate, fix, verify. They do not test
  feature design or long-horizon planning.
- **No Opus arm.** Opus 5.5 was not run here. The OpenRouter balance was $0.00 and the local
  Anthropic endpoint does not serve it, so any Opus comparison in this repository is against
  published numbers, clearly labelled as such.
