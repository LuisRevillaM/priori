# Changed Files

Baseline commit:

- `5becefc Freeze M1 baseline`

M1.1 implementation commits:

- `f74d8f8 Implement M1.1 Gate A IR binder`
- `8cc65a2 Implement M1.1 Gate B runtime parity`
- `bfd70c2 Implement M1.1 Gate C predicate traces`
- `abf6b34 Implement M1.1 Gate D geometric corridor relation`
- `40944b9 Implement M1.1 Gate E no-code composition`
- `0c4e6f8 Implement M1.1 Gate F developer inspector`

Diff stat from `5becefc..HEAD`:

```text
39 files changed, 9488 insertions(+), 16 deletions(-)
```

Key changed areas:

- `src/tqe/runtime/`: new IR, catalog, binder, executor, artifact generation, and relation code.
- `config/query-plans/`: approved M1 IR plan and experimental opposite-corridor plan.
- `src/tqe/verification/`: M1.1 aggregate verifier and Gate A-F verifiers.
- `src/tqe/inspector/`: static developer inspector generator.
- `tests/`: binder/runtime regression tests.
- `delivery/m1.1/`: status and controller reviews.
- `docs/learnings/`: per-gate durable learnings.
- `Makefile`: M1.1 gate commands.

Full source snapshots for the relevant files are copied under `source-files/`.
