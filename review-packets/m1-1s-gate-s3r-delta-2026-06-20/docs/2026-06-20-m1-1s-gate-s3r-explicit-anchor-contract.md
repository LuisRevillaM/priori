# M1.1S Gate S3R Learning - Explicit Anchor Sources Beat Sidecar Scanning

Date: 2026-06-20

Fact: Scanning arbitrary runtime record sidecars for `anchor_frame_id` produced duplicated physical anchors and unstable identity.

Decision: Plans now designate a single `anchor_source`, and the binder requires it to be an `episode_set<anchor_ref>` output. Runtime records moved from provenance metadata into `RuntimeValue.records`.

Learning: Generic anchor and trace code should not discover structure opportunistically. It needs an explicit source, a strict record schema, semantic IDs, and tests that synthetic non-M1 anchors work without M1 fields.

Evidence:

- `make m1-1-gate-s3r-verify` passes and writes `artifacts/m1.1/gate-s3r-verification-report.json`.
- The verifier proves node rename stability, deduplication, non-M1 target/trace support, side-channel independence, generic tri-state persistence, frame-length mismatch rejection, and parity preservation.

Follow-up: S4 can now focus on rule-driven result emission without having to reopen anchor identity or generic temporal semantics first.
