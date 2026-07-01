# M1.2 S2B Model-Backed Hermes Review Packet

Date: 2026-06-21

Packet type: `inspection_packet_only`

Commit under review: `be7ecf6`

## What This Is

This packet reviews S2B: the model-backed Hermes compiler and corpus evaluation
required before S3 can begin. S2A remains preserved as the deterministic compiler
contract and fallback; S2B proves the actual model-backed path.

## Review Scope

Please review whether S2B satisfies the required pre-S3 blockers:

- real model-backed Hermes path, not keyword routing;
- bounded model output: trusted recipe selection, typed experimental draft,
  clarification request, or capability gap;
- two semantically different supported requests produce different validated plan
  hashes through corridor parameters;
- ambiguous support language can be clarified into a two-second corridor plan;
- all corpus prompts are executed and scored;
- complete model session traces record model metadata, prompt/context/schema
  hashes, raw structured model output, ordered tool calls, host confirmation,
  execution, inspection, and replay.

## Validation Summary

- `make m1-2-gate-s2-verify`: pass, 12/12.
- `make m1-2-verify`: pass, 3/3.
- `make test`: pass, 27 tests.
- `make m1-1-gate-s7r-verify`: pass, 13/13.

Corpus score:

```json
{
  "schema_valid_or_refusal_rate": 1.0,
  "supported_accuracy": 0.9615384615384616,
  "ambiguous_accuracy": 0.9,
  "unsupported_accuracy": 1.0,
  "invented_identifier_count": 0,
  "unauthorized_tool_call_count": 0,
  "unconfirmed_execution_count": 0
}
```

## Review Map

- `source-excerpts/src/tqe/workshop/hermes_s2.py`: model-backed Hermes client.
- `source-excerpts/src/tqe/verification/m1_2_gate_s2.py`: S2B verifier and corpus scoring.
- `artifacts/agent-evaluation-report.json`: row-level corpus evaluation.
- `artifacts/hermes-s2-trace-report.json`: model/session trace manifest.
- `reports/gate-s2-verification-report.json`: S2B proof gate report.
- `diffs/head.patch`: committed implementation delta.

## What Is Not Claimed

- S3 feedback-driven revision diffs are not implemented.
- Recipe saving/promotion through Hermes is not implemented.
- No second tactical family is added.
- No UI polish or production infrastructure is added.

## Requested Decision

Return one of:

```text
APPROVE_S3_UNBLOCKED
APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S3
REJECT_KEEP_S3_BLOCKED
```
