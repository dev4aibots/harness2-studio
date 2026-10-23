"""Run the harness A/B: same model, same tools, same loop, different system prompt."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent
import tasks as tasklib

BENCH = Path(__file__).resolve().parent
PACK = BENCH.parent / "harness-pack" / "base"

TOOL_BRIEF = """You work in a sandboxed copy of a Python repository. Tools:

- list_files(path): list files
- read_file(path, start, end): read a file, 1-based line numbers in the output
- write_file(path, content): overwrite a file
- run_command(command): run one command in the workspace (python, pytest, grep, cat, ls, ...
  are allowed; redirection and chaining are not)
- grep(pattern, path): search file contents
- finish(): declare the work complete

The workspace root is the repository root. Tests run with `python -m pytest -q`.
"""

BASELINE = TOOL_BRIEF


def ours() -> str:
    parts = []
    for rel in ("systemprompt.md", "guardrails.md", "LongTermMEMORY.md", "tool_descriptions/tool_guidance.md"):
        path = PACK / rel
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    skills = sorted((PACK / "skills").glob("*/SKILL.md"))
    if skills:
        index = []
        for path in skills:
            head = path.read_text(encoding="utf-8")[:400]
            desc = next((ln[12:].strip() for ln in head.splitlines() if ln.startswith("description:")), "")
            index.append(f"- {path.parent.name}: {desc}")
        parts.append("# AVAILABLE SKILLS\nRead the matching SKILL.md before starting:\n" + "\n".join(index))
    subs = sorted((PACK / "sub_agents").glob("*/AGENT.md"))
    if subs:
        parts.append("# AVAILABLE SUBAGENTS\nDeeper work can follow these briefs:\n" + "\n".join(
            f"- {p.parent.name}: {next((ln[12:].strip() for ln in p.read_text(encoding='utf-8')[:400].splitlines() if ln.startswith('description:')), '')}"
            for p in subs
        ))
    parts.append(TOOL_BRIEF)
    return "\n\n---\n\n".join(parts)


def instruction(task: dict) -> str:
    tests = "\n".join(f"  {t}" for t in task["failed_tests"])
    return (
        "The test suite fails. These tests are red:\n\n"
        f"{tests}\n\n"
        f"Reported symptom: {task['issue']}\n\n"
        "Fix the implementation so the whole suite passes. Do not edit anything under tests/; "
        "the grader restores that directory before it runs. Use `python -m pytest -q` to check. "
        "Call finish when it is green.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--harness", choices=("baseline", "ours"), required=True)
    parser.add_argument("--k", type=int, default=1)
    parser.add_argument("--tasks", default="", help="comma-separated task ids")
    parser.add_argument("--cap", type=float, default=25.0, help="hard spend cap in USD")
    parser.add_argument("--out", default=str(BENCH / "results.jsonl"))
    parser.add_argument("--max-turns", type=int, default=agent.MAX_TURNS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    system = ours() if args.harness == "ours" else BASELINE
    if args.dry_run:
        print(f"{args.harness}: {len(system)} chars")
        return 0

    provider = os.environ.get("BENCH_PROVIDER", "nvidia")
    if provider == "nvidia":
        key = os.environ.get("NVIDIA_API_KEY", "")
    elif provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
    else:
        key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise SystemExit(f"no API key for provider {provider}")

    pristine = BENCH / "tasks" / "_pristine"
    chosen = [t.strip() for t in args.tasks.split(",") if t.strip()]
    task_dirs = sorted(p for p in (BENCH / "tasks").iterdir() if p.is_dir() and p.name != "_pristine")
    if chosen:
        task_dirs = [p for p in task_dirs if p.name in chosen]

    spent = 0.0
    out = Path(args.out)
    with out.open("a", encoding="utf-8") as sink:
        for task_dir in task_dirs:
            manifest = json.loads((task_dir / "TASK.json").read_text())
            for rep in range(1, args.k + 1):
                if spent >= args.cap:
                    print(f"cap reached: ${spent:.2f} >= ${args.cap:.2f}; stopping")
                    return 3
                work = BENCH / "work" / f"{manifest['id']}-{args.harness}-{rep}"
                tasklib.snapshot(work)
                started = time.time()
                try:
                    run = agent.run_agent(
                        task_id=manifest["id"],
                        workspace=work,
                        instruction=instruction(manifest),
                        system_prompt=system,
                        model=args.model,
                        key=key,
                        max_turns=args.max_turns,
                    )
                except Exception as exc:  # noqa: BLE001 - a failed call is a failed rollout
                    record = {
                        "task": manifest["id"], "harness": args.harness, "model": args.model,
                        "rep": rep, "passed": False, "error": str(exc)[:500], "cost": 0.0,
                    }
                    sink.write(json.dumps(record) + "\n")
                    print(f"{manifest['id']} rep{rep}: ERROR {str(exc)[:120]}")
                    continue
                passed, tail = tasklib.grade(work, pristine)
                spent += run.usage.cost
                record = {
                    "task": manifest["id"], "harness": args.harness, "model": args.model,
                    "rep": rep, "passed": passed, "turns": run.turns,
                    "tool_calls": run.tool_calls, "cost": round(run.usage.cost, 4),
                    "prompt_tokens": run.usage.prompt_tokens,
                    "completion_tokens": run.usage.completion_tokens,
                    "seconds": round(time.time() - started, 1), "tail": tail,
                }
                sink.write(json.dumps(record) + "\n")
                sink.flush()
                mark = "PASS" if passed else "fail"
                print(f"{manifest['id']:<24} {args.harness:<8} rep{rep} {mark} "
                      f"turns={run.turns:<2} ${run.usage.cost:.3f}  total ${spent:.2f}")
                shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
