# Current State Snapshot

Date: 2026-06-21

## Repository State

- Branch: `codex/m1-1-s1-ir-binder`
- Latest committed controller checkpoint before this snapshot:
  `bd67c96 Implement search_recipes and hold S2I-A acceptance`
- Working tree: no tracked modifications at snapshot time; existing untracked review packets and `docs/learnings.zip` remain outside this snapshot.
- Current product source of truth:
  - `delivery/m1.2/SPEC.md`
  - `delivery/m1.2/status.yaml`
  - `delivery/status.yaml`
  - `delivery/ledger.jsonl`

## Product Thesis

We are building a Tactical Query Evidence Explorer for football tracking data.

The model authors or selects a typed tactical definition. The deterministic engine measures real match tracking data. The UI shows real moments, evidence, predicate traces, and coordinate replay.

```text
football language
-> agent/compiler
-> typed tactical plan
-> deterministic matcher
-> real match moments
-> evidence, traces, replay
-> human feedback and recipe refinement
```

## Accepted And Frozen State

- M1 real-data spine: verified through canonical IDSSE/DFL tracking artifacts and replay proof.
- M1.1 deterministic tactical runtime: accepted through the M1.1S S7R2 unblock path, with M1 parity isolated behind the explicit legacy helper.
- M1.2 S0/S1/S2 safety harness: controller-verified through bounded tool schemas, host confirmation, opaque handles, model-visible caller profiles, manual workshop, model-backed compiler harness, provenance, sealed evaluation reports, and deterministic fallback reporting.
- Small-model compiler baseline: frozen at `f9eb5d8`.

The `gpt-4o-mini` compiler lane is now a reference compiler harness and fallback/evaluation control. It is not the target meeting runtime. No more synonym hardening or fresh sealed-set requests should be opened against that lane unless a concrete regression in the reference harness is found.

## Verification Commands

Known green commands at the frozen baseline:

```text
make m1-2-gate-s2-sealed-verify
make m1-2-gate-s2-verify
make m1-2-verify
make m1-1-gate-s7r-verify
make test
```

Additional available gates:

```text
make m1-verify
make m1-1-verify
make m1-2-gate-s0-verify
make m1-2-gate-s1-verify
```

## Stable Tool Boundary

Current Hermes/model-visible tool names in `src/tqe/workshop/m1_2.py` and `generated/capability-context.json`:

```text
list_capabilities
describe_capability
submit_query_plan
validate_query_plan
execute_query_plan
inspect_result
inspect_non_match
retrieve_replay_window
```

Manual/host-only tools already exist:

```text
compare_query_versions
record_feedback
save_experimental_recipe
host_confirm_bound_plan
```

Host confirmation remains outside model authority. A model can draft or select, but cannot confirm execution, mutate primitives, write approved recipes, execute raw code, access the filesystem, or request raw coordinate dumps.

## Current Contracts

Stable request/response schema sources:

- Tool models and dispatcher: `src/tqe/workshop/m1_2.py`
- Model-backed compiler harness: `src/tqe/workshop/hermes_s2.py`
- Generated capability context: `generated/capability-context.json`
- Generated query-plan schema: `generated/tactical-query-plan.schema.json`
- Generated TypeScript query-plan types: `generated/tactical-query-plan.types.ts`
- Runtime IR and binder: `src/tqe/runtime/ir.py`, `src/tqe/runtime/binder.py`
- Runtime executor and artifacts: `src/tqe/runtime/executor.py`, `src/tqe/runtime/artifacts.py`
- Primitive/relation catalog: `src/tqe/runtime/catalog.py`, `src/tqe/runtime/relations.py`
- Primitive registry docs: `docs/primitives/registry.yaml`

Replay contract:

- `retrieve_replay_window` returns an opaque `replay_window_id`, bounded summary metadata, frame range, entity counts, and an internally resolvable replay artifact.
- Replay JSON artifacts currently live under `artifacts/m1.2/workshop/replay-windows/`.
- The model-visible response does not expose local filesystem paths.

Execution contract:

- `submit_query_plan` stores a typed query document and returns a `draft_plan_id`.
- `validate_query_plan` binds and validates the draft and returns a `bound_plan_id` when valid.
- `host_confirm_bound_plan` creates host-owned execution authorization.
- `execute_query_plan` runs the deterministic runtime and returns an `execution_id` plus result IDs.
- `inspect_result` returns predicate traces and evidence for a result.
- `inspect_non_match` evaluates a target timestamp/frame against a bound plan.

## UI Surface Today

