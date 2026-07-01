# M1.2 S0R3 External Review

Date: 2026-06-21

Decision: APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S2

## Blocking Findings

The external review accepted the major S0R2 trust-boundary work but kept S2
blocked for one focused correction:

- `inspect_non_match` and `retrieve_replay_window` could resolve the same
  user-supplied target to different frames.
- Content-addressed immutable handles were not retry-safe for normal repeated
  agent/user calls.
- S1 needed to exercise the exact model-visible adapter rather than only the
  lower-level dispatcher.
- S1 needed a compatible-anchor predicate-failure proof, not only a
  no-compatible-anchor explanation.

## Integrated S0R3/S1R3 Corrections

- Added a shared resolved target path for non-match inspection and target replay.
- Added resolved target metadata to non-match inspection output.
- Made handle writes idempotent for identical canonical payloads and still fail
  on true payload collisions.
- Ignored volatile timestamps and timing metrics only for handle identity
  comparison.
- Verified authorization records against bound-plan hash as well as bound-plan
  ID.
- Routed S1 S2-visible calls through `dispatch_model_visible`, with host
  confirmation remaining outside model control.
- Added retry proof for submit, validate, execute, and replay.
- Added successful and failing model-visible schema checks for all eight S2
  tools.
- Added a real diagnostic typed plan proving a compatible anchor can fail a
  declared predicate.

## Current Controller Decision

S0R3/S1R3 are controller-verified and ready for external review. Hermes S2
remains blocked until the packet is reviewed and approved.
