# SCP2-2 Report: Hermes NL To Meaning Expression

Branch: `packet/scp2-2`

Frontier base: `a412a56` (`codex/afl08-passport-loop`)

Current evidence commit before this report update: `38c8050`

## Resolution Status

The R-AS2-amended subscription blocker is resolved. The owner refreshed the
OpenAI Codex OAuth credential in the canonical Hermes home
`/Users/luisrevilla/.hermes-priori` (credential #2), and the director
smoke-verified a live bridge call returning `ExpressionOutcome` through
`openai-codex`. The final DEV run used that canonical Hermes home.

No metered API provider was used for the final R-AS2-amended evidence. Billing
surface is the ChatGPT subscription.

Blind set remains sealed. I read only
`config/scp2-2-blind-eval.sha256`:
`4161ebcd5cbb890d334a681f2d5ed49402819d01e2ac7978eea413f657445625  scp2-2-blind-eval-set.json`.

No push was performed.

## Round-2 Rulings

| Ruling | Status | Evidence |
| --- | --- | --- |
| R-AQ | DONE | Target contract rendering is mechanically name-free; concept identity remains only in `coverage_row` and the meaning label. Mutation test: `test_renderer_makes_target_contract_name_free_even_when_text_echoes_concept`. |
| R-AS | DONE | Few-shot examples are generated from committed certified fixtures `scp2-1-roundtrip` and `r2-4-flagship`; prompt projection includes minimal-contract guidance. |
| R-AS2-amended | DONE | Strongest configured subscription tier: `openai-codex/gpt-5.5`; final DEV latency `842.982s`, long-run flagged. |
| R-AT | DONE | Canonical Hermes home is fixed at `/Users/luisrevilla/.hermes-priori`; final evidence used it. The director's backup was not modified by this executor. |

## Prompt Projection

| Field | Value |
| --- | --- |
| Pack path | `generated/tactical-knowledge-pack.json` |
| Pack hash | `b40458086fe5d81e3f709ceb5f2301038391d6a97f64ee02585f4a9019018099` |
| Prompt hash | `7c770eb04471dc81734d11a651dd48a08eb12581f79306524aac96d2a8ad8ef8` |
| Prompt length | `204343` chars |

## DEV Eval

Command:

```text
HERMES_HOME=/Users/luisrevilla/.hermes-priori PYTHONPATH=src:. .venv/bin/python scripts/scp2_2/eval_harness.py --case-set delivery/packets/scp2-2-dev-cases.json --output delivery/packets/scp2-2-dev-results.json --provider openai-codex --model gpt-5.5 --long-threshold-seconds 300
```

Result:

| Field | Value |
| --- | --- |
| Case-set hash | `0a5ca9eaa6f2af2eab54514a7e1fb87bf8226550a19711a92534709b8b5027fe` |
| Provider/model | `openai-codex/gpt-5.5` |
| Billing surface | `chatgpt_subscription` |
| Pass/fail | `15 PASS / 0 FAIL / 15 total` |
| Elapsed | `842.982s` |
| Long-run flag | `true` (`300s` threshold) |
| Output-shape errors | `0` |
| Anti-hint refusals | `0` |

Clarification note: `dev_clarification_support_definition` now uses a
generated classifier clarification for alias-only support language, then the
typed resume path selects the `support_arrival_relation` reading. This is not
reported as a model-generated first turn. `dev_clarification_distance_threshold`
uses `openai-codex/gpt-5.5` for the first turn and typed-state resume for the
answer.

Typed refusals were genuine missing capabilities: `BODY_ORIENTATION`,
`PASS_PROBABILITY`, `PLAYER_INTENT`, and unsupported modality `VIDEO`.

## Verification

| Check | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_scp2_2_hermes_nl tests.test_scp2_1_meaning_to_target` | PASS | 46 tests in `0.530s`. |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 560 tests in `460.132s`; long run. Executed in detached worktree `/private/tmp/priori-scp2-2-fullsuite-38c8050` at commit `38c8050`, with gitignored `data/canonical`, `data/raw`, and `data/features` symlinked from the main checkout. Matplotlib cache and Arrow `sysctlbyname` warnings only. |

Full-suite output ended with:

```text
Ran 560 tests in 460.132s

OK
{"attestation_status": "VERIFIED", "blocking_reasons": []}
```

## Mutation-Standard Guards

| Guard | Named Test |
| --- | --- |
| No fifth outcome constructible | `test_outcome_type_exhaustiveness_rejects_fifth_outcome_shape`, `test_model_output_parser_rejects_fifth_raw_shape` |
| Expression gate runs on model expressions | `test_mutation_bypassing_expression_gate_would_accept_body_orientation_oov` |
| Unsupported modality routes to typed refusal | `test_expression_gate_routes_unsupported_modality_to_typed_refusal` |
| Prompt projection is generated from pack | `test_prompt_projection_changes_when_pack_copy_changes_and_no_hand_sentinel_exists` |
| Certified few-shots generated into projection | `test_prompt_projection_contains_generated_certified_few_shots` |
| Recipe authoring guides generated into projection | `test_prompt_projection_contains_generated_recipe_authoring_guides` |
| Generated classifier rules in projection | `test_prompt_projection_contains_generated_classifier_rules` |
| Multi-turn typed resume without re-asking | `test_multi_turn_clarification_state_resumes_without_reasking_model`, `test_clarification_resume_selects_fuzzy_typed_reading`, `test_clarification_resume_can_select_by_reading_expression_identity` |
| Alias-only support clarification guard | `test_alias_only_support_uses_generated_typed_clarification_without_model_call` |
| Distance aliases do not preanswer without numeric threshold | `test_distance_clarification_alias_does_not_preanswer_without_numeric_threshold` |
| Name-free contract body | `test_renderer_makes_target_contract_name_free_even_when_text_echoes_concept` |
| Harness verdict correctness | `test_harness_verdict_correctness_on_tiny_fixture_set` |

## Appended Commits

| Commit | Summary |
| --- | --- |
| `ed2927b` | Default SCP2-2 Hermes to subscription path |
| `7b58407` | Record SCP2-2 subscription smoke blocker |
| `37ed44a` | Canonicalize SCP2-2 sequence and support resumes |
| `7e5a9e5` | Route possession corridor aliases to exact recipe |
| `a23b5da` | Stabilize SCP2-2 support clarification answer |
| `f9b3d5c` | Clarify SCP2-2 support arrival answer |
| `835f65e` | Cover counterattack count-rate sequence alias |
| `8fc98e1` | Add generated support clarification guard |
| `38c8050` | Record SCP2-2 openai-codex DEV pass |

## Residual Risk

The blind set was not possessed or run. The alias-only support first turn is a
generated deterministic clarification guard, not a model-generated
clarification; the report and DEV evidence do not claim otherwise.
