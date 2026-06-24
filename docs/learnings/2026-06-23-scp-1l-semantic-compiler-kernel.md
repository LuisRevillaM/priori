# SCP-1L Semantic Compiler Kernel

## Fact

The first useful SCP-1 milestone is a semantic compiler boundary, not a new
executor. `SemanticExpression` now represents football meaning in Football Query
Normal Form, then supported expressions lower into the existing
`TacticalQueryDocument` and binder.

## Decision

SCP-1L reuses checked-in runtime plans as lowering targets for the first two
pilots:

- Ball-Side Block Shift;
- High-Bypass Completed Pass.

This avoids duplicating runtime AST construction while still proving the
compiler boundary, parameter override path, schema validation, and binder
authority chain.

## Learning

Typed gaps are as important as successful compilation. The compiler now has
durable fixtures for:

- reconstructed goal-kick restart candidate: `MISSING_OPERATIONALIZATION`;
- player intent from scanning/body angle: `MODALITY_GAP`;
- underspecified support arrival: `CLARIFICATION_REQUIRED`.

These fixtures keep Priori honest: the language can represent more football
meaning than the executable library, but missing capabilities do not become
fake runtime plans.

## Evidence

- `make scp-1-verify` passes.
- SCP-1L verifier passes 22/22 checks.
- `tests.test_scp1_semantic_compiler` passes 8 tests.

## Follow-up

SCP-1C should add natural-language compilation into these semantic expressions.
SCP-1G should add held-out recipe-free and open-library evaluations. Neither is
proven by SCP-1L.
