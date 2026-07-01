# Validation Output

## Controller-Run Validation

The following validations were run in `/Users/luisrevilla/Documents/priori` on 2026-06-20.

| Command | Result | Evidence |
| --- | --- | --- |
| `make m1-1-gate-s7r-verify` | pass, `10/0/0` | `artifacts/gate-s7r-verification-report.json` |
| `make m1-1-gate-s6-verify` | pass, `8/0/0` | `artifacts/gate-s6-verification-report.json` |
| `make m1-1-gate-s7-verify` | pass, `7/0/0` | `artifacts/gate-s7-verification-report.json` |
| `make m1-1-gate-a-verify` | pass, `80/0/0` | `artifacts/binder-validation-report.json` |
| `make test` | pass, `27 tests OK` | Controller transcript; summarized here |
| `python3.12 -m py_compile src/tqe/verification/m1_1_gate_s7r.py` | pass | `commands/py-compile-s7r.txt` |
| `git diff --check` | pass | `commands/git-diff-check.txt` |

## Key S7R Proof Checks

From `artifacts/gate-s7r-verification-report.json`:

- `s7r.plan_predicate_consumes_anchor_evaluations`: pass.
- `s7r.canonical_relation_coverage_pass_fail`: pass, canonical first-period slice has `22 PASS` and `14 FAIL` coverage records.
- `s7r.threshold_tightening_yields_fail_not_unknown`: pass, tightened clearance yields `36 FAIL`, `0 UNKNOWN`, and `0` emitted rows.
- `s7r.exists_tristate_from_anchor_coverage`: pass.
- `s7r.unknown_policy_semantics`: pass.
- `s7r.witness_relation_controls_evidence`: pass.
- `s7r.count_at_least_anchor_relative_tristate`: pass.
- `s7r.generic_non_match_inspection_definitive_fail`: pass.
- `s7r.agent_safety_limits_enforced`: pass.
- `s7r.include_warning_rule_decision_preserved`: pass.

## Validation Requiring Full Repo

The Make targets require the full repository, installed dependencies, and local canonical data. This packet includes source files and generated reports, but it does not include enough data to rerun the commands independently.

## Security Scan

`rg -n "api[_-]?key|secret|token|password|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|sk-[A-Za-z0-9]"` returned no matches. Evidence: `commands/secret-scan.txt`.
