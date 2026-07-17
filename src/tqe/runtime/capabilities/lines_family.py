"""Observed-line capability implementations.

F2-4 relocates the line family from executor.py without changing behavior.
Shared runtime helpers remain in executor.py until the shared-kernel extraction
phase.
"""

from __future__ import annotations

from typing import Any

from tqe.evidence.observation_manifest import ObservationModality, gate_state_absence_status
from tqe.runtime.controlled_line_break import (
    ControlledLineBreakConfig,
    evaluate_controlled_line_break_episode,
)
from tqe.runtime.defensive_line import DefensiveLineConfig, evaluate_defensive_line_model
from tqe.runtime.executor import (
    PeriodState,
    anchor_record_id,
    ball_point_at_frame,
    cached_ball_x_at_frame,
    cached_defending_positions_at_frame,
    cached_observed_outfield_positions_at_frame,
    cached_player_position_at_frame,
    catalog_input_value,
    catalog_output,
    node_parameter_number,
    node_parameter_text,
    optional_int,
    outfield_player_ids,
    parquet_rows,
)
from tqe.runtime.ir import BoundCatalogNode, Unit
from tqe.runtime.one_touch import evaluate_receiver_line_transition
from tqe.runtime.pass_bypass import attack_x_sign_for
from tqe.runtime.relative_position_to_line import (
    RelativePositionToLineConfig,
    evaluate_relative_position_to_line,
)
from tqe.runtime.values import FrameSignal


def primitive_defensive_line_model(state: PeriodState, node: BoundCatalogNode) -> None:
    anchors_value = catalog_input_value(state, node, "anchors")
    anchors = anchors_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    config = DefensiveLineConfig(
        goal_side_buffer_m=node_parameter_number(node, "goal_side_buffer_m"),
        line_band_width_m=node_parameter_number(node, "line_band_width_m"),
        minimum_defenders=int(round(node_parameter_number(node, "minimum_line_defenders"))),
    )
    anchor_frame_field = node_parameter_text(node, "anchor_frame_field")
    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    attack_x_sign = attack_x_sign_for(
        orientation,
        state.match_id,
        state.period,
        state.perspective_team_role,
    )
    known_outfield_ids = outfield_player_ids(
        state.canonical_root,
        state.match_id,
        state.defending_team_role,
    )
    records = [
        defensive_line_anchor_record(
            state=state,
            anchor=anchor,
            anchor_frame_field=anchor_frame_field,
            attack_x_sign=attack_x_sign,
            known_outfield_ids=known_outfield_ids,
            config=config,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["line_status"]) == "UNKNOWN" else str(record["line_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "line_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "line_status").entity_scope,
        ),
        "line_status_records": records,
    }

def primitive_multi_line_model(state: PeriodState, node: BoundCatalogNode) -> None:
    anchors_value = catalog_input_value(state, node, "anchors")
    anchors = anchors_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    goal_side_buffer_m = node_parameter_number(node, "goal_side_buffer_m")
    line_band_width_m = node_parameter_number(node, "line_band_width_m")
    minimum_line_defenders = int(round(node_parameter_number(node, "minimum_line_defenders")))
    target_line_rank = int(round(node_parameter_number(node, "target_line_rank")))
    anchor_frame_field = node_parameter_text(node, "anchor_frame_field")
    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    attack_x_sign = attack_x_sign_for(
        orientation,
        state.match_id,
        state.period,
        state.perspective_team_role,
    )
    known_outfield_ids = outfield_player_ids(
        state.canonical_root,
        state.match_id,
        state.defending_team_role,
    )
    records = [
        multi_line_anchor_record(
            state=state,
            anchor=anchor,
            anchor_frame_field=anchor_frame_field,
            goal_side_buffer_m=goal_side_buffer_m,
            line_band_width_m=line_band_width_m,
            minimum_line_defenders=minimum_line_defenders,
            target_line_rank=target_line_rank,
            attack_x_sign=attack_x_sign,
            known_outfield_ids=known_outfield_ids,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "multi_line_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if str(record["multi_line_status"]) == "UNKNOWN" else str(record["multi_line_status"])
                for record in records
            ],
            unknown_mask=[str(record["multi_line_status"]) == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "multi_line_status").entity_scope,
        ),
        "multi_line_status_records": records,
    }

