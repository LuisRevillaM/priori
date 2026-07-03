# F2-Y Report - Round 2

Branch: `packet/f2-y`
Round-1 implementation tip: `467a5b3`
Review packet: `delivery/packets/F2-Y-REVIEW.md`
Push: no push, per direct-channel protocol.

## Scope

Round 1 was rejected only for the review findings below. T5, T6, V8, and
V9(a-c) remain untouched.

| Review item | Status | Evidence |
| --- | --- | --- |
| R1 report first commit | PASS | `6b0a901` created this report before code changes, per L1. |
| R2 T7 truth contract | PASS | `be9f43f` restores observed episode non-match to FAIL, preserves explicit UNKNOWN, and leaves coverage-evidenced frame-signal gaps as UNKNOWN. |
| R3 `_predicate_status` disposition | PASS | Not retired. It remains live in the legacy witness chain; see disposition below. |
| R4 hygiene | PASS | `c145d19` removes the dead witness `output_name` parameter, hardens empty-string manifest hashing, and records the count-field/multiplicity caveat. |

## Commits

| Commit | Purpose |
| --- | --- |
| `6b0a901` | Start F2-Y round 2 report. |
| `be9f43f` | Correct episode trace UNKNOWN contract. |
| `c145d19` | Clean up witness and cache boundary hygiene. |
| `5c5784a` | Restore predicate trace legacy record bridging. |

## R2 - T7 Contract

The rejected round-1 branch made plain episode non-match UNKNOWN via a
fabricated `episode_trace_anchor_uncovered` reason. That made FAIL unreachable
for list-backed episode predicates and wiped out existing reachable rows.

Round 2 changes only the T7 branch:

- Frame-signal missing anchor remains UNKNOWN with coverage evidence:
  `anchor_frame_missing_from_predicate_signal`.
- Explicit temporal UNKNOWN inside a matched episode remains UNKNOWN.
- Explicit temporal FAIL inside a matched episode remains FAIL.
- Plain episode-set non-match is FAIL.
- Temporal episode-set non-match is FAIL unless a matched episode explicitly
  carries UNKNOWN.

No escalation hook was added because the list-backed non-match branch has no
coverage evidence to justify UNKNOWN. The implementation fails closed to
observed non-satisfaction there; coverage-evidenced UNKNOWN still exists only
where the runtime has actual coverage evidence.

Targeted unit coverage:

- `test_episode_trace_plain_episode_non_match_is_fail`
- `test_episode_trace_temporal_unknown_remains_unknown`
- `test_episode_trace_explicit_temporal_fail_remains_fail`
- `test_episode_trace_temporal_records_no_match_is_fail`

## Corpus Delta

The legacy row removals remain visible, but their mechanism is now the
authorized one: frame-signal predicate coverage gaps, not fabricated episode
trace gaps.

| Probe | Prior reference | Round-2 committed tree | Attribution |
| --- | ---: | ---: | --- |
| `execute_default_plan` legacy rows | 180 rows / 900 PASS traces | 0 rows / 180 UNKNOWN traces | All sampled traces are `not_stoppage` UNKNOWN with `anchor_frame_missing_from_predicate_signal`. |
| `opposite_corridor_after_shift` generic rows | 9 rows | 0 rows / 792 UNKNOWN traces | Coverage-evidenced frame-signal gaps: `not_stoppage` 313, `destination_region_entered` 313, `has_opposite_corridor` 166. |
| `opposite_corridor_after_shift` legacy profile | 32 rows | 32 rows, traces `PASS:50`, `FAIL:14` | FAIL remains reachable; classifications remain `DESTINATION_ENTERED:18`, `CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY:14`. |

Representative evidence for the row wipeout:

```text
trace_source: not_stoppage.predicate
anchor_frame_id: 11580
reason: anchor_frame_missing_from_predicate_signal
```

## R3 - `_predicate_status` Disposition

`_predicate_status` was not removed. It is still a live side channel for the
legacy parity chain, not a quarantine-only artifact.

Current consumers/writers:

- `src/tqe/runtime/executor.py` writes candidate predicate status in
  `record_candidate_predicate`.
- `src/tqe/runtime/capabilities/teamshape_family.py` copies
  `_predicate_status` from source episodes into derived candidates.
- `src/tqe/runtime/capabilities/possession_family.py` carries candidate
  `_predicate_status` into possession-family results.
- `src/tqe/runtime/legacy_m1.py` writes and consumes `_predicate_status` for
  legacy M1 parity.

Disposition: leave standing. Retiring it would be a behavior change outside
this round-two review fix.

## R4 - Hygiene

- Removed the dead `output_name` parameter from the selected-relation witness
  helper path. The wrapper still accepts the bound plan for API shape but
  deletes it immediately because the helper no longer needs it.
- Changed `shared_catalog_node_cache_key` to treat an empty manifest hash
  string like a missing hash and recompute from canonical data. A regression
  test now sets `canonical_data_manifest_hash=""` to cover the guard.
- Count-field/multiplicity caveat: the current V9 complexity enforcement
  treats declared numeric count fields such as `relation_count` and
  `opponents_bypassed_count` as relation-multiplicity signals. That remains
  intentionally reported as a future limits review item, not fixed here.

## Round 3 - Scoped Legacy Trace Matcher

