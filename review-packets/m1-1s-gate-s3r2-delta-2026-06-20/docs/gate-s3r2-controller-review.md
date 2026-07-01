# M1.1S Gate S3R2 Controller Review

Decision: `ACCEPTED_CONTROLLER_ONLY`

This revision integrates the external `REJECT_KEEP_S4_BLOCKED` review of the first S3R packet.

Corrections implemented:

- runtime anchor discovery now canonicalizes every anchor from match, period, frame/window, and entity references;
- typed `anchor_ref` output validation rejects producer-supplied IDs that do not match the canonical semantic hash;
- anchor dedupe keys on the semantic canonical ID, not record order or producer-provided identity;
- list-backed frame signals now require explicit frame IDs;
- predicate nodes execute through an explicit resolved-input/resolved-parameter boundary;
- generic `persists_for` contains one Boolean frame-signal path and does not inspect records or `_predicate_status`;
- M1 record-backed persistence is isolated behind explicitly named legacy adapters;
- target inspection derives generic traces from declared predicate runtime outputs before falling back to legacy status records;
- S3R proof now includes a non-M1 anchor with real PASS and FAIL traces.

Verification:

- `make m1-1-gate-s3r-verify`: pass, 11/0/0.
- `make m1-1-gate-s1-verify`: pass, 8/0/0.
- `make m1-1-gate-b-verify`: pass, 14/0/0.
- `make m1-1-gate-c-verify`: pass, 10/0/0.
- `make m1-1-gate-r5-verify`: pass, 10/0/0.
- `make test`: pass, 26 tests.

Residual risk:

Legacy M1 adapters remain because exact parity is still required. They are explicitly named and structurally isolated from the generic `persists_for` implementation. S4 should still avoid relying on legacy result side channels.

