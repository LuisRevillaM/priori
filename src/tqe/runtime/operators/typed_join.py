"""typed_join composition operator.

R1-5 introduces explicit typed joins between independently produced evidence
channels. Joins are only allowed under declared identity constraints, or under
an explicit unconstrained rationale. The implementation records the fields and
witnesses used for the join so downstream claims can audit the composition.
"""

from __future__ import annotations

from typing import Any

from tqe.evidence.observation_manifest import ObservationModality, gate_state_absence_status
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
from tqe.runtime.values import FrameSignal, RuntimeValue, canonical_anchor_record_id


JOIN_KEY_VALUES = ("same_anchor", "same_frame_window", "same_entity", "episode_overlap")
NO_MATCH_POLICY_VALUES = ("FAIL", "UNKNOWN", "drop_with_count")
STATUS_VALUE_VALUES = ("PASS", "FAIL", "UNKNOWN")
EVIDENCE_FIELDS = [
    "match_id",
    "period",
    "perspective_team_role",
    "typed_join_status",
    "typed_join_reason",
    "join_key",
    "no_match_policy",
    "unconstrained",
    "unconstrained_rationale",
    "same_team_perspective_required",
    "entity_identity_preserved_required",
    "frame_alignment_required",
    "left_anchor_id_field",
    "right_anchor_id_field",
    "left_frame_field",
    "right_frame_field",
    "left_entity_id_field",
    "right_entity_id_field",
    "left_start_frame_field",
    "left_end_frame_field",
    "right_start_frame_field",
    "right_end_frame_field",
    "left_team_role_field",
    "right_team_role_field",
    "left_status_field",
    "right_status_field",
    "required_status_value",
    "left_required_status_value",
    "right_required_status_value",
    "maximum_frame_delta",
    "left_anchor_id",
    "right_anchor_id",
    "left_frame_id",
    "right_frame_id",
    "left_entity_id",
    "right_entity_id",
    "left_start_frame_id",
    "left_end_frame_id",
    "right_start_frame_id",
    "right_end_frame_id",
    "left_team_role",
    "right_team_role",
    "left_status",
    "right_status",
    "typed_join_match_count",
    "typed_join_dropped_no_match_count",
    "typed_join_constraint_failures",
    "left_record_hash",
    "right_record_hash",
    "left_record_index",
    "right_record_index",
    "witness_left_node_id",
    "witness_left_output_name",
    "witness_right_node_id",
    "witness_right_output_name",
]


