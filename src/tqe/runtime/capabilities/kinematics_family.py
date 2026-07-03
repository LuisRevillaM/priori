"""Kinematics, tracking, composition, and lane-occupancy implementations.

F2-7 relocates the final inline capability implementations from executor.py
without changing behavior. Shared runtime helpers remain in executor.py until
the shared-kernel extraction phase.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from tqe.runtime.executor import (
    FRAME_RATE_HZ,
    PeriodState,
    anchor_record_id,
    ball_point_at_frame,
    cached_observed_outfield_positions_at_frame,
    catalog_input_value,
    catalog_output,
    node_parameter_integer,
    node_parameter_number,
    node_parameter_text,
    optional_float,
    optional_int,
    outfield_player_ids,
    player_records_at_frame,
    point_from_xy,
    runtime_records,
    tracked_point_at_frame,
)
from tqe.runtime.ir import BoundCatalogNode, Unit
from tqe.runtime.lane_occupancy import LaneOccupancyConfig, evaluate_lane_occupancy
from tqe.runtime.values import FrameSignal


def primitive_tracking_quality(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    frame_field = node_parameter_text(node, "frame_field")
    records = [
        tracking_quality_anchor_record(state=state, anchor=record, frame_field=frame_field)
        for record in runtime_records(anchor_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "tracking_quality_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["tracking_quality_status"] == "UNKNOWN" else record["tracking_quality_status"]
                for record in records
            ],
            unknown_mask=[record["tracking_quality_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "tracking_quality_status").entity_scope,
        ),
        "tracking_quality_status_records": records,
    }


def primitive_pairwise_distance(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    frame_field = node_parameter_text(node, "frame_field")
    entity_a_field = node_parameter_text(node, "entity_a_field")
    entity_b_field = node_parameter_text(node, "entity_b_field")
    maximum_distance_m = node_parameter_number(node, "maximum_distance_m")
    records = [
        pairwise_distance_anchor_record(
            state=state,
            anchor=record,
            frame_field=frame_field,
            entity_a_field=entity_a_field,
            entity_b_field=entity_b_field,
            maximum_distance_m=maximum_distance_m,
        )
        for record in runtime_records(anchor_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "distance_m": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("distance_m") for record in records],
            unknown_mask=[record.get("distance_m") is None for record in records],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "distance_m").entity_scope,
        ),
        "distance_m_records": records,
        "pairwise_distance_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["pairwise_distance_status"] == "UNKNOWN" else record["pairwise_distance_status"]
                for record in records
            ],
            unknown_mask=[record["pairwise_distance_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "pairwise_distance_status").entity_scope,
        ),
        "pairwise_distance_status_records": records,
    }


def primitive_velocity(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    frame_field = node_parameter_text(node, "frame_field")
    entity_id_field = node_parameter_text(node, "entity_id_field")
    lookback_seconds = node_parameter_number(node, "lookback_seconds")
    records = [
        velocity_anchor_record(
            state=state,
            anchor=record,
            frame_field=frame_field,
            entity_id_field=entity_id_field,
            lookback_seconds=lookback_seconds,
        )
        for record in runtime_records(anchor_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "speed_mps": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("speed_mps") for record in records],
            unknown_mask=[record.get("speed_mps") is None for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "speed_mps").entity_scope,
        ),
        "speed_mps_records": records,
        "velocity_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["velocity_status"] == "UNKNOWN" else record["velocity_status"]
                for record in records
            ],
            unknown_mask=[record["velocity_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "velocity_status").entity_scope,
        ),
        "velocity_status_records": records,
    }


def primitive_acceleration(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    frame_field = node_parameter_text(node, "frame_field")
    entity_id_field = node_parameter_text(node, "entity_id_field")
    lookback_seconds = node_parameter_number(node, "lookback_seconds")
    minimum_abs_delta_speed_mps = node_parameter_number(node, "minimum_abs_delta_speed_mps")
    minimum_abs_acceleration_mps2 = node_parameter_number(node, "minimum_abs_acceleration_mps2")
    maximum_player_speed_mps = node_parameter_number(node, "maximum_player_speed_mps")
    maximum_abs_acceleration_mps2 = node_parameter_number(node, "maximum_abs_acceleration_mps2")
    records = [
        acceleration_anchor_record(
            state=state,
            anchor=record,
            frame_field=frame_field,
            entity_id_field=entity_id_field,
            lookback_seconds=lookback_seconds,
            minimum_abs_delta_speed_mps=minimum_abs_delta_speed_mps,
            minimum_abs_acceleration_mps2=minimum_abs_acceleration_mps2,
            maximum_player_speed_mps=maximum_player_speed_mps,
            maximum_abs_acceleration_mps2=maximum_abs_acceleration_mps2,
        )
        for record in runtime_records(anchor_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    acceleration_status_values = [
        None if str(record["acceleration_status"]) == "UNKNOWN" else str(record["acceleration_status"])
        for record in records
    ]
    deceleration_status_values = [
        None if str(record["deceleration_status"]) == "UNKNOWN" else str(record["deceleration_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "acceleration_mps2": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("acceleration_mps2") for record in records],
            unknown_mask=[record.get("acceleration_mps2") is None for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "acceleration_mps2").entity_scope,
        ),
        "acceleration_mps2_records": records,
        "acceleration_status": FrameSignal(
            frame_ids=frame_ids,
            values=acceleration_status_values,
            unknown_mask=[value is None for value in acceleration_status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "acceleration_status").entity_scope,
        ),
        "acceleration_status_records": records,
        "deceleration_status": FrameSignal(
            frame_ids=frame_ids,
            values=deceleration_status_values,
            unknown_mask=[value is None for value in deceleration_status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "deceleration_status").entity_scope,
        ),
        "deceleration_status_records": records,
    }


def tracking_quality_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    quality_frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or quality_frame_id is None:
        return None
    entity_refs = [str(item) for item in anchor.get("entity_refs") or []]
    ball_present = ball_point_at_frame(state, quality_frame_id) is not None
    players = player_records_at_frame(state, quality_frame_id)
    missing_entities = [
        entity_id
        for entity_id in entity_refs
        if entity_id not in players or players[entity_id].get("x_m") is None or players[entity_id].get("y_m") is None
    ]
    status = "PASS" if ball_present and not missing_entities else "UNKNOWN"
    reason = "tracking_available" if status == "PASS" else "tracking_evidence_missing"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": entity_refs,
        "tracking_quality_status": status,
        "tracking_quality_reason": reason,
        "tracking_quality_frame_id": quality_frame_id,
        "ball_position_present": ball_present,
        "expected_entity_ids": entity_refs,
        "missing_entity_ids": missing_entities,
    }


def pairwise_distance_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    entity_a_field: str,
    entity_b_field: str,
    maximum_distance_m: float,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or frame_id is None:
        return None
    entity_a_id = str(anchor.get(entity_a_field) or "")
    point_a = tracked_point_at_frame(state, frame_id, entity_a_id)
    point_b = ball_point_at_frame(state, frame_id) if entity_b_field == "ball" else tracked_point_at_frame(state, frame_id, str(anchor.get(entity_b_field) or ""))
    if not entity_a_id or point_a is None or point_b is None:
        status = "UNKNOWN"
        reason = "pairwise_tracking_missing"
        distance = None
    else:
        distance = math.dist(point_a, point_b)
        status = "PASS" if distance <= maximum_distance_m else "FAIL"
        reason = "distance_within_threshold" if status == "PASS" else "distance_exceeds_threshold"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "pairwise_distance_status": status,
        "pairwise_distance_reason": reason,
        "distance_frame_id": frame_id,
        "entity_a_field": entity_a_field,
        "entity_a_id": entity_a_id or None,
        "entity_b_field": entity_b_field,
        "entity_b_id": "ball" if entity_b_field == "ball" else anchor.get(entity_b_field),
        "distance_m": None if distance is None else round(float(distance), 3),
        "maximum_distance_m": maximum_distance_m,
        "entity_a_point": None if point_a is None else {"x_m": point_a[0], "y_m": point_a[1]},
        "entity_b_point": None if point_b is None else {"x_m": point_b[0], "y_m": point_b[1]},
    }


def velocity_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    entity_id_field: str,
    lookback_seconds: float,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or frame_id is None:
        return None
    entity_id = str(anchor.get(entity_id_field) or "")
    sample = velocity_sample(
        state=state,
        frame_id=frame_id,
        entity_id=entity_id,
        lookback_seconds=lookback_seconds,
    )
    status = "PASS" if sample.get("speed_mps") is not None else "UNKNOWN"
    reason = "velocity_observed" if status == "PASS" else str(sample.get("reason") or "velocity_evidence_missing")
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "velocity_status": status,
        "velocity_reason": reason,
        "velocity_frame_id": frame_id,
        "velocity_entity_id": entity_id,
        **sample,
    }


def velocity_sample(
    *,
    state: PeriodState,
    frame_id: int,
    entity_id: str,
    lookback_seconds: float,
) -> dict[str, Any]:
    lookback_frames = max(1, int(math.ceil(max(lookback_seconds, 0.04) * FRAME_RATE_HZ - 1e-9)))
    prior_frame_id = int(frame_id) - lookback_frames
    current = tracked_point_at_frame(state, int(frame_id), entity_id)
    previous = tracked_point_at_frame(state, prior_frame_id, entity_id)
    dt_seconds = lookback_frames / FRAME_RATE_HZ
    base = {
        "velocity_lookback_frames": lookback_frames,
        "velocity_dt_seconds": round(float(dt_seconds), 3),
        "velocity_prior_frame_id": prior_frame_id,
        "velocity_vx_mps": None,
        "velocity_vy_mps": None,
        "speed_mps": None,
    }
    if not entity_id:
        return {**base, "reason": "entity_id_missing"}
    if current is None or previous is None:
        return {**base, "reason": "tracking_endpoint_missing"}
    vx = (float(current[0]) - float(previous[0])) / dt_seconds
    vy = (float(current[1]) - float(previous[1])) / dt_seconds
    speed = math.hypot(vx, vy)
    return {
        **base,
        "velocity_vx_mps": round(float(vx), 3),
        "velocity_vy_mps": round(float(vy), 3),
        "speed_mps": round(float(speed), 3),
        "current_point": point_from_xy(current[0], current[1]),
        "previous_point": point_from_xy(previous[0], previous[1]),
    }


def acceleration_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    entity_id_field: str,
    lookback_seconds: float,
    minimum_abs_delta_speed_mps: float,
    minimum_abs_acceleration_mps2: float,
    maximum_player_speed_mps: float,
    maximum_abs_acceleration_mps2: float,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or frame_id is None:
        return None
    entity_id = str(anchor.get(entity_id_field) or "")
    sample = acceleration_sample(
        state=state,
        frame_id=frame_id,
        entity_id=entity_id,
        lookback_seconds=lookback_seconds,
        minimum_abs_delta_speed_mps=minimum_abs_delta_speed_mps,
        minimum_abs_acceleration_mps2=minimum_abs_acceleration_mps2,
        maximum_player_speed_mps=maximum_player_speed_mps,
        maximum_abs_acceleration_mps2=maximum_abs_acceleration_mps2,
    )
    common_status = str(sample.get("acceleration_observation_status") or "UNKNOWN")
    reason = str(sample.get("acceleration_reason") or "acceleration_evidence_missing")
    delta_speed = sample.get("delta_speed_mps")
    acceleration_status = "UNKNOWN"
    deceleration_status = "UNKNOWN"
    if common_status == "PASS" and delta_speed is not None:
        acceleration_status = "PASS" if float(delta_speed) > 0 else "FAIL"
        deceleration_status = "PASS" if float(delta_speed) < 0 else "FAIL"
    elif common_status == "FAIL":
        acceleration_status = "FAIL"
        deceleration_status = "FAIL"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "acceleration_status": acceleration_status,
        "deceleration_status": deceleration_status,
        "acceleration_reason": reason,
        "acceleration_frame_id": frame_id,
        "acceleration_entity_id": entity_id,
        **sample,
    }


def acceleration_sample(
    *,
    state: PeriodState,
    frame_id: int,
    entity_id: str,
    lookback_seconds: float,
    minimum_abs_delta_speed_mps: float,
    minimum_abs_acceleration_mps2: float,
    maximum_player_speed_mps: float,
    maximum_abs_acceleration_mps2: float,
) -> dict[str, Any]:
    lookback_frames = max(1, int(math.ceil(max(lookback_seconds, 0.04) * FRAME_RATE_HZ - 1e-9)))
    previous_velocity_frame_id = int(frame_id) - lookback_frames
    previous_sample = velocity_sample(
        state=state,
        frame_id=previous_velocity_frame_id,
        entity_id=entity_id,
        lookback_seconds=lookback_seconds,
    )
    current_sample = velocity_sample(
        state=state,
        frame_id=int(frame_id),
        entity_id=entity_id,
        lookback_seconds=lookback_seconds,
    )
    dt_seconds = lookback_frames / FRAME_RATE_HZ
    model = "speed_delta_between_two_non_overlapping_displacement_velocity_windows"
    smoothing_policy = "two_window_mean_displacement_velocity_no_additional_smoothing"
    noise_policy = (
        "UNKNOWN if either velocity window lacks tracking endpoints or if observed speed/acceleration "
        "exceeds frozen plausibility limits; second derivatives amplify tracking noise."
    )
    base = {
        "acceleration_observation_status": "UNKNOWN",
        "acceleration_reason": "acceleration_evidence_missing",
        "acceleration_dt_seconds": round(float(dt_seconds), 3),
        "acceleration_lookback_frames": lookback_frames,
        "previous_velocity_frame_id": previous_velocity_frame_id,
        "current_velocity_frame_id": int(frame_id),
        "previous_speed_mps": previous_sample.get("speed_mps"),
        "current_speed_mps": current_sample.get("speed_mps"),
        "delta_speed_mps": None,
        "acceleration_mps2": None,
        "minimum_abs_delta_speed_mps": round(float(minimum_abs_delta_speed_mps), 3),
        "minimum_abs_acceleration_mps2": round(float(minimum_abs_acceleration_mps2), 3),
        "maximum_player_speed_mps": round(float(maximum_player_speed_mps), 3),
        "maximum_abs_acceleration_mps2": round(float(maximum_abs_acceleration_mps2), 3),
        "acceleration_model": model,
        "smoothing_policy": smoothing_policy,
        "noise_policy": noise_policy,
        "tracking_quality_status": "UNKNOWN",
        "coverage_status": "UNKNOWN",
        "acceleration_verdict_bias": "conservative_for_acceleration_and_deceleration_under_tracking_noise",
    }
    if not entity_id:
        return {**base, "acceleration_reason": "entity_id_missing"}
    previous_speed = previous_sample.get("speed_mps")
    current_speed = current_sample.get("speed_mps")
    if previous_speed is None or current_speed is None:
        return {**base, "acceleration_reason": "tracking_endpoint_missing"}
    if max(float(previous_speed), float(current_speed)) > maximum_player_speed_mps:
        return {**base, "acceleration_reason": "implausible_velocity_endpoint"}
    delta_speed = float(current_speed) - float(previous_speed)
    acceleration = delta_speed / dt_seconds
    if abs(acceleration) > maximum_abs_acceleration_mps2:
        return {
            **base,
            "delta_speed_mps": round(float(delta_speed), 3),
            "acceleration_mps2": round(float(acceleration), 3),
            "acceleration_reason": "acceleration_noise_exceeds_plausibility_limit",
        }
    if abs(delta_speed) < minimum_abs_delta_speed_mps or abs(acceleration) < minimum_abs_acceleration_mps2:
        status = "FAIL"
        reason = "speed_change_below_threshold"
    else:
        status = "PASS"
        reason = "speed_change_observed"
    return {
        **base,
        "acceleration_observation_status": status,
        "acceleration_reason": reason,
        "tracking_quality_status": "PASS",
        "coverage_status": "PASS",
        "delta_speed_mps": round(float(delta_speed), 3),
        "acceleration_mps2": round(float(acceleration), 3),
        "previous_velocity_sample": previous_sample,
        "current_velocity_sample": current_sample,
    }


def primitive_join_episode_sets(state: PeriodState, node: BoundCatalogNode) -> None:
    left_records = runtime_records(catalog_input_value(state, node, "left_episodes"))
    right_records = runtime_records(catalog_input_value(state, node, "right_episodes"))
    left_key_field = node_parameter_text(node, "left_key_field")
    right_key_field = node_parameter_text(node, "right_key_field")
    left_status_field = node_parameter_text(node, "left_status_field")
    right_status_field = node_parameter_text(node, "right_status_field")
    required_status_value = node_parameter_text(node, "required_status_value")
    temporal_relation = node_parameter_text(node, "temporal_relation")
    left_time_field = node_parameter_text(node, "left_time_field")
    right_time_field = node_parameter_text(node, "right_time_field")
    maximum_gap_seconds = node_parameter_number(node, "maximum_gap_seconds")
    distinct_entity_fields = node_parameter_text(node, "distinct_entity_fields")
    same_entity_fields = node_parameter_text(node, "same_entity_fields")

    right_by_key: dict[str, list[dict[str, Any]]] = {}
    for right in right_records:
        key = right.get(right_key_field)
        if key is None:
            continue
        right_by_key.setdefault(str(key), []).append(right)

    records = [
        join_episode_sets_record(
            state=state,
            node=node,
            left_record=left,
            right_by_key=right_by_key,
            left_key_field=left_key_field,
            right_key_field=right_key_field,
            left_status_field=left_status_field,
            right_status_field=right_status_field,
            required_status_value=required_status_value,
            temporal_relation=temporal_relation,
            left_time_field=left_time_field,
            right_time_field=right_time_field,
            maximum_gap_seconds=maximum_gap_seconds,
            distinct_entity_fields=distinct_entity_fields,
            same_entity_fields=same_entity_fields,
        )
        for left in left_records
        if isinstance(left, dict)
    ]
    records = [record for record in records if record is not None]
    episodes = [record for record in records if str(record.get("join_status")) == "PASS"]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "episodes": episodes,
        "episodes_records": episodes,
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "join_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if str(record["join_status"]) == "UNKNOWN" else str(record["join_status"])
                for record in records
            ],
            unknown_mask=[str(record["join_status"]) == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "join_status").entity_scope,
        ),
        "join_status_records": records,
    }


def join_episode_sets_record(
    *,
    state: PeriodState,
    node: BoundCatalogNode,
    left_record: dict[str, Any],
    right_by_key: dict[str, list[dict[str, Any]]],
    left_key_field: str,
    right_key_field: str,
    left_status_field: str,
    right_status_field: str,
    required_status_value: str,
    temporal_relation: str,
    left_time_field: str,
    right_time_field: str,
    maximum_gap_seconds: float,
    distinct_entity_fields: str,
    same_entity_fields: str,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(left_record.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    left_key = left_record.get(left_key_field)
    matches = [] if left_key is None else right_by_key.get(str(left_key), [])
    right_record = matches[0] if len(matches) == 1 else None
    status = "UNKNOWN"
    reason = "join_evidence_missing"
    if not status_satisfies_join(left_record, left_status_field, required_status_value):
        status, reason = join_status_failure(left_record, "left", left_status_field, required_status_value)
    elif left_key is None:
        reason = "left_join_key_missing"
    elif not matches:
        status = "FAIL"
        reason = "right_join_key_not_found"
    elif len(matches) > 1:
        reason = "right_join_key_not_unique"
    elif right_record is None:
        reason = "right_record_missing"
    elif not status_satisfies_join(right_record, right_status_field, required_status_value):
        status, reason = join_status_failure(right_record, "right", right_status_field, required_status_value)
    else:
        status, reason = temporal_join_status(
            left_record=left_record,
            right_record=right_record,
            temporal_relation=temporal_relation,
            left_time_field=left_time_field,
            right_time_field=right_time_field,
            maximum_gap_seconds=maximum_gap_seconds,
        )
        if status == "PASS":
            status, reason = distinct_join_status(
                joined=project_joined_record(left_record, right_record),
                distinct_entity_fields=distinct_entity_fields,
            )
        if status == "PASS":
            status, reason = same_entity_join_status(
                joined=project_joined_record(left_record, right_record),
                same_entity_fields=same_entity_fields,
            )
    joined = project_joined_record(left_record, right_record)
    distinct_fields = parse_distinct_entity_fields(distinct_entity_fields)
    distinct_values = {field: joined.get(field) for field in distinct_fields}
    same_pairs = parse_same_entity_fields(same_entity_fields)
    same_values = {
        f"{left_field}={right_field}": {
            left_field: joined.get(left_field),
            right_field: joined.get(right_field),
        }
        for left_field, right_field in same_pairs
    }
    entity_refs = combined_entity_refs(left_record, right_record)
    start_frame_id = optional_int(left_record.get("start_frame_id")) or anchor_frame_id
    end_frame_id = optional_int(left_record.get("end_frame_id")) or anchor_frame_id
    if right_record is not None:
        right_end = optional_int(right_record.get("end_frame_id")) or optional_int(right_record.get("anchor_frame_id"))
        if right_end is not None:
            end_frame_id = max(end_frame_id, right_end)
    anchor_id = anchor_record_id(
        match_id=state.match_id,
        period=state.period,
        anchor_frame_id=anchor_frame_id,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        entity_refs=entity_refs,
    )
    return {
        **joined,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": anchor_id,
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "entity_refs": entity_refs,
        "join_node_id": node.node_id,
        "join_status": status,
        "join_reason": reason,
        "join_mode": "inner_by_key",
        "left_key_field": left_key_field,
        "right_key_field": right_key_field,
        "join_key": None if left_key is None else str(left_key),
        "left_anchor_id": left_record.get("anchor_id"),
        "right_anchor_id": None if right_record is None else right_record.get("anchor_id"),
        "left_status_field": left_status_field,
        "right_status_field": right_status_field,
        "required_status_value": required_status_value,
        "temporal_relation": temporal_relation,
        "left_time_field": left_time_field,
        "right_time_field": right_time_field,
        "left_time_frame_id": optional_int(left_record.get(left_time_field)),
        "right_time_frame_id": None if right_record is None else optional_int(right_record.get(right_time_field)),
        "temporal_gap_seconds": temporal_gap_seconds(left_record, right_record, left_time_field, right_time_field),
        "maximum_gap_seconds": maximum_gap_seconds,
        "distinct_entity_fields": distinct_fields,
        "distinct_entity_values": distinct_values,
        "distinct_entities_status": distinct_entities_status(distinct_values),
        "same_entity_fields": same_entity_fields,
        "same_entity_values": same_values,
        "same_entity_status": same_entity_status(same_values),
        "right_match_count": len(matches),
    }


def status_satisfies_join(record: dict[str, Any], field: str, required: str) -> bool:
    if field == "none":
        return True
    value = record.get(field)
    return value is not None and str(value) == required


def join_status_failure(
    record: dict[str, Any],
    side: str,
    field: str,
    required: str,
) -> tuple[str, str]:
    if field == "none":
        return "PASS", "status_not_required"
    value = record.get(field)
    if value is None or str(value) == "UNKNOWN":
        return "UNKNOWN", f"{side}_{field}_unknown"
    return "FAIL", f"{side}_{field}_not_{required.lower()}"


def project_joined_record(
    left_record: dict[str, Any],
    right_record: dict[str, Any] | None,
) -> dict[str, Any]:
    joined = dict(left_record)
    if "join_status" in joined:
        joined["left_join_status"] = joined.get("join_status")
        joined["left_join_reason"] = joined.get("join_reason")
    if right_record is None:
        return joined
    for key, value in right_record.items():
        if key not in joined:
            joined[key] = value
            continue
        collision_key = f"right_{key}"
        suffix = 2
        while collision_key in joined:
            collision_key = f"right_{suffix}_{key}"
            suffix += 1
        joined[collision_key] = value
    return joined


def combined_entity_refs(
    left_record: dict[str, Any],
    right_record: dict[str, Any] | None,
) -> list[str]:
    refs: list[str] = []
    for record in (left_record, right_record or {}):
        for value in record.get("entity_refs") or []:
            if value is not None and str(value) not in refs:
                refs.append(str(value))
    return refs


def temporal_join_status(
    *,
    left_record: dict[str, Any],
    right_record: dict[str, Any],
    temporal_relation: str,
    left_time_field: str,
    right_time_field: str,
    maximum_gap_seconds: float,
) -> tuple[str, str]:
    if temporal_relation == "none":
        return "PASS", "join_key_matched"
    if temporal_relation == "overlaps":
        left_start = optional_int(left_record.get("start_frame_id"))
        left_end = optional_int(left_record.get("end_frame_id"))
        right_start = optional_int(right_record.get("start_frame_id"))
        right_end = optional_int(right_record.get("end_frame_id"))
        if None in {left_start, left_end, right_start, right_end}:
            return "UNKNOWN", "temporal_overlap_frame_missing"
        return (
            ("PASS", "join_key_matched_and_temporal_relation_satisfied")
            if left_start <= right_end and right_start <= left_end
            else ("FAIL", "temporal_overlap_not_satisfied")
        )
    left_frame = optional_int(left_record.get(left_time_field))
    right_frame = optional_int(right_record.get(right_time_field))
    if left_frame is None or right_frame is None:
        return "UNKNOWN", "temporal_frame_missing"
    gap_seconds = round((right_frame - left_frame) / FRAME_RATE_HZ, 3)
    if temporal_relation == "left_ends_before_right":
        if left_frame > right_frame:
            return "FAIL", "temporal_order_not_satisfied"
        if gap_seconds > maximum_gap_seconds:
            return "FAIL", "temporal_gap_exceeded"
        return "PASS", "join_key_matched_and_temporal_relation_satisfied"
    if temporal_relation == "left_starts_before_right":
        return (
            ("PASS", "join_key_matched_and_temporal_relation_satisfied")
            if left_frame <= right_frame
            else ("FAIL", "temporal_order_not_satisfied")
        )
    raise RuntimeError(f"Unsupported join_episode_sets temporal_relation={temporal_relation}")


def temporal_gap_seconds(
    left_record: dict[str, Any],
    right_record: dict[str, Any] | None,
    left_time_field: str,
    right_time_field: str,
) -> float | None:
    if right_record is None:
        return None
    left_frame = optional_int(left_record.get(left_time_field))
    right_frame = optional_int(right_record.get(right_time_field))
    if left_frame is None or right_frame is None:
        return None
    return round((right_frame - left_frame) / FRAME_RATE_HZ, 3)


def parse_distinct_entity_fields(value: str) -> list[str]:
    if value == "none":
        return []
    return [field.strip() for field in value.split(",") if field.strip()]


def parse_same_entity_fields(value: str) -> list[tuple[str, str]]:
    if value == "none":
        return []
    pairs: list[tuple[str, str]] = []
    for raw_pair in value.split(";"):
        if "=" not in raw_pair:
            continue
        left, right = raw_pair.split("=", 1)
        left = left.strip()
        right = right.strip()
        if left and right:
            pairs.append((left, right))
    return pairs


def distinct_join_status(joined: dict[str, Any], distinct_entity_fields: str) -> tuple[str, str]:
    fields = parse_distinct_entity_fields(distinct_entity_fields)
    if not fields:
        return "PASS", "join_key_matched"
    values = [joined.get(field) for field in fields]
    if any(value is None or str(value) == "" for value in values):
        return "UNKNOWN", "distinct_entity_field_missing"
    return (
        ("PASS", "join_key_matched_and_distinct_entities_satisfied")
        if len({str(value) for value in values}) == len(values)
        else ("FAIL", "distinct_entity_constraint_failed")
    )


def same_entity_join_status(joined: dict[str, Any], same_entity_fields: str) -> tuple[str, str]:
    pairs = parse_same_entity_fields(same_entity_fields)
    if not pairs:
        return "PASS", "join_key_matched"
    for left_field, right_field in pairs:
        left_value = joined.get(left_field)
        right_value = joined.get(right_field)
        if left_value is None or right_value is None or str(left_value) == "" or str(right_value) == "":
            return "UNKNOWN", "same_entity_field_missing"
        if str(left_value) != str(right_value):
            return "FAIL", "same_entity_constraint_failed"
    return "PASS", "join_key_matched_and_same_entity_satisfied"


def distinct_entities_status(values: dict[str, Any]) -> str:
    if not values:
        return "NOT_REQUIRED"
    if any(value is None or str(value) == "" for value in values.values()):
        return "UNKNOWN"
    return "PASS" if len({str(value) for value in values.values()}) == len(values) else "FAIL"


def same_entity_status(values: dict[str, dict[str, Any]]) -> str:
    if not values:
        return "NOT_REQUIRED"
    for pair_values in values.values():
        pair = list(pair_values.values())
        if len(pair) != 2 or any(value is None or str(value) == "" for value in pair):
            return "UNKNOWN"
        if str(pair[0]) != str(pair[1]):
            return "FAIL"
    return "PASS"


def primitive_lane_occupancy(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchor_records = anchor_value.value
    if not isinstance(anchor_records, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    frame_field = node_parameter_text(node, "frame_field")
    player_scope = node_parameter_text(node, "player_scope")
    required_occupied_lane_count = node_parameter_integer(
        node,
        "required_occupied_lane_count"
    )
    records = [
        lane_occupancy_anchor_record(
            state=state,
            anchor=anchor,
            frame_field=frame_field,
            player_scope=player_scope,
            required_occupied_lane_count=required_occupied_lane_count,
        )
        for anchor in anchor_records
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None
        if str(record["lane_occupancy_status"]) == "UNKNOWN"
        else str(record["lane_occupancy_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "lane_occupancy_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "lane_occupancy_status").entity_scope,
        ),
        "lane_occupancy_status_records": records,
    }


def lane_occupancy_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    player_scope: str,
    required_occupied_lane_count: int,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    lane_evaluation_frame_id = optional_int(anchor.get(frame_field))
    if lane_evaluation_frame_id is None and frame_field != "anchor_frame_id":
        lane_evaluation_frame_id = anchor_frame_id
    if anchor_frame_id is None or lane_evaluation_frame_id is None:
        return None
    if player_scope == "defending_outfield":
        team_role = state.defending_team_role
    elif player_scope == "perspective_outfield":
        team_role = state.perspective_team_role
    else:
        team_role = state.perspective_team_role
    observed_positions = cached_observed_outfield_positions_at_frame(
        state,
        lane_evaluation_frame_id,
        team_role,
        outfield_player_ids(state.canonical_root, state.match_id, team_role),
    )
    evaluation = evaluate_lane_occupancy(
        player_positions=observed_positions,
        anchor_id=str(anchor.get("anchor_id")),
        anchor_frame_id=anchor_frame_id,
        frame_id=lane_evaluation_frame_id,
        required_occupied_lane_count=required_occupied_lane_count,
        config=LaneOccupancyConfig(),
    )
    payload = evaluation.to_dict()
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "lane_occupancy_status": str(payload["status"]),
        "lane_occupancy_reason": payload["reason"],
        "lane_evaluation_frame_field": frame_field,
        "lane_evaluation_frame_id": lane_evaluation_frame_id,
        "lane_player_scope": player_scope,
        "lane_team_role": team_role,
        "occupied_lanes": list(payload["occupied_lanes"]),
        "occupied_lane_count": len(payload["occupied_lanes"]),
        "lane_counts": payload["lane_counts"],
        "frame_lane_counts": payload["frame_lane_counts"],
        "player_lane_assignments": payload["player_assignments"],
        "evaluated_player_ids": list(payload["evaluated_player_ids"]),
        "missing_player_ids": list(payload["missing_player_ids"]),
        "invalid_player_ids": list(payload["invalid_player_ids"]),
        "invalid_coordinate_player_ids": list(payload["invalid_coordinate_player_ids"]),
        "duplicate_player_ids": list(payload["duplicate_player_ids"]),
        "outside_lane_player_ids": list(payload["outside_lane_player_ids"]),
        "missing_frame_ids": list(payload["missing_frame_ids"]),
        "required_occupied_lane_count": payload["required_occupied_lane_count"],
        "requirement_aggregation": payload["requirement_aggregation"],
        "coverage_status": payload["coverage_status"],
        "lane_definitions": payload["lane_definitions"],
        "pitch_width_m": payload["pitch_width_m"],
        "coordinate_system": payload["coordinate_system"],
        "boundary_policy": payload["boundary_policy"],
        "tie_epsilon_m": payload["tie_epsilon_m"],
        "observed_player_count": len(observed_positions),
    }
