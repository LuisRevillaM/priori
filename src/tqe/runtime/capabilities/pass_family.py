"""Pass-family capability implementations.

F2-2 moves these functions out of executor.py as pure relocation. Shared
runtime helpers stay in executor.py until later kernel extraction packets.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from tqe.runtime.controlled_pass import (
    ControlledPassConfig,
    ControlledPassOutput,
    align_event_to_frame,
    evaluate_controlled_passes,
)
from tqe.runtime.executor import (
    PeriodState,
    anchor_record_id,
    catalog_input_value,
    catalog_output,
    frame_match_time_ms,
    node_parameter_event_type_filter,
    node_parameter_number,
    node_parameter_text,
    optional_int,
    parquet_rows,
    point_from_xy,
)
from tqe.runtime.ir import BoundCatalogNode, Unit
from tqe.runtime.one_touch import (
    EVENT_COLUMNS,
    OneTouchRelayConfig,
    evaluate_one_touch_relays,
    parse_successful_pass_event,
)
from tqe.runtime.pass_bypass import PassBypassConfig, evaluate_pass_bypass_measurements
from tqe.runtime.possession_identity import possession_identity_at_frame
from tqe.runtime.values import FrameSignal


def primitive_action_event_anchor(state: PeriodState, node: BoundCatalogNode) -> None:
    action_type = node_parameter_text(node, "action_type")
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
        if action_type == "throw_in_successful_pass":
            parsed = parse_successful_pass_event(row, event_type_filter=("ThrowIn_Play_Pass",))
        elif action_type == "successful_pass":
            parsed = parse_successful_pass_event(row)
        else:
            parsed = None
        if parsed is None:
            continue
        anchor_frame_id, offset_ms = align_event_to_frame(parsed, frames)
        if anchor_frame_id is None:
            continue
        entity_refs = [str(parsed["passer_id"]), str(parsed["receiver_id"])]
        anchor_id = anchor_record_id(
            match_id=state.match_id,
            period=state.period,
            anchor_frame_id=anchor_frame_id,
            start_frame_id=anchor_frame_id,
            end_frame_id=anchor_frame_id,
            entity_refs=entity_refs,
        )
        records.append(
            {
                "anchor_id": anchor_id,
                "match_id": state.match_id,
                "period": state.period,
                "anchor_frame_id": anchor_frame_id,
                "start_frame_id": anchor_frame_id,
                "end_frame_id": anchor_frame_id,
                "entity_refs": entity_refs,
                "action_event_status": "PASS",
                "action_event_reason": "event_anchor_resolved",
                "action_type": action_type,
                "event_type": parsed["event_type"],
                "event_row_index": parsed["row_index"],
                "event_timestamp": parsed["event_timestamp"],
                "event_gameclock_seconds": parsed["gameclock_seconds"],
                "event_frame_offset_ms": offset_ms,
                "team_role": parsed["team_role"],
                "passer_id": parsed["passer_id"],
                "receiver_id": parsed["receiver_id"],
                "event_anchor_frame_id": anchor_frame_id,
            }
        )
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "action_event_status": FrameSignal(
            frame_ids=frame_ids,
            values=[record["action_event_status"] for record in records],
            unknown_mask=[False for _ in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "action_event_status").entity_scope,
        ),
        "action_event_status_records": records,
    }

def primitive_controlled_pass_episode(state: PeriodState, node: BoundCatalogNode) -> None:
    event_type_filter = node_parameter_event_type_filter(node)
    team_scope = node_parameter_text(node, "team_scope")
    config = ControlledPassConfig(
        event_type_filter=event_type_filter,
        max_release_alignment_ms=node_parameter_number(node, "max_release_alignment_ms"),
        release_search_before_seconds=node_parameter_number(node, "release_search_before_seconds"),
        release_search_after_seconds=node_parameter_number(node, "release_search_after_seconds"),
        reception_search_seconds=node_parameter_number(node, "reception_search_seconds"),
        control_distance_m=node_parameter_number(node, "control_distance_m"),
        nearest_teammate_margin_m=node_parameter_number(node, "nearest_teammate_margin_m"),
        minimum_receiver_dwell_seconds=node_parameter_number(node, "minimum_receiver_dwell_seconds"),
    )
    output = evaluate_controlled_passes(
        canonical_root=state.canonical_root,
        match_ids=(state.match_id,),
        periods=(state.period,),
        config=config,
    )
    evaluations = controlled_pass_evaluations_for_team_scope(
        output.anchor_evaluations,
        team_scope=team_scope,
        perspective_team_role=state.perspective_team_role,
    )
    anchors = [
        record
        for record in (
            controlled_pass_anchor_record(state, evaluation)
            for evaluation in evaluations
        )
        if record is not None
    ]
    anchor_by_pass_id = {str(record["pass_episode_id"]): record for record in anchors}
    episodes = [
        controlled_pass_episode_record(state, episode, anchor_by_pass_id.get(str(episode["pass_episode_id"])))
        for episode in output.episodes
        if anchor_by_pass_id.get(str(episode["pass_episode_id"])) is not None
    ]
    frame_ids = [int(record["anchor_frame_id"]) for record in anchors]
    state.signals[node.node_id] = {
        "candidate_evaluations_records": evaluations,
        "episodes": episodes,
        "episodes_records": episodes,
        "anchors": anchors,
        "anchors_records": anchors,
        "controlled_pass_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if str(record["controlled_pass_status"]) == "UNKNOWN" else str(record["controlled_pass_status"])
                for record in anchors
            ],
            unknown_mask=[str(record["controlled_pass_status"]) == "UNKNOWN" for record in anchors],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "controlled_pass_status").entity_scope,
        ),
        "controlled_pass_status_records": anchors,
        "forward_progression_m": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("forward_progression_m") for record in anchors],
            unknown_mask=[record.get("forward_progression_m") is None for record in anchors],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "forward_progression_m").entity_scope,
        ),
        "forward_progression_m_records": anchors,
    }


def controlled_pass_evaluations_for_team_scope(
    evaluations: list[dict[str, Any]],
    *,
    team_scope: str,
    perspective_team_role: str,
) -> list[dict[str, Any]]:
    if team_scope == "all":
        return list(evaluations)
    if team_scope != "perspective_team":
        raise RuntimeError(f"unsupported controlled-pass team_scope {team_scope}")
    return [
        evaluation
        for evaluation in evaluations
        if str(evaluation.get("team_role")) == perspective_team_role
    ]

def controlled_pass_anchor_record(state: PeriodState, evaluation: dict[str, Any]) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(evaluation.get("controlled_reception_frame_id")) or optional_int(
        evaluation.get("physical_release_frame_id")
    ) or optional_int(evaluation.get("event_anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    start_frame_id = optional_int(evaluation.get("physical_release_frame_id")) or anchor_frame_id
    end_frame_id = optional_int(evaluation.get("controlled_reception_frame_id")) or anchor_frame_id
    entity_refs = [str(evaluation.get("passer_id")), str(evaluation.get("receiver_id"))]
    anchor_id = anchor_record_id(
        match_id=state.match_id,
        period=state.period,
        anchor_frame_id=anchor_frame_id,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        entity_refs=entity_refs,
    )
    return {
        **evaluation,
        "source_controlled_pass_anchor_id": str(evaluation.get("anchor_id")),
        "anchor_id": anchor_id,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_frame_id": anchor_frame_id,
        "possession_id": possession_identity_at_frame(
            state,
            start_frame_id,
            str(evaluation.get("team_role") or ""),
        ),
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "entity_refs": entity_refs,
    }

def controlled_pass_episode_record(
    state: PeriodState,
    episode: dict[str, Any],
    anchor: dict[str, Any] | None,
) -> dict[str, Any]:
    release_frame_id = optional_int(episode.get("physical_release_frame_id")) or optional_int(episode.get("event_anchor_frame_id"))
    reception_frame_id = optional_int(episode.get("controlled_reception_frame_id")) or release_frame_id
    release_ball = point_from_xy(episode.get("release_ball_x_m"), episode.get("release_ball_y_m"))
    reception_ball = point_from_xy(episode.get("reception_ball_x_m"), episode.get("reception_ball_y_m"))
    release_passer = point_from_xy(episode.get("passer_x_m"), episode.get("passer_y_m"))
    reception_receiver = point_from_xy(episode.get("receiver_x_m"), episode.get("receiver_y_m"))
    return {
        **episode,
        "source_controlled_pass_anchor_id": str(episode.get("anchor_id")),
        "possession_id": (
            str(anchor.get("possession_id"))
            if anchor is not None and anchor.get("possession_id") is not None
            else possession_identity_at_frame(state, int(release_frame_id or reception_frame_id or 0), str(episode.get("team_role") or ""))
        ),
        "anchor_id": str(anchor["anchor_id"]) if anchor is not None else str(episode.get("anchor_id")),
        "anchor_frame_id": int(anchor["anchor_frame_id"]) if anchor is not None else int(reception_frame_id or 0),
        "start_frame_id": int(anchor["start_frame_id"]) if anchor is not None else int(release_frame_id or 0),
        "end_frame_id": int(anchor["end_frame_id"]) if anchor is not None else int(reception_frame_id or release_frame_id or 0),
        "entity_refs": list(anchor.get("entity_refs", [])) if anchor is not None else [str(episode.get("passer_id")), str(episode.get("receiver_id"))],
        "release_frame_id": release_frame_id,
        "reception_frame_id": reception_frame_id,
        "release_match_time_ms": frame_match_time_ms(state, release_frame_id),
        "reception_match_time_ms": frame_match_time_ms(state, reception_frame_id),
        "release_ball_point": release_ball,
        "reception_ball_point": reception_ball,
        "release_passer_point": release_passer,
        "reception_receiver_point": reception_receiver,
    }


def relation_controlled_pass_team_keyed_anchors(state: PeriodState, node: BoundCatalogNode) -> None:
    anchors_value = catalog_input_value(state, node, "controlled_pass_anchors")
    anchors = anchors_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires controlled_pass_anchors records")
    records = []
    for item in anchors:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        team_role = record.get("team_role")
        if team_role is not None:
            record["team_role"] = str(team_role)
        records.append(record)
    state.signals[node.node_id] = {
        "anchors": records,
        "anchors_records": records,
    }

def primitive_one_touch_relay_episode(state: PeriodState, node: BoundCatalogNode) -> None:
    config = OneTouchRelayConfig(
        event_type_filter=node_parameter_event_type_filter(node),
        max_release_alignment_ms=node_parameter_number(node, "max_release_alignment_ms"),
        relay_max_event_gap_seconds=node_parameter_number(node, "relay_max_event_gap_seconds"),
        relay_touch_distance_m=node_parameter_number(node, "relay_touch_distance_m"),
        maximum_relay_dwell_seconds=node_parameter_number(node, "maximum_relay_dwell_seconds"),
    )
    output = evaluate_one_touch_relays(
        canonical_root=state.canonical_root,
        match_ids=(state.match_id,),
        periods=(state.period,),
        config=config,
    )
    anchors = [
        one_touch_relay_anchor_record(state, evaluation)
        for evaluation in output.anchor_evaluations
    ]
    anchors = [record for record in anchors if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in anchors]
    state.signals[node.node_id] = {
        "anchor_evaluations": anchors,
        "anchor_evaluations_records": anchors,
        "episodes": [record for record in anchors if record.get("one_touch_relay_status") == "PASS"],
        "episodes_records": [record for record in anchors if record.get("one_touch_relay_status") == "PASS"],
        "one_touch_relay_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if str(record["one_touch_relay_status"]) == "UNKNOWN" else str(record["one_touch_relay_status"])
                for record in anchors
            ],
            unknown_mask=[str(record["one_touch_relay_status"]) == "UNKNOWN" for record in anchors],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "one_touch_relay_status").entity_scope,
        ),
        "one_touch_relay_status_records": anchors,
    }

def one_touch_relay_anchor_record(state: PeriodState, evaluation: dict[str, Any]) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(evaluation.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    start_frame_id = optional_int(evaluation.get("start_frame_id")) or anchor_frame_id
    end_frame_id = optional_int(evaluation.get("end_frame_id")) or anchor_frame_id
    entity_refs = list(evaluation.get("entity_refs") or [])
    anchor_id = anchor_record_id(
        match_id=state.match_id,
        period=state.period,
        anchor_frame_id=anchor_frame_id,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        entity_refs=entity_refs,
    )
    return {
        **evaluation,
        "source_one_touch_relay_anchor_id": str(evaluation.get("anchor_id")),
        "anchor_id": anchor_id,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "entity_refs": entity_refs,
        "relay_match_time_ms": frame_match_time_ms(state, anchor_frame_id),
        "input_release_match_time_ms": frame_match_time_ms(
            state,
            optional_int(evaluation.get("input_physical_release_frame_id")),
        ),
        "relay_release_match_time_ms": frame_match_time_ms(
            state,
            optional_int(evaluation.get("relay_physical_release_frame_id")),
        ),
    }

def relation_opponents_bypassed_by_action(state: PeriodState, node: BoundCatalogNode) -> None:
    episodes_value = catalog_input_value(state, node, "controlled_pass_episodes")
    anchors_value = catalog_input_value(state, node, "controlled_pass_anchors")
    episodes = episodes_value.value
    anchors = anchors_value.value
    if not isinstance(episodes, list) or not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires controlled pass episode and anchor records")
    controlled = ControlledPassOutput(
        schema_version="m2a.controlled_pass_episode.v1",
        capability="controlled_pass_episode",
        capability_version="0.1.0",
        status="pass",
        accepted_scope={
            "match_ids": [state.match_id],
            "periods": [state.period],
            "scope_policy": "executor_period_scope",
        },
        config={},
        summary={},
        episodes=[dict(item) for item in episodes if isinstance(item, dict)],
        anchor_evaluations=[dict(item) for item in anchors if isinstance(item, dict)],
        non_match_examples=[],
    )
    output = evaluate_pass_bypass_measurements(
        canonical_root=state.canonical_root,
        controlled_passes=controlled,
        match_ids=(state.match_id,),
        periods=(state.period,),
        config=PassBypassConfig(
            goal_side_buffer_m=node_parameter_number(node, "goal_side_buffer_m"),
            bypassed_buffer_m=node_parameter_number(node, "bypassed_buffer_m"),
        ),
    )
    episodes_by_id = {str(item.get("pass_episode_id")): item for item in episodes if isinstance(item, dict)}
    evaluations = [
        pass_bypass_anchor_record(state, evaluation, episodes_by_id.get(str(evaluation.get("pass_episode_id"))))
        for evaluation in output.anchor_evaluations
    ]
    evaluations = [record for record in evaluations if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in evaluations]
    count_values = [
        int(record["opponents_bypassed_count"]) if record.get("evaluation_status") == "PASS" else None
        for record in evaluations
    ]
    progression_values = [
        float(record["forward_progression_m"])
        if record.get("evaluation_status") == "PASS" and record.get("forward_progression_m") is not None
        else None
        for record in evaluations
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": evaluations,
        "anchor_evaluations_records": evaluations,
        "opponents_bypassed_count": FrameSignal(
            frame_ids=frame_ids,
            values=count_values,
            unknown_mask=[value is None for value in count_values],
            unit=Unit.COUNT,
            entity_scope=catalog_output(node, "opponents_bypassed_count").entity_scope,
        ),
        "opponents_bypassed_count_records": evaluations,
        "forward_progression_m": FrameSignal(
            frame_ids=frame_ids,
            values=progression_values,
            unknown_mask=[value is None for value in progression_values],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "forward_progression_m").entity_scope,
        ),
        "forward_progression_m_records": evaluations,
        "evaluation_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if str(record.get("evaluation_status") or "UNKNOWN") == "UNKNOWN" else str(record.get("evaluation_status"))
                for record in evaluations
            ],
            unknown_mask=[str(record.get("evaluation_status") or "UNKNOWN") == "UNKNOWN" for record in evaluations],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "evaluation_status").entity_scope,
        ),
        "evaluation_status_records": evaluations,
    }

def pass_bypass_anchor_record(
    state: PeriodState,
    evaluation: dict[str, Any],
    episode: dict[str, Any] | None,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(evaluation.get("controlled_reception_frame_id")) or optional_int(
        evaluation.get("reception_frame_id")
    ) or optional_int(evaluation.get("physical_release_frame_id")) or optional_int(evaluation.get("event_anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    release_frame_id = optional_int(evaluation.get("release_frame_id")) or optional_int(evaluation.get("physical_release_frame_id"))
    reception_frame_id = optional_int(evaluation.get("reception_frame_id")) or optional_int(
        evaluation.get("controlled_reception_frame_id")
    )
    start_frame_id = release_frame_id or anchor_frame_id
    end_frame_id = reception_frame_id or anchor_frame_id
    entity_refs = [str(evaluation.get("passer_id")), str(evaluation.get("receiver_id"))]
    anchor_id = anchor_record_id(
        match_id=state.match_id,
        period=state.period,
        anchor_frame_id=anchor_frame_id,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        entity_refs=entity_refs,
    )
    status = str(evaluation.get("evaluation_status") or "UNKNOWN")
    return {
        **evaluation,
        "source_controlled_pass_anchor_id": str(evaluation.get("anchor_id")),
        "anchor_id": anchor_id,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "entity_refs": entity_refs,
        "relation_count": 1 if status == "PASS" else 0,
        "witness_relation_id": str(evaluation.get("relation_id")) if evaluation.get("relation_id") else None,
        "release_frame_id": release_frame_id,
        "reception_frame_id": reception_frame_id,
        "release_match_time_ms": frame_match_time_ms(state, release_frame_id),
        "reception_match_time_ms": frame_match_time_ms(state, reception_frame_id),
        "controlled_pass_status": "PASS" if episode is not None else "UNKNOWN",
        "release_control_status": None if episode is None else episode.get("release_control_status"),
        "controlled_reception_status": None if episode is None else episode.get("controlled_reception_status"),
        "possession_continuity_status": None if episode is None else episode.get("possession_continuity_status"),
        "release_ball_point": point_from_xy(evaluation.get("release_ball_x_m"), evaluation.get("release_ball_y_m")),
        "reception_ball_point": point_from_xy(evaluation.get("reception_ball_x_m"), evaluation.get("reception_ball_y_m")),
        "release_passer_point": point_from_xy(
            None if episode is None else episode.get("passer_x_m"),
            None if episode is None else episode.get("passer_y_m"),
        ),
        "reception_receiver_point": point_from_xy(
            None if episode is None else episode.get("receiver_x_m"),
            None if episode is None else episode.get("receiver_y_m"),
        ),
        "bypassed_player_ids": list(evaluation.get("bypassed_player_ids") or []),
        "candidate_goal_side_player_ids": list(evaluation.get("candidate_goal_side_ids") or []),
        "expected_active_opposition_outfield_ids": list(evaluation.get("expected_active_opponent_ids") or []),
        "evaluated_opponent_ids": list(evaluation.get("evaluated_opponent_ids") or []),
        "missing_active_opponent_ids": list(evaluation.get("missing_active_opponent_ids") or []),
        "unknown_reason": evaluation.get("failure_reason"),
    }
