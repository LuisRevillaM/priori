# Current State Snapshot

Date: 2026-06-21

## Repository State

- Branch: `codex/m1-1-s1-ir-binder`
- Latest committed controller checkpoint before this snapshot:
  `d745f6c Add S2I-B provisioning spike report`
- Working tree: scoped S2I-B status/report updates; existing untracked review packets, primitive-audit artifacts, and `docs/learnings.zip` remain outside this snapshot.
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
- GPT-5.5 snapshot access: verified through direct Responses API provisioning probes.
- Responses API strict structured output call: verified for `gpt-5.5-2026-04-23`.
- Hermes CLI/local install: verified at `/Users/luisrevilla/.local/bin/hermes`.
- Hermes version: Hermes Agent v0.17.0 (2026.6.19), upstream `2b3a4f0a`.
- Hermes auth: `openai-codex` logged in via ChatGPT/Codex subscription device auth under `HERMES_HOME=/Users/luisrevilla/.hermes-priori`.
- Hermes model config: provider `openai-codex`, default `gpt-5.5`, reasoning effort `xhigh`.
- MCP support for Hermes: base provisioning is now green; the tactical MCP adapter has not yet been connected to a real Hermes-authored validation.

## S2I-A Tactical Knowledge Pack

Implemented and locally verified; formal acceptance is pending one successful
broader S2 regression run:

- JSON: `generated/tactical-knowledge-pack.json`
- Markdown: `generated/tactical-knowledge-pack.md`
- Pack SHA-256: `35b5d64e426ec3eb27faee220f5500713e71b0dd2a55fd477a26cd888f38a41e`
- Verification: `make m1-2-gate-s2i-verify`
- Local verification report:
  `docs/reviews/2026-06-21-m1-2-s2i-a-local-verification.md`

The pack is generated from source hashes and distinguishes the current S2
reference-harness tool surface from the S2I target Hermes/MCP allowlist. The S2I
target keeps `execute_query_plan` and `host_confirm_bound_plan` host-only.
`search_recipes` is implemented as a bounded schema-validated dispatcher tool.

## Known Gaps After S2I-B

- No real Hermes MCP adapter is wired to the bounded tool surface yet.
- No real Hermes-authored tactical request has run through list/search/describe,
  plan submission, validation, and stop-before-host-execution.
- Initial high/xhigh comparison has run outside Hermes context and currently
  recommends `xhigh`; Hermes-context evaluation still needs to prove the final
  runtime setting.
- One broader S2 regression run must still complete successfully before S2I-A is
  formally accepted.
- No final sealed acceptance set has been run against the intended frontier/Hermes path.

## S2I-B Provisioning Spike

Provisioning proof is now green:

- Report: `artifacts/m1.2/s2i-b-provisioning-report.json`
- Local review: `docs/reviews/2026-06-21-m1-2-s2i-b-provisioning.md`
- Result: `8 pass / 0 fail`
- Requested model: `gpt-5.5-2026-04-23`
- Returned model: `gpt-5.5-2026-04-23`
- Strict structured output: pass
- `high` reasoning: pass
- `xhigh` reasoning: pass
- Hermes executable: `/Users/luisrevilla/.local/bin/hermes`
- Hermes auth: `openai-codex: logged in`
- Hermes smoke: `hermes chat -q` returned `HERMES_READY`
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

The next implementation milestone is S2I tactical MCP integration on top of the
now-provisioned frontier/Hermes path.

S2I should:

1. Connect the tactical MCP adapter to Hermes without exposing host-only tools.
2. Run one real Hermes-authored request through list/search/describe, submit,
   validate, and stop before host execution.
3. Record pack hash, Hermes version/config hashes, latency, and any model repair
   or fallback use in session traces.
4. Keep the direct model harness as a control/evaluation path only.
5. Freeze the selected product runtime after Hermes-context validation.
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
