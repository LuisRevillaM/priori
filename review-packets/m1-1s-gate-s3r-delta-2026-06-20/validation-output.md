# Validation Output

## Repository state

- Working directory: `/Users/luisrevilla/Documents/priori`
- Branch: `codex/m1-1-s1-ir-binder`
- Commit: `9febb97f681fd862b156a62316a90d6cfe75cb0c`

Command outputs included:

- `commands/git-rev-parse-head.txt`
- `commands/git-branch-current.txt`
- `commands/git-status-short.txt`
- `commands/git-show-head-stat.txt`

`git status --short` showed only untracked packet/local artifacts at packet creation time. No source changes were unstaged.

## Commands reported as passed

These commands were run in the full local repository before packaging. Their generated JSON reports are included under `artifacts/` when applicable.

| Command | Status | Evidence |
| --- | --- | --- |
| `make m1-1-gate-s3r-verify` | pass, 9/0/0 | `artifacts/gate-s3r-verification-report.json` |
| `make m1-1-gate-s1-verify` | pass, 8/0/0 | `artifacts/gate-s1-verification-report.json` |
| `make m1-1-gate-s2-verify` | pass, 4/0/0 | `artifacts/gate-s2-verification-report.json` |
| `make m1-1-gate-s3-verify` | pass, 5/0/0 | `artifacts/gate-s3-verification-report.json` |
| `make m1-1-gate-b-verify` | pass, 14/0/0 | `artifacts/gate-b-verification-report.json` |
| `make m1-1-gate-c-verify` | pass, 10/0/0 | `artifacts/gate-c-verification-report.json` |
| `make m1-1-gate-r5-verify` | pass, 10/0/0 | `artifacts/gate-r5-verification-report.json` |
| `make test` | pass, 26 tests | summarized in controller review |
| `git diff --check` | pass | summarized in controller review |

## S3R proof checks

`artifacts/gate-s3r-verification-report.json` reports:

- `anchors.explicit_plan_anchor_source`: pass.
- `anchors.semantic_ids_survive_node_rename`: pass.
- `anchors.deduplicate_and_ignore_side_channels`: pass.
- `anchors.non_m1_anchor_targetable_and_traceable`: pass.
- `temporal.persists_for_generic_tri_state`: pass.
- `frame_signal.length_mismatch_rejected`: pass.
- `generic_anchor_trace_source.no_m1_assumptions`: pass.
- `nodes.execution_result_contract`: pass.
- `approved_plan.parity_preserved`: pass.

## Validation requiring full repo

The `make` commands cannot be rerun from this packet alone. They require the full source tree, dependencies, Makefile, generated artifacts, and local data/artifact context.

