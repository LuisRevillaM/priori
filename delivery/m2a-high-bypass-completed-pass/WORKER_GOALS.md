# M2A Worker Goals

Date: 2026-06-23

Status: controller-authored dispatch packet.

Primary spec:

```text
delivery/m2a-high-bypass-completed-pass/SPEC.md
delivery/m2a-high-bypass-completed-pass/PARALLEL_EXECUTION.md
```

Controller note: S1 runtime semantics remain blocked until the controller-owned S0C gate freezes `artifacts/m2a/s0-contract-freeze.json` and records `PROCEED_TO_S1`.

## Worker A - Event/Tracking And Controlled-Reception Preflight

```text
/goal Run M2A-S0A event/tracking and controlled-reception preflight for High-Bypass Completed Pass. Read delivery/m2a-high-bypass-completed-pass/SPEC.md and PARALLEL_EXECUTION.md first. Determine whether canonical event pass records can be reconciled with tracking frames, passer/receiver tracking identities, release control, and controlled reception on real canonical data. Produce delivery/m2a-high-bypass-completed-pass/M2A_S0A_EVENT_PREFLIGHT.md and artifacts/m2a/s0a-event-preflight.{json,csv if useful}. Answer: event timestamp meaning; event-to-frame alignment policy; passer/receiver ID mapping reliability; release-control feasibility; reception-control feasibility; provisional PASS/FAIL/UNKNOWN candidate counts; representative cases for clear reception, wrong receiver, deflection, near-ball/no-control, possession break, and missing frames. You may add read-only preflight scripts under src/tqe/verification or artifacts/m2a. Do not edit catalog.py, executor.py, knowledge_pack.py, m1_2.py, Makefile, recipe registry, generated catalogs, Workbench production UI, or runtime semantics. Stop and report if event timestamps, recipient IDs, or endpoint tracking cannot be reconciled on real data.
```

## Worker B - Active-Player Timeline

```text
/goal Run M2A-S0B active-player timeline proof for High-Bypass Completed Pass. Read delivery/m2a-high-bypass-completed-pass/SPEC.md and PARALLEL_EXECUTION.md first. Build or identify the trusted active on-pitch player timeline needed to compute the opposition outfield denominator at pass release and controlled reception. Produce delivery/m2a-high-bypass-completed-pass/M2A_S0B_ACTIVE_PLAYERS.md and artifacts/m2a/s0b-active-player-timeline.*. Answer: registered squad vs active on-pitch players vs observed tracked players; expected_active_outfield_ids at release and reception; missing_active_opponent_ids policy; substitution/dismissal/active-set transition policy; frequency of active-player membership changes inside candidate windows; policy/hash/version for the active-player timeline. If substitution, dismissal, or active membership changes inside a pass window, the relevant controlled-pass/bypass coverage must be UNKNOWN. You may add isolated helper/tests if needed, but do not edit shared runtime registries, generated catalogs, Hermes surfaces, or Workbench UI.
```

## Worker C - Pure Synthetic Bypass Measurement

```text
/goal Implement and prove the pure M2A bypass measurement engine without real pass extraction. Read delivery/m2a-high-bypass-completed-pass/SPEC.md and PARALLEL_EXECUTION.md first. Add src/tqe/runtime/bypass.py and tests/test_m2a_bypass.py if they do not already exist. The function must consume direction-normalized release/reception endpoint state plus expected active opposition outfield IDs, evaluate goal-side-at-release and behind-ball-at-reception with buffers, return candidate_goal_side_ids, evaluated_ids, missing_ids, bypassed_player_ids, opponents_bypassed_count, and coverage_status. It must be threshold-free: do not encode ">= 5" or "forward_progression_m >= 8" in this capability. Tests must cover attacking-direction mirroring, player order determinism, buffer edge cases, missing active opponents producing UNKNOWN, goalkeeper exclusion policy input, and count stability. Do not depend on real pass extraction and do not edit executor/catalog/knowledge-pack registries.
```

## Worker D - Cloud Event Dependency Contract

```text
/goal Define the M2A cloud event dependency/readiness contract. Read delivery/m2a-high-bypass-completed-pass/SPEC.md and PARALLEL_EXECUTION.md first. Produce delivery/m2a-high-bypass-completed-pass/M2A_S0D_CLOUD_CONTRACT.md plus any schema/verifier test changes needed to ensure deployed M2A readiness is fail-closed. The manifest must include event-data hashes, active-player timeline hashes, canonical-data version, runtime/version fields, and cache identity fields. /readyz must remain false for M2A until genuine event and active-player artifacts exist and hashes match. No placeholder hash may satisfy readiness. Do not alter tactical runtime semantics or expose M2A to Hermes.
```

## Worker E - Fixture-Only Replay Contract

```text
/goal Define and fixture-test the M2A replay overlay contract without wiring it into production result flow. Read delivery/m2a-high-bypass-completed-pass/SPEC.md and PARALLEL_EXECUTION.md first. Produce delivery/m2a-high-bypass-completed-pass/M2A_S0E_REPLAY_CONTRACT.md and fixture-only Workbench DTO/tests if useful. The overlay must support observed ball trail, labelled pass vector, passer/receiver highlights, release ghosts for bypassed opponents, reception positions, count reveal only after controlled reception, and UNKNOWN/missing-evidence rendering. It must never infer bypassed players not present in evidence. Do not wire this into normal Workbench results until S3 supplies exact release/reception points and bypassed_player_ids.
```

## Controller S0C Gate

```text
/goal Integrate M2A-S0A, S0B, and S0C pure bypass findings into the controller-owned M2A-S0C data truth gate. Freeze artifacts/m2a/s0-contract-freeze.json only if real data proves event/tracking alignment, controlled pass/reception semantics, active-player denominator, and bypass measurement are coherent enough for S1. The freeze artifact must pin pass-family definition, timestamp alignment policy/version, release-control definition, reception-control definition, reception search stop conditions, PASS/FAIL/UNKNOWN decision table, active-player timeline policy/version/hash, goalkeeper policy, ControlledPassEpisode schema, ControlledPassEvaluation schema, BypassedOpponentsEvaluation schema, default buffers, threshold ownership, accepted canonical matches, distributions for candidate pass counts and bypass counts, sample human-review IDs, and a final decision of PROCEED_TO_S1 or STOP_AND_REPORT_DATA_GAP. If accepted, update delivery/m2a-high-bypass-completed-pass/status.yaml from SPEC_DRAFTED to S0_ACCEPTED. Do not begin S1 before this gate passes.
```
