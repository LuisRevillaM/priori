# Manifest

| Packet Path | Source | Artifact Class | Why Included |
| --- | --- | --- | --- |
| `README.md` | `generated in packet` | `inspection_summary` | packet entry point |
| `artifacts/binder-validation-report.json` | `artifacts/m1.1/binder-validation-report.json` | `generated_report` | verification report evidence |
| `artifacts/gate-s4-verification-report.json` | `artifacts/m1.1/gate-s4-verification-report.json` | `generated_report` | verification report evidence |
| `artifacts/gate-s6-verification-report.json` | `artifacts/m1.1/gate-s6-verification-report.json` | `generated_report` | verification report evidence |
| `artifacts/gate-s7-verification-report.json` | `artifacts/m1.1/gate-s7-verification-report.json` | `generated_report` | verification report evidence |
| `artifacts/gate-s7r2-verification-report.json` | `artifacts/m1.1/gate-s7r-verification-report.json` | `generated_report` | verification report evidence |
| `commands/git-branch.txt` | `generated command output` | `command_output` | repo state or command evidence |
| `commands/git-diff-check.txt` | `generated command output` | `command_output` | repo state or command evidence |
| `commands/git-head.txt` | `generated command output` | `command_output` | repo state or command evidence |
| `commands/git-show-stat-head.txt` | `generated command output` | `command_output` | repo state or command evidence |
| `commands/git-status-short.txt` | `generated command output` | `command_output` | repo state or command evidence |
| `commands/report-summary.json` | `generated command output` | `command_output` | repo state or command evidence |
| `commands/secret-scan.txt` | `generated command output` | `command_output` | packet secret scan result; empty means no matches |
| `diffs/s7r2-commit.patch` | `git show HEAD` | `diff` | committed implementation patch |
| `docs/2026-06-20-m1-1s-gate-s7-external-review.md` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/2026-06-20-m1-1s-gate-s7r-external-review.md` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/2026-06-20-m1-1s-gate-s7r-relation-coverage.md` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/2026-06-20-m1-1s-gate-s7r2-agent-safety.md` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/STRUCTURAL_CORRECTIVE_SPEC.md` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/gate-s7r-controller-review.md` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/gate-s7r2-controller-review.md` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/ledger.jsonl` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/m1.1-status.yaml` | `generated in packet` | `documentation` | delivery/review documentation |
| `docs/m1.2-status.yaml` | `generated in packet` | `documentation` | delivery/review documentation |
| `external-review/s7r-decision-approve-with-required-changes-before-m1-2.txt` | `user-provided external review summarized in packet` | `external_reference` | required external finding |
| `known-gaps.md` | `generated in packet` | `inspection_summary` | non-proof boundaries |
| `next-steps.md` | `generated in packet` | `inspection_summary` | post-review path |
| `scope.md` | `generated in packet` | `inspection_summary` | binary review scope |
| `source-files/Makefile` | `git show HEAD:Makefile` | `source_file` | source required to inspect implementation |
| `source-files/ball_side_block_shift.ir.v1.json` | `git show HEAD:ball_side_block_shift.ir.v1.json` | `source_file` | source required to inspect implementation |
| `source-files/binder.py` | `git show HEAD:binder.py` | `source_file` | source required to inspect implementation |
| `source-files/capability-catalog.json` | `git show HEAD:capability-catalog.json` | `source_file` | source required to inspect implementation |
| `source-files/catalog.py` | `git show HEAD:catalog.py` | `source_file` | source required to inspect implementation |
| `source-files/executor.py` | `git show HEAD:executor.py` | `source_file` | source required to inspect implementation |
| `source-files/m1_1_gate_s4.py` | `git show HEAD:m1_1_gate_s4.py` | `source_file` | source required to inspect implementation |
| `source-files/m1_1_gate_s7r.py` | `git show HEAD:m1_1_gate_s7r.py` | `source_file` | source required to inspect implementation |
| `source-files/opposite_corridor_after_shift.experimental.v1.json` | `git show HEAD:opposite_corridor_after_shift.experimental.v1.json` | `source_file` | source required to inspect implementation |
| `source-files/possession_corridor_availability.experimental.v1.json` | `git show HEAD:possession_corridor_availability.experimental.v1.json` | `source_file` | source required to inspect implementation |
| `source-files/relations.py` | `git show HEAD:relations.py` | `source_file` | source required to inspect implementation |
| `validation-output.md` | `generated in packet` | `inspection_summary` | validation summary |
