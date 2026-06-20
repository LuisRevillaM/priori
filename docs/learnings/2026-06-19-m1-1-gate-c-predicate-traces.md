# M1.1 Gate C Predicate Traces

## Fact

The M1.1 runtime now emits full predicate traces for accepted results and evaluates supplied non-match windows through a formal `EvaluationTarget`.

## Decision

Accepted-result traces are generated from the runtime candidate objects after classification, not from a separate verifier explanation path. Non-match inspection reuses the same bound-plan execution path and returns either a closest compatible candidate with failed or unknown predicates, or `NO_COMPATIBLE_ANCHOR`.

## Learning

Non-match explanations need both failure and unknown states. A threshold near miss can fail `shift_persists` while leaving `not_stoppage` unknown because outcome classification is intentionally not evaluated after the shift gate fails. Preserving that distinction avoids silently converting unevaluated evidence into a false predicate.

## Evidence

- `make m1-1-gate-c-verify` passes with 10/0/0.
- `artifacts/m1.1/predicate-trace-report.json`
- `artifacts/m1.1/non-match-inspection-report.json`
- `delivery/m1.1/reviews/gate-c-controller-review.md`

## Follow-Up

Gate D should reuse the same trace pattern for `geometric_progressive_corridor`: relation episodes must expose opened/closed frames, persistence, limiting defender, and unknown/invalid geometry states without implying optimality or missed opportunity.
