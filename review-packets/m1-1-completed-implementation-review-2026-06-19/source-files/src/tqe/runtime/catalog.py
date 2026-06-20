"""Default M1.1 primitive, relation, and operator catalog."""

from __future__ import annotations

from tqe.runtime.ir import (
    CapabilityCatalog,
    Cardinality,
    CatalogEntry,
    CatalogOutput,
    ComplexityLimits,
    EntityScope,
    MissingDataSemantics,
    NodeKind,
    OperatorSignature,
    PayloadType,
    TemporalContainer,
    Unit,
)


def output(
    *,
    name: str,
    temporal_type: TemporalContainer,
    payload_type: PayloadType,
    cardinality: Cardinality,
    unit: Unit = Unit.NONE,
    entity_scope: EntityScope = EntityScope.NONE,
    evidence_fields: list[str] | None = None,
    missing_data_semantics: MissingDataSemantics = MissingDataSemantics.UNKNOWN,
) -> CatalogOutput:
    return CatalogOutput(
        name=name,
        temporal_type=temporal_type,
        payload_type=payload_type,
        cardinality=cardinality,
        unit=unit,
        entity_scope=entity_scope,
        missing_data_semantics=missing_data_semantics,
        evidence_fields=evidence_fields or [],
    )


def primitive(
    *,
    name: str,
    version: str,
    purpose: str,
    outputs: list[CatalogOutput],
    evidence_fields: list[str],
    limitations: list[str] | None = None,
    missing_data_semantics: MissingDataSemantics = MissingDataSemantics.UNKNOWN,
) -> CatalogEntry:
    return CatalogEntry(
        name=name,
        version=version,
        kind=NodeKind.PRIMITIVE,
        purpose=purpose,
        outputs=outputs,
        limitations=limitations or [],
        missing_data_semantics=missing_data_semantics,
        evidence_fields=evidence_fields,
    )


def relation(
    *,
    name: str,
    version: str,
    purpose: str,
    outputs: list[CatalogOutput],
    evidence_fields: list[str],
    limitations: list[str],
    missing_data_semantics: MissingDataSemantics = MissingDataSemantics.UNKNOWN,
) -> CatalogEntry:
    return CatalogEntry(
        name=name,
        version=version,
        kind=NodeKind.RELATION,
        purpose=purpose,
        outputs=outputs,
        limitations=limitations,
        missing_data_semantics=missing_data_semantics,
        evidence_fields=evidence_fields,
    )


