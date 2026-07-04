# R1-3 Report - extremum_over_set Operator

Branch: `packet/r1-3`
Frontier base: `d509ca2`
Review base: `f89c3bb` (`delivery/packets/R1-3-REVIEW.md`)
Packet: `delivery/packets/R1-3-extremum-over-set.md`
ADR: `docs/adr/0013-r1-operator-era.md`, including all three addenda
Push: no push, per direct-channel protocol.

## Result

READY FOR REVIEW, ROUND 2.

The sandbox blocks writes to the canonical repository's `.git` directory, so
this work is committed in a writable clone at `/private/tmp/priori-r1-3-clone`,
branch `packet/r1-3`.

Stage-committed-from-first-commit was satisfied by `c7bb27c`.

## Commit Ledger

| Commit | Purpose |
| --- | --- |
| `c7bb27c` | Stage-committed R1-3 report skeleton before implementation. |
| `645d6e3` | Implemented `extremum_over_set`, the defender-distance candidate relation, search synthesis, and the acceptance target. |
| `9662b5d` | Declared the defender-distance candidate relation in the semantic registry. |
| `37566fa` | Added the composition-level both-team test for the defender-distance relation feeding the operator. |
| `993dad9` | Finalized the round-1 report. |
| `18c3b99` | Addressed R1-3 review F1/F2/F4: top-k coverage, provider-blind search, stable external paths, and regression tests. |

## Round-2 Review Fixes

| Finding | Status | Evidence |
| --- | --- | --- |
| F1 top-k coverage | DONE | Coverage now decides against `ranked[top_k - 1]`, not rank 1. Added `test_top_k_coverage_decides_against_kth_ranked_value`. |
| F2 provider pinning / scoring | DONE | Removed `source_provider` and `source_output` from the extremum constraint input, removed the provider-name score bonus, and added tests that provider-pinning keys fail as unapplied constraints. |
| F2 T1 ratchet extension | DONE | Added `provider_name_used_as_hint` guard over target-contract string values and a test that the old `source_provider=defender_distance_candidate_set` channel is detected. |
| F3 full booked audit | DONE | All 20 selected rows are walked to raw parquet below. |
| F4 reproducible hashes | DONE | `relative_path` now emits stable `<external>/...` paths for out-of-repo temp artifacts. Two different temp proof dirs produced identical row-ledger/report hashes and the stable runtime trace hash below. |

## Implementation Summary

### Operator

`extremum_over_set@0.1.0` consumes declared candidate records and selects an
argmin/argmax/top-k record per anchor. The plan declares the value field, record
id field, entity id field, frame field, tie-breaker fields, optional
anchor/subject fields, status field, coverage field, coverage policy, and
value-bound semantics. Bind validation rejects unbound operator field
parameters.

Round 2 changed one behavior: incomplete-coverage top-k selection is now judged
against the kth ranked valid value. For example, with `top_k=2`, a missing
candidate that cannot beat rank 1 but could displace rank 2 now poisons the
answer to UNKNOWN.

Claim boundary: the operator selects over its supplied records only. It does not
create the candidate set, infer missing candidates, infer tactical assignment, or
claim quality/intent/optimality.

### Candidate Relation

`defender_distance_candidate_set@0.1.0` emits defender-distance candidate rows
for declared anchors and target players.

Supported scopes:

- `defending_outfield`: known defending outfield set, with missing tracked
  players producing incomplete coverage.
- `observed_defending_outfield`: observed defending outfield candidates only,
  complete over that observed set. This is the acceptance target scope; the
  target explicitly does not claim untracked defenders were farther away.

The relation emits candidate records only. It does not select the nearest
defender, infer marking assignment, pressure quality, intent, scheme, causation,
or optimality.

### Search Synthesis

The compiler search path supports the `extremum_over_set` constraint kind through
generic operator insertion. The round-2 target is unpinned: no
`source_provider`/`source_output` keys are accepted as synthesis input. The
selected provider/output remains post-hoc metadata only.

Unpinned discovery space:

| Field | Value |
| --- | --- |
| Candidate source count | 1 |
| Selected source | `defender_distance_candidate_set.anchor_evaluations` |
| Providers used | `controlled_pass_episode`, `defender_distance_candidate_set`, `operator:extremum_over_set` |
| Rules used | `typed_anchor_provider_discovery`, `provider_field_backward_search`, `generic_relation_on_anchor`, `generic_extremum_over_set_operator` |
| Concept-name hint | `false` |
| Provider-name hint | `false` |

The generated operator constraint consumed:

- `selection_mode=argmin`
- `top_k=1`
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
| `config/compiler-reachability/r1-3-extremum-over-set-targets.v0.json` | Declares the held-out acceptance target, target correspondence, and claim boundary. Round 2 removed provider-pinning keys from this target. |

## Acceptance Proof

