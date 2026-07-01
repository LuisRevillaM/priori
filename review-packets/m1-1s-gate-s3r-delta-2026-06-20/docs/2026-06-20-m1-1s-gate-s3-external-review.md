# M1.1S Gate S3 External Review

Date: 2026-06-20

Decision: APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S4

## Blocking Findings Accepted By Controller

1. Anchors were inferred from arbitrary record sidecars instead of a designated anchor domain.
2. Anchor IDs included node/output identity and ordering-sensitive fields.
3. Generic target and trace paths still assumed M1-shaped fields.
4. `persists_for` still contained block-shift-specific temporal semantics.
5. Node execution did not yet expose an explicit execution-result contract.
6. Frame-signal length mismatch could silently fall back to synthetic frame IDs.

## Required Corrective Gate

Create S3R: Explicit Anchor Contract and Generic Temporal Semantics.

Required before S4:

- plan-designated anchor source;
- semantic anchor IDs stable under node renaming;
- deduplication of repeated physical anchors;
- non-M1 anchors targetable and traceable;
- anchor discovery independent of `state.candidates` and `state.accepted`;
- generic `persists_for` over tri-state Boolean signals only;
- no mandatory `wide_entry_*`, `block_shift_*`, or `shift_gate_*` assumptions in generic anchor/trace code;
- hard failure on frame-ID/value length mismatch;
- explicit node execution result contract.

## Controller Response

Accepted. S4 remains blocked until S3R passes.
