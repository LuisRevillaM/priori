# N1D.1 — Hermes Origin & Novelty Attestation (STOP-AND-REPORT)

Date: 2026-06-22
Baseline: Beta 1A `59b6749`, Beta 1A.1 `a9d056e`, N1D `16fa57e`, Beta 1B `6b8ad90`.
External decision: APPROVE_WITH_REQUIRED_CHANGES_BEFORE_BETA_1C.
Scope: attestation + verifier + entry-mode presentation. No `HERMES_NOVEL_COMPOSITION` exposure; no
primitives/operators/MCP-auth/Hermes-prompt/runtime changes.

## Headline

Task 1 has an explicit gate: *"If the original Hermes session cannot be audited from existing
artifacts/state, stop and report. Do not fabricate origin."* That gate has tripped. I have **not**
fabricated origin. The N1D.1 verifier is implemented and **fails closed** with a **BLOCKED**
attestation, the entry-mode presentation defect is fixed, and the remediation path is below.

**Beta 1C remains blocked**: no backend-issued `VERIFIED` attestation exists, by design.

## Two conclusive origin defects (evidence)

### 1. The live Hermes session's raw decision and ordered MCP tool-call trace were never persisted
- Live novel session id: `20260622_141849_63e2a6` (recorded in
  `artifacts/n1b/n1-post-n1b-hero-structural-novelty-report.json` and the N1C manifest).
- The persisted Hermes traces under `artifacts/m1.2/workshop/hermes-traces/*.json` all belong to
  *other* M1.2 sessions (draft `d4526d02…`). No file in the repo carries session
  `20260622_141849_63e2a6` together with a `raw_model_output` or `tool_calls` array.
- Therefore the required **ordered MCP tool-call trace hash** and **raw Hermes decision hash** cannot
  be produced from existing artifacts. The verifier records them as `null` with a reason, not invented.

### 2. The pinned N1D plan is the local candidate, not the Hermes-submitted draft
Comparing the three plans (stripped of `requested_evidence`):
- Hermes-submitted draft (`draft_26912b2c452106e8`): stable hash `45cdc29a…`,
  structural fingerprint **`cd0a6b43…`** (this is the fingerprint N1C actually pinned).
- Local candidate / pinned N1D plan: stable hash `fc375559…`, structural fingerprint **`79b852cd…`**.
- `n1d == hermes` (stripped): **false**. `n1d == local` (stripped): **true**.

So N1D was frozen on the deterministic *local candidate*, which is **structurally different** from the
genuinely Hermes-authored draft. Both plans are novel versus the three registered templates, but N1D
is anchored to the wrong plan. The evidence diff between the N1D plan and the Hermes draft is also far
larger than the two allowed aliases — N1D added 5 aliases
(`destination_entry_mode`, `destination_observed_window_end_frame_id`, `destination_relation_id`,
`destination_time_to_entry_seconds`, `relation_duration_seconds`) and dropped several the Hermes draft
carried — so the allowed-augmentation rule (only `destination_entry_mode` +
`destination_time_to_entry_seconds`) is violated.

A novelty-only check would have looked fine (the pinned plan *is* novel); only the origin +
augmentation checks expose the problem. That is exactly why N1D.1 is required before Beta 1C.

## What was delivered

### N1D.1 verifier — `src/tqe/verification/n1d1.py` (Makefile `n1d1-verify`)
A fail-closed gate that issues an attestation (`artifacts/n1d/n1d1-attestation.json`, schema
`n1d1.attestation.v1`) with:
- **Hermes origin**: session id, original question SHA-256, Hermes draft hash, N1D plan hash, and the
  **allowed-augmentation diff** vs the Hermes draft. Missing trace/decision hashes are `null` (never fabricated).
- **Structural novelty** (Task 2): normalized fingerprint, registered-fingerprint-set hash, per-template
  comparison, `existing_recipe_selected=false`. The fingerprint preserves capability graph, input
  dependencies, operators, anchor topology, classification rules, and evidence-source structure; it
  ignores node ids, display text, match scope, result limits, and literal parameter values
  (reuses the audited `n1a.structural_fingerprint`).
