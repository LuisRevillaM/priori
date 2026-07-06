# SCP2-2 Report: Hermes NL To Meaning Expression

Branch: `packet/scp2-2`

Frontier base: `a412a56` (`codex/afl08-passport-loop`)

Current evidence commit before this report update: `b2b9148`

## Resolution Status

Round 3 reports the restored DEV set honestly. The previous round-2 `15/15`
claim is rejected in `delivery/packets/SCP2-2-REVIEW.md`; this report does not
carry it forward.

The live DEV evidence uses the canonical Hermes home
`/Users/luisrevilla/.hermes-priori`, provider/model `openai-codex/gpt-5.5`,
and the ChatGPT subscription billing surface. No metered API provider was used.

Blind set remains sealed. I read only `config/scp2-2-blind-eval.sha256`:
`4161ebcd5cbb890d334a681f2d5ed49402819d01e2ac7978eea413f657445625  scp2-2-blind-eval-set.json`.

No push was performed.

## Round-3 Rulings

| Ruling | Status | Evidence |
| --- | --- | --- |
| R-AU | DONE | Removed sequence/rate canned-plan routing, recipe alias exact-plan routing, single-provider elision, default-invocation population discards, deterministic support payloads, distance-threshold carve-out, and preanswered clarification auto-flip. Shortcut symbol scan over `src`, `tests`, `scripts`, and restored DEV cases is empty. |
| R-AV | DONE | Reverted silent `target_synthesis.py` changes back to SCP2-1 search/bind behavior except the flagged be_011 repair outside `target_synthesis.py`. If invariance needs equivalence law later, it remains a director ratification item. |
| R-AW | DONE | Restored `delivery/packets/scp2-2-dev-cases.json` to round-1 phrasings. Case-set hash: `07a10d76b1f3322e94131090068f19157975fbea65aefbebdb8e17aba2da4b7a`. |
| R-AX | DONE | Resume path re-runs the vocabulary gate; raw completions are committed in `delivery/packets/scp2-2-dev-results.json`; be_011 class fixed as a flagged machine-side defect repair. |
| R-AY | DONE | Restored DEV rerun reports the true number: `7 PASS / 8 FAIL / 15 total`. There is no pass-count target. |

## Kept General Work

Output boundary, repair re-gating, generated pack projection, fixture-generated
few-shots, refusal routing, and the R-AQ name-free renderer were kept. The
R-AQ guard remains `test_renderer_makes_target_contract_name_free_even_when_text_echoes_concept`.

## Flagged Machine-Side Repair

`scripts/coverage_map/compiler_search_reachability.py` now emits `none` for
typed-join field parameters that are inactive for the declared join semantics
and absent from the selected side output. Active join fields remain strict and
still have to bind.

This fixes the blind-class `be_011` failure mode where a valid `same_anchor`
typed join could bind-fail on unused episode start/end defaults. Regression:
`test_typed_join_synthesis_does_not_emit_inactive_missing_field_defaults`.
The accepted public fragile fixture still binds and preserves the committed
hash `bc77278b3358106178749a72edfdc730b56b23bd6b6b650c60895598ac2edfbe`.

## Prompt Projection

| Field | Value |
| --- | --- |
| Pack path | `generated/tactical-knowledge-pack.json` |
| Pack hash | `b40458086fe5d81e3f709ceb5f2301038391d6a97f64ee02585f4a9019018099` |
| Prompt hash | `7c770eb04471dc81734d11a651dd48a08eb12581f79306524aac96d2a8ad8ef8` |
| Provider/model | `openai-codex/gpt-5.5` |
| Billing surface | `chatgpt_subscription` |

## DEV Eval

Command:

```text
HERMES_HOME=/Users/luisrevilla/.hermes-priori PYTHONPATH=src:. .venv/bin/python scripts/scp2_2/eval_harness.py --case-set delivery/packets/scp2-2-dev-cases.json --output delivery/packets/scp2-2-dev-results.json --provider openai-codex --model gpt-5.5 --long-threshold-seconds 300
```

Result:

| Field | Value |
| --- | --- |
| Results commit | `e725c85` |
| Case-set hash | `07a10d76b1f3322e94131090068f19157975fbea65aefbebdb8e17aba2da4b7a` |
| Pack hash | `b40458086fe5d81e3f709ceb5f2301038391d6a97f64ee02585f4a9019018099` |
| Pass/fail | `7 PASS / 8 FAIL / 15 total` |
| Elapsed | `761.554s` |
| Long-run flag | `true` (`300s` threshold) |
| Raw completions committed | `20 observations` |
| Anti-hint refusals | `0` |
| Model output-shape errors | `0` |
| Local clarification-selection errors | `1` |

