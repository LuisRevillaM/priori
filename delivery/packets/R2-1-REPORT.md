# R2-1 Aggregate Over Report

## Branch

- Branch: `packet/r2-1`
- Frontier base: `codex/afl08-passport-loop`
- Push: not pushed

## Item 1: aggregate_over operator and guards

Status: implemented, targeted tests passing.

Files:

- `src/tqe/runtime/operators/aggregate_over.py`
- `src/tqe/runtime/operators/__init__.py`
- `src/tqe/runtime/binder.py`
- `tests/test_r2_1_aggregate_over.py`

Implemented:

- Added registry citizen `aggregate_over@0.1.0` with runtime executor wiring.
- Added `AggregateIntervalResult`, whose bounds are computed internally from PASS/FAIL/UNKNOWN row partitions and whose constructor raises if external bounds are supplied.
- Added interval evidence fields: `observed`, `lower_bound`, `upper_bound`, `unknown_count`, `population_count`, `pass_count`, `fail_count`, declared population expression, grouping fields, grouping key, and source provenance.
- Added bind-time guards for declared `group_by_fields`, numeric-field compatibility for `count` vs `sum`/`mean`, team-role declaration, and inherited upstream `typed_join` constraints.
- Added focused tests for count bounds with UNKNOWN rows, external-bound rejection, both team perspectives, tri-state status rejection, positive fixture binding, undeclared group-by fields, numeric-field guards, and inherited constraint failure.

Targeted verification:

| Command | Result |
| --- | --- |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_r2_1_aggregate_over -v` | PASS, 9 tests |

Mutation checks performed:

| Guard broken | Expected failing test | Observed failure |
| --- | --- | --- |
| External bounds rejection disabled | `test_constructor_refuses_external_bounds` | FAIL, `ValueError` not raised |
| UNKNOWN rows removed from count upper bound | `test_count_bounds_include_unknown_rows` | FAIL, expected upper bound 3 but got 2 |
| Fourth status value admitted | `test_non_tri_state_status_raises` | FAIL, `ValueError` not raised |
| Declared group-by field validation disabled | `test_bind_rejects_undeclared_group_by_field` | FAIL, `BindError` not raised |
| Count/numeric guard disabled | `test_bind_rejects_count_with_numeric_field` | FAIL, required aggregate error code absent |
| Sum/mean missing-numeric guard disabled | `test_bind_rejects_sum_without_numeric_field` | FAIL, required aggregate error code absent |
| Inherited typed-join constraint guard disabled | `test_bind_rejects_uninherited_same_team_constraint` | FAIL, required aggregate error code absent |

## Item 2: flagship CAR-0 denominator artifact

Status: pending.

Required output directory:

- `delivery/packets/r2-1-flagship/`

## Full-suite table on committed tree

Status: pending final committed tree.
