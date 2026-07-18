"""Canonical typed-field parameter contracts and legacy enum migration."""

from __future__ import annotations

from collections.abc import Iterable

from tqe.runtime.ir import (
    CatalogEntry,
    CompositionOperatorSignature,
    FieldReferenceKind,
    ParameterDefinition,
    PayloadType,
)


CatalogParameterKey = tuple[str, str]
OperatorParameterKey = tuple[str, str]


CATALOG_FIELD_REFERENCE_KINDS: dict[CatalogParameterKey, FieldReferenceKind] = {
    ("fragile_carrier_episode", "observation_frame_field"): FieldReferenceKind.FRAME,
    ("fragile_carrier_episode", "onset_carrier_id_field"): FieldReferenceKind.ENTITY,
    ("fragile_carrier_episode", "possession_id_field"): FieldReferenceKind.PROVENANCE,
    ("fragile_carrier_episode", "pressure_status_field"): FieldReferenceKind.STATUS,
    ("fragile_carrier_episode", "carrier_control_status_field"): FieldReferenceKind.STATUS,
    ("fragile_carrier_episode", "boundary_status_field"): FieldReferenceKind.STATUS,
    ("structured_zone", "frame_field"): FieldReferenceKind.FRAME,
    ("space_region_generation", "frame_field"): FieldReferenceKind.FRAME,
    ("outcome_window", "required_anchor_status_field"): FieldReferenceKind.STATUS,
    ("tracking_quality", "frame_field"): FieldReferenceKind.FRAME,
    ("pairwise_distance", "frame_field"): FieldReferenceKind.FRAME,
    ("pairwise_distance", "entity_a_field"): FieldReferenceKind.ENTITY,
    ("pairwise_distance", "entity_b_field"): FieldReferenceKind.ENTITY,
    ("marking", "frame_field"): FieldReferenceKind.FRAME,
    ("marking", "target_player_id_field"): FieldReferenceKind.ENTITY,
    ("cover_shadow", "frame_field"): FieldReferenceKind.FRAME,
    ("cover_shadow", "target_entity_field"): FieldReferenceKind.ENTITY,
    ("velocity", "frame_field"): FieldReferenceKind.FRAME,
    ("velocity", "entity_id_field"): FieldReferenceKind.ENTITY,
    ("acceleration", "frame_field"): FieldReferenceKind.FRAME,
    ("acceleration", "entity_id_field"): FieldReferenceKind.ENTITY,
    ("off_ball_run", "frame_field"): FieldReferenceKind.FRAME,
    ("time_to_arrival", "frame_field"): FieldReferenceKind.FRAME,
    ("time_to_arrival", "target_entity_field"): FieldReferenceKind.ENTITY,
    ("join_episode_sets", "left_key_field"): FieldReferenceKind.PROVENANCE,
    ("join_episode_sets", "right_key_field"): FieldReferenceKind.PROVENANCE,
    ("join_episode_sets", "left_status_field"): FieldReferenceKind.STATUS,
    ("join_episode_sets", "right_status_field"): FieldReferenceKind.STATUS,
    ("join_episode_sets", "left_time_field"): FieldReferenceKind.FRAME,
    ("join_episode_sets", "right_time_field"): FieldReferenceKind.FRAME,
    ("team_compactness", "frame_field"): FieldReferenceKind.FRAME,
    ("change_across_anchor", "before_status_field"): FieldReferenceKind.STATUS,
    ("change_across_anchor", "after_status_field"): FieldReferenceKind.STATUS,
    ("defensive_line_model", "anchor_frame_field"): FieldReferenceKind.FRAME,
    ("multi_line_model", "anchor_frame_field"): FieldReferenceKind.FRAME,
    ("relative_position_to_line", "entity_id_field"): FieldReferenceKind.ENTITY,
    ("relative_position_to_line", "entity_frame_field"): FieldReferenceKind.FRAME,
    ("lane_occupancy", "frame_field"): FieldReferenceKind.FRAME,
    ("support_arrival_relation", "anchor_frame_field"): FieldReferenceKind.FRAME,
    ("support_arrival_relation", "required_anchor_status_field"): FieldReferenceKind.STATUS,
    ("support_arrival_point_pair", "anchor_frame_field"): FieldReferenceKind.FRAME,
    ("support_arrival_point_pair", "required_anchor_status_field"): FieldReferenceKind.STATUS,
    ("pressure_on_carrier", "frame_field"): FieldReferenceKind.FRAME,
    ("pressure_on_carrier", "carrier_id_field"): FieldReferenceKind.ENTITY,
    ("defender_distance_candidate_set", "anchor_frame_field"): FieldReferenceKind.FRAME,
    ("defender_distance_candidate_set", "target_player_id_field"): FieldReferenceKind.ENTITY,
    ("defender_distance_candidate_set", "required_anchor_status_field"): FieldReferenceKind.STATUS,
    ("team_press", "frame_field"): FieldReferenceKind.FRAME,
    ("team_press", "carrier_id_field"): FieldReferenceKind.ENTITY,
    ("local_number_relation", "frame_field"): FieldReferenceKind.FRAME,
}