The round-three review diagnosed the remaining row wipeout as V8 fallout, not
the T7 redo. `record_matches_anchor` was correctly strict for witness
selection, but `predicate_trace_from_runtime_record` was using that strict
matcher for legacy predicate trace records that have no `anchor_id` key.
Those records identify their anchor by `result_id` or by the
`match_id` / `period` / `anchor_frame_id` triple, so strict matching missed
every record-backed trace, fell through to sparse frame-signal lookup, and
emitted `anchor_frame_missing_from_predicate_signal`.

Round 3 adds `legacy_trace_record_matches_anchor` and uses it only in the
predicate trace record path. `record_matches_anchor` remains strict and
unchanged for witness selection. The bridge:

- first honors strict `anchor_id` matching;
- refuses fallback when an `anchor_id` key is present but does not match;
- for anchor-id-less legacy records, matches `result_id` against
  `anchor.attributes["result_id"]` when available;
- otherwise matches the `match_id` / `period` / `anchor_frame_id` triple.

Probe tests added:

- `test_anchorless_legacy_trace_records_bridge_by_identity`
- `test_uncovered_frame_signal_trace_is_unknown_with_reason`

Backlog item recorded: the sparse FrameSignal fallback remains a trap for
record-backed predicate signals keyed by a different frame column than the
runtime anchor. This packet does not fix that broader R1-era issue; it only
restores the scoped legacy trace record identity bridge ruled for round 3.

## Restoration Census

| Probe | Round-2 broken state | Round-3 committed tree | Attribution |
| --- | ---: | ---: | --- |
| `execute_default_plan` legacy rows | 0 rows / 180 UNKNOWN traces | 180 rows / 900 PASS traces | Frozen baseline restored; five predicates per row: `wide_entry_threshold`, `wide_entry_persists`, `shift_threshold`, `shift_persists`, `not_stoppage`. |
| `opposite_corridor_after_shift` generic rows | 0 rows / 792 UNKNOWN traces | 9 rows / 655 traces | Generic results restored with `DESTINATION_ENTERED:6` and `CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY:3`; trace statuses `PASS:60`, `FAIL:3`, `UNKNOWN:592`. |
| `opposite_corridor_after_shift` legacy profile | 32 rows | 32 rows | Unchanged; classifications remain `DESTINATION_ENTERED:18`, `CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY:14`; trace statuses `PASS:50`, `FAIL:14`. |

`tests.test_m1_1_runtime` passes all 12 tests, including frozen selected-result
baseline equality and full predicate-trace emission. This is the byte-exact
frozen-baseline restoration requested by the review.

## Verification

Commands were run on the committed tree after `5c5784a` unless noted.

| Check | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_predicate_truth_series` | PASS | 13 tests, including the two round-three probes. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_m1_1_runtime` | PASS | 12 tests; restores 180-row frozen baseline and generic execution rows. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_executor_boundaries` | PASS | 14 tests from round two; this file was not touched in round three. |
| `git diff --check` | PASS | No whitespace errors. |
| `make PYTHON=.venv/bin/python test` | FAIL | 371 tests, 4 failures. The five M1 runtime failures from round two are gone; remaining failures are generated/frozen drift class. |

Full-suite failures observed:

- `test_m1_1_binder.M11BinderTests.test_generated_artifacts_are_current`
- `test_scp0_semantic_registry.SCP0SemanticRegistryTests.test_checked_in_lock_and_parity_report_match_fresh_regeneration`
- `test_verifier_write_mode.CheckModeIsReadOnlyTests.test_scp0_verifier_check_mode_leaves_tracked_files_untouched`
- `test_workbench_beta0_contract.WorkbenchBeta0ContractTests.test_attested_novel_composition_requires_verified_plan_hash`

## Pinned Gates

| Gate | Result | Attribution |
| --- | --- | --- |
| `n1d1-verify` | PASS | Attestation verified; no blocking reasons. |
| `afl-substrate-q4-verify` | FAIL | Runtime execution still PASS with 2 results and 0 evidence failures; frozen `bound_plan_hash`, `result_ids`, and `result_signature_hash` drift. |
| `afl-substrate-q6-verify` | FAIL | Runtime execution still PASS honest-zero with 0 evidence failures; frozen `bound_plan_hash` drift. |
| `afl-line-break-support-response-verify` | FAIL | Runtime execution still PASS with 1 result and 0 evidence failures; frozen `bound_plan_hash`, `result_ids`, and `result_signature_hash` drift. |
| `afl-lane-occupancy-verify` | PASS | Verification report PASS; lane occupancy unit suite passed. |
| `afl-09a-verify` | FAIL | Bootstrap factory gate reports Q4/Q8 drift from dependent frozen gates. |
| `scp-0-verify` | FAIL | Internal verification report status is PASS/no findings, but the make target exits red on generated semantic-registry projection and lock drift. |
| `afl-passport-verify` | FAIL | Stored capability passport projection and registry lock drift against freshly generated projection. |

Generated artifacts, semantic registry locks, frozen expectations, delivery
attestations, and artifacts remain fenced. They were not regenerated or
re-pinned in this packet.

## Working Tree

Tracked files are clean after the report commit. The unrelated untracked file
`docs/visual-explainers/tactical-compilation-concept.png` was present before
this round and was not touched.
