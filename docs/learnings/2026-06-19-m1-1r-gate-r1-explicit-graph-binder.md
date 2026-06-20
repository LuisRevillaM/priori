# M1.1R Gate R1 Explicit Graph Binder

Date: 2026-06-19

## Fact

The binder now requires explicit plan graph inputs for catalog nodes that depend on upstream outputs, validates those inputs against catalog signatures, validates node parameters against catalog schemas, and carries invocation mode/max results into the bound plan.

## Decision

Remove non-executable/no-op capabilities from the exposed default catalog. If a capability is shown to a future Hermes agent, it must have an implementation path and a proof gate.

## Learning

Schema shape is not enough. The binder must validate the relationship between the plan and the executable catalog, not just that both independently parse.

## Evidence

- `src/tqe/runtime/ir.py`
- `src/tqe/runtime/catalog.py`
- `src/tqe/runtime/binder.py`
- `src/tqe/verification/m1_1_gate_r1.py`
- `config/query-plans/ball_side_block_shift.ir.v1.json`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`
- `artifacts/m1.1/gate-r1-verification-report.json`

## Follow-Up

Gate R2 must make these bound contracts operational in the executor through first-class runtime values and invocation semantics.
