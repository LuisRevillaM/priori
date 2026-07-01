# External Reviewer Prompt

Please review the attached S2I-E packet strictly as the **M1.2 frontier configuration freeze**.

The core question is:

```text
Is the intended Hermes/frontier product route now frozen clearly enough to run the final independent evaluation without further configuration or architecture changes?
```

Review facts:

- Product route: Hermes Agent over local stdio Tactical MCP.
- Provider/model/reasoning: `openai-codex` / `gpt-5.5` / `xhigh`.
- Auth: ChatGPT/Codex subscription login.
- Direct API control route returned exact `gpt-5.5-2026-04-23`.
- Hermes session metadata reports alias `gpt-5.5` only.
- MCP tool allowlist:

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

- Host-only tools are absent:

```text
host_confirm_bound_plan
execute_query_plan
record_feedback
compare_query_versions
save_experimental_recipe
```

Local controller verification:

```text
S2I-E: 17/0
S2I-D: 20/0
S2I-A: 16/0
S0: 17/0
unit tests: 27 OK
git diff --check: clean
```

Important boundary:

This packet does **not** claim final independent acceptance. It freezes the route so the final evaluation can be run. S3 remains blocked until that evaluation passes and Workbench Alpha query-to-replay proof is accepted.

Please respond with one of:

```text
APPROVE_FRONTIER_FREEZE_FINAL_EVAL_REQUIRED
APPROVE_WITH_REQUIRED_CHANGES_BEFORE_FINAL_EVAL
REJECT_KEEP_FINAL_EVAL_BLOCKED
```

If approved, please provide either:

1. a fresh final independent evaluation set for the frozen route; or
2. exact instructions for how the local controller should generate/run that final evaluation without contaminating it.

Please do not expand this review into Workbench Alpha, UI polish, runtime semantics, new primitives, or new tactical families unless you find a concrete S2I-E blocker.
