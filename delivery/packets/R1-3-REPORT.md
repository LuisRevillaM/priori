# R1-3 Report - extremum_over_set Operator

Branch: `packet/r1-3`
Frontier base: `d509ca2`
Packet: `delivery/packets/R1-3-extremum-over-set.md`
ADR: `docs/adr/0013-r1-operator-era.md`, including all three addenda
Push: no push, per direct-channel protocol.

## Result

IN PROGRESS. This report was stage-committed before implementation, per the
R1 operator packet protocol.

The sandbox blocks writes to the canonical repository's `.git` directory, so
this work is being committed in a writable clone at
`/private/tmp/priori-r1-3-clone`, branch `packet/r1-3`.

## Required Acceptance Items

| Item | Status | Notes |
| --- | --- | --- |
| `extremum_over_set@0.1.0` signature and implementation | PENDING | Selection operator over declared set/value fields. |
| Selection witnesses | PENDING | Every selected element must carry selected record/entity id and frame. |
| Coverage poisoning | PENDING | UNKNOWN when incomplete set membership could change the selected answer. |
| Deterministic tie-breakers | PENDING | Declared total order; shuffle-stable tests required. |
| Both-teams correctness | PENDING | Composition-level house-standard test required. |
| Search synthesis | PENDING | Generic operator insertion, no provider-name scoring bonuses, all constraints enforced. |
| Acceptance composition | PENDING | Target correspondence, proof hashes, and before/after compiler-reachable counts required. |
| Booked-evidence audit | PENDING | Value distribution plus per-row correspondence and selected-witness audit required. |
| Full suite and pinned gates | PENDING | To be filled from committed-tree verification. |

## Verification

Pending implementation.
