# M1.2 S2I-A Local Verification

## Decision

S2I-A is implemented and locally verified, but formal acceptance remains pending
one successful broader S2 regression run.

## What Changed

- `search_recipes` is now a real bounded dispatcher tool with strict Pydantic
  request and response schemas.
- The Tactical Knowledge Pack now marks `search_recipes` as implemented rather
  than planned.
- The S2I-A verifier checks that:
  - Markdown is generated from the JSON pack;
  - `search_recipes` has an implemented schema;
  - host-owned execution remains absent from the S2I Hermes/MCP allowlist;
  - no obvious secret, absolute local path, raw-data path, frame array, or entity
    array markers are present;
  - pack size is recorded.

## Verification

Passed:

```text
python -m compileall src/tqe/workshop/m1_2.py src/tqe/workshop/knowledge_pack.py src/tqe/verification/m1_2_gate_s0.py src/tqe/verification/m1_2_gate_s2.py src/tqe/verification/m1_2_gate_s2i.py
make m1-2-gate-s0-verify
make m1-2-gate-s2i-verify
```

Results:

```text
S0: 17 pass / 0 fail
S2I-A: 16 pass / 0 fail
```

Search probe:

```text
search_recipes(query="progressive corridor", states=["EXPERIMENTAL"], limit=3)
```

returned `possession_corridor_availability_v1` and
`opposite_corridor_after_shift_v1` without exposing local paths or raw plan
files.

Not completed:

```text
make m1-2-gate-s2-verify
```

The live-model path was interrupted after waiting on an OpenAI Chat Completions
response in the sealed corpus path. Deterministic reference mode is not an
acceptable substitute because the existing S2 verifier has older assumptions
around clarification validation that fail under reference mode.

## Pack Size

- JSON file: 201,461 bytes, approximately 50,365 chars/4 tokens.
- Markdown file: 6,516 bytes, approximately 1,629 chars/4 tokens.
- Compact JSON payload recorded by verifier: 119,542 chars, approximately
  29,885 chars/4 tokens.

## Pack Hash

`44a9b5fb3f3748c0e8a7bc80a4134fe3cb062dd66807ca20a671cb980529b7c6`

## Acceptance Blocker

Complete one successful broader S2 regression after this change, or explicitly
revise that acceptance requirement if the team decides the old live
`gpt-4o-mini` sealed path should no longer gate S2I-A.
