# Manifest

| Packet path | Source repo path or command | Why included | Class |
| --- | --- | --- | --- |
| `README.md` | generated for packet | Reviewer overview and review map | inspection_summary |
| `scope.md` | generated for packet | Defines review scope and non-scope | inspection_summary |
| `changed-files.md` | generated for packet | Inventory of changed surfaces | inspection_summary |
| `validation-output.md` | generated for packet | Validation summary and evidence mapping | inspection_summary |
| `known-gaps.md` | generated for packet | Explicit residual risk and non-proofs | inspection_summary |
| `next-steps.md` | generated for packet | Requested reviewer decision and follow-up | inspection_summary |
| `external-review-prompt.md` | generated for packet | Relay-ready prompt for external reviewer | inspection_summary |
| `commands/git-rev-parse-head.txt` | `git rev-parse HEAD` | Exact commit ID | command_output |
| `commands/git-branch-current.txt` | `git branch --show-current` | Branch context | command_output |
| `commands/git-status-short.txt` | `git status --short` | Worktree state at packet creation | command_output |
| `commands/git-show-head-stat.txt` | `git show --stat --oneline HEAD` | Commit summary and changed-file stat | command_output |
| `diffs/commit-9febb97-full.patch` | `git show --format=fuller --find-renames HEAD` | Exact implementation diff | diff |
| `artifacts/gate-s3r-verification-report.json` | `artifacts/m1.1/gate-s3r-verification-report.json` | Direct S3R proof report | generated_report |
| `artifacts/gate-s1-verification-report.json` | `artifacts/m1.1/gate-s1-verification-report.json` | Regression evidence | generated_report |
| `artifacts/gate-s2-verification-report.json` | `artifacts/m1.1/gate-s2-verification-report.json` | Regression evidence | generated_report |
| `artifacts/gate-s3-verification-report.json` | `artifacts/m1.1/gate-s3-verification-report.json` | Regression evidence | generated_report |
| `artifacts/gate-b-verification-report.json` | `artifacts/m1.1/gate-b-verification-report.json` | Parity/baseline regression evidence | generated_report |
| `artifacts/gate-c-verification-report.json` | `artifacts/m1.1/gate-c-verification-report.json` | Trace/non-match regression evidence | generated_report |
| `artifacts/gate-r5-verification-report.json` | `artifacts/m1.1/gate-r5-verification-report.json` | Generality and runtime-control regression evidence | generated_report |
| `artifacts/parity-report.json` | `artifacts/m1.1/parity-report.json` | Frozen parity evidence | generated_report |
| `docs/2026-06-20-m1-1s-gate-s3-external-review.md` | `docs/reviews/2026-06-20-m1-1s-gate-s3-external-review.md` | Blocking external decision S3R addresses | documentation |
| `docs/2026-06-20-m1-1s-gate-s3r-explicit-anchor-contract.md` | `docs/learnings/2026-06-20-m1-1s-gate-s3r-explicit-anchor-contract.md` | Durable implementation learning | documentation |
| `docs/STRUCTURAL_CORRECTIVE_SPEC.md` | `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md` | Milestone/gate source of truth | documentation |
| `docs/status.yaml` | `delivery/m1.1/status.yaml` | Current milestone status | documentation |
| `docs/gate-s3r-controller-review.md` | `delivery/m1.1/reviews/gate-s3r-controller-review.md` | Controller review and acceptance | documentation |
| `source-files/ir.py` | `src/tqe/runtime/ir.py` | Plan/bound model changes | source_file |
| `source-files/binder.py` | `src/tqe/runtime/binder.py` | Anchor source validation | source_file |
| `source-files/catalog.py` | `src/tqe/runtime/catalog.py` | Anchor outputs and operator contract | source_file |
| `source-files/values.py` | `src/tqe/runtime/values.py` | RuntimeValue records and frame mismatch behavior | source_file |
| `source-files/executor.py` | `src/tqe/runtime/executor.py` | Execution, anchor, target, trace, and temporal semantics | source_file |
| `source-files/m1_1_gate_s3r.py` | `src/tqe/verification/m1_1_gate_s3r.py` | S3R verifier implementation | test |
| `source-files/m1_1_gate_r5.py` | `src/tqe/verification/m1_1_gate_r5.py` | R5 verifier updated for anchor source | test |
| `configs/ball_side_block_shift.ir.v1.json` | `config/query-plans/ball_side_block_shift.ir.v1.json` | Approved plan with anchor source | fixture |
| `configs/opposite_corridor_after_shift.experimental.v1.json` | `config/query-plans/opposite_corridor_after_shift.experimental.v1.json` | Second plan with anchor source | fixture |
| `schemas/tactical-query-plan.schema.json` | `generated/tactical-query-plan.schema.json` | Generated plan schema | schema |
| `schemas/tactical-query-plan.types.ts` | `generated/tactical-query-plan.types.ts` | Generated TypeScript contract | schema |
| `schemas/capability-catalog.json` | `generated/capability-catalog.json` | Generated capability catalog | schema |
