"""Team-shape and defending capability implementations.

F2-6 relocates team-shape/defending capability implementations from
executor.py without changing behavior. Shared runtime helpers remain in
executor.py until the shared-kernel extraction phase.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.executor import (
    FRAME_RATE_HZ,
    PITCH_HALF_WIDTH_M,
    PeriodState,
    anchor_record_id,
    anchor_reference_point,
    ball_point_at_frame,
    cached_observed_outfield_positions_at_frame,
    cached_observed_player_point_at_frame,
    catalog_input_value,
    catalog_output,
    node_parameter_integer,
    node_parameter_number,
    node_parameter_text,
    optional_float,
    optional_int,
    outfield_player_ids,
    player_records_at_frame_for_team,
    point_from_xy,
    runtime_records,
    time_to_arrival_candidates,
    tracked_point_at_frame,
)
from tqe.runtime.ir import BoundCatalogNode, Unit
from tqe.runtime.local_number_relation import (
    LocalNumberConfig,
    evaluate_local_number_relation,
)
from tqe.runtime.values import FrameSignal


def primitive_team_compactness(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchors = anchor_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    frame_field = node_parameter_text(node, "frame_field")
    player_scope = node_parameter_text(node, "player_scope")
    maximum_team_width_m = node_parameter_number(node, "maximum_team_width_m")
    maximum_team_depth_m = node_parameter_number(node, "maximum_team_depth_m")
    minimum_observed_players = node_parameter_integer(node, "minimum_observed_players")
    if player_scope not in {"defending_outfield", "perspective_outfield"}:
        raise RuntimeError(f"Unsupported team_compactness player_scope {player_scope}")
    records = [
        team_compactness_anchor_record(
            state=state,
            anchor=anchor,
            frame_field=frame_field,
            player_scope=player_scope,
            maximum_team_width_m=maximum_team_width_m,
            maximum_team_depth_m=maximum_team_depth_m,
            minimum_observed_players=minimum_observed_players,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["team_compactness_status"]) == "UNKNOWN" else str(record["team_compactness_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "team_compactness_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "team_compactness_status").entity_scope,
        ),
        "team_compactness_status_records": records,
    }
def primitive_change_across_anchor(state: PeriodState, node: BoundCatalogNode) -> None:
    anchors_value = catalog_input_value(state, node, "anchors")
    before_value = catalog_input_value(state, node, "before_evaluations")
    after_value = catalog_input_value(state, node, "after_evaluations")
    anchors = anchors_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    before_records = records_by_anchor_id(runtime_records(before_value))
    after_records = records_by_anchor_id(runtime_records(after_value))
    before_value_field = node_parameter_text(node, "before_value_field")
    after_value_field = node_parameter_text(node, "after_value_field")
    before_status_field = node_parameter_text(node, "before_status_field")
    after_status_field = node_parameter_text(node, "after_status_field")
    required_status_value = node_parameter_text(node, "required_status_value")
    change_mode = node_parameter_text(node, "change_mode")
    minimum_change_m = node_parameter_number(node, "minimum_change_m")
    maximum_before_value_m = node_parameter_number(node, "maximum_before_value_m")
    records = [
        change_across_anchor_record(
            state=state,
            anchor=anchor,
            before_record=before_records.get(str(anchor.get("anchor_id"))),
            after_record=after_records.get(str(anchor.get("anchor_id"))),
            before_value_field=before_value_field,
            after_value_field=after_value_field,
            before_status_field=before_status_field,
            after_status_field=after_status_field,
            required_status_value=required_status_value,
            change_mode=change_mode,
            minimum_change_m=minimum_change_m,
            maximum_before_value_m=maximum_before_value_m,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["change_status"]) == "UNKNOWN" else str(record["change_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "change_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "change_status").entity_scope,
        ),
        "change_status_records": records,
    }
def primitive_cover_shadow(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    frame_field = node_parameter_text(node, "frame_field")
    target_entity_field = node_parameter_text(node, "target_entity_field")
    candidate_scope = node_parameter_text(node, "candidate_scope")
    maximum_lane_distance_m = node_parameter_number(node, "maximum_lane_distance_m")
    minimum_projection_fraction = node_parameter_number(node, "minimum_projection_fraction")
    minimum_lane_length_m = node_parameter_number(node, "minimum_lane_length_m")
    minimum_observed_defenders = node_parameter_integer(node, "minimum_observed_defenders")
    records = [
        cover_shadow_anchor_record(
            state=state,
            anchor=record,
            frame_field=frame_field,
            target_entity_field=target_entity_field,
            candidate_scope=candidate_scope,
            maximum_lane_distance_m=maximum_lane_distance_m,
            minimum_projection_fraction=minimum_projection_fraction,
            minimum_lane_length_m=minimum_lane_length_m,
            minimum_observed_defenders=minimum_observed_defenders,
        )
        for record in runtime_records(anchor_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    cover_values = [
        None if str(record["cover_shadow_status"]) == "UNKNOWN" else str(record["cover_shadow_status"])
        for record in records
    ]
    lane_values = [
        None if str(record["passing_lane_denial_status"]) == "UNKNOWN" else str(record["passing_lane_denial_status"])
        for record in records
    ]
    distance_values = [
        record.get("screening_defender_distance_to_lane_m")
        if str(record["cover_shadow_status"]) == "PASS"
        else None
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "cover_shadow_status": FrameSignal(
            frame_ids=frame_ids,
            values=cover_values,
            unknown_mask=[value is None for value in cover_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "cover_shadow_status").entity_scope,
        ),
        "cover_shadow_status_records": records,
        "passing_lane_denial_status": FrameSignal(
            frame_ids=frame_ids,
            values=lane_values,
            unknown_mask=[value is None for value in lane_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "passing_lane_denial_status").entity_scope,
        ),
        "passing_lane_denial_status_records": records,
        "screening_defender_distance_to_lane_m": FrameSignal(
            frame_ids=frame_ids,
            values=distance_values,
            unknown_mask=[value is None for value in distance_values],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "screening_defender_distance_to_lane_m").entity_scope,
        ),
        "screening_defender_distance_to_lane_m_records": records,
    }
def relation_pressure_on_carrier(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchor_records = anchor_value.value
    if not isinstance(anchor_records, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    frame_field = node_parameter_text(node, "frame_field")
    carrier_id_field = node_parameter_text(node, "carrier_id_field")
    maximum_pressure_distance_m = node_parameter_number(node, "maximum_pressure_distance_m")
    minimum_closing_speed_mps = node_parameter_number(node, "minimum_closing_speed_mps")
    maximum_approach_angle_degrees = node_parameter_number(node, "maximum_approach_angle_degrees")
    minimum_pressure_duration_seconds = node_parameter_number(node, "minimum_pressure_duration_seconds")
    lookback_seconds = node_parameter_number(node, "lookback_seconds")
    candidate_scope = node_parameter_text(node, "candidate_scope")
    if candidate_scope != "defending_outfield":
        raise RuntimeError("pressure_on_carrier v0.1 supports candidate_scope=defending_outfield")
    known_outfield_ids = outfield_player_ids(state.canonical_root, state.match_id, state.defending_team_role)
    records = [
        pressure_on_carrier_anchor_record(
            state=state,
            anchor=anchor,
            frame_field=frame_field,
            carrier_id_field=carrier_id_field,
            maximum_pressure_distance_m=maximum_pressure_distance_m,
            minimum_closing_speed_mps=minimum_closing_speed_mps,
            maximum_approach_angle_degrees=maximum_approach_angle_degrees,
            minimum_pressure_duration_seconds=minimum_pressure_duration_seconds,
            lookback_seconds=lookback_seconds,
            known_outfield_ids=known_outfield_ids,
        )
        for anchor in anchor_records
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["pressure_status"]) == "UNKNOWN" else str(record["pressure_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "pressure_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "pressure_status").entity_scope,
        ),
        "pressure_status_records": records,
    }
def relation_team_press(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchor_records = anchor_value.value
    if not isinstance(anchor_records, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    frame_field = node_parameter_text(node, "frame_field")
    carrier_id_field = node_parameter_text(node, "carrier_id_field")
    maximum_press_distance_m = node_parameter_number(node, "maximum_press_distance_m")
    minimum_closing_speed_mps = node_parameter_number(node, "minimum_closing_speed_mps")
    maximum_approach_angle_degrees = node_parameter_number(node, "maximum_approach_angle_degrees")
    minimum_pressing_defenders = node_parameter_integer(node, "minimum_pressing_defenders")
    minimum_angle_spread_degrees = node_parameter_number(node, "minimum_angle_spread_degrees")
    minimum_observed_defenders = node_parameter_integer(node, "minimum_observed_defenders")
    lookback_seconds = node_parameter_number(node, "lookback_seconds")
    candidate_scope = node_parameter_text(node, "candidate_scope")
    if candidate_scope != "defending_outfield":
        raise RuntimeError("team_press v0.1 supports candidate_scope=defending_outfield")
    known_outfield_ids = outfield_player_ids(state.canonical_root, state.match_id, state.defending_team_role)
    records = [
        team_press_anchor_record(
            state=state,
            anchor=anchor,
            frame_field=frame_field,
            carrier_id_field=carrier_id_field,
            maximum_press_distance_m=maximum_press_distance_m,
            minimum_closing_speed_mps=minimum_closing_speed_mps,
            maximum_approach_angle_degrees=maximum_approach_angle_degrees,
            minimum_pressing_defenders=minimum_pressing_defenders,
            minimum_angle_spread_degrees=minimum_angle_spread_degrees,
            minimum_observed_defenders=minimum_observed_defenders,
            lookback_seconds=lookback_seconds,
            known_outfield_ids=known_outfield_ids,
        )
        for anchor in anchor_records
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["team_press_status"]) == "UNKNOWN" else str(record["team_press_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "team_press_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "team_press_status").entity_scope,
        ),
        "team_press_status_records": records,
        "pressure_actor_count": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("pressure_actor_count") for record in records],
            unknown_mask=[record.get("pressure_actor_count") is None for record in records],
            unit=Unit.COUNT,
            entity_scope=catalog_output(node, "pressure_actor_count").entity_scope,
        ),
        "pressure_actor_count_records": records,
        "pressure_angle_spread_degrees": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("pressure_angle_spread_degrees") for record in records],
            unknown_mask=[record.get("pressure_angle_spread_degrees") is None for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "pressure_angle_spread_degrees").entity_scope,
        ),
        "pressure_angle_spread_degrees_records": records,
    }
def relation_local_number(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchor_records = anchor_value.value
    if not isinstance(anchor_records, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    frame_field = node_parameter_text(node, "frame_field")
    radius_m = node_parameter_number(node, "radius_m")
    minimum_difference = node_parameter_integer(node, "minimum_difference")
    minimum_perspective_players = node_parameter_integer(node, "minimum_perspective_players")
    maximum_defending_players = node_parameter_integer(node, "maximum_defending_players")
    records = [
        local_number_anchor_record(
            state=state,
            anchor=anchor,
            frame_field=frame_field,
            radius_m=radius_m,
            minimum_difference=minimum_difference,
            minimum_perspective_players=minimum_perspective_players,
            maximum_defending_players=maximum_defending_players,
        )
        for anchor in anchor_records
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["local_number_status"]) == "UNKNOWN" else str(record["local_number_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "local_number_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "local_number_status").entity_scope,
        ),
        "local_number_status_records": records,
    }
def primitive_ball_lateral_fraction(state: PeriodState, node: BoundCatalogNode) -> None:
    state.signals[node.node_id] = {
        "fraction": np.abs(state.ball_y) / PITCH_HALF_WIDTH_M,
        "ball_y": state.ball_y,
    }
def primitive_defensive_outfield_centroid(state: PeriodState, node: BoundCatalogNode) -> None:
    ordered = state.defender_centroid_y.sort_index()
    state.signals[node.node_id] = {
        "centroid_y": FrameSignal(
            frame_ids=[int(frame_id) for frame_id in ordered.index.tolist()],
            values=[None if pd.isna(value) else float(value) for value in ordered.tolist()],
            unknown_mask=[pd.isna(value) for value in ordered.tolist()],
            unit=node.outputs[0].unit,
            entity_scope=node.outputs[0].entity_scope,
        )
    }
def primitive_signed_lateral_shift(state: PeriodState, node: BoundCatalogNode) -> None:
    possession_episodes = catalog_input_value(
        state,
        node,
        "possession_episodes",
    ).value
    entry_episodes = catalog_input_value(state, node, "entry_episodes").value
    defensive_centroid = catalog_input_value(state, node, "defensive_centroid").value
    if not isinstance(possession_episodes, list) or not isinstance(entry_episodes, list):
        raise RuntimeError(f"{node.node_id} requires episode-set inputs")
    if not isinstance(defensive_centroid, FrameSignal):
        raise RuntimeError(f"{node.node_id} requires defensive centroid frame signal")
    defensive_centroid_y = pd.Series(
        defensive_centroid.values,
        index=defensive_centroid.frame_ids,
        dtype="float64",
    ).dropna()
    candidates = wide_entry_candidates_from_episodes(
        state,
        entry_episodes=entry_episodes,
        possession_episodes=possession_episodes,
    )
    baseline_frames = int(round(state.params.number("baseline_window_seconds") * state.params.integer("analysis_rate_hz")))
    search_frames = int(round(state.params.number("shift_search_window_seconds") * state.params.integer("analysis_rate_hz")))
    shifted: list[dict[str, Any]] = []

    for candidate in candidates:
        segment_frame_ids = candidate["segment_frame_ids"]
        entry_idx = int(candidate["entry_index"])
        side_sign = int(candidate["side_sign"])
        baseline_start_frame = int(segment_frame_ids[max(0, entry_idx - baseline_frames)])
        baseline_end_frame = int(segment_frame_ids[entry_idx - 1])
        baseline_series = defensive_centroid_y.loc[
            (defensive_centroid_y.index >= baseline_start_frame)
            & (defensive_centroid_y.index <= baseline_end_frame)
        ]
        if baseline_series.empty:
            continue
        baseline_centroid_y = float(baseline_series.mean())
        search_end = min(len(segment_frame_ids), entry_idx + search_frames)
        search_frame_ids = segment_frame_ids[entry_idx:search_end]
        search_series = defensive_centroid_y.loc[
            defensive_centroid_y.index.isin(search_frame_ids)
        ]
        signed_shift = side_sign * (search_series - baseline_centroid_y)
        if signed_shift.empty:
            continue
        max_shift = float(signed_shift.max())
        anchor_frame_id = int(signed_shift.idxmax())
        enough_defenders = bool(
            state.defender_count.loc[
                (state.defender_count.index >= baseline_start_frame)
                & (state.defender_count.index <= int(search_frame_ids[-1]))
            ].min()
            >= state.params.integer("minimum_outfield_players_per_team")
        )
        shifted.append(
            {
                **candidate,
                "anchor_id": anchor_record_id(
                    match_id=state.match_id,
                    period=state.period,
                    anchor_frame_id=anchor_frame_id,
                    start_frame_id=baseline_start_frame,
                    end_frame_id=int(search_frame_ids[-1]),
                    entity_refs=[state.perspective_team_id, state.defending_team_id],
                ),
                "match_id": state.match_id,
                "period": state.period,
                "entity_refs": [state.perspective_team_id, state.defending_team_id],
                "baseline_start_frame_id": baseline_start_frame,
                "baseline_end_frame_id": baseline_end_frame,
                "start_frame_id": baseline_start_frame,
                "end_frame_id": int(search_frame_ids[-1]),
                "shift_search_start_frame_id": int(search_frame_ids[0]),
                "shift_search_end_frame_id": int(search_frame_ids[-1]),
                "baseline_defensive_centroid_y_m": round(baseline_centroid_y, 3),
                "anchor_frame_id": anchor_frame_id,
                "signed_shift_metres": round(max_shift, 3),
                "block_shift_score": round(max_shift, 6),
                "quality_status": "pass" if enough_defenders else "fail",
                "enough_defenders": enough_defenders,
                "measure_series": signed_shift,
            }
        )
    state.candidates = shifted
    state.signals[node.node_id] = {
        "signed_shift": FrameSignal(
            frame_ids=[int(item["anchor_frame_id"]) for item in shifted],
            values=[float(item["signed_shift_metres"]) for item in shifted],
            unknown_mask=[False for _ in shifted],
            unit=node.outputs[0].unit,
            entity_scope=node.outputs[0].entity_scope,
        ),
        "signed_shift_records": shifted,
        "anchors": shifted,
    }
def team_compactness_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    player_scope: str,
    maximum_team_width_m: float,
    maximum_team_depth_m: float,
    minimum_observed_players: int,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    evaluation_frame_id = optional_int(anchor.get(frame_field))
    if evaluation_frame_id is None and frame_field != "anchor_frame_id":
        evaluation_frame_id = anchor_frame_id
    if anchor_frame_id is None or evaluation_frame_id is None:
        return None
    team_role = state.defending_team_role if player_scope == "defending_outfield" else state.perspective_team_role
    outfield_ids = outfield_player_ids(state.canonical_root, state.match_id, team_role)
    positions = cached_observed_outfield_positions_at_frame(
        state,
        evaluation_frame_id,
        team_role,
        outfield_ids,
    )
    observed = [
        item for item in positions
        if item.get("x_m") is not None and item.get("y_m") is not None
    ]
    if len(observed) < minimum_observed_players:
        status = "UNKNOWN"
        reason = "insufficient_observed_outfield_players"
        width_m = None
        depth_m = None
        area_m2 = None
    else:
        xs = [float(item["x_m"]) for item in observed]
        ys = [float(item["y_m"]) for item in observed]
        width_m = max(ys) - min(ys)
        depth_m = max(xs) - min(xs)
        area_m2 = width_m * depth_m
        if width_m <= maximum_team_width_m and depth_m <= maximum_team_depth_m:
            status = "PASS"
            reason = "team_compactness_requirement_satisfied"
        else:
            status = "FAIL"
            reason = "team_compactness_requirement_not_met"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "team_compactness_status": status,
        "team_compactness_reason": reason,
        "team_compactness_frame_field": frame_field,
        "team_compactness_frame_id": evaluation_frame_id,
        "player_scope": player_scope,
        "team_role": team_role,
        "observed_player_count": len(observed),
        "minimum_observed_players": minimum_observed_players,
        "team_width_m": None if width_m is None else round(float(width_m), 3),
        "team_depth_m": None if depth_m is None else round(float(depth_m), 3),
        "team_area_m2": None if area_m2 is None else round(float(area_m2), 3),
        "maximum_team_width_m": maximum_team_width_m,
        "maximum_team_depth_m": maximum_team_depth_m,
        "observed_player_ids": sorted(str(item["player_id"]) for item in observed),
    }
def change_across_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    before_record: dict[str, Any] | None,
    after_record: dict[str, Any] | None,
    before_value_field: str,
    after_value_field: str,
    before_status_field: str,
    after_status_field: str,
    required_status_value: str,
    change_mode: str,
    minimum_change_m: float,
    maximum_before_value_m: float,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    before_value = None if before_record is None else optional_float(before_record.get(before_value_field))
    after_value = None if after_record is None else optional_float(after_record.get(after_value_field))
    before_status = None if before_record is None else before_record.get(before_status_field)
    after_status = None if after_record is None else after_record.get(after_status_field)
    delta_value = None if before_value is None or after_value is None else after_value - before_value
    status = "UNKNOWN"
    reason = "change_evidence_missing"
    if before_record is None or after_record is None:
        reason = "before_or_after_record_missing"
    elif str(before_status) != required_status_value:
        status = "UNKNOWN" if before_status is None else "FAIL"
        reason = "before_required_status_not_met"
    elif after_status_field != "none" and str(after_status) != required_status_value:
        status = "UNKNOWN" if after_status is None else "FAIL"
        reason = "after_required_status_not_met"
    elif before_value is None or after_value is None:
        reason = "change_value_missing"
    elif before_value > maximum_before_value_m:
        status = "FAIL"
        reason = "before_value_not_compact_enough"
    elif change_mode == "increase_at_least":
        status = "PASS" if delta_value is not None and delta_value >= minimum_change_m else "FAIL"
        reason = "change_requirement_satisfied" if status == "PASS" else "increase_below_threshold"
    elif change_mode == "decrease_at_least":
        status = "PASS" if delta_value is not None and -delta_value >= minimum_change_m else "FAIL"
        reason = "change_requirement_satisfied" if status == "PASS" else "decrease_below_threshold"
    elif change_mode == "absolute_delta_at_least":
        status = "PASS" if delta_value is not None and abs(delta_value) >= minimum_change_m else "FAIL"
        reason = "change_requirement_satisfied" if status == "PASS" else "absolute_delta_below_threshold"
    else:
        status = "UNKNOWN"
        reason = "unsupported_change_mode"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "change_status": status,
        "change_reason": reason,
        "change_mode": change_mode,
        "before_value_field": before_value_field,
        "after_value_field": after_value_field,
        "before_status": before_status,
        "after_status": after_status,
        "before_value": None if before_value is None else round(float(before_value), 3),
        "after_value": None if after_value is None else round(float(after_value), 3),
        "delta_value": None if delta_value is None else round(float(delta_value), 3),
        "minimum_change_m": minimum_change_m,
        "maximum_before_value_m": maximum_before_value_m,
        "before_evaluation_frame_id": None if before_record is None else optional_int(before_record.get("line_evaluation_frame_id")),
        "after_evaluation_frame_id": None if after_record is None else optional_int(after_record.get("line_evaluation_frame_id")),
    }
def cover_shadow_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    target_entity_field: str,
    candidate_scope: str,
    maximum_lane_distance_m: float,
    minimum_projection_fraction: float,
    minimum_lane_length_m: float,
    minimum_observed_defenders: int,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or frame_id is None:
        return None
    target_entity_id = str(anchor.get(target_entity_field) or "")
    ball_point = ball_point_at_frame(state, frame_id)
    target_point = tracked_point_at_frame(state, frame_id, target_entity_id)
    candidate_records, known_candidate_ids = time_to_arrival_candidates(
        state=state,
        anchor=anchor,
        frame_id=frame_id,
        candidate_scope=candidate_scope,
    )
    observed_candidates = [
        record
        for record in candidate_records
        if record.get("x_m") is not None and record.get("y_m") is not None
    ]
    missing_candidate_ids = sorted(
        str(player_id)
        for player_id in known_candidate_ids
        if player_id not in {str(record.get("player_id")) for record in observed_candidates}
    )
    model = "ball_target_lane_defender_projection_v0_1"
    claim_boundary = (
        "Observed ball-target lane screening geometry only; no defender intent, tactical denial quality, "
        "pass probability, pitch-control value, scheme, causation, or optimality claim."
    )
    max_lane_distance = float(maximum_lane_distance_m)
    projection_floor = max(0.0, min(0.49, float(minimum_projection_fraction)))
    lane_length = None if ball_point is None or target_point is None else math.dist(ball_point, target_point)

    def base(
        status: str,
        reason: str,
        *,
        screen: dict[str, Any] | None = None,
        all_screens: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        screens = all_screens or []
        return {
            **anchor,
            "match_id": state.match_id,
            "period": state.period,
            "anchor_id": str(anchor.get("anchor_id")),
            "anchor_frame_id": anchor_frame_id,
            "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
            "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
            "entity_refs": list(anchor.get("entity_refs") or []),
            "cover_shadow_status": status,
            "passing_lane_denial_status": status,
            "cover_shadow_reason": reason,
            "cover_shadow_frame_id": frame_id,
            "frame_field": frame_field,
            "target_entity_field": target_entity_field,
            "target_entity_id": target_entity_id or None,
            "ball_point": None if ball_point is None else point_from_xy(ball_point[0], ball_point[1]),
            "target_point": None if target_point is None else point_from_xy(target_point[0], target_point[1]),
            "lane_length_m": None if lane_length is None else round(float(lane_length), 3),
            "candidate_scope": candidate_scope,
            "candidate_player_ids": sorted(str(player_id) for player_id in known_candidate_ids),
            "observed_defender_ids": sorted(str(record["player_id"]) for record in observed_candidates),
            "missing_defender_ids": missing_candidate_ids,
            "observed_defender_count": len(observed_candidates),
            "minimum_observed_defenders": int(minimum_observed_defenders),
            "maximum_lane_distance_m": round(float(max_lane_distance), 3),
            "minimum_projection_fraction": round(float(projection_floor), 3),
            "minimum_lane_length_m": round(float(minimum_lane_length_m), 3),
            "screening_defender_id": None if screen is None else str(screen["player_id"]),
            "screening_defender_distance_to_lane_m": None if screen is None else screen["distance_to_lane_m"],
            "screening_defender_projection_fraction": None if screen is None else screen["projection_fraction"],
            "screening_defender_point": None if screen is None else screen["defender_point"],
            "screening_projection_point": None if screen is None else screen["projection_point"],
            "screening_defender_evidence": screens,
            "cover_shadow_model": model,
            "coverage_status": "UNKNOWN" if status == "UNKNOWN" else ("OBSERVED_ONLY" if missing_candidate_ids else "PASS"),
            "cover_shadow_claim_boundary": claim_boundary,
        }

    if max_lane_distance <= 0:
        return base("UNKNOWN", "invalid_lane_distance_threshold")
    if not target_entity_id:
        return base("UNKNOWN", "target_entity_id_missing")
    if ball_point is None:
        return base("UNKNOWN", "ball_tracking_missing")
    if target_point is None:
        return base("UNKNOWN", "target_tracking_missing")
    if lane_length is None or lane_length < float(minimum_lane_length_m):
        return base("UNKNOWN", "lane_too_short")
    if len(observed_candidates) < max(1, int(minimum_observed_defenders)):
        return base("UNKNOWN", "defender_tracking_missing")

    screens: list[dict[str, Any]] = []
    for record in observed_candidates:
        defender_point = (float(record["x_m"]), float(record["y_m"]))
        projection = lane_projection(
            start=ball_point,
            end=target_point,
            point=defender_point,
        )
        if projection is None:
            continue
        if projection["projection_fraction"] < projection_floor:
            continue
        if projection["projection_fraction"] > 1.0 - projection_floor:
            continue
        if projection["distance_to_lane_m"] > max_lane_distance:
            continue
        screens.append(
            {
                "player_id": str(record["player_id"]),
                "distance_to_lane_m": round(float(projection["distance_to_lane_m"]), 3),
                "projection_fraction": round(float(projection["projection_fraction"]), 3),
                "defender_point": point_from_xy(defender_point[0], defender_point[1]),
                "projection_point": point_from_xy(
                    projection["projection_point"][0],
                    projection["projection_point"][1],
                ),
            }
        )
    screens.sort(key=lambda item: (float(item["distance_to_lane_m"]), float(item["projection_fraction"]), str(item["player_id"])))
    if screens:
        return base("PASS", "screening_defender_on_ball_target_lane", screen=screens[0], all_screens=screens)
    return base("FAIL", "no_screening_defender_on_ball_target_lane", all_screens=[])
def lane_projection(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    point: tuple[float, float],
) -> dict[str, Any] | None:
    vx = float(end[0]) - float(start[0])
    vy = float(end[1]) - float(start[1])
    length_sq = vx * vx + vy * vy
    if length_sq <= 1e-9:
        return None
    wx = float(point[0]) - float(start[0])
    wy = float(point[1]) - float(start[1])
    fraction = (wx * vx + wy * vy) / length_sq
    projection = (float(start[0]) + fraction * vx, float(start[1]) + fraction * vy)
    distance = math.dist(point, projection)
    return {
        "projection_fraction": float(fraction),
        "projection_point": projection,
        "distance_to_lane_m": float(distance),
    }
def pressure_on_carrier_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    carrier_id_field: str,
    maximum_pressure_distance_m: float,
    minimum_closing_speed_mps: float,
    maximum_approach_angle_degrees: float,
    minimum_pressure_duration_seconds: float,
    lookback_seconds: float,
    known_outfield_ids: set[str],
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    pressure_frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or pressure_frame_id is None:
        return None
    carrier_id = str(anchor.get(carrier_id_field) or "")
    evidence = pressure_evidence_at_frame(
        state=state,
        frame_id=pressure_frame_id,
        carrier_id=carrier_id,
        known_outfield_ids=known_outfield_ids,
        maximum_pressure_distance_m=maximum_pressure_distance_m,
        minimum_closing_speed_mps=minimum_closing_speed_mps,
        maximum_approach_angle_degrees=maximum_approach_angle_degrees,
        lookback_seconds=lookback_seconds,
    )
    status = str(evidence["pressure_status"])
    if status == "PASS" and minimum_pressure_duration_seconds > 0:
        duration = pressure_duration_ending_at_frame(
            state=state,
            frame_id=pressure_frame_id,
            carrier_id=carrier_id,
            known_outfield_ids=known_outfield_ids,
            maximum_pressure_distance_m=maximum_pressure_distance_m,
            minimum_closing_speed_mps=minimum_closing_speed_mps,
            maximum_approach_angle_degrees=maximum_approach_angle_degrees,
            lookback_seconds=lookback_seconds,
            maximum_duration_seconds=minimum_pressure_duration_seconds,
        )
        evidence["pressure_duration_seconds"] = duration
        if duration < minimum_pressure_duration_seconds:
            status = "FAIL"
            evidence["pressure_status"] = "FAIL"
            evidence["pressure_reason"] = "pressure_duration_below_threshold"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "pressure_status": status,
        "pressure_frame_field": frame_field,
        "pressure_frame_id": pressure_frame_id,
        "carrier_id_field": carrier_id_field,
        "carrier_id": carrier_id or None,
        "maximum_pressure_distance_m": maximum_pressure_distance_m,
        "minimum_closing_speed_mps": minimum_closing_speed_mps,
        "maximum_approach_angle_degrees": maximum_approach_angle_degrees,
        "minimum_pressure_duration_seconds": minimum_pressure_duration_seconds,
        "lookback_seconds": lookback_seconds,
        **evidence,
    }
def team_press_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    carrier_id_field: str,
    maximum_press_distance_m: float,
    minimum_closing_speed_mps: float,
    maximum_approach_angle_degrees: float,
    minimum_pressing_defenders: int,
    minimum_angle_spread_degrees: float,
    minimum_observed_defenders: int,
    lookback_seconds: float,
    known_outfield_ids: set[str],
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    press_frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or press_frame_id is None:
        return None
    carrier_id = str(anchor.get(carrier_id_field) or "")
    evidence = team_press_evidence_at_frame(
        state=state,
        frame_id=press_frame_id,
        carrier_id=carrier_id,
        known_outfield_ids=known_outfield_ids,
        maximum_press_distance_m=maximum_press_distance_m,
        minimum_closing_speed_mps=minimum_closing_speed_mps,
        maximum_approach_angle_degrees=maximum_approach_angle_degrees,
        minimum_pressing_defenders=minimum_pressing_defenders,
        minimum_angle_spread_degrees=minimum_angle_spread_degrees,
        minimum_observed_defenders=minimum_observed_defenders,
        lookback_seconds=lookback_seconds,
    )
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "team_press_frame_field": frame_field,
        "team_press_frame_id": press_frame_id,
        "carrier_id_field": carrier_id_field,
        "carrier_id": carrier_id or None,
        "maximum_press_distance_m": round(float(maximum_press_distance_m), 3),
        "minimum_closing_speed_mps": round(float(minimum_closing_speed_mps), 3),
        "maximum_approach_angle_degrees": round(float(maximum_approach_angle_degrees), 3),
        "minimum_pressing_defenders": int(minimum_pressing_defenders),
        "minimum_angle_spread_degrees": round(float(minimum_angle_spread_degrees), 3),
        "minimum_observed_defenders": int(minimum_observed_defenders),
        "lookback_seconds": round(float(lookback_seconds), 3),
        **evidence,
    }
def team_press_evidence_at_frame(
    *,
    state: PeriodState,
    frame_id: int,
    carrier_id: str,
    known_outfield_ids: set[str],
    maximum_press_distance_m: float,
    minimum_closing_speed_mps: float,
    maximum_approach_angle_degrees: float,
    minimum_pressing_defenders: int,
    minimum_angle_spread_degrees: float,
    minimum_observed_defenders: int,
    lookback_seconds: float,
) -> dict[str, Any]:
    model = "multi_defender_pressure_geometry_v0_1"
    claim_boundary = (
        "Observed multi-defender pressure geometry only; no press trap, trigger plan, coordination intent, "
        "defensive scheme, causation, pressure quality, or optimality claim."
    )
    base = {
        "team_press_status": "UNKNOWN",
        "team_press_reason": "team_press_evidence_missing",
        "pressure_actor_ids": [],
        "pressure_actor_count": None,
        "nearby_defender_ids": [],
        "nearby_defender_count": None,
        "observed_defender_count": 0,
        "candidate_defender_ids": sorted(str(item) for item in known_outfield_ids),
        "missing_defender_ids": [],
        "pressure_angle_spread_degrees": None,
        "pressure_actor_evidence": [],
        "carrier_point": None,
        "coverage_status": "UNKNOWN",
        "team_press_model": model,
        "team_press_claim_boundary": claim_boundary,
    }
    carrier_point = tracked_point_at_frame(state, frame_id, carrier_id)
    if not carrier_id or carrier_point is None:
        return {**base, "team_press_reason": "carrier_tracking_missing"}
    defenders = [
        record
        for record in player_records_at_frame_for_team(state, frame_id, state.defending_team_role)
        if record["player_id"] in known_outfield_ids
        and record.get("x_m") is not None
        and record.get("y_m") is not None
    ]
    observed_ids = {str(record["player_id"]) for record in defenders}
    missing_ids = sorted(str(player_id) for player_id in known_outfield_ids if str(player_id) not in observed_ids)
    if len(defenders) < max(1, int(minimum_observed_defenders)):
        return {
            **base,
            "team_press_reason": "defender_tracking_missing",
            "observed_defender_count": len(defenders),
            "missing_defender_ids": missing_ids,
            "carrier_point": point_from_xy(carrier_point[0], carrier_point[1]),
        }

    lookback_frames = max(1, int(math.ceil(max(lookback_seconds, 0.04) * FRAME_RATE_HZ - 1e-9)))
    previous_frame_id = int(frame_id) - lookback_frames
    carrier_previous = tracked_point_at_frame(state, previous_frame_id, carrier_id)
    if carrier_previous is None:
        return {
            **base,
            "team_press_reason": "carrier_lookback_tracking_missing",
            "observed_defender_count": len(defenders),
            "missing_defender_ids": missing_ids,
            "carrier_point": point_from_xy(carrier_point[0], carrier_point[1]),
        }

    dt_seconds = lookback_frames / FRAME_RATE_HZ
    all_actor_evidence: list[dict[str, Any]] = []
    nearby: list[dict[str, Any]] = []
    pressing: list[dict[str, Any]] = []
    for defender in defenders:
        defender_id = str(defender["player_id"])
        defender_point = (float(defender["x_m"]), float(defender["y_m"]))
        current_distance = math.dist(carrier_point, defender_point)
        bearing = math.degrees(math.atan2(defender_point[1] - carrier_point[1], defender_point[0] - carrier_point[0]))
        bearing = (bearing + 360.0) % 360.0
        defender_previous = tracked_point_at_frame(state, previous_frame_id, defender_id)
        candidate = {
            "player_id": defender_id,
            "distance_m": round(float(current_distance), 3),
            "bearing_degrees": round(float(bearing), 3),
            "closing_speed_mps": None,
            "approach_angle_degrees": None,
            "defender_point": point_from_xy(defender_point[0], defender_point[1]),
            "kinematic_status": "UNKNOWN",
        }
        if defender_previous is not None:
            previous_distance = math.dist(carrier_previous, defender_previous)
            closing_speed = (previous_distance - current_distance) / dt_seconds
            defender_vx = (defender_point[0] - defender_previous[0]) / dt_seconds
            defender_vy = (defender_point[1] - defender_previous[1]) / dt_seconds
            to_carrier_x = carrier_point[0] - defender_point[0]
            to_carrier_y = carrier_point[1] - defender_point[1]
            approach_angle = vector_angle_degrees((defender_vx, defender_vy), (to_carrier_x, to_carrier_y))
            candidate = {
                **candidate,
                "previous_distance_m": round(float(previous_distance), 3),
                "closing_speed_mps": round(float(closing_speed), 3),
                "approach_angle_degrees": None if approach_angle is None else round(float(approach_angle), 3),
                "previous_defender_point": point_from_xy(defender_previous[0], defender_previous[1]),
                "kinematic_status": "PASS" if approach_angle is not None else "UNKNOWN",
            }
        all_actor_evidence.append(candidate)
        if current_distance <= float(maximum_press_distance_m):
            nearby.append(candidate)
            if (
                candidate["kinematic_status"] == "PASS"
                and float(candidate["closing_speed_mps"]) >= float(minimum_closing_speed_mps)
                and float(candidate["approach_angle_degrees"]) <= float(maximum_approach_angle_degrees)
            ):
                pressing.append(candidate)

    nearby.sort(key=lambda item: (float(item["distance_m"]), str(item["player_id"])))
    pressing.sort(key=lambda item: (float(item["distance_m"]), str(item["player_id"])))
    minimum_pressers = max(1, int(minimum_pressing_defenders))
    if len(nearby) < minimum_pressers:
        reason = "nearby_defender_count_below_threshold"
        status = "FAIL"
        angle_spread = None
    elif len([item for item in nearby if item["kinematic_status"] == "PASS"]) < minimum_pressers:
        return {
            **base,
            "team_press_reason": "pressing_kinematic_tracking_missing",
            "nearby_defender_ids": [str(item["player_id"]) for item in nearby],
            "nearby_defender_count": len(nearby),
            "observed_defender_count": len(defenders),
            "missing_defender_ids": missing_ids,
            "pressure_actor_evidence": nearby[:8],
            "carrier_point": point_from_xy(carrier_point[0], carrier_point[1]),
        }
    else:
        angle_spread = pressure_angle_spread([float(item["bearing_degrees"]) for item in pressing])
        count_ok = len(pressing) >= minimum_pressers
        spread_ok = angle_spread is not None and angle_spread >= float(minimum_angle_spread_degrees)
        status = "PASS" if count_ok and spread_ok else "FAIL"
        failed = []
        if not count_ok:
            failed.append("pressure_actor_count")
        if not spread_ok:
            failed.append("angle_spread")
        reason = "multi_defender_pressure_observed" if status == "PASS" else "team_press_threshold_not_met:" + ",".join(failed)

    return {
        **base,
        "team_press_status": status,
        "team_press_reason": reason,
        "pressure_actor_ids": [str(item["player_id"]) for item in pressing],
        "pressure_actor_count": len(pressing),
        "nearby_defender_ids": [str(item["player_id"]) for item in nearby],
        "nearby_defender_count": len(nearby),
        "observed_defender_count": len(defenders),
        "missing_defender_ids": missing_ids,
        "pressure_angle_spread_degrees": None if angle_spread is None else round(float(angle_spread), 3),
        "pressure_actor_evidence": pressing[:8],
        "nearby_defender_evidence": nearby[:8],
        "carrier_point": point_from_xy(carrier_point[0], carrier_point[1]),
        "coverage_status": "OBSERVED_ONLY" if missing_ids else "PASS",
    }
def pressure_angle_spread(bearings: list[float]) -> float | None:
    if len(bearings) < 2:
        return None
    max_gap = 0.0
    values = [float(value) % 360.0 for value in bearings]
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            delta = abs(left - right) % 360.0
            max_gap = max(max_gap, min(delta, 360.0 - delta))
    return float(max_gap)
def pressure_evidence_at_frame(
    *,
    state: PeriodState,
    frame_id: int,
    carrier_id: str,
    known_outfield_ids: set[str],
    maximum_pressure_distance_m: float,
    minimum_closing_speed_mps: float,
    maximum_approach_angle_degrees: float,
    lookback_seconds: float,
) -> dict[str, Any]:
    base = {
        "pressure_status": "UNKNOWN",
        "pressure_reason": "pressure_evidence_missing",
        "nearest_defender_id": None,
        "nearest_defender_distance_m": None,
        "closing_speed_mps": None,
        "approach_angle_degrees": None,
        "pressure_duration_seconds": 0.0,
        "coverage_status": "UNKNOWN",
        "candidate_defender_ids": sorted(str(item) for item in known_outfield_ids),
    }
    carrier_point = tracked_point_at_frame(state, frame_id, carrier_id)
    if not carrier_id or carrier_point is None:
        return {**base, "pressure_reason": "carrier_tracking_missing"}
    defenders = [
        record
        for record in player_records_at_frame_for_team(state, frame_id, state.defending_team_role)
        if record["player_id"] in known_outfield_ids
        and record.get("x_m") is not None
        and record.get("y_m") is not None
    ]
    if not defenders:
        return {**base, "pressure_reason": "defender_tracking_missing"}
    nearest = min(
        defenders,
        key=lambda record: (
            math.dist(carrier_point, (float(record["x_m"]), float(record["y_m"]))),
            str(record["player_id"]),
        ),
    )
    defender_id = str(nearest["player_id"])
    defender_point = (float(nearest["x_m"]), float(nearest["y_m"]))
    current_distance = math.dist(carrier_point, defender_point)
    lookback_frames = max(1, int(math.ceil(max(lookback_seconds, 0.04) * FRAME_RATE_HZ - 1e-9)))
    previous_frame_id = int(frame_id) - lookback_frames
    carrier_previous = tracked_point_at_frame(state, previous_frame_id, carrier_id)
    defender_previous = tracked_point_at_frame(state, previous_frame_id, defender_id)
    if carrier_previous is None or defender_previous is None:
        return {
            **base,
            "pressure_reason": "closing_speed_tracking_missing",
            "nearest_defender_id": defender_id,
            "nearest_defender_distance_m": round(float(current_distance), 3),
        }
    dt_seconds = lookback_frames / FRAME_RATE_HZ
    previous_distance = math.dist(carrier_previous, defender_previous)
    closing_speed = (previous_distance - current_distance) / dt_seconds
    defender_vx = (defender_point[0] - defender_previous[0]) / dt_seconds
    defender_vy = (defender_point[1] - defender_previous[1]) / dt_seconds
    to_carrier_x = carrier_point[0] - defender_point[0]
    to_carrier_y = carrier_point[1] - defender_point[1]
    approach_angle = vector_angle_degrees((defender_vx, defender_vy), (to_carrier_x, to_carrier_y))
    distance_ok = current_distance <= maximum_pressure_distance_m
    closing_ok = closing_speed >= minimum_closing_speed_mps
    angle_ok = approach_angle is not None and approach_angle <= maximum_approach_angle_degrees
    status = "PASS" if distance_ok and closing_ok and angle_ok else "FAIL"
    failed = []
    if not distance_ok:
        failed.append("distance")
    if not closing_ok:
        failed.append("closing_speed")
    if not angle_ok:
        failed.append("approach_angle")
    return {
        **base,
        "pressure_status": status,
        "pressure_reason": "pressure_observed" if status == "PASS" else "pressure_threshold_not_met:" + ",".join(failed),
        "nearest_defender_id": defender_id,
        "nearest_defender_distance_m": round(float(current_distance), 3),
        "previous_defender_distance_m": round(float(previous_distance), 3),
        "closing_speed_mps": round(float(closing_speed), 3),
        "approach_angle_degrees": None if approach_angle is None else round(float(approach_angle), 3),
        "pressure_duration_seconds": 0.0,
        "coverage_status": "COMPLETE",
        "carrier_point": point_from_xy(carrier_point[0], carrier_point[1]),
        "nearest_defender_point": point_from_xy(defender_point[0], defender_point[1]),
        "previous_carrier_point": point_from_xy(carrier_previous[0], carrier_previous[1]),
        "previous_defender_point": point_from_xy(defender_previous[0], defender_previous[1]),
    }
def pressure_duration_ending_at_frame(
    *,
    state: PeriodState,
    frame_id: int,
    carrier_id: str,
    known_outfield_ids: set[str],
    maximum_pressure_distance_m: float,
    minimum_closing_speed_mps: float,
    maximum_approach_angle_degrees: float,
    lookback_seconds: float,
    maximum_duration_seconds: float,
) -> float:
    required_frames = max(1, int(math.ceil(maximum_duration_seconds * FRAME_RATE_HZ - 1e-9)))
    observed = 0
    for candidate_frame_id in range(int(frame_id), int(frame_id) - required_frames, -1):
        evidence = pressure_evidence_at_frame(
            state=state,
            frame_id=candidate_frame_id,
            carrier_id=carrier_id,
            known_outfield_ids=known_outfield_ids,
            maximum_pressure_distance_m=maximum_pressure_distance_m,
            minimum_closing_speed_mps=minimum_closing_speed_mps,
            maximum_approach_angle_degrees=maximum_approach_angle_degrees,
            lookback_seconds=lookback_seconds,
        )
        if evidence.get("pressure_status") != "PASS":
            break
        observed += 1
    return round(float(observed / FRAME_RATE_HZ), 3)
def vector_angle_degrees(a: tuple[float, float], b: tuple[float, float]) -> float | None:
    a_norm = math.hypot(a[0], a[1])
    b_norm = math.hypot(b[0], b[1])
    if a_norm <= 1e-9 or b_norm <= 1e-9:
        return None
    cosine = max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / (a_norm * b_norm)))
    return math.degrees(math.acos(cosine))
def local_number_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    radius_m: float,
    minimum_difference: int,
    minimum_perspective_players: int,
    maximum_defending_players: int,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    evaluation_frame_id = optional_int(anchor.get(frame_field))
    if evaluation_frame_id is None and frame_field != "anchor_frame_id":
        evaluation_frame_id = anchor_frame_id
    if anchor_frame_id is None or evaluation_frame_id is None:
        return None
    perspective_outfield_ids = outfield_player_ids(
        state.canonical_root,
        state.match_id,
        state.perspective_team_role,
    )
    defending_outfield_ids = outfield_player_ids(
        state.canonical_root,
        state.match_id,
        state.defending_team_role,
    )
    perspective_positions = cached_observed_outfield_positions_at_frame(
        state,
        evaluation_frame_id,
        state.perspective_team_role,
        perspective_outfield_ids,
    )
    defending_positions = cached_observed_outfield_positions_at_frame(
        state,
        evaluation_frame_id,
        state.defending_team_role,
        defending_outfield_ids,
    )
    reference_point = anchor_reference_point(anchor)
    if reference_point is None:
        reference_point = cached_observed_player_point_at_frame(
            state,
            frame_id=evaluation_frame_id,
            player_id=anchor.get("receiver_id"),
        )
    evaluation = evaluate_local_number_relation(
        anchor_id=str(anchor.get("anchor_id")),
        anchor_frame_id=anchor_frame_id,
        evaluation_frame_id=evaluation_frame_id,
        reference_point=reference_point,
        perspective_positions=perspective_positions,
        defending_positions=defending_positions,
        config=LocalNumberConfig(
            radius_m=radius_m,
            minimum_difference=minimum_difference,
            minimum_perspective_players=minimum_perspective_players,
            maximum_defending_players=maximum_defending_players,
        ),
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
        "local_number_status": str(payload["status"]),
        "local_number_reason": payload["reason"],
        "local_number_frame_field": frame_field,
        "local_number_frame_id": evaluation_frame_id,
        "reference_point": reference_point,
        "radius_m": radius_m,
        "minimum_difference": minimum_difference,
        "minimum_perspective_players": minimum_perspective_players,
        "maximum_defending_players": maximum_defending_players,
        "perspective_player_ids": list(payload["perspective_player_ids"]),
        "defending_player_ids": list(payload["defending_player_ids"]),
        "perspective_count": payload["perspective_count"],
        "defending_count": payload["defending_count"],
        "local_number_difference": payload["local_number_difference"],
        "evaluated_perspective_player_ids": list(payload["evaluated_perspective_player_ids"]),
        "evaluated_defending_player_ids": list(payload["evaluated_defending_player_ids"]),
        "perspective_in_region_player_ids": list(payload["perspective_in_region_player_ids"]),
        "defending_in_region_player_ids": list(payload["defending_in_region_player_ids"]),
        "missing_perspective_player_ids": list(payload["missing_perspective_player_ids"]),
        "missing_defending_player_ids": list(payload["missing_defending_player_ids"]),
        "invalid_coordinate_player_ids": list(payload["invalid_coordinate_player_ids"]),
        "duplicate_perspective_player_ids": list(payload["duplicate_perspective_player_ids"]),
        "duplicate_defending_player_ids": list(payload["duplicate_defending_player_ids"]),
        "per_player_evidence": payload["per_player_evidence"],
        "coverage_status": payload["coverage_status"],
        "config_evidence": payload["config_evidence"],
        "perspective_team_role": state.perspective_team_role,
        "defending_team_role": state.defending_team_role,
    }
def wide_entry_candidates(
    state: PeriodState,
    wide_mask: np.ndarray,
    dwell_frames: int,
    possession_segments: list[Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    baseline_frames = int(round(state.params.number("baseline_window_seconds") * state.params.integer("analysis_rate_hz")))
    prior_central_threshold_m = state.params.number("prior_central_fraction") * PITCH_HALF_WIDTH_M

    for segment in possession_segments:
        segment_slice = slice(int(segment["start_index"]), int(segment["end_index"]) + 1)
        seg_frame_ids = state.frame_ids[segment_slice]
        seg_ball_y = state.ball_y[segment_slice]
        seg_wide = wide_mask[segment_slice]
        for i in range(max(baseline_frames, dwell_frames), len(seg_ball_y) - dwell_frames):
            if not (seg_wide[i] and not seg_wide[i - 1] and np.all(seg_wide[i : i + dwell_frames])):
                continue
            prior_start = max(0, i - int(round(2.0 * state.params.integer("analysis_rate_hz"))))
            if not np.any(np.abs(seg_ball_y[prior_start:i]) < prior_central_threshold_m):
                continue
            dwell_end = i
            while dwell_end < len(seg_wide) and bool(seg_wide[dwell_end]):
                dwell_end += 1
            side_sign = 1 if seg_ball_y[i] >= 0 else -1
            candidates.append(
                {
                    "entry_index": i,
                    "side_sign": side_sign,
                    "segment_frame_ids": seg_frame_ids,
                    "possession_start_frame_id": int(seg_frame_ids[0]),
                    "possession_end_frame_id": int(seg_frame_ids[-1]),
                    "possession_duration_seconds": round(
                        float(len(seg_frame_ids) / state.params.integer("analysis_rate_hz")),
                        3,
                    ),
                    "wide_entry_frame_id": int(seg_frame_ids[i]),
                    "wide_dwell_seconds": round(
                        float((dwell_end - i) / state.params.integer("analysis_rate_hz")),
                        3,
                    ),
                    "wide_dwell_end_frame_id": int(seg_frame_ids[dwell_end - 1]),
                    "prior_central_start_frame_id": int(seg_frame_ids[prior_start]),
                    "prior_central_end_frame_id": int(seg_frame_ids[i - 1]),
                    "wide_entry_y_m": round(float(seg_ball_y[i]), 3),
                    "ball_side": "right" if side_sign > 0 else "left",
                }
            )
    return candidates
def wide_entry_candidates_from_episodes(
    state: PeriodState,
    *,
    entry_episodes: list[Any],
    possession_episodes: list[Any],
) -> list[dict[str, Any]]:
    wide_mask = np.zeros(len(state.frame_ids), dtype=bool)
    structured_episodes: list[dict[str, Any]] = []
    frame_index = {int(frame_id): index for index, frame_id in enumerate(state.frame_ids)}
    for episode in entry_episodes:
        if isinstance(episode, dict) and episode.get("temporal_status") not in {None, "PASS"}:
            continue
        start_index = episode_start_index(episode, frame_index=frame_index)
        end_index = episode_end_index(episode, frame_index=frame_index)
        if start_index is None or end_index is None:
            continue
        wide_mask[start_index : end_index + 1] = True
        if isinstance(episode, dict):
            structured_episodes.append(episode)
    dwell_frames = int(
        round(state.params.number("minimum_wide_dwell_seconds") * state.params.integer("analysis_rate_hz"))
    )
    candidates = wide_entry_candidates(
        state,
        wide_mask,
        dwell_frames,
        possession_segments=possession_episodes,
    )
    for candidate in candidates:
        entry_frame_id = int(candidate["wide_entry_frame_id"])
        source_episode = next(
            (
                episode
                for episode in structured_episodes
                if int(episode.get("start_frame_id", -1))
                <= entry_frame_id
                <= int(episode.get("end_frame_id", -1))
            ),
            None,
        )
        if source_episode is not None and isinstance(source_episode.get("_predicate_status"), dict):
            candidate["_predicate_status"] = dict(source_episode["_predicate_status"])
    return candidates
def episode_start_index(episode: Any, *, frame_index: dict[int, int] | None = None) -> int | None:
    if isinstance(episode, dict):
        if "start_index" in episode:
            return int(episode["start_index"])
        if frame_index is not None and "start_frame_id" in episode:
            return frame_index.get(int(episode["start_frame_id"]))
        return None
    if isinstance(episode, tuple | list) and len(episode) >= 1:
        return int(episode[0])
    return None
def episode_end_index(episode: Any, *, frame_index: dict[int, int] | None = None) -> int | None:
    if isinstance(episode, dict):
        if "end_index" in episode:
            return int(episode["end_index"])
        if frame_index is not None and "end_frame_id" in episode:
            return frame_index.get(int(episode["end_frame_id"]))
        return None
    if isinstance(episode, tuple | list) and len(episode) >= 2:
        return int(episode[1])
    return None
def records_by_anchor_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        anchor_id = record.get("anchor_id")
        if anchor_id is None:
            continue
        indexed.setdefault(str(anchor_id), record)
    return indexed
