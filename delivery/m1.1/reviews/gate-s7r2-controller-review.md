# Gate S7R2 Controller Review

## Decision

`ACCEPTED_CONTROLLER_ONLY_READY_TO_UNBLOCK_M1_2`

S7R2 closes the final focused blockers from the S7R external review without redesigning the runtime.

## Evidence

- `make m1-1-gate-s7r-verify` passes `13/0/0`.
- `make m1-1-gate-s4-verify` passes `16/0/0`.
- `make m1-1-gate-s6-verify` passes `8/0/0`.
- `make m1-1-gate-s7-verify` passes `7/0/0`.
- `make m1-1-gate-a-verify` passes `80/0/0`.
- `make test` passes `27` tests.
- `git diff --check` is clean.

## Accepted Changes

- Mixed relation evidence now produces `UNKNOWN` unless a qualifying relation is already proven.
- A fully evaluated zero-relation anchor still produces definitive `FAIL`.
- Proven relation witnesses remain `PASS` even if unrelated evidence is unavailable.
- Evidence projection resolves witnesses per requested relation source.
- Agent-visible operator signatures no longer allow raw relation episode inputs to `exists` or `count_at_least`.
- Plan-authored complexity limits are capped by trusted catalog ceilings.

## M1.2 Status

From the controller perspective, M1.2 can begin after this implementation is committed and the owner confirms proceeding.
