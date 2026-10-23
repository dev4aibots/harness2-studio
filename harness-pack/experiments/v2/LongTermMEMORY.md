# Long-term memory

A small, curated file beats a long transcript. It is read at the start of a task and edited at the
end of any task that taught something durable.

## Budget

- Hard cap: 120 lines of entries. When full, merge or delete before adding.
- One line per entry. If it needs a paragraph, it belongs in the project docs, not here.

## Format

- `- FACT | evidence | when it applies`
- `- LESSON | what went wrong | the rule that prevents it`

Examples:

- FACT | tests run with `python -m pytest -q` | every backend change
- FACT | generated clients live in `src/gen/` and must not be hand-edited | any API change
- LESSON | grepping a symbol missed dynamic dispatch | search the interface name too

## Write protocol

Append only when the entry would change a future decision:

- a command that works here, and a plausible one that does not
- a non-obvious invariant, ordering rule, or data shape
- a failure mode that cost more than one attempt to find
- a user preference about output, naming, or scope

Do not record: what you did, file lists, narration, or anything already in the README.

## Read protocol

At task start, scan for entries matching the task's domain. Treat entries as hints, not truth:
verify a remembered command before relying on it. If an entry is wrong, correct it in place and say
you did.

## Compaction

When over budget: delete resolved items, merge duplicates into the broader rule, and keep the oldest
entry that still explains a current constraint.

## Never

- Never store secrets, tokens, customer data, or anything the user marked private.
- Never rewrite an entry another author wrote without keeping its meaning.
