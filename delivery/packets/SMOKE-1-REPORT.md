# SMOKE-1 Report

Branch: `packet/smoke-1`  
Latest implementation commit at report time: `bb91462fe473f2c445f10b35cb0075645ce4a1a1`  
Latest implementation tree at report time: `4e51932632cd299024bbc2d074c284470dbcb02b`

## Delivered With Evidence

SMOKE-1 is DELIVERED with committed evidence. The evidence producer is
`scripts/packets/smoke1_evidence.py` at SHA-256
`81d8a137ab085feb6572176ab0b10c0458ca1e4b186fb0d8c4a6f0da0dbc7095`.

Final R-AZ run:
`delivery/packets/smoke-1-evidence/runs/2026-07-07T115256Z00000000-81d8a137ab08/`

That run self-stamps:

- script hash, timestamp, branch, commit, and tree
- focused Python error-path tests: PASS
- Film Room UI typed-error tests: PASS
- owner exact ask through live Hermes: PASS as an honest refusal
- cache provenance: fresh run-local `output_root`, no persistent execution cache configured by the script
- billing surface: ChatGPT subscription via `openai-codex` Hermes CLI

The owner ask in the final evidence run returned:

- `outcome`: `understood_but_not_expressible`
- `refusal_gap`: `TARGET_SYNTHESIS_UNSATISFIED`
- `missing_capability`: `registered_operator_composition`
- Hermes latency: `152953 ms`
- synthesis latency: `3 ms`

## Root Cause

The owner ask was not a bad request. The live model could compile an expression, but the downstream target synthesizer could not build a registered operator composition for that generated rate contract. The concrete synthesis failure was `missing_constraint`: rate numerator and denominator compositions were not the same source relation. Before SMOKE-1, the broad POST handler catch could report that class of downstream failure as `REQUEST_SCHEMA_INVALID`.

The same live path also exposed the packet's truncation signature: long Hermes JSON around 14-15K characters can fail with `Expecting ',' delimiter`. SMOKE-1 now classifies that long cutoff shape as `MODEL_OUTPUT_TRUNCATED` and returns a typed retry refusal after bounded repair attempts.

## Changes

- Scoped request-schema handling to body decode and explicit request validation only.
- Added server-side traceback logging with `err_<12 hex>` correlation ids for internal failures.
- Raised SCP2-2 Hermes output ceiling through the local Hermes shim with `--max-output-tokens 32768`.
- Added truncation detection, continuation-style repair prompt, and typed `MODEL_OUTPUT_TRUNCATED` refusal.
- Converted synthesis failures after successful Hermes compilation into `TARGET_SYNTHESIS_UNSATISFIED` refusals.
- Preserved typed API errors in the frontend and rendered distinct schema, truncation, and internal error states.
- Added mutation/focused tests for handler scoping, truncation, synthesis refusal, and UI error rendering.
- Scoped Playwright e2e collection to `*.spec.ts`; unit `*.test.ts` files are still run by `test:unit`.
- Included the generated API contract sync for `runtime_evidence_sources`; those files were already dirty at packet start and are required for `test:contracts`.

## Live Attempt Accounting

Model-bound owner-ask runs were subscription-billed and capped at five:

| Attempt | Purpose | Result |
| --- | --- | --- |
| 1 | Reproduce original downstream crash | Reproduced `SynthesisError` after successful Hermes compile |
| 2 | Verify synthesis-refusal fix | `TARGET_SYNTHESIS_UNSATISFIED` refusal |
| 3 | First committed R-AZ evidence run | PASS, retained at `2026-07-07T113717Z...` |
| 4 | R-AZ rerun after harness commit | FAIL, long delimiter JSON escaped as generic model-output error; retained at `2026-07-07T114815Z...` |
| 5 | Final R-AZ evidence after detector repair | PASS, retained at `2026-07-07T115256Z...` |

## Full-Suite Table

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHON=.venv/bin/python PYTHONPATH=src make test` | PASS | 576 tests, 513.595s. Over 5 minutes: flagged. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:acceptance` | FAIL | `test:contracts`, fixture scan, unit tests, and build passed. Playwright e2e ran 16 spec tests and failed broadly because `/` currently renders `CoachSurface`/high-bypass browser while legacy e2e specs expect the Workbench app at `/`; one backend artifact test also failed its expected bad-inspection assertion. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run build` | PASS | Build also passed inside `test:acceptance`; Vite emitted the existing chunk-size warning. |
| `PYTHONPATH=src .venv/bin/python scripts/packets/smoke1_evidence.py --owner-attempts 1` | PASS | Final R-AZ run `2026-07-07T115256Z00000000-81d8a137ab08`; live owner ask subscription-billed. |

Nothing was pushed.
