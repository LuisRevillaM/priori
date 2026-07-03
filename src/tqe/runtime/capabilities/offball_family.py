"""Off-ball capability implementations.

F2-5 relocates support-arrival, time-to-arrival, marking, and off-ball-run
family implementations from executor.py without changing behavior. Shared
runtime helpers remain in executor.py until the shared-kernel extraction phase.
"""

from __future__ import annotations

import math
from typing import Any

from tqe.runtime.executor import (
    FRAME_RATE_HZ,
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
    optional_int,
    outfield_player_ids,
    parquet_rows,
    player_records_at_frame,
    player_records_at_frame_for_team,
    point_from_xy,
    runtime_records,
    arrival_candidates,
    tracked_point_at_frame,
)
from tqe.runtime.ir import BoundCatalogNode, Unit
from tqe.runtime.pass_bypass import attack_x_sign_for
from tqe.runtime.support_arrival import (
    SupportArrivalConfig,
    evaluate_support_arrival_relation,
)
from tqe.runtime.values import FrameSignal


def primitive_marking(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    frame_field = node_parameter_text(node, "frame_field")
    target_player_id_field = node_parameter_text(node, "target_player_id_field")
    candidate_scope = node_parameter_text(node, "candidate_scope")
    maximum_marking_distance_m = node_parameter_number(node, "maximum_marking_distance_m")
    minimum_observed_marker_candidates = node_parameter_integer(node, "minimum_observed_marker_candidates")
    records = [
        marking_anchor_record(
            state=state,
            anchor=record,
            frame_field=frame_field,
            target_player_id_field=target_player_id_field,
            candidate_scope=candidate_scope,
            maximum_marking_distance_m=maximum_marking_distance_m,
            minimum_observed_marker_candidates=minimum_observed_marker_candidates,
        )
        for record in runtime_records(anchor_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    marking_values = [
        None if str(record["marking_status"]) == "UNKNOWN" else str(record["marking_status"])
        for record in records
    ]
    unmarked_values = [
        None if str(record["unmarked_status"]) == "UNKNOWN" else str(record["unmarked_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "marking_status": FrameSignal(
            frame_ids=frame_ids,
            values=marking_values,
            unknown_mask=[value is None for value in marking_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "marking_status").entity_scope,
        ),
        "marking_status_records": records,
        "unmarked_status": FrameSignal(
            frame_ids=frame_ids,
            values=unmarked_values,
            unknown_mask=[value is None for value in unmarked_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "unmarked_status").entity_scope,
        ),
        "unmarked_status_records": records,
        "nearest_marker_distance_m": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("nearest_marker_distance_m") for record in records],
            unknown_mask=[record.get("nearest_marker_distance_m") is None for record in records],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "nearest_marker_distance_m").entity_scope,
        ),
        "nearest_marker_distance_m_records": records,
    }
def primitive_off_ball_run(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    frame_field = node_parameter_text(node, "frame_field")
    candidate_scope = node_parameter_text(node, "candidate_scope")
    lookahead_seconds = node_parameter_number(node, "lookahead_seconds")
    minimum_run_displacement_m = node_parameter_number(node, "minimum_run_displacement_m")
    minimum_run_speed_mps = node_parameter_number(node, "minimum_run_speed_mps")
    minimum_ball_distance_m = node_parameter_number(node, "minimum_ball_distance_m")
    minimum_observed_candidates = node_parameter_integer(node, "minimum_observed_candidates")
    maximum_missing_candidate_ratio = node_parameter_number(node, "maximum_missing_candidate_ratio")
    records = [
        off_ball_run_anchor_record(
            state=state,
            anchor=record,
            frame_field=frame_field,
            candidate_scope=candidate_scope,
            lookahead_seconds=lookahead_seconds,
            minimum_run_displacement_m=minimum_run_displacement_m,
            minimum_run_speed_mps=minimum_run_speed_mps,
            minimum_ball_distance_m=minimum_ball_distance_m,
            minimum_observed_candidates=minimum_observed_candidates,
            maximum_missing_candidate_ratio=maximum_missing_candidate_ratio,
        )
        for record in runtime_records(anchor_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["off_ball_run_status"]) == "UNKNOWN" else str(record["off_ball_run_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "off_ball_run_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "off_ball_run_status").entity_scope,
        ),
        "off_ball_run_status_records": records,
        "run_speed_mps": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("run_speed_mps") for record in records],
            unknown_mask=[record.get("run_speed_mps") is None for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "run_speed_mps").entity_scope,
        ),
        "run_speed_mps_records": records,
    }
