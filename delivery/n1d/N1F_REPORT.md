# N1F — Scoped Hermes Origin Re-run

## Decision

**BLOCKED.** N1F did not produce a VERIFIED Hermes-origin novel-composition attestation.

The scoped second faithful deploy-side Hermes turn ran with the demo canonical invocation binding, preserved the N1E clarification turn, submitted a draft, and stopped before host confirmation/execution because validation returned a capability gap:

```text
relation_destination_entry_classification is not agent-authorable for the possession-start corridor plan
```

No tactical semantics, primitives, operators, MCP auth, Hermes prompts, or model configuration were changed.

## Scope Clarification

The clarification answer was applied as invocation binding only, not tactical semantics:

```json
{
  "match_ids": ["J03WOY"],
  "periods": ["firstHalf"],
  "perspective_team_role": "home"
}
```

Clarification answer SHA-256:

```text
b27f73521531bb2f0c9aa94ba5860ba350d5367f83b36e4a0f3094468fc0b926
```

## Origin Chain

- Original hero question SHA-256: `4c0341c50842ea253a19959ca656a36b97ef4fa3bfb181db60f8a8bd68031fcf`
- Clarified second-turn request SHA-256: `5fa66c8976623f268604a61208dfef9f59dea6795220c4a046070252384ea590`
- Frozen compile prompt SHA-256: `b4047ac29b90f869b0d43964d849b909b20009e76ef0389207590f693d6d8610`
- First turn session: `20260623_025323_a63774`
- First turn outcome: `clarify`
- Second turn session: `20260623_040550_a65c8b`
- Second turn outcome: `capability_gap`
- Submitted draft id: `draft_36059f854063aa7f`
- Submitted draft hash: `ba4eebafd0cd474cfa80ef6bcd72fe374cc7f8ae4ce714c714752aadadd6ccaf`
- Raw Hermes decision SHA-256: `780992be95edf0c887317e6a43f894aaf01bc8e3aad1a9aa7f66833e4620e241`
- Ordered MCP tool-call trace SHA-256: `4fbad2ced941811af7c04ca48343130ea8bf9563fcad4bbbe060bdd66a84a665`

The complete preserved bundle is:

```text
delivery/n1d/n1f-origin-bundle.json
```

Downloaded bundle file SHA-256:

```text
062cfc747180dd89107afb0dbe19eb3fb30c2ac8331afd4d58a6ecec55e30d2f
```

Canonical stable JSON SHA-256:

```text
543c46b62c55e6a06309c783d3d837bfabee793333b198062b92b0006cc88b14
```

Render status endpoint bundle SHA-256:

```text
9a1ad9afbdcfedca66d0ae1e64900686809e12a20603b705cedb8048fc979699
```

Note: the status endpoint hash is computed over the raw file on the Render host. The downloaded API response is JSON-reserialized by the service before being written locally, so the byte-level file hash differs; the canonical stable JSON hash is the repo-side identity used by N1D.1.

## Hermes Capability Gap

Hermes returned these structured capability gaps:

```text
1. No approved recipe matches possession-start progressive corridor availability plus destination-region ball entry.
2. The possession-start corridor recipe can detect geometric progressive corridor availability from ordinary possession anchors, but destination-region entry classification is not agent-authorable for that recipe.
3. The experimental destination-entry capability exists only in the opposite-corridor-after-shift recipe path, which changes the requested tactical semantics from possession-start anchoring to wide-entry/block-shift anchoring.
```

The ordered MCP calls include `submit_query_plan` and `validate_query_plan`. No host confirmation or execution was performed.

## N1D.1 State

`make n1d1-verify` remains blocked, as intended:

```text
{"attestation_status": "BLOCKED", "blocking_reasons": ["n1d1.augmentation_diff_allowed"]}
```

The blocking reason is expected because the current pinned N1D plan is not equal to the Hermes-submitted draft plus exactly the two allowed evidence aliases. The diff includes additional evidence shape changes and one removed alias:

```text
added:
  destination_entry_mode
  destination_entry_status
  destination_observed_window_end_frame_id
  destination_relation_id
  destination_time_to_entry_seconds
  minimum_clearance_m
  target_player_id

removed:
  destination_classification
```

Therefore Beta 1C remains blocked.

## Deploy Evidence

- N1F runner implementation commit: `7044946`
- Deploy-image N1E bundle inclusion commit: `22a56a6`
- Failed-draft persistence commit: `534d51f`
- Tool-trace draft recovery commit: `56921fc`
- Final faithful N1F run deploy: `dep-d8t09snlk1mc73agrlkg`
- Runner-disabled deploy: `dep-d8t0e7b6sc1c73e0aj2g`

Final runner-disabled verification:

```text
/healthz -> 200 ALIVE
/api/n1f/status -> 403 N1E_RUNNER_UNAVAILABLE
```

## Verification

```text
make n1d1-verify
  expected blocked: N1D1_EXIT:2

make n1d-verify
  pass: 12/12

make n1c-verify
  pass: 8/8

PYTHONPATH=src .venv/bin/python -m unittest tests.test_n1d1_attestation tests.test_workbench_beta0_contract
  pass: 9 tests
```

`artifacts/n1c/*` was restored after `make n1c-verify` because that legacy verifier rewrites tracked artifact files.

## Caveat

This is not a product failure. It is an honest model/tool-boundary result: Hermes correctly refused to claim that the requested possession-start destination-entry composition is executable with the current agent-authorable capability surface. The next valid path is to either expose the needed destination-entry primitive as agent-authorable for this plan family, or choose a different novel-composition hero that is expressible by the current safe catalog.
