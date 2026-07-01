# Manifest

## Root Documents

- `README.md` - packet overview - `inspection_summary`
- `external-review-prompt.md` - reviewer instructions - `inspection_summary`
- `scope.md` - review scope and assumptions - `inspection_summary`
- `validation-output.md` - validation command summary - `command_output`
- `known-gaps.md` - limitations and risks - `inspection_summary`
- `next-steps.md` - recommended next steps - `inspection_summary`
- `changed-files.md` - diff file index - `inspection_summary`

## Plans

- `plans/ball_side_block_shift.ir.v1.json` - approved M1 parity plan - `fixture`
- `plans/opposite_corridor_after_shift.experimental.v1.json` - S4 generic plan - `fixture`
- `plans/possession_corridor_availability.experimental.v1.json` - S6 second generic plan - `fixture`

## Source Excerpts

- `source-excerpts/executor.py` - runtime execution, evidence, generic/legacy split - `source_file`
- `source-excerpts/ir.py` - IR and evidence request contract - `source_file`
- `source-excerpts/catalog.py` - primitive/relation/operator catalog - `source_file`
- `source-excerpts/binder.py` - binder validation and evidence-field checks - `source_file`
- `source-excerpts/values.py` - typed runtime value contract - `source_file`

## Verifiers

- `verifiers/m1_1_gate_s4.py` - rule-driven emission verifier - `validator`
- `verifiers/m1_1_gate_s5.py` - evidence alias verifier - `validator`
- `verifiers/m1_1_gate_s6.py` - second-pattern verifier - `validator`
- `verifiers/m1_1_gate_s7.py` - final architecture verifier - `validator`

## Generated Reports

- `artifacts/gate-s3r-verification-report.json` - S3R runtime correctness report - `generated_report`
- `artifacts/gate-s4-verification-report.json` - S4 result emission report - `generated_report`
- `artifacts/gate-s5-verification-report.json` - S5 evidence alias report - `generated_report`
- `artifacts/gate-s6-verification-report.json` - S6 second-pattern report - `generated_report`
- `artifacts/gate-s7-verification-report.json` - S7 final proof report - `generated_report`
- `artifacts/gate-b-verification-report.json` - M1 parity report - `generated_report`
- `artifacts/binder-validation-report.json` - Gate A binder/schema report - `generated_report`

## Documentation

- `docs/STRUCTURAL_CORRECTIVE_SPEC.md` - M1.1S acceptance source of truth - `documentation`
- `docs/status.yaml` - current milestone status - `documentation`
- `docs/gate-s4r-controller-review.md` - S4R controller review - `documentation`
- `docs/gate-s5-controller-review.md` - S5 controller review - `documentation`
- `docs/gate-s6-controller-review.md` - S6 controller review - `documentation`
- `docs/gate-s7-controller-review.md` - S7 controller review - `documentation`
- `docs/2026-06-20-m1-1s-gate-s4-external-review.md` - external S4 required changes - `external_reference`

## Diffs And Commands

- `diffs/m1-1s-focused.diff` - focused implementation diff - `diff`
- `diffs/m1-1s-diff-stat.txt` - diff stat - `diff`
- `diffs/m1-1s-changed-files.txt` - changed file list - `diff`
- `commands/git-log-recent.txt` - recent Git log - `command_output`
- `commands/git-show-stat-m1-1s.txt` - commit stat summary - `command_output`
