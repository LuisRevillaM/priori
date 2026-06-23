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

## Open decision for the controller

This environment cannot run the faithful live compile. Choose one:
- **(A) Run N1E in the deploy/runtime environment** with the frozen `hermes interpret` compile
  contract (recommended; only path that yields a faithful, hash-matching origin).
- **(B) Authorize a local live run via the general agent interface** — accepting a paid call on the
  personal Codex account and that it will **not** match the frozen `system_prompt_hash` (not a
  faithful frozen-origin re-run; would need an explicit prompt, which N1E currently forbids).
- **(C) Hold N1E**; keep Beta 1C blocked at the honest N1D.1 BLOCKED state.

No fabrication was performed. Beta 1C remains blocked.