def default_primitives() -> list[CatalogEntry]:
    return [
        primitive(
            name="possession_segment",
            version="0.1.0",
            purpose="Identify active-ball possession intervals for the perspective team.",
            outputs=[
                output(
                    name="episodes",
                    temporal_type=TemporalContainer.EPISODE_SET,
                    payload_type=PayloadType.BOOLEAN,
                    cardinality=Cardinality.COLLECTION,
                    entity_scope=EntityScope.POSSESSION,
                    evidence_fields=[
                        "possession_start_frame_id",
                        "possession_end_frame_id",
                        "possession_duration_seconds",
                    ],
                )
            ],
            evidence_fields=[
                "possession_start_frame_id",
                "possession_end_frame_id",
                "possession_duration_seconds",
            ],
        ),
        primitive(
            name="ball_lateral_fraction",
            version="0.1.0",
            purpose="Normalize ball distance from pitch centerline toward either touchline.",
            outputs=[
                output(
                    name="fraction",
                    temporal_type=TemporalContainer.FRAME_SIGNAL,
                    payload_type=PayloadType.NUMBER,
                    cardinality=Cardinality.SINGLE,
                    unit=Unit.FRACTION,
                    entity_scope=EntityScope.BALL,
                    evidence_fields=["wide_entry_y_m", "ball_side"],
                )
            ],
            evidence_fields=["wide_entry_y_m", "ball_side"],
            limitations=["Depends on canonical pitch coordinates and known pitch width."],
        ),
        primitive(
            name="wide_channel_dwell",
            version="0.1.0",
            purpose="Require ball to remain in a configured wide region long enough to avoid noise.",
            outputs=[
                output(
                    name="episodes",
                    temporal_type=TemporalContainer.EPISODE_SET,
                    payload_type=PayloadType.BOOLEAN,
                    cardinality=Cardinality.COLLECTION,
                    entity_scope=EntityScope.BALL,
                    evidence_fields=["wide_entry_frame_id", "wide_entry_y_m", "ball_side"],
                )
            ],
            evidence_fields=["wide_entry_frame_id", "wide_entry_y_m", "ball_side"],
        ),
        primitive(
            name="defensive_outfield_centroid",
            version="0.1.0",
            purpose="Measure defending outfield team centroid without goalkeeper bias.",
            outputs=[
                output(
                    name="centroid_y",
                    temporal_type=TemporalContainer.FRAME_SIGNAL,
                    payload_type=PayloadType.NUMBER,
                    cardinality=Cardinality.PER_TEAM,
                    unit=Unit.METRE,
                    entity_scope=EntityScope.TEAM,
                    evidence_fields=["baseline_defensive_centroid_y_m"],
                )
            ],
            evidence_fields=["baseline_defensive_centroid_y_m", "defending_team_id"],
            limitations=["Goalkeepers are excluded from the outfield centroid."],
        ),
        primitive(
            name="signed_lateral_shift",
            version="0.1.0",
            purpose="Measure defensive centroid movement toward the ball side.",
            outputs=[
                output(
                    name="signed_shift",
                    temporal_type=TemporalContainer.FRAME_SIGNAL,
                    payload_type=PayloadType.NUMBER,
                    cardinality=Cardinality.SINGLE,
                    unit=Unit.METRE,
                    entity_scope=EntityScope.TEAM,
                    evidence_fields=[
                        "baseline_start_frame_id",
                        "baseline_end_frame_id",
                        "anchor_frame_id",
                        "signed_shift_metres",
                        "block_shift_score",
                    ],
                )
            ],
            evidence_fields=[
                "baseline_start_frame_id",
                "baseline_end_frame_id",
                "anchor_frame_id",
                "signed_shift_metres",
                "block_shift_score",
            ],
        ),
        primitive(
            name="shift_persistence",
            version="0.1.0",
            purpose="Ensure the block shift persists rather than spiking for one frame.",
            outputs=[
                output(
                    name="episodes",
                    temporal_type=TemporalContainer.EPISODE_SET,
                    payload_type=PayloadType.BOOLEAN,
                    cardinality=Cardinality.COLLECTION,
                    entity_scope=EntityScope.TEAM,
                    evidence_fields=["persistent_shift"],
                )
            ],
            evidence_fields=["persistent_shift"],
        ),
        primitive(
            name="outcome_classification",
            version="0.1.0",
            purpose="Classify the post-anchor outcome under the frozen M1 predicates.",
            outputs=[
                output(
                    name="classification",
                    temporal_type=TemporalContainer.FRAME_SIGNAL,
                    payload_type=PayloadType.ENUM,
                    cardinality=Cardinality.SINGLE,
                    entity_scope=EntityScope.POSSESSION,
                    evidence_fields=["classification", "outcome_frame_id"],
                )
            ],
            evidence_fields=["classification", "outcome_frame_id"],
            limitations=["Does not infer intent, optimality, or missed opportunity."],
        ),
        primitive(
            name="relation_destination_entry_classification",
            version="0.1.0",
            purpose=(
                "Classify whether the ball later enters the destination region of a "
                "previously evaluated relation episode."
            ),
            outputs=[
                output(
                    name="classification",
                    temporal_type=TemporalContainer.FRAME_SIGNAL,
                    payload_type=PayloadType.ENUM,
                    cardinality=Cardinality.SINGLE,
                    entity_scope=EntityScope.RELATION,
                    evidence_fields=[
                        "classification",
                        "base_result_id",
                        "relation_id",
                        "destination_entry_frame_id",
                        "destination_region",
                        "destination_side",
                        "destination_lane",
                    ],
                )
            ],
            evidence_fields=[
                "classification",
                "base_result_id",
                "relation_id",
                "destination_entry_frame_id",
                "destination_region",
                "destination_side",
                "destination_lane",
            ],
            limitations=[
                "Requires an upstream relation episode set.",
                "No pass probability, optimality, decision-quality, intent, or missed-opportunity claim.",
            ],
        ),
        primitive(
            name="robust_team_width",
            version="0.1.0",
            purpose="Describe team structure with robust lateral spread.",
            outputs=[
                output(
                    name="width",
                    temporal_type=TemporalContainer.FRAME_SIGNAL,
                    payload_type=PayloadType.NUMBER,
                    cardinality=Cardinality.PER_TEAM,
                    unit=Unit.METRE,
                    entity_scope=EntityScope.TEAM,
                    evidence_fields=["team_width_m"],
                )
            ],
            evidence_fields=["team_width_m"],
        ),
        primitive(
            name="analysis_rate",
            version="0.1.0",
            purpose="Expose configured analysis cadence as a scalar for validation and provenance.",
            outputs=[
                output(
                    name="hz",
                    temporal_type=TemporalContainer.SCALAR,
                    payload_type=PayloadType.NUMBER,
                    cardinality=Cardinality.SINGLE,
                    unit=Unit.HERTZ,
                    entity_scope=EntityScope.MATCH,
                    evidence_fields=["analysis_rate_hz"],
                )
            ],
            evidence_fields=["analysis_rate_hz"],
            limitations=["Configuration value only; not an evaluated tactical predicate."],
            missing_data_semantics=MissingDataSemantics.NOT_APPLICABLE,
        ),
    ]