Per-case attribution:

| Case | Status | Attribution |
| --- | --- | --- |
| `dev_same_meaning_controlled_pass` | FAIL | Request 1 synthesized unbindable requested evidence (`anchors`, `episodes`); request 2 produced unsupported composed control-retention contract. |
| `dev_same_meaning_sequence_rate` | FAIL | Both expressions synthesized, but same-meaning document hashes differed. |
| `dev_same_meaning_line_break_support` | FAIL | Both phrasings named unsupported or unsatisfied composition. |
| `dev_changed_rate_vs_count` | FAIL | Request 2 omitted periods and failed document validation. |
| `dev_changed_controlled_vs_bypass` | PASS | Changed meaning stayed distinct. |
| `dev_known_possession_corridor` | FAIL | Bounded search could not satisfy reusable composition. |
| `dev_known_high_bypass` | PASS | Synthesized and bound. |
| `dev_known_first_time_relay` | FAIL | Bounded search could not satisfy reusable composition. |
| `dev_novel_sequence_rate` | PASS | Synthesized and bound. |
| `dev_refusal_body_orientation` | PASS | Typed `BODY_ORIENTATION` gap. |
| `dev_refusal_pass_probability` | PASS | Typed `PASS_PROBABILITY` gap. |
| `dev_refusal_player_intent` | PASS | Typed `PLAYER_INTENT` gap. |
| `dev_refusal_video_modality` | PASS | Typed unsupported modality `VIDEO`. |
| `dev_clarification_support_definition` | FAIL | First turn returned expression instead of `SUPPORT_DEFINITION` clarification. |
| `dev_clarification_distance_threshold` | FAIL | First turn asked `SUPPORT_DEFINITION` instead of `DISTANCE_THRESHOLD`; typed resume answer selected no reading. |

## Verification

| Check | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_scp2_1_meaning_to_target tests.test_scp2_2_hermes_nl` | PASS | 40 tests in `0.429s`. |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 554 tests in `450.287s`; long run. Executed in detached worktree `/private/tmp/priori-scp2-2-r3-fullsuite-b2b9148` at commit `b2b9148`, with gitignored `data/canonical`, `data/raw`, and `data/features` symlinked from the main checkout. Matplotlib cache and Arrow `sysctlbyname` warnings only. |

Full-suite output ended with:

```text
Ran 554 tests in 450.287s

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
| Multi-turn typed resume without re-asking | `test_multi_turn_clarification_state_resumes_without_reasking_model`, `test_clarification_resume_selects_fuzzy_typed_reading`, `test_clarification_resume_can_select_by_reading_expression_identity` |
| Local unmatched resume is not model-output error | `test_clarification_resume_unmatched_answer_is_not_model_output_error` |
| Distance aliases do not preanswer without numeric threshold | `test_distance_clarification_alias_does_not_preanswer_without_numeric_threshold` |
| Name-free contract body | `test_renderer_makes_target_contract_name_free_even_when_text_echoes_concept` |
| Canned sequence plan stripped | `test_r2_4_sequence_expression_uses_search_not_committed_certified_plan_ref` |
| Recipe exact-plan route stripped | `test_recipe_id_does_not_bypass_search_with_exact_plan_ref` |
| Single-provider elision stripped | `test_single_provider_overcomposition_is_not_silently_elided` |
| be_011 typed-join bind repair | `test_typed_join_synthesis_does_not_emit_inactive_missing_field_defaults` |
| Harness verdict correctness | `test_harness_verdict_correctness_on_tiny_fixture_set` |

## Appended Commits

| Commit | Summary |
| --- | --- |
| `9901bde` | SCP2-2 round 3 strip gamed bridge paths |
| `8bb442d` | Classify clarification resume misses separately |
| `e725c85` | Record SCP2-2 round 3 restored DEV evidence |
| `b2b9148` | Report SCP2-2 round 3 honest DEV result |

## Residual Risk

The blind v1 set is spent per review and remains sealed here. The current
honest capability is 7/15 on restored DEV with genuine model/search gaps named
above; future improvement should be based on those gaps, not dev-case edits or
targeted routing.
