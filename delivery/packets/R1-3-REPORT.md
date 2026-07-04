# R1-3 Report - extremum_over_set Operator

Branch: `packet/r1-3`
Frontier base: `d509ca2`
Packet: `delivery/packets/R1-3-extremum-over-set.md`
ADR: `docs/adr/0013-r1-operator-era.md`, including all three addenda
Push: no push, per direct-channel protocol.

## Result

READY FOR REVIEW.

The sandbox blocks writes to the canonical repository's `.git` directory, so
this work is being committed in a writable clone at
`/private/tmp/priori-r1-3-clone`, branch `packet/r1-3`.

Stage-committed-from-first-commit was satisfied by `c7bb27c`.

## Commit Ledger

| Commit | Purpose |
| --- | --- |
| `c7bb27c` | Stage-committed R1-3 report skeleton before implementation. |
| `645d6e3` | Implemented `extremum_over_set`, the defender-distance candidate relation, search synthesis, and the acceptance target. |
| `9662b5d` | Declared the defender-distance candidate relation in the semantic registry. |
| `37566fa` | Added the composition-level both-team test for the defender-distance relation feeding the operator. |

## Required Acceptance Items

| Item | Status | Notes |
| --- | --- | --- |
| `extremum_over_set@0.1.0` signature and implementation | DONE | Added `src/tqe/runtime/operators/extremum_over_set.py`, exported via the operator registry. |
| Selection witnesses | DONE | Output rows include selected record id, selected entity id, selected frame id, selected value, source record hash/index, source node/output, source anchor id, and subject id. |
| Coverage poisoning | DONE | Incomplete set coverage returns UNKNOWN unless the declared value bound proves missing candidates cannot improve the selected answer. `top_k > valid_count` returns UNKNOWN. |
| Deterministic tie-breakers | DONE | Tie order uses declared primary/secondary tie-breaker fields plus stable hash/index fallback; shuffle-stability is tested. |
| Both-teams correctness | DONE | Added composition-level test proving home anchors select away defenders and away anchors select home defenders. |
| Search synthesis | DONE | Generic `extremum_over_set` insertion added; all declared constraint keys are consumed or synthesis fails with unapplied-key diagnostics. |
| Acceptance composition | DONE | `nearest_defender_relation` now compiles through `controlled_pass_episode -> defender_distance_candidate_set -> extremum_over_set`. |
| Booked-evidence audit | DONE | See the witness audit table below; the selected defender is traced back to raw parquet. |
| Full suite and pinned gates | DONE WITH DISCLOSED GENERATED DRIFT | Runtime proof and q6 pass; full suite has three generated-currentness failures caused by the new declaration surface. |

## Implementation Summary

### Operator

`extremum_over_set@0.1.0` consumes declared candidate records and selects an
argmin/argmax/top-k record per anchor. The operator is deliberately field-driven:
the plan must declare the value field, record id field, entity id field, frame
field, tie-breaker fields, optional anchor/subject fields, status field, coverage
field, coverage policy, and value-bound semantics. Bind validation rejects
unbound operator field parameters.

Claim boundary: the operator selects over its supplied records only. It does not
create the candidate set, infer missing candidates, infer tactical assignment, or
claim quality/intent/optimality.

### Candidate Relation

Added `defender_distance_candidate_set@0.1.0` in the team-shape family. It emits
candidate defender-distance rows for declared anchors and target players.

Supported scopes:

- `defending_outfield`: known defending outfield set, with missing tracked
  players producing incomplete coverage.
- `observed_defending_outfield`: observed defending outfield candidates only,
  complete over that observed set. This is the acceptance target scope, and the
  target's semantic correspondence explicitly says it does not claim untracked
  defenders were farther away.

The relation is only a candidate-record source. Its catalog limitations state
that it does not select the nearest defender, infer marking assignment, pressure
quality, intent, scheme, causation, or optimality.

### Search Synthesis

The compiler search path now supports the `extremum_over_set` constraint kind.
For the acceptance target it found one discovery candidate:

| Field | Value |
| --- | --- |
| Candidate source count | 1 |
| Selected source | `defender_distance_candidate_set.anchor_evaluations` |
| Providers used | `controlled_pass_episode`, `defender_distance_candidate_set`, `operator:extremum_over_set` |
| Rules used | `typed_anchor_provider_discovery`, `provider_field_backward_search`, `generic_relation_on_anchor`, `generic_extremum_over_set_operator` |

The generated operator constraint consumed these declared fields:

- `selection_mode=argmin`
- `value_field=candidate_distance_m`, `value_unit=metre`
- `record_id_field=candidate_record_id`
- `entity_id_field=candidate_defender_id`
- `frame_field=candidate_frame_id`
- `anchor_id_field=source_anchor_id`
- `subject_id_field=target_player_id`
- `status_field=defender_distance_candidate_status`, `required_status_value=PASS`
- `coverage_status_field=coverage_status`
- `coverage_policy=unknown_if_incomplete_could_change_answer`
- `value_bound_kind=lower`, `value_bound=0.0`
- `tie_breaker_field=candidate_defender_id`
- `secondary_tie_breaker_field=candidate_record_id`
- `missing_evidence_policy=unknown`

The relation-on-anchor source constraint consumed:

- `anchor_frame_field=controlled_reception_frame_id`
- `target_player_id_field=receiver_id`
- `required_anchor_status_field=controlled_pass_status`
- `required_anchor_status_value=PASS`
- `candidate_scope=observed_defending_outfield`
- `minimum_observed_candidates=6`

## Declaration Edits

| File | Declaration |
| --- | --- |
| `src/tqe/runtime/operators/__init__.py` | Registers `extremum_over_set`. |
| `src/tqe/runtime/catalog.py` | Declares `defender_distance_candidate_set@0.1.0`, output evidence fields, status/count fields, parameters, limitations, and non-claim boundaries. |
| `src/tqe/runtime/capabilities/__init__.py` | Exposes the team-shape candidate relation implementation. |
| `semantic-registry/registry.yaml` | Adds `concept.observed_defender_distance_candidate_set`, `op.observed_defender_distance_candidate_set.v1`, `impl.defender_distance_candidate_set.python.v1`, binding `binding.relation.defender_distance_candidate_set.0_1_0`, claim/evidence contracts, and denied product/AI exposure policy. |
| `config/compiler-reachability/r1-3-extremum-over-set-targets.v0.json` | Declares the held-out acceptance target, target correspondence, and claim boundary. |

## Acceptance Proof

Committed-tree non-mutating proof command:

```bash
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-3-extremum-over-set-targets.v0.json \
TQE_SEARCH_OUT_DIR=/private/tmp/r1-3-proof-current.0mh3DY/out \
TQE_SEARCH_REPORT=/private/tmp/r1-3-proof-current.0mh3DY/report.json \
TQE_SEARCH_NODE_CACHE_ROOT=/private/tmp/r1-3-proof-current.0mh3DY/cache \
TQE_SEARCH_UPDATE_LEDGER=0 \
TQE_SEARCH_SHARED_NODE_CACHE=0 \
TQE_SEARCH_PERSISTENT_NODE_CACHE=0 \
UV_CACHE_DIR=/private/tmp/uv-cache-priori \
uv run python scripts/coverage_map/compiler_search_reachability.py
```

| Field | Value |
| --- | --- |
| Report status | PASS |
| Concept | `nearest_defender_relation` |
| Target | `r1_3_argmin_defender_distance_v0` |
| Result | `compiler_reachable` |
| Result count | 20 |
| Requested evidence failures | 0 |
| Document hash | `740acb05d9e9b84dbaa7283c9b292782b6f4a271a60fd413dbf6f43d289dce30` |
| Row-ledger hash | `4ec6609d7754908685ebcc6bbe18fd967ba727ff7bf76c7380d3010068b714ee` |
| Report hash | `dddaf52e1125413d202a6ef16d0ae3cbd3f7de6e8d794cb89fd43d88f5a0e03b` |

Ledger-copy delta command used the same target against a copied
`generated/coverage-map.json` with ledger mutation enabled.

| Field | Value |
| --- | --- |
| Temp dir | `/private/tmp/r1-3-ledger-current.EIBRDl` |
| Before compiler-reachable count | 9 |
| After compiler-reachable count | 10 |
| Supported count | 362 / 741 (48.9%) |
| After compiler-reachable pct | 1.3% |
| Target result count | 20 |
| Target requested evidence failures | 0 |
| Ledger-copy hash | `8d308c7115b67b613eccb8ccd1d127299af2e95afdec60f0c4b078692537598c` |
| Row-ledger hash | `262481ef05303bfdb3b21d97e7e21058e06220a479fab19d4d75feb4c7dcd351` |
| Report hash | `46a72615bbe7c316e20ed94ca15a7dcdb9f6ace3c08801cc8d16361706bc3f73` |

No tracked ledger was mutated; the real flip is left to the director.

## Booked-Evidence Audit

Audit artifact source: `/private/tmp/r1-3-search.ocMWVw`.

The first selected row was walked from result row to selected source record to
raw parquet.

| Field | Value |
| --- | --- |
| Result id | `e4876889c129ee87` |
| Match / period / frame | `J03WOH` / `firstHalf` / `14515` |
| Selected defender | `DFL-OBJ-002GAB` |
| Subject target | `DFL-OBJ-J014UG` |
| Selected value | `9.291` m |
| Source anchor id | `d007f13f1dbf128a` |
| Selected source record hash | `d326cbd7d8deb12ef64166853652790f30866bf0aa2f0ca51ca8e381f73e8295` |
| Selected source record index | 3 |
| Valid candidate count | 10 |
| Unknown candidate count | 0 |
| Coverage status | COMPLETE |

