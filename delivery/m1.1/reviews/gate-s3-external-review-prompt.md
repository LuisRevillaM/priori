# External Review Prompt - M1.1S Gates S1-S3

Please review the current M1.1S structural correction after Gates S1-S3.

## Context

An external review rejected the prior M1.1R implementation because it still did not prove that the typed plan controls execution. The accepted correction roadmap is M1.1S:

- S1: harden runtime values and result types;
- S2: ensure node implementations consume declared `RuntimeValue` inputs instead of undeclared global signal keys;
- S3: introduce a generic anchor and predicate trace core;
- S4-S7 remain pending: rule-driven result emission, alias-based evidence projection, second real plan proof, and final parity architecture proof.

The local controller has now marked S1, S2, and S3 as `ACCEPTED_CONTROLLER_ONLY`.

## What Changed In S3

S3 introduced a bounded `RuntimeAnchor` core:

- runtime anchors are derived from declared runtime output record sidecars via `runtime_anchors(state)`;
- target/non-match evaluation now derives compatible anchors from runtime outputs instead of reading `state.candidates`;
- accepted-result predicate traces are reconstructed from anchor/result records instead of walking mutable candidate dictionaries;
- non-match target evaluation emits explicit `UNKNOWN` traces with engine reasons when a downstream source output is unavailable;
- M1 parity remains intact: 180 approved results and 900 predicate traces.

Important boundary: this does **not** claim full generic result emission yet. M1 tactical primitives still carry M1-specific attributes, and `signed_lateral_shift` still writes `state.candidates` as a compatibility side effect. The asserted S3 improvement is narrower: generic target evaluation and trace extraction no longer depend on that side channel.

## Verification Claimed By Local Controller

- `make m1-1-gate-s3-verify`: pass, 5/0/0
- `make m1-1-gate-s2-verify`: pass, 4/0/0
- `make m1-1-gate-c-verify`: pass, 10/0/0
- `make m1-1-gate-r5-verify`: pass, 10/0/0
- `make test`: pass, 26 tests
- `git diff --check`: pass

## Files To Review Conceptually

- `src/tqe/runtime/executor.py`
  - `RuntimeAnchor`
  - `runtime_anchors`
  - `runtime_anchor_from_record`
  - `TacticalQueryExecutor.evaluate_target`
  - `accepted_predicate_traces`
  - `predicate_traces_for_anchor`
  - `missing_target_predicate_traces`
- `src/tqe/verification/m1_1_gate_s3.py`
- `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md`
- `delivery/m1.1/reviews/gate-s3-controller-review.md`
- `docs/learnings/2026-06-20-m1-1s-gate-s3-anchor-core.md`

## Review Questions

1. Is S3 correctly accepted as a bounded improvement, given that generic target evaluation and accepted trace extraction now use runtime anchors rather than `state.candidates`?
2. Is the current `RuntimeAnchor` shape sufficient to proceed to S4 rule-driven result emission, or should anchor schema normalization be tightened first?
3. Does deriving anchors from runtime output sidecar records introduce any hidden coupling, ordering fragility, or reward-hacking risk?
4. Is it acceptable for M1 tactical primitives to keep M1-specific attributes in anchor metadata until S4/S5, or should those attributes be isolated behind a stronger generic envelope now?
5. Are the S3 verifier checks strong enough, or should they add additional proof gates before S4?

## Requested Decision

Return one of:

- `APPROVE_PROCEED_TO_S4`
- `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S4`
- `REJECT_S3`

Please list blocking findings first. Distinguish required changes from non-blocking concerns.
