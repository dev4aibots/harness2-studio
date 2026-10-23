---
name: repo-recon
description: Map an unfamiliar codebase before changing it. Use when you have just opened a repository, when you cannot find where a behaviour lives, or when the task names a feature but not a file.
---

# Repo recon

Goal: in five minutes, know enough to make one correct change.

## Steps

1. **Shape.** Run `python3 scripts/repo_map.py .` and read the tree and symbol outline. If the
   script is unavailable, list the top two levels and open the manifest files.

2. **Commands.** Read the build and test entry points, in this order until you find them:
   `README`, `Makefile`, `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, `justfile`,
   `.github/workflows/`. Write down the exact test, lint, and build commands. These are the only
   commands you may later claim as verification.

3. **Entry point.** Find the executable path: the `main`, the route table, the CLI dispatch, the
   exported handler. Follow one request or command from entry to the place it touches data.

4. **One example.** Find an existing feature that does something similar to what you are about to
   add, and read it end to end. Copy its shape, not its details.

5. **Risk map.** Note: generated files, schema or migration order, feature flags, global state,
   and anything marked deprecated. These are where a small change breaks something large.

## Exit criteria

You can answer, with paths:

- where the behaviour lives, and what calls it
- how to run the relevant test
- which existing code is the pattern to follow
- what could break that the tests would not catch

## Anti-patterns

- Reading files alphabetically instead of following the call path.
- Trusting the README's commands without checking them.
- Exploring the whole repository when one directory owns the feature.
- Starting the edit before step 3 is done.
