"""extremum_over_set composition operator.

R1-3 introduces generic, witnessed selection over per-anchor candidate
records. It emits one selected element per anchor for argmin/argmax/top-k
queries, and turns incomplete set coverage into UNKNOWN whenever the missing
members could change the answer.
"""

from __future__ import annotations

import math
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
SELECTION_MODE_VALUES = ("argmin", "argmax")
COVERAGE_POLICY_VALUES = ("unknown_if_incomplete_could_change_answer",)
VALUE_BOUND_KIND_VALUES = ("none", "lower", "upper")
MISSING_EVIDENCE_POLICY_VALUES = ("unknown",)
EVIDENCE_FIELDS = [
    "extremum_selection_status",
    "extremum_selection_reason",
    "selection_mode",
    "top_k",
    "selected_rank",
    "value_field",
    "value_unit",
    "selected_value",
    "record_id_field",
    "selected_record_id",
    "entity_id_field",
    "selected_entity_id",
    "frame_field",
    "selected_frame_id",
    "subject_id_field",
    "subject_id",
    "anchor_id_field",
    "source_anchor_id",
    "status_field",
    "required_status_value",
    "coverage_status_field",
    "coverage_status",
    "coverage_policy",
    "value_bound_kind",
    "value_bound",
    "valid_candidate_count",
    "unknown_candidate_count",
    "excluded_candidate_count",
    "candidate_count",
    "tie_breaker_field",
    "secondary_tie_breaker_field",
    "selected_tie_breaker_value",
    "selected_secondary_tie_breaker_value",
    "selected_source_record_hash",
    "selected_source_record_index",
    "witness_source_node_id",
    "witness_source_output_name",
    "missing_evidence_policy",
]


EXTREMUM_OVER_SET_SIGNATURE = CompositionOperatorSignature(
    name="extremum_over_set",
    version="0.1.0",
    purpose=(
        "Select witnessed argmin/argmax/top-k elements from declared per-anchor "
        "candidate records under explicit coverage and tie-break rules."
    ),
    inputs=[
        OperatorInputDefinition(
            name="candidates",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        )
    ],
    outputs=[
        OperatorOutputDeclaration(
            name="extremum_selection_records",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="extremum_selection_status",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="selected_value",
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
            name="selection_mode",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(SELECTION_MODE_VALUES),
            description="Extremum criterion applied to value_field.",
        ),
        ParameterDefinition(
            name="top_k",
            payload_type=PayloadType.NUMBER,
            unit=Unit.COUNT,
            required=False,
            default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.COUNT, value=1),
            description="Number of ranked candidates to emit. k larger than the valid set is UNKNOWN.",
        ),
        ParameterDefinition(
            name="value_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Candidate-record scalar field used for selection.",
        ),
        ParameterDefinition(
            name="value_unit",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            allowed_values=["none", "metre", "second", "frame", "fraction", "hertz", "count"],
            description="Declared unit of value_field for evidence only.",
        ),
        ParameterDefinition(
            name="record_id_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Candidate-record field containing the record-level witness id.",
        ),
        ParameterDefinition(
            name="entity_id_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Candidate-record field containing the selected entity witness id.",
        ),
        ParameterDefinition(
            name="frame_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Candidate-record field containing the selected-frame witness.",
        ),
        ParameterDefinition(
            name="anchor_id_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="anchor_id"),
            description="Candidate-record field grouping candidates by source anchor.",
        ),
        ParameterDefinition(
            name="subject_id_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Optional candidate-record field naming the subject whose set is selected over.",
        ),
        ParameterDefinition(
            name="status_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Optional candidate-record status field that must equal required_status_value.",
        ),
        ParameterDefinition(
            name="required_status_value",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            allowed_values=list(STATUS_VALUE_VALUES),
            description="Required candidate status value when status_field is not none.",
        ),
        ParameterDefinition(
            name="coverage_status_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Optional field indicating set-membership coverage for each candidate group.",
        ),
        ParameterDefinition(
            name="coverage_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="unknown_if_incomplete_could_change_answer"),
            allowed_values=list(COVERAGE_POLICY_VALUES),
            description="Policy for incomplete candidate-set coverage.",
        ),
        ParameterDefinition(
            name="value_bound_kind",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            allowed_values=list(VALUE_BOUND_KIND_VALUES),
            description="Declared bound kind used to decide whether missing candidates could change the answer.",
        ),
        ParameterDefinition(
            name="value_bound",
            payload_type=PayloadType.NUMBER,
            required=False,
            default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.NONE, value=0.0),
            description="Declared lower/upper bound for value_field when value_bound_kind is not none.",
        ),
        ParameterDefinition(
            name="tie_breaker_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Primary deterministic tie-breaker field.",
        ),
        ParameterDefinition(
            name="secondary_tie_breaker_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Optional secondary deterministic tie-breaker field.",
        ),
        ParameterDefinition(
            name="missing_evidence_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="unknown"),
            allowed_values=list(MISSING_EVIDENCE_POLICY_VALUES),
            description="Policy for missing selected value/entity/frame evidence.",
        ),
    ],
    coverage_propagation_rule_id="incomplete_set_coverage_could_change_answer_to_unknown",
    witness_rule_id="selected_candidate_record_entity_frame",
    limitations=[
        "Selection is over declared candidate records only; it does not create candidate sets.",
        "Incomplete candidate coverage is UNKNOWN unless a declared field bound proves the missing member could not change the answer.",
        "Ties are resolved only by declared record fields and a final stable record hash.",
    ],
)


