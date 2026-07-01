# M1.1S Gate S1 Controller Review

Date: 2026-06-20

Decision: ACCEPTED_CONTROLLER_ONLY

## Scope Reviewed

Gate S1 covers runtime value and result type hardening.

Reviewed paths:

- `src/tqe/runtime/values.py`
- `src/tqe/runtime/executor.py`
- `src/tqe/verification/m1_1_gate_s1.py`
- `Makefile`

## Evidence

- `make m1-1-gate-s1-verify` passed with 8 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r2-verify` passed with 4 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r3-verify` passed with 9 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r5-verify` passed with 10 pass, 0 fail, 0 not-ready.
- `make test` passed 26 tests.
- `git diff --check` passed.

Gate S1 report highlights:

- frame signals preserve supplied frame IDs and missing values as UNKNOWN;
- M1-shaped result dictionaries are rejected as `FrameSignal<Number>` and `FrameSignal<Enum>` payloads;
- episode and relation episode records require frame identity/window shape;
- actual runtime outputs carry declared node/output/type provenance;
- actual frame-signal outputs are `FrameSignal` containers without structured M1 result dictionary payloads.

## Controller Assessment

Accepted for proceeding to Gate S2.

This does not complete M1.1S. Temporary compatibility side channels such as `classification_records` remain so old relation/result code can run while S2-S5 replace the execution handoff.

## Residual Risk

Some declared frame signals remain per-anchor rather than full-period frame signals. S1 makes that explicit through frame IDs and UNKNOWN masks; S2 and S3 must introduce the general anchor model and decide which values should become `AnchorSet` rather than continuing as frame-signal stand-ins.
