# M1.1S Gate S3R4 Controller Review

Decision: `ACCEPTED_CONTROLLER_ONLY`

S3R4 integrates the external `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S4` review of S3R3.

Corrections implemented:

- `TacticalQueryExecutor` now defaults to the `generic` compatibility profile.
- Frozen M1 parity helpers and tests opt into `legacy_m1_parity` explicitly.
- `duration_to_frames` normalizes `second`, `millisecond`, and `frame` units with positive-duration validation and ceiling semantics.
- `execute_persists_for` now emits PASS, UNKNOWN, and FAIL temporal intervals.
- Temporal target tracing returns UNKNOWN outside evaluated coverage.
- The S3R verifier proves `0.4 second`, `400 millisecond`, and `2 frame` are equivalent at 5 Hz.
- The verifier proves `TRUE, TRUE, UNKNOWN` with a three-frame requirement is UNKNOWN across the relevant window, while `TRUE, TRUE, FALSE` is definitive FAIL.
- The side-channel proof now injects a contradictory `state.predicate_traces` record.
- `FrameSignal` now asserts `unknown_mask` matches `None` values.
- Generic target results no longer carry `_predicate_status`.

Verification:

- `make m1-1-gate-s3r-verify`: pass, 13/0/0.
- `make m1-1-gate-b-verify`: pass, 14/0/0.
- `make m1-1-gate-c-verify`: pass, 10/0/0.
- `make m1-1-gate-r5-verify`: pass, 10/0/0.
- `make test`: pass, 26 tests.

Residual risk:

S4 is still not implemented. From the controller perspective, S3R4 addresses the temporal-correctness blockers identified before S4.