def default_relations() -> list[CatalogEntry]:
    return [
        relation(
            name="geometric_progressive_corridor",
            version="0.1.0",
            purpose=(
                "Represent a geometrically clear forward connection from the ball location "
                "to an attacking teammate over an interval."
            ),
            outputs=[
                output(
                    name="episodes",
                    temporal_type=TemporalContainer.RELATION_EPISODE_SET,
                    payload_type=PayloadType.RELATION_REF,
                    cardinality=Cardinality.COLLECTION,
                    entity_scope=EntityScope.RELATION,
                    evidence_fields=[
                        "relation_id",
                        "open_frame_id",
                        "open_confirm_frame_id",
                        "close_frame_id",
                        "duration_seconds",
                        "target_player_id",
                        "destination_side",
                        "destination_region",
                        "destination_lane",
                        "minimum_clearance_m",
                        "limiting_defender_id",
                        "source_open_point",
                        "target_open_point",
                        "source_close_point",
                        "target_close_point",
                    ],
                )
            ],
            evidence_fields=[
                "relation_id",
                "open_frame_id",
                "open_confirm_frame_id",
                "close_frame_id",
                "duration_seconds",
                "target_player_id",
                "destination_side",
                "destination_region",
                "destination_lane",
                "minimum_clearance_m",
                "limiting_defender_id",
                "source_open_point",
                "target_open_point",
                "source_close_point",
                "target_close_point",
            ],
            limitations=[
                "No pass probability.",
                "No optimality or decision-quality claim.",
                "No receiver body-orientation model.",
                "No offside model in V1 acceptance.",
            ],
        )
    ]