OPERATOR_FIELD_REFERENCE_KINDS: dict[OperatorParameterKey, FieldReferenceKind] = {
    ("project_onto_axis", "start_point_field"): FieldReferenceKind.POINT,
    ("project_onto_axis", "end_point_field"): FieldReferenceKind.POINT,
    ("project_onto_axis", "reference_point_field"): FieldReferenceKind.POINT,
    ("project_onto_axis", "lane_start_point_field"): FieldReferenceKind.POINT,
    ("project_onto_axis", "lane_end_point_field"): FieldReferenceKind.POINT,
    ("project_onto_axis", "acting_team_field"): FieldReferenceKind.ENTITY,
    ("project_onto_axis", "required_source_status_field"): FieldReferenceKind.STATUS,
    ("delta_across_anchor", "anchor_status_field"): FieldReferenceKind.STATUS,
    ("delta_across_anchor", "before_subject_field"): FieldReferenceKind.ENTITY,
    ("delta_across_anchor", "after_subject_field"): FieldReferenceKind.ENTITY,
    ("delta_across_anchor", "before_frame_field"): FieldReferenceKind.FRAME,
    ("delta_across_anchor", "after_frame_field"): FieldReferenceKind.FRAME,
    ("delta_across_anchor", "before_status_field"): FieldReferenceKind.STATUS,
    ("delta_across_anchor", "after_status_field"): FieldReferenceKind.STATUS,
    ("extremum_over_set", "record_id_field"): FieldReferenceKind.PROVENANCE,
    ("extremum_over_set", "entity_id_field"): FieldReferenceKind.ENTITY,
    ("extremum_over_set", "frame_field"): FieldReferenceKind.FRAME,
    ("extremum_over_set", "anchor_id_field"): FieldReferenceKind.PROVENANCE,
    ("extremum_over_set", "subject_id_field"): FieldReferenceKind.ENTITY,
    ("extremum_over_set", "status_field"): FieldReferenceKind.STATUS,
    ("extremum_over_set", "coverage_status_field"): FieldReferenceKind.STATUS,
    ("window", "anchor_frame_field"): FieldReferenceKind.FRAME,
    ("window", "anchor_status_field"): FieldReferenceKind.STATUS,
    ("window", "continuity_start_frame_field"): FieldReferenceKind.FRAME,
    ("window", "continuity_end_frame_field"): FieldReferenceKind.FRAME,
    ("window", "continuity_status_field"): FieldReferenceKind.STATUS,
    ("window", "anchor_team_role_field"): FieldReferenceKind.ENTITY,
    ("window", "continuity_team_role_field"): FieldReferenceKind.ENTITY,
    ("typed_join", "left_anchor_id_field"): FieldReferenceKind.PROVENANCE,
    ("typed_join", "right_anchor_id_field"): FieldReferenceKind.PROVENANCE,
    ("typed_join", "left_frame_field"): FieldReferenceKind.FRAME,
    ("typed_join", "right_frame_field"): FieldReferenceKind.FRAME,
    ("typed_join", "left_entity_id_field"): FieldReferenceKind.ENTITY,
    ("typed_join", "right_entity_id_field"): FieldReferenceKind.ENTITY,
    ("typed_join", "left_start_frame_field"): FieldReferenceKind.FRAME,
    ("typed_join", "left_end_frame_field"): FieldReferenceKind.FRAME,
    ("typed_join", "right_start_frame_field"): FieldReferenceKind.FRAME,
    ("typed_join", "right_end_frame_field"): FieldReferenceKind.FRAME,
    ("typed_join", "left_team_role_field"): FieldReferenceKind.ENTITY,
    ("typed_join", "right_team_role_field"): FieldReferenceKind.ENTITY,
    ("typed_join", "left_status_field"): FieldReferenceKind.STATUS,
    ("typed_join", "right_status_field"): FieldReferenceKind.STATUS,
    ("aggregate_over", "status_field"): FieldReferenceKind.STATUS,
    ("aggregate_over", "team_role_field"): FieldReferenceKind.ENTITY,
    ("rate", "numerator_status_field"): FieldReferenceKind.STATUS,
    ("rate", "denominator_status_field"): FieldReferenceKind.STATUS,
    ("rate", "team_role_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_1_status_field"): FieldReferenceKind.STATUS,
    ("sequence_pattern", "stage_2_status_field"): FieldReferenceKind.STATUS,
    ("sequence_pattern", "stage_3_status_field"): FieldReferenceKind.STATUS,
    ("sequence_pattern", "stage_1_frame_field"): FieldReferenceKind.FRAME,
    ("sequence_pattern", "stage_2_frame_field"): FieldReferenceKind.FRAME,
    ("sequence_pattern", "stage_3_frame_field"): FieldReferenceKind.FRAME,
    ("sequence_pattern", "stage_1_end_frame_field"): FieldReferenceKind.FRAME,
    ("sequence_pattern", "stage_2_end_frame_field"): FieldReferenceKind.FRAME,
    ("sequence_pattern", "stage_3_end_frame_field"): FieldReferenceKind.FRAME,
    ("sequence_pattern", "stage_1_team_role_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_2_team_role_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_3_team_role_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_1_possession_id_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_2_possession_id_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_3_possession_id_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_1_player_id_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_2_player_id_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "stage_3_player_id_field"): FieldReferenceKind.ENTITY,
    ("sequence_pattern", "team_role_field"): FieldReferenceKind.ENTITY,
}


def migrate_catalog_field_references(entries: Iterable[CatalogEntry]) -> list[CatalogEntry]:
    migrated: list[CatalogEntry] = []
    for entry in entries:
        parameters = [
            _migrate_parameter(
                parameter,
                CATALOG_FIELD_REFERENCE_KINDS.get((entry.name, parameter.name)),
            )
            for parameter in entry.parameters
        ]
        migrated.append(entry.model_copy(update={"parameters": parameters}))
    return migrated


def migrate_operator_field_references(
    signature: CompositionOperatorSignature,
) -> CompositionOperatorSignature:
    parameters = [
        _migrate_parameter(
            parameter,
            OPERATOR_FIELD_REFERENCE_KINDS.get((signature.name, parameter.name)),
        )
        for parameter in signature.parameters
    ]
    return signature.model_copy(update={"parameters": parameters})


def legacy_operator_signature(
    signature: CompositionOperatorSignature,
) -> CompositionOperatorSignature:
    parameters: list[ParameterDefinition] = []
    for parameter in signature.parameters:
        if parameter.payload_type != PayloadType.FIELD_REF:
            parameters.append(parameter)
            continue
        payload = parameter.model_dump(mode="python")
        payload.update(
            payload_type=PayloadType.ENUM,
            allowed_values=parameter.legacy_allowed_values,
            field_reference_kind=None,
            allow_legacy_enum=None,
            legacy_allowed_values=None,
        )
        parameters.append(ParameterDefinition.model_validate(payload))
    return signature.model_copy(update={"parameters": parameters})


def _migrate_parameter(
    parameter: ParameterDefinition,
    kind: FieldReferenceKind | None,
) -> ParameterDefinition:
    if kind is None:
        return parameter
    if parameter.payload_type != PayloadType.ENUM:
        raise RuntimeError(
            f"typed field migration expected enum parameter {parameter.name}, "
            f"got {parameter.payload_type.value}"
        )
    payload = parameter.model_dump(mode="python")
    payload.update(
        payload_type=PayloadType.FIELD_REF,
        allowed_values=None,
        field_reference_kind=kind,
        allow_legacy_enum=True,
        legacy_allowed_values=parameter.allowed_values,
    )
    return ParameterDefinition.model_validate(payload)
