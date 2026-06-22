# M1.2 S2I-C Tactical MCP Integration Review

Decision: **PASS_CONTROLLER**

S2I-C connects Hermes to the tactical query workshop through a local stdio MCP
adapter while preserving the host-owned execution boundary.

## Evidence

- MCP server: `src/tqe/workshop/mcp_server.py`
- Verification command: `make m1-2-gate-s2ic-verify`
- Verification report: `artifacts/m1.2/s2i-c-mcp-integration-report.json`
- Result: `12 pass / 0 fail`
- Hermes MCP server: `priori_tactical`
- Live Hermes session: `20260621_212207_0f45e6`
- Draft plan: `draft_92769e17bb25b809`
- Bound plan: `bound_7094041d9225ea8c`

## Accepted Claims

- Hermes can discover exactly the S2I product allowlist:
  `list_capabilities`, `search_recipes`, `describe_capability`,
  `submit_query_plan`, `validate_query_plan`, `inspect_result`,
  `inspect_non_match`, and `retrieve_replay_window`.
- Host-only operations are not visible through MCP:
  `host_confirm_bound_plan`, `execute_query_plan`, `record_feedback`,
  `compare_query_versions`, and `save_experimental_recipe`.
- MCP resources and prompts are disabled.
- A real Hermes session can list/search/describe capabilities, submit a seeded
  experimental query plan, validate it, and stop before host execution.
- The Tactical MCP adapter delegates to the existing host/workshop dispatcher
  rather than duplicating tactical runtime semantics.

## Explicit Non-Claims

- This does not prove fully autonomous natural-language plan drafting from
  summaries alone. The successful live Hermes validation supplied the
  experimental corridor plan JSON as the seed document.
- This does not prove Workbench Alpha, final sealed acceptance, S3 feedback
  loops, UI polish, or a second tactical family.

## Next

Start Workbench Alpha 1 against the host application service. Keep MCP as the
Hermes adapter path, and do not expose host confirmation or execution to Hermes.
