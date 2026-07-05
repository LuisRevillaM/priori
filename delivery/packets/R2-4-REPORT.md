# R2-4 Report: sequence_pattern

Branch: `packet/r2-4`

Frontier base: `104e373` (`codex/afl08-passport-loop`)

Clone-route provenance: main-workspace branch creation failed with
`.git/refs/heads/packet/r2-4.lock` EPERM, so work is being committed in
`/private/tmp/priori-r2-4-single-20260705095024`. Director recovery should
use this clone's commit SHAs via `format-patch`.

## Protocol Status

| Item | Status | Evidence |
| --- | --- | --- |
| Packet read | DONE | `delivery/packets/R2-4-sequence-pattern.md` |
| ADR 0013 read | DONE | Operator-era template and addenda govern. |
| ADR 0014 read | DONE | Aggregation principles 20-22 govern downstream counts/rates. |
| ADR 0015 read | DONE | Bridge principles 23-25 govern the meaning-expression fixture. |
| Branch | DONE_CLONE | `packet/r2-4` from `104e373` in `/private/tmp/priori-r2-4-single-20260705095024`. |
| Fences | ACTIVE | No ledger touch; no atlas; no sealed evidence; no autonomous artifacts except allowed canonical search report; no freezes/re-pins. |
| Push | NOT_DONE | Local commits only. |

## Implementation Log

| Commit | Contents |
| --- | --- |
| `198e0d7` | Report scaffold and clone-route provenance. |
| `PENDING` | sequence_pattern operator, registry, pack delta, focused tests. |

## Pack Delta

| Item | Before | After | Evidence |
| --- | ---: | ---: | --- |
| Composition operators | 7 | 8 | `sequence_pattern@0.1.0` appears in `generated/tactical-knowledge-pack.json`. |
| Composition constraint kinds | 14 | 15 | `sequence_pattern` constraint kind is registry-derived. |

The bridge schema was not extended. The meaning-expression vocabulary now sees `sequence_pattern` through the existing R-AE composition grammar path.

## Focused Evidence

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=/private/tmp/priori-r2-4-single-20260705095024/src UV_CACHE_DIR=/private/tmp/uv-cache-priori /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r2_4_sequence_pattern tests.test_r1_0_operator_scaffolding tests.test_scp2_1_meaning_to_target` | PASS | 31 tests in `0.057s`. |

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make test` | PENDING | Must run on committed tree. |

