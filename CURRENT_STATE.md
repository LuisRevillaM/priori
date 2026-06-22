# Current State Snapshot

Date: 2026-06-22

## Repository State

- Branch: `codex/integrated-alpha`
- Latest committed controller checkpoint before this snapshot:
  `4d7ad5e Record N1 post-contract live proof`
- Working tree: scoped N1 proof-integrity closure; existing untracked review packets, audits, test-results, and `docs/learnings.zip` remain outside this snapshot.
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
- Workbench Alpha/Beta 0 product path: controller-verified through a real query-to-result-to-replay loop, manifest-backed match scope, honest provenance labels, host confirmation, canonical match context, and evidence-backed corridor overlays.
- Small-model compiler baseline: frozen at `f9eb5d8`.

The `gpt-4o-mini` compiler lane is now a reference compiler harness and fallback/evaluation control. It is not the target meeting runtime. No more synonym hardening or fresh sealed-set requests should be opened against that lane unless a concrete regression in the reference harness is found.

## Verification Commands

Known green commands at the frozen baseline:

```text
make m1-2-gate-s2-sealed-verify
make m1-2-gate-s2-verify
make m1-2-gate-s2id-verify
make m1-2-gate-s2ie-verify
make m1-2-gate-s0-verify
make m1-2-gate-s2i-verify
make m1-2-verify
PYTHONPATH=src .venv/bin/python -m tqe.verification.n1a
PYTHONPATH=src .venv/bin/python -m tqe.verification.n1b
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

The S2I product Hermes/MCP profile is stricter than the S2 reference compiler
profile. It exposes only:

```text
list_capabilities
search_recipes
describe_capability
submit_query_plan
validate_query_plan
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

There is now a Workbench Alpha/Beta 0 React product surface over the host
orchestrator contracts, plus the older generated manual workshop artifacts:

- React app: `apps/workbench-alpha`
- HTML: `artifacts/m1.2/workshop/index.html`
- Data: `artifacts/m1.2/workshop/manual-workshop-data.json`
- Replay windows: `artifacts/m1.2/workshop/replay-windows/*.json`

The Workbench path is still not the final meeting UI polish layer, but it can
run real approved/manual and experimental corridor queries, confirm execution,
show results, inspect evidence/traces, and open coordinate replay.

## Agent And API Availability

- `OPENAI_API_KEY`: present in the environment at snapshot time; key value was not inspected or logged.
- GPT-5.5 snapshot access: verified through direct Responses API provisioning probes.
- Responses API strict structured output call: verified for `gpt-5.5-2026-04-23`.
- Hermes CLI/local install: verified at `/Users/luisrevilla/.local/bin/hermes`.
- Hermes version: Hermes Agent v0.17.0 (2026.6.19), upstream `2b3a4f0a`.
- Hermes auth: `openai-codex` logged in via ChatGPT/Codex subscription device auth under `HERMES_HOME=/Users/luisrevilla/.hermes-priori`.
- Hermes model config: provider `openai-codex`, default `gpt-5.5`, reasoning effort `xhigh`.
- MCP support for Hermes: tactical stdio MCP adapter is connected and verified through a real Hermes session that lists/searches/describes capabilities, submits a seeded experimental plan, validates it, and stops before execution.
- Frontier freeze: `delivery/m1.2/frontier-runtime-freeze.json`.
- Freeze status: `FROZEN_PENDING_FINAL_INDEPENDENT_EVALUATION`.
- Freeze SHA-256: `554f7415c3f5a08f7508f8fa3a168c0866c4f880c61594d59cb474c2a4d057bb`.
- Freeze report: `artifacts/m1.2/s2i-e-frontier-freeze-report.json`.
- Freeze report SHA-256: `bb9078c15523d45036570923f691aed901ac724acc41e419f1409f11f6f8f570`.
- Important identity boundary: direct Responses API probes returned exact model `gpt-5.5-2026-04-23`; Hermes sessions currently report the product alias `gpt-5.5`, not the exact snapshot.
- Final independent evaluation remains required before S3 acceptance. S2I-B probes and S2I-D live Hermes authoring are provisioning/authoring proof, not sealed acceptance.

## S2I-A Tactical Knowledge Pack

Implemented and controller-verified for the frontier/Hermes path:

- JSON: `generated/tactical-knowledge-pack.json`
- Markdown: `generated/tactical-knowledge-pack.md`
- Pack semantic SHA-256: `fd6d0843d32cc9632bc864b3dad11af4fea060fa2a5fd827196b3458af37b7a0`
- Pack file SHA-256: `7cf720c8210b1d81f12574c5c8299a1dc309930eb1ce17f8eb934d8814119962`
- Markdown file SHA-256: `2e65fec4741dd6ab29e87a6d31364206ac5dbf6dbc47ae2d1db9e59d42e179e7`
- Verification: `make m1-2-gate-s2i-verify`
- Local verification report:
  `docs/reviews/2026-06-21-m1-2-s2i-a-local-verification.md`