def multi_line_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    anchor_frame_field: str,
    goal_side_buffer_m: float,
    line_band_width_m: float,
    minimum_line_defenders: int,
    target_line_rank: int,
    attack_x_sign: int,
    known_outfield_ids: set[str],
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    evaluation_frame_id = optional_int(anchor.get(anchor_frame_field)) or anchor_frame_id
    if anchor_frame_id is None or evaluation_frame_id is None:
        return None
    ball_point = ball_point_at_frame(state, evaluation_frame_id)
    if ball_point is None:
        return multi_line_payload_from_anchor(
            state=state,
            anchor=anchor,
            evaluation_frame_id=evaluation_frame_id,
            status="UNKNOWN",
            reason="ball_position_missing",
            target_line_rank=target_line_rank,
            lines=[],
            attack_x_sign=attack_x_sign,
        )
    defenders = cached_observed_outfield_positions_at_frame(
        state,
        evaluation_frame_id,
        state.defending_team_role,
        known_outfield_ids,
    )
    candidates = []
    normalized_ball_x = float(ball_point[0]) * attack_x_sign
    for defender in defenders:
        if defender.get("x_m") is None or defender.get("y_m") is None:
            continue
        normalized_x = float(defender["x_m"]) * attack_x_sign
        if normalized_x > normalized_ball_x + goal_side_buffer_m:
            candidates.append(
                {
                    "player_id": str(defender["player_id"]),
                    "x_m": float(defender["x_m"]),
                    "y_m": float(defender["y_m"]),
                    "normalized_x_m": normalized_x,
                }
            )
    candidates.sort(key=lambda item: (item["normalized_x_m"], item["player_id"]))
    lines: list[dict[str, Any]] = []
    used: set[str] = set()
    for seed in candidates:
        if seed["player_id"] in used:
            continue
        band = [
            candidate for candidate in candidates
            if abs(candidate["normalized_x_m"] - seed["normalized_x_m"]) <= line_band_width_m
        ]
        if len(band) < minimum_line_defenders:
            continue
        defender_ids = sorted({str(item["player_id"]) for item in band})
        if any(defender_id in used for defender_id in defender_ids):
            continue
        used.update(defender_ids)
        normalized_line_x_m = sum(float(item["normalized_x_m"]) for item in band) / len(band)
        line_x_m = normalized_line_x_m / attack_x_sign
        lines.append(
            {
                "line_rank": len(lines) + 1,
                "line_id": f"observed_line:{state.match_id}:{state.period}:{evaluation_frame_id}:{len(lines) + 1}",
                "line_x_m": round(float(line_x_m), 3),
                "normalized_line_x_m": round(float(normalized_line_x_m), 3),
                "defender_ids": defender_ids,
                "defender_count": len(defender_ids),
            }
        )
    if not lines:
        status = "FAIL"
        reason = "no_observed_lines"
    elif len(lines) < target_line_rank:
        status = "FAIL"
        reason = "target_line_rank_not_observed"
    else:
        status = "PASS"
        reason = "target_line_rank_observed"
    if status == "FAIL":
        gated = gate_state_absence_status(
            state=state,
            start_frame_id=evaluation_frame_id,
            end_frame_id=evaluation_frame_id,
            modalities=(ObservationModality.PLAYER_TRACK,),
            status=status,
            reason=reason,
        )
        status, reason = gated.status, gated.reason
    return multi_line_payload_from_anchor(
        state=state,
        anchor=anchor,
        evaluation_frame_id=evaluation_frame_id,
        status=status,
        reason=reason,
        target_line_rank=target_line_rank,
        lines=lines,
        selected_line=lines[target_line_rank - 1] if len(lines) >= target_line_rank else None,
        ball_x_m=ball_point[0],
        normalized_ball_x_m=normalized_ball_x,
        goal_side_buffer_m=goal_side_buffer_m,
        line_band_width_m=line_band_width_m,
        minimum_line_defenders=minimum_line_defenders,
        attack_x_sign=attack_x_sign,
    )

