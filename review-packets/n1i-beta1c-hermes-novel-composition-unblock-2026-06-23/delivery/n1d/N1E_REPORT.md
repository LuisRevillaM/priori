# N1E — Live Hermes Origin Re-run

Date: 2026-06-22

## Decision

**BLOCKED.** The faithful deploy-side N1E compile ran against the Render runtime, but Hermes returned a typed clarification instead of an executable novel plan. No prompt tuning, vocabulary changes, local general-agent workaround, or fabricated origin evidence was used.

Beta 1C remains blocked.

## Runtime Path

The protected deploy runner was added behind:

```text
ENABLE_N1E_RUNNER=1
N1E_RUN_TOKEN=<runner token>
```

It ran inside the deployed Render service:

```text
service: priori-integrated-alpha
deploy commit: 9cac5a6a450177cdfdbec1b180c64ba3131464d0
Hermes project: /opt/hermes-agent
Hermes version: Hermes Agent v0.17.0 (2026.6.19) · upstream 5937b951
Python: /opt/hermes-agent/venv/bin/python
toolset: mcp-priori_tactical
provider: openai-codex
model: gpt-5.5
```

The runner used the existing Workbench compile contract:

```text
python -m tqe.workshop.hermes_invocation probe --toolset mcp-priori_tactical
python -m tqe.workshop.hermes_invocation interpret --provider openai-codex --model gpt-5.5 --toolset mcp-priori_tactical --prompt <frozen Workbench prompt>
```

## Result

Job:

```text
n1e_736b1f4814444f45
```

Status:

```text
failed
```

Concrete failure:

```text
Hermes did not return an executable plan: CLARIFICATION_REQUIRED
```

Recovered origin bundle:

```text
delivery/n1d/n1e-origin-bundle.json
local sha256: 4a5ec3ec1f974930ae2b6857679f7a50bdd5c0d5bb33558e198bc797f9e2a649
server-side bundle sha256 before API reserialization: befc2d0fae799519c031433d9fb6645d3838355690348b209a0924e0349a0f81
recovered job id: n1e_recovered_20260623_025323_a63774
session id: 20260623_025323_a63774
```

The byte hashes differ because the API returns a JSON reserialization of the server-side file. The committed local bundle is valid JSON and contains the recovered Hermes session trace.

## Hermes Decision

Hermes returned:

```json
{
  "outcome": "clarify",
  "recipe_id": null,
  "draft_plan_id": null,
  "bound_plan_id": null,
  "bound_plan_hash": null,
  "clarification_dimensions": [
    "match_ids",
    "periods",
    "perspective_team_role"
  ],
  "clarification_questions": [
    "Which match_ids should the default invocation bind to?",
    "Which periods should be included?",
    "Should the perspective_team_role be \"home\" or \"away\"?"
  ],
  "stopped_before_execution": true
}
```

It also reported that no approved recipe exactly matches the requested possession-anchored progressive corridor plus destination-region ball-entry concept, and that the closest support requires an experimental typed plan. However, it did not produce a validated draft.

## Tool Trace

The recovered bundle contains a persisted Hermes session trace. The ordered MCP calls were:

```text
mcp_priori_tactical_list_capabilities
mcp_priori_tactical_search_recipes
mcp_priori_tactical_search_recipes
mcp_priori_tactical_describe_capability
mcp_priori_tactical_describe_capability
mcp_priori_tactical_describe_capability
mcp_priori_tactical_search_recipes
mcp_priori_tactical_describe_capability
mcp_priori_tactical_describe_capability
mcp_priori_tactical_describe_capability
mcp_priori_tactical_submit_query_plan
mcp_priori_tactical_submit_query_plan
```

Hashes:

```text
ordered_tool_call_trace_sha256: 818d3636966f497e4da07ac91e2cfd13dd7fb1a1e3062a86a8a1081fe305450a
raw_hermes_decision_sha256: 9b27b511d2249e0bf62d92d3aa126d28eab3369db13d9842a65cca8bd0cce0d6
```

Hermes called `submit_query_plan`, but it never produced a valid submitted draft handle or reached `validate_query_plan`.

## Verification

`n1d1-verify` now consumes the recovered bundle and still fails closed:

```text
attestation_status: BLOCKED
blocking_reasons:
  - n1d1.origin_compile_tools_present
  - n1d1.augmentation_diff_allowed
```

Interpretation:

* `n1d1.origin_trace_persisted` is now satisfied by the recovered bundle.
* `n1d1.origin_compile_tools_present` remains blocked because the trace does not contain a successful `validate_query_plan` call.
* `n1d1.augmentation_diff_allowed` remains blocked because no Hermes-submitted draft exists, so there is no valid base plan to augment with exactly `destination_entry_mode` and `destination_time_to_entry_seconds`.

## Boundary

This is a good failure, not an infrastructure failure:

* Render had `/opt/hermes-agent`.
* The frozen MCP tool surface probed successfully.
* The paid Hermes compile returned structured output.
* The origin trace was recovered and committed.
* The model chose clarification instead of authoring a valid executable experimental plan.

Per the N1E guardrail, the result is preserved as evidence. No second attempt should be interpreted as the same frozen acceptance run unless it is explicitly rebaselined as a new N1F/N1E2 attempt with its own frozen conditions.
