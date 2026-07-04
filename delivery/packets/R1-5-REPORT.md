# R1-5 Report - typed_join Operator

Branch: `packet/r1-5`
Frontier base: `de7748a`
Packet: `delivery/packets/R1-5-typed-join.md`
ADR: `docs/adr/0013-r1-operator-era.md`, including all addenda
Push: no push, per direct-channel protocol.

## Result

READY FOR REVIEW.

The work is committed in the writable clone at `/private/tmp/priori-r1-5-clone`,
branch `packet/r1-5`.

Stage-committed-from-first-commit was satisfied by `65765be`.

## Commit Ledger

| Commit | Purpose |
| --- | --- |
| `65765be` | Stage-committed the R1-5 report skeleton before implementation. |
| `5232f6f` | Added `typed_join@0.1.0`, registry wiring, binder constraint enforcement, the R1-4 window obligations, and focused tests. |
| `aaab59c` | Wired generic typed-join synthesis, added the CAR-0 reachability target, promoted `fragile_possession_state`, and generated the first CAR proof. |
| `39631c4` | Refreshed the CAR proof for both home and away team perspectives and committed the reproducing artifacts. |
| `(this commit)` | Final report with committed-tree proof, audit table, and verification evidence. |

## Opening Obligations

| Obligation | Status | Evidence |
| --- | --- | --- |
| O1 - named both-teams composition-level test | DONE | `tests.test_r1_5_typed_join.TypedJoinOperatorTests.test_same_anchor_join_preserves_both_team_anchors` exercises home and away anchors in one join; `tests.test_r1_4_window` retains the R1-4 both-team window tests. |
| O2 - window data-boundary false FAIL | DONE | `window` now judges continuity coverage against the period-clipped requested span. Added `test_same_team_continuity_is_judged_against_clipped_observed_window`. |
| O3 - `latest_start` overlap-policy misnomer | DONE | Runtime/default/search target now use `latest_start_covering_anchor`; source grep finds only that value and historical target/concept names. |
| O4 - delete runtime `same_team_control` label | DONE | `window` continuity policy enum now declares only `fixed_duration` and `same_possession`. Remaining `same_team_control_after` strings are historical concept/target identifiers, not runtime enum values. |
| O5 - ledger/report hygiene | DONE | Generated artifacts were committed from the final proof: plan bundle, row ledger, report, and coverage-map row. Report uses clone-local commit hashes only. |

## Implementation Summary

### Operator

`typed_join@0.1.0` is a registry operator that joins two episode-set evidence
channels under declared identity and composition constraints. It is not a catalog
primitive and it does not create evidence.

Declared join keys:

- `same_anchor`
- `same_frame_window`
- `same_entity`
- `episode_overlap`

Declared composition constraints:

- `same_team_perspective_required`
- `entity_identity_preserved_required`
- `frame_alignment_required`
- `unconstrained` only with non-`none` `unconstrained_rationale`

Declared no-match policies:

- `FAIL`
- `UNKNOWN`
- `drop_with_count`

Tri-state behavior:

- If either side carries the declared status field as `UNKNOWN`, the joined row is `UNKNOWN` with `typed_join_reason=join_side_status_unknown`.
- Missing required counterpart follows the declared no-match policy.
- Dropped no-match rows record `typed_join_dropped_no_match_count` on emitted rows.

Witness behavior:

- Joined rows carry left/right record hashes, record indices, source node ids, output names, join fields, and constraint fields.
- Joined rows use `canonical_anchor_record_id` so anchor identity follows the same V8 record-identity rule as other runtime records.
- The output declaration includes the typed-join fields plus the CAR-carried fields required by the acceptance composition.

### Binder Enforcement

The binder enforces join constraints generically by detecting join-like operator
signatures, not by special-casing the `typed_join` name. A join with no enforced
constraint fails to bind unless it explicitly sets `unconstrained=true` and a
non-`none` rationale. Declared field parameters are checked against the bound
input evidence fields.

### Window Retrofit

`window` now reuses the typed-join same-team helper for continuity team checks.
The R1-4 continuity overlap default and target declaration were renamed to
`latest_start_covering_anchor`. The runtime `same_team_control` policy label was
removed; the remaining supported continuity label is `same_possession`.

### Search Synthesis

The compiler search path supports generic `typed_join` operator insertion. The
target declares side requirements and nested side composition constraints; the
builder recursively synthesizes each side, applies every declared key, and fails
if any accepted constraint key is unapplied.

The CAR-0 plan is:

```text
window(after, same_possession)
  typed_join same_anchor + same_team_perspective + frame_alignment
    typed_join pressure_on_carrier + support_arrival_point_pair
```

