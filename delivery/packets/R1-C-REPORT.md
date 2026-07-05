# R1-C Report

Branch: `packet/r1-c` from `codex/afl08-passport-loop` at
`54e12637496838355ce0122aa9c0ed410dd99e40`.

## Progress Ledger

| Item | Status | Evidence |
| --- | --- | --- |
| C1 unified sweep | DONE_WITH_CONCERNS | `delivery/packets/r1-c-sweep/` and `generated/compiler-search-v0/` |
| C2 KPI semantic-correspondence hardening | DONE | `scripts/coverage_map/compiler_search_reachability.py`, `tests/test_r1_c_checkpoint.py` |
| C3 R1-5 riders | DONE | `tests/test_r1_5_typed_join.py`, `scripts/audits/r1_5_population_audit.py`, `tests/test_r1_c_checkpoint.py` |
| C4 gate integrity manifest latency | DONE_WITH_CONCERNS | `data/manifest.json`, `src/tqe/runtime/executor.py`, `scripts/data/build_data_manifest.py`, `tests/test_executor_boundaries.py` |
| Full committed-tree suite | DONE | `make test` on committed tree `b26627c` |

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

`update_coverage_rows` now raises for any `compiler_reachable` result that
lacks either:

- `semantic_correspondence`
- certified plan reference fields: `plan_path` and `document_hash`

The positive ledger evidence now records `plan_path` alongside
`document_hash`, so a compiler-reachable flip points to the certified plan
that earned it.

Verification:

| Command | Result | Notes |
| --- | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_r1_c_checkpoint -v` | PASS | 5 tests; positive ledger update plus missing-correspondence, missing-plan, missing-hash, and non-reachable paths. |
| Mutation: break semantic-correspondence guard, then run `tests.test_r1_c_checkpoint.R1CCheckpointTests.test_update_coverage_rows_rejects_missing_semantic_correspondence` | FAIL as expected | Test errored after the guard was disabled, proving the named rejection path is load-bearing. Guard restored. |
| Mutation: break certified-plan-reference guard, then run `tests.test_r1_c_checkpoint.R1CCheckpointTests.test_update_coverage_rows_rejects_missing_certified_plan_reference` | FAIL as expected | Test errored after the guard was disabled, proving the named rejection path is load-bearing. Guard restored. |

## C3 R1-5 Riders

Rider 1: the both-teams CAR-0 composition suite now asserts
`continuity_team_role == anchor_team_role` for every accepted row.

Rider 2: committed `scripts/audits/r1_5_population_audit.py`. It has a
`summarize` path that renders `audit.md` from the committed `audit.json`, and
a `generate` path for rebuilding the full terminal-population audit from the
R1-5 plan bundle when canonical data is available.

Verification:

| Command | Result | Notes |
| --- | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_r1_c_checkpoint.R1CCheckpointTests.test_r1_5_population_audit_markdown_regenerates_from_json -v` | PASS | Committed `audit.json` renders committed `audit.md` byte-identically in-process. |
| `UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python scripts/audits/r1_5_population_audit.py summarize --audit-json delivery/packets/r1-5-population-audit/audit.json --output /private/tmp/r1_5_audit_smoke.md` + `cmp` | PASS | CLI-rendered markdown is byte-identical to committed `audit.md`. |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_r1_5_typed_join.TypedJoinCompositionSuiteTests.test_car0_composition_executes_for_both_team_perspectives -v` | PASS | 1 canonical-data composition test in 58.108s after mutation restore. |
| Mutation: temporarily invert the new continuity-team assertion and run the same named typed-join composition test | FAIL as expected | Failed on `AssertionError: 'away' == 'away'`; assertion restored and clean test rerun passed. |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m py_compile scripts/audits/r1_5_population_audit.py tests/test_r1_c_checkpoint.py tests/test_r1_5_typed_join.py` | PASS | Syntax check for changed Python files. |

## C4 Latency Manifest

Introduced `data/manifest.json` with file path, size, and sha256 entries for
the current canonical and raw data trees:

- 60 files
- 2,818,184,986 bytes covered
- manifest size: 12,048 bytes

`canonical_data_manifest_hash` now uses the repo-level manifest when it covers
the canonical root. Default verification hashes the manifest itself and checks
file existence/set/size only. `TQE_DEEP_VERIFY=1` additionally rehashes file
contents against the manifest sha256 values. If no covering manifest exists,
the old tree-hash fallback remains.

Timing:

| Command | Mode | Result | Wall time |
| --- | --- | --- | ---: |
| `UV_CACHE_DIR=/private/tmp/uv-cache /usr/bin/time -p make PYTHON="uv run --no-sync python" scp-0-verify` | before C4 | PASS | 30.95s |
| `UV_CACHE_DIR=/private/tmp/uv-cache /usr/bin/time -p make PYTHON="uv run --no-sync python" scp-0-verify` | after C4 | PASS | 31.12s |
| direct `canonical_data_manifest_hash(Path("data/canonical/v1"))` | default manifest+sizes | PASS | 0.41s |
| direct `TQE_DEEP_VERIFY=1 canonical_data_manifest_hash(Path("data/canonical/v1"))` | manifest+sizes+sha256 | PASS | 0.50s |

C4 concern: whole `scp-0-verify` wall time did not improve in this local
measurement because the target is dominated by the SCP-0 verifier/unit tests,
not by canonical-data hashing. The integrity path itself no longer reads the
182 MB canonical tree in default mode; focused tests enforce that by patching
`sha256_path` to fail if default verification attempts content hashing.

Verification:

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_canonical_data_manifest_uses_manifest_hash_without_default_content_hash tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_canonical_data_manifest_default_detects_size_mismatch tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_canonical_data_manifest_deep_verify_detects_sha_mismatch -v` | PASS | Default no-content-hash, default size mismatch, and deep sha mismatch tests. |
| `TQE_DEEP_VERIFY=1 ... canonical_data_manifest_hash(Path("data/canonical/v1"))` | PASS | Real canonical tree deep-verified against manifest sha256 values. |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m py_compile src/tqe/runtime/executor.py scripts/data/build_data_manifest.py tests/test_executor_boundaries.py` | PASS | Syntax check for changed files. |

## Verification

Full-suite table, run on committed tree `b26627c`:

| Command | Result | Tests | Runtime | Attestation | Failures |
| --- | --- | ---: | ---: | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache /usr/bin/time -p make PYTHON="uv run --no-sync python" test` | PASS | 457 | 450.095s (`real 450.99`) | `VERIFIED`, blocking reasons `[]` | None |

Failure attribution: no full-suite failures.

## Local Commits

| Commit | Scope |
| --- | --- |
| `3d2c9cb` | C1 unified compiler sweep evidence and initial report |
| `7dca26e` | C2 correspondence/plan-reference hardening and tests |
| `8f317e0` | C3 typed-join assertion and R1-5 audit generator |
| `b26627c` | C4 data manifest integrity checks and timing report |

No push performed.
