# M1.1S Gate S3 Controller Review - Anchor And Predicate Trace Core

Date: 2026-06-20

Decision: ACCEPTED_CONTROLLER_ONLY

## Scope Reviewed

- `src/tqe/runtime/executor.py`
- `src/tqe/verification/m1_1_gate_s3.py`
- `Makefile`
- generated verification artifacts under `artifacts/m1.1/`

## Acceptance Evidence

Gate S3 now establishes a bounded generic anchor core:

- `RuntimeAnchor` represents anchor identity, frame, source output, optional window, and structured attributes;
- `runtime_anchors(state)` builds anchors from declared runtime output record sidecars, not from accepted results;
- target evaluation derives compatible anchors from runtime outputs instead of `state.candidates`;
- accepted-result predicate traces are reconstructed from anchor/result records instead of walking mutable candidate dictionaries;
- non-match target inspection still emits explicit UNKNOWN traces with engine reasons when downstream source output is unavailable;
- prior unknown-policy and tri-state predicate proofs still pass through the R3 verifier.

## Verification Run

- `make m1-1-gate-s3-verify`: pass, 5/0/0
- `make m1-1-gate-s2-verify`: pass, 4/0/0
- `make m1-1-gate-c-verify`: pass, 10/0/0
- `make m1-1-gate-r5-verify`: pass, 10/0/0
- `make test`: pass, 26 tests
- `git diff --check`: pass

## Controller Notes

This gate intentionally does not claim full generic result emission. M1 tactical records still carry M1-specific attributes, and `signed_lateral_shift` still writes `state.candidates` as a compatibility side effect for later gates. The important S3 boundary is that generic target evaluation and accepted predicate trace extraction no longer depend on that side channel.

This is a meaningful external review checkpoint. The reviewer should decide whether the new anchor core is sufficient to proceed into S4 rule-driven result emission, or whether S3 needs stricter anchor schema normalization before S4/S5.
