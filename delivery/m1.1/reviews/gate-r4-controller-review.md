# M1.1R Gate R4 Controller Review

Date: 2026-06-20

Decision: ACCEPTED_CONTROLLER_ONLY

## Scope Reviewed

Gate R4 covers relation anchor decoupling and repair of the opposite-corridor experimental plan.

Reviewed paths:

- `src/tqe/runtime/executor.py`
- `src/tqe/runtime/catalog.py`
- `src/tqe/runtime/relations.py`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`
- `src/tqe/verification/m1_1_gate_r4.py`
- `generated/capability-catalog.json`

## Evidence

- `make m1-1-gate-r4-verify` passed with 8 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r1-verify` passed with 19 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-e-verify` passed with 21 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r3-verify` passed with 9 pass, 0 fail, 0 not-ready.
- `make test` passed 26 tests.

Gate R4 report highlights:

- `geometric_progressive_corridor` consumes an explicit `anchors` input.
- `relation_destination_entry_classification` consumes explicit `relation_episodes` input and no longer accepts `relation_node_id`.
- relation and destination implementations do not read `state.accepted`.
- the repaired opposite-corridor plan executes with 41 results.
- a valid relaxed plan produces 25 results, including 2 results sourced from STOPPAGE anchors outside the M1 accepted set.
- destination entry is represented as `side_lane_band` with explicit `min_y_m` and `max_y_m` bounds.

## Controller Assessment

Accepted for proceeding to Gate R5.

This does not complete M1.1R. R5 remains required to prove node-ID opacity, minimal advertised-capability execution, source-level approved-predicate-ID removal, cache deletion reproducibility, and full corrected M1 parity.

## Residual Risk

The executor still uses `state.accepted` as the final per-period result collection handoff. R4 removes hidden relation-input coupling, not the broader R5 generic-output-store proof.
