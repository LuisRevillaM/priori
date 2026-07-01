# Validation Output

## Repository state

- Working directory: `/Users/luisrevilla/Documents/priori`
- Branch: `codex/m1-1-s1-ir-binder`
- Commit: `0ae27e1d014685a7b5516832b7eff1f4046e8b95`

Command outputs:

- `commands/git-rev-parse-head.txt`
- `commands/git-branch-current.txt`
- `commands/git-status-short.txt`
- `commands/git-show-head-stat.txt`
- `commands/git-diff-stat-9febb97-to-head.txt`

At packet creation, `git status --short` contained untracked local packet artifacts and `docs/learnings.zip`; no tracked source changes were uncommitted.

## Passed validations

| Command | Status | Evidence |
| --- | --- | --- |
| `make m1-1-gate-s3r-verify` | pass, 11/0/0 | `artifacts/gate-s3r-verification-report.json` |
| `make m1-1-gate-s1-verify` | pass, 8/0/0 | `artifacts/gate-s1-verification-report.json` |
| `make m1-1-gate-b-verify` | pass, 14/0/0 | `artifacts/parity-report.json` |
| `make m1-1-gate-c-verify` | pass, 10/0/0 | `artifacts/gate-c-verification-report.json` |
| `make m1-1-gate-r5-verify` | pass, 10/0/0 | `artifacts/gate-r5-verification-report.json` |
| `make test` | pass, 26 tests | summarized in `docs/gate-s3r2-controller-review.md` |
| `git diff --check` | pass | summarized in `docs/gate-s3r2-controller-review.md` |

## Strengthened S3R proof checks

`artifacts/gate-s3r-verification-report.json` reports:

- `anchors.explicit_plan_anchor_source`: pass.
- `anchors.semantic_ids_survive_node_rename`: pass.
- `anchors.deduplicate_and_ignore_side_channels`: pass.
- `anchors.invalid_supplied_id_rejected`: pass.
- `anchors.non_m1_anchor_targetable_and_traceable`: pass.
- `temporal.persists_for_generic_tri_state`: pass.
- `frame_signal.length_mismatch_rejected`: pass.
- `frame_signal.sequence_requires_explicit_frame_ids`: pass.
- `generic_anchor_trace_source.no_m1_assumptions`: pass.
- `nodes.execution_result_contract`: pass.
- `approved_plan.parity_preserved`: pass.

## Full-repo requirement

The validation commands are not independently runnable from this packet alone.