def primitive_off_ball_run_type(state: PeriodState, node: BoundCatalogNode) -> None:
    run_value = catalog_input_value(state, node, "runs")
    minimum_forward_progression_m = node_parameter_number(node, "minimum_forward_progression_m")
    minimum_lateral_displacement_m = node_parameter_number(node, "minimum_lateral_displacement_m")
    minimum_observed_defenders = node_parameter_integer(node, "minimum_observed_defenders")
    records = [
        off_ball_run_type_anchor_record(
            state=state,
            run=record,
            minimum_forward_progression_m=minimum_forward_progression_m,
            minimum_lateral_displacement_m=minimum_lateral_displacement_m,
            minimum_observed_defenders=minimum_observed_defenders,
        )
        for record in runtime_records(run_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    type_values = [
        None if str(record["off_ball_run_type_status"]) == "UNKNOWN" else str(record["off_ball_run_type_status"])
        for record in records
    ]
    behind_values = [
        None if str(record["run_in_behind_status"]) == "UNKNOWN" else str(record["run_in_behind_status"])
        for record in records
    ]
    diagonal_values = [
        None if str(record["diagonal_run_status"]) == "UNKNOWN" else str(record["diagonal_run_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "off_ball_run_type_status": FrameSignal(
            frame_ids=frame_ids,
            values=type_values,
            unknown_mask=[value is None for value in type_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "off_ball_run_type_status").entity_scope,
        ),
        "off_ball_run_type_status_records": records,
        "run_in_behind_status": FrameSignal(
            frame_ids=frame_ids,
            values=behind_values,
            unknown_mask=[value is None for value in behind_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "run_in_behind_status").entity_scope,
        ),
        "run_in_behind_status_records": records,
        "diagonal_run_status": FrameSignal(
            frame_ids=frame_ids,
            values=diagonal_values,
            unknown_mask=[value is None for value in diagonal_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "diagonal_run_status").entity_scope,
        ),
        "diagonal_run_status_records": records,
    }
def primitive_time_to_arrival(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    frame_field = node_parameter_text(node, "frame_field")
    target_mode = node_parameter_text(node, "target_mode")
    target_entity_field = node_parameter_text(node, "target_entity_field")
    target_x_field = node_parameter_text(node, "target_x_field")
    target_y_field = node_parameter_text(node, "target_y_field")
    candidate_scope = node_parameter_text(node, "candidate_scope")
    maximum_arrival_seconds = node_parameter_number(node, "maximum_arrival_seconds")
    maximum_player_speed_mps = node_parameter_number(node, "maximum_player_speed_mps")
    minimum_observed_candidates = node_parameter_integer(node, "minimum_observed_candidates")
    records = [
        time_to_arrival_anchor_record(
            state=state,
            anchor=record,
            frame_field=frame_field,
            target_mode=target_mode,
            target_entity_field=target_entity_field,
            target_x_field=target_x_field,
            target_y_field=target_y_field,
            candidate_scope=candidate_scope,
            maximum_arrival_seconds=maximum_arrival_seconds,
            maximum_player_speed_mps=maximum_player_speed_mps,
            minimum_observed_candidates=minimum_observed_candidates,
        )
        for record in runtime_records(anchor_value)
        if isinstance(record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["time_to_arrival_status"]) == "UNKNOWN" else str(record["time_to_arrival_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "minimum_arrival_seconds": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("minimum_arrival_seconds") for record in records],
            unknown_mask=[record.get("minimum_arrival_seconds") is None for record in records],
            unit=Unit.SECOND,
            entity_scope=catalog_output(node, "minimum_arrival_seconds").entity_scope,
        ),
        "minimum_arrival_seconds_records": records,
        "time_to_arrival_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "time_to_arrival_status").entity_scope,
        ),
        "time_to_arrival_status_records": records,
    }
def relation_support_arrival(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchor_records = anchor_value.value
    if not isinstance(anchor_records, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    anchor_frame_field = node_parameter_text(node, "anchor_frame_field")
    candidate_scope = node_parameter_text(node, "candidate_scope")
    support_region_mode = node_parameter_text(node, "support_region_mode")
    maximum_arrival_seconds = node_parameter_number(node, "maximum_arrival_seconds")
    minimum_duration_seconds = node_parameter_number(node, "minimum_duration_seconds")
    maximum_support_distance_m = node_parameter_number(node, "maximum_support_distance_m")
    minimum_supporting_players = node_parameter_integer(node, "minimum_supporting_players")
    required_anchor_status_field = node_parameter_text(node, "required_anchor_status_field")
    required_anchor_status_value = node_parameter_text(node, "required_anchor_status_value")
    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    attack_x_sign = attack_x_sign_for(
        orientation,
        state.match_id,
        state.period,
        state.perspective_team_role,
    )
    records = [
        support_arrival_anchor_record(
            state=state,
            anchor=anchor,
            anchor_frame_field=anchor_frame_field,
            candidate_scope=candidate_scope,
            support_region_mode=support_region_mode,
            maximum_arrival_seconds=maximum_arrival_seconds,
            minimum_duration_seconds=minimum_duration_seconds,
            maximum_support_distance_m=maximum_support_distance_m,
            minimum_supporting_players=minimum_supporting_players,
            required_anchor_status_field=required_anchor_status_field,
            required_anchor_status_value=required_anchor_status_value,
            attack_x_sign=attack_x_sign,
        )
        for anchor in anchor_records
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["support_arrival_status"]) == "UNKNOWN" else str(record["support_arrival_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "support_arrival_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "support_arrival_status").entity_scope,
        ),
        "support_arrival_status_records": records,
    }
def marking_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    target_player_id_field: str,
    candidate_scope: str,
    maximum_marking_distance_m: float,
    minimum_observed_marker_candidates: int,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    marking_frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or marking_frame_id is None:
        return None
    target_player_id = str(anchor.get(target_player_id_field) or "")
    target_point = tracked_point_at_frame(state, marking_frame_id, target_player_id)
    target_team_role = marking_target_team_role(state, anchor, marking_frame_id, target_player_id)
    candidate_team_role = marking_candidate_team_role(state, anchor, candidate_scope, target_team_role)
    model = "nearest_observed_opposition_distance_at_anchor_v0_1"
    assignment_policy = "observed nearest-opponent proximity only; no marker assignment, responsibility, or scheme inference"
    claim_boundary = (
        "Observed nearest-opposition proximity only; no marking assignment, defensive scheme, "
        "man-or-zone responsibility, role, intent, communication, causation, quality, or optimality claim."
    )

    def base(status: str, unmarked_status: str, reason: str, **extra: Any) -> dict[str, Any]:
        return {
            **anchor,
            "match_id": state.match_id,
            "period": state.period,
            "anchor_id": str(anchor.get("anchor_id")),
            "anchor_frame_id": anchor_frame_id,
            "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
            "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
            "entity_refs": list(anchor.get("entity_refs") or []),
            "marking_status": status,
            "unmarked_status": unmarked_status,
            "marking_reason": reason,
            "marking_frame_id": marking_frame_id,
            "target_player_id_field": target_player_id_field,
            "target_player_id": target_player_id or None,
            "target_player_team_role": target_team_role,
            "candidate_scope": candidate_scope,
            "candidate_team_role": candidate_team_role,
            "nearest_marker_id": extra.get("nearest_marker_id"),
            "nearest_marker_distance_m": extra.get("nearest_marker_distance_m"),
            "target_player_point": extra.get("target_player_point"),
            "nearest_marker_point": extra.get("nearest_marker_point"),
            "maximum_marking_distance_m": round(float(maximum_marking_distance_m), 3),
            "minimum_observed_marker_candidates": int(minimum_observed_marker_candidates),
            "observed_marker_candidate_count": extra.get("observed_marker_candidate_count", 0),
            "observed_marker_candidate_ids": extra.get("observed_marker_candidate_ids", []),
            "marking_model": model,
            "marking_assignment_policy": assignment_policy,
            "coverage_status": "UNKNOWN" if status == "UNKNOWN" else "PASS",
            "marking_claim_boundary": claim_boundary,
        }

    if not target_player_id:
        return base("UNKNOWN", "UNKNOWN", "target_player_id_missing")
    if target_point is None:
        return base("UNKNOWN", "UNKNOWN", "target_tracking_missing")
    if candidate_team_role not in {"home", "away"}:
        return base("UNKNOWN", "UNKNOWN", "candidate_team_role_missing")
    outfield_ids = outfield_player_ids(state.canonical_root, state.match_id, candidate_team_role)
    candidates = [
        item
        for item in cached_observed_outfield_positions_at_frame(state, marking_frame_id, candidate_team_role, outfield_ids)
        if item.get("x_m") is not None and item.get("y_m") is not None
    ]
    candidate_ids = sorted(str(item["player_id"]) for item in candidates)
    coverage_payload = {
        "observed_marker_candidate_count": len(candidates),
        "observed_marker_candidate_ids": candidate_ids,
    }
    if len(candidates) < int(minimum_observed_marker_candidates):
        return base("UNKNOWN", "UNKNOWN", "insufficient_observed_marker_candidates", **coverage_payload)
    nearest = min(
        candidates,
        key=lambda item: (
            math.dist(target_point, (float(item["x_m"]), float(item["y_m"]))),
            str(item["player_id"]),
        ),
    )
    nearest_point = (float(nearest["x_m"]), float(nearest["y_m"]))
    nearest_distance = math.dist(target_point, nearest_point)
    marked = nearest_distance <= float(maximum_marking_distance_m)
    return base(
        "PASS" if marked else "FAIL",
        "FAIL" if marked else "PASS",
        "nearest_marker_within_threshold" if marked else "nearest_marker_outside_threshold",
        **coverage_payload,
        nearest_marker_id=str(nearest["player_id"]),
        nearest_marker_distance_m=round(float(nearest_distance), 3),
        target_player_point=point_from_xy(target_point[0], target_point[1]),
        nearest_marker_point=point_from_xy(nearest_point[0], nearest_point[1]),
    )
def marking_target_team_role(state: PeriodState, anchor: dict[str, Any], frame_id: int, target_player_id: str) -> str | None:
    if target_player_id:
        record = player_records_at_frame(state, frame_id).get(str(target_player_id))
        if record is not None:
            team_role = str(record.get("team_role") or "")
            if team_role in {"home", "away"}:
                return team_role
    team_role = str(anchor.get("team_role") or "")
    return team_role if team_role in {"home", "away"} else None
def marking_candidate_team_role(
    state: PeriodState,
    anchor: dict[str, Any],
    candidate_scope: str,
    target_team_role: str | None,
) -> str | None:
    if candidate_scope == "defending_outfield":
        return state.defending_team_role
    if candidate_scope == "perspective_outfield":
        return state.perspective_team_role
    if candidate_scope == "opposition_outfield_to_anchor_team":
        team_role = target_team_role or str(anchor.get("team_role") or "")
        if team_role == "home":
            return "away"
        if team_role == "away":
            return "home"
        return None
    return None
def off_ball_run_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    candidate_scope: str,
    lookahead_seconds: float,
    minimum_run_displacement_m: float,
    minimum_run_speed_mps: float,
    minimum_ball_distance_m: float,
    minimum_observed_candidates: int,
    maximum_missing_candidate_ratio: float,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    start_frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or start_frame_id is None:
        return None
    window_frames = max(1, int(math.ceil(max(lookahead_seconds, 0.2) * FRAME_RATE_HZ - 1e-9)))
    end_frame_id = int(start_frame_id) + window_frames
    candidate_team_role = off_ball_run_candidate_team_role(state, anchor, candidate_scope)
    excluded_player_ids = off_ball_run_excluded_player_ids(anchor)
    model = "anchor_scoped_outfield_endpoint_displacement_v0_1"
    distance_policy = "candidate must be at least the frozen ball-distance threshold from the ball at both observation endpoints"
    claim_boundary = (
        "Observed off-ball endpoint-window movement only; no run type, purpose, decoy, marker-dragging, "
        "space creation, role, intent, tactical causation, quality, or optimality claim."
    )

    def base(status: str, reason: str, **extra: Any) -> dict[str, Any]:
        run_player_id = None if extra.get("run_player_id") in {None, ""} else str(extra.get("run_player_id"))
        entity_refs = [] if run_player_id is None else [run_player_id]
        off_ball_anchor_id = anchor_record_id(
            match_id=state.match_id,
            period=state.period,
            anchor_frame_id=anchor_frame_id,
            start_frame_id=start_frame_id,
            end_frame_id=end_frame_id,
            entity_refs=entity_refs,
        )
        return {
            **anchor,
            "match_id": state.match_id,
            "period": state.period,
            "anchor_id": off_ball_anchor_id,
            "source_anchor_id": str(anchor.get("anchor_id") or ""),
            "anchor_frame_id": anchor_frame_id,
            "start_frame_id": start_frame_id,
            "end_frame_id": end_frame_id,
            "entity_refs": entity_refs,
            "off_ball_run_status": status,
            "off_ball_run_reason": reason,
            "run_player_id": run_player_id,
            "run_start_frame_id": start_frame_id,
            "run_end_frame_id": end_frame_id,
            "run_duration_seconds": round(window_frames / FRAME_RATE_HZ, 3),
            "run_displacement_m": extra.get("run_displacement_m"),
            "run_forward_progression_m": extra.get("run_forward_progression_m"),
            "run_lateral_displacement_m": extra.get("run_lateral_displacement_m"),
            "run_speed_mps": extra.get("run_speed_mps"),
            "run_start_ball_distance_m": extra.get("run_start_ball_distance_m"),
            "run_end_ball_distance_m": extra.get("run_end_ball_distance_m"),
            "run_start_point": extra.get("run_start_point"),
            "run_end_point": extra.get("run_end_point"),
            "candidate_scope": candidate_scope,
            "candidate_team_role": candidate_team_role,
            "excluded_player_ids": sorted(excluded_player_ids),
            "observed_candidate_count": extra.get("observed_candidate_count", 0),
            "expected_candidate_count": extra.get("expected_candidate_count", 0),
            "missing_candidate_count": extra.get("missing_candidate_count", 0),
            "missing_candidate_ratio": extra.get("missing_candidate_ratio"),
            "observed_candidate_ids": extra.get("observed_candidate_ids", []),
            "candidate_evaluation_sample": extra.get("candidate_evaluation_sample", []),
            "minimum_observed_candidates": int(minimum_observed_candidates),
            "minimum_run_displacement_m": round(float(minimum_run_displacement_m), 3),
            "minimum_run_speed_mps": round(float(minimum_run_speed_mps), 3),
            "minimum_ball_distance_m": round(float(minimum_ball_distance_m), 3),
            "maximum_missing_candidate_ratio": round(float(maximum_missing_candidate_ratio), 3),
            "off_ball_run_model": model,
            "off_ball_distance_policy": distance_policy,
            "tracking_quality_status": "UNKNOWN" if status == "UNKNOWN" else "PASS",
            "coverage_status": "UNKNOWN" if status == "UNKNOWN" else "PASS",
            "off_ball_run_claim_boundary": claim_boundary,
        }

    if candidate_team_role not in {"home", "away"}:
        return base("UNKNOWN", "candidate_team_role_missing")
    if end_frame_id > int(state.frame_ids[-1]):
        return base("UNKNOWN", "run_window_exceeds_period")
    ball_start = ball_point_at_frame(state, start_frame_id)
    ball_end = ball_point_at_frame(state, end_frame_id)
    if ball_start is None or ball_end is None:
        return base("UNKNOWN", "ball_endpoint_missing")

    outfield_ids = outfield_player_ids(state.canonical_root, state.match_id, candidate_team_role) - excluded_player_ids
    start_records = {
        str(item["player_id"]): item
        for item in cached_observed_outfield_positions_at_frame(state, start_frame_id, candidate_team_role, outfield_ids)
        if item.get("x_m") is not None and item.get("y_m") is not None
    }
    end_records = {
        str(item["player_id"]): item
        for item in cached_observed_outfield_positions_at_frame(state, end_frame_id, candidate_team_role, outfield_ids)
        if item.get("x_m") is not None and item.get("y_m") is not None
    }
    observed_denominator_ids = set(start_records) | set(end_records)
    observed_ids = sorted(set(start_records) & set(end_records))
    expected_candidate_count = len(observed_denominator_ids)
    missing_candidate_count = max(0, expected_candidate_count - len(observed_ids))
    missing_candidate_ratio = (
        None
        if expected_candidate_count == 0
        else round(float(missing_candidate_count) / float(expected_candidate_count), 3)
    )
    coverage_payload = {
        "expected_candidate_count": expected_candidate_count,
        "observed_candidate_count": len(observed_ids),
        "missing_candidate_count": missing_candidate_count,
        "missing_candidate_ratio": missing_candidate_ratio,
        "observed_candidate_ids": observed_ids,
    }
    if expected_candidate_count == 0:
        return base("UNKNOWN", "candidate_denominator_missing", **coverage_payload)
    if len(observed_ids) < int(minimum_observed_candidates):
        return base("UNKNOWN", "insufficient_observed_candidates", **coverage_payload)
    if missing_candidate_ratio is not None and float(missing_candidate_ratio) > maximum_missing_candidate_ratio:
        return base("UNKNOWN", "candidate_tracking_coverage_below_threshold", **coverage_payload)

    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    attack_x_sign = attack_x_sign_for(
        orientation,
        state.match_id,
        state.period,
        candidate_team_role,
    )
    candidate_records = [
        off_ball_run_candidate_record(
            player_id=player_id,
            start_record=start_records[player_id],
            end_record=end_records[player_id],
            ball_start=ball_start,
            ball_end=ball_end,
            duration_seconds=window_frames / FRAME_RATE_HZ,
            attack_x_sign=attack_x_sign,
            minimum_run_displacement_m=minimum_run_displacement_m,
            minimum_run_speed_mps=minimum_run_speed_mps,
            minimum_ball_distance_m=minimum_ball_distance_m,
        )
        for player_id in observed_ids
    ]
    candidate_records = sorted(
        candidate_records,
        key=lambda item: (
            item["candidate_status"] == "PASS",
            float(item.get("run_displacement_m") or 0.0),
            float(item.get("run_speed_mps") or 0.0),
        ),
        reverse=True,
    )
    if not candidate_records:
        return base("FAIL", "no_evaluable_off_ball_candidate", **coverage_payload)
    best = candidate_records[0]
    status = str(best["candidate_status"])
    reason = str(best["candidate_reason"])
    return base(
        status,
        reason,
        **coverage_payload,
        run_player_id=best["run_player_id"],
        run_displacement_m=best["run_displacement_m"],
        run_forward_progression_m=best["run_forward_progression_m"],
        run_lateral_displacement_m=best["run_lateral_displacement_m"],
        run_speed_mps=best["run_speed_mps"],
        run_start_ball_distance_m=best["run_start_ball_distance_m"],
        run_end_ball_distance_m=best["run_end_ball_distance_m"],
        run_start_point=best["run_start_point"],
        run_end_point=best["run_end_point"],
        candidate_evaluation_sample=candidate_records[:5],
    )
def off_ball_run_candidate_team_role(state: PeriodState, anchor: dict[str, Any], candidate_scope: str) -> str:
    if candidate_scope == "perspective_outfield":
        return state.perspective_team_role
    if candidate_scope == "defending_outfield":
        return state.defending_team_role
    team_role = str(anchor.get("team_role") or "")
    return team_role if team_role in {"home", "away"} else state.perspective_team_role
def off_ball_run_excluded_player_ids(anchor: dict[str, Any]) -> set[str]:
    excluded_fields = {
        "passer_id",
        "carrier_id",
        "relay_player_id",
        "input_passer_id",
    }
    excluded: set[str] = set()
    for field_name in excluded_fields:
        value = anchor.get(field_name)
        if value not in {None, ""}:
            excluded.add(str(value))
    return excluded
def off_ball_run_candidate_record(
    *,
    player_id: str,
    start_record: dict[str, Any],
    end_record: dict[str, Any],
    ball_start: tuple[float, float],
    ball_end: tuple[float, float],
    duration_seconds: float,
    attack_x_sign: int | None,
    minimum_run_displacement_m: float,
    minimum_run_speed_mps: float,
    minimum_ball_distance_m: float,
) -> dict[str, Any]:
    start_point = (float(start_record["x_m"]), float(start_record["y_m"]))
    end_point = (float(end_record["x_m"]), float(end_record["y_m"]))
    dx = float(end_point[0]) - float(start_point[0])
    dy = float(end_point[1]) - float(start_point[1])
    displacement = math.hypot(dx, dy)
    speed = displacement / max(float(duration_seconds), 1e-9)
    start_ball_distance = math.dist(start_point, ball_start)
    end_ball_distance = math.dist(end_point, ball_end)
    forward_progression = None if attack_x_sign not in {-1, 1} else dx * int(attack_x_sign)
    status = "PASS"
    reason = "off_ball_run_observed"
    if start_ball_distance < minimum_ball_distance_m or end_ball_distance < minimum_ball_distance_m:
        status = "FAIL"
        reason = "candidate_not_off_ball_at_endpoint"
    elif displacement < minimum_run_displacement_m:
        status = "FAIL"
        reason = "run_displacement_below_threshold"
    elif speed < minimum_run_speed_mps:
        status = "FAIL"
        reason = "run_speed_below_threshold"
    return {
        "run_player_id": str(player_id),
        "candidate_status": status,
        "candidate_reason": reason,
        "run_start_point": point_from_xy(start_point[0], start_point[1]),
        "run_end_point": point_from_xy(end_point[0], end_point[1]),
        "run_displacement_m": round(float(displacement), 3),
        "run_forward_progression_m": None if forward_progression is None else round(float(forward_progression), 3),
        "run_lateral_displacement_m": round(abs(float(dy)), 3),
        "run_speed_mps": round(float(speed), 3),
        "run_start_ball_distance_m": round(float(start_ball_distance), 3),
        "run_end_ball_distance_m": round(float(end_ball_distance), 3),
    }
def off_ball_run_type_anchor_record(
    *,
    state: PeriodState,
    run: dict[str, Any],
    minimum_forward_progression_m: float,
    minimum_lateral_displacement_m: float,
    minimum_observed_defenders: int,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(run.get("anchor_frame_id"))
    start_frame_id = optional_int(run.get("run_start_frame_id")) or optional_int(run.get("start_frame_id"))
    end_frame_id = optional_int(run.get("run_end_frame_id")) or optional_int(run.get("end_frame_id"))
    if anchor_frame_id is None or start_frame_id is None or end_frame_id is None:
        return None
    model = "observed_off_ball_run_endpoint_path_geometry_v0_1"
    claim_boundary = (
        "Observed off-ball run path geometry only; no decoy, marker-dragging, space creation, overlap/underlap role, "
        "third-player tactical purpose, intent, causation, quality, or optimality claim."
    )

    def base(
        *,
        type_status: str,
        behind_status: str,
        diagonal_status: str,
        reason: str,
        labels: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            **run,
            "match_id": state.match_id,
            "period": state.period,
            "anchor_id": str(run.get("anchor_id")),
            "source_off_ball_run_anchor_id": str(run.get("anchor_id") or ""),
            "anchor_frame_id": anchor_frame_id,
            "start_frame_id": optional_int(run.get("start_frame_id")) or start_frame_id,
            "end_frame_id": optional_int(run.get("end_frame_id")) or end_frame_id,
            "entity_refs": list(run.get("entity_refs") or []),
            "off_ball_run_type_status": type_status,
            "off_ball_run_type_reason": reason,
            "run_in_behind_status": behind_status,
            "diagonal_run_status": diagonal_status,
            "observed_run_type_labels": labels or [],
            "minimum_forward_progression_m": round(float(minimum_forward_progression_m), 3),
            "minimum_lateral_displacement_m": round(float(minimum_lateral_displacement_m), 3),
            "minimum_observed_defenders": int(minimum_observed_defenders),
            "off_ball_run_type_model": model,
            "off_ball_run_type_claim_boundary": claim_boundary,
            "coverage_status": "UNKNOWN" if type_status == "UNKNOWN" else "PASS",
            **extra,
        }

    base_run_status = str(run.get("off_ball_run_status") or "UNKNOWN")
    if base_run_status == "UNKNOWN":
        return base(type_status="UNKNOWN", behind_status="UNKNOWN", diagonal_status="UNKNOWN", reason="base_off_ball_run_unknown")
    if base_run_status != "PASS":
        return base(type_status="FAIL", behind_status="FAIL", diagonal_status="FAIL", reason="base_off_ball_run_not_observed")

    start_point = point_tuple_from_payload(run.get("run_start_point"))
    end_point = point_tuple_from_payload(run.get("run_end_point"))
    run_player_id = str(run.get("run_player_id") or "")
    candidate_team_role = str(run.get("candidate_team_role") or "")
    if start_point is None or end_point is None or not run_player_id:
        return base(type_status="UNKNOWN", behind_status="UNKNOWN", diagonal_status="UNKNOWN", reason="run_endpoint_tracking_missing")
    if candidate_team_role not in {"home", "away"}:
        return base(type_status="UNKNOWN", behind_status="UNKNOWN", diagonal_status="UNKNOWN", reason="candidate_team_role_missing")

    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    attack_x_sign = attack_x_sign_for(orientation, state.match_id, state.period, candidate_team_role)
    if attack_x_sign not in {-1, 1}:
        return base(type_status="UNKNOWN", behind_status="UNKNOWN", diagonal_status="UNKNOWN", reason="attacking_direction_missing")
    dx = float(end_point[0]) - float(start_point[0])
    dy = float(end_point[1]) - float(start_point[1])
    forward_progression = dx * int(attack_x_sign)
    lateral_displacement = abs(dy)

    diagonal_status = (
        "PASS"
        if forward_progression >= minimum_forward_progression_m and lateral_displacement >= minimum_lateral_displacement_m
        else "FAIL"
    )

    opposition_team_role = "away" if candidate_team_role == "home" else "home"
    start_line = observed_opposition_line_x(
        state=state,
        frame_id=start_frame_id,
        team_role=opposition_team_role,
        attack_x_sign=int(attack_x_sign),
        minimum_observed_defenders=minimum_observed_defenders,
    )
    end_line = observed_opposition_line_x(
        state=state,
        frame_id=end_frame_id,
        team_role=opposition_team_role,
        attack_x_sign=int(attack_x_sign),
        minimum_observed_defenders=minimum_observed_defenders,
    )
    line_payload = {
        "run_player_id": run_player_id,
        "run_start_frame_id": start_frame_id,
        "run_end_frame_id": end_frame_id,
        "run_forward_progression_m": round(float(forward_progression), 3),
        "run_lateral_displacement_m": round(float(lateral_displacement), 3),
        "attacking_direction": "positive_x" if int(attack_x_sign) == 1 else "negative_x",
        "defensive_line_start_x_m": None if start_line is None else start_line["line_x_m"],
        "defensive_line_end_x_m": None if end_line is None else end_line["line_x_m"],
        "defensive_line_candidate_count_start": 0 if start_line is None else start_line["candidate_count"],
        "defensive_line_candidate_count_end": 0 if end_line is None else end_line["candidate_count"],
    }
    if start_line is None or end_line is None:
        behind_status = "UNKNOWN"
        line_reason = "defensive_line_tracking_missing"
        start_beyond = None
        end_beyond = None
    else:
        start_beyond = is_beyond_line(start_point[0], float(start_line["line_x_m"]), int(attack_x_sign))
        end_beyond = is_beyond_line(end_point[0], float(end_line["line_x_m"]), int(attack_x_sign))
        behind_status = (
            "PASS"
            if (not start_beyond) and end_beyond and forward_progression >= minimum_forward_progression_m
            else "FAIL"
        )
        line_reason = "run_crossed_behind_observed_line" if behind_status == "PASS" else "run_did_not_cross_behind_observed_line"
    labels: list[str] = []
    if behind_status == "PASS":
        labels.append("run_in_behind")
    if diagonal_status == "PASS":
        labels.append("diagonal_run")
    if labels:
        type_status = "PASS"
        reason = "observed_run_type:" + ",".join(labels)
    elif behind_status == "UNKNOWN":
        type_status = "UNKNOWN"
        reason = line_reason
    else:
        type_status = "FAIL"
        reason = "observed_run_type_threshold_not_met"
    return base(
        type_status=type_status,
        behind_status=behind_status,
        diagonal_status=diagonal_status,
        reason=reason,
        labels=labels,
        run_start_beyond_line=start_beyond,
        run_end_beyond_line=end_beyond,
        **line_payload,
    )
def point_tuple_from_payload(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, dict):
        return None
    point = point_from_xy(value.get("x_m"), value.get("y_m"))
    if point is None:
        return None
    return float(point["x_m"]), float(point["y_m"])
def observed_opposition_line_x(
    *,
    state: PeriodState,
    frame_id: int,
    team_role: str,
    attack_x_sign: int,
    minimum_observed_defenders: int,
) -> dict[str, Any] | None:
    outfield_ids = outfield_player_ids(state.canonical_root, state.match_id, team_role)
    candidates = [
        item
        for item in cached_observed_outfield_positions_at_frame(state, frame_id, team_role, outfield_ids)
        if item.get("x_m") is not None and item.get("y_m") is not None
    ]
    if len(candidates) < int(minimum_observed_defenders):
        return None
    xs = [float(item["x_m"]) for item in candidates]
    line_x = max(xs) if attack_x_sign == 1 else min(xs)
    return {
        "line_x_m": round(float(line_x), 3),
        "candidate_count": len(candidates),
        "candidate_ids": sorted(str(item["player_id"]) for item in candidates),
    }
def is_beyond_line(player_x: float, line_x: float, attack_x_sign: int) -> bool:
    return bool(float(player_x) > float(line_x)) if attack_x_sign == 1 else bool(float(player_x) < float(line_x))
def time_to_arrival_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_field: str,
    target_mode: str,
    target_entity_field: str,
    target_x_field: str,
    target_y_field: str,
    candidate_scope: str,
    maximum_arrival_seconds: float,
    maximum_player_speed_mps: float,
    minimum_observed_candidates: int,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    frame_id = optional_int(anchor.get(frame_field)) or anchor_frame_id
    if anchor_frame_id is None or frame_id is None:
        return None
    target_point, target_entity_id, target_reason = time_to_arrival_target_point(
        state=state,
        anchor=anchor,
        frame_id=frame_id,
        target_mode=target_mode,
        target_entity_field=target_entity_field,
        target_x_field=target_x_field,
        target_y_field=target_y_field,
    )
    candidate_records, known_candidate_ids = arrival_candidates(
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
    per_player: list[dict[str, Any]] = []
    if target_point is not None and maximum_player_speed_mps > 0:
        for record in observed_candidates:
            player_id = str(record["player_id"])
            point = (float(record["x_m"]), float(record["y_m"]))
            distance = math.dist(point, target_point)
            arrival_seconds = distance / maximum_player_speed_mps
            per_player.append(
                {
                    "player_id": player_id,
                    "distance_to_target_m": round(float(distance), 3),
                    "arrival_seconds": round(float(arrival_seconds), 3),
                    "arrives_within_threshold": arrival_seconds <= maximum_arrival_seconds,
                    "point": point_from_xy(point[0], point[1]),
                }
            )
    nearest = min(
        per_player,
        key=lambda item: (float(item["arrival_seconds"]), str(item["player_id"])),
        default=None,
    )
    arriving_player_ids = [
        str(item["player_id"])
        for item in per_player
        if bool(item.get("arrives_within_threshold"))
    ]
    if maximum_player_speed_mps <= 0:
        status = "UNKNOWN"
        reason = "invalid_arrival_speed"
    elif target_point is None:
        status = "UNKNOWN"
        reason = target_reason or "target_point_missing"
    elif len(observed_candidates) < max(1, minimum_observed_candidates):
        status = "UNKNOWN"
        reason = "candidate_tracking_missing"
    elif arriving_player_ids:
        status = "PASS"
        reason = "arrival_within_threshold"
    else:
        status = "FAIL"
        reason = "arrival_threshold_not_met"
    coverage_status = "COMPLETE" if not missing_candidate_ids else "OBSERVED_ONLY"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "time_to_arrival_status": status,
        "time_to_arrival_reason": reason,
        "arrival_frame_id": frame_id,
        "frame_field": frame_field,
        "target_mode": target_mode,
        "target_entity_field": target_entity_field,
        "target_entity_id": target_entity_id,
        "target_point": None if target_point is None else point_from_xy(target_point[0], target_point[1]),
        "candidate_scope": candidate_scope,
        "candidate_player_ids": sorted(str(player_id) for player_id in known_candidate_ids),
        "observed_candidate_player_ids": sorted(str(record["player_id"]) for record in observed_candidates),
        "missing_candidate_player_ids": missing_candidate_ids,
        "arrival_player_ids": sorted(arriving_player_ids),
        "nearest_arrival_player_id": None if nearest is None else str(nearest["player_id"]),
        "minimum_arrival_seconds": None if nearest is None else float(nearest["arrival_seconds"]),
        "nearest_arrival_distance_m": None if nearest is None else float(nearest["distance_to_target_m"]),
        "maximum_arrival_seconds": round(float(maximum_arrival_seconds), 3),
        "maximum_player_speed_mps": round(float(maximum_player_speed_mps), 3),
        "reachability_model": "straight_line_declared_max_speed_point_mass",
        "momentum_policy": "ignored_v0_1",
        "reachable_verdict_bias": "optimistic_for_reachable_conservative_for_unreachable",
        "minimum_observed_candidates": int(minimum_observed_candidates),
        "observed_candidate_count": len(observed_candidates),
        "coverage_status": coverage_status,
        "per_player_arrival_evidence": per_player,
    }
def time_to_arrival_target_point(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_id: int,
    target_mode: str,
    target_entity_field: str,
    target_x_field: str,
    target_y_field: str,
) -> tuple[tuple[float, float] | None, str | None, str | None]:
    if target_mode == "ball":
        return ball_point_at_frame(state, frame_id), "ball", None
    if target_mode == "entity":
        entity_id = str(anchor.get(target_entity_field) or "")
        return tracked_point_at_frame(state, frame_id, entity_id), entity_id or None, None
    if target_mode == "fields":
        point = point_from_xy(anchor.get(target_x_field), anchor.get(target_y_field))
        return None if point is None else (float(point["x_m"]), float(point["y_m"])), None, None
    return None, None, "unsupported_target_mode"
def support_arrival_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    anchor_frame_field: str,
    candidate_scope: str,
    support_region_mode: str,
    maximum_arrival_seconds: float,
    minimum_duration_seconds: float,
    maximum_support_distance_m: float,
    minimum_supporting_players: int,
    required_anchor_status_field: str,
    required_anchor_status_value: str,
    attack_x_sign: int | None,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    support_anchor_frame_id = optional_int(anchor.get(anchor_frame_field))
    if support_anchor_frame_id is None and anchor_frame_field != "anchor_frame_id":
        support_anchor_frame_id = anchor_frame_id
    if anchor_frame_id is None or support_anchor_frame_id is None:
        return None
    if required_anchor_status_field != "none":
        anchor_status = anchor.get(required_anchor_status_field)
        if anchor_status is None or str(anchor_status) == "UNKNOWN":
            return support_arrival_prefilter_record(
                state=state,
                anchor=anchor,
                anchor_frame_id=anchor_frame_id,
                support_anchor_frame_id=support_anchor_frame_id,
                anchor_frame_field=anchor_frame_field,
                support_region_mode=support_region_mode,
                maximum_arrival_seconds=maximum_arrival_seconds,
                minimum_duration_seconds=minimum_duration_seconds,
                maximum_support_distance_m=maximum_support_distance_m,
                minimum_supporting_players=minimum_supporting_players,
                candidate_scope=candidate_scope,
                required_anchor_status_field=required_anchor_status_field,
                required_anchor_status_value=required_anchor_status_value,
                status="UNKNOWN",
                reason="required_anchor_status_unknown",
            )
        if str(anchor_status) != required_anchor_status_value:
            return support_arrival_prefilter_record(
                state=state,
                anchor=anchor,
                anchor_frame_id=anchor_frame_id,
                support_anchor_frame_id=support_anchor_frame_id,
                anchor_frame_field=anchor_frame_field,
                support_region_mode=support_region_mode,
                maximum_arrival_seconds=maximum_arrival_seconds,
                minimum_duration_seconds=minimum_duration_seconds,
                maximum_support_distance_m=maximum_support_distance_m,
                minimum_supporting_players=minimum_supporting_players,
                candidate_scope=candidate_scope,
                required_anchor_status_field=required_anchor_status_field,
                required_anchor_status_value=required_anchor_status_value,
                status="FAIL",
                reason="required_anchor_status_not_met",
            )
    if candidate_scope == "defending_outfield":
        team_role = state.defending_team_role
    else:
        team_role = state.perspective_team_role
    known_outfield_ids = outfield_player_ids(state.canonical_root, state.match_id, team_role)
    excluded_ids = {
        str(value)
        for value in (
            anchor.get("passer_id"),
            anchor.get("receiver_id"),
        )
        if value is not None
    }
    horizon_seconds = max(0.0, maximum_arrival_seconds) + max(0.0, minimum_duration_seconds)
    support_window_end_frame_id = support_anchor_frame_id + int(math.ceil(horizon_seconds * FRAME_RATE_HZ - 1e-9))
    candidate_positions = cached_observed_outfield_positions_between_frames(
        state,
        start_frame_id=support_anchor_frame_id,
        end_frame_id=support_window_end_frame_id,
        team_role=team_role,
        outfield_ids=known_outfield_ids,
        excluded_player_ids=excluded_ids,
    )
    reference_point = anchor_reference_point(anchor)
    if reference_point is None:
        reference_point = cached_observed_player_point_at_frame(
            state,
            frame_id=support_anchor_frame_id,
            player_id=anchor.get("receiver_id"),
        )
    evaluation = evaluate_support_arrival_relation(
        anchor_id=str(anchor.get("anchor_id")),
        anchor_frame_id=support_anchor_frame_id,
        reference_player_id=anchor.get("receiver_id"),
        reference_point=reference_point,
        candidate_positions=candidate_positions,
        analysis_rate_hz=FRAME_RATE_HZ,
        config=SupportArrivalConfig(
            support_region_mode=support_region_mode,
            maximum_arrival_seconds=maximum_arrival_seconds,
            minimum_duration_seconds=minimum_duration_seconds,
            maximum_support_distance_m=maximum_support_distance_m,
            minimum_supporting_players=minimum_supporting_players,
            attacking_direction=attack_x_sign,
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
        "support_arrival_status": str(payload["status"]),
        "support_arrival_reason": payload["reason"],
        "support_anchor_frame_field": anchor_frame_field,
        "support_anchor_frame_id": support_anchor_frame_id,
        "support_window_start_frame_id": payload["support_window_start_frame_id"],
        "support_window_end_frame_id": payload["support_window_end_frame_id"],
        "support_window_start_seconds_after_anchor": payload["support_window_start_seconds_after_anchor"],
        "support_window_end_seconds_after_anchor": payload["support_window_end_seconds_after_anchor"],
        "support_region_mode": support_region_mode,
        "maximum_arrival_seconds": maximum_arrival_seconds,
        "minimum_duration_seconds": minimum_duration_seconds,
        "maximum_support_distance_m": maximum_support_distance_m,
        "minimum_supporting_players": minimum_supporting_players,
        "candidate_scope": candidate_scope,
        "candidate_team_role": team_role,
        "required_anchor_status_field": required_anchor_status_field,
        "required_anchor_status_value": required_anchor_status_value,
        "candidate_player_ids": list(payload["candidate_player_ids"]),
        "evaluated_candidate_player_ids": list(payload["evaluated_candidate_player_ids"]),
        "supporting_player_ids": list(payload["supporting_player_ids"]),
        "first_arrival_frame_id": payload["first_arrival_frame_id"],
        "first_arrival_seconds_after_anchor": payload["first_arrival_seconds_after_anchor"],
        "support_duration_seconds": payload["support_duration_seconds"],
        "missing_candidate_player_ids": list(payload["missing_candidate_player_ids"]),
        "invalid_candidate_player_ids": list(payload["invalid_candidate_player_ids"]),
        "invalid_coordinate_player_ids": list(payload["invalid_coordinate_player_ids"]),
        "duplicate_candidate_player_ids": list(payload["duplicate_candidate_player_ids"]),
        "missing_frame_ids": list(payload["missing_frame_ids"]),
        "invalid_frame_ids": list(payload["invalid_frame_ids"]),
        "missing_reference_frame_ids": list(payload["missing_reference_frame_ids"]),
        "invalid_reference_frame_ids": list(payload["invalid_reference_frame_ids"]),
        "duplicate_reference_frame_ids": list(payload["duplicate_reference_frame_ids"]),
        "per_player_evidence": payload["per_player_evidence"],
        "coverage_status": payload["coverage_status"],
        "config_evidence": payload["config_evidence"],
        "reference_player_id": payload["reference_player_id"],
        "reference_point": reference_point,
        "observed_candidate_record_count": len(candidate_positions),
    }
def support_arrival_prefilter_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    anchor_frame_id: int,
    support_anchor_frame_id: int,
    anchor_frame_field: str,
    support_region_mode: str,
    maximum_arrival_seconds: float,
    minimum_duration_seconds: float,
    maximum_support_distance_m: float,
    minimum_supporting_players: int,
    candidate_scope: str,
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
        "support_arrival_status": status,
        "support_arrival_reason": reason,
        "support_anchor_frame_field": anchor_frame_field,
        "support_anchor_frame_id": support_anchor_frame_id,
        "support_window_start_frame_id": support_anchor_frame_id,
        "support_window_end_frame_id": support_anchor_frame_id,
        "support_region_mode": support_region_mode,
        "maximum_arrival_seconds": maximum_arrival_seconds,
        "minimum_duration_seconds": minimum_duration_seconds,
        "maximum_support_distance_m": maximum_support_distance_m,
        "minimum_supporting_players": minimum_supporting_players,
        "candidate_scope": candidate_scope,
        "candidate_team_role": None,
        "required_anchor_status_field": required_anchor_status_field,
        "required_anchor_status_value": required_anchor_status_value,
        "candidate_player_ids": [],
        "evaluated_candidate_player_ids": [],
        "supporting_player_ids": [],
        "first_arrival_frame_id": None,
        "first_arrival_seconds_after_anchor": None,
        "support_duration_seconds": 0.0,
        "missing_candidate_player_ids": [],
        "invalid_candidate_player_ids": [],
        "invalid_coordinate_player_ids": [],
        "duplicate_candidate_player_ids": [],
        "missing_frame_ids": [],
        "invalid_frame_ids": [],
        "missing_reference_frame_ids": [],
        "invalid_reference_frame_ids": [],
        "duplicate_reference_frame_ids": [],
        "per_player_evidence": [],
        "coverage_status": "UNKNOWN" if status == "UNKNOWN" else "NOT_EVALUATED",
        "config_evidence": {
            "prefiltered": True,
            "required_anchor_status_field": required_anchor_status_field,
            "required_anchor_status_value": required_anchor_status_value,
        },
        "reference_player_id": anchor.get("receiver_id"),
        "reference_point": anchor_reference_point(anchor),
        "observed_candidate_record_count": 0,
    }
def cached_observed_outfield_positions_between_frames(
    state: PeriodState,
    *,
    start_frame_id: int,
    end_frame_id: int,
    team_role: str,
    outfield_ids: set[str],
    excluded_player_ids: set[str],
) -> list[dict[str, Any]]:
    key = (
        "observed_outfield_positions_between_frames",
        int(start_frame_id),
        int(end_frame_id),
        team_role,
        tuple(sorted(str(value) for value in outfield_ids)),
        tuple(sorted(str(value) for value in excluded_player_ids)),
    )
    if key not in state.lookup_cache:
        allowed_ids = {str(value) for value in outfield_ids} - {
            str(value) for value in excluded_player_ids
        }
        result: list[dict[str, Any]] = []
        for frame_id in range(int(start_frame_id), int(end_frame_id) + 1):
            for record in player_records_at_frame_for_team(state, frame_id, team_role):
                if record["player_id"] not in allowed_ids:
                    continue
                result.append(dict(record))
        state.lookup_cache[key] = result
    return state.lookup_cache[key]
