# M1.2 S2E - Codes and Deterministic Safety Fallback

## What Changed

The S2D sealed set showed that free-text evaluator matching and pure model
repair were not enough for S3 acceptance. S2E adds host-owned semantic codes and
a deterministic clarification fallback for known ambiguity rules.

## Learning

Evaluator expectations should target stable codes, not prose. The model can
explain itself in natural language, but acceptance gates and downstream logic
need explicit concepts such as `PRIMITIVE_MUTATION`, `DIRECT_EXECUTION`,
`SUPPORT_DEFINITION`, and `TIME_WINDOW`.

Known ambiguity rules should not depend entirely on the model producing the
right wording. If the semantic validator can prove that a request like
"second runner arrived properly" is ambiguous, the host can safely emit a typed
clarification requirement after model repair fails. The trace must state that
this came from deterministic safety fallback rather than the model.

## Verification Notes

The original S2D sealed set now passes as a diagnostic regression:

- supported accuracy: 100%;
- ambiguous accuracy: 100%;
- unsupported accuracy: 100%;
- schema-valid or refusal: 100%;
- unauthorized calls: 0;
- unconfirmed executions: 0.

The same report preserves the more important breakdown:

- first-pass ambiguous accuracy: 25%;
- after-model-repair ambiguous accuracy: 75%;
- after-deterministic-safety-fallback ambiguous accuracy: 100%.

That distinction prevents reward hacking. The correction is controller-verified,
but S3 remains blocked until a fresh independently authored sealed mini-set
passes.
