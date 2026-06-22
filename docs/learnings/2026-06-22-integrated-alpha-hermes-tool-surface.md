# Integrated Alpha Hermes Tool Surface

Date: 2026-06-22

## Decision

Workbench `/api/interpret` now has a host-managed Hermes frontier path behind
`WORKBENCH_HERMES_ENABLED=1`, but it fails closed unless the Hermes invocation
exposes the frozen `priori_tactical` MCP tools without forbidden built-in tools.

## Finding

The current Hermes one-shot CLI invocation does not yet provide the required
safe tool surface:

- `--toolsets priori_tactical` does not expose the MCP tools in one-shot mode.
- `--toolsets all` exposes the MCP tools, but also exposes forbidden built-ins
  such as terminal, filesystem, browser, web, and code-execution tools.

Therefore Workbench currently returns `MODEL_UNAVAILABLE` for model mode when
the safe surface cannot be proven.

## Boundary

Do not wire an unsafe `all` toolset into Workbench. The browser still has no MCP
access, and manual mode remains the accepted deterministic path.

## Next Action

Fix Hermes provisioning so a one-shot or programmatic Hermes session can expose
exactly:

```text
mcp_priori_tactical_list_capabilities
mcp_priori_tactical_search_recipes
mcp_priori_tactical_describe_capability
mcp_priori_tactical_submit_query_plan
mcp_priori_tactical_validate_query_plan
mcp_priori_tactical_inspect_result
mcp_priori_tactical_inspect_non_match
mcp_priori_tactical_retrieve_replay_window
```

with no filesystem, terminal, browser, web, Python, SQL, host confirmation, or
execution tools. Then rerun Integrated Alpha:

```text
Workbench /api/interpret
-> host-managed Hermes session
-> validated typed plan
-> human confirmation
-> deterministic execution
-> real result/evidence/replay
```

