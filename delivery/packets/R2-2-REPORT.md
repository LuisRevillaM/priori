# R2-2 Executor Report

Branch: `packet/r2-2`

## Item 1: `rate_and_share` operator and bind guards

Status: implemented and focused-test verified; first item commit pending.

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

Status: pending.

## Full-suite table on committed tree

Status: pending.
