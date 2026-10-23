---
name: verify-change
description: Prove a change works before reporting it. Use before you say done, fixed, or passing, and whenever a diff touches behaviour that has no test yet.
---

# Verify change

The claim you are about to make must be the output you just read.

## Steps

1. **Pick the check.** Use the narrowest check that covers the changed behaviour, then the whole
   suite if it is cheap:

   | Change | Check |
   |---|---|
   | One function | the test that calls it |
   | Shared type or interface | every test that imports it |
   | Config or build | the build command, plus one runnable command |
   | Document or sheet | a command that opens it and prints its contents |
   | Dependency bump | the full suite, once |

2. **Run it and read it.** Run `python3 scripts/check_gates.py` for a project-wide pass when the
   change crosses modules. It prints a table of every gate with its exit code. Otherwise run the
   specific command yourself.

3. **Read the failure honestly.** A failure is information: quote the assertion and the input that
   produced it. Do not rerun hoping for a different result.

4. **Check the diff.** Read `git diff` yourself. Look for: debug prints, unrelated formatting,
   secrets, skipped tests, files you did not mean to touch, and generated files that should not be
   committed.

5. **State the boundary.** Write what you verified, with the command, and what you did not: manual
   UI, external service, data you cannot create locally.

## Exit criteria

- You can paste the command and its deciding output line.
- The diff contains only the intended change.
- The report names at least one thing that remains unverified, or states clearly that nothing does.

## Anti-patterns

- Running the suite from the wrong directory and calling the collection error a pass.
- Reporting "tests pass" when the run skipped the relevant test.
- Verifying with a command that does not exercise the changed path.
- Leaving a failing test to be discovered by the user.
