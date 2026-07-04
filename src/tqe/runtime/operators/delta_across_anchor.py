"""delta_across_anchor composition operator.

R1-2 introduces this as the second real operator: declared before/after
scalar values are compared for the same anchor, producing a witnessed signed
delta plus rising/falling edge statuses. Missing before/after evidence yields
UNKNOWN records rather than silent drops.
"""

from __future__ import annotations

from typing import Any

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
from tqe.runtime.values import FrameSignal, RuntimeValue


STATUS_VALUE_VALUES = ("PASS", "FAIL", "UNKNOWN")
MISSING_EVIDENCE_POLICY_VALUES = ("unknown",)
VALUE_UNIT_VALUES = ("none", "metre", "second", "frame", "fraction", "hertz", "count")
EVIDENCE_FIELDS = [
    "delta_status",
    "delta_reason",
    "rising_edge_status",
    "rising_edge_reason",
    "falling_edge_status",
    "falling_edge_reason",
    "before_value_field",
    "after_value_field",
    "before_status_field",
    "after_status_field",
    "required_status_value",
    "before_status",
    "after_status",
    "before_value",
    "after_value",
    "signed_delta",
    "edge_threshold",
    "hysteresis_margin",
    "value_unit",
    "missing_evidence_policy",
    "source_anchor_id",
    "source_anchor_frame_id",
    "before_evaluation_frame_id",
    "after_evaluation_frame_id",
    "before_record_hash",
    "after_record_hash",
    "witness_anchor_node_id",
    "witness_anchor_output_name",
    "witness_before_node_id",
    "witness_before_output_name",
    "witness_after_node_id",
    "witness_after_output_name",
]


