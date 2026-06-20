# M1.1R Gate R2 Runtime Values And Invocation

Date: 2026-06-19

## Fact

The executor now honors `execution_mode` and `max_results`, and every bound node output is wrapped in a `RuntimeValue` checked against its catalog output declaration during execution.

## Decision

Set the approved M1 IR plan's default invocation to `execute` with `max_results: 180`, because that plan is the full M1 parity plan. The 16-result proof set remains selected downstream by the proof-selection function, not by an inaccurate invocation cap.

## Learning

Contract truth matters more than preserving old metadata. A plan that requests `bind_only` or `max_results: 16` cannot be the same artifact used to claim 180 executed results.

## Evidence

- `src/tqe/runtime/values.py`
- `src/tqe/runtime/executor.py`
- `src/tqe/verification/m1_1_gate_r2.py`
- `config/query-plans/ball_side_block_shift.ir.v1.json`
- `artifacts/m1.1/gate-r2-verification-report.json`

## Follow-Up

Gate R3 must remove the compatibility layer by making predicates, classification, evidence projection, and unknown behavior consume typed runtime values and bound plan rules directly.