def execute_extremum_over_set(
    *,
    state: Any,
    node: Any,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> None:
    candidate_value = inputs.get("candidates")
    if candidate_value is None:
        raise RuntimeError(f"{node.node_id} requires candidates input")
    candidates = _runtime_records(candidate_value)
    candidate_ref = node.inputs["candidates"]
    selection_mode = _parameter_enum(parameters, "selection_mode")
    top_k = max(1, int(_parameter_number(parameters, "top_k", 1.0)))
    value_field = _parameter_enum(parameters, "value_field")
    value_unit = _parameter_enum(parameters, "value_unit", "none")
    record_id_field = _parameter_enum(parameters, "record_id_field")
    entity_id_field = _parameter_enum(parameters, "entity_id_field")
    frame_field = _parameter_enum(parameters, "frame_field")
    anchor_id_field = _parameter_enum(parameters, "anchor_id_field", "anchor_id")
    subject_id_field = _parameter_enum(parameters, "subject_id_field", "none")
    status_field = _parameter_enum(parameters, "status_field", "none")
    required_status_value = _parameter_enum(parameters, "required_status_value", "PASS")
    coverage_status_field = _parameter_enum(parameters, "coverage_status_field", "none")
    coverage_policy = _parameter_enum(
        parameters,
        "coverage_policy",
        "unknown_if_incomplete_could_change_answer",
    )
    value_bound_kind = _parameter_enum(parameters, "value_bound_kind", "none")
    value_bound = _parameter_number(parameters, "value_bound", 0.0)
    tie_breaker_field = _parameter_enum(parameters, "tie_breaker_field")
    secondary_tie_breaker_field = _parameter_enum(parameters, "secondary_tie_breaker_field", "none")
    missing_evidence_policy = _parameter_enum(parameters, "missing_evidence_policy", "unknown")

    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, record in enumerate(candidates):
        if not isinstance(record, dict):
            continue
        anchor_id = record.get(anchor_id_field)
        if anchor_id is None:
            anchor_id = record.get("anchor_id")
        if anchor_id is None:
            continue
        grouped.setdefault(str(anchor_id), []).append((index, record))

    records: list[dict[str, Any]] = []
    for source_anchor_id in sorted(grouped):
        records.extend(
            _selection_records_for_anchor(
                state=state,
                indexed_records=grouped[source_anchor_id],
                source_anchor_id=source_anchor_id,
                source_node_id=candidate_ref.source_node_id,
                source_output_name=candidate_ref.output_name,
                selection_mode=selection_mode,
                top_k=top_k,
                value_field=value_field,
                value_unit=value_unit,
                record_id_field=record_id_field,
                entity_id_field=entity_id_field,
                frame_field=frame_field,
                anchor_id_field=anchor_id_field,
                subject_id_field=subject_id_field,
                status_field=status_field,
                required_status_value=required_status_value,
                coverage_status_field=coverage_status_field,
                coverage_policy=coverage_policy,
                value_bound_kind=value_bound_kind,
                value_bound=value_bound,
                tie_breaker_field=tie_breaker_field,
                secondary_tie_breaker_field=secondary_tie_breaker_field,
                missing_evidence_policy=missing_evidence_policy,
            )
        )

    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if record["extremum_selection_status"] == "UNKNOWN" else record["extremum_selection_status"]
        for record in records
    ]
    selected_values = [
        record["selected_value"] if record["extremum_selection_status"] == "PASS" else None
        for record in records
    ]
    state.signals[node.node_id] = {
        "extremum_selection_records": records,
        "extremum_selection_records_records": records,
        "extremum_selection_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        "extremum_selection_status_records": records,
        "selected_value": FrameSignal(
            frame_ids=frame_ids,
            values=selected_values,
            unknown_mask=[value is None for value in selected_values],
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        "selected_value_records": records,
    }


def _selection_records_for_anchor(
    *,
    state: Any,
    indexed_records: list[tuple[int, dict[str, Any]]],
    source_anchor_id: str,
    source_node_id: str,
    source_output_name: str,
    selection_mode: str,
    top_k: int,
    value_field: str,
    value_unit: str,
    record_id_field: str,
    entity_id_field: str,
    frame_field: str,
    anchor_id_field: str,
    subject_id_field: str,
    status_field: str,
    required_status_value: str,
    coverage_status_field: str,
    coverage_policy: str,
    value_bound_kind: str,
    value_bound: float,
    tie_breaker_field: str,
    secondary_tie_breaker_field: str,
    missing_evidence_policy: str,
) -> list[dict[str, Any]]:
    first = indexed_records[0][1]
    anchor_frame_id = _record_frame_id(first, "anchor_frame_id") or _record_frame_id(first, frame_field) or 0
    subject_id = _field_value(first, subject_id_field)
    base = _base_record(
        state=state,
        first_record=first,
        source_anchor_id=source_anchor_id,
        anchor_frame_id=anchor_frame_id,
        selection_mode=selection_mode,
        top_k=top_k,
        value_field=value_field,
        value_unit=value_unit,
        record_id_field=record_id_field,
        entity_id_field=entity_id_field,
        frame_field=frame_field,
        anchor_id_field=anchor_id_field,
        subject_id_field=subject_id_field,
        subject_id=subject_id,
        status_field=status_field,
        required_status_value=required_status_value,
        coverage_status_field=coverage_status_field,
        coverage_policy=coverage_policy,
        value_bound_kind=value_bound_kind,
        value_bound=value_bound,
        tie_breaker_field=tie_breaker_field,
        secondary_tie_breaker_field=secondary_tie_breaker_field,
        source_node_id=source_node_id,
        source_output_name=source_output_name,
        missing_evidence_policy=missing_evidence_policy,
        indexed_records=indexed_records,
    )

    valid: list[tuple[int, dict[str, Any], float]] = []
    unknown_count = 0
    excluded_count = 0
    incomplete_coverage = False
    coverage_values: list[str] = []
    for source_index, record in indexed_records:
        status = _status_value(record, status_field)
        if status_field != "none" and status != required_status_value:
            if status is None or status == "UNKNOWN":
                unknown_count += 1
            else:
                excluded_count += 1
            continue
        coverage_status = _status_value(record, coverage_status_field)
        if coverage_status is not None:
            coverage_values.append(coverage_status)
            if coverage_status in {"UNKNOWN", "INCOMPLETE"}:
                incomplete_coverage = True
        value = _optional_float(record.get(value_field))
        entity_id = _field_value(record, entity_id_field)
        frame_id = _record_frame_id(record, frame_field)
        record_id = _field_value(record, record_id_field)
        if value is None or entity_id is None or frame_id is None or record_id is None:
            unknown_count += 1
            continue
        valid.append((source_index, record, value))

    valid_count = len(valid)
    base = {
        **base,
        "coverage_status": _coverage_status(coverage_values, incomplete_coverage),
        "valid_candidate_count": valid_count,
        "unknown_candidate_count": unknown_count,
        "excluded_candidate_count": excluded_count,
        "candidate_count": len(indexed_records),
    }
    if not valid:
        return [
            {
                **base,
                "extremum_selection_status": "UNKNOWN",
                "extremum_selection_reason": "no_valid_candidates",
                "selected_rank": None,
                "selected_value": None,
                "selected_record_id": None,
                "selected_entity_id": None,
                "selected_frame_id": None,
                "selected_tie_breaker_value": None,
                "selected_secondary_tie_breaker_value": None,
                "selected_source_record_hash": None,
                "selected_source_record_index": None,
            }
        ]
    ranked = _ranked_candidates(
        valid,
        selection_mode=selection_mode,
        tie_breaker_field=tie_breaker_field,
        secondary_tie_breaker_field=secondary_tie_breaker_field,
    )
    coverage_decision_index = min(top_k, valid_count) - 1
    coverage_decision_value = ranked[coverage_decision_index][2]
    selected_status, selected_reason = _coverage_decision(
        selected_value=coverage_decision_value,
        selection_mode=selection_mode,
        top_k=top_k,
        valid_count=valid_count,
        unknown_count=unknown_count,
        incomplete_coverage=incomplete_coverage,
        coverage_policy=coverage_policy,
        value_bound_kind=value_bound_kind,
        value_bound=value_bound,
    )
    if selected_status == "UNKNOWN":
        return [
            {
                **base,
                "extremum_selection_status": "UNKNOWN",
                "extremum_selection_reason": selected_reason,
                "selected_rank": None,
                "selected_value": None,
                "selected_record_id": None,
                "selected_entity_id": None,
                "selected_frame_id": None,
                "selected_tie_breaker_value": None,
                "selected_secondary_tie_breaker_value": None,
                "selected_source_record_hash": None,
                "selected_source_record_index": None,
            }
        ]
    selections: list[dict[str, Any]] = []
    for rank, (source_index, record, value) in enumerate(ranked[:top_k], start=1):
        selected_frame_id = _record_frame_id(record, frame_field)
        anchor_frame = selected_frame_id or anchor_frame_id
        entity_refs = _entity_refs(record, entity_id_field)
        start_frame = _record_frame_id(record, "start_frame_id") or anchor_frame
        end_frame = _record_frame_id(record, "end_frame_id") or anchor_frame
        selections.append(
            {
                **base,
                "anchor_id": _canonical_anchor_id(
                    match_id=str(record.get("match_id") or state.match_id),
                    period=str(record.get("period") or state.period),
                    anchor_frame_id=anchor_frame,
                    start_frame_id=start_frame,
                    end_frame_id=end_frame,
                    entity_refs=entity_refs,
                ),
                "anchor_frame_id": anchor_frame,
                "start_frame_id": start_frame,
                "end_frame_id": end_frame,
                "entity_refs": entity_refs,
                "extremum_selection_status": "PASS",
                "extremum_selection_reason": selected_reason,
                "selected_rank": rank,
                "selected_value": round(float(value), 3),
                "selected_record_id": _field_value(record, record_id_field),
                "selected_entity_id": _field_value(record, entity_id_field),
                "selected_frame_id": selected_frame_id,
                "selected_tie_breaker_value": _field_value(record, tie_breaker_field),
                "selected_secondary_tie_breaker_value": _field_value(record, secondary_tie_breaker_field),
                "selected_source_record_hash": stable_hash(record),
                "selected_source_record_index": source_index,
            }
        )
    return selections


def _base_record(
    *,
    state: Any,
    first_record: dict[str, Any],
    source_anchor_id: str,
    anchor_frame_id: int,
    selection_mode: str,
    top_k: int,
    value_field: str,
    value_unit: str,
    record_id_field: str,
    entity_id_field: str,
    frame_field: str,
    anchor_id_field: str,
    subject_id_field: str,
    subject_id: str | None,
    status_field: str,
    required_status_value: str,
    coverage_status_field: str,
    coverage_policy: str,
    value_bound_kind: str,
    value_bound: float,
    tie_breaker_field: str,
    secondary_tie_breaker_field: str,
    source_node_id: str,
    source_output_name: str,
    missing_evidence_policy: str,
    indexed_records: list[tuple[int, dict[str, Any]]],
) -> dict[str, Any]:
    start_frame_id = _record_frame_id(first_record, "start_frame_id") or anchor_frame_id
    end_frame_id = _record_frame_id(first_record, "end_frame_id") or anchor_frame_id
    entity_refs = [str(item) for item in list(first_record.get("entity_refs") or [])]
    match_id = str(first_record.get("match_id") or state.match_id)
    period = str(first_record.get("period") or state.period)
    return {
        "anchor_id": _canonical_anchor_id(
            match_id=match_id,
            period=period,
            anchor_frame_id=anchor_frame_id,
            start_frame_id=start_frame_id,
            end_frame_id=end_frame_id,
            entity_refs=entity_refs,
        ),
        "match_id": match_id,
        "period": period,
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "entity_refs": entity_refs,
        "selection_mode": selection_mode,
        "top_k": top_k,
        "value_field": value_field,
        "value_unit": value_unit,
        "record_id_field": record_id_field,
        "entity_id_field": entity_id_field,
        "frame_field": frame_field,
        "subject_id_field": subject_id_field,
        "subject_id": subject_id,
        "anchor_id_field": anchor_id_field,
        "source_anchor_id": source_anchor_id,
        "status_field": status_field,
        "required_status_value": required_status_value,
        "coverage_status_field": coverage_status_field,
        "coverage_policy": coverage_policy,
        "value_bound_kind": value_bound_kind,
        "value_bound": round(float(value_bound), 3),
        "tie_breaker_field": tie_breaker_field,
        "secondary_tie_breaker_field": secondary_tie_breaker_field,
        "witness_source_node_id": source_node_id,
        "witness_source_output_name": source_output_name,
        "missing_evidence_policy": missing_evidence_policy,
        "source_group_record_hashes": [stable_hash(record) for _, record in indexed_records],
    }


def _coverage_decision(
    *,
    selected_value: float,
    selection_mode: str,
    top_k: int,
    valid_count: int,
    unknown_count: int,
    incomplete_coverage: bool,
    coverage_policy: str,
    value_bound_kind: str,
    value_bound: float,
) -> tuple[str, str]:
    if top_k > valid_count:
        return "UNKNOWN", "top_k_exceeds_valid_candidate_count"
    if coverage_policy != "unknown_if_incomplete_could_change_answer":
        return "UNKNOWN", "unsupported_coverage_policy"
    if not incomplete_coverage and unknown_count == 0:
        return "PASS", "complete_candidate_set"
    if selection_mode == "argmin" and value_bound_kind == "lower":
        if float(value_bound) >= float(selected_value) - 1e-9:
            return "PASS", "incomplete_set_cannot_improve_argmin"
        return "UNKNOWN", "incomplete_set_could_change_argmin"
    if selection_mode == "argmax" and value_bound_kind == "upper":
        if float(value_bound) <= float(selected_value) + 1e-9:
            return "PASS", "incomplete_set_cannot_improve_argmax"
        return "UNKNOWN", "incomplete_set_could_change_argmax"
    return "UNKNOWN", "incomplete_set_could_change_answer"


def _ranked_candidates(
    candidates: list[tuple[int, dict[str, Any], float]],
    *,
    selection_mode: str,
    tie_breaker_field: str,
    secondary_tie_breaker_field: str,
) -> list[tuple[int, dict[str, Any], float]]:
    reverse_value = selection_mode == "argmax"

    def key(item: tuple[int, dict[str, Any], float]) -> tuple[Any, ...]:
        source_index, record, value = item
        sort_value = -float(value) if reverse_value else float(value)
        return (
            sort_value,
            _sortable(_field_value(record, tie_breaker_field)),
            _sortable(_field_value(record, secondary_tie_breaker_field)),
            stable_hash(record),
            source_index,
        )

    return sorted(candidates, key=key)


def _coverage_status(values: list[str], incomplete: bool) -> str:
    if incomplete:
        return "INCOMPLETE"
    if not values:
        return "NOT_DECLARED"
    if all(value in {"PASS", "COMPLETE"} for value in values):
        return "COMPLETE"
    return "OBSERVED"


def _runtime_records(value: RuntimeValue) -> list[dict[str, Any]]:
    if value.records and all(isinstance(item, dict) for item in value.records):
        return value.records
    if isinstance(value.value, list) and all(isinstance(item, dict) for item in value.value):
        return value.value
    return []


def _parameter_enum(parameters: dict[str, TypedValue], name: str, default: str = "") -> str:
    value = parameters.get(name)
    return default if value is None else str(value.value)


def _parameter_number(parameters: dict[str, TypedValue], name: str, default: float = 0.0) -> float:
    value = parameters.get(name)
    return default if value is None else float(value.value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _record_frame_id(record: dict[str, Any], field: str) -> int | None:
    if field == "none":
        return None
    value = record.get(field)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _status_value(record: dict[str, Any], field: str) -> str | None:
    if field == "none":
        return None
    value = record.get(field)
    return None if value is None else str(value)


def _field_value(record: dict[str, Any], field: str) -> str | None:
    if field == "none":
        return None
    value = record.get(field)
    return None if value is None else str(value)


def _entity_refs(record: dict[str, Any], entity_id_field: str) -> list[str]:
    refs = list(record.get("entity_refs") or [])
    entity_id = _field_value(record, entity_id_field)
    if entity_id is not None and entity_id not in refs:
        refs.append(entity_id)
    return [str(item) for item in refs]


def _canonical_anchor_id(
    *,
    match_id: str,
    period: str,
    anchor_frame_id: int,
    start_frame_id: int,
    end_frame_id: int,
    entity_refs: list[str],
) -> str:
    return stable_hash(
        {
            "match_id": str(match_id),
            "period": str(period),
            "anchor_frame_id": int(anchor_frame_id),
            "start_frame_id": int(start_frame_id),
            "end_frame_id": int(end_frame_id),
            "entity_refs": sorted(str(item) for item in entity_refs),
        }
    )[:16]


def _sortable(value: str | None) -> tuple[int, str]:
    return (1, "") if value is None else (0, str(value))
