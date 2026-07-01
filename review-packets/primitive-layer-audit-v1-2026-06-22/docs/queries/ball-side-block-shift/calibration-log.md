# Calibration Log - Ball-Side Block Shift

Calibration match: `J03WOH`

Evaluation matches:

- `J03WOY`
- `J03WPY`
- `J03WQQ`
- `J03WR9`

## Entries

Timestamp: 2026-06-19T18:11:48-05:00
Commit: uncommitted local worktree
Config version: `1.0.0`
Query hash: `af42853e6a3c8449e023dd98751ababbc7d34640f8751fbffa1c2bbbd0eab523`
Changed parameters: none after frozen evaluation
Reason: initial M1 Gate C calibration using `J03WOH` only
Calibration evidence: `artifacts/m1/gate-c/calibration-report.json`
Calibration counts: 47 accepted candidates on `J03WOH`: 24 `LOST_BEFORE_SWITCH`, 13 `RETAINED_NO_SWITCH`, 10 `SWITCHED`
Evaluation evidence: `artifacts/m1/gate-c/evaluation-report.json`
Evaluation counts: 180 accepted candidates across `J03WOY`, `J03WPY`, `J03WQQ`, and `J03WR9`
Proof-selected counts: 16 selected bundles: 11 `LOST_BEFORE_SWITCH`, 2 `RETAINED_NO_SWITCH`, 3 `SWITCHED`
Rejected alternatives: no threshold relaxation after evaluation; an implementation bug that truncated outcome classification to the possession segment was corrected to match the existing query definition
Reviewer/controller notes: verifier recomputes accepted predicates from canonical/raw data and checks replay-to-canonical parity; Gate C review is controller-only under owner instruction

After query freeze, no evaluation-set threshold changes are allowed without creating a new query version.
