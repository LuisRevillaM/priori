# Known Gaps

## Final Independent Evaluation Pending

Classification: `requires_human_decision`

What is missing:

- A fresh independently authored final evaluation set against the frozen S2I-E route.

Why it matters:

- S3 should not begin on the basis of provisioning probes and two live authoring examples alone.

Default boundary:

- S3 remains blocked.

Next action:

- External reviewer should either provide the final evaluation set or approve exact evaluation instructions.

## Hermes Exact Snapshot Alias

Classification: `unknown`

What is missing:

- Hermes session metadata does not expose exact model snapshot ID.

Why it matters:

- Direct Responses API proves `gpt-5.5-2026-04-23`, but Hermes reports only `gpt-5.5`.

Default boundary:

- Claim exact snapshot only for the direct API control route. Claim alias-only model identity for Hermes.

Next action:

- Do not block S2I-E on this unless the reviewer requires provider-level proof beyond Hermes metadata.

## Packet Is Inspection-Only

Classification: `requires_full_repo`

What is missing:

- Full repo, credentials, local Hermes home, canonical data, and runtime artifacts.

Why it matters:

- Reviewer cannot rerun Make gates from this packet alone.

Default boundary:

- Review source excerpts, reports, diffs, and local validation summaries.

Next action:

- If independent rerun is required, perform it in the actual repo environment.

## Workbench Alpha Is Separate

Classification: `not_in_scope`

What is missing:

- Workbench Alpha R1 review and query-to-replay proof.

Why it matters:

- S3 also depends on visible product proof, but this packet only covers Track A frontier configuration.

Default boundary:

- Do not approve S3 from this packet alone.

Next action:

- Review the Workbench packet separately.