DELTA_ACROSS_ANCHOR_SIGNATURE = CompositionOperatorSignature(
    name="delta_across_anchor",
    version="0.1.0",
    purpose=(
        "Compare declared before/after scalar values for the same anchor, "
        "emitting witnessed signed delta and rising/falling edge statuses."
    ),
    inputs=[
        OperatorInputDefinition(
            name="anchors",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        OperatorInputDefinition(
            name="before_evaluations",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        OperatorInputDefinition(
            name="after_evaluations",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
    ],
    outputs=[
        OperatorOutputDeclaration(
            name="delta_records",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="delta_status",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="signed_delta",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.NUMBER,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="rising_edge_status",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="falling_edge_status",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
    ],
    parameters=[
        ParameterDefinition(
            name="before_value_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Before-record numeric evidence field to compare.",
        ),
        ParameterDefinition(
            name="after_value_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="After-record numeric evidence field to compare.",
        ),
        ParameterDefinition(
            name="before_status_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Before-record status field required for scalar validity, or none.",
        ),
        ParameterDefinition(
            name="after_status_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="After-record status field required for scalar validity, or none.",
        ),
        ParameterDefinition(
            name="required_status_value",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(STATUS_VALUE_VALUES),
            description="Required before/after status value when status fields are not none.",
        ),
        ParameterDefinition(
            name="edge_threshold",
            payload_type=PayloadType.NUMBER,
            required=True,
            description="Scalar threshold for rising/falling edge classification.",
        ),
        ParameterDefinition(
            name="hysteresis_margin",
            payload_type=PayloadType.NUMBER,
            required=True,
            description="Margin that the before value must clear to avoid threshold flicker.",
        ),
        ParameterDefinition(
            name="value_unit",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(VALUE_UNIT_VALUES),
            description="Declared unit for before/after/delta scalar values.",
        ),
        ParameterDefinition(
            name="missing_evidence_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="unknown"),
            allowed_values=list(MISSING_EVIDENCE_POLICY_VALUES),
            description="Policy for missing before/after records or scalar values.",
        ),
    ],
    coverage_propagation_rule_id="missing_delta_evidence_to_unknown",
    witness_rule_id="anchor_before_after_records",
)


def execute_delta_across_anchor(
    *,
    state: Any,
    node: Any,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> None:
    anchors = _runtime_records(inputs.get("anchors"))
    before_records = _records_by_anchor_id(_runtime_records(inputs.get("before_evaluations")))
    after_records = _records_by_anchor_id(_runtime_records(inputs.get("after_evaluations")))
    before_ref = node.inputs["before_evaluations"]
    after_ref = node.inputs["after_evaluations"]
    anchor_ref = node.inputs["anchors"]
    before_value_field = _parameter_enum(parameters, "before_value_field")
    after_value_field = _parameter_enum(parameters, "after_value_field")
    before_status_field = _parameter_enum(parameters, "before_status_field")
    after_status_field = _parameter_enum(parameters, "after_status_field")
    required_status_value = _parameter_enum(parameters, "required_status_value")
    edge_threshold = _parameter_number(parameters, "edge_threshold")
    hysteresis_margin = _parameter_number(parameters, "hysteresis_margin")
    value_unit = _parameter_enum(parameters, "value_unit")
    missing_evidence_policy = _parameter_enum(parameters, "missing_evidence_policy", "unknown")

    records = [
        _delta_record(
            state=state,
            anchor=anchor,
            before_record=before_records.get(str(anchor.get("anchor_id"))),
            after_record=after_records.get(str(anchor.get("anchor_id"))),
            before_value_field=before_value_field,
            after_value_field=after_value_field,
            before_status_field=before_status_field,
            after_status_field=after_status_field,
            required_status_value=required_status_value,
            edge_threshold=edge_threshold,
            hysteresis_margin=hysteresis_margin,
            value_unit=value_unit,
            missing_evidence_policy=missing_evidence_policy,
            anchor_node_id=anchor_ref.source_node_id,
            anchor_output_name=anchor_ref.output_name,
            before_node_id=before_ref.source_node_id,
            before_output_name=before_ref.output_name,
            after_node_id=after_ref.source_node_id,
            after_output_name=after_ref.output_name,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "delta_records": records,
        "delta_records_records": records,
        "delta_status": _status_signal(records, frame_ids, "delta_status"),
        "delta_status_records": records,
        "signed_delta": FrameSignal(
            frame_ids=frame_ids,
            values=[
                record["signed_delta"] if record["delta_status"] == "PASS" else None
                for record in records
            ],
            unknown_mask=[record["delta_status"] != "PASS" for record in records],
            unit=Unit.NONE,
            entity_scope=DELTA_ACROSS_ANCHOR_SIGNATURE.outputs[2].entity_scope,
        ),
        "signed_delta_records": records,
        "rising_edge_status": _status_signal(records, frame_ids, "rising_edge_status"),
        "rising_edge_status_records": records,
        "falling_edge_status": _status_signal(records, frame_ids, "falling_edge_status"),
        "falling_edge_status_records": records,
    }


def _delta_record(
    *,
    state: Any,
    anchor: dict[str, Any],
    before_record: dict[str, Any] | None,
    after_record: dict[str, Any] | None,
    before_value_field: str,
    after_value_field: str,
    before_status_field: str,
    after_status_field: str,
    required_status_value: str,
    edge_threshold: float,
    hysteresis_margin: float,
    value_unit: str,
    missing_evidence_policy: str,
    anchor_node_id: str,
    anchor_output_name: str,
    before_node_id: str,
    before_output_name: str,
    after_node_id: str,
    after_output_name: str,
) -> dict[str, Any] | None:
    anchor_frame_id = _optional_int(anchor.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    before_value = None if before_record is None else _optional_float(before_record.get(before_value_field))
    after_value = None if after_record is None else _optional_float(after_record.get(after_value_field))
    before_status = _status_value(before_record, before_status_field)
    after_status = _status_value(after_record, after_status_field)
    delta_status = "UNKNOWN"
    delta_reason = "delta_evidence_missing"
    if before_record is None or after_record is None:
        delta_reason = "before_or_after_record_missing"
    elif not _status_matches(before_status, before_status_field, required_status_value):
        delta_status = "UNKNOWN" if before_status is None else "FAIL"
        delta_reason = "before_required_status_not_met"
    elif not _status_matches(after_status, after_status_field, required_status_value):
        delta_status = "UNKNOWN" if after_status is None else "FAIL"
        delta_reason = "after_required_status_not_met"
    elif before_value is None or after_value is None:
        delta_reason = "delta_value_missing"
    else:
        delta_status = "PASS"
        delta_reason = "delta_observed"
    delta_value = None if before_value is None or after_value is None else after_value - before_value
    rising_status, rising_reason = _edge_status(
        edge_kind="rising",
        delta_status=delta_status,
        before_value=before_value,
        after_value=after_value,
        threshold=edge_threshold,
        hysteresis_margin=hysteresis_margin,
    )
    falling_status, falling_reason = _edge_status(
        edge_kind="falling",
        delta_status=delta_status,
        before_value=before_value,
        after_value=after_value,
        threshold=edge_threshold,
        hysteresis_margin=hysteresis_margin,
    )
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": _optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": _optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "delta_status": delta_status,
        "delta_reason": delta_reason,
        "rising_edge_status": rising_status,
        "rising_edge_reason": rising_reason,
        "falling_edge_status": falling_status,
        "falling_edge_reason": falling_reason,
        "before_value_field": before_value_field,
        "after_value_field": after_value_field,
        "before_status_field": before_status_field,
        "after_status_field": after_status_field,
        "required_status_value": required_status_value,
        "before_status": before_status,
        "after_status": after_status,
        "before_value": None if before_value is None else round(float(before_value), 3),
        "after_value": None if after_value is None else round(float(after_value), 3),
        "signed_delta": None if delta_value is None else round(float(delta_value), 3),
        "edge_threshold": edge_threshold,
        "hysteresis_margin": hysteresis_margin,
        "value_unit": value_unit,
        "missing_evidence_policy": missing_evidence_policy,
        "source_anchor_id": str(anchor.get("anchor_id")),
        "source_anchor_frame_id": anchor_frame_id,
        "before_evaluation_frame_id": _record_frame_id(before_record),
        "after_evaluation_frame_id": _record_frame_id(after_record),
        "before_record_hash": None if before_record is None else stable_hash(before_record),
        "after_record_hash": None if after_record is None else stable_hash(after_record),
        "witness_anchor_node_id": anchor_node_id,
        "witness_anchor_output_name": anchor_output_name,
        "witness_before_node_id": before_node_id,
        "witness_before_output_name": before_output_name,
        "witness_after_node_id": after_node_id,
        "witness_after_output_name": after_output_name,
    }


def _edge_status(
    *,
    edge_kind: str,
    delta_status: str,
    before_value: float | None,
    after_value: float | None,
    threshold: float,
    hysteresis_margin: float,
) -> tuple[str, str]:
    if delta_status == "UNKNOWN":
        return "UNKNOWN", "delta_unknown"
    if delta_status == "FAIL":
        return "FAIL", "delta_precondition_failed"
    if before_value is None or after_value is None:
        return "UNKNOWN", "delta_value_missing"
    if edge_kind == "rising":
        before_clear = before_value <= threshold - hysteresis_margin
        after_crossed = after_value >= threshold
        if before_clear and after_crossed:
            return "PASS", "rising_edge_observed"
        return "FAIL", "rising_edge_not_observed"
    before_clear = before_value >= threshold + hysteresis_margin
    after_crossed = after_value <= threshold
    if before_clear and after_crossed:
        return "PASS", "falling_edge_observed"
    return "FAIL", "falling_edge_not_observed"


def _status_signal(records: list[dict[str, Any]], frame_ids: list[int], field: str) -> FrameSignal:
    values = [None if record[field] == "UNKNOWN" else record[field] for record in records]
    return FrameSignal(
        frame_ids=frame_ids,
        values=values,
        unknown_mask=[value is None for value in values],
        unit=Unit.NONE,
        entity_scope=EntityScope.ANCHOR,
    )


def _runtime_records(value: RuntimeValue | None) -> list[dict[str, Any]]:
    if value is None:
        return []
    if value.records and all(isinstance(item, dict) for item in value.records):
        return value.records
    if isinstance(value.value, list) and all(isinstance(item, dict) for item in value.value):
        return value.value
    return []


def _records_by_anchor_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        anchor_id = record.get("anchor_id")
        if anchor_id is None:
            continue
        indexed.setdefault(str(anchor_id), record)
    return indexed


def _status_value(record: dict[str, Any] | None, field: str) -> str | None:
    if field == "none":
        return None
    if record is None:
        return None
    value = record.get(field)
    return None if value is None else str(value)


def _status_matches(value: str | None, field: str, required: str) -> bool:
    if field == "none":
        return True
    return value == required


def _record_frame_id(record: dict[str, Any] | None) -> int | None:
    if record is None:
        return None
    for key in (
        "anchor_frame_id",
        "frame_id",
        "line_evaluation_frame_id",
        "pressure_frame_id",
        "team_compactness_frame_id",
        "lane_evaluation_frame_id",
        "local_number_frame_id",
    ):
        value = _optional_int(record.get(key))
        if value is not None:
            return value
    return None


def _parameter_enum(parameters: dict[str, TypedValue], name: str, default: str = "") -> str:
    value = parameters.get(name)
    return default if value is None else str(value.value)


def _parameter_number(parameters: dict[str, TypedValue], name: str, default: float = 0.0) -> float:
    value = parameters.get(name)
    return default if value is None else float(value.value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
