# M1.2 S2I-E Frontier Freeze Review Packet

## What This Is

This is an `inspection_packet_only` for an external reviewer who does not have repo access.

It packages the S2I-E frontier configuration freeze for M1.2: the intended Hermes product route, MCP boundary, knowledge/context hashes, local verification reports, and the exact commit patch that introduced the freeze gate.

## Review Scope

Primary scope:

- Commit under review: `93ba710 Freeze frontier Hermes configuration`
- Milestone: `M1.2 — Grounded Tactical Query Workshop`
- Slice: `S2I-E_frontier_configuration_freeze`

Current repo `HEAD` at packet build time was `87b2441 Harden Workbench Alpha R1 acceptance`. That later Workbench commit is out of scope for this packet except as repo-state context.

## What Changed

S2I-E added:

- `delivery/m1.2/frontier-runtime-freeze.json`
- `artifacts/m1.2/s2i-e-frontier-freeze-report.json`
- `src/tqe/verification/m1_2_gate_s2ie.py`
- `make m1-2-gate-s2ie-verify`
- roadmap/status updates naming the frontier route as frozen but final independent evaluation as still pending

S2I-D verification was also repaired to read the durable Hermes `validate_query_plan` session result instead of requiring transient bound-plan handle files.

## What Is Real

- Hermes is installed and authenticated locally through `openai-codex` ChatGPT/Codex subscription login.
- The frozen product route is Hermes Agent over local stdio Tactical MCP.
- Configured Hermes provider/model/reasoning: `openai-codex` / `gpt-5.5` / `xhigh`.
- The Tactical MCP allowlist is restricted to:

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

- Host-only execution/confirmation/feedback/recipe-save tools remain absent from Hermes.
- S2I-D has two recorded live Hermes sessions that authored and validated unseeded experimental plans, then stopped before execution.

## Important Identity Boundary

Direct Responses API control probes proved exact model `gpt-5.5-2026-04-23`.

Hermes session metadata reports only product alias `gpt-5.5`. This packet does not claim Hermes exposes the exact snapshot ID in session metadata.

## Validation Run

Locally verified before commit:

- `make m1-2-gate-s2ie-verify`: 17 pass / 0 fail
- `make m1-2-gate-s2id-verify`: 20 pass / 0 fail
- `make m1-2-gate-s2i-verify`: 16 pass / 0 fail
- `make m1-2-gate-s0-verify`: 17 pass / 0 fail
- `make test`: 27 tests OK
- `git diff --check`: clean

See `validation-output.md` and copied JSON reports under `artifacts/`.

## Not Proven

- Final independent sealed acceptance is not proven.
- S3 remains blocked until a fresh independent evaluation passes against the frozen route.
- Workbench Alpha query-to-replay proof is tracked separately and is not reviewed here.
- The packet cannot rerun local Hermes sessions or Make targets without the full repo, Hermes home, credentials, and local data.

## Review Map

- Start here: `scope.md`
- Freeze artifact: `artifacts/frontier-runtime-freeze.json`
- Freeze report: `artifacts/s2i-e-frontier-freeze-report.json`
- S2I-D live-authoring report: `artifacts/s2i-d-unseeded-hermes-report.json`
- Verifier source: `source-excerpts/m1_2_gate_s2ie.py`
- Commit patch: `diffs/93ba710-freeze-frontier-hermes-configuration.patch`
- Gaps: `known-gaps.md`
- Requested reviewer action: `external-reviewer-prompt.md`
