# M1.2 S2I Rebaseline

Type: decision

## Fact

The repeated `gpt-4o-mini` sealed-set cycle proved the deterministic safety
harness, schema validation, host confirmation, repair accounting, and fallback
behavior. It also showed that continued synonym hardening against the small
model is no longer the highest-value path toward the intended demo.

## Decision

Freeze `f9eb5d8` as the small-model reference compiler baseline. Stop requesting
fresh sealed sets for the `gpt-4o-mini` lane. Add S2I to prove the intended
Hermes/frontier-model product path, and start Workbench Alpha in parallel over
the stable deterministic contracts.

## Learning

The model should not be treated as the measurement system. The model selects or
authors tactical definitions; the deterministic runtime measures the match. The
next proof should evaluate the actual deployment architecture: Hermes with a
frontier model, a generated tactical knowledge pack, and a bounded tool surface.

## Evidence

- `CURRENT_STATE.md`
- `delivery/m1.2/SPEC.md`
- `delivery/m1.2/status.yaml`
- `delivery/status.yaml`
- Baseline commit: `f9eb5d8`

## Follow-Up

Implement S2I in this order: knowledge pack, Hermes-compatible tool boundary,
GPT-5.5 Responses configuration, direct harness comparison, runtime freeze, final
sealed acceptance. In parallel, build Workbench Alpha query-to-replay UI without
adding new runtime semantics.
