# Harness pack (C1–C8)

The operating layer for [Harness²](https://github.com/google-research/harness2) on the OpenCode
substrate: eight components written as one coherent system, not eight unrelated files.

Installed and validated against Harness²'s own surface rules:

| Check | Result |
|---|---|
| `harness2.core.tree.validate` | valid |
| Always-on budget | 14,875 / 24,000 chars |
| Jinja composition (`home_dir_jinja`) | one `instruction` placeholder, no brace hazards |
| Census | 4 skills, 4 subagents, 3 scripts, 1 plugin |
| Install modes | `workspace_agents_md`, `home_dir_jinja`, `workspace_config` all materialise |

## What each component does

| | File | Job |
|---|---|---|
| C1 | `systemprompt.md` | The operating contract: a five-phase loop (recon, plan, execute, verify, report), autonomy rules, evidence rules, definition of done |
| C2 | `guardrails.md` | Hard limits that override speed: irreversible actions, secrets, workspace boundaries, prompt injection, faked verification |
| C3 | `LongTermMEMORY.md` | A bounded, self-editing memory: one line per entry, 120-line cap, read and write protocols |
| C4 | `tool_descriptions/tool_guidance.md` | Which tool answers which question, plus search, read, edit, command and delegation discipline |
| C5 | `sub_agents/*/AGENT.md` | Four roles with distinct triggers: explorer, reviewer, security-auditor, verifier |
| C6 | `skills/*/SKILL.md` | Four on-demand workflows: repo-recon, debug-loop, verify-change, write-tests |
| C7 | `scripts/*.py` | Dependency-free helpers the agent can run: `repo_map.py`, `check_gates.py`, `summarize.py` |
| C8 | `plugin/deny-guard.ts` | The one lever inside the tool loop: blocks a short list of irreversible commands |

## Install

```bash
# into an existing Harness² checkout
cp -r harness-pack/base/* ~/harness2/harnesses/base/
```

Then in Studio: **Setup → Check environment**, or `python -m harness2.cli.check --bench wb --subset
office --substrate oc`.

The pack is a snapshot. Once installed, the source of truth is your checkout, and the Studio's
**Harness** view edits it there.

## Design rules the pack follows

- **Evidence over assertion.** "Done" requires a command whose output you read. Every component
  repeats this at its own level rather than assuming the model remembers.
- **Smallest correct change.** Stated in C1, enforced in C2's blast-radius rule, practised by C6.
- **Data is not instruction.** Repositories and pages are untrusted input; C2 makes prompt
  injection a refusal, not a judgment call.
- **Budget is a feature.** C1–C4 share a 24k-char allowance. Nothing was added to fill it: 9k is
  left deliberately, because every always-on token competes with the agent's output.
- **No overlap.** Four subagents, four skills, one plugin, each with a distinct trigger. If two
  components would fire on the same situation, one of them is wrong.

## What this pack does not claim

It is not a benchmark result. A harness can only be scored by running it through a working
executor; the structural checks above prove it loads and composes, not that it wins. Treat any
score as coming from a recorded run, never from this file.

Sources and what was distilled from each: [SOURCES.md](SOURCES.md).