There is a plain generated manual workshop, not the final React product UI:

- HTML: `artifacts/m1.2/workshop/index.html`
- Data: `artifacts/m1.2/workshop/manual-workshop-data.json`
- Replay windows: `artifacts/m1.2/workshop/replay-windows/*.json`

The existing app directory is `apps/replay-proof`, used for earlier replay proof/verification. There is not yet a Workbench Alpha React UI over the M1.2 orchestrator.

## Agent And API Availability

- `OPENAI_API_KEY`: present in the environment at snapshot time; key value was not inspected or logged.
- GPT-5.5 snapshot access: not yet verified locally.
- Responses API strict structured output call: not yet verified locally.
- Hermes CLI/local install: no `hermes` or `hermes-agent` executable found on PATH during snapshot.
- MCP support for Hermes: not yet verified locally.

## S2I-A Tactical Knowledge Pack

Implemented and locally verified; formal acceptance is pending one successful
broader S2 regression run:

- JSON: `generated/tactical-knowledge-pack.json`
- Markdown: `generated/tactical-knowledge-pack.md`
- Pack SHA-256: `9a58b26f1426b9bfc7c61a531a8dfb05fd885cf035b925310594868a1f75160b`
- Verification: `make m1-2-gate-s2i-verify`
- Local verification report:
  `docs/reviews/2026-06-21-m1-2-s2i-a-local-verification.md`

The pack is generated from source hashes and distinguishes the current S2
reference-harness tool surface from the S2I target Hermes/MCP allowlist. The S2I
target keeps `execute_query_plan` and `host_confirm_bound_plan` host-only.
`search_recipes` is implemented as a bounded schema-validated dispatcher tool.

## Known Gaps Before S2I-B

- No real Hermes MCP adapter is wired to the bounded tool surface.
- GPT-5.5 direct Responses API access has been probed successfully, but no
  Hermes-backed adapter has run it yet.
- Initial high/xhigh comparison has run outside Hermes context and recommends
  `high` until Hermes-context evaluation proves otherwise.
- One broader S2 regression run must still complete successfully before S2I-A is
  formally accepted.
- No final sealed acceptance set has been run against the intended frontier/Hermes path.
- No local `hermes` or `hermes-agent` executable is currently available; Hermes
  must be installed/configured with ChatGPT/Codex subscription login before the
  full S2I-B gate can pass.

## S2I-B Provisioning Spike

Partial proof exists:

- Report: `artifacts/m1.2/s2i-b-provisioning-report.json`
- Local review: `docs/reviews/2026-06-21-m1-2-s2i-b-provisioning.md`
- Result: `7 pass / 1 fail`
- Failing check: `hermes.executable_available`
- Requested model: `gpt-5.5-2026-04-23`
- Returned model: `gpt-5.5-2026-04-23`
- Strict structured output: pass
- `high` reasoning: pass
- `xhigh` reasoning: pass
- Product MCP allowlist excludes host-only execution and confirmation tools.
- Tactical tool proof submits and validates the experimental corridor plan, then
  stops before execution.

## Known Gaps Before Workbench Alpha

- No React Workbench Alpha over the M1.2 orchestrator.
- No hosted/local HTTP orchestrator API for the UI.
- Existing manual workshop is static/plain and generated from artifacts.
- UI does not yet show the full product loop: query, interpretation, confirmation, results, replay, evidence, clarification, capability gap, feedback.
- Result-to-replay artifacts exist, but UI readiness and replay performance have not been measured for the Workbench Alpha target.

## Next Roadmap State

The next implementation milestone is S2I: Frontier Agent Provisioning and Context Rebaseline.

S2I should:

1. Generate a single Tactical Knowledge Pack from current sources of truth.
2. Expose the bounded tactical tools through a Hermes-compatible MCP/tool boundary.
3. Configure and test GPT-5.5 through the Responses API with strict structured outputs.
4. Keep the direct model harness as a control/evaluation path only.
5. Freeze the selected product runtime.
6. Run one final independent sealed acceptance set.

Workbench Alpha should start in parallel against stable deterministic contracts:

```text
manual/saved recipe
-> interpreted plan
-> host confirmation
-> execution
-> result rail
-> predicate/evidence panel
-> coordinate replay
-> clarification/capability-gap states
```

S3 remains blocked until S2I passes and Workbench Alpha proves minimal
query-to-replay over real data. This means a working query/selection,
interpretation, confirmation, execution, result rail, evidence/trace, and replay
path. It does not mean finished visual design, animation polish, guided demo
mode, or meeting packaging.
