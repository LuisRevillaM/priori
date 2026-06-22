# M1.2 S2I Tactical Knowledge Pack

Type: implementation learning

## Fact

S2I-A now generates a Tactical Knowledge Pack from executable/project sources
instead of maintaining another hand-written football prompt. `search_recipes` is
implemented as a bounded schema-validated dispatcher tool rather than remaining
a planned-only MCP affordance.

## Decision

The generated pack distinguishes the current S2 reference-harness tool surface
from the S2I target Hermes/MCP product allowlist. The target product allowlist
keeps `execute_query_plan` and `host_confirm_bound_plan` host-only; Hermes can
draft, submit, validate, inspect, and retrieve replay windows but cannot confirm
or initiate execution.

## Evidence

- `generated/tactical-knowledge-pack.json`
- `generated/tactical-knowledge-pack.md`
- `src/tqe/workshop/knowledge_pack.py`
- `src/tqe/verification/m1_2_gate_s2i.py`
- `make m1-2-gate-s2i-verify`
- Pack SHA-256: `44a9b5fb3f3748c0e8a7bc80a4134fe3cb062dd66807ca20a671cb980529b7c6`
- S2I-A local review:
  `docs/reviews/2026-06-21-m1-2-s2i-a-local-verification.md`

## Follow-Up

Before formal S2I-A acceptance, complete one broader S2 regression or revise the
acceptance rule if the old live `gpt-4o-mini` sealed path should no longer gate
S2I-A. Then run S2I-B provisioning: verify GPT-5.5 Responses access, strict
structured outputs, high/xhigh reasoning, Hermes installation, trivial local
stdio MCP connectivity, and tactical tool allowlisting.
