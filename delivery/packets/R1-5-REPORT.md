# R1-5 Report - typed_join Operator

Branch: `packet/r1-5`  
Frontier base: `de7748a`  
Packet: `delivery/packets/R1-5-typed-join.md`  
Round-2 review: `delivery/packets/R1-5-REVIEW.md`  
ADR: `docs/adr/0013-r1-operator-era.md`, including Addendum 4  
Push: no push, per direct-channel protocol.

## Result

READY FOR REVIEW.

The work is committed in the writable clone at `/private/tmp/priori-r1-5-clone`,
branch `packet/r1-5`.

Stage-committed-from-first-commit was satisfied by `65765be`. Round 2 also
satisfied the review's first-commit order: `6fca2f5` added the named
both-teams composition-level suite test and the executor-path chain test before
any authority or semantic changes.

## Commit Ledger

| Commit | Purpose |
| --- | --- |
| `65765be` | Stage-committed the R1-5 report skeleton before implementation. |
| `5232f6f` | Added `typed_join@0.1.0`, registry wiring, binder constraint enforcement, the R1-4 window obligations, and focused tests. |
| `aaab59c` | Wired generic typed-join synthesis, added the CAR-0 reachability target, promoted `fragile_possession_state`, and generated the first CAR proof. |
| `39631c4` | Refreshed the CAR proof for both home and away team perspectives. |
| `61258d6` | Finalized the round-1 report. |
| `6fca2f5` | R-N first commit: composition-level both-team suite test and executor-path chain test. |
| `d54fde0` | R-M: restored R1-4 provenance, reverted the tracked ledger flip/deletions, and republished the delta on a copy ledger. |
| `9177e90` | R-O: input-derived typed_join output declarations, per-side status values, predicate targeting, regenerated proof fixture/artifacts. |
| `8114bcf` | R-P: committed full-population audit artifacts with UNKNOWN accounting. |
| `(this commit)` | Final round-2 report and verification table. |

## Round-2 Review Items

| Item | Status | Evidence |
| --- | --- | --- |
| R-N first commit | DONE | `6fca2f5`; `TypedJoinCompositionSuiteTests.test_car0_composition_executes_for_both_team_perspectives` executes the generated CAR-0 composition for both `home` and `away`; `test_car0_executor_path_chains_window_into_typed_join` proves the executor path chains `window` into terminal `typed_join`. |
| R-M director authority boundary | DONE | Tracked generated ledger remains unflipped; R1-4 plan bundle is restored at `generated/compiler-search-v0/plans/r1_4_same_team_control_after_reception_v0.json`; CAR-0 delta is measured only on `/private/tmp/r1-5-copy-ledger/coverage-map.work.json` and published under `delivery/packets/r1-5-copy-proof/`. |
| R-O input-derived outputs and side statuses | DONE | Static `typed_join` evidence fields are generic only; generated typed_join nodes derive output fields from bound inputs. `left_required_status_value` / `right_required_status_value` are declared and recorded. Inner CAR join now requires pressure `PASS` on the left and support-arrival `FAIL` on the right. The only generated predicate is terminal `typed_join_status == PASS`. |
| R-P full-population audit | DONE | `delivery/packets/r1-5-population-audit/audit.json` and `.md` are committed in-tree. The audit counts every terminal joined record across seven matches, two periods, and both team perspectives before result truncation. |

## Implementation Summary

### Operator

`typed_join@0.1.0` is a registry operator that joins two episode-set evidence
channels under declared identity and composition constraints. It is not a
catalog primitive and it does not create football evidence.

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

- If either declared side status is `UNKNOWN`, the joined row is `UNKNOWN` with `typed_join_reason=join_side_status_unknown`.
- Missing required counterpart follows the declared no-match policy.
- Dropped no-match rows record `typed_join_dropped_no_match_count` on emitted rows.

Witness behavior:

- Joined rows carry left/right record hashes, record indices, source node ids, output names, join fields, side status requirements, and constraint fields.
- Joined rows use `canonical_anchor_record_id` so anchor identity follows the same V8 record-identity rule as other runtime records.

### Output Declarations

Addendum 4 forbids static CAR-specific output declarations in the operator
source. The static `typed_join` signature now declares only generic join fields.
When compiler search synthesizes a specific typed join, the emitted operator node
declares output evidence fields derived from the bound left and right inputs
plus generic join fields. CAR fields such as `window_status`, `pressure_status`,
and `support_arrival_status` therefore appear in the CAR proof plan because the
bound input channels carry them, not because `typed_join.py` knows about CAR.