Two non-mutating proof runs were executed from the committed round-2 tree in
different temp directories:

- `/private/tmp/r1-3-r2-proof-a.9CEAFA`
- `/private/tmp/r1-3-r2-proof-b.ZdgaOZ`

Both used:

```bash
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-3-extremum-over-set-targets.v0.json \
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
| Runtime trace hash | `638e4de523fdd5f8030fb7f533c2c276475e2107a9d44331e57e32f91459f810` |
| Row-ledger hash, both temp dirs | `4efc151fce41b6deb771955f5a218dfc222f27a397e5abaeb4b8c6ab1fe90b69` |
| Report hash, both temp dirs | `76758857f83413f32056b522286e4923bca4e7f8a5d6dc17e002405ba475b876` |
| Unpinned discovery count | 1 |

Ledger-copy delta command used the same target against a copied
`generated/coverage-map.json` with ledger mutation enabled.

| Field | Value |
| --- | --- |
| Temp dir | `/private/tmp/r1-3-r2-ledger.3J100d` |
| Before compiler-reachable count | 9 |
| After compiler-reachable count | 10 |
| Supported count | 362 / 741 (48.9%) |
| After compiler-reachable pct | 1.3% |
| Target result count | 20 |
| Target requested evidence failures | 0 |
| Runtime trace hash | `638e4de523fdd5f8030fb7f533c2c276475e2107a9d44331e57e32f91459f810` |
| Ledger-copy hash | `b52400fbc719791f73ccd6a88c15ad727c0cb6a91b59ebf55195dde61940e2db` |
| Row-ledger hash | `4efc151fce41b6deb771955f5a218dfc222f27a397e5abaeb4b8c6ab1fe90b69` |
| Report hash | `07e91adfe2547ad7e89a7e8a573b9eb447617023d1381b4676f42c87fee0110c` |

No tracked ledger was mutated; the real flip remains a director action.

## Full Booked-Evidence Audit

Audit artifact source: `/private/tmp/r1-3-r2-full-audit.json` and
`/private/tmp/r1-3-r2-full-audit.md`.

Method: execute the generated proof plan, then for every selected row load the
raw positions parquet at `match_id/period/frame_id`, derive the selected
candidate team from the selected entity's raw team role at that frame, exclude
goalkeepers via `players.parquet`, compute all outfield candidate distances to
the subject target, and verify the selected entity is the nearest raw candidate.

All 20 rows matched the raw nearest candidate. Differences below are only the
expected rounded-reporting deltas.

| n | result_id | frame_id | subject_team_role | candidate_team_role | subject_id | selected_entity_id | reported_m | computed_m | abs_diff_m | nearest_raw_entity_id | candidate_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | e4876889c129ee87 | 14515 | home | away | DFL-OBJ-J014UG | DFL-OBJ-002GAB | 9.291 | 9.291211 | 0.000211 | DFL-OBJ-002GAB | 10 |
| 2 | 35707d5bc52836d0 | 14567 | home | away | DFL-OBJ-002FXT | DFL-OBJ-002651 | 2.147 | 2.147301 | 0.000301 | DFL-OBJ-002651 | 10 |
| 3 | 97b18c1817ac9b1b | 15081 | home | away | DFL-OBJ-0028FW | DFL-OBJ-002G2Y | 14.681 | 14.680613 | 0.000387 | DFL-OBJ-002G2Y | 10 |
| 4 | 4e2099c431b03ea6 | 15146 | home | away | DFL-OBJ-J0130T | DFL-OBJ-0027VS | 3.388 | 3.387875 | 0.000125 | DFL-OBJ-0027VS | 10 |
| 5 | ff34ccdc27829964 | 15190 | home | away | DFL-OBJ-J014UG | DFL-OBJ-002G2Y | 16.657 | 16.657146 | 0.000146 | DFL-OBJ-002G2Y | 10 |
| 6 | 070942ddf2856edd | 15756 | away | home | DFL-OBJ-002GNH | DFL-OBJ-00003X | 10.315 | 10.314771 | 0.000229 | DFL-OBJ-00003X | 10 |
| 7 | 785db9eaf7db5be4 | 17719 | home | away | DFL-OBJ-00006V | DFL-OBJ-002G2Y | 13.405 | 13.40457 | 0.00043 | DFL-OBJ-002G2Y | 10 |
| 8 | f5eb1f1823384e50 | 18826 | home | away | DFL-OBJ-002GM1 | DFL-OBJ-0028SW | 1.114 | 1.113643 | 0.000357 | DFL-OBJ-0028SW | 10 |
| 9 | 0f8942291d7c47d3 | 20464 | home | away | DFL-OBJ-0000NZ | DFL-OBJ-0027XP | 9.589 | 9.588535 | 0.000465 | DFL-OBJ-0027XP | 10 |
| 10 | e694147344056a25 | 23259 | home | away | DFL-OBJ-J014UG | DFL-OBJ-002GAB | 17.523 | 17.523461 | 0.000461 | DFL-OBJ-002GAB | 10 |
| 11 | 930bb54e50791670 | 23335 | home | away | DFL-OBJ-0028FW | DFL-OBJ-0027XP | 9.377 | 9.377126 | 0.000126 | DFL-OBJ-0027XP | 10 |
| 12 | 79d12aad787fe856 | 23670 | away | home | DFL-OBJ-002651 | DFL-OBJ-00028V | 2.703 | 2.702961 | 0.000039 | DFL-OBJ-00028V | 10 |
| 13 | 616ad071072a6e66 | 23745 | away | home | DFL-OBJ-002GEE | DFL-OBJ-00003X | 7.907 | 7.906839 | 0.000161 | DFL-OBJ-00003X | 10 |
| 14 | a213d2824201baeb | 23881 | away | home | DFL-OBJ-002GNH | DFL-OBJ-002FXT | 14.989 | 14.988863 | 0.000137 | DFL-OBJ-002FXT | 10 |
| 15 | ec2ff65c8adbb0f9 | 24137 | home | away | DFL-OBJ-J0130T | DFL-OBJ-002G2Y | 2.775 | 2.775464 | 0.000464 | DFL-OBJ-002G2Y | 10 |
| 16 | c7883d3ce0fe7993 | 25882 | away | home | DFL-OBJ-002GNH | DFL-OBJ-00003X | 26.891 | 26.890537 | 0.000463 | DFL-OBJ-00003X | 10 |
| 17 | 5032558370fa396d | 26032 | away | home | DFL-OBJ-0027VS | DFL-OBJ-00028V | 4.397 | 4.396931 | 0.000069 | DFL-OBJ-00028V | 10 |
| 18 | bc294d4ae9debf85 | 26109 | away | home | DFL-OBJ-0026UQ | DFL-OBJ-0000F8 | 9.518 | 9.517736 | 0.000264 | DFL-OBJ-0000F8 | 10 |
| 19 | 21e0464b1249b10e | 26301 | away | home | DFL-OBJ-0027VS | DFL-OBJ-0000F8 | 7.418 | 7.418383 | 0.000383 | DFL-OBJ-0000F8 | 10 |
| 20 | a3e2260787ea402d | 26615 | home | away | DFL-OBJ-002GM1 | DFL-OBJ-002GAB | 5.88 | 5.880306 | 0.000306 | DFL-OBJ-002GAB | 10 |

## Behavioral Boundaries

- The target is over `observed_defending_outfield` candidates. It does not claim
  untracked defenders were farther away.
- The relation emits candidates only; the operator performs the selection.
- Missing set coverage poisons selection when a missing candidate could change
  the selected top-k answer under the declared value-bound policy.
- The target forbids marking assignment, pressure quality, defender intent,
  defensive scheme, tactical causation, and optimality claims.

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori uv run python -m py_compile src/tqe/runtime/operators/extremum_over_set.py scripts/coverage_map/compiler_search_reachability.py tests/test_r1_3_extremum_over_set.py` | PASS | Syntax check for changed files. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori uv run python -m unittest tests.test_r1_3_extremum_over_set tests.test_r1_0_operator_scaffolding tests.test_r1_2_delta_across_anchor.DeltaAcrossAnchorTests.test_candidate_score_ratcheted_against_provider_name_literals` | PASS | 19 tests in 0.059s. Includes round-2 top-k and provider-pinning regressions. |
| Non-mutating compiler proof, two temp dirs | PASS | `compiler_reachable`, 20 rows, 0 requested evidence failures; row-ledger/report hashes reproduced exactly. |
| Ledger-copy compiler proof | PASS | Compiler-reachable count 9 -> 10 on copied ledger only. |
| Full raw-parquet selected-witness audit | PASS | All 20 selected rows walked to raw parquet; every selected entity was the nearest raw outfield candidate at the selected frame. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make afl-substrate-q6-verify` | PASS | Honest-zero remains intact; runtime trace hash `b9e24dabc23931c0de15ee665d39fcd15a6ce30de02c0fa932a012f332695f8c`. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make scp-0-verify` | EXPECTED FAIL, semantic PASS | SCP-0 report status PASS, findings `[]`, runtime capabilities orphaned `0`; make exits non-zero due generated semantic-registry projection/lock drift after the new registry declaration. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make test` | EXPECTED FAIL, 417 tests / 3 failures | Runtime attestation status VERIFIED with no blocking reasons. Failures are generated-currentness drift guards listed below. |

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

The committed branch is the output. The temporary clone uses a local `data`
symlink for verification and `uv.lock` may be generated by local `uv`; neither
is a packet output and both are removed before handoff.
