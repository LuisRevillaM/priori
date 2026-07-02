# F1-B Report - Controlled-Pass Tri-State Honesty

Branch: `packet/f1-b`

Implementation commit: `ee4ab83` (`F1-B: make controlled pass evidence fail closed`)

## Summary

Implemented the four scoped behavioral fixes from
`delivery/packets/F1-B-controlled-pass-honesty.md`:

1. truncated reception windows now produce `UNKNOWN`;
2. sparse or unconfirmed release evidence now produces `UNKNOWN`, restoring the
   PASS/UNKNOWN release-control domain;
3. controlled-pass and one-touch pass candidate selection now defaults to exact
   `Play_Pass` events instead of substring `"Pass"`;
4. release alignment tolerance is declared/configured at 250 ms and alignment
   failure uses `release_frame_alignment_failed`.

No frozen expectations, semantic-registry projections, tracked artifacts,
case-study text, or case-study UI were modified.

## Per-fix detail

### T1: truncated reception window -> UNKNOWN

Files:

- `src/tqe/runtime/controlled_pass.py:434-436`
- `src/tqe/runtime/controlled_pass.py:496-505`
- `tests/test_controlled_pass_honesty.py:21-66`

Change:

- The reception search now records whether the requested reception horizon was
  clipped by period end.
- If no receiver or other-player control has been positively observed and the
  search was clipped, the result is:

```text
controlled_reception_status = UNKNOWN
controlled_reception_reason = reception_window_truncated
```

- Full windows with real contradiction still return `FAIL`, tested with an
  opponent controlling first.

### T2: sparse/unconfirmed release -> UNKNOWN

Files:

- `src/tqe/runtime/controlled_pass.py:348-359`
- `src/tqe/runtime/controlled_pass.py:375-391`
- `tests/test_controlled_pass_honesty.py:68-131`

Change:

- The release window now applies `max_missing_frame_ratio`, matching the
  reception-side missing-frame discipline.
- If release evidence is sparse, the release is `UNKNOWN/missing_tracking`.
- If release tracking is present but no physical release transition is proven,
  the release is `UNKNOWN/release_not_confirmed`, not `FAIL`.
- The equality boundary is not inflated: missing ratio exactly equal to the
  threshold remains admissible.

Observed corpus effect:

- In pre-change code, `release_detection_status=FAIL` with
  `release_detection_reason=release_not_confirmed` occurred 33 times on J03WOY.
- Those 33 rows now become `UNKNOWN`.
- The packet's 84 `release_not_confirmed` figure was a non-exclusive reason
  count across release and reception reason fields. The actual release-status
  FAIL population was 33.

### G9: event filter excludes set pieces by default

Files:

- `src/tqe/runtime/controlled_pass.py:45`
- `src/tqe/runtime/controlled_pass.py:125-127`
- `src/tqe/runtime/controlled_pass.py:670-712`
- `src/tqe/runtime/one_touch.py:64-66`
- `src/tqe/runtime/one_touch.py:141-143`
- `src/tqe/runtime/one_touch.py:199-235`
- `src/tqe/runtime/catalog.py:3150-3163`
- `src/tqe/runtime/catalog.py:3247-3270`
- `tests/test_controlled_pass_honesty.py:133-189`

Change:

- `ControlledPassConfig.event_type_filter` defaults to `("Play_Pass",)`.
- `OneTouchRelayConfig.event_type_filter` also defaults to `("Play_Pass",)`.
- The widened `("any",)` mode preserves the old substring behavior for
  inspection/comparison.
- Specific restart event types can be re-admitted explicitly while preserving
  event-type provenance.
- Excluded events are removed from the candidate denominator.

J03WOY default denominator effect:

```text
639 total old substring-pass candidates
- 76 restart candidates
= 563 Play_Pass candidates
```

Removed restart candidates:

| Event type | Count |
| --- | ---: |
| `KickOff_Play_Pass` | 6 |
| `FreeKick_Play_Pass` | 17 |
| `GoalKick_Play_Pass` | 12 |
| `ThrowIn_Play_Pass` | 41 |
| **Total** | **76** |

### D9: declared alignment/search parameters and reason string

Files:

- `src/tqe/runtime/controlled_pass.py:45-49`
- `src/tqe/runtime/controlled_pass.py:231-241`
- `src/tqe/runtime/controlled_pass.py:299-316`
- `src/tqe/runtime/controlled_pass.py:618-632`
- `src/tqe/runtime/one_touch.py:64-66`
- `src/tqe/runtime/one_touch.py:141-143`
- `src/tqe/runtime/one_touch.py:268-287`
- `src/tqe/runtime/catalog.py:3105-3122`
- `src/tqe/runtime/catalog.py:3247-3270`
- `tests/test_controlled_pass_honesty.py:191-214`

Change:

- `max_release_alignment_ms` is a declared config/catalog parameter with
  default `250.0`.
- Misalignment now reports `release_frame_alignment_failed`.
- `reception_search_seconds` default is now `4.0`, with catalog maximum `10.0`,
  matching the M2A SPEC.

J03WOY 4 s vs 6 s comparison:

- No PASS/FAIL/UNKNOWN distribution changed between 4 s and 6 s, under either
  the default `Play_Pass` filter or widened `any` filter.

Alignment corpus effect:

- With the widened old-style event filter, 2 old `missing_tracking` alignment
  cases now report `release_frame_alignment_failed`.
- Under the default `Play_Pass` filter, those two cases are removed because
  they are restart candidates.

## Headline distribution table: J03WOY controlled_pass_episode

Old baseline was evaluated from commit `d0490ab` in a detached worktree using
the same local canonical data.

| Mode | Candidates | PASS | FAIL | UNKNOWN |
| --- | ---: | ---: | ---: | ---: |
| Old baseline (`d0490ab`, substring `"Pass"`, 100 ms, 6 s) | 639 | 453 | 135 | 51 |
| New default (`Play_Pass`, 250 ms, 4 s) | 563 | 408 | 84 | 71 |
| New `Play_Pass`, 250 ms, 6 s | 563 | 408 | 84 | 71 |
| New widened `any`, 250 ms, 4 s | 639 | 453 | 102 | 84 |
| New widened `any`, 250 ms, 6 s | 639 | 453 | 102 | 84 |

Interpretation:

- T2 accounts for the old-baseline `FAIL` decrease under the widened filter:
  33 release-not-confirmed FAIL rows become UNKNOWN.
- G9 accounts for the default denominator decrease: 76 restart candidates are
  excluded rather than counted as PASS/FAIL/UNKNOWN.
- D9's 4 s reception horizon did not change J03WOY counts relative to 6 s.

## Reason breakdown

### Old baseline (`d0490ab`, 639 candidates)

Controlled-pass status:

| Status | Count |
| --- | ---: |
| PASS | 453 |
| FAIL | 135 |
| UNKNOWN | 51 |

Release status:

| Status | Count |
| --- | ---: |
| PASS | 555 |
| FAIL | 33 |
| UNKNOWN | 51 |

Release reasons:

| Reason | Count |
| --- | ---: |
| `missing_tracking` | 2 |
| `release_not_confirmed` | 33 |
| `unique_release_transition_not_found` | 49 |

Reception status:

| Status | Count |
| --- | ---: |
| PASS | 453 |
| FAIL | 102 |
| UNKNOWN | 84 |

Reception reasons:

| Reason | Count |
| --- | ---: |
| `another_player_controlled_first` | 35 |
| `possession_definitively_broke` | 67 |
| `release_contradicted` | 33 |
| `release_not_confirmed` | 51 |

All reason mentions:

| Reason | Count |
| --- | ---: |
| `another_player_controlled_first` | 35 |
| `missing_tracking` | 2 |
| `possession_definitively_broke` | 67 |
| `release_contradicted` | 33 |
| `release_not_confirmed` | 84 |
| `unique_release_transition_not_found` | 49 |

### New default (`Play_Pass`, 563 candidates)

Controlled-pass status:

| Status | Count |
| --- | ---: |
| PASS | 408 |
| FAIL | 84 |
| UNKNOWN | 71 |

Release status:

| Status | Count |
| --- | ---: |
| PASS | 492 |
| UNKNOWN | 71 |

Release reasons:

| Reason | Count |
| --- | ---: |
| `release_not_confirmed` | 24 |
| `unique_release_transition_not_found` | 47 |

Reception status:

| Status | Count |
| --- | ---: |
| PASS | 408 |
| FAIL | 84 |
| UNKNOWN | 71 |

Reception reasons:

| Reason | Count |
| --- | ---: |
| `another_player_controlled_first` | 31 |
| `possession_definitively_broke` | 53 |
| `release_not_confirmed` | 71 |

