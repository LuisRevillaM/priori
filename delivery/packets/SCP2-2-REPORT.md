# SCP2-2 Report: Hermes NL To Meaning Expression

Branch: `packet/scp2-2`

Frontier base: `a412a56` (`codex/afl08-passport-loop`)

## Ratification Flag

The canonical Hermes home at `/Users/luisrevilla/.hermes-priori` could not expose
the required `mcp-priori_tactical` tool surface because its MCP server config
points at stale `/Users/luisrevilla/Documents/priori` paths. I did not edit the
canonical home. For model-bound checks I used a temporary home:
`/private/tmp/hermes-priori-scp2-2`, copied from the canonical config and patched
only to point the MCP command/PYTHONPATH/output root at this checkout and
`/private/tmp/priori-scp2-2-workshop`.

The model calls were real and still used `src/tqe/workshop/hermes_invocation.py`
through the workshop service wrapper. Director action requested before blind
eval: ratify this temp-home invocation or update the canonical Hermes config.

## Protocol Status

| Item | Status | Evidence |
| --- | --- | --- |
| ADR 0015 reread | DONE | Principles 23-25 govern this packet. |
| Packet read | DONE | `delivery/packets/SCP2-2-hermes-nl.md` |
| Branch | DONE | `packet/scp2-2` from `a412a56` |
| Blind set | FENCED | Only `config/scp2-2-blind-eval.sha256` read: `4161ebcd5cbb890d334a681f2d5ed49402819d01e2ac7978eea413f657445625  scp2-2-blind-eval-set.json`. |
| Model access | AVAILABLE_WITH_ENV_NOTE | Explicit Anthropic Hermes smoke passed; workshop probe passed only with temp Hermes home above. |
| Push | NOT_DONE | Local commits only. |

## Delivered

| Slice | Status | Evidence |
| --- | --- | --- |
| Prompt projection | DONE | `build_prompt_projection()` derives schema, concepts, fields, operators, constraints, gap codes, ambiguity dimensions, refusal routing, and claim boundaries from `generated/tactical-knowledge-pack.json`. |
| Outcome contract | DONE | `HermesOutcome` is the discriminated union of `expression`, `clarification_required`, `understood_but_not_expressible`, `unsupported_modality`; invalid model JSON raises `HermesNLModelOutputError`, not a fifth outcome. |
| Vocabulary gate | DONE | Every expression payload routes through `load_meaning_expression_result`; gate refusals become typed refusals. |
| Multi-turn state | DONE | `ClarificationState` carries expressible readings; answer resume selects a typed reading without model re-entry. |
| Eval harness/dev set | DONE | `scripts/scp2_2/eval_harness.py`, `delivery/packets/scp2-2-dev-cases.json`, `delivery/packets/scp2-2-dev-results.json`. |
| Blind set | FENCED | Harness takes a case-set path; no blind cases possessed or reconstructed. |

Prompt projection:

| Field | Value |
| --- | --- |
| Pack hash | `b40458086fe5d81e3f709ceb5f2301038391d6a97f64ee02585f4a9019018099` |
| Prompt hash | `a18d60848fb810d26258399c28af774fb1da8193043817e9d0ee052bdff20bd6` |
| Prompt length | `147222` chars |

## DEV Eval

Command used:

```text
HERMES_HOME=/private/tmp/hermes-priori-scp2-2 WORKBENCH_HERMES_WORKSHOP_ROOT=/private/tmp/priori-scp2-2-workshop TQE_WORKSHOP_OUTPUT_ROOT=/private/tmp/priori-scp2-2-workshop PYTHONPATH=src:. .venv/bin/python scripts/scp2_2/eval_harness.py --case-set delivery/packets/scp2-2-dev-cases.json --output delivery/packets/scp2-2-dev-results.json --provider anthropic --model claude-sonnet-4-5 --long-threshold-seconds 300
```

Result: `4 PASS / 11 FAIL / 15 total`, elapsed `344.457s`, long-run flag `true`.

Passing cases: `dev_refusal_body_orientation`,
`dev_refusal_pass_probability`, `dev_refusal_player_intent`,
`dev_refusal_video_modality`.

Failing pattern: expression outcomes usually passed the model-output and
vocabulary gates but failed synthesis because target contracts contained
reporting concept names, unsatisfied fields, or invalid join/parameter shapes.
Clarification cases did not reliably return `clarification_required` first-turn
state.

## Verification

| Check | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_scp2_2_hermes_nl` | PASS | 7 tests. |
| `PYTHONPATH=src:. .venv/bin/python -m unittest tests.test_scp2_1_meaning_to_target tests.test_scp2_2_hermes_nl` | PASS | 25 tests. |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 539 tests in 479.083s; long run. Sandbox emitted Matplotlib/Arrow environment warnings. |
| `PYTHONPATH=src:. .venv/bin/python -m py_compile ...` | PASS | New module, harness, and tests compiled. |
| `PYTHONPATH=src:. .venv/bin/python -m ruff check ...` | NOT_RUN | `ruff` is not installed in the repo venv. |

Mutation-standard tests:

| Guard | Named Test |
| --- | --- |
| No fifth outcome constructible | `test_outcome_type_exhaustiveness_rejects_fifth_outcome_shape`, `test_model_output_parser_rejects_fifth_raw_shape` |
| Expression gate runs on every model expression | `test_mutation_bypassing_expression_gate_would_accept_body_orientation_oov` |
| Unsupported modality routed through gate | `test_expression_gate_routes_unsupported_modality_to_typed_refusal` |
| Prompt projection derived from pack | `test_prompt_projection_changes_when_pack_copy_changes_and_no_hand_sentinel_exists` |
| Multi-turn typed resume | `test_multi_turn_clarification_state_resumes_without_reasking_model` |
| Harness verdict correctness | `test_harness_verdict_correctness_on_tiny_fixture_set` |

## Commits

| Commit | Summary |
| --- | --- |
| `6b17b01` | SCP2-2 report scaffold |
| `696bf49` | Add SCP2-2 Hermes NL compiler harness |
| `436ba38` | Compact SCP2-2 prompt projection |
| `1a39d32` | Make SCP2-2 eval harness attribute case failures |
| `0b790ab` | Tighten SCP2-2 Hermes output prompt contract |
| `31cf7b7` | Guide SCP2-2 model toward synthesizeable contracts |
| `0171460` | Add generated refusal routing to SCP2-2 prompt |
| `5338455` | Record SCP2-2 DEV eval results |

## Residual Risk

The output boundary and refusal discipline are implemented and tested, but the
model side is not yet strong enough to produce synthesizeable expressions for
the DEV expression/clarification cases. The blind harness can run unmodified,
but the reported DEV result predicts blind expression cases will fail unless
the director accepts a follow-up packet for expression-target quality.