TYPED_JOIN_SIGNATURE = CompositionOperatorSignature(
    name="typed_join",
    version="0.1.0",
    purpose=(
        "Join two declared evidence channels on explicit identity keys under "
        "bind-time composition constraints."
    ),
    inputs=[
        OperatorInputDefinition(
            name="left",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        OperatorInputDefinition(
            name="right",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
    ],
    outputs=[
        OperatorOutputDeclaration(
            name="typed_join_records",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="typed_join_status",
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
            name="join_key",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(JOIN_KEY_VALUES),
            description="Declared identity key used to match left and right records.",
        ),
        ParameterDefinition(
            name="no_match_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="UNKNOWN"),
            allowed_values=list(NO_MATCH_POLICY_VALUES),
            description="Policy when a required counterpart is absent.",
        ),
        ParameterDefinition(
            name="same_team_perspective_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=False),
            description="Require left and right records to carry the same team role.",
        ),
        ParameterDefinition(
            name="entity_identity_preserved_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=False),
            description="Require left and right entity ids to be identical.",
        ),
        ParameterDefinition(
            name="frame_alignment_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=False),
            description="Require left and right frame ids to align within maximum_frame_delta.",
        ),
        ParameterDefinition(
            name="unconstrained",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=False),
            description="Explicit escape hatch for unconstrained diagnostic joins.",
        ),
        ParameterDefinition(
            name="unconstrained_rationale",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Required textual rationale when unconstrained is true.",
        ),
        ParameterDefinition(
            name="left_anchor_id_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="anchor_id"),
            description="Left anchor id field for same_anchor joins.",
        ),
        ParameterDefinition(
            name="right_anchor_id_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="anchor_id"),
            description="Right anchor id field for same_anchor joins.",
        ),
        ParameterDefinition(
            name="left_frame_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="anchor_frame_id"),
            description="Left frame field for frame-aligned joins.",
        ),
        ParameterDefinition(
            name="right_frame_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="anchor_frame_id"),
            description="Right frame field for frame-aligned joins.",
        ),
        ParameterDefinition(
            name="left_entity_id_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Left entity id field for same_entity or entity-preserved constraints.",
        ),
        ParameterDefinition(
            name="right_entity_id_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Right entity id field for same_entity or entity-preserved constraints.",
        ),
        ParameterDefinition(
            name="left_start_frame_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="start_frame_id"),
            description="Left episode start field for episode-overlap joins.",
        ),
        ParameterDefinition(
            name="left_end_frame_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="end_frame_id"),
            description="Left episode end field for episode-overlap joins.",
        ),
        ParameterDefinition(
            name="right_start_frame_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="start_frame_id"),
            description="Right episode start field for episode-overlap joins.",
        ),
        ParameterDefinition(
            name="right_end_frame_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="end_frame_id"),
            description="Right episode end field for episode-overlap joins.",
        ),
        ParameterDefinition(
            name="left_team_role_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Left team-role field for same-team-perspective constraints.",
        ),
        ParameterDefinition(
            name="right_team_role_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Right team-role field for same-team-perspective constraints.",
        ),
        ParameterDefinition(
            name="left_status_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Optional left record status field.",
        ),
        ParameterDefinition(
            name="right_status_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Optional right record status field.",
        ),
        ParameterDefinition(
            name="required_status_value",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            allowed_values=list(STATUS_VALUE_VALUES),
            description="Legacy default status when a side-specific required status is not declared.",
        ),
        ParameterDefinition(
            name="left_required_status_value",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            allowed_values=list(STATUS_VALUE_VALUES),
            description="Required status for the left status field when declared.",
        ),
        ParameterDefinition(
            name="right_required_status_value",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            allowed_values=list(STATUS_VALUE_VALUES),
            description="Required status for the right status field when declared.",
        ),
        ParameterDefinition(
            name="maximum_frame_delta",
            payload_type=PayloadType.NUMBER,
            unit=Unit.FRAME,
            required=False,
            default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.FRAME, value=0),
            minimum=0.0,
            description="Permitted absolute frame delta for frame alignment.",
        ),
    ],
    coverage_propagation_rule_id="missing_join_counterpart_or_unknown_side_to_unknown",
    witness_rule_id="typed_left_right_join_witnesses",
    limitations=[
        "typed_join composes existing evidence only; it does not fabricate missing counterpart records.",
        "Unconstrained joins require an explicit rationale and are surfaced as diagnostic, not semantic proof.",
        "Constraint fields are declared parameters and are recorded on each joined row.",
    ],
)