### Side-Specific Status Values

The round-1 target had to enforce support failure with a side-provider predicate
because `typed_join` exposed only one `required_status_value`. Round 2 adds
side-specific values while preserving the legacy default:

- `required_status_value`: compatibility default
- `left_required_status_value`: left side requirement
- `right_required_status_value`: right side requirement

The CAR inner join now declares:

```text
left_status_field=pressure_status
left_required_status_value=PASS
right_status_field=support_arrival_status
right_required_status_value=FAIL
```

The regenerated plan has only one predicate:

```text
typed_join_2.typed_join_status == PASS
```

`window_status`, `pressure_status`, and `support_arrival_status` remain requested
evidence from `typed_join_2.typed_join_records`, but they are no longer separate
side-provider predicates.

### Search Synthesis

The compiler search path supports generic `typed_join` insertion. The target
declares side requirements and nested side composition constraints; the builder
recursively synthesizes each side, applies every declared key, and fails if any
accepted constraint key is unapplied.

The CAR-0 plan is:

```text
window(after, same_possession)
  typed_join same_anchor + same_team_perspective + frame_alignment
    typed_join pressure_on_carrier + support_arrival_point_pair
```

Search-blindness checks from the regenerated row ledger:

| Check | Value |
| --- | --- |
| Concept-name hint used as input | `False` |
| Provider-name hint used as input | `False` |
| Coverage gold chain used as input | `False` |
| Pattern dispatch used | `False` |
| Coverage gold-chain audit | `post_hoc_only` |

## Copy-Ledger Acceptance Proof

Round 2 does not flip the tracked generated ledger. The delta is measured on a
copy ledger only.

Proof command:

```bash
PYTHONPATH=src \
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-5-typed-join-targets.v0.json \
TQE_SEARCH_LEDGER=/private/tmp/r1-5-copy-ledger/coverage-map.work.json \
TQE_SEARCH_UPDATE_LEDGER=1 \
TQE_SEARCH_OUT_DIR=delivery/packets/r1-5-copy-proof/search-run \
TQE_SEARCH_REPORT=delivery/packets/r1-5-copy-proof/compiler-search-v0-report.json \
TQE_SEARCH_PERSPECTIVE_TEAM_ROLES=home,away \
TQE_SEARCH_MATCH_IDS=J03WOH \
TQE_DATA_ROOT=/Users/luisrevilla/code/priori/data/canonical/v1 \
TQE_RAW_ROOT=/Users/luisrevilla/code/priori/data/raw/idsse/figshare-28196177-v1 \
TQE_SEARCH_SHARED_NODE_CACHE=1 \
TQE_SEARCH_NODE_CACHE_NAMESPACE=r1_5_round2_ro_proof_j03woh \
UV_CACHE_DIR=/private/tmp/uv-cache \
uv run --no-sync python scripts/coverage_map/compiler_search_reachability.py
```

| Field | Value |
| --- | --- |
| Report status | PASS |
| Target | `r1_5_fragile_possession_state_v0` |
| Result | `compiler_reachable` |
| Result count | 24 |
| Requested evidence failures | 0 |
| Perspective roles | `home,away` |
| Match scope | `J03WOH` |
| Document hash | `ae4d5b3915454e78ff11b81f88cd302b3564c12de1af978a52b3c420ba69c20e` |
| Runtime trace hash | `cdf7a6d45b873193acbde88990b3b72322cf56e1ba81935c498e96efb93b066e` |
| Runtime value count | 116 |
| Node-cache hits / misses | 8 / 28 |
| Terminal provider | `operator:typed_join` |
| Rules used | `generic_typed_join_operator`, `generic_window_operator`, `provider_field_backward_search` |
| Plan-bundle hash | `44f90db1cf9949323d30dc2fe90587b61549edab0942994732901f75c8db060c` |
| Row-ledger hash | `717aa853b4290ae49457bb4e8f469d227ac74dd6c733422682adc0933a66d2f3` |
| Report hash | `ea585bb7207b5fbee5bb562e1685f9048083a9218dd785028dc20840b40630d3` |
| Coverage-delta hash | `96f1c308cd5cc17afe94f79b278beb38520a19e8ef3428cc5063facb1a7fa07b` |

Copy-ledger delta:

