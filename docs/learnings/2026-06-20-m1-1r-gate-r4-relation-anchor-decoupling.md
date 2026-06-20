# M1.1R Gate R4 Relation Anchor Decoupling

Date: 2026-06-20

## Fact

The relation layer previously ignored its bound `anchors` input and read `state.accepted` directly. Destination classification also used a `relation_node_id` parameter to recover upstream relation state.

## Decision

Relations now read anchor records from bound inputs. Destination classification reads relation episodes through its bound input, and relation episode selection is explicit via `episode_selection=first_by_duration_clearance`.

## Learning

A structural source check is not enough for this gate. The proof needs a valid plan mutation that produces results from anchors outside the M1 accepted set. The R4 verifier does that by relaxing relation filters on one match/period and confirming final results sourced from STOPPAGE anchors.

## Evidence

- `make m1-1-gate-r4-verify`: 8 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r1-verify`: 19 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-e-verify`: 21 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r3-verify`: 9 pass, 0 fail, 0 not-ready.
- `make test`: 26 tests passed.

## Follow-Up

Gate R5 must remove the remaining source-level approved-recipe predicate IDs from generic executor code and prove node-ID opacity end to end.
