# N1E — Live Hermes Origin Re-run (STOP-AND-REPORT: not executable in this environment)

Date: 2026-06-22
Baseline: N1D.1 `fe7645c` (attestation BLOCKED). Beta 1C remains blocked.
Scope guardrails honored: no `HERMES_NOVEL_COMPOSITION` exposure; no changes to primitives,
operators, tactical semantics, MCP auth, or Hermes prompts.

## Headline

Task 9 is explicit: *"If Hermes selects a recipe, fails, or produces unsupported/invalid output,
preserve the failure honestly and stop. Do not tune prompts or vocabulary."* The live re-run cannot
be performed faithfully in this environment, so I stopped without fabricating a session or altering
prompts. **No VERIFIED attestation was produced. N1D.1 stays BLOCKED; Beta 1C stays blocked.**

## What I verified (no model call was made)

The frozen N1 origin was authored by **Hermes Agent v0.17.0** via provider `openai-codex`,
model `gpt-5.5`, toolset `mcp-priori_tactical`, with a pinned `system_prompt_hash`
(see `delivery/m1.2/frontier-runtime-freeze.json` and the N1C manifest).

The workbench's frozen compile path (`src/tqe/workshop/app_service.py:hermes_interpret_request`)
invokes the agent as:

```
hermes interpret --provider openai-codex --model gpt-5.5 --toolset mcp-priori_tactical --prompt <frozen prompt>
hermes probe --toolset mcp-priori_tactical
```

and is gated by `WORKBENCH_HERMES_ENABLED=1`.

Findings in this environment:
- `hermes` resolves to `/Users/luisrevilla/.local/bin/hermes` — the user's **personal Hermes Agent
  v0.17.0** (general assistant: `chat`, `model`, `slack`, `cron`, `memory`, `mcp`, …).
- It has **no `interpret` subcommand** and **no `probe` subcommand** (argparse rejects both). The
  frozen workbench compile contract is therefore **not reachable** through the installed binary.
- `WORKBENCH_HERMES_ENABLED` is unset (live model mode is disabled, as the Beta 1A tests assert via
  `MODEL_UNAVAILABLE`).
- The `priori_tactical` MCP server *is* registered in `~/.hermes-priori/config.yaml`
  (`mcp_servers.priori_tactical → tqe.workshop.mcp_server`), so the tool surface exists — but the
  dedicated frozen compile CLI does not.

## Why I did not force a run

Reproducing the compile via the agent's general interface
(`hermes -z "<prompt>" -t mcp-priori_tactical -m gpt-5.5 --provider openai-codex --yolo`) would require:
1. **Supplying a compile system prompt** to turn the general agent into the tactical compiler — that
   is altering Hermes prompts, which the N1E baseline and Task 9 explicitly forbid, and it would not
   match the pinned `system_prompt_hash` (so the result would not be a faithful frozen-origin re-run).
2. A **paid, outward-facing frontier call on the user's personal Codex account**, running their
   personal agent with `--yolo` tool auto-accept.
3. Driving MCP `submit_query_plan/validate/confirm/execute` from that personal agent.

None of that produces a faithful, in-contract origin, and items 1–2 violate the guardrails. So per
Task 9 I preserved the failure and stopped. I did **not** fabricate a session, decision, or trace.

## Current proof state (unchanged)

- `n1d1-verify`: **BLOCKED** (origin trace not persisted; N1D plan ≠ Hermes draft + the two aliases).
- `n1d-verify`: pass 12/12. `n1c-verify`: pass 8/8.
- Entry-mode presentation fix from N1D.1 remains in place (PRESENT_AT_OPEN honest at t=0.0).

## Remediation (the intended N1E environment)

