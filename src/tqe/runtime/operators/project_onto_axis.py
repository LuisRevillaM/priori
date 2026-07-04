"""project_onto_axis composition operator.

R1-1 introduces this as the first real operator: per-record point-pair
vectors are projected onto a declared axis and emitted as witnessed scalar
channels. Missing vector evidence yields UNKNOWN records rather than silent
drops.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from tqe.runtime.ir import (
    Cardinality,
    CompositionOperatorSignature,
    EntityScope,
    MissingDataSemantics,
    OperatorInputDefinition,
    OperatorOutputDeclaration,
    ParameterDefinition,
    PayloadType,
    TemporalContainer,
    TypedValue,
    Unit,
    stable_hash,
)
from tqe.runtime.pass_bypass import attack_x_sign_for
from tqe.runtime.values import FrameSignal, RuntimeValue


AXIS_VALUES = ("goalward", "lateral", "toward_point", "along_lane_normal")
POINT_FIELD_VALUES = (
    "none",
    "release_ball_point",
    "reception_ball_point",
    "release_passer_point",
    "reception_receiver_point",
    "start_point",
    "end_point",
    "run_start_point",
    "run_end_point",
    "carry_start_point",
    "carry_end_point",
    "ball_point",
    "target_point",
    "reference_point",
    "screening_defender_point",
    "screening_projection_point",
    "source_open_point",
    "target_open_point",
    "source_close_point",
    "target_close_point",
)
STATUS_FIELD_VALUES = (
    "none",
    "controlled_pass_status",
    "carry_status",
    "off_ball_run_status",
    "support_arrival_status",
    "projection_status",
)
STATUS_VALUE_VALUES = ("PASS", "FAIL", "UNKNOWN")
EVIDENCE_FIELDS = [
    "axis_projection_status",
    "axis_projection_reason",
    "axis",
    "source_start_point_field",
    "source_end_point_field",
    "reference_point_field",
    "lane_start_point_field",
    "lane_end_point_field",
    "source_start_point",
    "source_end_point",
    "axis_unit_vector",
    "signed_projection_m",
    "angle_between_degrees",
    "source_anchor_id",
    "source_frame_id",
    "source_record_hash",
    "witness_source_node_id",
    "witness_source_output_name",
]


PROJECT_ONTO_AXIS_SIGNATURE = CompositionOperatorSignature(
    name="project_onto_axis",
    version="0.1.0",
    purpose=(
        "Project a source point-pair vector onto a declared axis, producing "
        "witnessed signed scalar and angle channels."
    ),
    inputs=[
        OperatorInputDefinition(
            name="source",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.BOOLEAN,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.POSSESSION,
        )
    ],
    outputs=[
        OperatorOutputDeclaration(
            name="axis_projection_records",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="axis_projection_status",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="signed_projection_m",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.NUMBER,
            cardinality=Cardinality.SINGLE,
            unit=Unit.METRE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="angle_between_degrees",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.NUMBER,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
    ],
    parameters=[
        ParameterDefinition(
            name="axis",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="goalward"),
            allowed_values=list(AXIS_VALUES),
            description="Projection axis.",
        ),
        ParameterDefinition(
            name="start_point_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="release_ball_point"),
            allowed_values=list(POINT_FIELD_VALUES),
            description="Source record point field used as vector start.",
        ),
        ParameterDefinition(
            name="end_point_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="reception_ball_point"),
            allowed_values=list(POINT_FIELD_VALUES),
            description="Source record point field used as vector end.",
        ),
        ParameterDefinition(
            name="reference_point_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            allowed_values=list(POINT_FIELD_VALUES),
            description="Reference point for toward_point axes, when record-backed.",
        ),
        ParameterDefinition(
            name="lane_start_point_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            allowed_values=list(POINT_FIELD_VALUES),
            description="Lane start point for along_lane_normal axes.",
        ),
        ParameterDefinition(
            name="lane_end_point_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            allowed_values=list(POINT_FIELD_VALUES),
            description="Lane end point for along_lane_normal axes.",
        ),
        ParameterDefinition(
            name="reference_x_m",
            payload_type=PayloadType.NUMBER,
            unit=Unit.METRE,
            required=False,
            default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.METRE, value=0.0),
            description="Fallback reference x coordinate for toward_point axes.",
        ),
        ParameterDefinition(
            name="reference_y_m",
            payload_type=PayloadType.NUMBER,
            unit=Unit.METRE,
            required=False,
            default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.METRE, value=0.0),
            description="Fallback reference y coordinate for toward_point axes.",
        ),
        ParameterDefinition(
            name="required_source_status_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            allowed_values=list(STATUS_FIELD_VALUES),
            description="Optional source status field that must equal required_source_status_value.",
        ),
        ParameterDefinition(
            name="required_source_status_value",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            allowed_values=list(STATUS_VALUE_VALUES),
            description="Required source status value when required_source_status_field is set.",
        ),
    ],
    coverage_propagation_rule_id="missing_vector_evidence_to_unknown",
    witness_rule_id="source_record_frame",
)


def execute_project_onto_axis(
    *,
    state: Any,
    node: Any,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> None:
    source = inputs.get("source")
    if source is None:
        raise RuntimeError(f"{node.node_id} requires source input")
    source_records = _runtime_records(source)
    source_ref = node.inputs["source"]
    axis = _parameter_enum(parameters, "axis", "goalward")
    start_field = _parameter_enum(parameters, "start_point_field", "release_ball_point")
    end_field = _parameter_enum(parameters, "end_point_field", "reception_ball_point")
    reference_field = _parameter_enum(parameters, "reference_point_field", "none")
    lane_start_field = _parameter_enum(parameters, "lane_start_point_field", "none")
    lane_end_field = _parameter_enum(parameters, "lane_end_point_field", "none")
    required_status_field = _parameter_enum(parameters, "required_source_status_field", "none")
    required_status_value = _parameter_enum(parameters, "required_source_status_value", "PASS")
    reference_coordinate = (
        _parameter_number(parameters, "reference_x_m", 0.0),
        _parameter_number(parameters, "reference_y_m", 0.0),
    )
    attack_x_sign = _attack_x_sign_for_state(state)

    records: list[dict[str, Any]] = []
    for index, source_record in enumerate(source_records):
        records.append(
            _projection_record(
                state=state,
                source_record=source_record,
                source_record_index=index,
                source_node_id=source_ref.source_node_id,
                source_output_name=source_ref.output_name,
                axis=axis,
                start_field=start_field,
                end_field=end_field,
                reference_field=reference_field,
                lane_start_field=lane_start_field,
                lane_end_field=lane_end_field,
                required_status_field=required_status_field,
                required_status_value=required_status_value,
                reference_coordinate=reference_coordinate,
                attack_x_sign=attack_x_sign,
            )
        )

    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if record["axis_projection_status"] == "UNKNOWN" else record["axis_projection_status"]
        for record in records
    ]
    signed_values = [record["signed_projection_m"] for record in records]
    angle_values = [record["angle_between_degrees"] for record in records]
    state.signals[node.node_id] = {
        "axis_projection_records": records,
        "axis_projection_records_records": records,
        "axis_projection_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        "axis_projection_status_records": records,
        "signed_projection_m": FrameSignal(
            frame_ids=frame_ids,
            values=signed_values,
            unknown_mask=[value is None for value in signed_values],
            unit=Unit.METRE,
            entity_scope=EntityScope.ANCHOR,
        ),
        "signed_projection_m_records": records,
        "angle_between_degrees": FrameSignal(
            frame_ids=frame_ids,
            values=angle_values,
            unknown_mask=[value is None for value in angle_values],
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        "angle_between_degrees_records": records,
    }


def _projection_record(
    *,
    state: Any,
    source_record: dict[str, Any],
    source_record_index: int,
    source_node_id: str,
    source_output_name: str,
    axis: str,
    start_field: str,
    end_field: str,
    reference_field: str,
    lane_start_field: str,
    lane_end_field: str,
    required_status_field: str,
    required_status_value: str,
    reference_coordinate: tuple[float, float],
    attack_x_sign: int | None,
) -> dict[str, Any]:
    anchor_frame_id = _anchor_frame_id(source_record)
    start_frame_id = _optional_int(source_record.get("start_frame_id")) or anchor_frame_id
    end_frame_id = _optional_int(source_record.get("end_frame_id")) or anchor_frame_id
    entity_refs = source_record.get("entity_refs")
    if not isinstance(entity_refs, list):
        entity_refs = []
    source_anchor_id = str(source_record.get("anchor_id") or "")
    anchor_id = source_anchor_id or (
        f"axis_projection:{state.match_id}:{state.period}:{anchor_frame_id}:{source_record_index}"
    )
    base = {
        "anchor_id": anchor_id,
        "match_id": str(source_record.get("match_id") or state.match_id),
        "period": str(source_record.get("period") or state.period),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "entity_refs": [str(item) for item in entity_refs],
        "axis": axis,
        "source_start_point_field": start_field,
        "source_end_point_field": end_field,
        "reference_point_field": reference_field,
        "lane_start_point_field": lane_start_field,
        "lane_end_point_field": lane_end_field,
        "source_anchor_id": source_anchor_id or None,
        "source_frame_id": anchor_frame_id,
        "source_record_index": source_record_index,
        "source_record_hash": stable_hash(source_record),
        "witness_source_node_id": source_node_id,
        "witness_source_output_name": source_output_name,
    }

    if required_status_field != "none" and str(source_record.get(required_status_field)) != required_status_value:
        return {
            **base,
            "axis_projection_status": "UNKNOWN",
            "axis_projection_reason": "source_status_not_required_value",
            "source_start_point": None,
            "source_end_point": None,
            "axis_unit_vector": None,
            "signed_projection_m": None,
            "angle_between_degrees": None,
        }

    start_point = _point_from_record(source_record, start_field)
    end_point = _point_from_record(source_record, end_field)
    if start_point is None or end_point is None:
        return {
            **base,
            "axis_projection_status": "UNKNOWN",
            "axis_projection_reason": "missing_vector_point",
            "source_start_point": _point_payload(start_point),
            "source_end_point": _point_payload(end_point),
            "axis_unit_vector": None,
            "signed_projection_m": None,
            "angle_between_degrees": None,
        }
    vector = (end_point[0] - start_point[0], end_point[1] - start_point[1])
    axis_vector, axis_reason = _axis_vector(
        state=state,
        record=source_record,
        axis=axis,
        start_point=start_point,
        reference_field=reference_field,
        lane_start_field=lane_start_field,
        lane_end_field=lane_end_field,
        reference_coordinate=reference_coordinate,
        attack_x_sign=attack_x_sign,
    )
    if axis_vector is None:
        return {
            **base,
            "axis_projection_status": "UNKNOWN",
            "axis_projection_reason": axis_reason,
            "source_start_point": _point_payload(start_point),
            "source_end_point": _point_payload(end_point),
            "axis_unit_vector": None,
            "signed_projection_m": None,
            "angle_between_degrees": None,
        }
    unit_axis = _unit_vector(axis_vector)
    if unit_axis is None or _vector_length(vector) == 0:
        return {
            **base,
            "axis_projection_status": "UNKNOWN",
            "axis_projection_reason": "zero_length_vector",
            "source_start_point": _point_payload(start_point),
            "source_end_point": _point_payload(end_point),
            "axis_unit_vector": _point_payload(unit_axis),
            "signed_projection_m": None,
            "angle_between_degrees": None,
        }
    signed_projection = vector[0] * unit_axis[0] + vector[1] * unit_axis[1]
    angle = _angle_between_degrees(vector, unit_axis)
    return {
        **base,
        "axis_projection_status": "PASS",
        "axis_projection_reason": "projection_observed",
        "source_start_point": _point_payload(start_point),
        "source_end_point": _point_payload(end_point),
        "axis_unit_vector": _point_payload(unit_axis),
        "signed_projection_m": round(float(signed_projection), 3),
        "angle_between_degrees": None if angle is None else round(float(angle), 3),
    }


def _axis_vector(
    *,
    state: Any,
    record: dict[str, Any],
    axis: str,
    start_point: tuple[float, float],
    reference_field: str,
    lane_start_field: str,
    lane_end_field: str,
    reference_coordinate: tuple[float, float],
    attack_x_sign: int | None,
) -> tuple[tuple[float, float] | None, str]:
    if axis == "goalward":
        record_direction = _attacking_direction_value(record.get("attacking_direction"))
        sign = record_direction if record_direction is not None else attack_x_sign
        if sign not in {-1, 1}:
            return None, "attacking_direction_missing"
        return (float(sign), 0.0), "axis_observed"
    if axis == "lateral":
        return (0.0, 1.0), "axis_observed"
    if axis == "toward_point":
        reference = _point_from_record(record, reference_field)
        if reference is None:
            reference = reference_coordinate
        return (reference[0] - start_point[0], reference[1] - start_point[1]), "axis_observed"
    if axis == "along_lane_normal":
        lane_start = _point_from_record(record, lane_start_field)
        lane_end = _point_from_record(record, lane_end_field)
        if lane_start is None or lane_end is None:
            return None, "lane_axis_point_missing"
        lane_vector = (lane_end[0] - lane_start[0], lane_end[1] - lane_start[1])
        return (-lane_vector[1], lane_vector[0]), "axis_observed"
    return None, "axis_unknown"


def _attack_x_sign_for_state(state: Any) -> int | None:
    orientation_path = Path(state.canonical_root) / "orientation.parquet"
    try:
        orientation = pd.read_parquet(orientation_path)
    except (OSError, ValueError, ImportError):
        return None
    return attack_x_sign_for(
        orientation,
        str(state.match_id),
        str(state.period),
        str(state.perspective_team_role),
    )


def _runtime_records(value: RuntimeValue) -> list[dict[str, Any]]:
    if value.records and all(isinstance(item, dict) for item in value.records):
        return value.records
    if isinstance(value.value, list) and all(isinstance(item, dict) for item in value.value):
        return value.value
    return []


def _point_from_record(record: dict[str, Any], field: str) -> tuple[float, float] | None:
    if field == "none":
        return None
    raw = record.get(field)
    parsed = _parse_point(raw)
    if parsed is not None:
        return parsed
    if field.endswith("_point"):
        prefix = field.removesuffix("_point")
        parsed = _parse_xy(record.get(f"{prefix}_x_m"), record.get(f"{prefix}_y_m"))
        if parsed is not None:
            return parsed
    return _parse_xy(record.get(f"{field}_x_m"), record.get(f"{field}_y_m"))


def _parse_point(raw: Any) -> tuple[float, float] | None:
    if isinstance(raw, dict):
        return _parse_xy(raw.get("x_m"), raw.get("y_m"))
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return _parse_xy(raw[0], raw[1])
    return None


def _parse_xy(x_value: Any, y_value: Any) -> tuple[float, float] | None:
    try:
        x_m = float(x_value)
        y_m = float(y_value)
    except (TypeError, ValueError):
        return None
    if math.isnan(x_m) or math.isnan(y_m):
        return None
    return x_m, y_m


def _point_payload(point: tuple[float, float] | None) -> dict[str, float] | None:
    if point is None:
        return None
    return {"x_m": round(float(point[0]), 3), "y_m": round(float(point[1]), 3)}


def _unit_vector(vector: tuple[float, float]) -> tuple[float, float] | None:
    length = _vector_length(vector)
    if length == 0:
        return None
    return vector[0] / length, vector[1] / length


def _vector_length(vector: tuple[float, float]) -> float:
    return math.hypot(vector[0], vector[1])


def _angle_between_degrees(vector: tuple[float, float], unit_axis: tuple[float, float]) -> float | None:
    unit_vector = _unit_vector(vector)
    if unit_vector is None:
        return None
    cosine = max(-1.0, min(1.0, unit_vector[0] * unit_axis[0] + unit_vector[1] * unit_axis[1]))
    return math.degrees(math.acos(cosine))


def _anchor_frame_id(record: dict[str, Any]) -> int:
    for field in ("anchor_frame_id", "controlled_reception_frame_id", "end_frame_id", "start_frame_id"):
        value = _optional_int(record.get(field))
        if value is not None:
            return value
    return 0


def _optional_int(value: Any) -> int | None:
    try:
        if value is None or bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parameter_enum(parameters: dict[str, TypedValue], name: str, default: str) -> str:
    value = parameters.get(name)
    return default if value is None else str(value.value)


def _parameter_number(parameters: dict[str, TypedValue], name: str, default: float) -> float:
    value = parameters.get(name)
    if value is None:
        return default
    return float(value.value)


def _attacking_direction_value(value: Any) -> int | None:
    if value in {-1, 1}:
        return int(value)
    text = str(value).strip().lower()
    if text in {"1", "+1", "positive_x", "right", "left_to_right"}:
        return 1
    if text in {"-1", "negative_x", "left", "right_to_left"}:
        return -1
    return None