The pack is generated from source hashes and distinguishes the current S2
reference-harness tool surface from the S2I target Hermes/MCP allowlist. The S2I
target keeps `execute_query_plan` and `host_confirm_bound_plan` host-only.
`search_recipes` is implemented as a bounded schema-validated dispatcher tool.

## S2I-C Tactical MCP Integration

Controller-verified:

- Report: `artifacts/m1.2/s2i-c-mcp-integration-report.json`
- Local review: `docs/reviews/2026-06-21-m1-2-s2i-c-mcp-integration.md`
- Verification: `make m1-2-gate-s2ic-verify`
- Result: `12 pass / 0 fail`
- MCP server: `src/tqe/workshop/mcp_server.py`
- Hermes MCP server name: `priori_tactical`
- Hermes session: `20260621_212207_0f45e6`
- Draft plan: `draft_92769e17bb25b809`
- Bound plan: `bound_7094041d9225ea8c`
- Product allowlist excludes `execute_query_plan`, `host_confirm_bound_plan`,
  arbitrary filesystem access, terminal access, raw-data dumps, resources, and
  prompts.

The proof is intentionally bounded. It proves Hermes can use the Tactical MCP
adapter to submit and validate a seeded experimental plan through the host
boundary, then stop before execution. It does not yet prove fully autonomous
natural-language plan drafting from summary-only context.

## S2I-D Unseeded Hermes Authoring

Controller-verified:

- Report: `artifacts/m1.2/s2i-d-unseeded-hermes-report.json`
- Local review: `docs/reviews/2026-06-21-m1-2-s2i-d-unseeded-hermes-authoring.md`
- Verification: `make m1-2-gate-s2id-verify`
- Result: `20 pass / 0 fail`
- Hermes provider/model: `openai-codex` / `gpt-5.5`
- Reasoning effort: `xhigh`
- Historical S2I-D Tactical Knowledge Pack file SHA-256:
  `5bf10d06011c3c31cff18da6b02d30d6f68d6b15ed32ff99cd2646f3b865b6af`
- Hermes config SHA-256:
  `e6eb64649a9880f318c669ceb00844b9ff2f03360a4ffd877c3c2b1cf0eff237`

Live unseeded runs:

- `20260621_220512_1d38ec`: "Find possession anchors with any progressive
  corridor" -> `bound_2179b7a023359695`, default `5.0m` progression and `0.4s`
  duration.
- `20260621_221026_2eacf0`: "Find corridors progressing at least 12 metres,
  remaining open for 0.8 seconds" -> `bound_a622811f41c9f5d0`, `12.0m`
  progression and `0.8s` duration.

S2I-D required one knowledge-surface repair: `describe_capability` now describes
recipe IDs and returns a declarative authoring contract derived from checked-in
recipe documents. This is not tactical runtime logic and does not expose host
execution.

## S2I-E Frontier Configuration Freeze

Controller-verified:

- Freeze artifact: `delivery/m1.2/frontier-runtime-freeze.json`
- Freeze report: `artifacts/m1.2/s2i-e-frontier-freeze-report.json`
- Local review: `docs/reviews/2026-06-22-m1-2-s2i-e-frontier-freeze.md`
- Verification: `make m1-2-gate-s2ie-verify`
- Result: `19 pass / 0 fail`
- Product route: Hermes Agent over local stdio Tactical MCP.
- Provider/model: `openai-codex` / `gpt-5.5`.
- Reasoning effort: `xhigh`.
- Direct API control route exact returned model: `gpt-5.5-2026-04-23`.
- Hermes exact snapshot status: Hermes session metadata reports the alias `gpt-5.5` only.
- Frozen tool allowlist: `list_capabilities`, `search_recipes`, `describe_capability`, `submit_query_plan`, `validate_query_plan`, `inspect_result`, `inspect_non_match`, `retrieve_replay_window`.
- Host-only tools remain absent: `host_confirm_bound_plan`, `execute_query_plan`, `record_feedback`, `compare_query_versions`, `save_experimental_recipe`.

The freeze intentionally does not claim final sealed acceptance. It fixes the target route and evidence hashes so the next independent evaluation can be run against a stable frontier configuration.

## Known Gaps After S2I-E

- Initial high/xhigh comparison has run outside full Workbench context and
  currently recommends `xhigh`; final product-runtime acceptance still needs the
  post-freeze sealed path.
- The old small-model S2 regression lane remains useful as control coverage, but
  it is no longer a frontier-runtime acceptance blocker.
- No final sealed acceptance set has been run against the intended frontier/Hermes path.