def multi_line_payload_from_anchor(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    evaluation_frame_id: int,
    status: str,
    reason: str,
    target_line_rank: int,
    lines: list[dict[str, Any]],
    selected_line: dict[str, Any] | None = None,
    ball_x_m: float | None = None,
    normalized_ball_x_m: float | None = None,
    goal_side_buffer_m: float | None = None,
    line_band_width_m: float | None = None,
    minimum_line_defenders: int | None = None,
    attack_x_sign: int | None = None,
) -> dict[str, Any]:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id")) or evaluation_frame_id
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "multi_line_status": status,
        "multi_line_reason": reason,
        "line_status": status,
        "line_reason": reason,
        "line_type": "observed_ranked_line" if status == "PASS" else None,
        "line_evaluation_frame_id": evaluation_frame_id,
        "target_line_rank": target_line_rank,
        "observed_line_count": len(lines),
        "observed_lines": lines,
        "selected_line": selected_line,
        "line_x_m": None if selected_line is None else selected_line.get("line_x_m"),
        "normalized_line_x_m": None if selected_line is None else selected_line.get("normalized_line_x_m"),
        "defensive_line_player_ids": [] if selected_line is None else selected_line.get("defender_ids", []),
        "ball_x_m": ball_x_m,
        "normalized_ball_x_m": normalized_ball_x_m,
        "goal_side_buffer_m": goal_side_buffer_m,
        "line_band_width_m": line_band_width_m,
        "minimum_line_defenders": minimum_line_defenders,
        "attacking_direction": attack_x_sign,
    }

def defensive_line_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    anchor_frame_field: str,
    attack_x_sign: int | None,
    known_outfield_ids: set[str],
    config: DefensiveLineConfig,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    line_evaluation_frame_id = optional_int(anchor.get(anchor_frame_field))
    if line_evaluation_frame_id is None and anchor_frame_field != "anchor_frame_id":
        line_evaluation_frame_id = anchor_frame_id
    if anchor_frame_id is None or line_evaluation_frame_id is None:
        return None
    ball_x_m = cached_ball_x_at_frame(state, line_evaluation_frame_id)
    defender_positions = cached_defending_positions_at_frame(
        state,
        line_evaluation_frame_id,
        state.defending_team_role,
        known_outfield_ids,
    )
    evaluation = evaluate_defensive_line_model(
        ball_x_m=ball_x_m,
        defending_player_positions=defender_positions,
        attacking_direction=attack_x_sign,
        goalkeeper_id=None,
        goalkeeper_id_known=bool(known_outfield_ids),
        # cached_defending_positions_at_frame filters to known_outfield_ids,
        # so the goalkeeper is already excluded from the supplied positions.
        goalkeeper_excluded_from_positions=bool(known_outfield_ids),
        active_defender_ids_known=bool(known_outfield_ids),
        anchor_frame_id=line_evaluation_frame_id,
        config=config,
    )
    payload = evaluation.to_dict()
    line_status = str(payload["status"])
    line_reason = str(payload["reason"])
    if line_status == "FAIL" and line_reason == "no_qualifying_line":
        gated = gate_state_absence_status(
            state=state,
            start_frame_id=line_evaluation_frame_id,
            end_frame_id=line_evaluation_frame_id,
            modalities=(ObservationModality.PLAYER_TRACK,),
            status=line_status,
            reason=line_reason,
        )
        line_status, line_reason = gated.status, gated.reason
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(
            anchor.get("anchor_id")
            or anchor_record_id(
                match_id=state.match_id,
                period=state.period,
                anchor_frame_id=anchor_frame_id,
                start_frame_id=optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
                end_frame_id=optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
                entity_refs=anchor.get("entity_refs"),
            )
        ),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "perspective_team_role": state.perspective_team_role,
        "defending_team_role": state.defending_team_role,
        "line_evaluation_frame_field": anchor_frame_field,
        "line_evaluation_frame_id": line_evaluation_frame_id,
        "line_status": line_status,
        "line_reason": line_reason,
        "line_type": payload["line_type"],
        "selected_band_id": payload["selected_band_id"],
        "line_x_m": payload["line_x_m"],
        "normalized_line_x_m": payload["normalized_line_x_m"],
        "line_compactness_m": payload["compactness_m"],
        "defensive_line_player_ids": list(payload["defender_ids"]),
        "defenders_goal_side_count": payload["defenders_goal_side_count"],
        "candidate_line_count": payload["candidate_band_count"],
        "ambiguous_line_player_ids": [list(item) for item in payload["ambiguous_band_defender_ids"]],
        "goal_side_buffer_m": payload["goal_side_buffer_m"],
        "line_band_width_m": payload["line_band_width_m"],
        "minimum_line_defenders": payload["minimum_defenders"],
        "attacking_direction": payload["attacking_direction"],
        "ball_x_m": payload["ball_x_m"],
        "normalized_ball_x_m": payload["normalized_ball_x_m"],
        "observed_defending_outfield_ids": sorted(defender_positions),
        "defender_positions_used": list(payload["defender_positions_used"]),
    }

