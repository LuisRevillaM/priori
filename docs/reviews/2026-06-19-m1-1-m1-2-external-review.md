# External Review - M1.1 / M1.2 Architecture Split

Date: 2026-06-19

Decision: `APPROVE_WITH_REQUIRED_CHANGES`

## Summary

The reviewer approved the split:

- M1.1 proves the deterministic compositional runtime.
- M1.2 proves Hermes can operate it safely.

The reviewer rejected implementation readiness until required changes are integrated into the specs.

## Required Changes Integrated

- M1.1 must begin with an M1 baseline freeze, including a valid Git baseline, owner acceptance or explicit waiver, source/config hashes, legacy result manifest, evidence-bundle manifest, and reviewed semantic gold set.
- M1 parity must be measured against both complete machine output and reviewed examples.
- The binder type system must include payload types, cardinality, units, entity scope, and missing-data semantics.
- Predicate logic must be tri-state: `TRUE`, `FALSE`, `UNKNOWN`.
- `RecipeDefinition`, `QueryInvocation`, `BoundQueryPlan`, and `QueryExecution` must be separate objects.
- M1.1 implementation order must prove M1 runtime parity before building the relation layer.
- `geometric_progressive_corridor` V1 must stay narrow and geometric.
- Non-match inspection must use a formal `EvaluationTarget` and support `NO_COMPATIBLE_ANCHOR`.
- Hermes scoped data access must return artifact/window IDs and summaries, not coordinate dumps.
- M1.2 must include a frozen quantitative evaluation corpus.
- M1.2 persistence must be simple, immutable, and versioned.

## Blocking Findings Recorded

1. The repository has no valid Git baseline yet.
2. M1 parity preserves behavior, not correctness, so reviewed semantic examples are needed.
3. The original type system was incomplete.
4. Non-match inspection was underspecified.
5. `geometric_progressive_corridor` needed narrowing to avoid becoming a full pass model.

## Source Files Updated

- `delivery/m1.1/SPEC.md`
- `delivery/m1.1/status.yaml`
- `delivery/m1.2/SPEC.md`
- `delivery/m1.2/status.yaml`
- `MILESTONES.md`
- `docs/adr/0011-m1-1-m1-2-runtime-workshop-split.md`
- `docs/learnings/2026-06-19-runtime-workshop-split.md`
- `delivery/ledger.jsonl`

## Remaining Owner Decision

Before implementation, the owner must either:

- ask Codex to commit the M1 baseline; or
- explicitly waive the baseline commit requirement and accept the resulting oracle risk.
