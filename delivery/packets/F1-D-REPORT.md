# F1-D Report — Lane Unification And Occupancy Honesty

Branch: `packet/f1-d`

## Summary

F1-D implements the shared five-equal-lanes model, switches lane requirement
evaluation to per-frame distinct-player semantics, and closes the required
ride-along backlog. No generated artifacts, frozen expectations, N1 delivery
pins, or case-study files were regenerated on this worker branch.

## Fixes

### G4: One Shared Lane Geometry

- Added `src/tqe/runtime/lane_geometry.py` with the shared five-equal-lanes
  partition over a 68m pitch, mirror-symmetric boundary ties toward center, and
  `tie_epsilon_m=1e-9`.
- Updated `src/tqe/runtime/lane_occupancy.py` to use the shared geometry and
  expose `boundary_policy` and `tie_epsilon_m` in evidence.
- Updated `src/tqe/runtime/relations.py` so `destination_side`,
  `destination_lane`, and `destination_region_bounds` use the same shared lane
  model. The central destination is now a declared central band, not only
  `y==0.0`.
- Added a guard for destinations outside the declared lane geometry; these now
  produce an invalid/unknown reason instead of being forced into the old wide
  bucket.
- Declared the lane partition semantics in `src/tqe/runtime/catalog.py` for
  lane occupancy, destination-entry classifications, and corridor relations.

### G2: Occupancy Counts Players, Not Player-Frames

- Updated lane requirements to evaluate per frame over distinct player IDs.
- Declared `requirement_aggregation="all_frames"` as the default aggregation.
- Added `any_frame` and `min_frame_ratio:X` support as declared alternatives.
- Missing explicitly requested frames with declared requirements now route to
  `UNKNOWN` with `frame_coverage_insufficient`.
- Aggregate `lane_counts` now counts distinct players per lane across the
  window, not repeated player-frame assignments.

### Ride-Alongs

- Removed synthetic `Counter({"UNKNOWN": 1})` from the corridor
  orientation-unavailable path. Unevaluated windows now report zero states and
  still resolve to UNKNOWN through the anchor verdict.
- Moved corridor honesty tests out of `tests/test_m2a_bypass.py` into
  `tests/test_corridor_episode_honesty.py`.
- Promoted the corridor missing-evidence test to a full `execute()` path with
  requested evidence projection for `corridor.episodes.close_reason`.
- Declared the F1-C round-2 whole-missing-frame rule in the catalog limitation:
  UNKNOWN emission is scoped to targets observed somewhere in the evaluated
  window; roster players never tracked in-window emit no states.
- Changed `event_type_allowed(..., event_type_filter=())` to fail closed.
  `None` remains the explicit broad pass-family mode, and `"any"` remains the
  declared widening token.

## Tests Added Or Updated

- Shared lane equivalence between lane occupancy and corridor destination
  classification, including all edges and both signs.
- Mirror-symmetry checks for the lane model.
- Tie-to-center checks at lane boundaries.
- G2 reproduction: one player over two frames no longer satisfies a two-player
  lane-count requirement; two players in one frame does.
- Requirement coverage UNKNOWN when a requested frame is missing.
- Corridor orientation-unavailable empty state-count assertion.
- Full executor-path corridor missing-evidence close-reason projection.
- Empty event-type filter tuple fail-closed behavior.

## Lane Reclassification Delta

Player-frame lane assignment changes under the unified five-equal-lanes model:

| Match | Player Frames | Changes |
| --- | ---: | --- |
| J03WMX | 3,211,274 | `RIGHT_WIDE -> RIGHT_HALF_SPACE`: 271; `RIGHT_HALF_SPACE -> CENTRAL`: 512 |
| J03WN1 | 2,983,397 | `RIGHT_HALF_SPACE -> CENTRAL`: 480; `RIGHT_WIDE -> RIGHT_HALF_SPACE`: 240 |
| J03WOH | 3,018,708 | `RIGHT_HALF_SPACE -> CENTRAL`: 479; `RIGHT_WIDE -> RIGHT_HALF_SPACE`: 216 |
| J03WOY | 3,135,792 | `RIGHT_WIDE -> RIGHT_HALF_SPACE`: 279; `RIGHT_HALF_SPACE -> CENTRAL`: 513 |
| J03WPY | 3,216,642 | `RIGHT_WIDE -> RIGHT_HALF_SPACE`: 256; `RIGHT_HALF_SPACE -> CENTRAL`: 534 |
| J03WQQ | 3,078,601 | `RIGHT_HALF_SPACE -> CENTRAL`: 546; `RIGHT_WIDE -> RIGHT_HALF_SPACE`: 310 |
| J03WR9 | 3,229,820 | `RIGHT_WIDE -> RIGHT_HALF_SPACE`: 323; `RIGHT_HALF_SPACE -> CENTRAL`: 607 |

