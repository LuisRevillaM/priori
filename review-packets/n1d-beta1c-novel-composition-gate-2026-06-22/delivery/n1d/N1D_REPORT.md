# N1D — Runtime-Pinned Novel Composition Refresh

Date: 2026-06-22
Baseline: Beta 1A `59b6749`; N1C proof integrity `393b4db`.
Scope: backend / proof only. No Workbench UI exposure (per stop condition).

## Problem

N1C pinned the N1B **live** hero artifacts, which were produced **before** the runtime emitted
`entry_mode`. So those artifacts cannot honestly be presented as current-runtime output, and the
Workbench correctly keeps `HERMES_NOVEL_COMPOSITION` non-runnable / "pending proof refresh".

## What N1D does

Re-executes the **same frozen hero** under the **current HEAD runtime** (which emits `entry_mode`),
produces fresh draft/bound/execution/result/replay artifacts whose result evidence carries
`entry_mode`, and pins a canonical manifest to the exact runtime/data/artifact/result hashes that
produced them. The N1D verifier is a **read-compare freeze gate**: it fails on drift instead of
silently regenerating proof.

- Hero question: unchanged (same frozen text as N1A/N1C).
- Plan shape / capabilities / operators / Hermes prompts: unchanged.
- Only change: the N1D hero plan surfaces two **already-runtime-emitted, catalog-declared** evidence
  fields — `entry_mode` and `time_to_entry_seconds` (aliases `destination_entry_mode`,
  `destination_time_to_entry_seconds`) from the `destination_entry`/`entry_status` output. This is
  evidence surfacing required for proof consumption, not new vocabulary, primitives, or operators.
  (Without it the runtime projects only requested evidence, so `entry_mode` never reaches results.)

## Artifact identity (pinned)

Frozen at commit `59b67499f37c595028fdb5952f4cf71ff5175fa1` (runtime pinned by content hash, so the
gate stays valid across later commits as long as the runtime files are unchanged).

| Artifact | ID |
|----------|-----|
| Draft plan | `draft_55983414d43845f3` |
| Bound plan | `bound_73d049710392394d` |
| Execution | `exec_d549f238bbc6ef39` |
| First result | `0b06e5f2a538ab8e` |
| Replay window | `replay_a9d17b6b632465e9` |

| Hash | Value |
|------|-------|
| Hero plan document sha256 | `064be47c06cce4aeb4b87d2600397daa06ce1a168495e91126e25e235396f23a` |
| Draft plan hash | `55983414d43845f3190ff1b6d11db3e17e82a09ddf9f6af5c46f76a2852b3358` |
| Bound plan hash | `73d049710392394dfc4dbcdf46b09a282761708a3922bda7c208f9361a46c6b4` |
| Result fingerprint | `d97ef1a2656ead4b53546ca274bbb74bcca037fc261d22e52ab4e2c369f5b284` |
| Runtime executor sha256 | `f74725adace6470d9d6f81d8f8ffb41bce8d3ba603c3624b6f3bc62e756d0446` |
| Canonical data inventory sha256 | `8386ac9ae7d028fa45db536a38ecd4c6dfeb098c0a837018daa152491e83392c` |

Pinned source-of-truth (committed): `delivery/n1d/n1d-canonical-freeze-manifest.json`,
`delivery/n1d/n1d-hero-plan.json`, `delivery/n1d/n1d-entry-mode-audit.json`.
Regenerated handles (gitignored, deterministic content): `artifacts/n1d/workshop/…`.
Gate run report: `artifacts/n1d/n1d-verification-report.json`.

## Top-result entry_mode audit

Distribution over the 5 returned results: **PRESENT_AT_OPEN ×3, ENTERED_AFTER_OPEN ×2,
NOT_ENTERED ×0, UNKNOWN ×0**.

