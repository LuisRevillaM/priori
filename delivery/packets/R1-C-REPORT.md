# R1-C Report

Branch: `packet/r1-c` from `codex/afl08-passport-loop` at
`54e12637496838355ce0122aa9c0ed410dd99e40`.

## Progress Ledger

| Item | Status | Evidence |
| --- | --- | --- |
| C1 unified sweep | DONE_WITH_CONCERNS | `delivery/packets/r1-c-sweep/` and `generated/compiler-search-v0/` |
| C2 KPI semantic-correspondence hardening | NOT_STARTED | Pending |
| C3 R1-5 riders | NOT_STARTED | Pending |
| C4 gate integrity manifest latency | NOT_STARTED | Pending |
| Full committed-tree suite | NOT_STARTED | Pending |

## C1 Unified Sweep

Command:

```bash
TQE_SEARCH_TARGETS=delivery/packets/r1-c-sweep/targets.v0.json \
TQE_SEARCH_OUT_DIR=generated/compiler-search-v0 \
TQE_SEARCH_REPORT=delivery/packets/r1-c-sweep/compiler-search-v0-report.json \
TQE_SEARCH_UPDATE_LEDGER=0 \
TQE_SEARCH_PERSPECTIVE_TEAM_ROLES=home,away \
TQE_SEARCH_SHARED_NODE_CACHE=0 \
TQE_SEARCH_WORKERS=4 \
TQE_SEARCH_NODE_CACHE_ROOT=/private/tmp/priori-r1-c-node-cache \
UV_CACHE_DIR=/private/tmp/uv-cache \
uv run --no-sync python scripts/coverage_map/compiler_search_reachability.py
```

Result: PASS. The invocation searched all 14 targets from the pre-era
`search-targets.v0.json` file plus R1-1 through R1-5. It found 12
compiler-reachable rows and left `generated/coverage-map.json` untouched
(`TQE_SEARCH_UPDATE_LEDGER=0`).

Artifacts:

- `delivery/packets/r1-c-sweep/targets.v0.json`
- `delivery/packets/r1-c-sweep/compiler-search-v0-report.json`
- `delivery/packets/r1-c-sweep/row-ledger.json`
- `delivery/packets/r1-c-sweep/row-ledger.csv`
- `delivery/packets/r1-c-sweep/plans/*.json`
- `generated/compiler-search-v0/row-ledger.json`
- `generated/compiler-search-v0/row-ledger.csv`
- `generated/compiler-search-v0/plans/*.json`

Sweep summary:

| Target | Rows searched | Rows compiler_reachable | Correspondence status |
| --- | ---: | ---: | --- |
| `search_heldout_carry_displacement_v0` | 40 | 40 | NOT_DECLARED |
| `search_heldout_support_arrival_v0` | 40 | 40 | NOT_DECLARED |
| `search_carry_progression_v0` | 40 | 40 | NOT_DECLARED |
| `search_direct_pressure_candidate_v0` | 40 | 40 | NOT_DECLARED |
| `search_post_regain_retention_v0` | 40 | 40 | NOT_DECLARED |
| `search_heldout_shape_expansion_v0` | 40 | 40 | NOT_DECLARED |
| `search_carry_out_of_pressure_v0` | 2 | 2 | NOT_DECLARED |
| `search_penetration_support_response_v0` | 0 | 0 | N/A, `missing_constraint` |
| `search_expected_pass_completion_v0` | 0 | 0 | N/A, `unsupported_modality` |
| `r1_1_goalward_axis_projection_v0` | 40 | 40 | PASS |
| `r1_2_pressure_distance_delta_v0` | 40 | 40 | PASS |
| `r1_3_argmin_defender_distance_v0` | 40 | 40 | PASS |
| `r1_4_same_team_control_after_reception_v0` | 40 | 40 | PASS |
| `r1_5_fragile_possession_state_v0` | 40 | 40 | PASS |

C1 finding: the unified sweep proves 12 compiler-reachable rows in one
invocation on one tree, but only the five R1 target rows carry declared
`semantic_correspondence` in their source target files. The seven reachable
pre-era rows from `search-targets.v0.json` are reported as NOT_DECLARED.
This is a deviation from the packet's expected "12/12 with correspondence
PASS" and is recorded here as a finding, not fixed in C1.

Operational note: an earlier serial attempt was interrupted before artifacts
were written because it was spending time deep-copying shared node cache
entries. The committed C1 evidence is the completed four-worker invocation
above with shared node cache disabled.

## C2 KPI Semantic-Correspondence Hardening

Pending.

## C3 R1-5 Riders

Pending.

## C4 Latency Manifest

Pending.

## Verification

Full committed-tree `make test` is pending final item completion.
