# M1.2 S2I-B Provisioning Spike

Date: 2026-06-21

## Decision

S2I-B is **GO_FOR_HERMES_MCP_INTEGRATION** after installing Hermes, logging in
through the ChatGPT/Codex subscription path, and rerunning the provisioning gate.

## Evidence

- Report: `artifacts/m1.2/s2i-b-provisioning-report.json`
- Command: `make m1-2-gate-s2ib-verify`
- Result: `8 pass / 0 fail`

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
- Hermes is installed at `/Users/luisrevilla/.local/bin/hermes`.
- Hermes version is v0.17.0 (2026.6.19), upstream `2b3a4f0a`.
- Hermes is authenticated as `openai-codex` under
  `HERMES_HOME=/Users/luisrevilla/.hermes-priori`.
- Hermes config uses provider `openai-codex`, default model `gpt-5.5`, and
  reasoning effort `xhigh`.
- A direct `hermes chat -q` smoke returned `HERMES_READY`.

## Measured Comparison

Frozen probe set: 4 prompts, run once with `high` and once with `xhigh`.

```text
high:
  completed: 4/4
  exact matches: 2/4
  total latency: 43.173s
  estimated cost: $0.059035

xhigh:
  completed: 4/4
  exact matches: 2/4
  total latency: 34.642s
  estimated cost: $0.051475
```

Recommendation from this spike: use `xhigh` for the next Hermes integration
slice, then re-evaluate once the real Hermes MCP context is connected.

Pricing estimate source: `https://openai.com/api/pricing/`, checked
2026-06-21. GPT-5.5 rates used: $5.00 / 1M input tokens, $0.50 / 1M cached
input tokens, and $30.00 / 1M output tokens.

## Notes

Per owner direction, Hermes instances use ChatGPT/Codex subscription login, not
the local `OPENAI_API_KEY` used for direct API probes. The `openai-codex`
provider accepts `gpt-5.5` in this local Hermes configuration; several
`*-codex` model IDs returned provider errors under the ChatGPT account and
should not be treated as the current product path.

## Next Step

Connect the tactical MCP adapter to Hermes and run one real Hermes-authored
request through list/search/describe, submit an experimental plan, validate the
bound interpretation, and stop before host execution. Workbench Alpha should
continue in parallel because the deterministic host/orchestrator tools can
already submit and validate the experimental corridor plan.
