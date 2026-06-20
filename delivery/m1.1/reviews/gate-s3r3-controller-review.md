# M1.1S Gate S3R3 Controller Review

Decision: `ACCEPTED_CONTROLLER_ONLY`

S3R3 integrates the external `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S4` review of S3R2.

Corrections implemented:

- `TacticalQueryExecutor` now has a host-only compatibility profile: `generic` or `legacy_m1_parity`.
- Generic execution cannot invoke legacy M1 persistence adapters regardless of attached runtime records.
- Legacy trace fallback is available only under the explicit M1 parity profile.
- Generic target inspection ignores `_runtime_result` and `_predicate_status`.
- `execute_persists_for` is the single shared generic temporal implementation.
- `predicate_persists_for` delegates to `execute_persists_for`.
- Generic persistence emits PASS episodes and UNKNOWN intervals, preserving unknown semantics for target tracing.
- Non-M1 proof now executes actual predicate nodes through `_execute_node` in generic mode.
- The proof emits engine-generated PASS, FAIL, and UNKNOWN traces and confirms side-channel perturbation does not change them.

Verification:

- `make m1-1-gate-s3r-verify`: pass, 12/0/0.
- `make m1-1-gate-b-verify`: pass, 14/0/0.
- `make m1-1-gate-c-verify`: pass, 10/0/0.
- `make m1-1-gate-r5-verify`: pass, 10/0/0.
- `make test`: pass, 26 tests.

Residual risk:

Legacy M1 adapters remain for frozen parity. They are host-profile gated and not available to generic execution. S4 should use the generic profile.

