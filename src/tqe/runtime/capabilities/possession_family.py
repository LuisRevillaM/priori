"""Possession, space, set-piece, and outcome capability implementations.

F2-7 relocates the final possession/outcome family from executor.py without
changing behavior. Shared runtime helpers remain in executor.py until the
shared-kernel extraction phase.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
import pandas as pd

from tqe.evidence.observation_manifest import ObservationModality, gate_state_absence_status
from tqe.runtime.executor import (
    FRAME_RATE_HZ,
    PITCH_HALF_LENGTH_M,
    PITCH_HALF_WIDTH_M,
    PeriodState,
    RuntimeParameters,
    anchor_record_id,
    ball_point_at_frame,
    cached_observed_outfield_positions_at_frame,
    catalog_input_value,
    catalog_output,
    frame_match_time_ms,
    node_parameter_integer,
    node_parameter_number,
    node_parameter_text,
    optional_float,
    optional_int,
    outfield_player_ids,
    parquet_rows,
    point_from_xy,
    runtime_records,
    segment_true,
)
from tqe.runtime.controlled_pass import align_event_to_frame
from tqe.runtime.fragile_carrier_episode import EpisodeIdentityConfig, build_fragile_carrier_episodes
from tqe.runtime.ir import BoundCatalogNode, Unit
from tqe.runtime.one_touch import EVENT_COLUMNS
from tqe.runtime.pass_bypass import attack_x_sign_for
from tqe.runtime.possession_identity import possession_identity_at_frame
from tqe.runtime.values import FrameSignal


def primitive_fragile_carrier_episode(state: PeriodState, node: BoundCatalogNode) -> None:
    """Adapt certified pressure records to the pure CAR episode kernel."""
    value = catalog_input_value(state, node, "pressure_evaluations")
    source = runtime_records(value)
    observations: list[dict[str, Any]] = []
    for raw in source:
        record = dict(raw)
        frame_id = optional_int(record.get(node_parameter_text(node, "observation_frame_field")))
        frame_id = frame_id if frame_id is not None else optional_int(record.get("pressure_frame_id"))
        if frame_id is None:
            continue
        record["pressure_frame_id"] = frame_id
        record["match_id"] = str(record.get("match_id") or state.match_id)
        record["period"] = int(record.get("period") or state.period)
        record["team_role"] = str(record.get("team_role") or state.perspective_team_role)
        possession_field = node_parameter_text(node, "possession_id_field")
        possession_id = record.get(possession_field)
        if possession_id is None:
            possession_id = possession_identity_at_frame(state, frame_id, record["team_role"])
        record["possession_id"] = possession_id
        record["possession_status"] = record.get(
            "possession_status", "PASS" if possession_id is not None else "UNKNOWN"
        )
        record["match_time_ms"] = int(record.get("match_time_ms") or frame_match_time_ms(state, frame_id))
        carrier_field = node_parameter_text(node, "onset_carrier_id_field")
        if record.get("carrier_id") is None:
            record["carrier_id"] = record.get(carrier_field)
        pressure_field = node_parameter_text(node, "pressure_status_field")
        record["pressure_status"] = record.get(pressure_field, record.get("pressure_status", "UNKNOWN"))
        control_field = node_parameter_text(node, "carrier_control_status_field")
        record["carrier_control_status"] = record.get(control_field, "UNKNOWN")
        boundary_field = node_parameter_text(node, "boundary_status_field")
        record["episode_boundary_status"] = record.get(boundary_field, "FAIL")
        observations.append(record)
    episodes = build_fragile_carrier_episodes(
        observations,
        EpisodeIdentityConfig(
            same_episode_gap_tolerance_s=node_parameter_number(node, "same_episode_gap_tolerance_s"),
            refractory_after_resolution_s=node_parameter_number(node, "refractory_after_resolution_s"),
        ),
    )
    state.signals[node.node_id] = {
        "episodes": episodes,
        "attribution_status": FrameSignal(
            frame_ids=[int(item["onset_frame_id"]) for item in episodes],
            values=[item["attribution_status"] if item["attribution_status"] != "UNKNOWN" else None for item in episodes],
            unknown_mask=[item["attribution_status"] == "UNKNOWN" for item in episodes],
            unit=node.outputs[1].unit,
            entity_scope=node.outputs[1].entity_scope,
        ),
    }


def primitive_possession_segment(state: PeriodState, node: BoundCatalogNode) -> None:
    possession_mask = (
        state.possession_role == state.perspective_team_role
    ) & _known_ball_alive_mask(state.ball_alive)
    minimum_frames = int(round(state.params.number("minimum_possession_seconds") * state.params.integer("analysis_rate_hz")))
    segments = [
        {
            "anchor_id": anchor_record_id(
                match_id=state.match_id,
                period=state.period,
                anchor_frame_id=int(state.frame_ids[start]),
                start_frame_id=int(state.frame_ids[start]),
                end_frame_id=int(state.frame_ids[end]),
                entity_refs=[state.perspective_team_id],
            ),
            "match_id": state.match_id,
            "period": state.period,
            "anchor_frame_id": int(state.frame_ids[start]),
            "start_index": start,
            "end_index": end,
            "start_frame_id": int(state.frame_ids[start]),
            "end_frame_id": int(state.frame_ids[end]),
            "possession_start_frame_id": int(state.frame_ids[start]),
            "possession_end_frame_id": int(state.frame_ids[end]),
            "possession_duration_seconds": round(
                float((end - start + 1) / state.params.integer("analysis_rate_hz")),
                3,
            ),
            "entity_refs": [state.perspective_team_id],
        }
        for start, end in segment_true(possession_mask, minimum_frames)
    ]
    state.signals[node.node_id] = {"episodes": segments, "anchors": segments}


def relation_possession_segment_team_keyed_episodes(state: PeriodState, node: BoundCatalogNode) -> None:
    segments_value = catalog_input_value(state, node, "possession_segments")
    segments = segments_value.value
    if not isinstance(segments, list):
        raise RuntimeError(f"{node.node_id} requires possession_segments records")
    records = []
    for item in segments:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        record["team_role"] = state.perspective_team_role
        records.append(record)
    state.signals[node.node_id] = {
        "episodes": records,
        "episodes_records": records,
    }


def primitive_transition_anchor(state: PeriodState, node: BoundCatalogNode) -> None:
    transition_type = node_parameter_text(node, "transition_type")
    minimum_prior_possession_seconds = node_parameter_number(node, "minimum_prior_possession_seconds")
    zone_filter = node_parameter_text(node, "zone_filter")
    zone_boundary_buffer_m = node_parameter_number(node, "zone_boundary_buffer_m")
    if transition_type not in {"regain", "loss"}:
        raise RuntimeError(f"Unsupported transition_type {transition_type}")
    if zone_filter not in {"any", "own_half", "attacking_half", "middle_third", "final_third", "defensive_third"}:
        raise RuntimeError(f"Unsupported transition zone_filter {zone_filter}")
    analysis_rate_hz = state.params.integer("analysis_rate_hz")
    prior_frames_required = max(1, int(math.ceil(minimum_prior_possession_seconds * analysis_rate_hz - 1e-9)))
    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    attack_x_sign = attack_x_sign_for(
        orientation,
        state.match_id,
        state.period,
        state.perspective_team_role,
    )
    records: list[dict[str, Any]] = []
    previous_role_required = state.defending_team_role if transition_type == "regain" else state.perspective_team_role
    new_role_required = state.perspective_team_role if transition_type == "regain" else state.defending_team_role
    for idx in range(1, len(state.frame_ids)):
        previous_raw = state.possession_role[idx - 1]
        new_raw = state.possession_role[idx]
        alive_raw = state.ball_alive[idx]
        frame_id = int(state.frame_ids[idx])
        previous_frame_id = int(state.frame_ids[idx - 1])
        if any(_tracking_value_unknown(value) for value in (previous_raw, new_raw, alive_raw)):
            zone = zone_evaluation_at_frame(
                state=state,
                frame_id=frame_id,
                zone_name=zone_filter if zone_filter != "any" else "any",
                attack_x_sign=attack_x_sign,
                zone_boundary_buffer_m=zone_boundary_buffer_m,
            )
            entity_refs = [state.perspective_team_id]
            records.append(
                {
                    "anchor_id": anchor_record_id(
                        match_id=state.match_id,
                        period=state.period,
                        anchor_frame_id=frame_id,
                        start_frame_id=previous_frame_id,
                        end_frame_id=frame_id,
                        entity_refs=entity_refs,
                    ),
                    "match_id": state.match_id,
                    "period": state.period,
                    "anchor_frame_id": frame_id,
                    "start_frame_id": previous_frame_id,
                    "end_frame_id": frame_id,
                    "entity_refs": entity_refs,
                    "transition_status": "UNKNOWN",
                    "transition_reason": "possession_or_ball_evidence_unknown",
                    "transition_type": transition_type,
                    "possession_id": None,
                    "transition_frame_id": frame_id,
                    "previous_frame_id": previous_frame_id,
                    "previous_team_role": previous_role_required,
                    "new_team_role": new_role_required,
                    "observed_previous_team_role": None,
                    "observed_new_team_role": None,
                    "prior_possession_frame_count": 0,
                    "minimum_prior_possession_seconds": minimum_prior_possession_seconds,
                    "transition_match_time_ms": frame_match_time_ms(state, frame_id),
                    "attacking_direction": attack_x_sign,
                    **zone,
                }
            )
            continue
        previous_role = str(previous_raw)
        new_role = str(new_raw)
        if previous_role != previous_role_required or new_role != new_role_required:
            continue
        prior_start = max(0, idx - prior_frames_required)
        prior_slice = state.possession_role[prior_start:idx]
        prior_alive = state.ball_alive[prior_start:idx]
        prior_complete = (
            len(prior_slice) >= prior_frames_required
            and bool(np.all(prior_slice == previous_role_required))
            and bool(np.all(prior_alive))
        )
        transition_alive = bool(state.ball_alive[idx])
        zone = zone_evaluation_at_frame(
            state=state,
            frame_id=frame_id,
            zone_name=zone_filter if zone_filter != "any" else "any",
            attack_x_sign=attack_x_sign,
            zone_boundary_buffer_m=zone_boundary_buffer_m,
        )
        status = "PASS"
        reason = "transition_observed"
        if not transition_alive:
            status = "UNKNOWN"
            reason = "transition_frame_not_ball_alive"
        elif not prior_complete:
            status = "UNKNOWN"
            reason = "prior_possession_window_incomplete"
        elif zone_filter != "any" and zone["zone_status"] != "PASS":
            status = zone["zone_status"]
            reason = f"zone_{zone['zone_reason']}"
        entity_refs = [state.perspective_team_id]
        anchor_id = anchor_record_id(
            match_id=state.match_id,
            period=state.period,
            anchor_frame_id=frame_id,
            start_frame_id=previous_frame_id,
            end_frame_id=frame_id,
            entity_refs=entity_refs,
        )
        records.append(
            {
                "anchor_id": anchor_id,
                "match_id": state.match_id,
                "period": state.period,
                "anchor_frame_id": frame_id,
                "start_frame_id": previous_frame_id,
                "end_frame_id": frame_id,
                "entity_refs": entity_refs,
                "transition_status": status,
                "transition_reason": reason,
                "transition_type": transition_type,
                "possession_id": possession_identity_at_frame(state, frame_id, new_role),
                "transition_frame_id": frame_id,
                "previous_frame_id": previous_frame_id,
                "previous_team_role": previous_role,
                "new_team_role": new_role,
                "prior_possession_frame_count": int(len(prior_slice)),
                "minimum_prior_possession_seconds": minimum_prior_possession_seconds,
                "transition_match_time_ms": frame_match_time_ms(state, frame_id),
                "attacking_direction": attack_x_sign,
                **zone,
            }
        )
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "transition_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["transition_status"] == "UNKNOWN" else record["transition_status"]
                for record in records
            ],
            unknown_mask=[record["transition_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "transition_status").entity_scope,
        ),
        "transition_status_records": records,
    }


def _tracking_value_unknown(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _known_ball_alive_mask(values: np.ndarray) -> np.ndarray:
    return np.asarray(
        [False if _tracking_value_unknown(value) else bool(value) for value in values],
        dtype=bool,
    )


def primitive_structured_zone(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchors = runtime_records(anchor_value)
    frame_field = node_parameter_text(node, "frame_field")
    zone_name = node_parameter_text(node, "zone_name")
    zone_boundary_buffer_m = node_parameter_number(node, "zone_boundary_buffer_m")
    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    attack_x_sign = attack_x_sign_for(
        orientation,
        state.match_id,
        state.period,
        state.perspective_team_role,
    )
    records: list[dict[str, Any]] = []
    for anchor in anchors:
        frame_id = optional_int(anchor.get(frame_field)) or optional_int(anchor.get("anchor_frame_id"))
        anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
        if frame_id is None or anchor_frame_id is None:
            continue
        zone = zone_evaluation_at_frame(
            state=state,
            frame_id=frame_id,
            zone_name=zone_name,
            attack_x_sign=attack_x_sign,
            zone_boundary_buffer_m=zone_boundary_buffer_m,
        )
        records.append(
            {
                **anchor,
                "match_id": state.match_id,
                "period": state.period,
                "anchor_id": str(anchor.get("anchor_id")),
                "anchor_frame_id": anchor_frame_id,
                "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
                "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
                "entity_refs": list(anchor.get("entity_refs") or []),
                "zone_frame_field": frame_field,
                "zone_frame_id": frame_id,
                "attacking_direction": attack_x_sign,
                **zone,
            }
        )
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "zone_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["zone_status"] == "UNKNOWN" else record["zone_status"]
                for record in records
            ],
            unknown_mask=[record["zone_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "zone_status").entity_scope,
        ),
        "zone_status_records": records,
    }


def primitive_space_region_generation(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchors = runtime_records(anchor_value)
    frame_field = node_parameter_text(node, "frame_field")
    zone_scope = node_parameter_text(node, "zone_scope")
    grid_step_m = node_parameter_number(node, "grid_step_m")
    minimum_opponent_distance_m = node_parameter_number(node, "minimum_opponent_distance_m")
    minimum_teammate_distance_m = node_parameter_number(node, "minimum_teammate_distance_m")
    minimum_open_points = node_parameter_integer(node, "minimum_open_points")
    maximum_candidate_points = node_parameter_integer(node, "maximum_candidate_points")
    minimum_observed_players_per_team = node_parameter_integer(node, "minimum_observed_players_per_team")
    records = [
        space_region_generation_anchor_record(
            state=state,
            anchor=anchor,
            frame_field=frame_field,
            zone_scope=zone_scope,
            grid_step_m=grid_step_m,
            minimum_opponent_distance_m=minimum_opponent_distance_m,
            minimum_teammate_distance_m=minimum_teammate_distance_m,
            minimum_open_points=minimum_open_points,
            maximum_candidate_points=maximum_candidate_points,
            minimum_observed_players_per_team=minimum_observed_players_per_team,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    values = [
        None if record["open_space_status"] == "UNKNOWN" else record["open_space_status"]
        for record in records
    ]
    count_values = [
        None if record["open_space_status"] == "UNKNOWN" else int(record.get("open_space_region_count") or 0)
        for record in records
    ]
    point_values = [
        record.get("representative_open_space_point")
        if record["open_space_status"] == "PASS"
        else None
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "open_space_status": FrameSignal(
            frame_ids=frame_ids,
            values=values,
            unknown_mask=[value is None for value in values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "open_space_status").entity_scope,
        ),
        "open_space_status_records": records,
        "open_space_region_count": FrameSignal(
            frame_ids=frame_ids,
            values=count_values,
            unknown_mask=[value is None for value in count_values],
            unit=Unit.COUNT,
            entity_scope=catalog_output(node, "open_space_region_count").entity_scope,
        ),
        "open_space_region_count_records": records,
        "representative_open_space_point": FrameSignal(
            frame_ids=frame_ids,
            values=point_values,
            unknown_mask=[value is None for value in point_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "representative_open_space_point").entity_scope,
        ),
        "representative_open_space_point_records": records,
    }


def primitive_outcome_window(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchors = runtime_records(anchor_value)
    maximum_window_seconds = node_parameter_number(node, "maximum_window_seconds")
    minimum_settled_possession_seconds = node_parameter_number(node, "minimum_settled_possession_seconds")
    required_anchor_status_field = node_parameter_text(node, "required_anchor_status_field")
    required_anchor_status_value = node_parameter_text(node, "required_anchor_status_value")
    records = [
        outcome_window_anchor_record(
            state=state,
            anchor=anchor,
            maximum_window_seconds=maximum_window_seconds,
            minimum_settled_possession_seconds=minimum_settled_possession_seconds,
            required_anchor_status_field=required_anchor_status_field,
            required_anchor_status_value=required_anchor_status_value,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "outcome_window_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["outcome_window_status"] == "UNKNOWN" else record["outcome_window_status"]
                for record in records
            ],
            unknown_mask=[record["outcome_window_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "outcome_window_status").entity_scope,
        ),
        "outcome_window_status_records": records,
        "possession_phase_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["possession_phase_status"] == "UNKNOWN" else record["possession_phase_status"]
                for record in records
            ],
            unknown_mask=[record["possession_phase_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "possession_phase_status").entity_scope,
        ),
        "possession_phase_status_records": records,
    }


def zone_evaluation_at_frame(
    *,
    state: PeriodState,
    frame_id: int,
    zone_name: str,
    attack_x_sign: int | None,
    zone_boundary_buffer_m: float,
) -> dict[str, Any]:
    ball_point = ball_point_at_frame(state, frame_id)
    if attack_x_sign not in {-1, 1}:
        return {
            "zone_name": zone_name,
            "zone_status": "UNKNOWN",
            "zone_reason": "attacking_direction_invalid",
            "zone_ball_x_m": None,
            "zone_ball_y_m": None,
            "zone_normalized_ball_x_m": None,
            "zone_boundary_buffer_m": zone_boundary_buffer_m,
        }
    if ball_point is None:
        return {
            "zone_name": zone_name,
            "zone_status": "UNKNOWN",
            "zone_reason": "ball_position_missing",
            "zone_ball_x_m": None,
            "zone_ball_y_m": None,
            "zone_normalized_ball_x_m": None,
            "zone_boundary_buffer_m": zone_boundary_buffer_m,
        }
    x_m = float(ball_point[0])
    y_m = float(ball_point[1])
    normalized_x = x_m * int(attack_x_sign)
    buffer_m = max(0.0, zone_boundary_buffer_m)
    status = "FAIL"
    reason = "outside_declared_zone"
    if zone_name == "any":
        status = "PASS"
        reason = "zone_not_filtered"
    elif zone_name == "own_half":
        if normalized_x < -buffer_m:
            status = "PASS"
            reason = "ball_in_own_half"
        elif abs(normalized_x) <= buffer_m:
            status = "UNKNOWN"
            reason = "ball_near_halfway_boundary"
    elif zone_name == "attacking_half":
        if normalized_x > buffer_m:
            status = "PASS"
            reason = "ball_in_attacking_half"
        elif abs(normalized_x) <= buffer_m:
            status = "UNKNOWN"
            reason = "ball_near_halfway_boundary"
    elif zone_name == "defensive_third":
        threshold = -PITCH_HALF_LENGTH_M / 3.0
        if normalized_x < threshold - buffer_m:
            status = "PASS"
            reason = "ball_in_defensive_third"
        elif abs(normalized_x - threshold) <= buffer_m:
            status = "UNKNOWN"
            reason = "ball_near_third_boundary"
    elif zone_name == "middle_third":
        threshold = PITCH_HALF_LENGTH_M / 3.0
        if -threshold + buffer_m < normalized_x < threshold - buffer_m:
            status = "PASS"
            reason = "ball_in_middle_third"
        elif abs(abs(normalized_x) - threshold) <= buffer_m:
            status = "UNKNOWN"
            reason = "ball_near_third_boundary"
    elif zone_name == "final_third":
        threshold = PITCH_HALF_LENGTH_M / 3.0
        if normalized_x > threshold + buffer_m:
            status = "PASS"
            reason = "ball_in_final_third"
        elif abs(normalized_x - threshold) <= buffer_m:
            status = "UNKNOWN"
            reason = "ball_near_third_boundary"
    else:
        status = "UNKNOWN"
        reason = "unsupported_zone_name"
    return {
        "zone_name": zone_name,
        "zone_status": status,
        "zone_reason": reason,
        "zone_ball_x_m": round(x_m, 3),
        "zone_ball_y_m": round(y_m, 3),
        "zone_normalized_ball_x_m": round(float(normalized_x), 3),
        "zone_boundary_buffer_m": zone_boundary_buffer_m,
    }


def space_region_generation_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    zone_scope: str,
    grid_step_m: float,
    minimum_opponent_distance_m: float,
    minimum_teammate_distance_m: float,
    minimum_open_points: int,
    maximum_candidate_points: int,
    minimum_observed_players_per_team: int,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or frame_id is None:
        return None
    model = "sampled_grid_distance_from_observed_outfield_players_v0_1"
    claim_boundary = (
        "Observed sampled open-space candidate geometry only; no space value, pitch control, creation, exploitation, "
        "player intent, tactical causation, or optimality claim."
    )
    perspective_team_role = str(anchor.get("team_role") or state.perspective_team_role)
    if perspective_team_role not in {"home", "away"}:
        perspective_team_role = state.perspective_team_role
    opponent_team_role = "away" if perspective_team_role == "home" else "home"
    perspective_ids = outfield_player_ids(state.canonical_root, state.match_id, perspective_team_role)
    opponent_ids = outfield_player_ids(state.canonical_root, state.match_id, opponent_team_role)
    perspective_positions = [
        item
        for item in cached_observed_outfield_positions_at_frame(state, frame_id, perspective_team_role, perspective_ids)
        if item.get("x_m") is not None and item.get("y_m") is not None
    ]
    opponent_positions = [
        item
        for item in cached_observed_outfield_positions_at_frame(state, frame_id, opponent_team_role, opponent_ids)
        if item.get("x_m") is not None and item.get("y_m") is not None
    ]
    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    attack_x_sign = attack_x_sign_for(orientation, state.match_id, state.period, perspective_team_role)

    def base(status: str, reason: str, *, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        candidates = candidates or []
        representative = candidates[0] if candidates else None
        return {
            **anchor,
            "match_id": state.match_id,
            "period": state.period,
            "anchor_id": str(anchor.get("anchor_id")),
            "anchor_frame_id": anchor_frame_id,
            "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
            "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
            "entity_refs": list(anchor.get("entity_refs") or []),
            "open_space_status": status,
            "open_space_reason": reason,
            "space_frame_field": frame_field,
            "space_frame_id": frame_id,
            "zone_scope": zone_scope,
            "grid_step_m": round(float(grid_step_m), 3),
            "minimum_opponent_distance_m": round(float(minimum_opponent_distance_m), 3),
            "minimum_teammate_distance_m": round(float(minimum_teammate_distance_m), 3),
            "minimum_open_points": int(minimum_open_points),
            "maximum_candidate_points": int(maximum_candidate_points),
            "minimum_observed_players_per_team": int(minimum_observed_players_per_team),
            "perspective_team_role": perspective_team_role,
            "opponent_team_role": opponent_team_role,
            "observed_teammate_count": len(perspective_positions),
            "observed_opponent_count": len(opponent_positions),
            "open_space_region_count": len(candidates),
            "representative_open_space_point": None
            if representative is None
            else point_from_xy(representative["x_m"], representative["y_m"]),
            "representative_nearest_opponent_distance_m": None
            if representative is None
            else representative["nearest_opponent_distance_m"],
            "representative_nearest_teammate_distance_m": None
            if representative is None
            else representative["nearest_teammate_distance_m"],
            "open_space_candidate_points": candidates[: max(0, int(maximum_candidate_points))],
            "space_region_model": model,
            "space_region_claim_boundary": claim_boundary,
            "coverage_status": "UNKNOWN" if status == "UNKNOWN" else "PASS",
        }

    if grid_step_m <= 0:
        return base("UNKNOWN", "invalid_grid_step")
    if attack_x_sign not in {-1, 1}:
        return base("UNKNOWN", "attacking_direction_missing")
    if len(perspective_positions) < max(1, minimum_observed_players_per_team):
        return base("UNKNOWN", "teammate_tracking_missing")
    if len(opponent_positions) < max(1, minimum_observed_players_per_team):
        return base("UNKNOWN", "opponent_tracking_missing")

    candidates = open_space_candidate_points(
        perspective_positions=perspective_positions,
        opponent_positions=opponent_positions,
        attack_x_sign=int(attack_x_sign),
        zone_scope=zone_scope,
        grid_step_m=grid_step_m,
        minimum_opponent_distance_m=minimum_opponent_distance_m,
        minimum_teammate_distance_m=minimum_teammate_distance_m,
        maximum_candidate_points=maximum_candidate_points,
    )
    if len(candidates) >= max(1, minimum_open_points):
        return base("PASS", "open_space_candidates_found", candidates=candidates)
    gated = gate_state_absence_status(
        state=state,
        start_frame_id=frame_id,
        end_frame_id=frame_id,
        modalities=(ObservationModality.PLAYER_TRACK,),
        status="FAIL",
        reason="open_space_threshold_not_met",
    )
    return base(gated.status, gated.reason, candidates=candidates)


def open_space_candidate_points(
    *,
    perspective_positions: list[dict[str, Any]],
    opponent_positions: list[dict[str, Any]],
    attack_x_sign: int,
    zone_scope: str,
    grid_step_m: float,
    minimum_opponent_distance_m: float,
    minimum_teammate_distance_m: float,
    maximum_candidate_points: int,
) -> list[dict[str, Any]]:
    teammate_points = [(float(item["x_m"]), float(item["y_m"])) for item in perspective_positions]
    opponent_points = [(float(item["x_m"]), float(item["y_m"])) for item in opponent_positions]
    scored: list[dict[str, Any]] = []
    for x_m in sampled_axis_values(-PITCH_HALF_LENGTH_M, PITCH_HALF_LENGTH_M, grid_step_m):
        for y_m in sampled_axis_values(-PITCH_HALF_WIDTH_M, PITCH_HALF_WIDTH_M, grid_step_m):
            if not point_in_space_zone_scope(x_m, y_m, zone_scope, attack_x_sign):
                continue
            nearest_opponent = min(math.dist((x_m, y_m), point) for point in opponent_points)
            nearest_teammate = min(math.dist((x_m, y_m), point) for point in teammate_points)
            if nearest_opponent < minimum_opponent_distance_m or nearest_teammate < minimum_teammate_distance_m:
                continue
            scored.append(
                {
                    "x_m": round(float(x_m), 3),
                    "y_m": round(float(y_m), 3),
                    "nearest_opponent_distance_m": round(float(nearest_opponent), 3),
                    "nearest_teammate_distance_m": round(float(nearest_teammate), 3),
                    "space_score": round(float(nearest_opponent + 0.5 * nearest_teammate), 3),
                }
            )
    scored.sort(key=lambda item: (-float(item["space_score"]), float(item["x_m"]) * -attack_x_sign, abs(float(item["y_m"]))))
    return scored[: max(0, int(maximum_candidate_points))]


def sampled_axis_values(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    value = float(start)
    while value <= float(stop) + 1e-9:
        values.append(round(value, 6))
        value += float(step)
    if values and values[-1] < stop:
        values.append(float(stop))
    return values


def point_in_space_zone_scope(x_m: float, y_m: float, zone_scope: str, attack_x_sign: int) -> bool:
    del y_m
    normalized_x = float(x_m) * int(attack_x_sign)
    if zone_scope == "any":
        return True
    if zone_scope == "attacking_half":
        return normalized_x > 0
    if zone_scope == "defensive_half":
        return normalized_x < 0
    if zone_scope == "final_third":
        return normalized_x > PITCH_HALF_LENGTH_M / 3.0
    if zone_scope == "middle_third":
        threshold = PITCH_HALF_LENGTH_M / 3.0
        return -threshold <= normalized_x <= threshold
    return True


def outcome_window_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    maximum_window_seconds: float,
    minimum_settled_possession_seconds: float,
    required_anchor_status_field: str,
    required_anchor_status_value: str,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    if required_anchor_status_field != "none":
        anchor_status = anchor.get(required_anchor_status_field)
        if anchor_status is None or str(anchor_status) == "UNKNOWN":
            return outcome_window_prefilter_record(
                state=state,
                anchor=anchor,
                anchor_frame_id=anchor_frame_id,
                maximum_window_seconds=maximum_window_seconds,
                minimum_settled_possession_seconds=minimum_settled_possession_seconds,
                required_anchor_status_field=required_anchor_status_field,
                required_anchor_status_value=required_anchor_status_value,
                status="UNKNOWN",
                reason="required_anchor_status_unknown",
            )
        if str(anchor_status) != required_anchor_status_value:
            return outcome_window_prefilter_record(
                state=state,
                anchor=anchor,
                anchor_frame_id=anchor_frame_id,
                maximum_window_seconds=maximum_window_seconds,
                minimum_settled_possession_seconds=minimum_settled_possession_seconds,
                required_anchor_status_field=required_anchor_status_field,
                required_anchor_status_value=required_anchor_status_value,
                status="FAIL",
                reason="required_anchor_status_not_met",
            )
    frame_index = analysis_frame_index(state).get(anchor_frame_id)
    if frame_index is None:
        return outcome_window_prefilter_record(
            state=state,
            anchor=anchor,
            anchor_frame_id=anchor_frame_id,
            maximum_window_seconds=maximum_window_seconds,
            minimum_settled_possession_seconds=minimum_settled_possession_seconds,
            required_anchor_status_field=required_anchor_status_field,
            required_anchor_status_value=required_anchor_status_value,
            status="UNKNOWN",
            reason="anchor_frame_not_in_analysis_stream",
        )
    analysis_rate_hz = state.params.integer("analysis_rate_hz")
    horizon_frames = max(1, int(math.ceil(maximum_window_seconds * analysis_rate_hz - 1e-9)))
    settled_frames = max(1, int(math.ceil(minimum_settled_possession_seconds * analysis_rate_hz - 1e-9)))
    end_index_exclusive = min(len(state.frame_ids), frame_index + horizon_frames + 1)
    window_roles = state.possession_role[frame_index:end_index_exclusive]
    window_alive = state.ball_alive[frame_index:end_index_exclusive]
    window_frame_ids = state.frame_ids[frame_index:end_index_exclusive]
    if len(window_frame_ids) < settled_frames:
        status = "UNKNOWN"
        reason = "outcome_window_incomplete"
        settled_start_frame_id = None
        settled_end_frame_id = None
        loss_frame_id = None
        stoppage_frame_id = None
    else:
        retained_mask = (window_roles == state.perspective_team_role) & window_alive
        segments = segment_true(retained_mask, settled_frames)
        settled_segment = segments[0] if segments else None
        loss_indices = np.where((window_roles != state.perspective_team_role) & window_alive)[0]
        dead_indices = np.where(~window_alive)[0]
        loss_frame_id = int(window_frame_ids[int(loss_indices[0])]) if len(loss_indices) else None
        stoppage_frame_id = int(window_frame_ids[int(dead_indices[0])]) if len(dead_indices) else None
        if settled_segment is not None:
            start, end = settled_segment
            status = "PASS"
            reason = "settled_possession_window_observed"
            settled_start_frame_id = int(window_frame_ids[start])
            settled_end_frame_id = int(window_frame_ids[end])
        elif loss_frame_id is not None:
            status = "FAIL"
            reason = "possession_lost_before_settled_window"
            settled_start_frame_id = None
            settled_end_frame_id = None
        elif stoppage_frame_id is not None:
            status = "FAIL"
            reason = "stoppage_before_settled_window"
            settled_start_frame_id = None
            settled_end_frame_id = None
        elif end_index_exclusive >= len(state.frame_ids):
            status = "UNKNOWN"
            reason = "period_ended_before_outcome_window_complete"
            settled_start_frame_id = None
            settled_end_frame_id = None
        else:
            status = "FAIL"
            reason = "settled_threshold_not_met_within_window"
            settled_start_frame_id = None
            settled_end_frame_id = None
    outcome_window_end_frame_id = int(window_frame_ids[-1]) if len(window_frame_ids) else anchor_frame_id
    if status == "FAIL" and reason == "settled_threshold_not_met_within_window":
        gated = gate_state_absence_status(
            state=state,
            start_frame_id=anchor_frame_id,
            end_frame_id=outcome_window_end_frame_id,
            modalities=(ObservationModality.BALL, ObservationModality.POSSESSION),
            status=status,
            reason=reason,
        )
        status, reason = gated.status, gated.reason
    possession_phase_status = "SETTLED" if status == "PASS" else ("UNKNOWN" if status == "UNKNOWN" else "NOT_SETTLED")
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "outcome_window_status": status,
        "outcome_window_reason": reason,
        "possession_phase_status": possession_phase_status,
        "outcome_window_start_frame_id": anchor_frame_id,
        "outcome_window_end_frame_id": outcome_window_end_frame_id,
        "maximum_window_seconds": maximum_window_seconds,
        "minimum_settled_possession_seconds": minimum_settled_possession_seconds,
        "settled_start_frame_id": settled_start_frame_id,
        "settled_end_frame_id": settled_end_frame_id,
        "loss_frame_id": loss_frame_id,
        "stoppage_frame_id": stoppage_frame_id,
        "required_anchor_status_field": required_anchor_status_field,
        "required_anchor_status_value": required_anchor_status_value,
    }


def outcome_window_prefilter_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    anchor_frame_id: int,
    maximum_window_seconds: float,
    minimum_settled_possession_seconds: float,
    required_anchor_status_field: str,
    required_anchor_status_value: str,
    status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "outcome_window_status": status,
        "outcome_window_reason": reason,
        "possession_phase_status": "UNKNOWN" if status == "UNKNOWN" else "NOT_SETTLED",
        "outcome_window_start_frame_id": anchor_frame_id,
        "outcome_window_end_frame_id": anchor_frame_id,
        "maximum_window_seconds": maximum_window_seconds,
        "minimum_settled_possession_seconds": minimum_settled_possession_seconds,
        "settled_start_frame_id": None,
        "settled_end_frame_id": None,
        "loss_frame_id": None,
        "stoppage_frame_id": None,
        "required_anchor_status_field": required_anchor_status_field,
        "required_anchor_status_value": required_anchor_status_value,
    }


def analysis_frame_index(state: PeriodState) -> dict[int, int]:
    key = ("analysis_frame_index",)
    if key not in state.lookup_cache:
        state.lookup_cache[key] = {
            int(frame_id): index
            for index, frame_id in enumerate(state.frame_ids)
        }
    return state.lookup_cache[key]


def primitive_set_piece_structure(state: PeriodState, node: BoundCatalogNode) -> None:
    minimum_observed = node_parameter_integer(node, "minimum_observed_outfield_players")
    events = parquet_rows(
        state.canonical_root / "events" / f"match_id={state.match_id}.parquet",
        EVENT_COLUMNS,
    )
    events = events[events["period"].astype(str) == state.period].sort_values("row_index").reset_index(drop=True)
    frames = parquet_rows(
        state.canonical_root / "frames" / f"match_id={state.match_id}" / f"period={state.period}.parquet",
        ["frame_id", "timestamp_utc"],
    ).sort_values("frame_id").reset_index(drop=True)
    frames["_frame_ts_utc"] = pd.to_datetime(frames["timestamp_utc"], utc=True, errors="coerce")
    records: list[dict[str, Any]] = []
    for _, row in events.iterrows():
        event_type = str(row.get("event_type") or "")
        restart_type = set_piece_restart_type(event_type)
        parsed_event = {
            "event_timestamp": str(row.get("timestamp") or ""),
        }
        anchor_frame_id, offset_ms = align_event_to_frame(parsed_event, frames)
        if anchor_frame_id is None:
            if restart_type is None:
                continue
            anchor_frame_id = 0
        record = set_piece_structure_event_record(
            state=state,
            row=row,
            anchor_frame_id=anchor_frame_id,
            offset_ms=offset_ms,
            restart_type=restart_type,
            minimum_observed_outfield_players=minimum_observed,
        )
        if record is not None:
            records.append(record)
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["set_piece_structure_status"]) == "UNKNOWN" else str(record["set_piece_structure_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "set_piece_structure_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "set_piece_structure_status").entity_scope,
        ),
        "set_piece_structure_status_records": records,
    }


def set_piece_restart_type(event_type: str) -> str | None:
    normalized = str(event_type or "")
    if normalized.startswith("CornerKick"):
        return "corner_kick"
    if normalized.startswith("FreeKick"):
        return "free_kick"
    if normalized.startswith("GoalKick"):
        return "goal_kick"
    if normalized.startswith("ThrowIn"):
        return "throw_in"
    if normalized.startswith("KickOff"):
        return "kick_off"
    if normalized.startswith("Penalty_"):
        return "penalty"
    return None


def set_piece_structure_event_record(
    *,
    state: PeriodState,
    row: pd.Series,
    anchor_frame_id: int,
    offset_ms: float | None,
    restart_type: str | None,
    minimum_observed_outfield_players: int,
) -> dict[str, Any] | None:
    event_type = str(row.get("event_type") or "")
    team_role = str(row.get("team_role") or "")
    if team_role not in {"home", "away"}:
        team_role = state.perspective_team_role
    opponent_role = "away" if team_role == "home" else "home"
    row_index = int(row.get("row_index"))
    entity_refs = [
        f"event_row:{row_index}",
        f"event_type:{event_type}",
        f"team_role:{team_role}",
    ]
    if pd.notna(row.get("player_id")):
        entity_refs.append(f"player:{row.get('player_id')}")
    anchor_id = anchor_record_id(
        match_id=state.match_id,
        period=state.period,
        anchor_frame_id=anchor_frame_id,
        start_frame_id=anchor_frame_id,
        end_frame_id=anchor_frame_id,
        entity_refs=entity_refs,
    )
    base = {
        "anchor_id": anchor_id,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": anchor_frame_id,
        "end_frame_id": anchor_frame_id,
        "entity_refs": entity_refs,
        "event_type": event_type,
        "event_row_index": row_index,
        "event_timestamp": str(row.get("timestamp") or ""),
        "event_gameclock_seconds": optional_float(row.get("gameclock_seconds")),
        "event_anchor_frame_id": None if anchor_frame_id == 0 else anchor_frame_id,
        "event_frame_offset_ms": None if offset_ms is None else round(float(offset_ms), 3),
        "set_piece_attacking_team_role": team_role,
        "set_piece_defending_team_role": opponent_role,
        "minimum_observed_outfield_players": minimum_observed_outfield_players,
        "structure_model": "provider_restart_event_plus_anchor_frame_outfield_width_depth_centroid",
        "coordinate_system": "canonical_tracking_pitch_meters_unoriented",
        "set_piece_structure_claim_boundary": (
            "Observed provider restart/set-piece event and at-frame outfield arrangement only; "
            "no routine, role, marking scheme, planned play, intent, quality, or causation claim."
        ),
    }
    if restart_type is None:
        return {
            **base,
            "set_piece_structure_status": "FAIL",
            "set_piece_structure_reason": "event_type_not_recognized_restart",
            "set_piece_restart_type": "non_set_piece",
            "coverage_status": "NOT_EVALUATED",
            **empty_set_piece_shape_fields(),
        }
    attacking_shape = set_piece_team_shape_summary(
        state=state,
        frame_id=anchor_frame_id,
        team_role=team_role,
        prefix="attacking",
        minimum_observed_outfield_players=minimum_observed_outfield_players,
    )
    defending_shape = set_piece_team_shape_summary(
        state=state,
        frame_id=anchor_frame_id,
        team_role=opponent_role,
        prefix="defending",
        minimum_observed_outfield_players=minimum_observed_outfield_players,
    )
    shape_ok = bool(attacking_shape["attacking_shape_coverage_ok"] and defending_shape["defending_shape_coverage_ok"])
    if shape_ok:
        status = "PASS"
        reason = "recognized_restart_with_observed_outfield_arrangement"
        coverage_status = "PASS"
    else:
        status = "UNKNOWN"
        reason = "insufficient_observed_outfield_players_for_structure"
        coverage_status = "UNKNOWN"
    return {
        **base,
        "set_piece_structure_status": status,
        "set_piece_structure_reason": reason,
        "set_piece_restart_type": restart_type,
        "coverage_status": coverage_status,
        **{key: value for key, value in attacking_shape.items() if not key.endswith("_coverage_ok")},
        **{key: value for key, value in defending_shape.items() if not key.endswith("_coverage_ok")},
    }


def empty_set_piece_shape_fields() -> dict[str, Any]:
    return {
        "attacking_shape_width_m": None,
        "attacking_shape_depth_m": None,
        "attacking_shape_centroid_x_m": None,
        "attacking_shape_centroid_y_m": None,
        "attacking_observed_player_count": 0,
        "attacking_observed_player_ids": [],
        "defending_shape_width_m": None,
        "defending_shape_depth_m": None,
        "defending_shape_centroid_x_m": None,
        "defending_shape_centroid_y_m": None,
        "defending_observed_player_count": 0,
        "defending_observed_player_ids": [],
    }


def set_piece_team_shape_summary(
    *,
    state: PeriodState,
    frame_id: int,
    team_role: str,
    prefix: str,
    minimum_observed_outfield_players: int,
) -> dict[str, Any]:
    outfield_ids = outfield_player_ids(state.canonical_root, state.match_id, team_role)
    observed = [
        item
        for item in cached_observed_outfield_positions_at_frame(state, frame_id, team_role, outfield_ids)
        if item.get("x_m") is not None and item.get("y_m") is not None
    ]
    if len(observed) < minimum_observed_outfield_players:
        return {
            f"{prefix}_shape_width_m": None,
            f"{prefix}_shape_depth_m": None,
            f"{prefix}_shape_centroid_x_m": None,
            f"{prefix}_shape_centroid_y_m": None,
            f"{prefix}_observed_player_count": len(observed),
            f"{prefix}_observed_player_ids": sorted(str(item["player_id"]) for item in observed),
            f"{prefix}_shape_coverage_ok": False,
        }
    xs = [float(item["x_m"]) for item in observed]
    ys = [float(item["y_m"]) for item in observed]
    return {
        f"{prefix}_shape_width_m": round(float(max(ys) - min(ys)), 3),
        f"{prefix}_shape_depth_m": round(float(max(xs) - min(xs)), 3),
        f"{prefix}_shape_centroid_x_m": round(float(sum(xs) / len(xs)), 3),
        f"{prefix}_shape_centroid_y_m": round(float(sum(ys) / len(ys)), 3),
        f"{prefix}_observed_player_count": len(observed),
        f"{prefix}_observed_player_ids": sorted(str(item["player_id"]) for item in observed),
        f"{prefix}_shape_coverage_ok": True,
    }


def primitive_outcome_classification(state: PeriodState, node: BoundCatalogNode) -> None:
    accepted: list[dict[str, Any]] = []
    near_misses: list[dict[str, Any]] = []
    accepted_shift_records = catalog_input_value(state, node, "accepted_shift_episodes").value
    if not isinstance(accepted_shift_records, list):
        raise RuntimeError(f"{node.node_id} requires accepted shift episode records")
    accepted_shift_records = expanded_pass_source_records(accepted_shift_records)
    query_hash = state.params.text("result_id_seed_hash")
    analysis_rate_hz = state.params.integer("analysis_rate_hz")
    dedupe_source_frames = int(round(state.params.number("dedupe_window_seconds") * FRAME_RATE_HZ))
    last_kept_by_segment: dict[tuple[int, int], int] = {}
    frame_index = {int(frame_id): index for index, frame_id in enumerate(state.frame_ids)}

    for candidate in accepted_shift_records:
        segment_key = (
            int(candidate["possession_start_frame_id"]),
            int(candidate["possession_end_frame_id"]),
        )
        last_kept_entry = last_kept_by_segment.get(segment_key, -10**12)
        if int(candidate["wide_entry_frame_id"]) - last_kept_entry < dedupe_source_frames:
            continue
        try:
            anchor_idx = frame_index[int(candidate["anchor_frame_id"])]
        except KeyError:
            continue
        outcome, outcome_offset = classify_outcome(
            signed_ball_y=state.ball_y[anchor_idx:],
            possession_role=state.possession_role[anchor_idx:],
            ball_alive=state.ball_alive[anchor_idx:],
            side_sign=int(candidate["side_sign"]),
            params=state.params,
            perspective_team_role=state.perspective_team_role,
        )
        outcome_frame_id = (
            int(state.frame_ids[anchor_idx + outcome_offset])
            if outcome_offset is not None and anchor_idx + outcome_offset < len(state.frame_ids)
            else int(state.frame_ids[min(len(state.frame_ids) - 1, anchor_idx)])
        )
        result_id = hashlib.sha256(
            f"{query_hash}:{state.match_id}:{state.period}:{candidate['wide_entry_frame_id']}:{candidate['anchor_frame_id']}".encode()
        ).hexdigest()[:16]
        result = {
            **base_result_fields(state, candidate, query_hash, analysis_rate_hz),
            "result_id": result_id,
            "classification": outcome,
            "outcome_frame_id": outcome_frame_id,
            "accepted": outcome != "STOPPAGE" and candidate["quality_status"] == "pass",
            "_predicate_status": candidate.get("_predicate_status", {}),
            "replay_start_frame_id": max(
                int(candidate["segment_frame_ids"][0]),
                int(candidate["baseline_start_frame_id"]) - FRAME_RATE_HZ * 2,
            ),
            "replay_end_frame_id": min(
                int(state.frame_ids[-1]),
                outcome_frame_id + FRAME_RATE_HZ * 2,
            ),
        }
        candidate["_runtime_result"] = result
        if result["accepted"]:
            accepted.append(result)
            last_kept_by_segment[segment_key] = int(candidate["wide_entry_frame_id"])
        else:
            near_miss = {**result, "near_miss_reason": "excluded_outcome"}
            candidate["_runtime_result"] = near_miss
            near_misses.append(near_miss)
    state.accepted = accepted
    state.near_misses = near_misses
    classification_records = accepted + near_misses
    state.signals[node.node_id] = {
        "classification": FrameSignal(
            frame_ids=[
                int(item.get("outcome_frame_id") or item["anchor_frame_id"])
                for item in classification_records
            ],
            values=[
                str(item["classification"]) if item.get("classification") is not None else None
                for item in classification_records
            ],
            unknown_mask=[
                item.get("classification") is None
                for item in classification_records
            ],
            unit=node.outputs[0].unit,
            entity_scope=node.outputs[0].entity_scope,
        ),
        "classification_records": classification_records,
    }


def expanded_pass_source_records(records: list[Any]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("temporal_status") not in {None, "PASS"}:
            continue
        source_records = [
            item
            for item in record.get("source_records") or []
            if isinstance(item, dict) and "possession_start_frame_id" in item
        ]
        if source_records:
            expanded.extend(source_records)
        elif "possession_start_frame_id" in record:
            expanded.append(record)
    return expanded


def base_result_fields(
    state: PeriodState,
    candidate: dict[str, Any],
    query_hash: str,
    analysis_rate_hz: int,
) -> dict[str, Any]:
    return {
        "query_id": state.recipe_id,
        "query_version": state.recipe_version,
        "query_hash": query_hash,
        "analysis_rate_hz": analysis_rate_hz,
        "match_id": state.match_id,
        "period": state.period,
        "perspective_team_role": state.perspective_team_role,
        "perspective_team_id": state.perspective_team_id,
        "defending_team_role": state.defending_team_role,
        "defending_team_id": state.defending_team_id,
        "possession_start_frame_id": int(candidate["possession_start_frame_id"]),
        "possession_end_frame_id": int(candidate["possession_end_frame_id"]),
        "possession_duration_seconds": candidate["possession_duration_seconds"],
        "wide_entry_frame_id": int(candidate["wide_entry_frame_id"]),
        "wide_entry_y_m": candidate["wide_entry_y_m"],
        "ball_side": candidate["ball_side"],
        "baseline_start_frame_id": int(candidate["baseline_start_frame_id"]),
        "baseline_end_frame_id": int(candidate["baseline_end_frame_id"]),
        "baseline_defensive_centroid_y_m": candidate["baseline_defensive_centroid_y_m"],
        "anchor_frame_id": int(candidate["anchor_frame_id"]),
        "signed_shift_metres": candidate["signed_shift_metres"],
        "block_shift_score": candidate["block_shift_score"],
        "quality_status": candidate["quality_status"],
    }


def classify_outcome(
    *,
    signed_ball_y: np.ndarray,
    possession_role: np.ndarray,
    ball_alive: np.ndarray,
    side_sign: int,
    params: RuntimeParameters,
    perspective_team_role: str,
) -> tuple[str, int | None]:
    horizon_frames = int(round(params.number("outcome_horizon_seconds") * params.integer("analysis_rate_hz")))
    retain_frames = int(round(params.number("retained_after_switch_seconds") * params.integer("analysis_rate_hz")))
    opposite_y_threshold_m = params.number("opposite_side_fraction") * PITCH_HALF_WIDTH_M
    y = signed_ball_y[:horizon_frames]
    possession = possession_role[:horizon_frames]
    alive = ball_alive[:horizon_frames]

    opposite = np.where(side_sign * y <= -opposite_y_threshold_m)[0]
    loss = np.where((possession != perspective_team_role) & alive)[0]
    dead = np.where(~alive)[0]

    first_dead = int(dead[0]) if len(dead) else None
    first_loss = int(loss[0]) if len(loss) else None
    first_switch = int(opposite[0]) if len(opposite) else None

    if first_dead is not None and (
        first_switch is None or first_dead < first_switch
    ) and (first_loss is None or first_dead < first_loss):
        return "STOPPAGE", first_dead

    if first_switch is not None:
        end = min(len(possession), first_switch + retain_frames)
        retained = end - first_switch >= retain_frames and np.all(
            (possession[first_switch:end] == perspective_team_role) & alive[first_switch:end]
        )
        if retained:
            return "SWITCHED", first_switch
        if first_loss is not None:
            return "LOST_BEFORE_SWITCH", first_loss

    if first_loss is not None:
        return "LOST_BEFORE_SWITCH", first_loss
    return "RETAINED_NO_SWITCH", len(y) - 1 if len(y) else None
