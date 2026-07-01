# Scope

## Target

M1.1S Gate S3R: **Explicit Anchor Contract and Generic Temporal Semantics**.

## Reason for packet

The prior external review accepted S1-S3 only with required changes before S4. It identified six blocking issues:

1. Anchors were inferred by scanning arbitrary runtime sidecars.
2. Anchor identity depended on node/output/list ordering.
3. Generic target/trace still had M1-shaped field assumptions.
4. `persists_for` was still partly block-shift-specific.
5. Node execution contract was not explicit enough.
6. Frame alignment could silently fall back to synthetic frame IDs.

This packet asks whether S3R sufficiently addresses those blockers and whether S4 may proceed.

## In scope

- Anchor source declaration and binder validation.
- Anchor record type/schema and semantic ID stability.
- Runtime anchor discovery and deduplication.
- Non-M1 anchor targeting/tracing.
- Runtime record storage outside provenance.
- Generic tri-state temporal persistence.
- Frame/value alignment errors.
- Node execution result contract.
- Regression/parity preservation.

## Out of scope

- Implementing S4 rule-driven result emission.
- UI/demo implementation.
- Priori integration.
- Dataset acquisition or data model expansion.
- Removing all legacy M1 compatibility paths.

