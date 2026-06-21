# M1.1S Gate S5 Controller Review

Decision: `ACCEPTED_CONTROLLER_ONLY`

S5 proves alias-based evidence projection as a standalone runtime contract.

Accepted evidence:

- `make m1-1-gate-s5-verify`: pass, 6/0/0.
- `make m1-1-gate-s4-verify`: pass, 16/0/0.
- `make m1-1-gate-s6-verify`: pass, 8/0/0.
- `make m1-1-gate-a-verify`: pass, 78/0/0.
- `make test`: pass, 27 tests.
- `git diff --check`: pass.

Accepted claims:

- Requested evidence uses stable aliases, not node-ID-shaped keys.
- Renaming an evidence-producing node preserves public result shape and requested evidence.
- Rewiring an evidence request to another declared field changes projected values.
- Unsupported evidence fields fail at bind time.
- Missing required evidence returns visible `INCOMPLETE` execution status with provenance failures.
- Optional evidence is explicit through `required: false`.
- The second generic plan does not leak hardcoded M1 evidence by default.

Residual risk:

S5 does not package the final external review packet or prove the final source-level architecture constraints. Those remain S7.
