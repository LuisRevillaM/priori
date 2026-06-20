# M1.1R Gate R5 Controller Review

Date: 2026-06-20

Decision: ACCEPTED_CONTROLLER_ONLY

## Scope Reviewed

Gate R5 covers architecture proof and M1 parity after the M1.1R corrective runtime changes.

Reviewed paths:

- `src/tqe/runtime/executor.py`
- `src/tqe/runtime/catalog.py`
- `src/tqe/runtime/values.py`
- `src/tqe/verification/m1_1_gate_r5.py`
- `config/query-plans/ball_side_block_shift.ir.v1.json`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`
- `generated/capability-catalog.json`
- `Makefile`

## Evidence

- `make m1-1-gate-r5-verify` passed with 10 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r4-verify` passed with 8 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r3-verify` passed with 9 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r2-verify` passed with 4 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r1-verify` passed with 19 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-c-verify` passed with 10 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-b-verify` passed with 14 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-e-verify` passed with 21 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-f-verify` passed with 13 pass, 0 fail, 0 not-ready.
- `make test` passed 26 tests.
- `git diff --check` passed.

Gate R5 report highlights:

- renaming every approved-plan node while preserving references returns the same 180 runtime results;
- removing `signed_lateral_shift.possession_episodes` fails binding with `missing_node_input`;
- every advertised primitive, relation, and operator executes across approved, experimental, and simple valid plans;
- classification rules, requested evidence, and unknown policy all change runtime behavior;
- generic executor source contains none of the approved recipe predicate IDs;
- the simple non-block-shift plan executes without block-shift result fields;
- removing generated `artifacts/m1.1` cache still reproduces approved results from canonical data;
- Gate B full-output parity remains passing after the correction.

## Controller Assessment

Accepted for external review packet preparation.

M1.1R is now controller-verified, but M1.2 remains blocked until external review approves this corrective implementation or required changes are integrated and re-reviewed.

## Residual Risk

The runtime still uses `PeriodState` as an execution context and `state.accepted` as the final per-period result handoff. R5 proves the corrected explicit graph contract, node-ID opacity for approved-plan results, advertised capability execution, and M1 parity; it does not claim a universal graph engine or remove all legacy context plumbing.
