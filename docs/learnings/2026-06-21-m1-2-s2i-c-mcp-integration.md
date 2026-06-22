# M1.2 S2I-C Tactical MCP Integration Learning

## Fact

Hermes can connect to a local stdio MCP server and use the bounded tactical
tool surface with the `openai-codex` subscription login.

## Decision

Keep a separate `HERMES_S2I_MCP` caller profile for the product MCP path. The
older S2 reference compiler profile can remain broader for evaluation and
debugging, but the product Hermes path must not expose execution or host
confirmation.

## Learning

The first live Hermes attempt, with only capability summaries and schemas, did
not have enough context to author a full experimental query plan. The successful
proof supplied the experimental corridor plan JSON as a seed, after which
Hermes correctly used MCP to submit, validate, and stop before execution.

That means the next unseeded-drafting milestone should improve knowledge
retrieval or provide an explicit draft-support workflow. It should not broaden
permissions, expose raw data, or let Hermes execute plans directly.

## Evidence

- `make m1-2-gate-s2ic-verify`: `12 pass / 0 fail`
- Report: `artifacts/m1.2/s2i-c-mcp-integration-report.json`
- Live Hermes session: `20260621_212207_0f45e6`
- Bound plan: `bound_7094041d9225ea8c`

## Follow-Up

Workbench Alpha should call the host application service directly. MCP remains
the Hermes adapter, not the UI application core.