All reason mentions:

| Reason | Count |
| --- | ---: |
| `another_player_controlled_first` | 31 |
| `possession_definitively_broke` | 53 |
| `release_not_confirmed` | 95 |
| `unique_release_transition_not_found` | 47 |

### New widened filter (`any`, 639 candidates)

Controlled-pass status:

| Status | Count |
| --- | ---: |
| PASS | 453 |
| FAIL | 102 |
| UNKNOWN | 84 |

Release status:

| Status | Count |
| --- | ---: |
| PASS | 555 |
| UNKNOWN | 84 |

Release reasons:

| Reason | Count |
| --- | ---: |
| `release_frame_alignment_failed` | 2 |
| `release_not_confirmed` | 33 |
| `unique_release_transition_not_found` | 49 |

Reception status:

| Status | Count |
| --- | ---: |
| PASS | 453 |
| FAIL | 102 |
| UNKNOWN | 84 |

Reception reasons:

| Reason | Count |
| --- | ---: |
| `another_player_controlled_first` | 35 |
| `possession_definitively_broke` | 67 |
| `release_not_confirmed` | 84 |

All reason mentions:

| Reason | Count |
| --- | ---: |
| `another_player_controlled_first` | 35 |
| `possession_definitively_broke` | 67 |
| `release_frame_alignment_failed` | 2 |
| `release_not_confirmed` | 117 |
| `unique_release_transition_not_found` | 49 |

## Set-piece filter on vs off

| Filter | Candidates | PASS | FAIL | UNKNOWN | High-bypass results |
| --- | ---: | ---: | ---: | ---: | ---: |
| Default `Play_Pass` | 563 | 408 | 84 | 71 | 5 |
| Widened `any` | 639 | 453 | 102 | 84 | 7 |

The two high-bypass results removed by the default filter:

- `J03WOY:firstHalf:home:188:DFL-OBJ-002G5J:DFL-OBJ-002FXT`
- `J03WOY:secondHalf:away:172:DFL-OBJ-002FZB:DFL-OBJ-0028IJ`

Remaining high-bypass result IDs:

- `J03WOY:firstHalf:away:227:DFL-OBJ-00286X:DFL-OBJ-00019R`
- `J03WOY:firstHalf:home:331:DFL-OBJ-0028FW:DFL-OBJ-002FXT`
- `J03WOY:secondHalf:home:102:DFL-OBJ-002GM9:DFL-OBJ-002FXT`
- `J03WOY:secondHalf:home:356:DFL-OBJ-002GMO:DFL-OBJ-0026RH`
- `J03WOY:secondHalf:away:385:DFL-OBJ-0025BB:DFL-OBJ-0001IG`

## Pinned test values changed

`tests/test_m2a_pass_bypass.py`

| Field | Old | New | Reason |
| --- | ---: | ---: | --- |
| `controlled_anchor_evaluation_count` | 639 | 563 | G9 excludes 76 restart candidates from the default denominator. |
| `evaluation_status_counts.PASS` | 453 | 408 | G9 removes 45 restart PASS candidates. |
| `evaluation_status_counts.UNKNOWN` | 186 | 155 | G9 removes 31 non-PASS restart candidates from bypass evaluation; T2 keeps release uncertainty as UNKNOWN for remaining rows. |

`tests/test_m2a_high_bypass_pass.py`

| Field | Old | New | Reason |
| --- | ---: | ---: | --- |
| result count | 7 | 5 | G9 excludes two restart-derived high-bypass results. |
| expected IDs | 7 IDs | 5 IDs | Removed the two restart-derived result IDs listed above. |

## Verification run

Commands that passed:

```bash
PYTHONPATH=src .venv/bin/python -m unittest tests.test_controlled_pass_honesty
PYTHONPATH=src .venv/bin/python -m unittest tests.test_m2a_controlled_pass
PYTHONPATH=src .venv/bin/python -m unittest tests.test_m2a_pass_bypass tests.test_m2a_high_bypass_pass
PYTHONPATH=src .venv/bin/python -m unittest tests.test_one_touch_pass_chain
```

Focused pass counts:

- `tests.test_controlled_pass_honesty`: 12 tests OK.
- `tests.test_m2a_controlled_pass`: 3 tests OK.
- `tests.test_m2a_pass_bypass` + `tests.test_m2a_high_bypass_pass`: 19 tests OK.
- `tests.test_one_touch_pass_chain`: 4 tests OK.

