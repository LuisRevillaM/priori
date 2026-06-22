# M1.2 S2I-D Unseeded Hermes Authoring Review

Decision: **PASS_CONTROLLER**

S2I-D proves the intended frontier-agent path at the bounded authoring layer:
Hermes receives football language, discovers tactical knowledge through MCP,
authors an experimental typed plan, submits it, validates it, and stops before
execution.

## Evidence

- Verification: `make m1-2-gate-s2id-verify`
- Report: `artifacts/m1.2/s2i-d-unseeded-hermes-report.json`
- Result: `20 pass / 0 fail`
- Hermes provider: `openai-codex`
- Hermes model: `gpt-5.5`
- Reasoning effort: `xhigh`
- Hermes config hash: `e6eb64649a9880f318c669ceb00844b9ff2f03360a4ffd877c3c2b1cf0eff237`
- Tactical Knowledge Pack hash: `49edb17edfadf7b59150176430cda5bcc394d30110fe7a2e635b40afc9137b1e`

## Live Runs

1. `20260621_220512_1d38ec`
   - Request: find possession anchors with any progressive corridor.
   - Draft: `draft_496efd224daf3c31`
   - Bound: `bound_2179b7a023359695`
   - Parameters: default progression `5.0m`, duration `0.4s`

2. `20260621_221026_2eacf0`
   - Request: find corridors progressing at least `12m`, open for `0.8s`.
   - Draft: `draft_4f4a534a0b4fd356`
   - Bound: `bound_a622811f41c9f5d0`
   - Parameters: progression `12.0m`, duration `0.8s`

The bound plan hashes differ, and the verifier proves the material parameter
delta.

## Accepted Claims

- Prompts did not include a plan document or seeded plan JSON.
- Hermes used only the restricted `priori_tactical` toolset.
- Required discovery tools were used: list, search, describe, submit, validate.
- Host-only tools were not visible or called.
- No filesystem, terminal, Python, SQL, raw-data, confirmation, or execution
  tools were called.
- Both validated plans are `generic` and `bind_only`.
- The MCP adapter remains thin and delegates to the host dispatcher.

## Required Repair

S2I-D initially exposed a real knowledge-surface gap: `search_recipes` returned
recipe IDs, but `describe_capability` could not describe those recipes. The
repair lets `describe_capability` return a recipe authoring contract derived
from existing recipe documents. This is not tactical runtime logic and does not
grant execution authority.

## Next

Freeze the frontier configuration and run the final evaluation set. Workbench
Alpha should continue in parallel against the host application service.