def execute_typed_join(
    *,
    state: Any,
    node: Any,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> None:
    left_records = _runtime_records(inputs.get("left"))
    right_records = _runtime_records(inputs.get("right"))
    left_ref = node.inputs["left"]
    right_ref = node.inputs["right"]
    join_key = _parameter_enum(parameters, "join_key")
    no_match_policy = _parameter_enum(parameters, "no_match_policy", "UNKNOWN")
    same_team_required = _parameter_bool(parameters, "same_team_perspective_required")
    entity_required = _parameter_bool(parameters, "entity_identity_preserved_required")
    frame_required = _parameter_bool(parameters, "frame_alignment_required")
    unconstrained = _parameter_bool(parameters, "unconstrained")
    rationale = _parameter_enum(parameters, "unconstrained_rationale", "none")
    fields = _JoinFields(
        left_anchor_id_field=_parameter_enum(parameters, "left_anchor_id_field", "anchor_id"),
        right_anchor_id_field=_parameter_enum(parameters, "right_anchor_id_field", "anchor_id"),
        left_frame_field=_parameter_enum(parameters, "left_frame_field", "anchor_frame_id"),
        right_frame_field=_parameter_enum(parameters, "right_frame_field", "anchor_frame_id"),
        left_entity_id_field=_parameter_enum(parameters, "left_entity_id_field", "none"),
        right_entity_id_field=_parameter_enum(parameters, "right_entity_id_field", "none"),
        left_start_frame_field=_parameter_enum(parameters, "left_start_frame_field", "start_frame_id"),
        left_end_frame_field=_parameter_enum(parameters, "left_end_frame_field", "end_frame_id"),
        right_start_frame_field=_parameter_enum(parameters, "right_start_frame_field", "start_frame_id"),
        right_end_frame_field=_parameter_enum(parameters, "right_end_frame_field", "end_frame_id"),
        left_team_role_field=_parameter_enum(parameters, "left_team_role_field", "none"),
        right_team_role_field=_parameter_enum(parameters, "right_team_role_field", "none"),
        left_status_field=_parameter_enum(parameters, "left_status_field", "none"),
        right_status_field=_parameter_enum(parameters, "right_status_field", "none"),
    )
    required_status_value = _parameter_enum(parameters, "required_status_value", "PASS")
    left_required_status_value = _parameter_enum(parameters, "left_required_status_value", required_status_value)
    right_required_status_value = _parameter_enum(parameters, "right_required_status_value", required_status_value)
    maximum_frame_delta = int(round(_parameter_number(parameters, "maximum_frame_delta", 0.0)))

    records: list[dict[str, Any]] = []
    dropped = 0
    for left_index, left in enumerate(left_records):
        if not isinstance(left, dict):
            continue
        matches: list[tuple[int, dict[str, Any]]] = []
        for right_index, right in enumerate(right_records):
            if not isinstance(right, dict):
                continue
            if _join_key_matches(join_key, left, right, fields, maximum_frame_delta) and _constraints_match(
                left,
                right,
                fields,
                same_team_required=same_team_required,
                entity_required=entity_required,
                frame_required=frame_required,
                maximum_frame_delta=maximum_frame_delta,
            ):
                matches.append((right_index, right))
        if not matches:
            if no_match_policy == "drop_with_count":
                dropped += 1
                continue
            status = "FAIL" if no_match_policy == "FAIL" else "UNKNOWN"
            reason = "join_counterpart_missing_fail" if status == "FAIL" else "join_counterpart_missing_unknown"
            left_start = _record_frame_id(left, fields.left_start_frame_field)
            left_end = _record_frame_id(left, fields.left_end_frame_field)
            left_frame = _record_frame_id(left, fields.left_frame_field)
            window_start = left_start if left_start is not None else left_frame
            window_end = left_end if left_end is not None else left_frame
            if status == "FAIL" and window_start is not None and window_end is not None:
                gated = gate_state_absence_status(
                    state=state,
                    start_frame_id=window_start,
                    end_frame_id=window_end,
                    modalities=(
                        ObservationModality.EVENT,
                        ObservationModality.BALL,
                        ObservationModality.POSSESSION,
                        ObservationModality.PLAYER_TRACK,
                    ),
                    status=status,
                    reason=reason,
                )
                status, reason = gated.status, gated.reason
            records.append(
                _join_record(
                    state=state,
                    left=left,
                    right=None,
                    left_index=left_index,
                    right_index=None,
                    join_key=join_key,
                    no_match_policy=no_match_policy,
                    unconstrained=unconstrained,
                    rationale=rationale,
                    same_team_required=same_team_required,
                    entity_required=entity_required,
                    frame_required=frame_required,
                    fields=fields,
                    required_status_value=required_status_value,
                    left_required_status_value=left_required_status_value,
                    right_required_status_value=right_required_status_value,
                    maximum_frame_delta=maximum_frame_delta,
                    match_count=0,
                    dropped_count=dropped,
                    left_node_id=left_ref.source_node_id,
                    left_output_name=left_ref.output_name,
                    right_node_id=right_ref.source_node_id,
                    right_output_name=right_ref.output_name,
                    status=status,
                    reason=reason,
                )
            )
            continue
        for right_index, right in matches:
            status, reason = _status_from_sides(
                left,
                right,
                fields,
                left_required_status_value=left_required_status_value,
                right_required_status_value=right_required_status_value,
            )
            records.append(
                _join_record(
                    state=state,
                    left=left,
                    right=right,
                    left_index=left_index,
                    right_index=right_index,
                    join_key=join_key,
                    no_match_policy=no_match_policy,
                    unconstrained=unconstrained,
                    rationale=rationale,
                    same_team_required=same_team_required,
                    entity_required=entity_required,
                    frame_required=frame_required,
                    fields=fields,
                    required_status_value=required_status_value,
                    left_required_status_value=left_required_status_value,
                    right_required_status_value=right_required_status_value,
                    maximum_frame_delta=maximum_frame_delta,
                    match_count=len(matches),
                    dropped_count=dropped,
                    left_node_id=left_ref.source_node_id,
                    left_output_name=left_ref.output_name,
                    right_node_id=right_ref.source_node_id,
                    right_output_name=right_ref.output_name,
                    status=status,
                    reason=reason,
                )
            )
    for record in records:
        record["typed_join_dropped_no_match_count"] = dropped
    records.sort(
        key=lambda item: (
            str(item["match_id"]),
            str(item["period"]),
            int(item["anchor_frame_id"]),
            str(item["left_anchor_id"]),
            str(item["right_anchor_id"]),
        )
    )
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if record["typed_join_status"] == "UNKNOWN" else record["typed_join_status"]
        for record in records
    ]
    state.signals[node.node_id] = {
        "typed_join_records": records,
        "typed_join_records_records": records,
        "typed_join_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        "typed_join_status_records": records,
    }


