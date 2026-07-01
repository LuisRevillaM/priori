# M1.2 S0R2 External Review

Date: 2026-06-21

Decision: APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S2

## Blocking Findings

The external review accepted the S0R/S1R direction but kept S2 blocked on one
more focused trust-boundary correction:

- Hermes and manual/host tools were not separated strongly enough in code.
- Model-visible execution confirmation was still too close to model control.
- Opaque handles needed pattern validation, storage-root confinement, and
  create-once behavior.
- Hermes-authored plans needed explicit `EXPERIMENTAL` restriction and
  `agent_authorable` enforcement.
- Approved recipes and legacy parity had to be selected from trusted host state,
  not by model-authored status claims.
- Hermes-visible replay responses still exposed local filesystem paths.
- Supplied target times needed canonical frame resolution, and empty replay
  windows had to fail explicitly.
- Model-visible dispatcher payloads needed response-schema validation.

## Integrated S0R2/S1R2 Corrections

- Added `CallerProfile` and enforced a strict Hermes S2 tool surface distinct
  from the host/manual reference surface.
- Replaced model-supplied confirmation tokens with host-created authorization
  handles.
- Added strict handle regexes for drafts, bound plans, executions, replay
  windows, recipes, and authorizations.
- Made handle writes create-once and confined under the workshop handle store.
- Restricted Hermes submissions to `EXPERIMENTAL` plans.
- Rejected non-authorable catalog refs for Hermes-authored plans unless the
  bound plan is the trusted frozen M1 recipe.
- Removed local artifact paths from `retrieve_replay_window` responses and added
  an internal host resolver for verifiers/UI.
- Mapped target timestamps to canonical frames and rejected replay requests that
  return no frames.
- Added model-visible dispatcher output validation against generated response
  models.
- Updated S0 and S1 verifiers to prove the new trust boundary, hostile handles,
  manual-only tool denial, schema conformance, and replay behavior.

## Current Controller Decision

S0R2/S1R2 are controller-verified and ready for an external packet. Hermes S2
remains blocked until the packet is reviewed and approved.
