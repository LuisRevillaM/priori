# R2-1 Aggregate Over Report

## Branch And Recovery

- Branch: `packet/r2-1`
- Frontier base: `codex/afl08-passport-loop`
- Push: not pushed
- Original workspace commit succeeded for the first item, then `.git/index.lock` failed with EPERM on the second commit.
- Recovery clone: `/private/tmp/priori-r2-1-work`
- Director recovery: use `format-patch` from the clone commits below.

Clone commits:

| SHA | Commit |
| --- | --- |
| `2948880` | `Add interval aggregate_over operator` |
| `88b47cb` | `Add R2-1 flagship aggregate table` |
| `d1b195d` | `Update operator scaffolding for aggregate_over` |

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
- Added bind-time guards for declared `group_by_fields`, numeric-field compatibility for `count` vs `sum`/`mean`, team-role declaration, and inherited upstream join-composition constraints.
- Added state-level grouping support for the declared runtime identity field `perspective_team_role`, used by the flagship denominator table.
- Added focused tests for count bounds with UNKNOWN rows, external-bound rejection, both team perspectives, state perspective grouping, tri-state status rejection, positive fixture binding, undeclared group-by fields, numeric-field guards, and inherited constraint failure.

Targeted verification:

| Command | Result |
| --- | --- |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_r2_1_aggregate_over -v` | PASS, 10 tests |

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

Status: implemented.

Output directory:

- `delivery/packets/r2-1-flagship/`

Files:

- `delivery/packets/r2-1-flagship/aggregate_over_fragile_possession_state_v0.json`
- `delivery/packets/r2-1-flagship/provenance.json`
- `delivery/packets/r2-1-flagship/fragile_possession_state_denominator_table.json`
- `delivery/packets/r2-1-flagship/fragile_possession_state_denominator_table.md`

Flagship query:

- Denominator: `fragile_possession_state typed_join rows per team perspective per match`
- Aggregation kind: `count`
- Declared grouping key: `perspective_team_role`, `match_id`
- Status field: `typed_join_status`
- Population source: `typed_join_2.typed_join_records` in the certified R1-5 fragile possession state plan

Fresh operator-run totals:

| Metric | Value |
| --- | ---: |
| Role-match rows | 14 |
| Observed PASS rows | 145 |
| Lower bound | 145 |
| Upper bound | 5799 |
| UNKNOWN rows | 5654 |
| FAIL rows | 2615 |
| Population rows | 8414 |

Sealed audit reconciliation:

| Sealed audit field | Sealed value | Aggregate value |
| --- | ---: | ---: |
| `typed_join_status.PASS` | 145 | 145 |
| `typed_join_status.FAIL` | 2615 | 2615 |
| `typed_join_status.UNKNOWN` | 5654 | 5654 |
| `total_rows` | 8414 | 8414 |

Every one of the 14 role-match rows matches the sealed audit's PASS/FAIL/UNKNOWN counts for the same role and match.

## Item 3: registry test hardening

Status: implemented.

Files:

- `tests/test_r1_0_operator_scaffolding.py`
- `src/tqe/runtime/binder.py`

Implemented:

- Updated explicit operator-registry expectations to include `aggregate_over@0.1.0`.
- Kept the R1 shared-runtime literal ratchet green by removing the aggregate binder's hard-coded upstream operator-name literal; the guard now requires the upstream composition output to expose the inherited constraint parameters.
- Hardened the registry assertion so it inspects the executor module registry without constructing `TacticalQueryExecutor`, avoiding unrelated canonical-data requirements in a registry-only test.

Targeted verification:

| Command | Result |
| --- | --- |
| `PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python PYTHONPATH=/private/tmp/priori-r2-1-work/src /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r1_0_operator_scaffolding.R10OperatorScaffoldingTests.test_operator_registry_is_explicit_and_complete tests.test_r1_0_operator_scaffolding.R10OperatorScaffoldingTests.test_r1_operator_names_do_not_leak_into_shared_runtime_code tests.test_r2_1_aggregate_over -v` | PASS, 12 tests |

## Full-suite table on committed tree

Committed tree tested: clone commit `d1b195d` in `/private/tmp/priori-r2-1-work`.

Environment note: the clone needed untracked local test data copied from the source workspace (`data/canonical/v1` and seven `data/raw/idsse/figshare-28196177-v1/*/tracking.xml` files) because the source repo's `.git/index.lock` EPERM required a `/private/tmp` recovery clone.

| Command | Result | Tests | Skipped | Failures | Errors | Duration |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python make test` | PASS | 473 | 42 | 0 | 0 | 432.952s |

Failure enumeration for the final committed-tree run: none.
