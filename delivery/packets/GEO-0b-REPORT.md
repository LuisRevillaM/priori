# GEO-0b — typed field references report

Branch: `packet/geo-0b`

Frontier: `e30c70fd8028b51a9fd15ca47c735cb5c0c43ec7`

Executor clone: `/private/tmp/priori-geo0b-executor.yxaF0J` (outside the
repository tree)

Status: **IMPLEMENTED — CERTIFIED STOP AUDIT CLEAR**

## Design brief (authored before implementation)

### Problem and boundary

The current IR uses `TypedValue(payload_type="enum", value="<field>")` for
field selectors. Catalog selectors then constrain that string with repeated
literal `allowed_values` lists. A new controller, frame, region point, or
status field therefore requires editing consumers that should only need to
know the field's semantic type. Composition operators avoid most literal
lists, but still describe their field parameters as untyped enums.

GEO-0b replaces that authoring contract for the five kinds ratified by ADR
0018: frame, entity, point, status, and provenance. It does not reinterpret
policy enums, scalar-value selectors, grouping expressions, comparison
expressions, or comma/equality mini-languages as one of those five kinds.

### Reference type model

The IR gains one `field_ref` payload and a strict structured value:

```json
{
  "payload_type": "field_ref",
  "unit": "none",
  "value": {
    "kind": "frame | entity | point | status | provenance",
    "field": "declared_field_name"
  }
}
```

`field: null` is the typed spelling of an intentionally absent optional
reference. Field names remain open, lower-snake-case identifiers; the five
semantic kinds are closed. Thus a producer may add
`controller_frame_id`, `controller_id`, or `region_reference_point` without a
consumer enum change, while a point reference cannot bind to a frame
parameter.

Each field-reference parameter declares its required kind. Binding checks:

1. the value is a `field_ref` of the required kind;
2. a non-null field is declared by a bound input's output/evidence contract;
3. runtime access still applies the consumer's existing shape and
   missing-evidence rules (integer frame, point object, tri-state status,
   etc.).

The parameter contract is the type boundary. GEO-0b does not invent a global
field-name registry: that would merely move the literal bloat. Producers
continue declaring the fields they emit; consumers name one through a typed
reference.

### Enum inventory at the frontier

The pre-implementation inventory found **126** parameters named `*_field` or
`*_fields`:

| Surface | Owners | Parameters | Encoding today | Literal members |
| --- | ---: | ---: | --- | ---: |
| primitive/relation catalog | 24 | 50 | 50 `enum` parameters with `allowed_values` | 234 |
| composition operator signatures | 8 | 76 | 72 `enum`; 4 `entity_set` | 0 |

Catalog locations, grouped by owner (the parameter list is exhaustive):

| Kind | Owner | Current field parameters |
| --- | --- | --- |
| primitive | `structured_zone` | `frame_field` |
| primitive | `space_region_generation` | `frame_field` |
| primitive | `outcome_window` | `required_anchor_status_field` |
| primitive | `tracking_quality` | `frame_field` |
| primitive | `pairwise_distance` | `frame_field`, `entity_a_field`, `entity_b_field` |
| primitive | `marking` | `frame_field`, `target_player_id_field` |
| primitive | `cover_shadow` | `frame_field`, `target_entity_field` |
| primitive | `velocity` | `frame_field`, `entity_id_field` |
| primitive | `acceleration` | `frame_field`, `entity_id_field` |
| primitive | `off_ball_run` | `frame_field` |
| primitive | `time_to_arrival` | `frame_field`, `target_entity_field`, `target_x_field`, `target_y_field` |
| primitive | `join_episode_sets` | `left_key_field`, `right_key_field`, `left_status_field`, `right_status_field`, `left_time_field`, `right_time_field`, `distinct_entity_fields`, `same_entity_fields` |
| primitive | `team_compactness` | `frame_field` |
| primitive | `change_across_anchor` | `before_value_field`, `after_value_field`, `before_status_field`, `after_status_field` |
| primitive | `defensive_line_model` | `anchor_frame_field` |
| primitive | `multi_line_model` | `anchor_frame_field` |
| primitive | `relative_position_to_line` | `entity_id_field`, `entity_frame_field` |
| primitive | `lane_occupancy` | `frame_field` |
| relation | `support_arrival_relation` | `anchor_frame_field`, `required_anchor_status_field` |
| relation | `support_arrival_point_pair` | `anchor_frame_field`, `required_anchor_status_field` |
| relation | `pressure_on_carrier` | `frame_field`, `carrier_id_field` |
| relation | `defender_distance_candidate_set` | `anchor_frame_field`, `target_player_id_field`, `required_anchor_status_field` |
| relation | `team_press` | `frame_field`, `carrier_id_field` |
| relation | `local_number_relation` | `frame_field` |

