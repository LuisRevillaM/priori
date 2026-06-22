# N1 Post-N1B Live Hermes Result

Decision: `APPROVE_N1_BACKEND_ENGINE_PROOF_WITH_REQUIRED_CHANGES_CLOSED`

The post-N1B rerun used the same frozen hero question and the same Hermes tool boundary. Hermes authored and validated a structurally novel experimental plan, stopped before host confirmation/execution, and the controller then executed the validated plan through the host-owned confirmation path.

Opus later reviewed the post-N1B proof and accepted the backend novel-composition loop as genuinely demonstrated, with required integrity cleanups before Workbench exposure. Those cleanups are now recorded here: hash provenance is reconciled, UNKNOWN preservation is exercised by fixture, executor runtime-parameter access has a structural guard, enum-domain scope is documented, and `time_to_entry_seconds=0.0` is labeled honestly.

## Frozen Hero Question

> Show possessions where a progressive corridor opens within four seconds of possession starting, remains available for at least 0.8 seconds, and the ball enters that corridor's destination region within five seconds of the corridor opening.

## Live Hermes Session

- Session: `20260622_141849_63e2a6`
- Source: `n1_live`
- Toolset: `priori_tactical`
- Tools used:
  - `list_capabilities`
  - `search_recipes`
  - `describe_capability`
  - `submit_query_plan`
  - `validate_query_plan`
- Draft plan: `draft_26912b2c452106e8`
- Bound plan: `bound_f619f6c9677a4d2a`
- Bound hash: `f619f6c9677a4d2afdddcd72752ff9e5799b5fc7f2063aae5d0cf5a2104b4c76`

Hermes did not call host confirmation, execution, filesystem, terminal, Python, SQL, or raw coordinate tools.

## What Passed

- Hermes did not select an existing recipe.
- Hermes authored an `EXPERIMENTAL` typed plan from composable capabilities.
- The plan uses `possession_segment`, `geometric_progressive_corridor_from_anchor_set`, `relation_destination_entry`, `exists`, and `eq`.
- The destination-entry predicate compares `entry_status == PASS`.
- Host-injected runtime globals are present in the bound plan.
- Structural fingerprint is novel:
  `cd0a6b43b779ed63ec444a3adb5063d898517ac7aad8d7b1bc43ee73fe51893c`
- Registered fingerprints do not match:
  - `ball_side_block_shift_v1`: `327300f055b23a865532cfc645c033f35992538a5894097b3b4577dc7799b368`
  - `possession_corridor_availability_v1`: `033a909cbc977f93a2c87f22d4a2bf130e53f77d64c40875ec79dd5d6ae5c1c7`
  - `opposite_corridor_after_shift_v1`: `577392987e6dc0e2fb6af1618d4342ff6e3fa342295c185b426591cecda3e62e`

## Host Execution

- Execution ID: `exec_5466f201a479ba0f`
- Compatibility profile: `generic`
- Total results: `64`
- Returned in proof call: `5`
- First cache-aware execution: `MISS`
- Cache status after execution: `HIT`
- Knowledge pack file SHA-256: `7cf720c8210b1d81f12574c5c8299a1dc309930eb1ce17f8eb934d8814119962`
- Knowledge pack semantic SHA-256: `fd6d0843d32cc9632bc864b3dad11af4fea060fa2a5fd827196b3458af37b7a0`

First result:

- Result ID: `ab256488c8e9b408`
- Match: `J03WOY`
- Period: `firstHalf`
- Match time: `54600` ms
- Predicate traces: `has_progressive_corridor=PASS`, `destination_region_entered=PASS`
- Replay window: `replay_63574966cd34b86d`
- Replay frames: `11315..11415`
- Anchor frame: `11365`
- Evidence relation: `dd74570708cce6a3`
- Corridor open frame: `11375`
- Destination-entry frame: `11375`
- Time to entry: `0.0` seconds
- Destination status: `PASS`

`time_to_entry_seconds=0.0` means the ball was already present in the destination region at the corridor open frame, or entered on the same analysis sample. Workbench copy should describe this as immediate destination-region presence/entry at opening, not as a proven later transition after the corridor opened.

## Evidence Artifacts

- `artifacts/n1b/n1-post-n1b-hero-structural-novelty-report.json`
- `artifacts/n1b/n1-post-n1b-hero-execution-report.json`
- `artifacts/n1b/n1-post-n1b-hero-cache-report.json`
- `artifacts/n1b/n1-post-n1b-hero-inspection-report.json`
- `artifacts/m1.2/workshop/handles/draft-plans/draft_26912b2c452106e8.json`
- `artifacts/m1.2/workshop/handles/bound-plans/bound_f619f6c9677a4d2a.json`

## Integrity Closure

- N1B verifier: `artifacts/n1b/n1b-verification-report.json`
- N1B result: `9 pass / 0 fail`
- UNKNOWN fixture: missing ball evidence produces `entry_status=UNKNOWN`, `signal_values=[None]`, and `unknown_mask=[true]` through the generic destination-entry primitive.
- Runtime-parameter guard: every executor `RuntimeParameters` access is declared by host defaults or a checked-in recipe parameter.
- Freeze artifact: `delivery/m1.2/frontier-runtime-freeze.json`
- Freeze result: `19 pass / 0 fail`
- N1C manifest: `artifacts/n1c/n1c-canonical-freeze-manifest.json`
- N1C manifest SHA-256: `423b80651cf53c2850c0558ed12c1334b703eb44946572c5dad48cbda2ffcd12`
- N1C verifier: `artifacts/n1c/n1c-verification-report.json`
- N1C result: `8 pass / 0 fail`
- N1C adds actual generic PASS/FAIL/UNKNOWN node execution, proves `entry_status == PASS` preserves UNKNOWN, and emits `entry_mode` evidence.

Enum-domain validation is proven for catalog outputs that explicitly declare `allowed_values`. This review must not be read as claiming catalog-wide enum-domain safety for outputs that do not yet declare allowed domains.

## Boundary

This proves the backend/Hermes novel-composition loop for the frozen N1 question:

```text
natural language
-> live Hermes over bounded MCP tools
-> novel typed plan
-> deterministic validation
-> host confirmation
-> generic execution
-> real results, traces, evidence, replay window
```

It does not claim final visual-demo polish or a broad tactical ontology. The next product step is to expose this exact capability honestly in the Workbench, including provenance, confirmation, result evidence, and replay.
