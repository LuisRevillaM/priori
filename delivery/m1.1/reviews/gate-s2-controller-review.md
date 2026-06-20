# M1.1S Gate S2 Controller Review - Node Execution Contract

Date: 2026-06-20

Decision: ACCEPTED_CONTROLLER_ONLY

## Scope Reviewed

- `src/tqe/runtime/executor.py`
- `src/tqe/runtime/values.py`
- `src/tqe/verification/m1_1_gate_s2.py`
- `Makefile`
- generated verification artifacts under `artifacts/m1.1/`

## Acceptance Evidence

Gate S2 now proves the node execution contract at the current bounded runtime layer:

- downstream catalog implementations resolve declared inputs through `RuntimeValue` records instead of undeclared global signal keys;
- generic predicate operators no longer branch on `state.candidates` or M1-specific candidate fields;
- `signed_lateral_shift` consumes the declared `defensive_centroid` input, proven by substituting a compatible centroid signal and observing changed shift output;
- frame-level predicate facts travel through declared runtime record sidecars, preserving non-match traces without global signal reads;
- the approved M1 parity plan still returns 180 results and 900 predicate traces.

## Verification Run

- `make m1-1-gate-s2-verify`: pass, 4/0/0
- `make m1-1-gate-s1-verify`: pass, 8/0/0
- `make m1-1-gate-r2-verify`: pass, 4/0/0
- `make m1-1-gate-r3-verify`: pass, 9/0/0
- `make m1-1-gate-r5-verify`: pass, 10/0/0
- `make m1-1-gate-c-verify`: pass, 10/0/0
- `make m1-1-gate-d-verify`: pass, 11/0/0
- `make m1-1-gate-e-verify`: pass, 21/0/0
- `make test`: pass, 26 tests
- `git diff --check`: pass

## Controller Notes

The first S2 implementation dropped one frozen approved result because the declared `defensive_centroid` runtime value had been normalized to the analysis cadence. The fix was to emit the centroid as an explicit full-frame `FrameSignal`, preserving the original detector semantics while still making the input declared and substitutable.

The second issue was that `persists_for` briefly treated frame-level predicate facts as candidate records. That is now split: records with a generic `persistence_series` use record persistence; boolean frame masks still produce episode records and inherit prior predicate facts through `RuntimeValue` provenance.

Gate S2 is accepted as controller-verified. It does not complete the broader M1.1S architecture. S3 remains responsible for replacing the remaining M1 candidate-based anchor and target-inspection core with a generic anchor/predicate trace model.
