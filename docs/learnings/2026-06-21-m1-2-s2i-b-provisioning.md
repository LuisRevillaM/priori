# M1.2 S2I-B Provisioning

Date: 2026-06-21
Type: implementation learning

## Fact

Direct OpenAI Responses API access is available for `gpt-5.5-2026-04-23`, and
the provider accepts strict structured output with both `high` and `xhigh`
reasoning efforts.

Hermes is now installed locally at `/Users/luisrevilla/.local/bin/hermes` and
authenticated with `openai-codex` through the ChatGPT/Codex subscription device
login path under `HERMES_HOME=/Users/luisrevilla/.hermes-priori`.

## Decision

Use the local `OPENAI_API_KEY` only for direct provisioning probes and reference
API evidence. Hermes instances must use the ChatGPT/Codex subscription-login
path, per owner direction.

Use Hermes provider `openai-codex`, model `gpt-5.5`, and reasoning effort
`xhigh` for the next integration slice. The local ChatGPT/Codex account did not
accept the tested `*-codex` model IDs through Hermes, while `gpt-5.5` produced a
successful `HERMES_READY` smoke response.

Treat the old S2 reference harness and the S2I product MCP surface as separate
surfaces. The reference harness still exposes `execute_query_plan`; the S2I
product MCP allowlist must not.

## Learning

The first S2I-B report was correctly a no-go report. After installing and
logging in to Hermes, the same gate now passes and should become the baseline for
Hermes MCP integration. The remaining question is no longer "can this account run
Hermes?" but "can a real Hermes instance call only the bounded tactical MCP
surface and stop before host execution?"

## Evidence

- `artifacts/m1.2/s2i-b-provisioning-report.json`
- `docs/reviews/2026-06-21-m1-2-s2i-b-provisioning.md`
- `src/tqe/verification/m1_2_gate_s2ib.py`
- `make m1-2-gate-s2ib-verify`

## Follow-Up

Run one real Hermes-authored request through:

```text
search/list/describe
-> submit experimental plan
-> validate bound interpretation
-> stop before host execution
```

Workbench Alpha should proceed in parallel against the deterministic
host/orchestrator path.
