# Opus 5.5: published numbers

Retrieved 2026-10-23. These are vendor and aggregator figures, not measurements taken on this
machine. Every row names its source; the verification status is stated because it changes how much
weight the number deserves.

## Anthropic's own launch numbers

Source: <https://www.anthropic.com/claude-opus-5-5> (published 2026-09-22). Anthropic states that
Opus 5.5 was run at max effort with adaptive thinking, with production safeguards enabled.

| Benchmark | Opus 5.5 | Fable 5.1 | Opus 5 | GPT-6 Astra |
|---|---|---|---|---|
| Terminal-Bench 4.0 | **66.4%** | 55.8% | 52.3% | 57.9% |
| FrontierCode v1.1 (Main) | **54.4%** | 50.3% | 48.0% | 53.3% |
| CursorBench 4.0 | **57.8%** | 51.8% | 46.6% | -- |
| GDPval-AA v2.1 (Elo) | **1846** | 1735 | 1708 | 1542 |
| AutomationBench | **40.0%** | 31.4% | 26.9% | 41.4% |
| Humanity's Last Exam (tools) | **67.7%** | 65.6% | 63.6% | 57.2% |
| Terminal-Bench-Science 0.1 | **58.7%** | 52.6% | 29.0% | 64.6% |
| OSWorld 2.1 | **81.8%** (partial) | 80.7% | 74.0% | -- |

Anthropic's own footnotes are part of the result: Terminal-Bench 4.0 carries a standard error of
+/-2.6 points, and the public leaderboard reports Opus 5 at 51.8% under a Claude Code harness while
Anthropic reproduces 52.3% in its own setup. Harness and setup move these numbers by more than the
gap between adjacent models.

## SWE-Bench Pro, aggregator leaderboard

Source: <https://llm-stats.com/benchmarks/swe-bench-pro> (last updated 2026-10-23). LLM Stats marks
this benchmark **unverified: 0 verified, 62 self-reported**. Treat the ordering as a vendor claim,
not an independent audit.

| # | Model | Score |
|---|---|---|
| 1 | Claude Opus 5.5 | **0.899** |
| 2 | Claude Sonnet 5.5 | 0.813 |
| 3 | Claude Fable 5 | 0.800 |
| 5 | Claude Opus 4.8 | 0.692 |
| 6 | Qwen3.8 Max | 0.677 |
| 7 | Beam 1.0 (open weights) | 0.661 |
| 9 | Claude Haiku 5.5 | 0.648 |
| 11 | GPT-5.6 Sol | 0.646 |
| 18 | GLM-5.2 | 0.621 |
| 20 | Muse Spark 1.1 | 0.615 |
| 25 | Kimi K2.6 | 0.586 |
| 42 | DeepSeek-V4-Pro-Max | 0.554 |
| 44 | Gemini 3.5 Flash | 0.551 |

The spread between the top self-reported row (0.899) and the top standardized public-set row
reported elsewhere (Meta's Muse Spark 1.1 at 61.5%, Scale's set) is roughly 28 points. Any claim of
the form "X beats Opus" has to say which of those two numbers it is comparing against.

## What Harness² itself measured

Source: the Harness² paper, arXiv [2610.14224](https://arxiv.org/abs/2610.14224). Gains are reported
for GLM-5 and Gemini 3.5 Flash against their own base harnesses, on the paper's three professional
benchmarks:

| Benchmark | Gain from one improvement step |
|---|---|
| WorkBuddy-Bench | up to **+11.5** points |
| JobBench | up to **+4.5** points |
| LAB | up to **+11.8** percentage points |

This is the only published evidence that a harness change of this kind moves scores at all. It does
not transfer to Opus by arithmetic: the paper's deltas are measured on other models, other tasks and
a different harness. Applying them to Opus's 89.9% would be a projection, not a result.

## What this means for "beat Opus 5.5"

Three different claims get confused, and only one is measurable with what is installed here:

1. **Same model, different harness.** Measurable, and reported in [RESULTS.md](RESULTS.md).
2. **A cheaper model with our harness vs Opus with its stock harness.** Needs Opus to run on the
   same tasks. The OpenRouter balance on this machine is $0.00 and the Anthropic endpoint is a local
   proxy that does not serve Opus, so this arm has not been run.
3. **Our harness vs Opus's published number on a public benchmark.** Not a measurement. Different
   tasks, different grader, different harness.

Claims 1 and 3 are what most "we beat Opus" posts actually report. This file keeps them apart.