class _JoinFields:
    def __init__(self, **kwargs: str) -> None:
        self.__dict__.update(kwargs)


def same_team_perspective_satisfied(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
    *,
    left_team_role_field: str,
    right_team_role_field: str,
) -> tuple[bool | None, str | None, str | None]:
    left_role = _record_text(left, left_team_role_field)
    right_role = _record_text(right, right_team_role_field)
    if left_role is None or right_role is None:
        return None, left_role, right_role
    return left_role == right_role, left_role, right_role


def _join_key_matches(
    join_key: str,
    left: dict[str, Any],
    right: dict[str, Any],
    fields: _JoinFields,
    maximum_frame_delta: int,
) -> bool:
    if join_key == "same_anchor":
        return _record_text(left, fields.left_anchor_id_field) == _record_text(right, fields.right_anchor_id_field)
    if join_key == "same_frame_window":
        left_frame = _record_frame_id(left, fields.left_frame_field)
        right_frame = _record_frame_id(right, fields.right_frame_field)
        return left_frame is not None and right_frame is not None and abs(left_frame - right_frame) <= maximum_frame_delta
    if join_key == "same_entity":
        return _record_text(left, fields.left_entity_id_field) == _record_text(right, fields.right_entity_id_field)
    if join_key == "episode_overlap":
        left_start = _record_frame_id(left, fields.left_start_frame_field)
        left_end = _record_frame_id(left, fields.left_end_frame_field)
        right_start = _record_frame_id(right, fields.right_start_frame_field)
        right_end = _record_frame_id(right, fields.right_end_frame_field)
        return (
            left_start is not None
            and left_end is not None
            and right_start is not None
            and right_end is not None
            and max(left_start, right_start) <= min(left_end, right_end)
        )
    return False


def _constraints_match(
    left: dict[str, Any],
    right: dict[str, Any],
    fields: _JoinFields,
    *,
    same_team_required: bool,
    entity_required: bool,
    frame_required: bool,
    maximum_frame_delta: int,
) -> bool:
    if same_team_required:
        same_team, _left_role, _right_role = same_team_perspective_satisfied(
            left,
            right,
            left_team_role_field=fields.left_team_role_field,
            right_team_role_field=fields.right_team_role_field,
        )
        if same_team is not True:
            return False
    if entity_required:
        if _record_text(left, fields.left_entity_id_field) != _record_text(right, fields.right_entity_id_field):
            return False
    if frame_required:
        left_frame = _record_frame_id(left, fields.left_frame_field)
        right_frame = _record_frame_id(right, fields.right_frame_field)
        if left_frame is None or right_frame is None or abs(left_frame - right_frame) > maximum_frame_delta:
            return False
    return True


def _status_from_sides(
    left: dict[str, Any],
    right: dict[str, Any],
    fields: _JoinFields,
    *,
    left_required_status_value: str,
    right_required_status_value: str,
) -> tuple[str, str]:
    left_status = _status_value(left, fields.left_status_field)
    right_status = _status_value(right, fields.right_status_field)
    if left_status == "UNKNOWN" or right_status == "UNKNOWN":
        return "UNKNOWN", "join_side_status_unknown"
    if fields.left_status_field != "none" and left_status != left_required_status_value:
        return "FAIL", "left_status_not_required_value"
    if fields.right_status_field != "none" and right_status != right_required_status_value:
        return "FAIL", "right_status_not_required_value"
    return "PASS", "typed_join_matched"