def primitive_relative_position_to_line(state: PeriodState, node: BoundCatalogNode) -> None:
    line_value = catalog_input_value(state, node, "line_evaluations")
    entity_value = catalog_input_value(state, node, "entity_anchors")
    line_records = line_value.value
    entity_records = entity_value.value
    if not isinstance(line_records, list) or not isinstance(entity_records, list):
        raise RuntimeError(f"{node.node_id} requires line and entity anchor records")
    entity_by_anchor_id = {
        str(record.get("anchor_id")): record
        for record in entity_records
        if isinstance(record, dict) and record.get("anchor_id") is not None
    }
    entity_id_field = node_parameter_text(node, "entity_id_field")
    entity_frame_field = node_parameter_text(
        node,
        "entity_frame_field"
    )
    config = RelativePositionToLineConfig(
        buffer_m=node_parameter_number(node, "line_buffer_m")
    )
    records = [
        relative_position_to_line_anchor_record(
            state=state,
            line_record=line_record,
            entity_record=entity_by_anchor_id.get(str(line_record.get("anchor_id")))
            if isinstance(line_record, dict)
            else None,
            entity_id_field=entity_id_field,
            entity_frame_field=entity_frame_field,
            config=config,
        )
        for line_record in line_records
        if isinstance(line_record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None
        if str(record["relative_position_status"]) == "UNKNOWN"
        else str(record["relative_position_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "relative_position_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "relative_position_status").entity_scope,
        ),
        "relative_position_status_records": records,
    }

def relative_position_to_line_anchor_record(
    *,
    state: PeriodState,
    line_record: dict[str, Any],
    entity_record: dict[str, Any] | None,
    entity_id_field: str,
    entity_frame_field: str,
    config: RelativePositionToLineConfig,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(line_record.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    entity_id = (
        None
        if entity_record is None or entity_record.get(entity_id_field) is None
        else str(entity_record.get(entity_id_field))
    )
    entity_frame_id = optional_int(entity_record.get(entity_frame_field)) if entity_record else None
    if entity_frame_id is None and entity_frame_field == "anchor_frame_id":
        entity_frame_id = optional_int(line_record.get("anchor_frame_id"))
    entity_position = (
        None
        if entity_id is None or entity_frame_id is None
        else cached_player_position_at_frame(state, entity_frame_id, entity_id)
    )
    evaluation = evaluate_relative_position_to_line(
        entity_position=entity_position,
        line_evaluation=line_record,
        entity_id=entity_id,
        anchor_frame_id=anchor_frame_id,
        config=config,
    )
    payload = evaluation.to_dict()
    return {
        **line_record,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(line_record.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(line_record.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(line_record.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(line_record.get("entity_refs") or []),
        "relative_position_status": str(payload["status"]),
        "relative_position_reason": payload["reason"],
        "relative_position_entity_id_field": entity_id_field,
        "relative_position_entity_frame_field": entity_frame_field,
        "entity_record_found": entity_record is not None,
        "entity_id": payload["entity_id"],
        "entity_frame_id": entity_frame_id,
        "entity_x_m": payload["entity_x_m"],
        "entity_y_m": payload["entity_y_m"],
        "normalized_entity_x_m": payload["normalized_entity_x_m"],
        "signed_distance_to_line_m": payload["signed_distance_to_line_m"],
        "distance_to_line_m": payload["distance_to_line_m"],
        "line_buffer_m": payload["buffer_m"],
    }

def primitive_receiver_line_transition_during_pass_leg(state: PeriodState, node: BoundCatalogNode) -> None:
    relay_value = catalog_input_value(state, node, "relay_anchors")
    line_value = catalog_input_value(state, node, "line_evaluations")
    release_value = catalog_input_value(state, node, "release_relative_positions")
    relay_position_value = catalog_input_value(state, node, "relay_relative_positions")
    relay_records = relay_value.value
    line_records = line_value.value
    release_records = release_value.value
    relay_position_records = relay_position_value.value
    if (
        not isinstance(relay_records, list)
        or not isinstance(line_records, list)
        or not isinstance(release_records, list)
        or not isinstance(relay_position_records, list)
    ):
        raise RuntimeError(f"{node.node_id} requires anchor-relative record collections")
    line_by_anchor_id = record_by_anchor_id(line_records)
    release_by_anchor_id = record_by_anchor_id(release_records)
    relay_position_by_anchor_id = record_by_anchor_id(relay_position_records)
    records = [
        receiver_line_transition_anchor_record(
            state=state,
            relay_record=relay_record,
            line_record=line_by_anchor_id.get(str(relay_record.get("anchor_id")))
            if isinstance(relay_record, dict)
            else None,
            release_record=release_by_anchor_id.get(str(relay_record.get("anchor_id")))
            if isinstance(relay_record, dict)
            else None,
            relay_position_record=relay_position_by_anchor_id.get(str(relay_record.get("anchor_id")))
            if isinstance(relay_record, dict)
            else None,
        )
        for relay_record in relay_records
        if isinstance(relay_record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "receiver_line_transition_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None
                if str(record["receiver_line_transition_status"]) == "UNKNOWN"
                else str(record["receiver_line_transition_status"])
                for record in records
            ],
            unknown_mask=[str(record["receiver_line_transition_status"]) == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "receiver_line_transition_status").entity_scope,
        ),
        "receiver_line_transition_status_records": records,
    }

def receiver_line_transition_anchor_record(
    *,
    state: PeriodState,
    relay_record: dict[str, Any],
    line_record: dict[str, Any] | None,
    release_record: dict[str, Any] | None,
    relay_position_record: dict[str, Any] | None,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(relay_record.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    evaluation = evaluate_receiver_line_transition(
        relay_evidence=relay_record,
        observed_line_evidence=line_record,
        release_relative_position_evidence=release_record,
        relay_relative_position_evidence=relay_position_record,
    )
    return {
        **relay_record,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(relay_record.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "receiver_line_transition_status": str(evaluation["receiver_line_transition_status"]),
        "receiver_line_transition_reason": evaluation["receiver_line_transition_reason"],
        "line_anchor_id": evaluation["line_anchor_id"],
        "line_anchor_frame_id": evaluation["line_anchor_frame_id"],
        "line_x_m": evaluation["line_x_m"],
        "normalized_line_x_m": evaluation["normalized_line_x_m"],
        "receiver_line_transition_attacking_direction": evaluation["attacking_direction"],
        "release_relative_position_status": evaluation["release_relative_position_status"],
        "release_signed_distance_to_line_m": evaluation["release_signed_distance_to_line_m"],
        "relay_relative_position_status": evaluation["relay_relative_position_status"],
        "relay_signed_distance_to_line_m": evaluation["relay_signed_distance_to_line_m"],
        "line_record_found": line_record is not None,
        "release_relative_position_record_found": release_record is not None,
        "relay_relative_position_record_found": relay_position_record is not None,
    }

def primitive_controlled_line_break_episode(state: PeriodState, node: BoundCatalogNode) -> None:
    controlled_value = catalog_input_value(state, node, "controlled_pass_anchors")
    line_value = catalog_input_value(state, node, "line_evaluations")
    release_value = catalog_input_value(state, node, "release_relative_positions")
    reception_value = catalog_input_value(state, node, "reception_relative_positions")
    controlled_records = controlled_value.value
    line_records = line_value.value
    release_records = release_value.value
    reception_records = reception_value.value
    if (
        not isinstance(controlled_records, list)
        or not isinstance(line_records, list)
        or not isinstance(release_records, list)
        or not isinstance(reception_records, list)
    ):
        raise RuntimeError(f"{node.node_id} requires anchor-relative record collections")

    line_by_anchor_id = record_by_anchor_id(line_records)
    release_by_anchor_id = record_by_anchor_id(release_records)
    reception_by_anchor_id = record_by_anchor_id(reception_records)
    config = ControlledLineBreakConfig(
        line_buffer_m=node_parameter_number(node, "line_buffer_m")
    )
    records = [
        controlled_line_break_anchor_record(
            state=state,
            controlled_record=controlled_record,
            line_record=line_by_anchor_id.get(str(controlled_record.get("anchor_id")))
            if isinstance(controlled_record, dict)
            else None,
            release_record=release_by_anchor_id.get(str(controlled_record.get("anchor_id")))
            if isinstance(controlled_record, dict)
            else None,
            reception_record=reception_by_anchor_id.get(str(controlled_record.get("anchor_id")))
            if isinstance(controlled_record, dict)
            else None,
            config=config,
        )
        for controlled_record in controlled_records
        if isinstance(controlled_record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None
        if str(record["line_break_status"]) == "UNKNOWN"
        else str(record["line_break_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "line_break_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "line_break_status").entity_scope,
        ),
        "line_break_status_records": records,
    }

def controlled_line_break_anchor_record(
    *,
    state: PeriodState,
    controlled_record: dict[str, Any],
    line_record: dict[str, Any] | None,
    release_record: dict[str, Any] | None,
    reception_record: dict[str, Any] | None,
    config: ControlledLineBreakConfig,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(controlled_record.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    evaluation = evaluate_controlled_line_break_episode(
        controlled_pass_evidence=controlled_record,
        observed_line_evidence=line_record,
        release_relative_position_evidence=release_record,
        reception_relative_position_evidence=reception_record,
        anchor_id=str(controlled_record.get("anchor_id")),
        config=config,
    )
    payload = evaluation.to_dict()
    return {
        **controlled_record,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(controlled_record.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "line_break_status": str(payload["status"]),
        "line_break_reason": payload["reason"],
        "line_anchor_id": payload["line_anchor_id"],
        "line_anchor_frame_id": payload["line_anchor_frame_id"],
        "line_x_m": payload["line_x_m"],
        "normalized_line_x_m": payload["normalized_line_x_m"],
        "line_break_attacking_direction": payload["attacking_direction"],
        "release_relative_position_status": payload["release_status"],
        "release_relative_position_reason": payload["release_reason"],
        "release_signed_distance_to_line_m": payload["release_signed_distance_to_line_m"],
        "release_distance_to_line_m": payload["release_distance_to_line_m"],
        "reception_relative_position_status": payload["reception_status"],
        "reception_relative_position_reason": payload["reception_reason"],
        "reception_signed_distance_to_line_m": payload["reception_signed_distance_to_line_m"],
        "reception_distance_to_line_m": payload["reception_distance_to_line_m"],
        "line_buffer_m": payload["line_buffer_m"],
        "release_level_counts_as_not_yet_beyond": payload["release_level_counts_as_not_yet_beyond"],
        "controlled_pass_anchor_id": payload["controlled_pass_anchor_id"],
        "release_relative_position_record_found": release_record is not None,
        "reception_relative_position_record_found": reception_record is not None,
        "line_record_found": line_record is not None,
    }

def record_by_anchor_id(records: list[Any]) -> dict[str, dict[str, Any]]:
    return {
        str(record.get("anchor_id")): record
        for record in records
        if isinstance(record, dict) and record.get("anchor_id") is not None
    }
