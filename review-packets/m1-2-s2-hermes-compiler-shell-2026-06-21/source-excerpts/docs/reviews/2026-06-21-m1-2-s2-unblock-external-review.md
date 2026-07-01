# M1.2 S2 Unblock External Review

Date: 2026-06-21

Decision: APPROVE_S2_UNBLOCKED

## Accepted Findings

External review accepted the focused S0R3/S1R3 correction:

- target inspection and replay now resolve to the same canonical frame;
- compatible-anchor predicate failure is distinguishable from no compatible
  anchor;
- content-addressed tool calls are retry-safe;
- all S2-visible tools are exercised through the model-visible adapter;
- host/manual and Hermes caller boundaries remain intact.

The packet README had one incorrect full hash, but `commands/head.txt` and the
patch identified the correct commit:
`8a2685a43f551f957ec99b00c12873fc142985d7`.

## S2 Guardrails

- Prove the experimental happy path under `CallerProfile.HERMES_S2`.
- Keep host confirmation outside model control.
- Add recipe lookup and drafting without widening the trust surface.
- Persist the full language-to-execution trace.
- Keep capability gaps explicit.
- Stabilize error semantics before freezing prompt evaluation.
- Do not pull S3 revisions, threshold tuning, second tactical family, UI polish,
  or production infrastructure into S2.

## Controller Decision

S2 is unblocked. Begin with a bounded Hermes compiler shell and verification
gate before claiming full M1.2 completion.
