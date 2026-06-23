# N1H — Scoped Hermes Origin Runner Recovery

Status: `blocked_after_export`
Generated: `2026-06-23T05:05:00+00:00`

## Scope

N1H only repaired the deploy-side runner/export path. It did not change tactical semantics, prompts, model configuration, hero wording, MCP auth, or Workbench UI.

## Diagnosis

The N1G faithful Render run reached Hermes and Hermes returned a draft, but the runner failed with:

```text
Unknown draft-plans handle: draft_d6feb3859f859fec
```

The root cause was split artifact roots:

- the Workbench host ran with `output_root=/var/data/runtime`;
- the Hermes MCP server wrote handles under `TQE_WORKSHOP_OUTPUT_ROOT=${TQE_RUNTIME_ROOT}`;
- the runner tried to read Hermes draft handles from `HERMES_WORKSHOP_ROOT`, whose default was the local relative path `artifacts/m1.2/workshop`.

N1H makes the active server `output_root` the Hermes MCP `TQE_WORKSHOP_OUTPUT_ROOT` for probe and interpret subprocesses, and reads draft/bound handles from the same persistent root.

## Implementation

- `HERMES_WORKSHOP_ROOT` now defaults to `WORKBENCH_HERMES_WORKSHOP_ROOT`, then `TQE_WORKSHOP_OUTPUT_ROOT`, then `TQE_RUNTIME_ROOT`, before falling back to the local artifact path.
- Hermes probe/interpret invocations receive the active server output root through `TQE_WORKSHOP_OUTPUT_ROOT`.
- N1E/N1F runner code resolves Hermes draft handles from the same active root used by host confirmation, execution, inspection, replay, and export.
- If draft-handle lookup fails, the runner can recover the draft document from the persisted `submit_query_plan.arguments.plan_document` trace and draft hash from the `submit_query_plan` tool response.
- The public model interpretation path also passes the active request output root into Hermes handle recovery.

## Local Verification

- `.venv/bin/python -m unittest tests.test_workbench_beta0_contract`: pass, 9 tests.
- `make n1g-verify`: pass, 10/10.
- `make n1c-verify`: pass, 8/8 when run sequentially after restoring generated artifacts.
- `.venv/bin/python -m unittest tests.test_m1_1_runtime tests.test_m1_1_binder tests.test_n1d1_attestation`: pass, 34 tests; N1D.1 remains blocked on the previous origin bundle as expected before a successful fresh origin.

## Render Rerun

- Runtime commit deployed: `dcbe5328a478faa2833f5e108afd37bc3bd55ff7`
- Enable-runner deploy: `dep-d8t13am7r5hc73ecvhmg`
- Runner job: `n1f_2c1a7baed5ef4fad`
- Disable-runner deploy: `dep-d8t17br7uimc73daieig`
- Runner-disabled verification: `/api/n1f/status` returned `403 N1E_RUNNER_UNAVAILABLE`.

Render logs confirm the N1H root fix was active:

```text
subcommand=probe workshop_output_root=/var/data/runtime
subcommand=interpret workshop_output_root=/var/data/runtime
```

The runner exported a failure bundle instead of losing the origin artifact:

- Status file: `delivery/n1d/n1h-faithful-rerun-status.json`
- Origin bundle: `delivery/n1d/n1h-origin-bundle.json`
- Server-reported bundle SHA-256: `a9358a0033341748ff128923ba20ce3cb7d8a34b6b61ed8d4f14873bb9923798`
- Downloaded bundle JSON SHA-256: `004a57655c65c28e45ed363cd6ecbde932124eab656a256597e5d98ce06dc580`

The hash values differ because the API reserializes the stored JSON object when returning it. The bundle content is preserved in-repo.

## Faithful Outcome

Hermes did not return an executable plan:

```text
status=failed_compile
stage=non_plan_outcome
session_id=20260623_050002_1e983b
final_outcome=capability_gap
draft_plan_id=draft_327d06b5dce40827
draft_record_source=handle
```

Hermes attempted multiple `submit_query_plan` calls and eventually produced a draft handle, but its final decision remained a capability gap. The reported gap:

```text
No approved recipe matches possession-start progressive corridor availability with destination-region ball entry.

Closest experimental recipes are insufficient: possession_corridor_availability_v1 detects corridor availability from possession anchors but does not classify destination-region ball entry; opposite_corridor_after_shift_v1 classifies destination entry but anchors on wide-entry/block-shift semantics rather than possession start.

Validation could not bind the authored experimental typed plan because the required catalog primitive/relation/operator for active-ball possession anchor, progressive corridor availability, and ball-enters-corridor-destination-region are not available under the submitted catalog refs; validate_query_plan returned unknown_catalog_ref/unknown_operator and no bound plan.
```

Because Hermes did not produce a valid executable plan, N1H did not add evidence aliases, host-confirm, execute, inspect, retrieve replay, re-pin N1D, or run a VERIFIED N1D.1 attestation.

## Current Blocker

The deploy-side runner/export path is no longer the blocker. The new blocker is that Hermes still cannot author a schema-valid executable AST for the frozen hero using the currently visible catalog contract.

Beta 1C remains blocked.