- **Augmentation enforcement** (Task 3): Hermes draft stripped of `requested_evidence` must equal the
  N1D plan stripped of `requested_evidence`, and the added aliases must equal exactly
  `{destination_entry_mode, destination_time_to_entry_seconds}`.
- **Beta 1C unlock contract** (Task 4), published in the attestation for later enforcement:
  `provenance_source=HERMES_NOVEL_COMPOSITION`, `status=VERIFIED`, `plan_hash`=current bound plan hash,
  `freeze_manifest_id`=current N1D manifest; fail-closed on browser payload, model payload, stale
  attestation, or mismatched plan hash.

Current result: **status BLOCKED**, exit 1, blocking reasons
`["n1d1.origin_trace_persisted", "n1d1.augmentation_diff_allowed"]`.

### Entry-mode presentation fix (Task 5) — `apps/workbench-alpha/src/presentation.ts`
One combined mapper `entryModePresentation(mode, timeToEntrySeconds)` reading the N1D aliases:
- `PRESENT_AT_OPEN` → "Already in destination when corridor opened"
- `ENTERED_AFTER_OPEN` + t → "Entered destination {t}s after opening"
- `NOT_ENTERED` → "Did not enter destination in the observed window"
- `UNKNOWN` → "Destination entry could not be determined"

`principalMeasurement` now consults entry-mode **before** raw time-to-entry, so `PRESENT_AT_OPEN`
(t=0.0) renders honestly and never as "Entry in 0 s". Unit-tested.

## Tests

- `make n1d1-verify` (`python -m tqe.verification.n1d1`): **BLOCKED, exit 1** (fails closed).
- `python -m unittest tests.test_n1d1_attestation`: **OK** — verifier fails closed, origin trace/decision
  hashes are `null` (never fabricated), novelty computable, augmentation diff rejects >2 aliases.
- `python -m tqe.verification.n1c`: **pass 8/8**. `python -m tqe.verification.n1d`: **pass 12/12**.
- `apps/workbench-alpha` `npm run test:acceptance`: **16 e2e + 5 unit suites pass**; `tsc` clean.

## Acceptance status

| Criterion | Status |
|-----------|--------|
| Verifier fails if origin hashes drift | Met (fail-closed; drift compare applies once VERIFIED+frozen) |
| Verifier fails if fingerprint matches a registered recipe/template | Met (novelty check) |
| Verifier fails if N1D plan changes beyond the two allowed aliases | **Met — currently failing on the real defect** |
| UI mapper renders PRESENT_AT_OPEN honestly at t=0.0 | **Met** |
| Beta 1C blocked until backend-issued VERIFIED attestation exists | **Met (attestation is BLOCKED)** |
| Existing N1C/N1D/Beta 1A/1A.1/1B tests green | **Met** |
| **N1D.1 verifier passes (VERIFIED)** | **NOT met — blocked by the origin defects above; cannot pass honestly** |
| Replace synthetic novel UI test with a passing host-path unlock e2e | **Deferred — cannot pass until VERIFIED; the host-path gate test asserts the current BLOCK instead** |

## Remediation (required before Beta 1C; needs the model/MCP — out of scope here)

1. Re-run the **frozen hero question** through live Hermes with full persistence of the raw decision
   (`raw_model_output`) and the **ordered MCP tool-call trace** for the session.
2. Re-pin N1D on the **Hermes-submitted draft** plus **exactly** the two allowed evidence aliases
   (`destination_entry_mode`, `destination_time_to_entry_seconds`) — re-run `n1d-freeze`.
3. Re-run `n1d1-verify`; on `VERIFIED`, promote `n1d1-attestation.json` to `delivery/n1d/` (committed)
   and only then build the Beta 1C unlock that consumes it.

## Caveats

- Origin artifacts (Hermes draft handle, N1B reports, N1C manifest) live under gitignored `artifacts/`;
  the raw decision + tool-call trace for the live session are not present there at all. A committed,
  CI-reproducible origin attestation will require persisting those during the remediation re-run.
- The current N1D pin is still honest as a *runtime* proof (N1D gate green), but it is **not** an
  attested Hermes-origin proof. Do not represent it as model-authored until N1D.1 is `VERIFIED`.
