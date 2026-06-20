# M1.1S Gate S1 Runtime Values

Date: 2026-06-20

## Fact

The old runtime value normalizer silently converted M1-shaped dictionaries into scalar frame-signal values, and Pandas Series normalization dropped missing values.

## Decision

Runtime frame signals now use an explicit `FrameSignal` container carrying frame IDs, values, UNKNOWN mask, unit, and entity scope. Structured dictionaries are rejected as frame-signal payloads. Episode and relation episode outputs have minimum schema checks, and actual runtime values carry declared output provenance.

## Learning

S1 should not try to remove all old side channels at once. It should make declared outputs honest first. Compatibility records can temporarily remain under undeclared keys, but they are no longer allowed to masquerade as typed frame-signal outputs.

## Evidence

- `make m1-1-gate-s1-verify`: 8 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r2-verify`: 4 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r3-verify`: 9 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r5-verify`: 10 pass, 0 fail, 0 not-ready.
- `make test`: 26 tests passed.
- `git diff --check`: passed.

## Follow-Up

Gate S2 must move node implementations toward explicit input bundles and remove generic-operator candidate-shape branches. The `classification_records` compatibility side channel is a known transitional artifact, not an accepted final architecture.
