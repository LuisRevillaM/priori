# M1.2 S0/S1 External Review

Date: 2026-06-21

Decision: APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S2

## Blocking Findings

The external review accepted the underlying workshop evidence but blocked S2 on
the agent-facing boundary:

- the prior packet was generated before the reviewed commit and showed a dirty
  worktree;
- tool schemas were placeholders;
- tools accepted local filesystem paths instead of host-owned handles;
- result inspection and replay could re-execute plans instead of using an
  immutable execution record;
- compatibility profile was client-selectable and too broadly mapped from
  `APPROVED`;
- capability entries lacked input-port contracts and agent-authorable status;
- S1 verifier bypassed the exact tool surface in several places;
- feedback and recipe writes were not strongly grounded.

## Integrated S0R/S1R Corrections

- Added real Pydantic-derived request and response JSON Schemas to the generated
  capability context.
- Added host-owned `draft_plan_id`, `bound_plan_id`, `execution_id`, and
  `replay_window_id` handles.
- Added `submit_query_plan` and serialized `dispatch_tool` as the boundary the
  manual client and future Hermes client use.
- Removed client-selected compatibility profile from the request models.
- Restricted legacy parity to the frozen `ball_side_block_shift` recipe.
- Stored immutable execution records with draft hash, bound hash, dataset
  identity, compatibility profile, result IDs, predicate traces, and evidence.
- Made `inspect_result`, `inspect_non_match`, `retrieve_replay_window`, and
  `record_feedback` resolve through `execution_id`.
- Made feedback requests require exactly one result or target.
- Made recipe save bind and safety-check submitted experimental drafts before
  persistence.
- Added input-port contracts and `agent_authorable` metadata to capability
  entries.
- Updated S1 to run through the serialized dispatcher rather than private
  runtime calls.

## Current Controller Decision

S0R/S1R are controller-verified and ready for another external review packet.
Hermes S2 remains blocked until that packet is reviewed.