Search-blindness checks from the final row ledger:

| Check | Value |
| --- | --- |
| Concept-name hint used as input | `False` |
| Provider-name hint used as input | `False` |
| Coverage gold chain used as input | `False` |
| Pattern dispatch used | `False` |
| Coverage gold-chain audit | `post_hoc_only` |
| Target contract hash | `c2c755538884bf7db1532233d536675d8465cf2027d025835d6b44e96dc043c2` |

## Acceptance Proof - CAR-0

Final proof command, run on committed implementation tree `39631c4` with both
team perspectives:

```bash
PYTHONPATH=src \
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-5-typed-join-targets.v0.json \
TQE_SEARCH_UPDATE_LEDGER=1 \
TQE_SEARCH_PERSPECTIVE_TEAM_ROLES=home,away \
TQE_DATA_ROOT=/Users/luisrevilla/code/priori/data/canonical/v1 \
TQE_RAW_ROOT=/Users/luisrevilla/code/priori/data/raw/idsse/figshare-28196177-v1 \
TQE_SEARCH_SHARED_NODE_CACHE=1 \
TQE_SEARCH_NODE_CACHE_NAMESPACE=r1_5_car_both_teams \
UV_CACHE_DIR=/private/tmp/uv-cache \
uv run --no-sync python scripts/coverage_map/compiler_search_reachability.py
```

| Field | Value |
| --- | --- |
| Report status | PASS |
| Concept | `fragile_possession_state` |
| Target | `r1_5_fragile_possession_state_v0` |
| Result | `compiler_reachable` |
| Result count | 40 |
| Requested evidence failures | 0 |
| Perspective roles | `home,away` |
| Document hash | `e62cd3147bca35e432b087bc4767215c6830f4987121888b6e5934f66e269bef` |
| Runtime trace hash | `a84895fc56d20ada23928fcac5ec3bf05e0a5742f4b648eb17400191307b7129` |
| Runtime value count | 896 |
| Node-cache hits / misses | 56 / 196 |
| Terminal provider | `operator:typed_join` |
| Rules used | `generic_typed_join_operator`, `generic_window_operator`, `provider_field_backward_search` |
| Row-ledger hash | `bc5d2d989d128c7baaeaaa79283461d970dded6c411adcc77842590fa0179ab9` |
| Report hash | `65f6e0d163a9aa32ed1d3c4cbae3b0a81ac7753ecaf2a438002434078a7b5c6a` |
| Plan-bundle hash | `83dbcec28e97aaf9262680c284e1848c58555e0911cede73f5a36de6fc425cee` |

Coverage-map delta on the tracked ledger:

| Metric | Before | After |
| --- | --- | --- |
| Compiler-reachable count | 11 | 12 |
| Supported count | 362 | 363 |
| Compiler-reachable pct | 1.5% | 1.6% |
| Supported pct | 48.9% | 48.9% |

`fragile_possession_state` was added as a new supported coverage row with a
compiler-reachable evidence object. Claim boundary: observed same-team
possession continuation, carrier pressure, and support-arrival failure only; no
risk, value, intent, causation, trap, quality, or decision correctness.

## Full Booked-Evidence Audit

Audit extraction executed the committed proof bundle directly for both roles.
Artifacts are local review aids:

- `/private/tmp/r1-5-car-audit.json` (`b4991de50123a49ef20dbac81be2a9978339cca81d20fbb5cfe47a51fb456e9a`)
- `/private/tmp/r1-5-car-audit.md` (`d95bfefefcacc2b1bb15838854c84fb47f4bd9e0e869c50203e91c717b783376`)

Per-role execution:

| Role | Status | Rows | Requested evidence failures | Runtime values | Runtime trace hash |
| --- | --- | ---: | ---: | ---: | --- |
| `away` | pass | 20 | 0 | 448 | `493fbdc662b2c40a485af5fc20215c976ba40c809f456d3c8e3af5aab85e1e69` |
| `home` | pass | 20 | 0 | 448 | `d1ed7ea45a926a30f509f02bfb0b4c939a2f2e380bdaba78ed50f5a85981540d` |

Audit summary:

| Metric | Value |
| --- | --- |
| Total rows | 40 |
| `typed_join_status` distribution | PASS 40 |
| `window_status` distribution | PASS 40 |
| `pressure_status` distribution | PASS 40 |
| `support_arrival_status` distribution | FAIL 40 |
| Team-pair distribution | away->away 20; home->home 20 |