Composition locations, grouped by operator (also exhaustive):

| Operator | Current field parameters |
| --- | --- |
| `project_onto_axis` | `start_point_field`, `end_point_field`, `reference_point_field`, `lane_start_point_field`, `lane_end_point_field`, `acting_team_field`, `required_source_status_field` |
| `delta_across_anchor` | `before_value_field`, `after_value_field`, `anchor_status_field`, `before_subject_field`, `after_subject_field`, `before_frame_field`, `after_frame_field`, `before_status_field`, `after_status_field` |
| `extremum_over_set` | `value_field`, `record_id_field`, `entity_id_field`, `frame_field`, `anchor_id_field`, `subject_id_field`, `status_field`, `coverage_status_field`, `tie_breaker_field`, `secondary_tie_breaker_field` |
| `window` | `anchor_frame_field`, `anchor_status_field`, `continuity_start_frame_field`, `continuity_end_frame_field`, `continuity_status_field`, `anchor_team_role_field`, `continuity_team_role_field` |
| `typed_join` | `left_anchor_id_field`, `right_anchor_id_field`, `left_frame_field`, `right_frame_field`, `left_entity_id_field`, `right_entity_id_field`, `left_start_frame_field`, `left_end_frame_field`, `right_start_frame_field`, `right_end_frame_field`, `left_team_role_field`, `right_team_role_field`, `left_status_field`, `right_status_field` |
| `aggregate_over` | `group_by_fields`, `status_field`, `team_role_field` |
| `rate` | `group_by_fields`, `numerator_status_field`, `denominator_status_field`, `subset_predicate_fields`, `removed_denominator_predicate_fields`, `team_role_field` |
| `sequence_pattern` | `stage_1_status_field`, `stage_2_status_field`, `stage_3_status_field`, `stage_1_frame_field`, `stage_2_frame_field`, `stage_3_frame_field`, `stage_1_end_frame_field`, `stage_2_end_frame_field`, `stage_3_end_frame_field`, `stage_1_team_role_field`, `stage_2_team_role_field`, `stage_3_team_role_field`, `stage_1_possession_id_field`, `stage_2_possession_id_field`, `stage_3_possession_id_field`, `stage_1_player_id_field`, `stage_2_player_id_field`, `stage_3_player_id_field`, `stage_2_minimum_numeric_field`, `team_role_field` |

Of the 126, **107** are singular references in the charter's five kinds and
will migrate in this packet: 41 frame, 31 entity, 5 point, 24 status, and 6
provenance/record-identity references. The remaining 19 are deliberately not
mis-typed: numeric/value/tie-break selectors, X/Y scalar components, grouping
or predicate field sets, and the legacy comma/equality mini-languages. They
remain visible debt but do not require enum expansion for the new
controller/region anchors governed by ADR 0018.

### Migration and compatibility

Migration is dual-read and typed-write:

- The 107 parameter definitions advertise `field_ref` plus their required
  kind. Their existing literal lists move to an explicitly legacy-only
  compatibility list; no new field name may be added there.
- New plans and new primitives author structured `field_ref` values. They are
  checked by kind and by the bound input's declared field names.
- Existing `enum` field values remain accepted only on migrated parameters.
  Existing enum defaults remain byte-identical. The binder preserves those
  values instead of silently rewriting committed plans, so legacy bound-plan
  serialization and hashes can remain stable.
- Runtime field extraction accepts either representation and resolves both to
  the same field name. Optional typed null resolves to the existing internal
  `none` sentinel; public serving/error shapes do not change.
