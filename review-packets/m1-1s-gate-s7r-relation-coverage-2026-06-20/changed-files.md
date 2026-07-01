# Changed Files

## Runtime

- `src/tqe/runtime/relations.py`
  - Adds per-anchor relation evaluation coverage.
  - Selects a deterministic witness relation for passing anchors.

- `src/tqe/runtime/executor.py`
  - Emits `anchor_evaluations` from filtered relation episodes.
  - Implements tri-state `exists` over relation coverage.
  - Implements anchor-relative `count_at_least` over relation coverage.
  - Resolves requested evidence through predicate witness relation IDs.
  - Preserves `INCLUDE_WITH_WARNING` rule decisions.
  - Enforces runtime `max_relations_per_anchor`.

- `src/tqe/runtime/catalog.py`
  - Declares `anchor_evaluations` as a relation output.

- `src/tqe/runtime/binder.py`
  - Enforces `max_execution_cost`.
  - Enforces `max_nesting_depth`.

## Plans And Generated Contract

- `config/query-plans/possession_corridor_availability.experimental.v1.json`
  - Routes `has_progressive_corridor` to `progressive_corridor.anchor_evaluations`.

- `config/query-plans/ball_side_block_shift.ir.v1.json`
  - Updates declared `max_nesting_depth` to match the approved plan graph under the new depth check.

- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`
  - Updates declared `max_nesting_depth` to match the experimental plan graph under the new depth check.

- `generated/capability-catalog.json`
  - Refreshed after catalog output changes.

## Verification

- `src/tqe/verification/m1_1_gate_s7r.py`
  - Adds the focused S7R proof target.

- `Makefile`
  - Adds `m1-1-gate-s7r-verify`.

## Delivery Records

- `docs/reviews/2026-06-20-m1-1s-gate-s7-external-review.md`
- `delivery/m1.1/reviews/gate-s7r-controller-review.md`
- `docs/learnings/2026-06-20-m1-1s-gate-s7r-relation-coverage.md`
- `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md`
- `delivery/m1.1/status.yaml`
- `delivery/ledger.jsonl`