| result_id | entry_mode | time_to_entry_seconds | entry_status |
|-----------|-----------|-----------------------|--------------|
| `0b06e5f2a538ab8e` | PRESENT_AT_OPEN | 0.0 | PASS |
| `a950be165bcf2a01` | ENTERED_AFTER_OPEN | 0.16 | PASS |
| `f81740ea1ba517e4` | PRESENT_AT_OPEN | 0.0 | PASS |
| `ac61ba5a1fe73030` | PRESENT_AT_OPEN | 0.0 | PASS |
| `3e052a0bb2e6559d` | ENTERED_AFTER_OPEN | 0.28 | PASS |

- **Task #6:** every result with `time_to_entry_seconds == 0.0` is labelled `PRESENT_AT_OPEN`
  (not "entered later"). Verified by `n1d.zero_time_is_present_at_open`.
- **Task #7 (entry-before-open):** zero anomalies, and it is **structurally impossible by design** —
  `ball_entry_evaluation_into_destination_region` scans ball frames from `open_frame_id` forward, so
  the first in-region frame has `frame_id >= open_frame_id` ⇒ `time_to_entry_seconds >= 0.0`, and
  `PRESENT_AT_OPEN` is emitted exactly when the entry frame equals the open frame. This is the
  expected data/evidence timing, not a bug; annotated in the audit (`entry_before_open_analysis`).

## Verifier (read-compare freeze gate)

`python -m tqe.verification.n1d` (Makefile `n1d-verify`): reads the pinned manifest, re-runs the
full host-authority pipeline into a throwaway scratch dir, recomputes the deterministic identity,
and compares. It never overwrites the pinned proof.

`python -m tqe.verification.n1d --freeze` (Makefile `n1d-freeze`): one-time re-pin.

Gate checks (all pass): `manifest_present`, `no_artifact_or_runtime_drift`, `runtime_matches_claim`,
`result_evidence_contains_entry_mode`, `entry_mode_in_declared_domain`, `zero_time_is_present_at_open`,
`no_entry_before_open`, plus preserved N1C contracts (`entry_status_pass_fail_unknown_exercised`,
`eq_pass_preserves_unknown`, `entry_mode_tri_state_emitted`, `declared_enum_outputs_enforced`,
`executor_runtime_parameters_declared`).

## Tests run

- `n1d-verify` (gate): **PASS 12/12**.
- Drift tamper test: corrupting a pinned runtime hash and the result fingerprint ⇒ gate **FAILS,
  exit 1**, reporting both drifts; restoring ⇒ **PASS, exit 0**.
- `n1c-verify`: **PASS 8/8** (N1C UNKNOWN + enum-domain contracts preserved).
- Backend regression: `python -m unittest discover -s tests` (see commit notes).

## Acceptance

- ✅ Frozen hero executes under current runtime.
- ✅ New artifacts contain `entry_mode` in result evidence.
- ✅ Manifest runtime hashes match the runtime being claimed (current HEAD).
- ✅ No stale N1B live artifacts are used as current proof (fresh re-execution under `delivery/n1d`).
- ✅ Verifier fails on drift.
- ✅ Workbench can safely remove the "pending proof refresh" block in a later Beta 1C slice
  (not done here — UI exposure is out of scope per the stop condition).

## Remaining caveats / follow-ups

- The pinned commit (`59b6749…`) is the freeze provenance; the gate's drift check is on **runtime
  file content hashes**, not the commit, so it remains valid across later commits while the runtime
  is unchanged. Any runtime/data/plan change ⇒ gate fails ⇒ re-run `n1d-freeze` deliberately.
- The hero invocation is the frozen `max_results=5` over match `J03WOY`; the audit covers those 5
  top results. Broadening scope/result count would be a separate, deliberate re-freeze.
- Beta 1C (separate slice, on request): wire Workbench `HERMES_NOVEL_COMPOSITION` to consume the
  N1D-pinned artifacts and drop the "pending proof refresh" gate, with end-to-end UI tests.
