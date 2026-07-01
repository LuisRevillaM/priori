# Changed Files

Committed patch: `a003bc8 Harden M1.2 workshop trust boundary`

## Source

- `src/tqe/workshop/m1_2.py`: adds caller profiles, strict handle validation,
  host-owned authorization, model-visible response validation, canonical replay
  target lookup, Hermes authoring restrictions, and internal-only replay artifact
  resolution.
- `src/tqe/verification/m1_2_gate_s0.py`: proves Hermes/manual tool separation,
  hostile handle rejection, non-authorable capability rejection, schema
  conformance, and safe capability exposure.
- `src/tqe/verification/m1_2_gate_s1.py`: runs the manual workshop through the
  dispatcher, host authorization, execution handles, replay handles, feedback,
  and recipe save path.

## Durable Plan/Review Docs

- `delivery/m1.2/SPEC.md`: records the S0R2/S1R2 trust-boundary requirements.
- `delivery/m1.2/status.yaml`: marks S0R2/S1R2 controller-verified and keeps S2
  blocked pending external review.
- `docs/reviews/2026-06-21-m1-2-s0r2-external-review.md`: external review
  summary and integrated corrections.
- `docs/learnings/2026-06-21-m1-2-s0r2-trust-boundary.md`: durable learning for
  future controller/worker agents.

## Generated

- `generated/capability-context.json`: regenerated Hermes-visible context after
  narrowing the tool surface and removing path exposure.
