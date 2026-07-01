# Validation Output

Commands were run in `/Users/luisrevilla/Documents/priori` on 2026-06-20.

| Command | Result | Evidence |
| --- | --- | --- |
| `make m1-1-gate-s7r-verify` | pass, `13/0/0` | `artifacts/gate-s7r2-verification-report.json` |
| `make m1-1-gate-s4-verify` | pass, `16/0/0` | `artifacts/gate-s4-verification-report.json` |
| `make m1-1-gate-s6-verify` | pass, `8/0/0` | `artifacts/gate-s6-verification-report.json` |
| `make m1-1-gate-s7-verify` | pass, `7/0/0` | `artifacts/gate-s7-verification-report.json` |
| `make m1-1-gate-a-verify` | pass, `80/0/0` | `artifacts/binder-validation-report.json` |
| `make test` | pass, `27 OK` | controller run before commit |
| `git diff --check` | pass | `commands/git-diff-check.txt` |

## Main S7R2 Proof Checks

`artifacts/gate-s7r2-verification-report.json` contains:

- `s7r2.mixed_relation_evidence_unknown_semantics`
- `s7r2.witness_selection_scoped_to_evidence_source`
- `s7r2.raw_relation_episode_collection_predicates_rejected`
- `s7r.agent_safety_limits_enforced`
- existing S7R relation coverage, witness, count, unknown-policy, non-match, and warning-rule checks.

## Reproduction Boundary

This is an inspection packet. Re-running validation requires the full repository, canonical data, Python environment, and local Make targets.
