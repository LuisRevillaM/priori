# GEO-0b — typed field references report

Branch: `packet/geo-0b`

Frontier: `e30c70fd8028b51a9fd15ca47c735cb5c0c43ec7`

Executor clone: `/private/tmp/priori-geo0b-executor.yxaF0J` (outside the
repository tree)

Status: **DESIGN BRIEF SEALED BEFORE IMPLEMENTATION**

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

Pending. This section will be updated only after the design brief above is
committed as its own predecessor commit.
