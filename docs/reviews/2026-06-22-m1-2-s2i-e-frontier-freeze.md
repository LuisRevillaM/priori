# M1.2 S2I-E Frontier Configuration Freeze

## Decision

Controller-verifies S2I-E as implemented and locally passing. This is a configuration freeze, not final sealed acceptance.

## Evidence

- Freeze artifact: `delivery/m1.2/frontier-runtime-freeze.json`
- Freeze SHA-256: `b072b8006ae60aba64e3a564d983dae30effbfccdb5ec091c2c1bcb001cd11b9`
- Verification report: `artifacts/m1.2/s2i-e-frontier-freeze-report.json`
- Verification report SHA-256: `a55ae56fed08f1a379e85a9712e8de46ddcc603742101653d0e403571f4709d2`
- Command: `HERMES_HOME=/Users/luisrevilla/.hermes-priori CODEX_HOME=/Users/luisrevilla/.codex make m1-2-gate-s2ie-verify`
- Result: 17 passed, 0 failed

## Frozen Route

- Product route: Hermes Agent over local stdio Tactical MCP.
- Provider: `openai-codex`.
- Hermes configured model: `gpt-5.5`.
- Reasoning effort: `xhigh`.
- Toolset: `priori_tactical`.
- Auth route: ChatGPT/Codex subscription login.

Direct Responses API provisioning/control probes returned exact model `gpt-5.5-2026-04-23` and verified strict structured output plus high/xhigh reasoning. Hermes session metadata reports only the product alias `gpt-5.5`, so exact snapshot identity is not claimed for Hermes sessions.

## Boundary

Hermes-visible MCP tools remain exactly:

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

Host-only tools remain outside Hermes:

```text
host_confirm_bound_plan
execute_query_plan
record_feedback
compare_query_versions
save_experimental_recipe
```

Resources and prompts are disabled. Filesystem, terminal, raw-data, SQL, Python, execution, and host-confirmation surfaces are not exposed through the Tactical MCP adapter.

## Remaining Gate

S2I-E leaves final independent evaluation pending. S2I-B probes and S2I-D unseeded live authoring are accepted as provisioning and authoring evidence, not sealed acceptance. S3 remains blocked until a fresh independent final evaluation passes against this frozen route, and Workbench Alpha proves the query-to-replay path.
