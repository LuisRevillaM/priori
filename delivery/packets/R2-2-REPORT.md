# R2-2 Executor Report

Branch: `packet/r2-2`

## Clone Provenance

Round 2 is being executed in clone `/private/tmp/priori-r2-2-round2-single` because the main workspace git index returned `index.lock` EPERM before edits. The director should recover round 2 via `format-patch` from clone SHA `e1558e0` plus the final report commit. Nothing is pushed.

## Round 1 Baseline

Round 1 commits on this branch:

| Commit | Purpose |
| --- | --- |
| `c742920` | Implemented the original `rate_and_share` core. |
| `0b35f6f` | Added the first flagship artifact under CAR-named surfaces. |
| `25d3b66` | Finalized the round 1 report. |
| `7787de8` | Director review: R2-2 round 1 REVISE. |

## Round 2 Item 1: Deviation And Ratification (R-AA)

Status: implemented in report and regenerated artifacts.

Process law restated: when a spec cannot be implemented as written, the executor must flag the deviation and request ratification before substituting a different question. Correctness does not transfer authority.

Degeneracy found in round 1: the literal spec population `window_status PASS / typed_join_status PASS` could not be bound honestly under the packet subset law. In the R1-5 terminal join, `typed_join_status PASS` already requires the left-side retention window (`left_status_field=window_status`, required `PASS`). Therefore all 145 final fragile PASS rows already have retention baked in. Using raw `window_status` as numerator over final `typed_join_status` also produces numerator PASS rows with denominator FAIL, which the runtime correctly raises as a subset-law violation.

Ratified populations per R-AA:

| Role | Field | Meaning |
| --- | --- | --- |
| Numerator | `typed_join_status` | Retained final fragile-condition subset. |
| Denominator | `right_status` | The right-side pressure-without-support fragile condition. |
| Added predicate | `window_status` | Same-team retention window added by the terminal join. |

Era note carried from R-AA: the condition-side concept behind `right_status` deserves a named registration in a later packet instead of remaining implicit in the terminal join.

## Honest R2-1 Source-Population And PASS-Count Reconciliation

This packet claims the correspondence that is true under the ratified recomposition:

| Check | Result |
| --- | --- |
| Same 14 role-match rows as R2-1 flagship table | TRUE |
| Source population count matches R2-1 | `8414 == 8414` |
| A count matches R2-1 `typed_join_status` PASS count | `145 == 145` |
| All 14 source populations match R2-1 row-for-row | TRUE |
| All 14 retained fragile PASS counts match R2-1 row-for-row | TRUE |

It does not claim that the ratified rate denominator interval is identical to the R2-1 denominator status interval. That would be false after changing the denominator from final `typed_join_status` to the condition-side `right_status`; the spec's original reconciliation wording was unsatisfiable under the subset law.

## Round 2 Item 2: Rename Off CAR Surfaces (R-AB)

Status: implemented.

Renamed surfaces:

| Old | New |
| --- | --- |
| `delivery/packets/r2-2-flagship/car0_retention_rate_table.json` | `delivery/packets/r2-2-flagship/fragile_retention_rate_table.json` |
| `delivery/packets/r2-2-flagship/car0_retention_rate_table.md` | `delivery/packets/r2-2-flagship/fragile_retention_rate_table.md` |
| `delivery/packets/r2-2-flagship/rate_and_share_car0_retention_v0.json` | `delivery/packets/r2-2-flagship/fragile_retention_rate_v0.json` |
| node id `rate_and_share_car0_retention` | `fragile_retention_rate` |
| target/invocation id `r2_2_rate_and_share_car0_retention_v0*` | `r2_2_fragile_retention_rate_v0*` |
| population expression `CAR-0 retained fragile-condition rate...` | `fragile-condition retention rate...` |

The original round 1 commit title remains in history; round 2 renames the live surfaces and records the correction here. Standing law restated: CAR is a player metric, and this packet is a team-level baseline.

## Round 2 Item 3: Share Amputation And Operator Rename (R-AC)

Status: implemented.

Files:

- `src/tqe/runtime/operators/rate.py`
- `src/tqe/runtime/operators/__init__.py`
- `src/tqe/runtime/binder.py`
- `tests/test_r2_2_rate.py`
- `tests/test_r1_0_operator_scaffolding.py`

Implemented:

- Renamed the registered composition operator from `rate_and_share@0.1.0` to `rate@0.1.0`.
- Renamed the implementation callable to `execute_rate` and the signature to `RATE_SIGNATURE`.
- Removed `share_key_field` and all runtime share assertion code.
- Constrained `rate_kind` to `['rate']` only.
- Added limitations text declaring correct future share semantics: key-partition counts over one common denominator, observed shares summing to 1 over known rows, interval-typed.

## Round 2 Item 4: R-AD Edge Behavior

Status: implemented.

Behavior:

| Case | Result |
| --- | --- |
| D1-only population | Emits one row with `rate_status=UNKNOWN`, `observed=None`, `lower_bound=0`, `upper_bound=0`. |
| Empty population | Emits one typed UNKNOWN row instead of zero rows. |

Focused verification:

| Command | Result |
| --- | --- |
| `PYTHONPATH=src /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r2_2_rate tests.test_r1_0_operator_scaffolding` | PASS, 25 tests |

Round 2 mutation checks:

| Mutation | Named test | Result |
| --- | --- | --- |
| Re-admit `share` to `RATE_KINDS` | `test_signature_declares_rate_as_only_rate_kind` | FAIL as expected; restored |
| Reintroduce `share_key_field` | `test_signature_does_not_advertise_share_key_field` | FAIL as expected; restored |
| Disable D1-only UNKNOWN branch | `test_d1_only_population_is_unknown_with_zero_bounds` | FAIL as expected, status regressed to `PASS`; restored |
| Disable empty-population fallback row | `test_empty_population_emits_typed_unknown_row` | FAIL as expected, zero rows emitted; restored |

## Round 2 Flagship Totals

Regenerated via `scripts/packets/r2_2_flagship_generator.py` using the committed R1-C population audit and the guarded `RateIntervalResult` constructor.

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

Generator verification:

| Command | Result |
| --- | --- |
| `PYTHONPATH=src /Users/luisrevilla/code/priori/.venv/bin/python scripts/packets/r2_2_flagship_generator.py` | PASS, 14 rows, reconciled source populations `true`, reconciled pass counts `true` |

## Full-suite table on committed tree

Status: complete.

Committed clone tree tested: `e1558e0`. The final report commit is report-only and follows this run.

Clone data setup for the run:

- `data/canonical/v1` symlinked to `/Users/luisrevilla/code/priori/data/canonical/v1`
- `data/raw/idsse/figshare-28196177-v1` symlinked to `/Users/luisrevilla/code/priori/data/raw/idsse/figshare-28196177-v1`
- Python interpreter: `/Users/luisrevilla/code/priori/.venv/bin/python`

| Command | Result | Tests | Skipped | Failures | Errors | Duration |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `make test PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python` | PASS | 499 | 0 | 0 | 0 | 452.321s |

Failure enumeration for the final committed-tree run: none.

Additional suite output: `{"attestation_status": "VERIFIED", "blocking_reasons": []}`.

Earlier clone-only attempts failed before the data symlinks were installed; those failures were attributable to missing canonical/raw data in the clone, not to R2-2 code.
