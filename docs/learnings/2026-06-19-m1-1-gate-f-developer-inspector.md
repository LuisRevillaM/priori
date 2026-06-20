# M1.1 Gate F Developer Inspector

## Fact

M1.1 now generates a static developer inspector under `artifacts/m1.1/inspector/` with two selectable plans, 57 inspectable results, replay frames, predicate traces, non-match evaluations, validation summaries, and raw evidence.

## Decision

Gate F remains a developer proof artifact, not the final analyst workshop. The inspector uses a generic plan/result data contract and reuses existing replay bundles instead of introducing a new replay source or hardcoded M1 result panel.

## Learning

The safest bridge from runtime proof to future UI is a static, inspectable artifact with explicit data contracts. It lets Gate F prove that the runtime outputs are complete enough for a UI without forcing M1.1 to solve product interaction design. Embedding replay frames makes the artifact large, but keeps it self-sufficient and easy for verifiers to inspect.

## Evidence

- `make m1-1-gate-f-verify` passes with 13/0/0.
- `make m1-1-verify` passes with 118/0/0 across Gates A-F.
- `artifacts/m1.1/inspector/index.html`
- `artifacts/m1.1/inspector/inspector-data.json`
- `artifacts/m1.1/inspector/manifest.json`
- `delivery/m1.1/reviews/gate-f-controller-review.md`

## Follow-Up

M1.2 should treat this inspector as a runtime-proof reference, not as the workshop UI. The workshop can reuse the same plan/result/replay/trace contract, but should add a proper interaction layer for Hermes interpretation, feedback, revisions, and saved experimental recipes.
