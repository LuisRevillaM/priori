# Manifest

| Packet path | Source repo path or command | Why included | Class |
| --- | --- | --- | --- |
| `README.md` | generated for packet | Executive overview and review map | inspection_summary |
| `scope.md` | generated for packet | Review scope and non-scope | inspection_summary |
| `changed-files.md` | generated for packet | Changed surface inventory | inspection_summary |
| `validation-output.md` | generated for packet | Validation summary | inspection_summary |
| `known-gaps.md` | generated for packet | Residual risks and non-proofs | inspection_summary |
| `next-steps.md` | generated for packet | Requested reviewer decision | inspection_summary |
| `external-review-prompt.md` | generated for packet | Relay-ready prompt | inspection_summary |
| `commands/git-rev-parse-head.txt` | `git rev-parse HEAD` | Exact commit | command_output |
| `commands/git-branch-current.txt` | `git branch --show-current` | Branch context | command_output |
| `commands/git-status-short.txt` | `git status --short` | Worktree state at packet creation | command_output |
| `commands/git-show-head-stat.txt` | `git show --stat --oneline HEAD` | Commit summary | command_output |
| `commands/git-diff-stat-0ae27e1-to-head.txt` | `git diff --stat 0ae27e1..HEAD` | S3R3 delta stat | command_output |
| `diffs/s3r3-delta-0ae27e1-to-d4e34d3.patch` | `git diff --find-renames 0ae27e1..HEAD` | Exact corrective delta | diff |
| `diffs/commit-d4e34d3-full.patch` | `git show --format=fuller --find-renames HEAD` | Full commit patch | diff |
| `artifacts/gate-s3r-verification-report.json` | `artifacts/m1.1/gate-s3r-verification-report.json` | Direct S3R3 proof report | generated_report |
| `artifacts/gate-c-verification-report.json` | `artifacts/m1.1/gate-c-verification-report.json` | Target/trace regression | generated_report |
| `artifacts/gate-r5-verification-report.json` | `artifacts/m1.1/gate-r5-verification-report.json` | Architecture/parity regression | generated_report |
| `artifacts/parity-report.json` | `artifacts/m1.1/parity-report.json` | Frozen M1 parity | generated_report |
| `docs/2026-06-20-m1-1s-gate-s3r2-external-review.md` | `docs/reviews/2026-06-20-m1-1s-gate-s3r2-external-review.md` | Review S3R3 responds to | documentation |
| `docs/2026-06-20-m1-1s-gate-s3r-external-review.md` | `docs/reviews/2026-06-20-m1-1s-gate-s3r-external-review.md` | Prior rejection context | documentation |
| `docs/gate-s3r3-controller-review.md` | `delivery/m1.1/reviews/gate-s3r3-controller-review.md` | Controller acceptance | documentation |
| `docs/gate-s3r2-controller-review.md` | `delivery/m1.1/reviews/gate-s3r2-controller-review.md` | Prior controller review context | documentation |
| `docs/STRUCTURAL_CORRECTIVE_SPEC.md` | `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md` | Milestone/gate source of truth | documentation |
| `docs/status.yaml` | `delivery/m1.1/status.yaml` | Current milestone status | documentation |
| `docs/2026-06-20-m1-1s-gate-s3r3-profile-temporal-correction.md` | `docs/learnings/2026-06-20-m1-1s-gate-s3r3-profile-temporal-correction.md` | Durable learning | documentation |
| `source-files/executor.py` | `src/tqe/runtime/executor.py` | Runtime implementation | source_file |
| `source-files/values.py` | `src/tqe/runtime/values.py` | Runtime value context | source_file |
| `source-files/ir.py` | `src/tqe/runtime/ir.py` | Type/model context | source_file |
| `source-files/binder.py` | `src/tqe/runtime/binder.py` | Binder context | source_file |
| `source-files/catalog.py` | `src/tqe/runtime/catalog.py` | Catalog/operator context | source_file |
| `source-files/m1_1_gate_s3r.py` | `src/tqe/verification/m1_1_gate_s3r.py` | Strengthened verifier | test |
| `source-files/m1_1_gate_r5.py` | `src/tqe/verification/m1_1_gate_r5.py` | Regression verifier | test |
| `configs/ball_side_block_shift.ir.v1.json` | `config/query-plans/ball_side_block_shift.ir.v1.json` | Approved M1 plan | fixture |
| `configs/opposite_corridor_after_shift.experimental.v1.json` | `config/query-plans/opposite_corridor_after_shift.experimental.v1.json` | Second plan context | fixture |
| `schemas/tactical-query-plan.schema.json` | `generated/tactical-query-plan.schema.json` | Generated schema | schema |
| `schemas/tactical-query-plan.types.ts` | `generated/tactical-query-plan.types.ts` | Generated TS contract | schema |
| `schemas/capability-catalog.json` | `generated/capability-catalog.json` | Generated capability catalog | schema |