| Metric | Before tracked ledger | After copy ledger | Delta |
| --- | ---: | ---: | ---: |
| Compiler-reachable count | 11 | 12 | +1 |
| Supported count | 363 | 363 | 0 |
| Tracked ledger mutated | false | false | n/a |

The tracked row for `fragile_possession_state` is supported but unflipped; the
director-owned acceptance flip remains outside executor authority.

## Full-Population Audit

The audit executes the terminal anchor source directly across all seven matches,
both periods, and both team perspectives. It reads terminal joined records before
result truncation, so the `max_results=100` binder limit does not cap the
population denominator.

Artifacts:

- `delivery/packets/r1-5-population-audit/audit.json`
  - SHA-256 `4ece84ae78c1d66a212b36215d9ff5dd3702e3e47e31adf4d39ca60781718278`
- `delivery/packets/r1-5-population-audit/audit.md`
  - SHA-256 `39482ea0af272aa8d8251e7c06001050bb3db7bd9539e6286e5a610009432859`

Audit summary:

| Metric | Value |
| --- | ---: |
| Terminal rows | 8,414 |
| Terminal population hash | `5cb6279ffb2ac055c20dcb928de42ea728916d3d6a07003b9b4479033b7706ab` |
| Requested-evidence missing rows | 5,654 |

Status distributions:

| Field | Distribution |
| --- | --- |
| `typed_join_status` | FAIL 2,615; PASS 145; UNKNOWN 5,654 |
| `window_status` | FAIL 1,420; PASS 2,292; UNKNOWN 4,702 |
| `pressure_status` | FAIL 5,138; None 2,560; PASS 716 |
| `support_arrival_status` | FAIL 3,308; None 2,560; PASS 2,546 |

UNKNOWN accounting:

| Unknown source | Rows |
| --- | ---: |
| `typed_join_status == UNKNOWN` | 5,654 |
| `window_status == UNKNOWN` | 4,702 |
| `pressure_status == UNKNOWN` | 0 |
| `support_arrival_status == UNKNOWN` | 0 |

Role totals:

| Role | Rows | FAIL | PASS | UNKNOWN |
| --- | ---: | ---: | ---: | ---: |
| `away` | 4,207 | 1,163 | 72 | 2,972 |
| `home` | 4,207 | 1,452 | 73 | 2,682 |

This replaces the round-1 capped booked-evidence table. The earlier 40-row table
was accepted-result evidence only; it did not disclose the UNKNOWN/FAIL
population denominator.

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src ... uv run --no-sync python -m unittest tests.test_r1_5_typed_join` | PASS | 12 tests in 93.751s after regenerating the fixture. |
| `PYTHONPATH=src ... uv run --no-sync python -m unittest tests.test_r1_0_operator_scaffolding tests.test_r1_4_window tests.test_r1_5_typed_join` | PASS | 37 tests in 110.520s. |
| `TQE_SEARCH_TARGETS=config/compiler-reachability/r1-5-typed-join-targets.v0.json ... TQE_SEARCH_MATCH_IDS=J03WOH ... uv run --no-sync python scripts/coverage_map/compiler_search_reachability.py` | PASS | Copy-ledger proof: compiler-reachable, 24 rows, 0 requested evidence failures, copy delta 11 -> 12. |
| R1-5 full-population audit generator | PASS | 8,414 terminal rows; PASS 145 / FAIL 2,615 / UNKNOWN 5,654; artifacts committed in-tree. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make PYTHON="uv run --no-sync python" test` | PASS | Post-report-commit run on `e8f9d7a`: 448 tests in 449.634s; runtime attestation `VERIFIED`, blocking reasons `[]`. Required temporary ignored symlinks from clone-local `data/canonical/v1` and `data/raw/idsse/figshare-28196177-v1` to the canonical corpus, then symlinks were removed. |

## Notes for Review

- The static `typed_join` operator no longer declares CAR/provider fields.
- The regenerated plan intentionally declares CAR fields only on the emitted
  typed_join nodes because their bound inputs carry those fields.
- Predicate targeting is terminal-only for CAR-0. Side facts are enforced by
  side-specific join parameters and surfaced as requested evidence.
- The copy proof is scoped to `J03WOH` for review speed; the full-population
  audit spans all seven matches.
- The tracked generated ledger and R1-4 provenance remain restored. The
  director-owned coverage flip is measured but not performed by this branch.