- Normal policy enums retain their current exact validation. `allowed_values`
  keeps its original meaning for non-field enums.
- The semantic compiler uses the same compatibility predicate as the binder;
  it may read old plans but emits typed references for newly authored field
  values once their definitions are typed.

There is no registry mutation and no primitive behavior change in GEO-0b.

### Verification and STOP law

The oracle must prove both directions:

- a previously unseen but upstream-declared field name binds through a typed
  reference without editing any literal enum;
- a reference of the wrong kind, or to an undeclared field, fails binding;
- the same legacy enum plan still binds and executes with the same serialized
  bound value and plan hash.

Mutation standard: bypass the kind check and show the wrong-kind oracle fails;
restore it and show the oracle passes.

The GEO-0a STOP law applies unchanged. Fresh controls will compare the
certified R2-1, R2-2, R2-4, and GALLERY-2 surfaces against an untouched
`e30c70fd` clone. Any tactical value, status, count, classification, evidence
population, or certified plan/table/period hash delta that is not solely an
explicitly disclosed schema-artifact change fires STOP. Nothing will be
re-certified or rewritten to make the comparison pass.

## Implementation record

The design brief was committed first as 2c134992. Implementation landed in
8b32693b; generated authoring/parity artifacts and the committed SCP2
round-trip refresh landed in 35467af8. No registry YAML or certified tactical
table changed on the packet branch.

### Sealed-inventory correction

The design-time name heuristic said 107 of the 126 field parameters would
migrate. The exact owner/parameter map contains **110** singular references:

| Kind | Exact migrated count |
| --- | ---: |
| frame | 41 |
| entity | 34 |
| point | 5 |
| status | 24 |
| provenance | 6 |
| **total** | **110** |

The net correction is +3. The heuristic undercounted acting-team,
possession-identity, and team-role references while sweeping two
comma/equality mini-language selectors into its provisional entity count.
Those mini-languages remain excluded. The exact split is 44 of 50 catalog
parameters and 66 of 76 operator parameters; 16 value/grouping/mini-language
selectors remain unmigrated. The exact-inventory test locks all 110 owners.

### Runtime and compiler changes

- PayloadType.FIELD_REF, FieldReferenceKind, and FieldReference implement the
  five closed kinds with an open lower-snake-case field and typed null.
- Catalog and operator declarations migrate through exact owner/parameter
  maps. Exported signatures advertise field_ref, kind, and a legacy-only
  compatibility vocabulary.
- Binder and semantic compiler dual-read both spellings. Typed values must
  have the required kind; non-null fields must be declared by a bound input.
- The executor unwraps typed and legacy forms to the same field name. Typed
  null preserves the existing none sentinel.
- Compiler search typed-writes migrated selectors. Existing plans remain
  legacy-readable.
- Legacy defaults stay byte-identical. A reconstructed legacy operator
  signature preserves old plan hashes. The Q5 compatibility fixture remains
  exactly 618ce9961bc04d6d4fefb2e1d58f4a8ed24ae2bac0435c751cc141675f928d30
  / 7ff420d83a54a821f2ca117dbb7b0d348a95590e1062f0cb0be611773375b3c2.

The registry YAML remains unchanged, as designed. SCP-0 recognizes an exact
legacy Enum binding as the compatibility face of field_ref only when
allow_legacy_enum is true and its values equal legacy_allowed_values.
Projection parity canonicalizes that accepted face, preserving existing
waiver hashes without hiding the typed generated authoring contract.

Schema, TypeScript, catalog, knowledge pack, runtime manifest, SCP-0
projections/passports/lock, and reports were regenerated through committed
producers. SCP-0 is PASS with zero findings. The SCP2 round-trip typed-writes,
executes its novel composition with 13 results and zero evidence failures,
and now agrees with the coverage map on document hash
f902c33100671cb1e997e4fa50d5f89a7eee7f47704c22dbda65b7b8a27ab59f.
Older certified R1/R2 execution provenance remains unchanged and valid.

## Mutation evidence