## N1 Novel Composition Proof

Frozen hero question:

> Show possessions where a progressive corridor opens within four seconds of possession starting, remains available for at least 0.8 seconds, and the ball enters that corridor's destination region within five seconds of the corridor opening.

N1A local expressibility is green:

- Verifier: `src/tqe/verification/n1a.py`
- Command: `PYTHONPATH=src .venv/bin/python -m tqe.verification.n1a`
- Result: `8 pass / 0 fail`
- Local candidate emits real generic results and uses `possession_segment`,
  `geometric_progressive_corridor_from_anchor_set`,
  `relation_destination_entry`, `exists`, and `eq`.

First live Hermes attempt failed honestly:

- Session: `20260622_131836_38c3fb`
- Draft: `draft_412f54700786817a`
- Bound: `bound_a4cdbc77075c85e7`
- Failure: validated plan later failed execution because `analysis_rate_hz`
  was absent, and it compared `entry_status` to `DESTINATION_ENTERED` instead
  of `PASS`.

N1B capability-contract correction is controller-verified:

- Verifier: `src/tqe/verification/n1b.py`
- Command: `PYTHONPATH=src .venv/bin/python -m tqe.verification.n1b`
- Result: `9 pass / 0 fail`
- Failed draft fixture:
  `config/evaluation/n1b_failed_hermes_draft_412f54700786817a.json`
- Report: `artifacts/n1b/n1b-verification-report.json`
- Contract change: host runtime globals are injected, and
  `relation_destination_entry.entry_status` now exposes `PASS`, `FAIL`, and
  `UNKNOWN` as explicit allowed values.
- Validation now rejects the exact failed draft with
  `compare_value_not_allowed` before execution.
- Additional proof-integrity checks now exercise a missing-ball-evidence fixture
  that propagates `UNKNOWN` through the generic destination-entry signal, and
  scan executor `RuntimeParameters` accesses so every accessed name is declared
  by host defaults or a checked-in recipe.

Post-N1B live Hermes proof is green:

- Session: `20260622_141849_63e2a6`
- Draft: `draft_26912b2c452106e8`
- Bound: `bound_f619f6c9677a4d2a`
- Bound hash:
  `f619f6c9677a4d2afdddcd72752ff9e5799b5fc7f2063aae5d0cf5a2104b4c76`
- Structural fingerprint:
  `cd0a6b43b779ed63ec444a3adb5063d898517ac7aad8d7b1bc43ee73fe51893c`
- Execution: `exec_5466f201a479ba0f`
- Result count: `64`
- First cache-aware execution: `MISS`, then `HIT`
- First replay: `replay_63574966cd34b86d`
- Review: `docs/reviews/2026-06-22-n1-post-n1b-live-hermes-result.md`

This is a backend engine proof of the novel-composition loop. It does not claim
the final Workbench experience is already polished around that loop.
The enum-domain claim is currently scoped to catalog outputs that explicitly
declare `allowed_values`, especially `relation_destination_entry.entry_status`.
The first live result's `time_to_entry_seconds=0.0` means the ball was already
present in the corridor destination region at the corridor open frame, not that
a later post-open transition was proven.

N1C proof integrity is green:

- Verifier: `src/tqe/verification/n1c.py`
- Command: `make n1c-verify`
- Result: `8 pass / 0 fail`
- Manifest: `artifacts/n1c/n1c-canonical-freeze-manifest.json`
- Manifest SHA-256: `423b80651cf53c2850c0558ed12c1334b703eb44946572c5dad48cbda2ffcd12`
- Report: `artifacts/n1c/n1c-verification-report.json`
- Report SHA-256: `7599dea004f267e9762f575e997e0f50f41b640f9daedba0fcada9eeeb94fcaa`
- N1C adds a canonical provenance manifest, an end-to-end synthetic
  `relation_destination_entry` PASS/FAIL/UNKNOWN fixture through actual bound
  node execution, proof that `entry_status == PASS` preserves UNKNOWN, runtime
  enum-domain enforcement for declared enum outputs, and `entry_mode` evidence:
  `PRESENT_AT_OPEN`, `ENTERED_AFTER_OPEN`, `NOT_ENTERED`, `UNKNOWN`.

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

## Next Roadmap State

The immediate frontier/product milestone is exposing the proven N1 loop honestly
in Workbench. The broader S2I-F final independent evaluation remains the formal
frontier acceptance gate. Workbench Alpha continues as the visible product path.

The Workbench N1 exposure should:

1. Preserve strict provenance: `HERMES_NOVEL_COMPOSITION`, not manual preset.
2. Keep Hermes unable to confirm or execute.
3. Show the typed interpretation and require host confirmation.
4. Run the deterministic execution path with cache status.
5. Surface evidence, PASS traces, and coordinate replay for real results.

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
