---
name: write-tests
description: Write a test that fails for the right reason before the implementation exists. Use when adding behaviour, fixing a bug, or when a change has no coverage.
---

# Write tests

A test is a specification that runs. It should fail for exactly one reason and pass for exactly one
reason.

## Steps

1. **Name the behaviour** in one sentence: "returns 409 when the slug already exists". If the
   sentence has an "and", write two tests.

2. **Find the harness.** Use the project's existing test framework, fixtures, and factories. Read
   one neighbouring test and match its structure; do not introduce a second testing style.

3. **Write the failing case first.** The smallest input that demonstrates the behaviour. Run it and
   confirm it fails, and that it fails on the assertion you intended, not on an import error.

4. **Implement to green.** Change production code, not the test.

5. **Cover the edges that matter**, not every branch:
   - the boundary: empty, one, maximum, off-by-one
   - the error path: what the caller sees when the dependency fails
   - the regression: the exact input from the bug report

6. **Keep it deterministic.** No real network, no wall-clock sleeps, no ordering between tests, no
   dependence on the developer's home directory. Use a temp directory and a fixed clock or seed.

## Exit criteria

- The test fails before the change and passes after it, both observed.
- The assertion message explains the failure to someone who did not write it.
- The suite runtime did not grow noticeably.

## Anti-patterns

- Asserting on a snapshot of a large object nobody reads.
- Mocking the function under test, so the test proves the mock.
- One test with eight asserts covering eight behaviours.
- Retrying a flaky test instead of removing the nondeterminism.
