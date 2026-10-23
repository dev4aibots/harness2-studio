---
name: debug-loop
description: Find the cause of a failure before changing code. Use when a test fails, a command errors, output is wrong, or a bug report arrives without a reproduction.
---

# Debug loop

A fix without a reproduction is a guess. This skill produces the reproduction first.

## Steps

1. **Reproduce.** Run the smallest command that shows the failure. Quote the exact error text.
   If you cannot reproduce it, stop and report what you tried, with the command and output.

2. **Locate.** Find the first frame in the stack that belongs to this project. Read that function
   and its inputs. Do not start at the last line of the traceback.

3. **Narrow.** Halve the search space with one question per step:
   - Does it fail with the simplest possible input?
   - Does it fail on the previous commit?
   - Does it fail when the suspect line is removed?
   Each answer must come from a command, not from reasoning about the code.

4. **Hypothesise in writing.** One sentence: "It fails because X happens before Y." Then predict
   what you will see if that is true. Run the check. If the prediction is wrong, discard the
   hypothesis; do not adjust it to fit.

5. **Fix the cause.** Change the smallest thing that makes the hypothesis false. If the fix needs
   three other changes, the diagnosis was wrong.

6. **Prove it.** Add the failing case as a test if one does not exist. Run it before the fix to see
   it fail, then after to see it pass. Run the neighbouring tests for regressions.

## Exit criteria

- The failing case is a test that exists in the repository.
- The test failed before the fix and passes after it, and you observed both.
- No unrelated test changed state or was skipped.

## Anti-patterns

- Adding a try/except where the error surfaced.
- Changing the test to match the output.
- "It works now" without a command that shows it.
- Fixing two suspected causes at once, so neither is proven.
