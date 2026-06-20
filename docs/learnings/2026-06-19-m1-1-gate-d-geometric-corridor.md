# M1.1 Gate D Geometric Corridor

## Fact

`geometric_progressive_corridor` V1 now emits deterministic relation episodes from canonical ball, attacking-player, defending-player, and orientation data.

## Decision

The relation remains a narrow geometric relation. It requires forward progression, segment length bounds, minimum defender-to-segment clearance, and hysteresis. It does not emit pass probability, completion likelihood, best-decision, optimality, intent, causation, or missed-opportunity claims.

## Learning

A 5m defender-to-segment clearance threshold is conservative enough to stay visually meaningful while still producing breadth across the Fortuna evaluation corpus: 165 episodes across all four evaluation matches and 75 accepted runtime results. The verifier reconstructs every emitted episode from canonical positions instead of trusting stored relation fields.

## Evidence

- `make m1-1-gate-d-verify` passes with 11/0/0.
- `artifacts/m1.1/relation-validation-report.json`
- `artifacts/m1.1/relation-visual-review/*.svg`
- `delivery/m1.1/reviews/gate-d-controller-review.md`

## Follow-Up

Gate E should consume this relation through an experimental plan document only. It should not add a query-specific detector or hidden Python branch for the opposite-corridor-after-shift composition.
