# M1.2 Next Tasks

Date: 2026-06-21

Source of truth: `CURRENT_STATE.md`, `delivery/m1.2/SPEC.md`,
`delivery/m1.2/status.yaml`.

## Current Decision

Roadmap commit `4e78390` remains the active source of truth, amended by the
accepted S2I rebaseline and Workbench Alpha R1 hardening commits through
`36649b3`.

Clarification from external review: S3 is blocked on a working frontier-agent
path and a minimal query-to-replay workbench. It is not blocked on a finished,
polished UI.

As of commit `36649b3`, the Workbench side of that entry requirement is
controller-verified with `make workbench-alpha-verify`. The remaining S3 blocker
is the final independent evaluation against the frozen Hermes/frontier route.

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

MCP posture:

- MCP is the Hermes adapter, not the application core.
- Build a host-owned application/orchestrator service first; the React
  Workbench and the Tactical MCP adapter both call that same service.
- Use local `stdio` MCP for the demo spike. Do not build remote/cloud MCP,
  authentication, or service-token infrastructure yet.
- The first Hermes/MCP allowlist is:
  - `list_capabilities`
  - `search_recipes`
  - `describe_capability`
  - `submit_query_plan`
  - `validate_query_plan`
  - `inspect_result`
  - `inspect_non_match`
  - `retrieve_replay_window`
- Keep these host-only:
  - `host_confirm_bound_plan`
  - `execute_query_plan`
  - `record_feedback`
  - `compare_query_versions`
  - `save_experimental_recipe`
- The current S2 reference harness may still expose `execute_query_plan` for
  regression tests, but the S2I product/Hermes path must not.

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
- proof that the generated pack distinguishes current reference-harness tools
  from the S2I target Hermes/MCP allowlist.

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

Status: **DONE_CONTROLLER_VERIFIED** at commit `36649b3`.

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

Status: **DONE_CONTROLLER_VERIFIED_MINIMAL_R1_HARDENED** at commit `36649b3`.
The implementation also now sanitizes public replay DTOs, validates generated
error contracts, exposes host-owned cache progress, and labels manual
interpretation sources honestly.

## Track A Final - S2I-F

Outcome:

> A fresh independently authored sealed set passes against the frozen
> Hermes/frontier product route.

The executable gate is:

```bash
make m1-2-gate-s2if-verify
```

By default it reads:

```text
config/evaluation/m1_2_s2i_final_independent_set.json
```

or a caller can provide:

```bash
S2I_FINAL_EVAL_SET=/path/to/external-set.json make m1-2-gate-s2if-verify
```

The gate fails closed when the external set is absent. It must run the frozen
route:

```text
Hermes Agent
-> openai-codex / gpt-5.5 / xhigh
-> local stdio priori_tactical MCP
-> bounded validate-only tactical tools
```

Acceptance remains:

- supported accuracy at least 90%;
- ambiguous accuracy at least 90%;
- unsupported accuracy exactly 100%;
- schema-valid-or-refusal exactly 100%;
- unauthorized calls: 0;
- unconfirmed executions: 0.

Do not use old `gpt-4o-mini` sealed sets as final acceptance evidence. They are
diagnostic history only.

## S3 Entry Criteria

S3 may begin only after:

1. S2I freezes a working frontier/Hermes runtime path and passes final sealed
   acceptance.
2. Workbench Alpha proves minimal query-to-replay over real data.

The Workbench Alpha requirement is intentionally minimal. It does not require
final typography, motion design, guided demo mode, or visual polish.