def default_operators() -> list[OperatorSignature]:
    return [
        OperatorSignature(
            name="gt",
            version="1.0.0",
            purpose="Compare a numeric signal to a strict lower numeric threshold.",
            input_temporal_types=[TemporalContainer.SCALAR, TemporalContainer.FRAME_SIGNAL],
            input_payload_types=[PayloadType.NUMBER],
            input_cardinalities=[
                Cardinality.SINGLE,
                Cardinality.PER_PLAYER,
                Cardinality.PER_TEAM,
            ],
            compare_payload_types=[PayloadType.NUMBER],
            compare_required=True,
            compare_unit_must_match=True,
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
        OperatorSignature(
            name="gte",
            version="1.0.0",
            purpose="Compare a numeric signal to a numeric threshold.",
            input_temporal_types=[TemporalContainer.SCALAR, TemporalContainer.FRAME_SIGNAL],
            input_payload_types=[PayloadType.NUMBER],
            input_cardinalities=[
                Cardinality.SINGLE,
                Cardinality.PER_PLAYER,
                Cardinality.PER_TEAM,
            ],
            compare_payload_types=[PayloadType.NUMBER],
            compare_required=True,
            compare_unit_must_match=True,
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
        OperatorSignature(
            name="lte",
            version="1.0.0",
            purpose="Compare a numeric signal to an upper numeric threshold.",
            input_temporal_types=[TemporalContainer.SCALAR, TemporalContainer.FRAME_SIGNAL],
            input_payload_types=[PayloadType.NUMBER],
            input_cardinalities=[
                Cardinality.SINGLE,
                Cardinality.PER_PLAYER,
                Cardinality.PER_TEAM,
            ],
            compare_payload_types=[PayloadType.NUMBER],
            compare_required=True,
            compare_unit_must_match=True,
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
        OperatorSignature(
            name="eq",
            version="1.0.0",
            purpose="Compare a signal to an equal typed value.",
            input_temporal_types=[
                TemporalContainer.SCALAR,
                TemporalContainer.FRAME_SIGNAL,
                TemporalContainer.EPISODE_SET,
            ],
            input_payload_types=[
                PayloadType.BOOLEAN,
                PayloadType.NUMBER,
                PayloadType.ENUM,
                PayloadType.ENTITY_REF,
                PayloadType.TEAM_REF,
                PayloadType.REGION_REF,
            ],
            input_cardinalities=[
                Cardinality.SINGLE,
                Cardinality.PER_PLAYER,
                Cardinality.PER_TEAM,
            ],
            compare_payload_types=[
                PayloadType.BOOLEAN,
                PayloadType.NUMBER,
                PayloadType.ENUM,
                PayloadType.ENTITY_REF,
                PayloadType.TEAM_REF,
                PayloadType.REGION_REF,
            ],
            compare_required=True,
            compare_unit_must_match=True,
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
        OperatorSignature(
            name="neq",
            version="1.0.0",
            purpose="Compare a signal to a non-equal typed value.",
            input_temporal_types=[
                TemporalContainer.SCALAR,
                TemporalContainer.FRAME_SIGNAL,
                TemporalContainer.EPISODE_SET,
            ],
            input_payload_types=[
                PayloadType.BOOLEAN,
                PayloadType.NUMBER,
                PayloadType.ENUM,
                PayloadType.ENTITY_REF,
                PayloadType.TEAM_REF,
                PayloadType.REGION_REF,
            ],
            input_cardinalities=[
                Cardinality.SINGLE,
                Cardinality.PER_PLAYER,
                Cardinality.PER_TEAM,
            ],
            compare_payload_types=[
                PayloadType.BOOLEAN,
                PayloadType.NUMBER,
                PayloadType.ENUM,
                PayloadType.ENTITY_REF,
                PayloadType.TEAM_REF,
                PayloadType.REGION_REF,
            ],
            compare_required=True,
            compare_unit_must_match=True,
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
        OperatorSignature(
            name="persists_for",
            version="1.0.0",
            purpose="Promote a boolean frame signal to intervals after minimum duration.",
            input_temporal_types=[TemporalContainer.FRAME_SIGNAL],
            input_payload_types=[PayloadType.BOOLEAN],
            input_cardinalities=[Cardinality.SINGLE, Cardinality.PER_PLAYER, Cardinality.PER_TEAM],
            duration_required=True,
            output_temporal_type=TemporalContainer.EPISODE_SET,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.COLLECTION,
            limitations=["UNKNOWN remains UNKNOWN; absence is not converted to FALSE."],
        ),
        OperatorSignature(
            name="exists",
            version="1.0.0",
            purpose="Test whether an episode or relation collection contains any episode.",
            input_temporal_types=[
                TemporalContainer.EPISODE_SET,
                TemporalContainer.RELATION_EPISODE_SET,
            ],
            input_payload_types=[PayloadType.BOOLEAN, PayloadType.RELATION_REF],
            input_cardinalities=[Cardinality.COLLECTION],
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
        OperatorSignature(
            name="count_at_least",
            version="1.0.0",
            purpose="Count a collection and compare to a count threshold.",
            input_temporal_types=[
                TemporalContainer.EPISODE_SET,
                TemporalContainer.RELATION_EPISODE_SET,
            ],
            input_payload_types=[PayloadType.ENTITY_SET, PayloadType.RELATION_REF, PayloadType.BOOLEAN],
            input_cardinalities=[Cardinality.COLLECTION],
            compare_payload_types=[PayloadType.NUMBER],
            compare_required=True,
            output_temporal_type=TemporalContainer.FRAME_SIGNAL,
            output_payload_type=PayloadType.BOOLEAN,
            output_cardinality=Cardinality.SINGLE,
        ),
    ]


def default_catalog() -> CapabilityCatalog:
    return CapabilityCatalog(
        primitives=default_primitives(),
        relations=default_relations(),
        operators=default_operators(),
        default_complexity_limits=ComplexityLimits(
            max_plan_nodes=40,
            max_nesting_depth=8,
            max_temporal_horizon_seconds=15.0,
            max_returned_moments=100,
            max_relations_per_anchor=1000,
            max_execution_cost=100000,
        ),
    )