Raw parquet audit:

| Raw field | Value |
| --- | --- |
| Target point | `(47.81, -18.15)` |
| Selected defender point | `(43.46, -9.94)` |
| Raw computed distance | `9.291211` m |
| Reported rounded value | `9.291` m |
| Absolute difference | `0.000211` m |
| Nearest observed defenders | `DFL-OBJ-002GAB` 9.291211 m; `DFL-OBJ-002G2Y` 9.660233 m; `DFL-OBJ-0027VS` 22.380920 m |
| Observed outfield candidate count | 10 |

The selected source record hash matched exactly one relation output row, and the
raw parquet nearest defender is the selected defender. This satisfies the
selection-witness requirement for the booked exhibit.

## Behavioral Boundaries

- The target is over `observed_defending_outfield` candidates. It does not claim
  untracked defenders were farther away.
- The relation emits candidates only; the operator performs the selection.
- Missing set coverage poisons selection only when a missing candidate could
  change the selected answer under the declared value-bound policy.
- The target forbids marking assignment, pressure quality, defender intent,
  defensive scheme, tactical causation, and optimality claims.

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori uv run python -m py_compile tests/test_r1_3_extremum_over_set.py` | PASS | Syntax check for the latest both-team test. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori uv run python -m unittest tests.test_r1_3_extremum_over_set tests.test_r1_0_operator_scaffolding tests.test_r1_2_delta_across_anchor.DeltaAcrossAnchorTests.test_candidate_score_ratcheted_against_provider_name_literals` | PASS | 16 tests in 0.128s. Includes tie-breaks, coverage poisoning, top-k boundary, bind validation, executor path, provider-name ratchet, and both-team relation composition. |
| Non-mutating compiler proof, current committed tree | PASS | `compiler_reachable`, 20 rows, 0 requested evidence failures. |
| Ledger-copy compiler proof | PASS | Compiler-reachable count 9 -> 10 on copied ledger only. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make afl-substrate-q6-verify` | PASS | Honest-zero remains intact; runtime trace hash `b9e24dabc23931c0de15ee665d39fcd15a6ce30de02c0fa932a012f332695f8c`. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make scp-0-verify` | EXPECTED FAIL, semantic PASS | SCP-0 report status PASS, findings `[]`, runtime capabilities orphaned `0`; make exits 1 due generated semantic-registry projection/lock drift after the new registry declaration. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make test` | EXPECTED FAIL, 414 tests / 3 failures | Runtime attestation status VERIFIED with no blocking reasons. Failures are generated-currentness drift guards listed below. |

Full-suite failures on the committed tree:

| Test | Failure class | Attribution |
| --- | --- | --- |
| `test_m1_1_binder.M11BinderTests.test_generated_artifacts_are_current` | Generated binder artifact stale | Fresh generation includes `defender_distance_candidate_*` evidence fields; checked-in artifact has previous team-press surface. |
| `test_scp0_semantic_registry.SCP0SemanticRegistryTests.test_checked_in_lock_and_parity_report_match_fresh_regeneration` | Semantic registry lock/report stale | Checked-in lock hash `848edee312004998c1bc8ec5779f436d7ea49ccbf9155c751748132fa5a6e616`; fresh lock hash `2d19d16d099b56aeb6a18ad424af7589ace8042f46702bab04fb13321221986a`. |
| `test_verifier_write_mode.CheckModeIsReadOnlyTests.test_scp0_verifier_check_mode_leaves_tracked_files_untouched` | SCP-0 check-mode exits on drift | Same generated semantic-registry projection/lock drift. |

SCP-0 projection drift paths reported by `make scp-0-verify`:

- `generated/semantic-registry/ai-projection.json`
- `generated/semantic-registry/capability-passport-projection.json`
- `generated/semantic-registry/product-projection.json`
- `generated/semantic-registry/recipe-library-projection.json`
- `generated/semantic-registry/research-atlas-projection.json`
- `generated/semantic-registry/runtime-manifest.json`
- `generated/semantic-registry/semantic-parity-report.json`
- `generated/semantic-registry/unsupported-capability-projection.json`
- `semantic-registry/registry.lock.json`

These generated artifacts were not regenerated in the packet branch; the packet
adds the implementation and declarations and reports the drift for director
acceptance/refreeze.

## Final Worktree Note

The committed branch is the output. At report time the only local untracked
helpers were a `data` symlink for the temporary clone and `uv.lock` generated by
the local `uv` invocation; they are not packet outputs and are removed before
handoff.
