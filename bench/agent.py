"""A minimal, deterministic agent loop used to compare harnesses.

One loop, one tool set, one model per run. The only variable is the system prompt, so a
difference in pass rate is attributable to the harness rather than to the scaffold.
"""

from __future__ import annotations

import itertools
import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

API = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MAX_TURNS = 20
MAX_TOOL_CHARS = 4000
COMMAND_TIMEOUT = 60

ALLOWED = {
    "python", "python3", "pytest", "ls", "cat", "head", "tail", "grep", "rg",
    "find", "wc", "sed", "awk", "diff", "sort", "uniq", "echo", "tree", "file",
}
FORBIDDEN_CHARS = (";", "&&", "||", "$(", "`", ">", "<")


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0

    def add(self, other: Usage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cost += other.cost


@dataclass
class Run:
    task_id: str
    model: str
    harness: str
    passed: bool = False
    turns: int = 0
    tool_calls: int = 0
    usage: Usage = field(default_factory=Usage)
    transcript: list[dict] = field(default_factory=list)
    error: str = ""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a file. Output carries 1-based line numbers. Use offset and limit for a range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string"},
                    "offset": {"type": "integer", "default": 1},
                    "limit": {"type": "integer", "default": 400},
                },
                "required": ["filePath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Overwrite a file with new content.",
            "parameters": {
                "type": "object",
                "properties": {"filePath": {"type": "string"}, "content": {"type": "string"}},
                "required": ["filePath", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Replace one occurrence of oldString with newString in a file. Fails if the text is absent or ambiguous.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string"},
                    "oldString": {"type": "string"},
                    "newString": {"type": "string"},
                    "replaceAll": {"type": "boolean", "default": False},
                },
                "required": ["filePath", "oldString", "newString"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run one shell command in the workspace and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "default": 60},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search file contents with a regular expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "include": {"type": "string", "default": "*"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Find files by glob pattern, for example '**/*.py'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list",
            "description": "List a directory of the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Declare the task complete. Call only after the full test suite passes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _within(root: Path, rel: str) -> Path | None:
    try:
        target = (root / rel).resolve()
    except (OSError, ValueError):
        return None
    return target if target == root or root in target.parents else None


def _command_ok(command: str) -> bool:
    if any(ch in command for ch in FORBIDDEN_CHARS):
        return False
    for segment in command.split("|"):
        try:
            parts = shlex.split(segment)
        except ValueError:
            return False
        if not parts or parts[0] not in ALLOWED:
            return False
    return True


def _run_command(root: Path, command: str, timeout: int = COMMAND_TIMEOUT) -> str:
    if not _command_ok(command):
        return "refused: command not allowed in this sandbox"
    site = ""
    try:
        import site as _site

        site = _site.getusersitepackages()
    except (AttributeError, ImportError, OSError):
        site = ""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(root),
        "PYTHONPATH": os.pathsep.join(p for p in (str(root), site) if p),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
    }
    try:
        proc = subprocess.run(
            ["sh", "-c", command], cwd=root, capture_output=True, text=True,
            timeout=timeout, env=env, check=False,
        )
    except subprocess.TimeoutExpired:
        return f"timeout after {timeout}s"
    out = (proc.stdout + proc.stderr).strip()
    return out[:MAX_TOOL_CHARS] or f"exit {proc.returncode}"


def _arg(args: dict, *names: str, default=None):
    for name in names:
        if name in args and args[name] not in (None, ""):
            return args[name]
    return default


def execute_tool(root: Path, name: str, args: dict) -> tuple[str, bool]:
    if name == "finish":
        return "done", True
    if name in ("read", "read_file"):
        target = _within(root, str(_arg(args, "filePath", "path", default="")))
        if target is None or not target.is_file():
            return "no such file", False
        start = max(1, int(_arg(args, "offset", "start", default=1)))
        limit = int(_arg(args, "limit", default=400))
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        body = "\n".join(f"{i:>4} {line}" for i, line in enumerate(lines[start - 1 : start - 1 + limit], start))
        return body[:MAX_TOOL_CHARS] or "(empty file)", False
    if name in ("write", "write_file"):
        target = _within(root, str(_arg(args, "filePath", "path", default="")))
        if target is None:
            return "path escapes the workspace", False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(args.get("content", "")), encoding="utf-8")
        return f"wrote {target.relative_to(root)}", False
    if name == "edit":
        target = _within(root, str(_arg(args, "filePath", "path", default="")))
        if target is None or not target.is_file():
            return "no such file", False
        source = target.read_text(encoding="utf-8")
        old = str(args.get("oldString", ""))
        new = str(args.get("newString", ""))
        hits = source.count(old) if old else 0
        if hits == 0:
            return "oldString not found; read the file and copy the text exactly", False
        if hits > 1 and not args.get("replaceAll"):
            return f"oldString appears {hits} times; add context or set replaceAll", False
        target.write_text(source.replace(old, new, -1 if args.get("replaceAll") else 1), encoding="utf-8")
        return f"edited {target.relative_to(root)}", False
    if name in ("bash", "run_command"):
        timeout = min(120, max(5, int(args.get("timeout", COMMAND_TIMEOUT))))
        return _run_command(root, str(args.get("command", "")), timeout), False
    if name == "grep":
        pattern = str(args.get("pattern", ""))
        include = str(args.get("include", "*"))
        try:
            proc = subprocess.run(
                ["grep", "-rn", f"--include={include}", "-E", pattern, str(args.get("path", "."))],
                cwd=root, capture_output=True, text=True, timeout=30, check=False,
            )
        except subprocess.TimeoutExpired:
            return "timeout", False
        return (proc.stdout or "no matches")[:MAX_TOOL_CHARS], False
    if name == "glob":
        base = _within(root, str(args.get("path", ".")))
        if base is None or not base.is_dir():
            return "no such directory", False
        pattern = str(args.get("pattern", "**/*"))
        hits = sorted(str(p.relative_to(root)) for p in base.glob(pattern) if "__pycache__" not in p.parts)
        return ("\n".join(hits[:200]) or "no matches")[:MAX_TOOL_CHARS], False
    if name in ("list", "list_files"):
        base = _within(root, str(args.get("path", ".")))
        if base is None or not base.exists():
            return "no such path", False
        entries = sorted(
            str(p.relative_to(root)) + ("/" if p.is_dir() else "")
            for p in list(base.rglob("*"))[:200]
            if "__pycache__" not in p.parts
        )
        return "\n".join(entries)[:MAX_TOOL_CHARS], False
    return f"unknown tool {name}", False


_KEY_CURSOR = itertools.count()


def _nvidia_keys() -> list[str]:
    keys = []
    for name in ["NVIDIA_API_KEY"] + [f"NVIDIA_API_KEY_{i}" for i in range(2, 8)]:
        value = os.environ.get(name, "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def call_model(model: str, messages: list[dict], key: str) -> tuple[dict, Usage]:
    provider = os.environ.get("BENCH_PROVIDER", "nvidia")
    if provider == "gemini":
        url = GEMINI_API
    elif provider == "nvidia":
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
    else:
        url = API
    pool = _nvidia_keys() if provider == "nvidia" else [os.environ.get("GEMINI_API_KEY", "") if provider == "gemini" else key]
    if not pool or not pool[0]:
        raise RuntimeError(f"no key for provider {provider}")
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0,
        "max_tokens": 4096,
    }
    if provider == "openrouter":
        payload["usage"] = {"include": True}
    last: Exception | None = None
    for attempt in range(12):
        key_index = next(_KEY_CURSOR) % len(pool)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {pool[key_index]}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/dev4aibots/harness2-studio",
                "X-Title": "harness-bench",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                body = json.loads(response.read())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            last = RuntimeError(f"HTTP {exc.code}: {detail}")
            if exc.code in (429, 500, 502, 503, 504, 403):
                time.sleep(min(45, 3 * 2**min(attempt, 4)))
                continue
            raise last from None
        except (urllib.error.URLError, TimeoutError) as exc:
            last = RuntimeError(f"network: {exc}")
            time.sleep(min(30, 2 * 2**attempt))
    else:
        raise last or RuntimeError("model call failed")

    usage_raw = body.get("usage") or {}
    usage = Usage(
        prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
        completion_tokens=int(usage_raw.get("completion_tokens", 0)),
        cost=float(usage_raw.get("cost", 0.0)),
    )
    return body["choices"][0]["message"], usage


def run_agent(
    *,
    task_id: str,
    workspace: Path,
    instruction: str,
    system_prompt: str,
    model: str,
    key: str,
    budget: BudgetExceeded | None = None,
    max_turns: int = MAX_TURNS,
) -> Run:
    run = Run(task_id=task_id, model=model, harness="")
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": instruction},
    ]
    for turn in range(1, max_turns + 1):
        message, usage = call_model(model, messages, key)
        run.turns = turn
        run.usage.add(usage)
        assistant = {
            "role": "assistant",
            "content": message.get("content") or "",
        }
        if message.get("tool_calls"):
            assistant["tool_calls"] = message["tool_calls"]
        messages.append(assistant)

        calls = message.get("tool_calls") or []
        if not calls:
            run.transcript.append({"turn": turn, "text": (message.get("content") or "")[:2000]})
            break
        for call in calls:
            run.tool_calls += 1
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            output, finished = execute_tool(workspace, name, args)
            messages.append(
                {"role": "tool", "tool_call_id": call.get("id", ""), "content": output}
            )
            run.transcript.append({"turn": turn, "tool": name, "args": args, "output": output[:800]})
            if finished:
                return run
    return run
