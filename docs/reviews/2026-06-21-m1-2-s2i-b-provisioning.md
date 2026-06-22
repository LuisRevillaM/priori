# M1.2 S2I-B Provisioning Spike

Date: 2026-06-21

## Decision

S2I-B is partially proven but remains **NO_GO_FOR_FULL_S2I_B** because no local
Hermes executable is installed yet.

## Evidence

- Report: `artifacts/m1.2/s2i-b-provisioning-report.json`
- Command: `make m1-2-gate-s2ib-verify`
- Result: `7 pass / 1 fail`
- Failing check: `hermes.executable_available`

## Proven

- The requested model `gpt-5.5-2026-04-23` is listed for the current OpenAI API
  account.
- Responses API calls succeed with the exact requested model and return the same
  model identifier.
- Strict structured output succeeds.
- Reasoning efforts `high` and `xhigh` are accepted by the provider.
- The product S2I Hermes/MCP allowlist excludes host-only execution and
  confirmation tools.
- Tactical tool proof can list/search/describe capabilities, submit the
  experimental corridor plan, validate it, and stop before execution.
- The existing S2 reference harness still exposes `execute_query_plan`, but the
  S2I product MCP allowlist keeps it host-only.

## Measured Comparison

Frozen probe set: 4 prompts, run once with `high` and once with `xhigh`.

```text
high:
  completed: 4/4
  exact matches: 2/4
  total latency: 45.638s
  estimated cost: $0.072625

xhigh:
  completed: 4/4
  exact matches: 2/4
  total latency: 50.200s
  estimated cost: $0.074035
```

Recommendation from this spike: use `high` until Hermes-context evaluation shows
that `xhigh` materially improves behavior.

Pricing estimate source: `https://openai.com/api/pricing/`, checked
2026-06-21. GPT-5.5 rates used: $5.00 / 1M input tokens, $0.50 / 1M cached
input tokens, and $30.00 / 1M output tokens.

## Blocker

No `hermes` or `hermes-agent` executable is present on PATH. Per owner
direction, Hermes instances should use ChatGPT/Codex subscription login, not the
local `OPENAI_API_KEY` used for the direct API probes.

## Next Step

Install/configure Hermes with the subscription-login path, then rerun
`make m1-2-gate-s2ib-verify`. Workbench Alpha should proceed in parallel because
the deterministic host/orchestrator tools can already submit and validate the
experimental corridor plan.