def _join_record(
    *,
    state: Any,
    left: dict[str, Any],
    right: dict[str, Any] | None,
    left_index: int,
    right_index: int | None,
    join_key: str,
    no_match_policy: str,
    unconstrained: bool,
    rationale: str,
    same_team_required: bool,
    entity_required: bool,
    frame_required: bool,
    fields: _JoinFields,
    required_status_value: str,
    left_required_status_value: str,
    right_required_status_value: str,
    maximum_frame_delta: int,
    match_count: int,
    dropped_count: int,
    left_node_id: str,
    left_output_name: str,
    right_node_id: str,
    right_output_name: str,
    status: str,
    reason: str,
) -> dict[str, Any]:
    left_team_role = _record_text(left, fields.left_team_role_field)
    right_team_role = _record_text(right, fields.right_team_role_field)
    left_frame = _record_frame_id(left, fields.left_frame_field)
    right_frame = _record_frame_id(right, fields.right_frame_field)
    anchor_frame_id = left_frame or _record_frame_id(left, "anchor_frame_id") or 0
    joined_payload = dict(left)
    if right is not None:
        for key, value in right.items():
            if key not in joined_payload or joined_payload[key] is None:
                joined_payload[key] = value
    record = {
        **joined_payload,
        "match_id": str(left.get("match_id") or getattr(state, "match_id", "")),
        "period": str(left.get("period") or getattr(state, "period", "")),
        "perspective_team_role": str(getattr(state, "perspective_team_role", "")),
        "anchor_frame_id": int(anchor_frame_id),
        "typed_join_status": status,
        "typed_join_reason": reason,
        "join_key": join_key,
        "no_match_policy": no_match_policy,
        "unconstrained": bool(unconstrained),
        "unconstrained_rationale": rationale,
        "same_team_perspective_required": bool(same_team_required),
        "entity_identity_preserved_required": bool(entity_required),
        "frame_alignment_required": bool(frame_required),
        "left_anchor_id_field": fields.left_anchor_id_field,
        "right_anchor_id_field": fields.right_anchor_id_field,
        "left_frame_field": fields.left_frame_field,
        "right_frame_field": fields.right_frame_field,
        "left_entity_id_field": fields.left_entity_id_field,
        "right_entity_id_field": fields.right_entity_id_field,
        "left_start_frame_field": fields.left_start_frame_field,
        "left_end_frame_field": fields.left_end_frame_field,
        "right_start_frame_field": fields.right_start_frame_field,
        "right_end_frame_field": fields.right_end_frame_field,
        "left_team_role_field": fields.left_team_role_field,
        "right_team_role_field": fields.right_team_role_field,
        "left_status_field": fields.left_status_field,
        "right_status_field": fields.right_status_field,
        "required_status_value": required_status_value,
        "left_required_status_value": left_required_status_value,
        "right_required_status_value": right_required_status_value,
        "maximum_frame_delta": int(maximum_frame_delta),
        "left_anchor_id": _record_text(left, fields.left_anchor_id_field),
        "right_anchor_id": _record_text(right, fields.right_anchor_id_field),
        "left_frame_id": left_frame,
        "right_frame_id": right_frame,
        "left_entity_id": _record_text(left, fields.left_entity_id_field),
        "right_entity_id": _record_text(right, fields.right_entity_id_field),
        "left_start_frame_id": _record_frame_id(left, fields.left_start_frame_field),
        "left_end_frame_id": _record_frame_id(left, fields.left_end_frame_field),
        "right_start_frame_id": _record_frame_id(right, fields.right_start_frame_field),
        "right_end_frame_id": _record_frame_id(right, fields.right_end_frame_field),
        "left_team_role": left_team_role,
        "right_team_role": right_team_role,
        "left_status": _status_value(left, fields.left_status_field),
        "right_status": _status_value(right, fields.right_status_field),
        "typed_join_match_count": int(match_count),
        "typed_join_dropped_no_match_count": int(dropped_count),
        "typed_join_constraint_failures": [] if status == "PASS" else [reason],
        "left_record_hash": stable_hash(left),
        "right_record_hash": None if right is None else stable_hash(right),
        "left_record_index": int(left_index),
        "right_record_index": right_index,
        "witness_left_node_id": left_node_id,
        "witness_left_output_name": left_output_name,
        "witness_right_node_id": right_node_id,
        "witness_right_output_name": right_output_name,
    }
    record["anchor_id"] = canonical_anchor_record_id(record)
    return record


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


def _parameter_bool(parameters: dict[str, TypedValue], name: str, default: bool = False) -> bool:
    value = parameters.get(name)
    return default if value is None else bool(value.value)


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
    value = record.get(frame_field)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
