# M1.2 S2I-B Provisioning

Date: 2026-06-21
Type: implementation learning

## Fact

Direct OpenAI Responses API access is available for `gpt-5.5-2026-04-23`, and
the provider accepts strict structured output with both `high` and `xhigh`
reasoning efforts.

No local `hermes` or `hermes-agent` executable is currently available on PATH.

## Decision

Use the local `OPENAI_API_KEY` only for direct provisioning probes and reference
API evidence. Hermes instances must use the ChatGPT/Codex subscription-login
path, per owner direction.

Treat the old S2 reference harness and the S2I product MCP surface as separate
surfaces. The reference harness still exposes `execute_query_plan`; the S2I
product MCP allowlist must not.

## Learning

The first useful S2I-B report should be a **no-go report**, not another runtime
repair cycle. Model access, structured output, reasoning effort, and tactical
tool validation are all good enough to proceed in parallel, but full Hermes
acceptance cannot be claimed until the real Hermes runtime exists and connects
through the same bounded allowlist.

## Evidence

- `artifacts/m1.2/s2i-b-provisioning-report.json`
- `docs/reviews/2026-06-21-m1-2-s2i-b-provisioning.md`
- `src/tqe/verification/m1_2_gate_s2ib.py`
- `make m1-2-gate-s2ib-verify`

## Follow-Up

Install/configure Hermes with subscription login, rerun S2I-B, then run one real
Hermes-authored request through:

```text
search/list/describe
-> submit experimental plan
-> validate bound interpretation
-> stop before host execution
```

Workbench Alpha should proceed in parallel against the deterministic
host/orchestrator path.
