"""window composition operator.

R1-4 adds generic, witnessed temporal window construction over anchor
records. The operator emits bounded windows before/after/around anchors, plus
trace-back windows whose start is bounded by declared continuity evidence.
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
from tqe.runtime.operators.typed_join import same_team_perspective_satisfied
from tqe.runtime.values import FrameSignal, RuntimeValue


WINDOW_MODE_VALUES = ("before", "after", "around", "trace_back_from_outcome")
TRUNCATION_POLICY_VALUES = ("emit_with_flag", "unknown")
CONTINUITY_POLICY_VALUES = ("fixed_duration", "same_possession")
OVERLAP_POLICY_VALUES = ("preserve_all",)
TEAM_BINDING_POLICY_VALUES = ("none", "equal_team_role")
CONTINUITY_OVERLAP_POLICY_VALUES = ("latest_start_covering_anchor", "unknown_on_ambiguous")
STATUS_VALUE_VALUES = ("PASS", "FAIL", "UNKNOWN")
EVIDENCE_FIELDS = [
    "window_status",
    "window_reason",
    "window_mode",
    "source_anchor_id",
    "source_anchor_frame_id",
    "source_anchor_start_frame_id",
    "source_anchor_end_frame_id",
    "anchor_frame_field",
    "anchor_status_field",
    "anchor_status_value",
    "anchor_status",
    "requested_before_seconds",
    "requested_after_seconds",
    "requested_start_frame_id",
    "requested_end_frame_id",
    "window_start_frame_id",
    "window_end_frame_id",
    "window_duration_frames",
    "window_duration_seconds",
    "frame_rate_hz",
    "period_start_frame_id",
    "period_end_frame_id",
    "truncated_start",
    "truncated_end",
    "truncation_policy",
    "continuity_policy",
    "continuity_status",
    "continuity_reason",
    "continuity_start_frame_field",
    "continuity_end_frame_field",
    "continuity_status_field",
    "continuity_status_value",
    "anchor_team_role_field",
    "continuity_team_role_field",
    "anchor_team_role",
    "continuity_team_role",
    "team_binding_policy",
    "continuity_overlap_policy",
    "continuity_evidence_id",
    "continuity_start_frame_id",
    "continuity_end_frame_id",
    "continuity_evidence_record_hash",
    "continuity_evidence_source_node_id",
    "continuity_evidence_source_output_name",
    "witness_anchor_node_id",
    "witness_anchor_output_name",
    "witness_anchor_record_hash",
    "witness_anchor_record_index",
    "overlap_policy",
]


WINDOW_SIGNATURE = CompositionOperatorSignature(
    name="window",
    version="0.1.0",
    purpose=(
        "Emit witnessed bounded temporal windows around anchors, including "
        "trace-back windows bounded by declared continuity evidence."
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
            name="continuity_evidence",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.BOOLEAN,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.POSSESSION,
            required=False,
        ),
    ],
    outputs=[
        OperatorOutputDeclaration(
            name="window_records",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="window_status",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="window_duration_seconds",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.NUMBER,
            cardinality=Cardinality.SINGLE,
            unit=Unit.SECOND,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
    ],
    parameters=[
        ParameterDefinition(
            name="window_mode",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(WINDOW_MODE_VALUES),
            description="Window construction mode.",
        ),
        ParameterDefinition(
            name="anchor_frame_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Anchor-record frame field used as the window reference frame.",
        ),
        ParameterDefinition(
            name="before_duration_seconds",
            payload_type=PayloadType.NUMBER,
            unit=Unit.SECOND,
            required=True,
            minimum=0.0,
            description="Requested duration before the anchor frame.",
        ),
        ParameterDefinition(
            name="after_duration_seconds",
            payload_type=PayloadType.NUMBER,
            unit=Unit.SECOND,
            required=True,
            minimum=0.0,
            description="Requested duration after the anchor frame.",
        ),
        ParameterDefinition(
            name="frame_rate_hz",
            payload_type=PayloadType.NUMBER,
            unit=Unit.HERTZ,
            required=True,
            minimum=0.001,
            description="Analysis frame rate used to convert declared seconds into frame counts.",
        ),
        ParameterDefinition(
            name="anchor_status_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Optional anchor status field required before a window is claimed.",
        ),
        ParameterDefinition(
            name="anchor_status_value",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            allowed_values=list(STATUS_VALUE_VALUES),
            description="Required anchor status value when anchor_status_field is not none.",
        ),
        ParameterDefinition(
            name="truncation_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="emit_with_flag"),
            allowed_values=list(TRUNCATION_POLICY_VALUES),
            description="Policy when requested windows cross observed period/data boundaries.",
        ),
        ParameterDefinition(
            name="continuity_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="fixed_duration"),
            allowed_values=list(CONTINUITY_POLICY_VALUES),
            description="Continuity evidence required for trace-back or continuity-bounded windows.",
        ),
        ParameterDefinition(
            name="continuity_start_frame_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Continuity-record start frame field for same-possession/team-control policies.",
        ),
        ParameterDefinition(
            name="continuity_end_frame_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Continuity-record end frame field for same-possession/team-control policies.",
        ),
        ParameterDefinition(
            name="continuity_status_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Optional continuity-record status field.",
        ),
        ParameterDefinition(
            name="continuity_status_value",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            allowed_values=list(STATUS_VALUE_VALUES),
            description="Required continuity status value when continuity_status_field is not none.",
        ),
        ParameterDefinition(
            name="anchor_team_role_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Anchor-record team-role field used to key continuity evidence.",
        ),
        ParameterDefinition(
            name="continuity_team_role_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Continuity-record team-role field used to key continuity evidence.",
        ),
        ParameterDefinition(
            name="team_binding_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            allowed_values=list(TEAM_BINDING_POLICY_VALUES),
            description="Declared policy for matching anchor and continuity team evidence.",
        ),
        ParameterDefinition(
            name="continuity_overlap_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="latest_start_covering_anchor"),
            allowed_values=list(CONTINUITY_OVERLAP_POLICY_VALUES),
            description="Declared policy when multiple continuity records cover the anchor.",
        ),
        ParameterDefinition(
            name="overlap_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="preserve_all"),
            allowed_values=list(OVERLAP_POLICY_VALUES),
            description="Deterministic policy for overlapping output windows.",
        ),
    ],
    coverage_propagation_rule_id="continuity_coverage_gap_could_change_window_to_unknown",
    witness_rule_id="window_anchor_and_continuity_evidence",
    limitations=[
        "Windows are derived from declared anchor frames and declared durations only.",
        "Boundary truncation is recorded and either emitted or UNKNOWN according to truncation_policy.",
        "same_possession uses supplied continuity intervals only; missing coverage is UNKNOWN.",
        "Continuity-backed policies require declared team-role fields and equal team-role binding.",
        "trace_back_from_outcome bounds the preceding window by continuity evidence and does not infer causation.",
    ],
)


def execute_window(
    *,
    state: Any,
    node: Any,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> None:
    anchor_value = inputs.get("anchors")
    if anchor_value is None:
        raise RuntimeError(f"{node.node_id} requires anchors input")
    anchor_ref = node.inputs["anchors"]
    continuity_ref = node.inputs.get("continuity_evidence")
    anchors = _runtime_records(anchor_value)
    continuity_records = _runtime_records(inputs.get("continuity_evidence"))

    window_mode = _parameter_enum(parameters, "window_mode")
    anchor_frame_field = _parameter_enum(parameters, "anchor_frame_field")
    before_seconds = max(0.0, _parameter_number(parameters, "before_duration_seconds"))
    after_seconds = max(0.0, _parameter_number(parameters, "after_duration_seconds"))
    frame_rate_hz = _parameter_number(parameters, "frame_rate_hz")
    anchor_status_field = _parameter_enum(parameters, "anchor_status_field", "none")
    anchor_status_value = _parameter_enum(parameters, "anchor_status_value", "PASS")
    truncation_policy = _parameter_enum(parameters, "truncation_policy", "emit_with_flag")
    continuity_policy = _parameter_enum(parameters, "continuity_policy", "fixed_duration")
    continuity_start_field = _parameter_enum(parameters, "continuity_start_frame_field", "none")
    continuity_end_field = _parameter_enum(parameters, "continuity_end_frame_field", "none")
    continuity_status_field = _parameter_enum(parameters, "continuity_status_field", "none")
    continuity_status_value = _parameter_enum(parameters, "continuity_status_value", "PASS")
    anchor_team_role_field = _parameter_enum(parameters, "anchor_team_role_field", "none")
    continuity_team_role_field = _parameter_enum(parameters, "continuity_team_role_field", "none")
    team_binding_policy = _parameter_enum(parameters, "team_binding_policy", "none")
    continuity_overlap_policy = _parameter_enum(parameters, "continuity_overlap_policy", "latest_start_covering_anchor")
    overlap_policy = _parameter_enum(parameters, "overlap_policy", "preserve_all")

    if frame_rate_hz <= 0:
        raise RuntimeError(f"{node.node_id} frame_rate_hz must be positive")
    period_start, period_end = _period_bounds(state, anchors)
    records = [
        _window_record(
            state=state,
            anchor=anchor,
            anchor_index=index,
            anchor_node_id=anchor_ref.source_node_id,
            anchor_output_name=anchor_ref.output_name,
            continuity_node_id=None if continuity_ref is None else continuity_ref.source_node_id,
            continuity_output_name=None if continuity_ref is None else continuity_ref.output_name,
            continuity_records=continuity_records,
            window_mode=window_mode,
            anchor_frame_field=anchor_frame_field,
            before_seconds=before_seconds,
            after_seconds=after_seconds,
            frame_rate_hz=frame_rate_hz,
            anchor_status_field=anchor_status_field,
            anchor_status_value=anchor_status_value,
            truncation_policy=truncation_policy,
            continuity_policy=continuity_policy,
            continuity_start_field=continuity_start_field,
            continuity_end_field=continuity_end_field,
            continuity_status_field=continuity_status_field,
            continuity_status_value=continuity_status_value,
            anchor_team_role_field=anchor_team_role_field,
            continuity_team_role_field=continuity_team_role_field,
            team_binding_policy=team_binding_policy,
            continuity_overlap_policy=continuity_overlap_policy,
            overlap_policy=overlap_policy,
            period_start_frame_id=period_start,
            period_end_frame_id=period_end,
        )
        for index, anchor in enumerate(anchors)
        if isinstance(anchor, dict)
    ]
    records.sort(
        key=lambda item: (
            str(item["match_id"]),
            str(item["period"]),
            int(item["window_start_frame_id"]),
            int(item["window_end_frame_id"]),
            str(item["source_anchor_id"]),
            str(item["anchor_id"]),
        )
    )
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if record["window_status"] == "UNKNOWN" else record["window_status"]
        for record in records
    ]
    duration_values = [
        None if record["window_status"] == "UNKNOWN" else record["window_duration_seconds"]
        for record in records
    ]
    state.signals[node.node_id] = {
        "window_records": records,
        "window_records_records": records,
        "window_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        "window_status_records": records,
        "window_duration_seconds": FrameSignal(
            frame_ids=frame_ids,
            values=duration_values,
            unknown_mask=[value is None for value in duration_values],
            unit=Unit.SECOND,
            entity_scope=EntityScope.ANCHOR,
        ),
        "window_duration_seconds_records": records,
    }


def _window_record(
    *,
    state: Any,
    anchor: dict[str, Any],
    anchor_index: int,
    anchor_node_id: str,
    anchor_output_name: str,
    continuity_node_id: str | None,
    continuity_output_name: str | None,
    continuity_records: list[dict[str, Any]],
    window_mode: str,
    anchor_frame_field: str,
    before_seconds: float,
    after_seconds: float,
    frame_rate_hz: float,
    anchor_status_field: str,
    anchor_status_value: str,
    truncation_policy: str,
    continuity_policy: str,
    continuity_start_field: str,
    continuity_end_field: str,
    continuity_status_field: str,
    continuity_status_value: str,
    anchor_team_role_field: str,
    continuity_team_role_field: str,
    team_binding_policy: str,
    continuity_overlap_policy: str,
    overlap_policy: str,
    period_start_frame_id: int,
    period_end_frame_id: int,
) -> dict[str, Any]:
    source_anchor_frame_id = _record_frame_id(anchor, anchor_frame_field) or _record_frame_id(anchor, "anchor_frame_id")
    source_anchor_start = _record_frame_id(anchor, "start_frame_id") or source_anchor_frame_id
    source_anchor_end = _record_frame_id(anchor, "end_frame_id") or source_anchor_frame_id
    match_id = str(anchor.get("match_id") or getattr(state, "match_id", ""))
    period = str(anchor.get("period") or getattr(state, "period", ""))
    entity_refs = [str(item) for item in list(anchor.get("entity_refs") or [])]
    source_anchor_id = str(anchor.get("anchor_id") or "")
    if source_anchor_frame_id is None:
        return _status_record(
            state=state,
            anchor=anchor,
            match_id=match_id,
            period=period,
            entity_refs=entity_refs,
            source_anchor_id=source_anchor_id,
            source_anchor_frame_id=0,
            source_anchor_start_frame_id=source_anchor_start,
            source_anchor_end_frame_id=source_anchor_end,
            anchor_frame_field=anchor_frame_field,
            anchor_status_field=anchor_status_field,
            anchor_status_value=anchor_status_value,
            anchor_status=None,
            before_seconds=before_seconds,
            after_seconds=after_seconds,
            frame_rate_hz=frame_rate_hz,
            requested_start_frame_id=None,
            requested_end_frame_id=None,
            window_start_frame_id=0,
            window_end_frame_id=0,
            period_start_frame_id=period_start_frame_id,
            period_end_frame_id=period_end_frame_id,
            truncated_start=False,
            truncated_end=False,
            truncation_policy=truncation_policy,
            continuity_policy=continuity_policy,
            continuity_start_field=continuity_start_field,
            continuity_end_field=continuity_end_field,
            continuity_status_field=continuity_status_field,
            continuity_status_value=continuity_status_value,
            anchor_team_role_field=anchor_team_role_field,
            continuity_team_role_field=continuity_team_role_field,
            anchor_team_role=None,
            team_binding_policy=team_binding_policy,
            continuity_overlap_policy=continuity_overlap_policy,
            continuity=None,
            anchor_node_id=anchor_node_id,
            anchor_output_name=anchor_output_name,
            anchor_index=anchor_index,
            overlap_policy=overlap_policy,
            status="UNKNOWN",
            reason="anchor_frame_missing",
            continuity_status="UNKNOWN",
            continuity_reason="anchor_frame_missing",
        )
    anchor_status = _status_value(anchor, anchor_status_field)
    anchor_team_role = _record_text(anchor, anchor_team_role_field)
    requested_start, requested_end = _requested_window_frames(
        anchor_frame_id=source_anchor_frame_id,
        window_mode=window_mode,
        before_seconds=before_seconds,
        after_seconds=after_seconds,
        frame_rate_hz=frame_rate_hz,
    )
    bounded_start = int(requested_start)
    bounded_end = int(requested_end)
    continuity_evaluation_start = max(int(requested_start), int(period_start_frame_id))
    continuity_evaluation_end = min(int(requested_end), int(period_end_frame_id))
    if int(source_anchor_frame_id) < int(period_start_frame_id) or int(source_anchor_frame_id) > int(period_end_frame_id):
        bounded_start = bounded_end = min(
            max(int(source_anchor_frame_id), int(period_start_frame_id)),
            int(period_end_frame_id),
        )
        return _status_record(
            state=state,
            anchor=anchor,
            match_id=match_id,
            period=period,
            entity_refs=entity_refs,
            source_anchor_id=source_anchor_id,
            source_anchor_frame_id=int(source_anchor_frame_id),
            source_anchor_start_frame_id=source_anchor_start,
            source_anchor_end_frame_id=source_anchor_end,
            anchor_frame_field=anchor_frame_field,
            anchor_status_field=anchor_status_field,
            anchor_status_value=anchor_status_value,
            anchor_status=anchor_status,
            before_seconds=before_seconds,
            after_seconds=after_seconds,
            frame_rate_hz=frame_rate_hz,
            requested_start_frame_id=int(requested_start),
            requested_end_frame_id=int(requested_end),
            window_start_frame_id=int(bounded_start),
            window_end_frame_id=int(bounded_end),
            period_start_frame_id=period_start_frame_id,
            period_end_frame_id=period_end_frame_id,
            truncated_start=True,
            truncated_end=True,
            truncation_policy=truncation_policy,
            continuity_policy=continuity_policy,
            continuity_start_field=continuity_start_field,
            continuity_end_field=continuity_end_field,
            continuity_status_field=continuity_status_field,
            continuity_status_value=continuity_status_value,
            anchor_team_role_field=anchor_team_role_field,
            continuity_team_role_field=continuity_team_role_field,
            anchor_team_role=anchor_team_role,
            team_binding_policy=team_binding_policy,
            continuity_overlap_policy=continuity_overlap_policy,
            continuity=None,
            anchor_node_id=anchor_node_id,
            anchor_output_name=anchor_output_name,
            anchor_index=anchor_index,
            overlap_policy=overlap_policy,
            status="UNKNOWN",
            reason="anchor_outside_observed_bounds",
            continuity_status="UNKNOWN",
            continuity_reason="continuity_not_evaluated_anchor_outside_bounds",
            continuity_node_id=continuity_node_id,
            continuity_output_name=continuity_output_name,
            window_mode=window_mode,
        )
    status = "PASS"
    reason = "window_constructed"
    continuity_status = "PASS" if continuity_policy == "fixed_duration" else "UNKNOWN"
    continuity_reason = "fixed_duration_policy" if continuity_policy == "fixed_duration" else "continuity_not_evaluated"
    continuity: dict[str, Any] | None = None
    if anchor_status_field != "none":
        if anchor_status is None or anchor_status == "UNKNOWN":
            status = "UNKNOWN"
            reason = "required_anchor_status_unknown"
        elif anchor_status != anchor_status_value:
            status = "FAIL"
            reason = "required_anchor_status_not_met"
    if status == "PASS" and continuity_policy != "fixed_duration":
        continuity, continuity_status, continuity_reason = _continuity_decision(
            continuity_records=continuity_records,
            anchor_frame_id=int(source_anchor_frame_id),
            requested_start=continuity_evaluation_start,
            requested_end=continuity_evaluation_end,
            window_mode=window_mode,
            continuity_start_field=continuity_start_field,
            continuity_end_field=continuity_end_field,
            continuity_status_field=continuity_status_field,
            continuity_status_value=continuity_status_value,
            anchor_team_role=anchor_team_role,
            continuity_team_role_field=continuity_team_role_field,
            team_binding_policy=team_binding_policy,
            continuity_overlap_policy=continuity_overlap_policy,
        )
        if continuity_status == "UNKNOWN":
            status = "UNKNOWN"
            reason = continuity_reason
        elif continuity_status == "FAIL":
            status = "FAIL"
            reason = continuity_reason
        elif continuity is not None:
            continuity_start = _record_frame_id(continuity, continuity_start_field)
            continuity_end = _record_frame_id(continuity, continuity_end_field)
            if continuity_start is not None and continuity_end is not None:
                if window_mode == "trace_back_from_outcome":
                    continuity_bounded_start = max(bounded_start, continuity_start)
                    continuity_bounded_end = min(bounded_end, continuity_end)
                    if continuity_bounded_start > continuity_bounded_end:
                        status = "UNKNOWN"
                        reason = "continuity_evidence_does_not_overlap_window"
                    else:
                        if continuity_bounded_start != bounded_start or continuity_bounded_end != bounded_end:
                            continuity_reason = "trace_back_bounded_by_continuity"
                        bounded_start, bounded_end = continuity_bounded_start, continuity_bounded_end
                elif continuity_start > continuity_evaluation_start or continuity_end < continuity_evaluation_end:
                    status = "FAIL"
                    reason = "continuity_break_inside_window"
                    continuity_status = "FAIL"
                    continuity_reason = "continuity_break_inside_window"
    clipped_start = max(int(bounded_start), int(period_start_frame_id))
    clipped_end = min(int(bounded_end), int(period_end_frame_id))
    truncated_start = clipped_start != int(bounded_start)
    truncated_end = clipped_end != int(bounded_end)
    if clipped_end < clipped_start:
        clipped_start = clipped_end = min(
            max(int(source_anchor_frame_id), int(period_start_frame_id)),
            int(period_end_frame_id),
        )
        status = "UNKNOWN"
        reason = "window_outside_observed_bounds"
        if continuity_policy != "fixed_duration" and continuity_status == "PASS":
            continuity_status = "UNKNOWN"
            continuity_reason = "window_outside_observed_bounds"
    if status == "PASS" and (truncated_start or truncated_end) and truncation_policy == "unknown":
        status = "UNKNOWN"
        reason = "window_truncated_by_boundary"
    return _status_record(
        state=state,
        anchor=anchor,
        match_id=match_id,
        period=period,
        entity_refs=entity_refs,
        source_anchor_id=source_anchor_id,
        source_anchor_frame_id=int(source_anchor_frame_id),
        source_anchor_start_frame_id=source_anchor_start,
        source_anchor_end_frame_id=source_anchor_end,
        anchor_frame_field=anchor_frame_field,
        anchor_status_field=anchor_status_field,
        anchor_status_value=anchor_status_value,
        anchor_status=anchor_status,
        before_seconds=before_seconds,
        after_seconds=after_seconds,
        frame_rate_hz=frame_rate_hz,
        requested_start_frame_id=int(requested_start),
        requested_end_frame_id=int(requested_end),
        window_start_frame_id=int(clipped_start),
        window_end_frame_id=int(clipped_end),
        period_start_frame_id=period_start_frame_id,
        period_end_frame_id=period_end_frame_id,
        truncated_start=truncated_start,
        truncated_end=truncated_end,
        truncation_policy=truncation_policy,
        continuity_policy=continuity_policy,
        continuity_start_field=continuity_start_field,
        continuity_end_field=continuity_end_field,
        continuity_status_field=continuity_status_field,
        continuity_status_value=continuity_status_value,
        anchor_team_role_field=anchor_team_role_field,
        continuity_team_role_field=continuity_team_role_field,
        anchor_team_role=anchor_team_role,
        team_binding_policy=team_binding_policy,
        continuity_overlap_policy=continuity_overlap_policy,
        continuity=continuity,
        anchor_node_id=anchor_node_id,
        anchor_output_name=anchor_output_name,
        anchor_index=anchor_index,
        overlap_policy=overlap_policy,
        status=status,
        reason=reason,
        continuity_status=continuity_status,
        continuity_reason=continuity_reason,
        continuity_node_id=continuity_node_id,
        continuity_output_name=continuity_output_name,
        window_mode=window_mode,
    )


def _requested_window_frames(
    *,
    anchor_frame_id: int,
    window_mode: str,
    before_seconds: float,
    after_seconds: float,
    frame_rate_hz: float,
) -> tuple[int, int]:
    before_frames = _duration_frames(before_seconds, frame_rate_hz)
    after_frames = _duration_frames(after_seconds, frame_rate_hz)
    if window_mode == "before":
        return int(anchor_frame_id) - before_frames, int(anchor_frame_id)
    if window_mode == "after":
        return int(anchor_frame_id), int(anchor_frame_id) + after_frames
    if window_mode == "around":
        return int(anchor_frame_id) - before_frames, int(anchor_frame_id) + after_frames
    if window_mode == "trace_back_from_outcome":
        return int(anchor_frame_id) - before_frames, int(anchor_frame_id)
    raise RuntimeError(f"Unsupported window_mode {window_mode}")


def _continuity_decision(
    *,
    continuity_records: list[dict[str, Any]],
    anchor_frame_id: int,
    requested_start: int,
    requested_end: int,
    window_mode: str,
    continuity_start_field: str,
    continuity_end_field: str,
    continuity_status_field: str,
    continuity_status_value: str,
    anchor_team_role: str | None,
    continuity_team_role_field: str,
    team_binding_policy: str,
    continuity_overlap_policy: str,
) -> tuple[dict[str, Any] | None, str, str]:
    if continuity_start_field == "none" or continuity_end_field == "none":
        return None, "UNKNOWN", "continuity_frame_fields_missing"
    if team_binding_policy != "equal_team_role":
        return None, "UNKNOWN", "continuity_team_binding_policy_missing"
    if anchor_team_role is None or continuity_team_role_field == "none":
        return None, "UNKNOWN", "continuity_team_fields_missing"
    if not continuity_records:
        return None, "UNKNOWN", "continuity_evidence_missing"
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    mismatched_covering_candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for record in continuity_records:
        start = _record_frame_id(record, continuity_start_field)
        end = _record_frame_id(record, continuity_end_field)
        if start is None or end is None:
            continue
        status = _status_value(record, continuity_status_field)
        if continuity_status_field != "none" and status != continuity_status_value:
            continue
        if start <= anchor_frame_id <= end:
            same_team, _anchor_role, record_team_role = same_team_perspective_satisfied(
                {"team_role": anchor_team_role},
                record,
                left_team_role_field="team_role",
                right_team_role_field=continuity_team_role_field,
            )
            if same_team is None:
                return record, "UNKNOWN", "continuity_team_field_missing"
            candidate = (int(start), int(end), stable_hash(record), record)
            if same_team:
                candidates.append(candidate)
            else:
                mismatched_covering_candidates.append(candidate)
    if not candidates:
        if mismatched_covering_candidates:
            mismatched_covering_candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            return mismatched_covering_candidates[0][3], "FAIL", "continuity_team_mismatch"
        return None, "UNKNOWN", "continuity_evidence_not_covering_anchor"
    if continuity_overlap_policy == "unknown_on_ambiguous" and len(candidates) > 1:
        return None, "UNKNOWN", "ambiguous_overlapping_continuity_evidence"
    if window_mode == "trace_back_from_outcome":
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    else:
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    start, end, _hash, record = candidates[0]
    if end < requested_start or start > requested_end:
        return record, "UNKNOWN", "continuity_evidence_does_not_overlap_window"
    return record, "PASS", "continuity_evidence_observed"


def _status_record(
    *,
    state: Any,
    anchor: dict[str, Any],
    match_id: str,
    period: str,
    entity_refs: list[str],
    source_anchor_id: str,
    source_anchor_frame_id: int,
    source_anchor_start_frame_id: int | None,
    source_anchor_end_frame_id: int | None,
    anchor_frame_field: str,
    anchor_status_field: str,
    anchor_status_value: str,
    anchor_status: str | None,
    before_seconds: float,
    after_seconds: float,
    frame_rate_hz: float,
    requested_start_frame_id: int | None,
    requested_end_frame_id: int | None,
    window_start_frame_id: int,
    window_end_frame_id: int,
    period_start_frame_id: int,
    period_end_frame_id: int,
    truncated_start: bool,
    truncated_end: bool,
    truncation_policy: str,
    continuity_policy: str,
    continuity_start_field: str,
    continuity_end_field: str,
    continuity_status_field: str,
    continuity_status_value: str,
    anchor_team_role_field: str,
    continuity_team_role_field: str,
    anchor_team_role: str | None,
    team_binding_policy: str,
    continuity_overlap_policy: str,
    continuity: dict[str, Any] | None,
    anchor_node_id: str,
    anchor_output_name: str,
    anchor_index: int,
    overlap_policy: str,
    status: str,
    reason: str,
    continuity_status: str,
    continuity_reason: str,
    continuity_node_id: str | None = None,
    continuity_output_name: str | None = None,
    window_mode: str = "after",
) -> dict[str, Any]:
    window_duration_frames = max(0, int(window_end_frame_id) - int(window_start_frame_id) + 1)
    window_duration_seconds = window_duration_frames / float(frame_rate_hz) if frame_rate_hz > 0 else 0.0
    continuity_start = None if continuity is None else _record_frame_id(continuity, continuity_start_field)
    continuity_end = None if continuity is None else _record_frame_id(continuity, continuity_end_field)
    continuity_team_role = None if continuity is None else _record_text(continuity, continuity_team_role_field)
    record = {
        **anchor,
        "match_id": match_id or str(getattr(state, "match_id", "")),
        "period": period or str(getattr(state, "period", "")),
        "anchor_frame_id": int(source_anchor_frame_id),
        "start_frame_id": int(window_start_frame_id),
        "end_frame_id": int(window_end_frame_id),
        "entity_refs": entity_refs,
        "window_status": status,
        "window_reason": reason,
        "window_mode": window_mode,
        "source_anchor_id": source_anchor_id,
        "source_anchor_frame_id": int(source_anchor_frame_id),
        "source_anchor_start_frame_id": source_anchor_start_frame_id,
        "source_anchor_end_frame_id": source_anchor_end_frame_id,
        "anchor_frame_field": anchor_frame_field,
        "anchor_status_field": anchor_status_field,
        "anchor_status_value": anchor_status_value,
        "anchor_status": anchor_status,
        "requested_before_seconds": round(float(before_seconds), 3),
        "requested_after_seconds": round(float(after_seconds), 3),
        "requested_start_frame_id": requested_start_frame_id,
        "requested_end_frame_id": requested_end_frame_id,
        "window_start_frame_id": int(window_start_frame_id),
        "window_end_frame_id": int(window_end_frame_id),
        "window_duration_frames": window_duration_frames,
        "window_duration_seconds": round(float(window_duration_seconds), 3),
        "frame_rate_hz": round(float(frame_rate_hz), 3),
        "period_start_frame_id": int(period_start_frame_id),
        "period_end_frame_id": int(period_end_frame_id),
        "truncated_start": bool(truncated_start),
        "truncated_end": bool(truncated_end),
        "truncation_policy": truncation_policy,
        "continuity_policy": continuity_policy,
        "continuity_status": continuity_status,
        "continuity_reason": continuity_reason,
        "continuity_start_frame_field": continuity_start_field,
        "continuity_end_frame_field": continuity_end_field,
        "continuity_status_field": continuity_status_field,
        "continuity_status_value": continuity_status_value,
        "anchor_team_role_field": anchor_team_role_field,
        "continuity_team_role_field": continuity_team_role_field,
        "anchor_team_role": anchor_team_role,
        "continuity_team_role": continuity_team_role,
        "team_binding_policy": team_binding_policy,
        "continuity_overlap_policy": continuity_overlap_policy,
        "continuity_evidence_id": None if continuity is None else str(continuity.get("anchor_id") or ""),
        "continuity_start_frame_id": continuity_start,
        "continuity_end_frame_id": continuity_end,
        "continuity_evidence_record_hash": None if continuity is None else stable_hash(continuity),
        "continuity_evidence_source_node_id": continuity_node_id,
        "continuity_evidence_source_output_name": continuity_output_name,
        "witness_anchor_node_id": anchor_node_id,
        "witness_anchor_output_name": anchor_output_name,
        "witness_anchor_record_hash": stable_hash(anchor),
        "witness_anchor_record_index": int(anchor_index),
        "overlap_policy": overlap_policy,
    }
    record["anchor_id"] = _canonical_anchor_id(
        match_id=record["match_id"],
        period=record["period"],
        anchor_frame_id=int(record["anchor_frame_id"]),
        start_frame_id=int(record["start_frame_id"]),
        end_frame_id=int(record["end_frame_id"]),
        entity_refs=entity_refs,
    )
    return record


def _duration_frames(seconds: float, frame_rate_hz: float) -> int:
    if seconds <= 0:
        return 0
    return int(math.ceil(float(seconds) * float(frame_rate_hz) - 1e-9))


def _period_bounds(
    state: Any,
    anchors: list[dict[str, Any]],
) -> tuple[int, int]:
    frame_ids = getattr(state, "frame_ids", None)
    if frame_ids is not None and len(frame_ids):
        values = [int(item) for item in list(frame_ids)]
        return min(values), max(values)
    candidates: list[int] = []
    for record in anchors:
        for field in ("anchor_frame_id", "start_frame_id", "end_frame_id"):
            value = _record_frame_id(record, field)
            if value is not None:
                candidates.append(value)
    if candidates:
        return min(candidates), max(candidates)
    return 0, 0


def _runtime_records(value: RuntimeValue | None) -> list[dict[str, Any]]:
    if value is None:
        return []
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


def _status_value(record: dict[str, Any] | None, field: str) -> str | None:
    if field == "none" or record is None:
        return None
    value = record.get(field)
    return None if value is None else str(value)


def _record_text(record: dict[str, Any] | None, field: str) -> str | None:
    if field == "none" or record is None:
        return None
    value = record.get(field)
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _record_frame_id(record: dict[str, Any] | None, frame_field: str) -> int | None:
    if record is None or frame_field == "none":
        return None
    return _optional_int(record.get(frame_field))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
