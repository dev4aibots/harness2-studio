# Sources

This pack is an original synthesis. No source text was copied verbatim; the repositories below
supplied structure, failure modes and operating rules that were rewritten for the Harness² surface
and its 24k always-on budget.

## Consulted

| Source | License | What it contributed |
|---|---|---|
| [anomalyco/opencode](https://github.com/anomalyco/opencode) | MIT | The substrate's own agent prompt: pragmatic stance, smallest-change preference, persistence to end of task, editing constraints, defence against reverting another agent's work. Its V1 plugin hook (`tool.execute.before`) shaped C8. |
| [openai/codex](https://github.com/openai/codex) CLI system prompt | Apache-2.0 | Planning discipline, preambles that group actions instead of narrating each call, task-execution order, final-answer structure. |
| [Anthropic Claude Code 2.0](https://github.com/anthropics/claude-code) system prompt (archived copy in `x1xhlol/system-prompts-and-models-of-ai-tools`) | Anthropic terms | Tone and professional objectivity, task management with a todo list, tool-usage policy, code references as `path:line`. The archive is a third-party mirror; treat it as reference, not redistribution. |
| [anthropics/skills](https://github.com/anthropics/skills) | MIT | `SKILL.md` frontmatter contract: `name` must match the directory, `description` is the trigger and carries the "use when" clause. Directly enforced by Harness²'s validator. |
| [openai/openai-guardrails-python](https://github.com/openai/openai-guardrails-python) | MIT | The tripwire model: a guardrail blocks an action and raises, rather than warning and continuing. C2 and C8 use that shape. |
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | Apache-2.0 | Single-pass, ADD-only memory extraction: accumulate facts, do not rewrite history on every pass. C3 adopts append-first; the 120-line cap is ours, because a file needs compaction where a vector store does not. |
| [letta-ai/letta](https://github.com/letta-ai/letta) | Apache-2.0 | Self-editing memory blocks with an explicit budget, and the idea that memory is read at task start and edited at task end. |

Also checked for existence and scope, but not used as a source of text: NVIDIA/NeMo-Guardrails,
meta-llama/PurpleLlama, wshobson/agents, VoltAgent/awesome-claude-code-subagents,
obra/superpowers. Their patterns are already represented by the sources above.

## What is ours

- The five-phase loop and its exit criteria.
- The evidence rule ("a zero exit code from the wrong command proves nothing").
- The 120-line memory format with `FACT`/`LESSON` lines and compaction rules.
- The tool decision table and the two-null-results rule.
- The four subagent roles, their output contracts, and the "no finding without an exploit path"
  rule.
- `repo_map.py`, `check_gates.py`, `summarize.py`, and `deny-guard.ts`.

## Licensing

The pack is MIT, like the rest of this repository. The sources above remain under their own
licenses; nothing from them is redistributed here.
