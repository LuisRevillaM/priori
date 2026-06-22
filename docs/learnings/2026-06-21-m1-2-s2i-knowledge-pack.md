# M1.2 S2I Tactical Knowledge Pack

Type: implementation learning

## Fact

S2I-A now generates a Tactical Knowledge Pack from executable/project sources
instead of maintaining another hand-written football prompt.

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
- Pack SHA-256: `69cc6ed3160179643de2c5cf5ed7dcdb0c0ade35f8280178c8b22af1c7681866`

## Follow-Up

Run S2I-B provisioning: verify GPT-5.5 Responses access, strict structured
outputs, high/xhigh reasoning, Hermes installation, trivial local stdio MCP
connectivity, and tactical tool allowlisting.
