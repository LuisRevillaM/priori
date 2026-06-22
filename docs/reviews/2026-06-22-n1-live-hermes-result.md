# N1 Live Hermes Novel-Composition Result

Decision: `REJECT_KEEP_N1_BLOCKED`

The live Hermes run did not prove N1. It produced a useful failure after the local N1A repair.

## Frozen Hero Question

> Show possessions where a progressive corridor opens within four seconds of possession starting, remains available for at least 0.8 seconds, and the ball enters that corridor's destination region within five seconds of the corridor opening.

## Live Session

- Session: `20260622_131836_38c3fb`
- Source: `n1_live`
- Model: `gpt-5.5`
- Reasoning effort: `xhigh`
- Tool calls: `17`
- Toolset used: `priori_tactical`
- Tools called:
  - `mcp_priori_tactical_list_capabilities`
  - `mcp_priori_tactical_search_recipes`
  - `mcp_priori_tactical_describe_capability`
  - `mcp_priori_tactical_submit_query_plan`
  - `mcp_priori_tactical_validate_query_plan`

Hermes did not call host confirmation, execution, filesystem, terminal, Python, SQL, or raw-data tools.

## What Passed

- Hermes did not select an existing registered recipe.
- Hermes authored an `EXPERIMENTAL` typed plan.
- The plan used:
  - `possession_segment`
  - `geometric_progressive_corridor_from_anchor_set`
  - `relation_destination_entry`
  - `exists`
  - `eq`
- Host validation returned:
  - Draft plan: `draft_412f54700786817a`
  - Bound plan: `bound_a4cdbc77075c85e7`
  - Bound hash: `a4cdbc77075c85e7d9c6d70ca63f00eb9838f03dd96e265c05b5b78c23996c5c`
- Hermes stopped before execution.

## Blocking Failures

1. The plan omitted required runtime-global parameters.

   Host execution fails before result emission:

   ```text
   KeyError: 'analysis_rate_hz'
   ```

   The validator accepted a plan that the deterministic runtime cannot execute.

2. The plan compared `entry_status` to the wrong enum value.

   The generic capability emits:

   ```text
   PASS
   FAIL
   UNKNOWN
   ```

   Hermes authored:

   ```text
   entry_status == DESTINATION_ENTERED
   ```

   That is schema-valid but semantically wrong. The rule should compare `entry_status == PASS` and let the classification rule emit `DESTINATION_ENTERED`.

## Diagnosis

This is not a broad architecture failure and not a prompt-vocabulary failure. It exposes two missing host contracts:

1. Runtime-required global parameters are not declared strongly enough for Hermes or enforced by validation.
2. Enum domains for capability outputs are not explicit enough for validation to reject impossible comparisons.

## Next Corrective Slice

Open `N1B — Capability Output Domains and Runtime Parameter Contract`.

Required corrections:

- Make runtime-global parameters such as `analysis_rate_hz`, possession-duration, quality, and analysis-gap defaults explicit in either the plan contract or host injection layer.
- Validate that every runtime-required parameter is present before a plan can be marked executable.
- Add an enum domain for `relation_destination_entry.entry_status`: `PASS`, `FAIL`, `UNKNOWN`.
- Reject predicates that compare `entry_status` to tactical labels such as `DESTINATION_ENTERED`.
- Add tests proving the live Hermes-authored invalid plan is rejected before execution.
- Preserve the failed N1 session and do not rerun the frozen hero until N1B is committed and reviewed.

Do not tune Hermes prompts, aliases, or model instructions as the first fix.
