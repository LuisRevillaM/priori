# M1.2 Next Tasks

Date: 2026-06-21

Source of truth: `CURRENT_STATE.md`, `delivery/m1.2/SPEC.md`,
`delivery/m1.2/status.yaml`.

## Current Decision

Roadmap commit `4e78390` remains the active source of truth.

Clarification from external review: S3 is blocked on a working frontier-agent
path and a minimal query-to-replay workbench. It is not blocked on a finished,
polished UI.

## Track A - S2I-A/B

Outcome:

> The intended frontier-agent path is provisioned enough to prove access,
> configuration, and tool-boundary feasibility before deeper integration.

Scope:

1. Generate the Tactical Knowledge Pack:
   - `generated/tactical-knowledge-pack.json`
   - `generated/tactical-knowledge-pack.md`
2. Source the pack from executable/project truth, not a manually maintained
   prompt document.
3. Include:
   - approved and experimental recipes;
   - primitive and relation definitions;
   - input/output contracts;
   - valid parameters, units, and limits;
   - allowed operators;
   - evidence definitions;
   - ambiguity dimensions;
   - capability-gap codes;
   - allowed and prohibited claims;
   - query-plan schema;
   - model-visible tool schemas.
4. Run a provisioning spike that verifies:
   - access to `gpt-5.5-2026-04-23`;
   - Responses API strict structured output;
   - `high` and `xhigh` reasoning requests, if accessible;
   - Hermes installation and exact version;
   - Hermes connectivity to a trivial local MCP server;
   - MCP allowlisting of only selected tactical tools;
   - API billing/rate-limit readiness on the eventual demo machine.

Non-goals:

- no runtime semantics changes;
- no query IR redesign;
- no evaluation-vocabulary tuning;
- no second tactical family;
- no UI polish.

Evidence required:

- generated knowledge pack JSON and Markdown;
- source-hash or manifest section proving where pack content came from;
- provisioning report with exact versions, configuration, latency, failures, and
  recommended next step;
- no secrets in traces or reports.

Stop condition:

If GPT-5.5 or Hermes/MCP access is unavailable, stop with a concrete failure
report and preserve all partial knowledge-pack artifacts.

## Track B - Workbench Alpha 1

Outcome:

> A minimal React/TypeScript workbench proves query/selection to real results
> through the existing manual/saved-plan orchestration contract.

Architecture:

```text
AgentClient
  -> ManualPlanClient
  -> ReferenceCompilerClient
  -> HermesClient
```

The UI should depend on the orchestration contract, not a particular model.

Scope:

- recipe/query selection;
- interpreted plan display;
- host confirmation;
- execution;
- real result rail;
- loading state;
- empty-results state;
- validation-failure state;
- clarification state;
- capability-gap state;
- model-unavailable state.

Hard acceptance:

- one approved query and one experimental query execute end to end;
- every visible moment comes from a real execution;
- interpretation is shown before confirmation;
- confirmation is genuine;
- the manual/saved-plan path works with the model disabled;
- no hardcoded featured coordinates;
- no Hermes coupling required.

Non-goals:

- no final visual polish;
- no animation polish;
- no new tactical primitives;
- no second tactical family;
- no agent-owned confirmation.

## Track B Follow-Up - Workbench Alpha 2

Add evidence and replay after Alpha 1:

- `PitchReplayCanvas`;
- playback controls;
- evidence panel;
- predicate trace panel;
- moment timeline;
- non-match inspector.

Replay should use real `execution_id`, `result_id`, and `replay_window_id`
handles. The browser must not rerun or infer result moments.

## S3 Entry Criteria

S3 may begin only after:

1. S2I freezes a working frontier/Hermes runtime path and passes final sealed
   acceptance.
2. Workbench Alpha proves minimal query-to-replay over real data.

The Workbench Alpha requirement is intentionally minimal. It does not require
final typography, motion design, guided demo mode, or visual polish.