| n | result_id | exec_role | match_id | period | anchor_frame | left_team | right_team | window | pressure | support | nearest_defender_m | supporters | join_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5803ac63b35b75f6 | away | J03WOH | firstHalf | 23670 | away | away | PASS | PASS | FAIL | 2.703 |  | typed_join_matched |
| 2 | 7fb3cb48ad638950 | away | J03WOH | firstHalf | 46205 | away | away | PASS | PASS | FAIL | 2.667 |  | typed_join_matched |
| 3 | ac9eebd18fa17cfe | away | J03WOH | firstHalf | 63491 | away | away | PASS | PASS | FAIL | 3.936 |  | typed_join_matched |
| 4 | 193cf97cd374119d | away | J03WOH | firstHalf | 65279 | away | away | PASS | PASS | FAIL | 1.493 |  | typed_join_matched |
| 5 | 6cab439ec3ef2e9f | away | J03WOH | secondHalf | 101803 | away | away | PASS | PASS | FAIL | 3.293 |  | typed_join_matched |
| 6 | 16740ab21803709c | away | J03WOH | secondHalf | 106378 | away | away | PASS | PASS | FAIL | 1.788 |  | typed_join_matched |
| 7 | 47525cc0a061a797 | away | J03WOH | secondHalf | 109688 | away | away | PASS | PASS | FAIL | 2.731 |  | typed_join_matched |
| 8 | 70c5c6d5c9e363f5 | away | J03WOH | secondHalf | 111815 | away | away | PASS | PASS | FAIL | 3.292 |  | typed_join_matched |
| 9 | 30a6c71ac340917f | away | J03WOH | secondHalf | 138607 | away | away | PASS | PASS | FAIL | 1.228 |  | typed_join_matched |
| 10 | 3f92dd11a4b4e2ba | away | J03WOH | secondHalf | 156033 | away | away | PASS | PASS | FAIL | 1.744 |  | typed_join_matched |
| 11 | 7379592739c2e98c | away | J03WOH | secondHalf | 156138 | away | away | PASS | PASS | FAIL | 3.203 |  | typed_join_matched |
| 12 | 35f0d8be38533684 | away | J03WOY | firstHalf | 36730 | away | away | PASS | PASS | FAIL | 2.541 |  | typed_join_matched |
| 13 | 4b9f0611982ce415 | away | J03WOY | firstHalf | 51891 | away | away | PASS | PASS | FAIL | 3.691 |  | typed_join_matched |
| 14 | c13438b542010cc1 | away | J03WOY | secondHalf | 115230 | away | away | PASS | PASS | FAIL | 2.066 |  | typed_join_matched |
| 15 | f7eca11d3abcef45 | away | J03WOY | secondHalf | 116483 | away | away | PASS | PASS | FAIL | 2.182 |  | typed_join_matched |
| 16 | ce84ef01f98bca43 | away | J03WOY | secondHalf | 135062 | away | away | PASS | PASS | FAIL | 3.396 |  | typed_join_matched |
| 17 | 71e75ddf01dbc4e1 | away | J03WOY | secondHalf | 165768 | away | away | PASS | PASS | FAIL | 1.901 |  | typed_join_matched |
| 18 | 40b19e224a44f4cd | away | J03WPY | firstHalf | 33621 | away | away | PASS | PASS | FAIL | 2.114 |  | typed_join_matched |
| 19 | d19b889cdcaa0604 | away | J03WPY | secondHalf | 144621 | away | away | PASS | PASS | FAIL | 3.842 |  | typed_join_matched |
| 20 | fb072c3c7b6c7a1d | away | J03WPY | secondHalf | 144649 | away | away | PASS | PASS | FAIL | 3.623 |  | typed_join_matched |
| 21 | 97a9ab0f87d6fcc2 | home | J03WOH | firstHalf | 15146 | home | home | PASS | PASS | FAIL | 3.388 |  | typed_join_matched |
| 22 | d7d27f72828a42cd | home | J03WOH | firstHalf | 35484 | home | home | PASS | PASS | FAIL | 2.834 |  | typed_join_matched |
| 23 | db5e45ee4ec63d93 | home | J03WOH | firstHalf | 35922 | home | home | PASS | PASS | FAIL | 3.66 |  | typed_join_matched |
| 24 | 4bb7d465a8a8fb89 | home | J03WOH | firstHalf | 37526 | home | home | PASS | PASS | FAIL | 2.925 |  | typed_join_matched |
| 25 | ca9772f1e8a07073 | home | J03WOH | firstHalf | 49046 | home | home | PASS | PASS | FAIL | 1.972 |  | typed_join_matched |
| 26 | 6b82dbe9e1facd87 | home | J03WOH | firstHalf | 68981 | home | home | PASS | PASS | FAIL | 2.191 |  | typed_join_matched |
| 27 | a1e74c91a2626ab5 | home | J03WOH | firstHalf | 71280 | home | home | PASS | PASS | FAIL | 2.833 |  | typed_join_matched |
| 28 | 75f68814b7453293 | home | J03WOH | firstHalf | 73608 | home | home | PASS | PASS | FAIL | 2.102 |  | typed_join_matched |
| 29 | f150227a546e3151 | home | J03WOH | secondHalf | 115915 | home | home | PASS | PASS | FAIL | 3.428 |  | typed_join_matched |
| 30 | 1ba79962e4bd1615 | home | J03WOH | secondHalf | 117800 | home | home | PASS | PASS | FAIL | 2.853 |  | typed_join_matched |
| 31 | dc762c868da8bf9e | home | J03WOH | secondHalf | 119413 | home | home | PASS | PASS | FAIL | 3.444 |  | typed_join_matched |
| 32 | 8e1090ad717362fb | home | J03WOH | secondHalf | 141231 | home | home | PASS | PASS | FAIL | 2.596 |  | typed_join_matched |
| 33 | 7409d5a03993074a | home | J03WOH | secondHalf | 165401 | home | home | PASS | PASS | FAIL | 3.65 |  | typed_join_matched |
| 34 | e4832ba8b952fd2a | home | J03WOY | firstHalf | 13160 | home | home | PASS | PASS | FAIL | 3.384 |  | typed_join_matched |
| 35 | c4685898060d4cee | home | J03WOY | firstHalf | 18556 | home | home | PASS | PASS | FAIL | 3.731 |  | typed_join_matched |
| 36 | 489d20518b53d1b6 | home | J03WOY | firstHalf | 19800 | home | home | PASS | PASS | FAIL | 2.503 |  | typed_join_matched |
| 37 | d9b4be1b56132561 | home | J03WOY | firstHalf | 19891 | home | home | PASS | PASS | FAIL | 2.151 |  | typed_join_matched |
| 38 | d421b78581f86662 | home | J03WOY | firstHalf | 21392 | home | home | PASS | PASS | FAIL | 3.52 |  | typed_join_matched |
| 39 | 07ceef3915a2309c | home | J03WOY | firstHalf | 22034 | home | home | PASS | PASS | FAIL | 3.5 |  | typed_join_matched |
| 40 | ce9a07020bef29ec | home | J03WOY | firstHalf | 42928 | home | home | PASS | PASS | FAIL | 3.425 |  | typed_join_matched |

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src ... uv run python -m unittest tests.test_r1_0_operator_scaffolding tests.test_r1_4_window tests.test_r1_5_typed_join` | PASS | 34 tests in 9.653s. Covers registry ratchets, window obligations, join keys, no-match policies, UNKNOWN propagation, both-team anchors, binder constraint rejection, and unconstrained rationale. |
| `TQE_SEARCH_TARGETS=config/compiler-reachability/r1-5-typed-join-targets.v0.json TQE_SEARCH_PERSPECTIVE_TEAM_ROLES=home,away ... uv run --no-sync python scripts/coverage_map/compiler_search_reachability.py` | PASS | `compiler_reachable`, 40 rows, 0 requested evidence failures, compiler-reachable count 11 -> 12. |
| CAR booked-evidence audit extraction | PASS | 40 rows; home 20 / away 20; all team pairs same-team; all requested statuses match target semantics. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make PYTHON="uv run --no-sync python" afl-substrate-q6-verify` | PASS | Honest-zero intact; runtime trace hash `b9e24dabc23931c0de15ee665d39fcd15a6ce30de02c0fa932a012f332695f8c`. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make PYTHON="uv run --no-sync python" scp-0-verify` | PASS | SCP-0 status PASS; 58 tests OK. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make PYTHON="uv run --no-sync python" m1-1-gate-a-verify` | PASS | 450 binder validation rows pass. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make PYTHON="uv run --no-sync python" test` | PASS | 445 tests in 356.871s; runtime attestation `VERIFIED`, blocking reasons `[]`. |
| Source hygiene grep | PASS | `latest_start` appears only as `latest_start_covering_anchor`; `same_team_control` appears only in historical concept/target/projection identifiers, not runtime enum values. |

Full-suite note: the first `make test` attempt in the temp clone failed with 1
failure and 5 errors because several corpus-backed tests pass the relative path
`data/canonical/v1` into runtime calls while the fresh clone had no ignored
`data/` directory. I created a temporary ignored symlink to the canonical corpus,
reran the same command, and the corpus-backed full suite passed. The symlink was
removed afterward; the branch tree is clean.