Full suite:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

Result:

```text
Ran 311 tests in 367.504s
FAILED (failures=5)
```

Failures:

1. `test_m1_1_binder.M11BinderTests.test_generated_artifacts_are_current`
   - generated contract artifact drift caused by the controlled-pass catalog
     parameter changes.
2. `test_scp0_semantic_registry.SCP0SemanticRegistryTests.test_canonical_product_shared_records_have_no_contract_drift`
   - expected `contract_changed` for `controlled_pass_episode` and
     `one_touch_relay_episode`.
3. `test_scp0_semantic_registry.SCP0SemanticRegistryTests.test_checked_in_lock_and_parity_report_match_fresh_regeneration`
   - registry lock hash drift from fresh regeneration.
4. `test_scp0_semantic_registry.SCP0SemanticRegistryTests.test_scp0_generation_passes_and_excludes_atlas_from_product_and_ai`
   - SCP-0 fresh report status is FAIL because runtime parameter signatures and
     projections drifted.
5. `test_verifier_write_mode.CheckModeIsReadOnlyTests.test_scp0_verifier_check_mode_leaves_tracked_files_untouched`
   - representative SCP-0 check exits nonzero because the drift is real.

These are the expected projection/contract ripples from adding declared
parameters and changing defaults. They require director-owned projection
regeneration, not packet-owned write mode.

## Check-mode gates

All commands below were run without `TQE_WRITE=1`. After the runs, tracked files
remained unchanged.

### `make scp-0-verify`

Status: FAIL.

Expected root cause: runtime parameter signature/projection drift.

Key findings:

- `controlled_pass_episode` parameter `reception_search_seconds` changed:
  default 6.0 -> 4.0, max 15.0 -> 10.0.
- `controlled_pass_episode` parameter `event_type_filter` changed:
  default `any` -> `Play_Pass`; allowed values expanded to include
  `FreeKick_Play_Pass` and `KickOff_Play_Pass`.
- `controlled_pass_episode` new runtime parameter:
  `max_release_alignment_ms`.
- `one_touch_relay_episode` new runtime parameters:
  `event_type_filter`, `max_release_alignment_ms`.
- Product and AI projections have unapproved contract changes for both
  `controlled_pass_episode` and `one_touch_relay_episode`.

### `make afl-substrate-q4-verify`

Status: FAIL.

Execution status: PASS. Requested evidence failures: 0. Result count: 2.

Failure reason: frozen expectation drift in bound plan hash, result IDs, and
result signature hash.

### `make afl-time-to-arrival-verify`

Status: FAIL.

Execution status: PASS. Requested evidence failures: 0. Result count: 1.

Failure reason: frozen expectation drift in bound plan hash, result IDs, and
result signature hash.

### `make afl-relative-position-verify`

Status: FAIL.

Execution status: PASS. Requested evidence failures: 0. Result count: 20.

Failure reasons:

- SCP-0 parity failed because projections are stale after catalog drift.
- Frozen expectation drift in report status, bound plan hash, result IDs, and
  result signature hash.

### `make afl-line-break-support-response-verify`

Status: FAIL.

Execution status: PASS. Requested evidence failures: 0. Result mode:
HONEST_ZERO. Result count: 0.

Failure reasons:

- SCP-0 parity failed because projections are stale after catalog drift.
- Frozen expectation drift. The pinned result count moved 1 -> 0 after the
  controlled-pass/default-filter changes.

### `make afl-09a-verify`

Status: FAIL.

Failure reason: bootstrap factory gates failed because
`afl-line-break-support-response` and `afl-relative-position` are failing in
check mode as above.

## Anything missed by the packet analysis

- The scoped event-filter/alignment changes also need declaration on
  `one_touch_relay_episode`; otherwise the module would enforce `Play_Pass`
  while its catalog contract remained silent. This creates expected SCP-0
  drift for one-touch in addition to controlled-pass.
- The real J03WOY corpus showed no distribution difference between 4 s and
  6 s reception search under the tested configs.
- The D9 reason-string fix affects two restart candidates under widened
  filtering; those rows disappear under the default `Play_Pass` filter.
- The `line_break_support_response` gate now produces honest zero rather than
  the previously pinned single result. That is expected downstream movement
  from stricter controlled-pass candidacy, but it should be reviewed during
  director acceptance before re-freeze.

