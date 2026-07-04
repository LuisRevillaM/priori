# R1-4 Report - window + trace_back_from_outcome Operator

Branch: `packet/r1-4`
Frontier base: `a0a1709`
Packet: `delivery/packets/R1-4-window-trace-back.md`
ADR: `docs/adr/0013-r1-operator-era.md`, including all addenda
Push: no push, per direct-channel protocol.

## Result

IN PROGRESS. This report was stage-committed before implementation, per the R1
operator packet protocol.

The canonical repository's `.git` directory is not writable from this sandbox,
so this work is committed in the writable clone at
`/private/tmp/priori-r1-4-clone`, branch `packet/r1-4`.

## Required Acceptance Items

| Item | Status | Notes |
| --- | --- | --- |
| `window@0.1.0` signature and implementation | PENDING | Bounded temporal windows over anchor sets. |
| `trace_back_from_outcome` signature variant | PENDING | Preceding window bounded by declared continuity policy. |
| Continuity policy evidence | PENDING | Same-possession / same-team-control / fixed-duration policies must declare evidence requirements. |
| Truncation handling | PENDING | Boundary truncation recorded; declared truncation policy honored. |
| Determinism | PENDING | Overlap/tie policies declared and tested. |
| Both-teams correctness | PENDING | Composition-level house-standard test required. |
| Acceptance composition | PENDING | Previously-gap `*_within` / `*_after` class row must become compiler-reachable. |
| Booked-evidence audit | PENDING | All booked rows walked to source evidence/raw data. |
| Full suite and pinned gates | PENDING | To be filled from committed-tree verification. |

## Verification

Pending implementation.
