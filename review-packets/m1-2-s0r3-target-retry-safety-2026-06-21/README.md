# M1.2 S0R3 Target And Retry Safety Review Packet

Date: 2026-06-21

Packet type: `inspection_packet_only`

Commit under review: `8a2685a43f551f957ec99b00c12873fc142985d7`

Branch: `codex/m1-1-s1-ir-binder`

## What This Is

This packet is a focused delta review for the remaining pre-S2 blockers from
the external S0R2 review. It does not reopen the runtime architecture, query IR,
relation semantics, or replay format.

## Review Scope

Please review whether S2 can now safely begin Hermes drafting given these
corrections:

- one canonical target resolver is used by both `inspect_non_match` and
  `retrieve_replay_window`;
- inspection output exposes resolved target metadata;
- inspection frame equals replay anchor frame;
- a compatible-anchor predicate-failure case is proven, not only
  `NO_COMPATIBLE_ANCHOR`;
- submit, validate, execute, and replay calls are idempotent for identical
  content-addressed resources;
- conflicting handle payloads still fail as collisions;
- all eight S2-visible tools have successful and failing model-visible response
  schema validation;
- host confirmation remains outside model control.

## What Is Real

- The implementation is committed in `8a2685a`.
- S0 passes 17/17.
- S1 passes 10/10.
- Aggregate M1.2 passes 2/2.
- M1.1 S7R passes 13/13.
- Unit tests pass, 27/27.

## Key Evidence

- `artifacts/target-consistency-summary.json` shows:
  - non-match inspection frame equals replay frame: `10000 == 10000`;
  - predicate-failure inspection frame equals replay frame: `11365 == 11365`;
  - predicate-failure probe is `NON_MATCH` with one compatible candidate and one failed predicate.
- `reports/gate-s0-verification-report.json` contains retry and full S2 tool schema checks.
- `reports/gate-s1-verification-report.json` contains target consistency and predicate-failure checks.
- `diffs/head.patch` contains the committed delta.

## Not Proven

- Hermes natural-language drafting is not implemented here.
- Prompt corpus results are not claimed.
- S3 feedback-driven revisions and semantic diffs are not complete.
- This packet is not self-contained enough to rerun the Make targets without the full repo.

## Requested Decision

Return one of:

```text
APPROVE_S2_UNBLOCKED
APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S2
REJECT_KEEP_S2_BLOCKED
```

Focus on whether the model-visible tool boundary is now target-consistent and
retry-safe enough for Hermes S2.
