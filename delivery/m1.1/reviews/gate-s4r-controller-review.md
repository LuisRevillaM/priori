# M1.1S Gate S4R Controller Review

Decision: `ACCEPTED_CONTROLLER_ONLY`

S4R integrates the external S4 required changes before the second tactical pattern.

Accepted evidence:

- `make m1-1-gate-s4-verify`: pass, 16/0/0.
- `make m1-1-gate-s3r-verify`: pass, 13/0/0.
- `make m1-1-gate-c-verify`: pass, 10/0/0.
- `make m1-1-gate-d-verify`: pass, 11/0/0.
- `make m1-1-gate-e-verify`: pass, 21/0/0.
- `make test`: pass, 27 tests.
- `git diff --check`: pass.

What changed:

- UNKNOWN traces are retained as audit evidence even when `EXCLUDE_CANDIDATE` emits no result.
- `INVALIDATE_EXECUTION` can now see retained anchor-level UNKNOWN evidence and returns `INCOMPLETE`.
- Generic predicate trace generation consumes explicit predicate records instead of `_predicate_status`.
- Classification conflict resolution is explicit: higher specificity wins, then plan order.
- The inclusion proof now isolates one label so a required-predicate mutation changes emitted count rather than being absorbed by an overlapping rule.
- Requested evidence uses stable aliases and selected-relation correlation.
- Legacy parity traces preserve frozen `_predicate_status` semantics under the explicit legacy helper while generic execution ignores those side channels.

Residual risk:

This still does not prove a second tactical family. The next milestone should be the second dissimilar tactical pattern, not another S4 repair gate unless a concrete regression appears.
