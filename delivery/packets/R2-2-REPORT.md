# R2-2 Executor Report

Branch: `packet/r2-2`

## Item 1: `rate_and_share` operator and bind guards

Status: implemented and focused-test verified.

Commit: `c742920`.

Files:

- `src/tqe/runtime/operators/rate_and_share.py`
- `src/tqe/runtime/operators/__init__.py`
- `src/tqe/runtime/binder.py`
- `tests/test_r2_2_rate_and_share.py`
- `tests/test_r1_0_operator_scaffolding.py`

Implemented:

- Added `rate_and_share@0.1.0` as a registry citizen with `rate_records` output and evidence fields carrying A/B/C/D1/D2/E, the rate interval, and numerator/denominator count intervals.
- `RateIntervalResult` computes bounds internally from the exact joint partition and refuses caller-supplied `observed`, `lower_bound`, or `upper_bound`.
- Runtime subset invariant raises on `num PASS` with denominator `FAIL` or `UNKNOWN`.
- Degenerate denominators (`A+B+C+D1+D2 == 0`) emit typed `UNKNOWN` with no NaN/zero point estimate.
- Binder structural dispatch accepts only same-source numerator/denominator declarations, rejects removed denominator predicates, inherits R2-1 constraint gates, and keeps perspective grouping tied to same-team lineage.
- Registry ratchet now includes `rate_and_share` and extends the shared-runtime literal leak check.

Focused verification:

| Command | Result |
| --- | --- |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_r2_2_rate_and_share tests.test_r1_0_operator_scaffolding` | PASS, 22 tests |

Mutation checks:

| Mutation | Named test | Result |
| --- | --- | --- |
| Add C to observed denominator | `test_c_partition_is_not_in_observed_denominator` | FAIL as expected, observed changed from `0.5` to `0.3333333333333333`; restored |
| Drop D1 from lower-bound denominator | `test_d1_partition_remains_in_lower_bound_denominator` | FAIL as expected, lower bound changed from `0.3333333333333333` to `0.5`; restored |
| Allow numerator PASS with denominator FAIL | `test_num_pass_with_den_fail_raises` | FAIL as expected, `ValueError` not raised; restored |
| Allow numerator PASS with denominator UNKNOWN | `test_num_pass_with_den_unknown_raises` | FAIL as expected, `ValueError` not raised; restored |
| Allow external constructor bounds | `test_constructor_refuses_external_bounds` | FAIL as expected, `ValueError` not raised; restored |
| Bypass constructor ordering invariant | `test_constructor_enforces_interval_ordering_invariant` | FAIL as expected, `ValueError` not raised; restored |
| Disable same-source binder gate | `test_bind_rejects_different_source_relations` | FAIL as expected, subset-specific error disappeared; restored |
| Disable removed-predicate binder gate | `test_bind_rejects_removed_denominator_predicates` | FAIL as expected, `BindError` not raised; restored |

## Item 2: flagship CAR-0 v0 rate artifact

Status: implemented and byte-reproduction verified.

Files:

- `scripts/packets/r2_2_flagship_generator.py`
- `delivery/packets/r2-2-flagship/rate_and_share_car0_retention_v0.json`
- `delivery/packets/r2-2-flagship/provenance.json`
- `delivery/packets/r2-2-flagship/car0_retention_rate_table.json`
- `delivery/packets/r2-2-flagship/car0_retention_rate_table.md`

Implemented:

- Added a committed generator that derives the R2-2 rate plan from `delivery/packets/r1-c-sweep/plans/r1_5_fragile_possession_state_v0.json`.
- The derived plan appends `rate_and_share_car0_retention` with same-source numerator and denominator inputs from `typed_join_2.typed_join_records`.
- Numerator status: `typed_join_status` (`PASS` is retained final CAR-0 fragile state).
- Denominator status: `right_status` (the right-side fragile condition in the terminal CAR-0 join).
- The subset declaration states that `typed_join_status PASS` is the same-source retained subset of `right_status PASS`, with `window_status` as the added retention predicate; removed predicate fields are empty.
- The generator binds the derived plan, then derives the table from the committed R1-C population audit rows and routes period and merged rows through `RateIntervalResult`.

Flagship totals:

| Partition/count | Total |
| --- | ---: |
| A: numerator PASS, denominator PASS | 145 |
| B: numerator FAIL, denominator PASS | 77 |
| C: numerator UNKNOWN, denominator PASS | 54 |
| D1: numerator FAIL, denominator UNKNOWN | 0 |
| D2: numerator UNKNOWN, denominator UNKNOWN | 2560 |
| E: denominator FAIL, excluded | 5578 |
| Observed denominator count `A+B` | 222 |
| Source record count | 8414 |

R2-1 denominator reconciliation:

| Check | Result |
| --- | --- |
| Same 14 role-match rows as R2-1 flagship table | TRUE |
| Source population count matches R2-1 | `8414 == 8414` |
| A count matches R2-1 `typed_join_status` PASS count | `145 == 145` |
| All 14 source populations match R2-1 row-for-row | TRUE |
| All 14 retained fragile PASS counts match R2-1 row-for-row | TRUE |

Generator verification:

| Command | Result |
| --- | --- |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python scripts/packets/r2_2_flagship_generator.py` | PASS, 14 rows, reconciled source populations `true`, reconciled pass counts `true` |
| Hash before/after rerun for all four generated artifacts | PASS, identical hashes: `3d50a189fd82ce80b02451a65c11e8c61f784149`, `a7688ce838f8154909a0e43827d2829fe7d2923d`, `27d7b6faa343c56fb43b19b0cfc5bc6b7ad5824b`, `4699bab7c31fe4c24f88a5363b9cf3ed2d8391fa` |

## Full-suite table on committed tree

Status: complete.

Committed tree tested: `0b35f6f`.

| Command | Result | Tests | Skipped | Failures | Errors | Duration |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `make test` | PASS | 496 | 0 | 0 | 0 | 515.694s |

Failure enumeration for the committed-tree run: none.

Additional suite output: `{"attestation_status": "VERIFIED", "blocking_reasons": []}`.