The binder kind guard was temporarily bypassed. The wrong-kind oracle failed
because BindError was not raised. Restoring the guard made the same test pass;
a source grep confirmed no mutation remained. Direction tests also prove a
new upstream-declared controller_frame_id binds without enum expansion,
wrong-kind and undeclared fields fail, and typed null requires unit none.

## Certified-result STOP audit

Controls ran in external clone /private/tmp/priori-geo0b-controls.R1VcAD
against clone-local canonical data and the unchanged raw corpus.

| Certified surface | Fresh result | Disposition |
| --- | --- | --- |
| R2-1 aggregate | file SHA 68d8100793a3cf907a177a7b25c5a7625b03691fb4855850ec40833702c47a30; period 15ddf8d7e1c998a35428993dbf020dc876fc148a9ef92f0a80c395597d301945; PASS 145 / FAIL 2,615 / UNKNOWN 5,654 / population 8,414 | exact frontier match |
| R2-2 retention | file SHA 58e34c6ddc1971605d235c780c147783131ebad00400dfe8e3387a8fc48305cf; period 1a263f547ac10216bfbf7e764e69547c3a0227392568f62830ca69e7f95bd7d2; plan df155f08757cc9e5b136ac6752c0bb0765c2cad5fe1a4d98baa4338518e84f6a; 14 reconciliations true | exact frontier match |
| R2-4 sequence | period 3fb270eda29fc14f57746491881afacaee388f7799284ee9f6caf2bf74416afd; 28 records; population 2,811; PASS 1 / FAIL 0 / UNKNOWN 2,810 | exact tactical match; two schema hashes disclosed |
| GALLERY-2 pressing | plan 41d80fb5308a7e90ad633327e4422f11ef3c5c404d01f6012aa90e080317925c; table e40f1abc02d142eb96b644e12841e6ac5714b60c1f94817aecfbeda2d482e97e; 2,811 = 1,204 + 1,054 + 500 + 53 UNKNOWN | generator and independent check exact |

The first R2-2 diagnostic consumed the freshly regenerated R2-1 table and
therefore differed only in its embedded r2_1_table_hash. Repeating it with
the sealed R2-1 input reproduced the frontier file exactly.

R2-4's recursive table comparison found exactly two changes:
plan_hash and synthesized_sequence_rate_document_hash, both moving from
legacy-enum d8179a5a... to typed-write
a33882bfbd400657c3d178d78dd166801a602e9b06a804b957c7904075266966.
Every other field was identical. This is the brief's disclosed
schema-artifact exception: no value, status, count, population,
classification, evidence row, or period hash changed. **STOP does not fire.**

## Verification table

| Gate | Result |
| --- | --- |
| Direction and R1 operator suites | PASS — 135 tests in 132.640s |
| Binder kind-guard mutation | EXPECTED FAIL; restored oracle PASS |
| Typed compiler/SCP2 focused suite | PASS — 30 tests in 0.098s |
| SCP-0 artifact check | PASS — zero findings and drift |
| Validation-factory dirty-runtime diagnostic | EXPECTED FAIL before commit; PASS — 4 tests after commit |
| Fresh R2-1 / R2-2 / R2-4 controls | PASS as above |
| GALLERY-2 generation and independent check | PASS — exact 2,811 |
| Final canonical make test | PASS — 615 tests in 735.709s; attestation VERIFIED |
| compileall and git diff check | PASS |

## Deviations and environment notes

- Initial broad runs were invalid because the external clone lacked regular
  data files; symlinks also fail manifest path resolution. The authoritative
  run used APFS-cloned regular canonical files and the untouched raw root.
- A 602-test intermediate run had ten manifest errors plus the intentional
  dirty-runtime validation guard. Neither remained in the final run.
- R2-1 took about 40 minutes; R2-4 took 716.919 seconds. Both completed.
- The Gallery producer retained in packet history is absent from the current
  tree. The archived committed producer at
  /private/tmp/priori-geo0a-proof.hPnEjY was copied only into the disposable
  control clone, run against current code, then run with its own check. It is
  not added back to this branch.
- No push was attempted. All commits are in
  /private/tmp/priori-geo0b-executor.yxaF0J.
