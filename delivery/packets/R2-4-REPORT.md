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
| `93bf39a` | sequence_pattern operator, registry, pack delta, focused tests. |
| `PENDING` | Possession-continuity evidence, compiler-search sequence builder, R2-4 meaning-expression fixture, bridge regression test. |

## Pack Delta

| Item | Before | After | Evidence |
| --- | ---: | ---: | --- |
| Composition operators | 7 | 8 | `sequence_pattern@0.1.0` appears in `generated/tactical-knowledge-pack.json`. |
| Composition constraint kinds | 14 | 15 | `sequence_pattern` constraint kind is registry-derived. |

The bridge schema was not extended. The meaning-expression vocabulary now sees `sequence_pattern` through the existing R-AE composition grammar path.

## Focused Evidence

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=/private/tmp/priori-r2-4-single-20260705095024/src UV_CACHE_DIR=/private/tmp/uv-cache-priori /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r2_4_sequence_pattern tests.test_r1_0_operator_scaffolding tests.test_scp2_1_meaning_to_target` | PASS | 32 tests in `0.066s`; includes R2-4 registry-to-pack-to-synthesis fixture. |

## Bridge Fixture

| Item | Evidence |
| --- | --- |
| Fixture | `delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_chain_count.v0.json` |
| Vocabulary path | Accepted by `load_meaning_expression_from_path` using generated pack SHA. |
| Synthesis path | `synthesize_and_bind` returns `operator:aggregate_over` with `population_terminal=operator:sequence_pattern`. |
| Document hash | `7e876649b73fd502e79291389b76ef028a229e8fa83bd3b39a4d224c10489dc7` |
| Schema change | No bridge schema extension; `stage_N_required_fields` and `possession_continuity_source` are registry-derived composition/operator parameters. |

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make test` | PENDING | Must run on committed tree. |