Total changed player-frame assignments: 5,566.

Corridor destination-lane changes in the historical M1.1 relation-validation
report:

| Match | Corridor Episodes | Changes |
| --- | ---: | --- |
| J03WOY | 28 | `central -> half_space`: 3; `half_space -> wide`: 2 |
| J03WPY | 72 | `half_space -> wide`: 8; `central -> half_space`: 13 |
| J03WQQ | 41 | `half_space -> wide`: 2; `central -> half_space`: 2 |
| J03WR9 | 24 | `central -> half_space`: 1; `half_space -> wide`: 1; `wide -> outside`: 2 |

Total changed corridor classifications: 34.

## Verification

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_lane_occupancy` | PASS | 16 tests. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_m2a_bypass tests.test_corridor_episode_honesty tests.test_lane_occupancy` | PASS | 36 tests. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_controlled_pass_honesty tests.test_lane_occupancy tests.test_corridor_episode_honesty tests.test_m2a_bypass` | PASS | 55 tests in 58.277s. |
| `make afl-lane-occupancy-verify` | FAIL | Runtime execution passed with 20 results and zero requested-evidence failures; fails only on `scp0_parity_failed` because semantic-registry/generated artifacts were not regenerated. |
| `make m1-1-verify` | FAIL / not_ready | Summary `482 pass / 7 fail / 0 not_ready`; root failure is stale `generated/capability-catalog.json`, with downstream gate precondition cascade. |
| `make n1c-verify` | FAIL | Check-run report fails `n1c.live_artifacts_referenced` because expected live handle files are absent in this checkout; N1 remains fenced. |
| `make n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons. |
| `make n1d-verify` | FAIL | Expected N1 pinned artifact/runtime drift after runtime/catalog changes; no N1 pins regenerated. |
| `make n1i-verify` | FAIL | Expected checked-in generated knowledge-pack/capability-context drift; no generated files regenerated. |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests` | FAIL | 336 tests run in 374.085s; 7 failures enumerated below. |
| `git diff --check` | PASS | No whitespace errors. |

### Full Suite Failure Table

| Test | Failure | Attribution |
| --- | --- | --- |
| `test_afl_validation_factory.ValidationFactoryTests.test_freeze_then_read_compare_and_fail_on_drift` | Validation factory status is `FAIL` instead of expected `PASS`. | Expected dirty-runtime guard from uncommitted runtime edits. |
| `test_m1_1_binder.M11BinderTests.test_generated_artifacts_are_current` | `generated/capability-catalog.json` differs from fresh generation. | Expected generated artifact drift from new catalog lane metadata. |
| `test_scp0_semantic_registry.SCP0SemanticRegistryTests.test_canonical_product_shared_records_have_no_contract_drift` | Contract changes detected for lane occupancy, destination-entry classifications, and both corridor relations. | Expected SCP0 semantic-registry drift from declared lane semantics. |
| `test_scp0_semantic_registry.SCP0SemanticRegistryTests.test_checked_in_lock_and_parity_report_match_fresh_regeneration` | Checked-in lock hash `789a...5654` differs from fresh `b7a4...2870`. | Expected SCP0 lock drift; not regenerated in this packet. |
| `test_scp0_semantic_registry.SCP0SemanticRegistryTests.test_scp0_generation_passes_and_excludes_atlas_from_product_and_ai` | SCP0 generation status `FAIL`. | Expected semantic-registry/generated drift after catalog declarations. |
| `test_verifier_write_mode.CheckModeIsReadOnlyTests.test_scp0_verifier_check_mode_leaves_tracked_files_untouched` | `scp0.main()` exits `1` in check mode. | Expected because SCP0 check-mode detects drift without rewriting tracked files. |
| `test_workbench_beta0_contract.WorkbenchBeta0ContractTests.test_attested_hero_execution_resolves_every_required_evidence_alias` | Live hero rows are `12`, pinned expectation is `11`. | Expected N1 truth ripple from unified lane semantics; N1 remains fenced and requires director re-pin/disclosure. |

## Changed Pins Or Frozen Artifacts

None. All regenerated/generated/frozen artifacts are intentionally left stale
for director acceptance and re-freeze:

- `generated/capability-catalog.json`
- `generated/capability-context.json`
- `generated/tactical-knowledge-pack.json`
- `generated/tactical-knowledge-pack.md`
- SCP0 semantic-registry lock/report artifacts
- N1 delivery pins and workbench attestation expectations

## Missed Or Deferred

- No write-mode regeneration was performed.
- N1 live hero artifacts were not updated; the live result-count ripple is
  reported only.
- Two historical M1.1 corridor episodes in `J03WR9` classify outside the
  declared lane geometry under the unified model. Runtime now refuses to coerce
  them into `wide`; acceptance should decide the frozen-artifact update.