The frozen compile contract exists in the **deploy/runtime environment** provisioned by
`scripts/bootstrap-hermes.sh` (installs `/opt/hermes-agent` exposing the `interpret`/`probe`
compile CLI, registers the `priori_tactical` MCP, pins `gpt-5.5`/`openai-codex` and the frozen system
prompt). Run N1E there:
1. `WORKBENCH_HERMES_ENABLED=1`, with the deploy Hermes compile wrapper on PATH.
2. Re-run the exact frozen hero question; persist the origin trace (session id, question + hash,
   ordered MCP tool calls, raw structured decision, submitted draft + hash).
3. Confirm Hermes authors a structurally novel experimental plan (not a recipe selection).
4. Re-pin N1D on the Hermes-submitted draft + exactly `destination_entry_mode` and
   `destination_time_to_entry_seconds`; re-run the host-authority path; re-freeze.
5. `make n1d1-verify` → target VERIFIED.

## Option A attempt (deploy/runtime environment) — outcome: BLOCKED, stopped per Task 9

Controller approved Option A (run in the deploy environment; paid frontier calls authorized; do **not**
use the local general-agent workaround; if the deploy is unavailable or does not expose the frozen
contract, stop and report — do not relax). Outcome:

- **Frozen compile source absent locally**: `/opt/hermes-agent` and `/var/data` do not exist in this
  sandbox; `WORKBENCH_HERMES_PYTHON` (`/opt/hermes-agent/venv/bin/python`) is absent. The only local
  `hermes` is the personal agent without the `interpret`/`probe` contract (above).
- **Deploy reachable and contract configured**: `https://priori-integrated-alpha.onrender.com`
  `/api/health` → ok; `/api/bootstrap` → `model.available: true`, `status: HERMES_CONFIGURED`
  ("each interpretation is probed and validated at request time"). So the frozen compile contract
  exists on the deploy host.
- **But the deploy does not EXPOSE the origin trace for export**:
  - `/api/interpret` (product response) does not carry the raw model decision or the ordered MCP
    tool-call trace; those are written to server-side `artifacts/.../hermes-traces/` files.
  - There is no artifact/trace retrieval endpoint: `/api/hermes-trace`, `/api/origin`, `/api/export`,
    `/api/n1`, `/api/retrieve_replay_window` → 404; concrete artifact `.json` (e.g. a hermes-trace or
    an execution handle) → 404 `STATIC_NOT_FOUND`. The `/artifacts/.../` `200` is only the SPA
    `index.html` fallback (`content-type: text/html`), not a file listing.
  - No shell/file access to the Render host is available from this sandbox to extract the trace bundle.

Therefore the deploy **has** the frozen contract but **does not expose** its origin-trace artifacts
in any way I can export into the repo. Firing the paid `/api/interpret` compile on the deploy would
author a session whose raw decision + tool-call trace I could not retrieve — producing no in-repo
VERIFIED attestation and wasting a paid call. Per the controller's explicit fallback, I stopped and
did not relax N1E. **No fabrication. No prompt tuning. No local general-agent workaround.**

## What is required to complete N1E faithfully

A runner that has BOTH (1) the frozen compile contract (`hermes interpret --toolset
mcp-priori_tactical`, `--provider openai-codex --model gpt-5.5`, frozen system prompt, via
`scripts/bootstrap-hermes.sh` / `/opt/hermes-agent`) AND (2) write access to this repo (or a defined
export channel). Concretely, one of:
- a job executed **on the deploy host** (Render SSH/one-off job) that runs the frozen compile + the
  host-authority path, persists the origin trace, and exports the bundle below into the repo; or
- a locally provisioned `/opt/hermes-agent` compile environment with the same frozen contract.

The exported bundle must contain: raw model decision; ordered MCP tool-call trace; submitted Hermes
draft + draft hash; host-augmented N1D plan with exactly the two aliases
(`destination_entry_mode`, `destination_time_to_entry_seconds`); validate/confirm/execute/inspect/
replay IDs; and the `n1d1-verify` VERIFIED attestation + hashes. Then re-pin N1D and re-run
`make n1d1-verify` → VERIFIED.

No fabrication was performed. N1D.1 remains BLOCKED; Beta 1C remains blocked.
