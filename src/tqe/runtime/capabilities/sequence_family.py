"""Sequence, switch, carry, and pass-chain capability implementations.

F2-7 relocates sequence-family implementations from executor.py without
changing behavior. Shared runtime helpers remain in executor.py until the
shared-kernel extraction phase.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.executor import (
    FRAME_RATE_HZ,
    PeriodState,
    anchor_record_id,
    ball_point_at_frame,
    cached_player_position_at_frame,
    catalog_input_value,
    catalog_output,
    frame_match_time_ms,
    lateral_side,
    node_parameter_number,
    optional_int,
    parquet_rows,
    player_records_at_frame,
    point_from_record,
    point_from_xy,
    runtime_records,
    tuple_point_to_record,
)
from tqe.runtime.ir import BoundCatalogNode, Unit
from tqe.runtime.one_touch import evaluate_pass_chain
from tqe.runtime.pass_bypass import attack_x_sign_for
from tqe.runtime.values import FrameSignal


def primitive_action_chain(state: PeriodState, node: BoundCatalogNode) -> None:
    action_value = catalog_input_value(state, node, "actions")
    actions = runtime_records(action_value)
    max_gap_seconds = node_parameter_number(node, "maximum_action_gap_seconds")
    chain_length = int(round(node_parameter_number(node, "chain_length")))
    if chain_length != 2:
        raise RuntimeError("action_chain v0.1 supports chain_length=2")
    records: list[dict[str, Any]] = []
    ordered = sorted(
        [record for record in actions if isinstance(record, dict)],
        key=lambda item: (
            float(item.get("event_gameclock_seconds") or -1),
            int(item.get("event_row_index") or -1),
        ),
    )
    for first, second in zip(ordered, ordered[1:], strict=False):
        if first.get("team_role") != second.get("team_role"):
            continue
        first_time = first.get("event_gameclock_seconds")
        second_time = second.get("event_gameclock_seconds")
        if first_time is None or second_time is None:
            continue
        gap_seconds = float(second_time) - float(first_time)
        if gap_seconds < 0:
            continue
        status = "PASS" if gap_seconds <= max_gap_seconds else "FAIL"
        reason = "actions_linked_in_order" if status == "PASS" else "action_gap_exceeded"
        anchor_frame_id = optional_int(second.get("anchor_frame_id"))
        start_frame_id = optional_int(first.get("anchor_frame_id"))
        if anchor_frame_id is None or start_frame_id is None:
            continue
        entity_refs = list(
            dict.fromkeys(
                [
                    *[str(item) for item in first.get("entity_refs") or []],
                    *[str(item) for item in second.get("entity_refs") or []],
                ]
            )
        )
        anchor_id = anchor_record_id(
            match_id=state.match_id,
            period=state.period,
            anchor_frame_id=anchor_frame_id,
            start_frame_id=start_frame_id,
            end_frame_id=anchor_frame_id,
            entity_refs=entity_refs,
        )
        records.append(
            {
                "anchor_id": anchor_id,
                "match_id": state.match_id,
                "period": state.period,
                "anchor_frame_id": anchor_frame_id,
                "start_frame_id": start_frame_id,
                "end_frame_id": anchor_frame_id,
                "entity_refs": entity_refs,
                "action_chain_status": status,
                "action_chain_reason": reason,
                "chain_length": chain_length,
                "maximum_action_gap_seconds": max_gap_seconds,
                "action_gap_seconds": gap_seconds,
                "first_action_anchor_id": first.get("anchor_id"),
                "second_action_anchor_id": second.get("anchor_id"),
                "first_action_row_index": first.get("event_row_index"),
                "second_action_row_index": second.get("event_row_index"),
                "team_role": first.get("team_role"),
            }
        )
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "action_chain_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["action_chain_status"] == "UNKNOWN" else record["action_chain_status"]
                for record in records
            ],
            unknown_mask=[record["action_chain_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "action_chain_status").entity_scope,
        ),
        "action_chain_status_records": records,
    }


def primitive_switch_of_play(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchors = anchor_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    minimum_lateral_displacement_m = node_parameter_number(node, "minimum_lateral_displacement_m")
    minimum_start_lateral_m = node_parameter_number(node, "minimum_start_lateral_m")
    minimum_end_lateral_m = node_parameter_number(node, "minimum_end_lateral_m")
    maximum_duration_seconds = node_parameter_number(node, "maximum_duration_seconds")
    records = [
        switch_of_play_anchor_record(
            state=state,
            anchor=anchor,
            minimum_lateral_displacement_m=minimum_lateral_displacement_m,
            minimum_start_lateral_m=minimum_start_lateral_m,
            minimum_end_lateral_m=minimum_end_lateral_m,
            maximum_duration_seconds=maximum_duration_seconds,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["switch_status"]) == "UNKNOWN" else str(record["switch_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "switch_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "switch_status").entity_scope,
        ),
        "switch_status_records": records,
    }


def switch_of_play_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    minimum_lateral_displacement_m: float,
    minimum_start_lateral_m: float,
    minimum_end_lateral_m: float,
    maximum_duration_seconds: float,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    release_frame_id = optional_int(anchor.get("physical_release_frame_id"))
    reception_frame_id = optional_int(anchor.get("controlled_reception_frame_id"))
    if anchor_frame_id is None:
        return None
    release_point = point_from_record(anchor.get("release_ball_point"))
    reception_point = point_from_record(anchor.get("reception_ball_point"))
    if release_point is None and release_frame_id is not None:
        release_point = tuple_point_to_record(ball_point_at_frame(state, release_frame_id))
    if reception_point is None and reception_frame_id is not None:
        reception_point = tuple_point_to_record(ball_point_at_frame(state, reception_frame_id))
    duration_seconds = (
        None
        if release_frame_id is None or reception_frame_id is None
        else max(0.0, (int(reception_frame_id) - int(release_frame_id)) / FRAME_RATE_HZ)
    )
    status = "UNKNOWN"
    reason = "switch_endpoint_missing"
    release_side = None
    reception_side = None
    lateral_displacement_m = None
    if release_point is not None and reception_point is not None:
        release_y = float(release_point["y_m"])
        reception_y = float(reception_point["y_m"])
        release_side = lateral_side(release_y)
        reception_side = lateral_side(reception_y)
        lateral_displacement_m = abs(reception_y - release_y)
        if release_side == "CENTER" or reception_side == "CENTER":
            status = "FAIL"
            reason = "endpoint_not_wide_enough"
        elif release_side == reception_side:
            status = "FAIL"
            reason = "same_lateral_side"
        elif lateral_displacement_m < minimum_lateral_displacement_m:
            status = "FAIL"
            reason = "lateral_displacement_below_threshold"
        elif abs(release_y) < minimum_start_lateral_m or abs(reception_y) < minimum_end_lateral_m:
            status = "FAIL"
            reason = "endpoint_lateral_depth_below_threshold"
        elif duration_seconds is not None and duration_seconds > maximum_duration_seconds:
            status = "FAIL"
            reason = "switch_duration_exceeded"
        else:
            status = "PASS"
            reason = "opposite_side_ball_transfer_observed"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or release_frame_id or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or reception_frame_id or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "switch_status": status,
        "switch_reason": reason,
        "release_frame_id": release_frame_id,
        "reception_frame_id": reception_frame_id,
        "release_ball_point": release_point,
        "reception_ball_point": reception_point,
        "release_lateral_side": release_side,
        "reception_lateral_side": reception_side,
        "lateral_displacement_m": None if lateral_displacement_m is None else round(float(lateral_displacement_m), 3),
        "switch_duration_seconds": None if duration_seconds is None else round(float(duration_seconds), 3),
        "minimum_lateral_displacement_m": minimum_lateral_displacement_m,
        "minimum_start_lateral_m": minimum_start_lateral_m,
        "minimum_end_lateral_m": minimum_end_lateral_m,
        "maximum_duration_seconds": maximum_duration_seconds,
    }


def primitive_carry_episode(state: PeriodState, node: BoundCatalogNode) -> None:
    anchors_value = catalog_input_value(state, node, "controlled_pass_anchors")
    anchors = anchors_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires controlled_pass anchor records")
    pass_records = [
        record
        for record in anchors
        if isinstance(record, dict)
        and str(record.get("controlled_pass_status")) == "PASS"
        and optional_int(record.get("controlled_reception_frame_id")) is not None
        and optional_int(record.get("physical_release_frame_id")) is not None
    ]
    pass_records.sort(
        key=lambda record: (
            int(optional_int(record.get("physical_release_frame_id")) or 0),
            int(record.get("event_row_index") or 0),
            str(record.get("pass_episode_id") or ""),
        )
    )
    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    records = [
        carry_episode_anchor_record(
            state=state,
            start_pass=start_pass,
            pass_records=pass_records,
            attack_x_sign=attack_x_sign_for(
                orientation,
                state.match_id,
                state.period,
                str(start_pass.get("team_role") or state.perspective_team_role),
            ),
            maximum_carry_seconds=node_parameter_number(node, "maximum_carry_seconds"),
            minimum_displacement_m=node_parameter_number(node, "minimum_displacement_m"),
            control_distance_m=node_parameter_number(node, "control_distance_m"),
            nearest_teammate_margin_m=node_parameter_number(node, "nearest_teammate_margin_m"),
            maximum_ball_player_speed_delta_mps=node_parameter_number(
                node,
                "maximum_ball_player_speed_delta_mps"
            ),
            minimum_controlled_frame_ratio=node_parameter_number(node, "minimum_controlled_frame_ratio"),
            minimum_comoving_frame_ratio=node_parameter_number(node, "minimum_comoving_frame_ratio"),
            maximum_missing_frame_ratio=node_parameter_number(node, "maximum_missing_frame_ratio"),
        )
        for start_pass in pass_records
    ]
    records = [record for record in records if record is not None]
    episodes = [record for record in records if str(record.get("carry_status")) == "PASS"]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["carry_status"]) == "UNKNOWN" else str(record["carry_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "episodes": episodes,
        "episodes_records": episodes,
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "carry_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "carry_status").entity_scope,
        ),
        "carry_status_records": records,
        "displacement_m": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("displacement_m") for record in records],
            unknown_mask=[record.get("displacement_m") is None for record in records],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "displacement_m").entity_scope,
        ),
        "displacement_m_records": records,
        "forward_progression_m": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("carry_forward_progression_m") for record in records],
            unknown_mask=[record.get("carry_forward_progression_m") is None for record in records],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "forward_progression_m").entity_scope,
        ),
        "forward_progression_m_records": records,
    }


def carry_episode_anchor_record(
    *,
    state: PeriodState,
    start_pass: dict[str, Any],
    pass_records: list[dict[str, Any]],
    attack_x_sign: int | None,
    maximum_carry_seconds: float,
    minimum_displacement_m: float,
    control_distance_m: float,
    nearest_teammate_margin_m: float,
    maximum_ball_player_speed_delta_mps: float,
    minimum_controlled_frame_ratio: float,
    minimum_comoving_frame_ratio: float,
    maximum_missing_frame_ratio: float,
) -> dict[str, Any] | None:
    start_frame_id = optional_int(start_pass.get("controlled_reception_frame_id"))
    carrier_id = str(start_pass.get("receiver_id") or "")
    team_role = str(start_pass.get("team_role") or "")
    if start_frame_id is None or not carrier_id or not team_role:
        return None
    maximum_end_frame_id = int(start_frame_id + math.ceil(maximum_carry_seconds * FRAME_RATE_HZ - 1e-9))
    terminal = terminal_pass_after_reception(
        start_pass=start_pass,
        pass_records=pass_records,
        carrier_id=carrier_id,
        team_role=team_role,
        start_frame_id=start_frame_id,
        maximum_end_frame_id=maximum_end_frame_id,
    )
    terminal_record = terminal.get("record")
    terminal_release_frame_id = optional_int(terminal_record.get("physical_release_frame_id")) if isinstance(terminal_record, dict) else None
    end_frame_id = terminal_release_frame_id or min(maximum_end_frame_id, int(state.frame_ids[-1]))
    continuity = carry_possession_continuity(
        state=state,
        team_role=team_role,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
    )
    control = carry_control_continuity(
        state=state,
        carrier_id=carrier_id,
        team_role=team_role,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        control_distance_m=control_distance_m,
        nearest_teammate_margin_m=nearest_teammate_margin_m,
        maximum_ball_player_speed_delta_mps=maximum_ball_player_speed_delta_mps,
        minimum_controlled_frame_ratio=minimum_controlled_frame_ratio,
        minimum_comoving_frame_ratio=minimum_comoving_frame_ratio,
        maximum_missing_frame_ratio=maximum_missing_frame_ratio,
    )
    start_point = point_from_record(start_pass.get("reception_receiver_point")) or tuple_point_to_record(
        cached_player_position_at_frame(state, start_frame_id, carrier_id)
    )
    end_point = (
        point_from_record(terminal_record.get("release_passer_point"))
        if isinstance(terminal_record, dict)
        else None
    ) or tuple_point_to_record(cached_player_position_at_frame(state, end_frame_id, carrier_id))
    displacement_m = point_distance(start_point, end_point)
    forward_progression_m = (
        None
        if start_point is None or end_point is None or attack_x_sign not in {-1, 1}
        else round((float(end_point["x_m"]) - float(start_point["x_m"])) * int(attack_x_sign), 3)
    )
    if terminal.get("status") != "PASS":
        status = "FAIL"
        reason = str(terminal.get("reason") or "terminal_pass_not_found")
    elif continuity["status"] != "PASS":
        status = str(continuity["status"])
        reason = str(continuity["reason"])
    elif control["status"] != "PASS":
        status = str(control["status"])
        reason = str(control["reason"])
    elif attack_x_sign not in {-1, 1}:
        status = "UNKNOWN"
        reason = "attacking_direction_missing"
    elif displacement_m is None:
        status = "UNKNOWN"
        reason = "carry_endpoint_missing"
    elif displacement_m < minimum_displacement_m:
        status = "FAIL"
        reason = "minimum_displacement_not_met"
    else:
        status = "PASS"
        reason = "carry_observed"
    anchor_id = anchor_record_id(
        match_id=state.match_id,
        period=state.period,
        anchor_frame_id=start_frame_id,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        entity_refs=[carrier_id],
    )
    return {
        "anchor_id": anchor_id,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_frame_id": start_frame_id,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "entity_refs": [carrier_id],
        "carry_episode_id": f"carry:{state.match_id}:{state.period}:{carrier_id}:{start_frame_id}:{end_frame_id}",
        "source_reception_pass_id": start_pass.get("pass_episode_id"),
        "terminal_pass_id": terminal_record.get("pass_episode_id") if isinstance(terminal_record, dict) else None,
        "carrier_id": carrier_id,
        "team_role": team_role,
        "carry_status": status,
        "carry_reason": reason,
        "control_model": "controlled_pass_distance_plus_comovement_v0_1",
        "control_bias": "conservative_clear_control_only",
        "control_distance_m": round(float(control_distance_m), 3),
        "nearest_teammate_margin_m": round(float(nearest_teammate_margin_m), 3),
        "maximum_ball_player_speed_delta_mps": round(float(maximum_ball_player_speed_delta_mps), 3),
        "minimum_controlled_frame_ratio": round(float(minimum_controlled_frame_ratio), 3),
        "minimum_comoving_frame_ratio": round(float(minimum_comoving_frame_ratio), 3),
        "maximum_missing_frame_ratio": round(float(maximum_missing_frame_ratio), 3),
        "minimum_displacement_m": round(float(minimum_displacement_m), 3),
        "maximum_carry_seconds": round(float(maximum_carry_seconds), 3),
        "carry_start_frame_id": start_frame_id,
        "carry_end_frame_id": end_frame_id,
        "start_match_time_ms": frame_match_time_ms(state, start_frame_id),
        "end_match_time_ms": frame_match_time_ms(state, end_frame_id),
        "carry_duration_seconds": round(max(0.0, (end_frame_id - start_frame_id) / FRAME_RATE_HZ), 3),
        "start_point": start_point,
        "end_point": end_point,
        "displacement_m": displacement_m,
        "carry_forward_progression_m": forward_progression_m,
        "attacking_direction": attack_x_sign,
        "possession_continuity_status": continuity["status"],
        "possession_continuity_reason": continuity["reason"],
        "control_continuity_status": control["status"],
        "control_continuity_reason": control["reason"],
        "controlled_frame_ratio": control["controlled_frame_ratio"],
        "comoving_frame_ratio": control["comoving_frame_ratio"],
        "missing_frame_ratio": control["missing_frame_ratio"],
        "observed_frame_count": control["observed_frame_count"],
        "controlled_frame_count": control["controlled_frame_count"],
        "comoving_frame_count": control["comoving_frame_count"],
        "velocity_observed_frame_count": control["velocity_observed_frame_count"],
        "missing_frame_count": control["missing_frame_count"],
        "terminal_detection_status": terminal.get("status"),
        "terminal_detection_reason": terminal.get("reason"),
        "terminal_passer_id": terminal_record.get("passer_id") if isinstance(terminal_record, dict) else None,
        "terminal_receiver_id": terminal_record.get("receiver_id") if isinstance(terminal_record, dict) else None,
        "terminal_release_frame_id": terminal_release_frame_id,
        "terminal_reception_frame_id": optional_int(terminal_record.get("controlled_reception_frame_id"))
        if isinstance(terminal_record, dict)
        else None,
    }


def terminal_pass_after_reception(
    *,
    start_pass: dict[str, Any],
    pass_records: list[dict[str, Any]],
    carrier_id: str,
    team_role: str,
    start_frame_id: int,
    maximum_end_frame_id: int,
) -> dict[str, Any]:
    start_pass_id = str(start_pass.get("pass_episode_id") or "")
    for candidate in pass_records:
        candidate_id = str(candidate.get("pass_episode_id") or "")
        if candidate_id == start_pass_id:
            continue
        release_frame_id = optional_int(candidate.get("physical_release_frame_id"))
        if release_frame_id is None or release_frame_id <= start_frame_id:
            continue
        if release_frame_id > maximum_end_frame_id:
            break
        if str(candidate.get("passer_id") or "") != carrier_id or str(candidate.get("team_role") or "") != team_role:
            return {"status": "FAIL", "reason": "next_confirmed_pass_by_other_player", "record": candidate}
        return {"status": "PASS", "reason": "terminal_same_player_pass", "record": candidate}
    return {"status": "FAIL", "reason": "terminal_pass_not_found_within_window", "record": None}


def carry_possession_continuity(
    *,
    state: PeriodState,
    team_role: str,
    start_frame_id: int,
    end_frame_id: int,
) -> dict[str, str]:
    indexes = analysis_indexes_between(state, start_frame_id, end_frame_id)
    if not indexes:
        return {"status": "UNKNOWN", "reason": "frame_window_missing"}
    alive = state.ball_alive[indexes[0] : indexes[-1] + 1]
    roles = state.possession_role[indexes[0] : indexes[-1] + 1]
    if len(alive) == 0 or len(roles) == 0:
        return {"status": "UNKNOWN", "reason": "possession_window_missing"}
    if not bool(np.all(alive)):
        return {"status": "FAIL", "reason": "ball_not_alive_during_carry"}
    if not bool(np.all(roles == team_role)):
        return {"status": "FAIL", "reason": "possession_changed_during_carry"}
    return {"status": "PASS", "reason": "same_team_possession_continuity_observed"}


def carry_control_continuity(
    *,
    state: PeriodState,
    carrier_id: str,
    team_role: str,
    start_frame_id: int,
    end_frame_id: int,
    control_distance_m: float,
    nearest_teammate_margin_m: float,
    maximum_ball_player_speed_delta_mps: float,
    minimum_controlled_frame_ratio: float,
    minimum_comoving_frame_ratio: float,
    maximum_missing_frame_ratio: float,
) -> dict[str, Any]:
    indexes = analysis_indexes_between(state, start_frame_id, end_frame_id)
    if not indexes:
        return carry_control_summary("UNKNOWN", "frame_window_missing")
    frame_ids = [int(state.frame_ids[index]) for index in indexes]
    player_maps, ball_points = coordinate_maps_by_frame(state)
    missing = observed = controlled = velocity_observed = comoving = 0
    previous_ball: tuple[float, float] | None = None
    previous_player: tuple[float, float] | None = None
    for frame_id in frame_ids:
        ball = ball_points.get(frame_id)
        frame_players = player_maps.get(frame_id, {})
        record = frame_players.get(carrier_id)
        player = (
            None
            if record is None or record.get("x_m") is None or record.get("y_m") is None
            else (float(record["x_m"]), float(record["y_m"]))
        )
        if ball is None or player is None or record is None or str(record.get("team_role")) != team_role:
            missing += 1
            previous_ball = ball
            previous_player = player
            continue
        observed += 1
        distance_m = math.hypot(ball[0] - player[0], ball[1] - player[1])
        if distance_m <= control_distance_m and nearest_teammate_allows_carry_control(
            frame_players=frame_players,
            team_role=team_role,
            ball_point=ball,
            player_distance_m=distance_m,
            nearest_teammate_margin_m=nearest_teammate_margin_m,
        ):
            controlled += 1
        if previous_ball is not None and previous_player is not None:
            dt_seconds = 1.0 / FRAME_RATE_HZ
            ball_vx = (ball[0] - previous_ball[0]) / dt_seconds
            ball_vy = (ball[1] - previous_ball[1]) / dt_seconds
            player_vx = (player[0] - previous_player[0]) / dt_seconds
            player_vy = (player[1] - previous_player[1]) / dt_seconds
            velocity_observed += 1
            if math.hypot(ball_vx - player_vx, ball_vy - player_vy) <= maximum_ball_player_speed_delta_mps:
                comoving += 1
        previous_ball = ball
        previous_player = player
    total = len(frame_ids)
    if total == 0:
        return carry_control_summary("UNKNOWN", "frame_window_missing")
    missing_ratio = round(missing / total, 3)
    controlled_ratio = round(controlled / observed, 3) if observed else None
    comoving_ratio = round(comoving / velocity_observed, 3) if velocity_observed else None
    if missing_ratio > maximum_missing_frame_ratio:
        status, reason = "UNKNOWN", "tracking_missing_during_carry"
    elif not observed or controlled_ratio is None or comoving_ratio is None:
        status, reason = "UNKNOWN", "control_evidence_missing"
    elif controlled_ratio < minimum_controlled_frame_ratio:
        status, reason = "FAIL", "ball_not_continuously_under_control"
    elif comoving_ratio < minimum_comoving_frame_ratio:
        status, reason = "FAIL", "ball_not_comoving_with_carrier"
    else:
        status, reason = "PASS", "continuous_clear_control_observed"
    return carry_control_summary(
        status,
        reason,
        observed_frame_count=observed,
        controlled_frame_count=controlled,
        comoving_frame_count=comoving,
        velocity_observed_frame_count=velocity_observed,
        missing_frame_count=missing,
        total_frame_count=total,
        controlled_frame_ratio=controlled_ratio,
        comoving_frame_ratio=comoving_ratio,
        missing_frame_ratio=missing_ratio,
    )


def carry_control_summary(
    status: str,
    reason: str,
    *,
    observed_frame_count: int = 0,
    controlled_frame_count: int = 0,
    comoving_frame_count: int = 0,
    velocity_observed_frame_count: int = 0,
    missing_frame_count: int = 0,
    total_frame_count: int = 0,
    controlled_frame_ratio: float | None = None,
    comoving_frame_ratio: float | None = None,
    missing_frame_ratio: float | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "observed_frame_count": observed_frame_count,
        "controlled_frame_count": controlled_frame_count,
        "comoving_frame_count": comoving_frame_count,
        "velocity_observed_frame_count": velocity_observed_frame_count,
        "missing_frame_count": missing_frame_count,
        "total_frame_count": total_frame_count,
        "controlled_frame_ratio": controlled_frame_ratio,
        "comoving_frame_ratio": comoving_frame_ratio,
        "missing_frame_ratio": missing_frame_ratio,
    }


def nearest_teammate_allows_carry_control(
    *,
    frame_players: dict[str, dict[str, Any]],
    team_role: str,
    ball_point: tuple[float, float],
    player_distance_m: float,
    nearest_teammate_margin_m: float,
) -> bool:
    distances = [
        math.hypot(float(record["x_m"]) - ball_point[0], float(record["y_m"]) - ball_point[1])
        for record in frame_players.values()
        if str(record.get("team_role")) == team_role
        and record.get("x_m") is not None
        and record.get("y_m") is not None
    ]
    return bool(distances) and player_distance_m <= min(distances) + nearest_teammate_margin_m


def analysis_indexes_between(state: PeriodState, start_frame_id: int, end_frame_id: int) -> list[int]:
    if end_frame_id < start_frame_id:
        return []
    return [
        index
        for index, frame_id in enumerate(state.frame_ids)
        if int(start_frame_id) <= int(frame_id) <= int(end_frame_id)
    ]


def point_distance(a: dict[str, float] | None, b: dict[str, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return round(math.hypot(float(a["x_m"]) - float(b["x_m"]), float(a["y_m"]) - float(b["y_m"])), 3)


def coordinate_maps_by_frame(
    state: PeriodState,
) -> tuple[dict[int, dict[str, dict[str, Any]]], dict[int, tuple[float, float]]]:
    key = ("coordinate_maps_by_frame",)
    if key not in state.lookup_cache:
        player_records: dict[int, dict[str, dict[str, Any]]] = {}
        ball_points: dict[int, tuple[float, float]] = {}
        for row in state.positions.itertuples(index=False):
            frame_id = int(row.frame_id)
            if str(row.entity_type) == "ball":
                if not pd.isna(row.x_m) and not pd.isna(row.y_m):
                    ball_points[frame_id] = (float(row.x_m), float(row.y_m))
                continue
            if str(row.entity_type) != "player":
                continue
            if pd.isna(row.x_m) or pd.isna(row.y_m):
                x_m = None
                y_m = None
            else:
                x_m = float(row.x_m)
                y_m = float(row.y_m)
            player_records.setdefault(frame_id, {})[str(row.entity_id)] = {
                "player_id": str(row.entity_id),
                "frame_id": frame_id,
                "team_id": str(row.team_id),
                "team_role": str(row.team_role),
                "x_m": x_m,
                "y_m": y_m,
            }
        state.lookup_cache[key] = (player_records, ball_points)
    return state.lookup_cache[key]




def primitive_pass_chain_episode(state: PeriodState, node: BoundCatalogNode) -> None:
    relay_value = catalog_input_value(state, node, "relay_anchors")
    terminal_value = catalog_input_value(state, node, "terminal_controlled_pass_anchors")
    relay_records = relay_value.value
    terminal_records = terminal_value.value
    if not isinstance(relay_records, list) or not isinstance(terminal_records, list):
        raise RuntimeError(f"{node.node_id} requires relay and terminal controlled-pass records")
    terminal_by_pass_id = {
        str(record.get("pass_episode_id")): record
        for record in terminal_records
        if isinstance(record, dict) and record.get("pass_episode_id") is not None
    }
    records = [
        pass_chain_anchor_record(
            state=state,
            relay_record=relay_record,
            terminal_record=terminal_by_pass_id.get(str(relay_record.get("relay_pass_episode_id")))
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
        "pass_chain_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if str(record["pass_chain_status"]) == "UNKNOWN" else str(record["pass_chain_status"])
                for record in records
            ],
            unknown_mask=[str(record["pass_chain_status"]) == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "pass_chain_status").entity_scope,
        ),
        "pass_chain_status_records": records,
    }


def pass_chain_anchor_record(
    *,
    state: PeriodState,
    relay_record: dict[str, Any],
    terminal_record: dict[str, Any] | None,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(relay_record.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    evaluation = evaluate_pass_chain(
        relay_evidence=relay_record,
        terminal_controlled_pass_evidence=terminal_record,
    )
    terminal_reception_frame_id = (
        optional_int(terminal_record.get("controlled_reception_frame_id"))
        if terminal_record is not None
        else None
    )
    return {
        **relay_record,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(relay_record.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "pass_chain_status": str(evaluation["pass_chain_status"]),
        "pass_chain_reason": evaluation["pass_chain_reason"],
        "terminal_pass_episode_id": relay_record.get("relay_pass_episode_id"),
        "terminal_receiver_id": None if terminal_record is None else terminal_record.get("receiver_id"),
        "terminal_controlled_reception_frame_id": terminal_reception_frame_id,
        "terminal_reception_match_time_ms": frame_match_time_ms(state, terminal_reception_frame_id),
        "terminal_forward_progression_m": None if terminal_record is None else terminal_record.get("forward_progression_m"),
        "terminal_controlled_pass_record_found": terminal_record is not None,
        "terminal_controlled_pass_status": None if terminal_record is None else terminal_record.get("controlled_pass_status"),
        "terminal_reception_ball_point": None if terminal_record is None else terminal_record.get("reception_ball_point"),
        "terminal_reception_receiver_point": None
        if terminal_record is None
        else terminal_record.get("reception_receiver_point"),
    }