## Working tree note

`git status --short --branch` after check-mode verification showed only the
pre-existing unrelated untracked file:

```text
?? docs/visual-explainers/tactical-compilation-concept.png
```

No tracked frozen expectations, semantic projections, delivery evidence, or
artifacts were modified by this packet.

## Round 2 review response

Review source: `delivery/packets/F1-B-REVIEW.md` on frontier commit `4125c20`.

The round 1 behavioral fixes were accepted at the football/module level, but
the packet was rejected at the executor boundary. Round 2 fixes the boundary:

- `controlled_pass_episode` executor wiring now passes the bound
  `event_type_filter`, `max_release_alignment_ms`, and
  `reception_search_seconds` into `ControlledPassConfig`.
- The executor no longer performs a second exact-match event-type post-filter
  after the controlled-pass module has already applied the declared filter.
- The executor fallback for `reception_search_seconds` is now `4.0`, matching
  the catalog and module default.
- `one_touch_relay_episode` executor wiring now passes the bound
  `event_type_filter` and `max_release_alignment_ms` into
  `OneTouchRelayConfig`.
- `action_event_anchor` now requests `ThrowIn_Play_Pass` explicitly when its
  action type is `throw_in_successful_pass`; otherwise the shared pass parser's
  new `Play_Pass` default silently filtered out throw-in action anchors.
- Release-side sparse tracking now fails closed only when no physical release
  transition was positively observed. A proven release transition is not
  downgraded to UNKNOWN by unrelated sparse frames elsewhere in the search
  window.

### Executor-path parameter checks

Added coverage in `tests/test_controlled_pass_honesty.py`:

- executor `event_type_filter="any"` restores the widened J03WOY candidate
  distribution:

```text
Candidates: 639
PASS:       453
FAIL:       102
UNKNOWN:     84
```

- executor `event_type_filter="ThrowIn_Play_Pass"` restores J03WOY throw-in
  candidates:

```text
Candidates: 41
PASS:       27
FAIL:       10
UNKNOWN:     4
```

- controlled-pass executor config spy confirms:

```text
event_type_filter=("any",)
max_release_alignment_ms=375.0
reception_search_seconds=4.0
```

- one-touch executor config spy confirms:

```text
event_type_filter=("FreeKick_Play_Pass",)
max_release_alignment_ms=375.0
```

Implementation note: two widened `any` J03WOY candidates are
`KickOff_Play_Pass` alignment UNKNOWNs with no anchor frame. They are preserved
in the executor's internal `candidate_evaluations_records` for audit/testing,
but cannot become emitted anchor records because there is no frame to anchor.

### Q6 gate restoration

`make afl-substrate-q6-verify` was run after the executor fixes.

Functional checks are restored:

```text
generic_execution:                 true
q6_compiles_end_to_end:             true
requested_evidence_complete:        true
throw_in_action_clause_exercised:   true
slice_4_velocity_exercised:         true
slice_5_pressure_exercised:         true
result_or_honest_zero:              true
execution.status:                   pass
result_count:                       0
result_mode:                        HONEST_ZERO
requested_evidence_failure_count:   0
```

First-period probe:

```text
match_id:              J03WOH
period:                firstHalf
throw_in_action_count: 17
throw_in_pass_count:   17
velocity_count:        17
pressure_count:        17
line_transition_count: 17
```

The make target still exits nonzero because the validation factory reports the
expected frozen expectation drift:

```text
bound_plan_hash:
  expected 78069091c494a36415e390a68d7d6ee55d62436c3dbac259427d48d6d533f352
  actual   3f1fe004bc16bb029f82635a80f26c2a2e8865de4ec7d1490d943fb1c36c81b5
```

No frozen expectations were refreshed in this packet.

### Round 2 verification commands

```text
PYTHONPATH=src .venv/bin/python -m unittest tests.test_controlled_pass_honesty
```

Result:

```text
Ran 18 tests in 31.798s
OK
```

```text
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_m2a_controlled_pass \
  tests.test_m2a_pass_bypass \
  tests.test_m2a_high_bypass_pass \
  tests.test_one_touch_pass_chain
```

Result:

```text
Ran 26 tests in 80.654s
OK
```

```text
make afl-substrate-q6-verify
```

Result: FAIL only for expected frozen expectation drift; all q6 functional
checks are true and the probe substrate is restored.
