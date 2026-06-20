# M1.1R Gate R3 Controller Review

Date: 2026-06-20

Decision: ACCEPTED_CONTROLLER_ONLY

## Scope Reviewed

Gate R3 covers generic predicate execution, plan-driven classification, requested evidence projection, and unknown-evidence behavior for the corrective M1.1R runtime.

Reviewed paths:

- `src/tqe/runtime/executor.py`
- `src/tqe/runtime/values.py`
- `src/tqe/verification/m1_1_gate_r3.py`
- `Makefile`
- `artifacts/m1.1/gate-r3-verification-report.json`
- `artifacts/m1.1/gate-r2-verification-report.json`

## Evidence

- `make m1-1-gate-r3-verify` passed with 9 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r2-verify` passed with 4 pass, 0 fail, 0 not-ready after the runtime changes.
- `make m1-1-gate-c-verify` passed with 10 pass, 0 fail, 0 not-ready as a predicate-trace regression check.
- `make test` passed 26 tests.

Gate R3 report highlights:

- approved plan execution: 180 results and 900 predicate traces;
- classification rules are evaluated from predicate trace outputs;
- narrowing classification rules to `SWITCHED` narrows runtime output to 31 switched results;
- requested evidence projection changes when the plan requests only `signed_shift.signed_shift_metres`;
- unknown policy include/exclude/invalidate paths produce distinct behavior;
- `persists_for` consumes `True`/`False`/`UNKNOWN` frame-signal values and does not bridge across unknown frames.

## Controller Assessment

Accepted for proceeding to Gate R4.

This does not complete M1.1R. The runtime still has known R4/R5 work: relation anchoring remains coupled to accepted M1 source results, and the final architecture proof must remove the remaining approved-recipe predicate-ID literals from the generic executor source.

## Residual Risk

The current trace builder serializes predicate-status records emitted during execution, with a legacy reconstruction fallback retained for compatibility. R5 must prove the fallback no longer lets approved-recipe predicate IDs satisfy architecture gates.
