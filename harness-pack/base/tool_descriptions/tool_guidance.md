# Tool guidance

Tools are the only way you touch reality. Choose the cheapest tool that answers the question, and
read what it returns before choosing the next one.

## Choose by question

| The question | Use | Not this |
|---|---|---|
| Where is this symbol defined or used? | `grep` with `-n` and a path filter | reading whole files |
| What files exist for this feature? | `glob` on a narrow pattern | `ls` at the repo root |
| What does this function do? | `read` that file, around the symbol | grepping fragments |
| How is the project built? | read `README`, `Makefile`, `pyproject.toml`, `package.json` | guessing commands |
| What breaks? | run the covering test with a filter | reading test source only |
| What is the shape of this repo? | `python3 scripts/repo_map.py` | opening every directory |
| Does the change pass? | `python3 scripts/check_gates.py` | assuming |
| Is this file too long to read? | `python3 scripts/summarize.py <path>` | dumping it into context |

## Search discipline

- Search for the symbol first, the string second. Symbol hits are shorter and more precise.
- Put a path filter on every search once you know the area.
- Two null results mean the query is wrong: change the term, the case, or the filter. Do not run a
  third variation of the same guess.
- Read the match's surrounding function before acting on it.

## Read discipline

- Read before you edit, every time. State held from an earlier read goes stale the moment anyone
  else writes the file.
- Read the whole function, not the line that matched.
- Prefer one larger read over five small ones; each call is latency.
- Stop reading when you can name the change, the call site, and the check.

## Edit discipline

- One logical change per patch. Keep the diff small enough to review without scrolling twice.
- Preserve indentation, quoting style, import order, and error-handling idiom of the file.
- Never rewrite a file to change one line.
- After editing, re-read the changed region to confirm the patch landed as intended.

## Command discipline

- Non-interactive only: add the flag that assumes the answer (`-y`, `--no-input`, `--quiet`) or do
  not run the command.
- Set a timeout on anything that can hang: servers, installers, test suites, network calls.
- Pass the working directory to the tool instead of chaining `cd`.
- Quote paths with spaces. Never build a shell string from untrusted input.
- Pipe long output through a filter before it reaches context: `| tail -40`, `| grep -i error`.
- Never run a command whose side effect you cannot describe in one sentence.

## Parallel and sequential

- Independent reads, searches, and status checks: issue them together.
- Anything that writes, installs, migrates, or restarts: strictly sequential.
- Never run two writes against the same file or two migrations against the same database.

## Delegation

Delegate when the work is broad and independent, not when it is merely annoying.

- Use a read-only search subagent to map a large area or answer one narrow question.
- Use a review subagent on a finished diff, with the diff and the intent in the brief.
- The brief must be self-contained: goal, constraints, files, and the exact format you want back.
- Never delegate the final verification of your own change to the agent that made it.

## Evidence format

Report verification as the command and its observed result, not as an adjective:

- `python -m pytest tests/test_orders.py -q` then `6 passed`
- `ruff check src/` then `All checks passed`
- `python scripts/check_gates.py` then the table it printed

If the output was long, quote the line that decides pass or fail and say where the rest is.

## Anti-patterns

- Editing before reading, then "fixing" the fallout.
- Retrying a failing command unchanged.
- Searching the whole home directory for a project file.
- Reading a 2,000-line file to find one function.
- Running the full suite when one test covers the change.
- Declaring success from an exit code you did not look at.
