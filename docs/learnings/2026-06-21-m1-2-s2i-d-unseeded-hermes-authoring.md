# M1.2 S2I-D Unseeded Hermes Authoring Learning

## Fact

Hermes can author and validate typed experimental plans from unseeded football
language when the MCP knowledge surface exposes recipe authoring contracts.

## Decision

Keep the authoring contract inside `describe_capability` for recipe IDs. Do not
add a separate drafting tool yet, and do not expose execution or host
confirmation.

## Learning

The first unseeded attempt before the repair showed the model repeatedly
guessing unsupported recipe, anchor, and operator names. The narrow repair was
to make the existing recipe discoverable by ID and expose the declarative plan
shape already present in the checked-in recipe document.

That is the right boundary: Hermes gets enough structure to author a plan, but
the deterministic binder/runtime still owns validation and execution semantics.

## Evidence

- `make m1-2-gate-s2id-verify`: `20 pass / 0 fail`
- Report: `artifacts/m1.2/s2i-d-unseeded-hermes-report.json`
- Sessions: `20260621_220512_1d38ec`, `20260621_221026_2eacf0`

## Follow-Up

The next frontier gate should freeze the selected runtime configuration and run
final evaluation. The old small-model lane remains a regression/control harness,
not the frontier-runtime acceptance path.
