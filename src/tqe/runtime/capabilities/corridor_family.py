"""Corridor and destination-entry capability implementations.

F2-3 relocates this family from executor.py without changing behavior.  Shared
runtime helpers remain in executor.py until the shared-kernel extraction phase.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any

from tqe.evidence.observation_manifest import ObservationModality, gate_state_absence_status
from tqe.runtime.executor import (
    FRAME_RATE_HZ,
    PeriodState,
    catalog_input_value,
    node_parameter_integer,
    node_parameter_number,
    node_parameter_text,
    optional_int,
    predicate_traces_for_anchor,
    runtime_anchor_from_record,
    runtime_records,
    typed_enum,
    typed_number,
)
from tqe.runtime.ir import BoundCatalogNode, PredicateTrace, Unit
from tqe.runtime.relations import (
    CorridorConfig,
    destination_region_bounds,
    evaluate_geometric_progressive_corridors,
)
from tqe.runtime.values import FrameSignal


def relation_anchor_source(node: BoundCatalogNode) -> str:
    anchor_reference = node.inputs.get("anchors")
    if anchor_reference is None:
        return "missing"
    return f"{anchor_reference.source_node_id}.{anchor_reference.output_name}"


def relation_anchor_results(state: PeriodState, node: BoundCatalogNode) -> list[dict[str, Any]]:
    raw_anchors = runtime_records(catalog_input_value(state, node, "anchors"))
    anchor_results: list[dict[str, Any]] = []
    for anchor in raw_anchors:
        if not isinstance(anchor, dict):
            continue
        normalized = normalized_relation_anchor(state, anchor)
        if normalized is not None:
            anchor_results.append(normalized)
    anchor_results.sort(
        key=lambda item: (
            str(item["match_id"]),
            str(item["period"]),
            int(item["anchor_frame_id"]),
            str(item["result_id"]),
        )
    )
    return anchor_results


def normalized_relation_anchor(state: PeriodState, anchor: dict[str, Any]) -> dict[str, Any] | None:
    if not relation_anchor_has_required_fields(anchor):
        return None
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    result_id = str(anchor.get("result_id") or anchor.get("anchor_id") or "")
    if not result_id:
        return None
    return {
        **anchor,
        "result_id": result_id,
        "match_id": str(anchor.get("match_id") or state.match_id),
        "period": str(anchor.get("period") or state.period),
        "perspective_team_role": str(anchor.get("perspective_team_role") or state.perspective_team_role),
        "defending_team_role": str(anchor.get("defending_team_role") or state.defending_team_role),
        "anchor_frame_id": anchor_frame_id,
        "outcome_frame_id": optional_int(anchor.get("outcome_frame_id"))
        or optional_int(anchor.get("end_frame_id"))
        or min(int(state.frame_ids[-1]), anchor_frame_id + FRAME_RATE_HZ * 4),
        "replay_start_frame_id": optional_int(anchor.get("replay_start_frame_id"))
        or max(int(state.frame_ids[0]), anchor_frame_id - FRAME_RATE_HZ * 2),
        "replay_end_frame_id": optional_int(anchor.get("replay_end_frame_id"))
        or min(int(state.frame_ids[-1]), anchor_frame_id + FRAME_RATE_HZ * 6),
    }


def relation_anchor_has_required_fields(anchor: dict[str, Any]) -> bool:
    required_fields = {
        "match_id",
        "period",
        "anchor_frame_id",
    }
    has_identity = "result_id" in anchor or "anchor_id" in anchor
    return has_identity and required_fields.issubset(anchor)






def relation_geometric_progressive_corridor(state: PeriodState, node: BoundCatalogNode) -> None:
    source_results = relation_anchor_results(state, node)
    if not source_results:
        state.signals[node.node_id] = {
            "episodes": [],
            "anchor_evaluations": [],
            "source_results": [],
            "summary": {
                "episode_count": 0,
                "result_count_with_episode": 0,
                "anchor_source": relation_anchor_source(node),
            },
        }
        return

    config = CorridorConfig(
        analysis_rate_hz=state.params.integer("analysis_rate_hz"),
        max_window_seconds=node_parameter_number(node, "max_window_seconds"),
        minimum_progression_m=node_parameter_number(node, "minimum_progression_m"),
        minimum_segment_length_m=node_parameter_number(node, "minimum_segment_length_m"),
        maximum_segment_length_m=node_parameter_number(node, "maximum_segment_length_m"),
        minimum_clearance_m=node_parameter_number(node, "minimum_clearance_m"),
        open_after_frames=node_parameter_integer(node, "open_after_frames"),
        close_after_frames=node_parameter_integer(node, "close_after_frames"),
    )
    relation_report = evaluate_geometric_progressive_corridors(
        results=source_results,
        canonical_root=state.canonical_root,
        config=config,
    )
    episodes = relation_report["episodes"]
    side_filter = node_parameter_text(node, "side_filter")
    minimum_duration_seconds = node_parameter_number(node, "minimum_duration_seconds")
    source_by_result_id = {str(result["result_id"]): result for result in source_results}
    filtered = [
        {
            **episode,
            "source_result": source_by_result_id.get(str(episode["result_id"])),
            "relation_anchor_source": relation_anchor_source(node),
        }
        for episode in episodes
        if float(episode["duration_seconds"]) >= minimum_duration_seconds
        and relation_side_matches(
            episode=episode,
            source_result=source_by_result_id.get(str(episode["result_id"])),
            side_filter=side_filter,
        )
    ]
    filtered.sort(
        key=lambda item: (
            item["result_id"],
            -float(item["duration_seconds"]),
            -float(item["minimum_clearance_m"]),
            int(item["open_frame_id"]),
            item["relation_id"],
        )
    )
    anchor_evaluations = relation_anchor_evaluations_from_filtered(
        source_results=source_results,
        filtered=filtered,
        raw_anchor_evaluations=relation_report.get("anchor_evaluations") or [],
    )
    state.signals[node.node_id] = {
        "episodes": filtered,
        "anchor_evaluations": anchor_evaluations,
        "source_results": source_results,
        "anchor_source": relation_anchor_source(node),
        "summary": {
            **relation_report["summary"],
            "filtered_episode_count": len(filtered),
            "filtered_result_count_with_episode": len({item["result_id"] for item in filtered}),
            "filtered_anchor_evaluation_counts": dict(
                sorted(Counter(item["evaluation_status"] for item in anchor_evaluations).items())
            ),
            "anchor_source": relation_anchor_source(node),
            "side_filter": side_filter,
            "minimum_duration_seconds": minimum_duration_seconds,
        },
        "config": relation_report["config"],
        "artifact_hash": relation_report["artifact_hash"],
    }


def relation_anchor_evaluations_from_filtered(
    *,
    source_results: list[dict[str, Any]],
    filtered: list[dict[str, Any]],
    raw_anchor_evaluations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_by_result_id = {
        str(record.get("result_id")): record
        for record in raw_anchor_evaluations
        if isinstance(record, dict) and record.get("result_id") is not None
    }
    filtered_by_result_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in filtered:
        filtered_by_result_id[str(episode["result_id"])].append(episode)

    evaluations: list[dict[str, Any]] = []
    for source_result in source_results:
        result_id = str(source_result["result_id"])
        raw = raw_by_result_id.get(result_id, {})
        episodes = filtered_by_result_id.get(result_id, [])
        base = {
            **raw,
            "relation": "geometric_progressive_corridor",
            "relation_version": "0.1.0",
            "result_id": result_id,
            "anchor_id": str(source_result.get("anchor_id") or result_id),
            "match_id": str(source_result["match_id"]),
            "period": str(source_result["period"]),
            "perspective_team_role": str(source_result["perspective_team_role"]),
            "defending_team_role": str(source_result["defending_team_role"]),
            "anchor_frame_id": int(source_result["anchor_frame_id"]),
            "source_result": source_result,
            "relation_anchor_source": raw.get("relation_anchor_source"),
        }
        if episodes:
            witness = selected_relation_episode(episodes)
            evaluations.append(
                {
                    **base,
                    "evaluation_status": "PASS",
                    "relation_count": len(episodes),
                    "witness_relation_id": str(witness["relation_id"]),
                    "unknown_reason": None,
                }
            )
            continue
        if raw.get("evaluation_status") == "UNKNOWN" or relation_coverage_has_unknown_evidence(raw):
            evaluations.append(
                {
                    **base,
                    "evaluation_status": "UNKNOWN",
                    "relation_count": 0,
                    "witness_relation_id": None,
                    "unknown_reason": raw.get("unknown_reason") or "mixed_relation_evidence_unavailable",
                }
            )
            continue
        evaluations.append(
            {
                **base,
                "evaluation_status": "FAIL",
                "relation_count": 0,
                "witness_relation_id": None,
                "unknown_reason": None,
            }
        )
    evaluations.sort(
        key=lambda item: (
            str(item["match_id"]),
            str(item["period"]),
            int(item["anchor_frame_id"]),
            str(item["result_id"]),
        )
    )
    return evaluations


def relation_coverage_has_unknown_evidence(record: dict[str, Any]) -> bool:
    counts = record.get("state_counts")
    if not isinstance(counts, dict):
        return False
    return int(counts.get("UNKNOWN") or 0) > 0 or int(counts.get("INVALID") or 0) > 0


def selected_relation_episode(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        episodes,
        key=lambda item: (
            -float(item["duration_seconds"]),
            -float(item["minimum_clearance_m"]),
            int(item["open_frame_id"]),
            str(item["relation_id"]),
        ),
    )[0]


def select_relation_episode(
    relation_candidates: list[dict[str, Any]],
    episode_selection: str,
) -> dict[str, Any]:
    if episode_selection != "first_by_duration_clearance":
        raise RuntimeError(f"Unsupported relation episode selection {episode_selection}")
    return sorted(
        relation_candidates,
        key=lambda item: (
            -float(item["duration_seconds"]),
            -float(item["minimum_clearance_m"]),
            int(item["open_frame_id"]),
            str(item["relation_id"]),
        ),
    )[0]


def relation_destination_evaluations(
    *,
    state: PeriodState,
    relation_candidates: list[dict[str, Any]],
    horizon_seconds: float,
    episode_selection: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    evaluated = [
        (
            episode,
            ball_entry_evaluation_into_destination_region(
                state=state,
                episode=episode,
                horizon_seconds=horizon_seconds,
            ),
        )
        for episode in relation_candidates
    ]
    if episode_selection == "first_by_duration_clearance":
        selected = select_relation_episode(relation_candidates, episode_selection)
        return [
            item
            for item in evaluated
            if str(item[0]["relation_id"]) == str(selected["relation_id"])
        ]
    if episode_selection != "entry_first_then_progression":
        raise RuntimeError(f"Unsupported relation episode selection {episode_selection}")
    return sorted(evaluated, key=relation_destination_evaluation_sort_key)


def relation_destination_evaluation_sort_key(
    item: tuple[dict[str, Any], dict[str, Any]],
) -> tuple[Any, ...]:
    episode, evaluation = item
    status = str(evaluation["entry_status"])
    status_rank = {"PASS": 0, "UNKNOWN": 1, "FAIL": 2}.get(status, 3)
    entry_frame = evaluation.get("entry", {}).get("frame_id") if isinstance(evaluation.get("entry"), dict) else None
    return (
        status_rank,
        int(entry_frame) if entry_frame is not None else int(episode["open_frame_id"]),
        -relation_progression_m(episode),
        -float(episode.get("duration_seconds") or 0.0),
        -float(episode.get("minimum_clearance_m") or 0.0),
        str(episode["relation_id"]),
    )


def relation_progression_m(episode: dict[str, Any]) -> float:
    source = episode.get("source_open_point")
    target = episode.get("target_open_point")
    if not isinstance(source, dict) or not isinstance(target, dict):
        return 0.0
    try:
        return float(target["x_m"]) - float(source["x_m"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def primitive_relation_destination_entry_classification(
    state: PeriodState,
    node: BoundCatalogNode,
) -> None:
    relation_value = catalog_input_value(state, node, "relation_episodes")
    relation_episodes = relation_value.value
    if not isinstance(relation_episodes, list):
        raise RuntimeError(f"{node.node_id} requires relation episode records")
    generic_entry_output = node.outputs[0].name == "entry_status"
    output_name = node.outputs[0].name
    episodes_by_result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_results_by_id: dict[str, dict[str, Any]] = {}
    for episode in relation_episodes:
        source_result = episode.get("source_result")
        if not isinstance(source_result, dict):
            continue
        source_result_id = str(source_result["result_id"])
        episodes_by_result[source_result_id].append(episode)
        source_results_by_id.setdefault(source_result_id, source_result)

    horizon_seconds = node_parameter_number(node, "destination_entry_horizon_seconds")
    result_seed = node.resolved_parameters.get("result_id_seed")
    seed = str(result_seed.value) if result_seed is not None else state.params.text("result_id_seed_hash")
    episode_selection = node_parameter_text(
        node,
        "episode_selection"
    )
    source_results = list(source_results_by_id.values())

    final_results: list[dict[str, Any]] = []
    final_traces: list[PredicateTrace] = []
    for source_result in source_results:
        source_result_id = str(source_result["result_id"])
        relation_candidates = episodes_by_result.get(source_result_id, [])
        if not relation_candidates:
            continue
        evaluations = relation_destination_evaluations(
            state=state,
            relation_candidates=relation_candidates,
            horizon_seconds=horizon_seconds,
            episode_selection=episode_selection,
        )
        selected_evaluations = evaluations if generic_entry_output else evaluations[:1]
        for episode, entry_evaluation in selected_evaluations:
            entry = entry_evaluation["entry"]
            entry_status = str(entry_evaluation["entry_status"])
            destination_entered = entry_status == "PASS"
            result_id = hashlib.sha256(
                (
                    f"{seed}:relation_destination_entry:"
                    f"{source_result_id}:{episode['relation_id']}"
                ).encode("utf-8")
            ).hexdigest()[:16]
            classification = (
                "DESTINATION_ENTERED"
                if destination_entered
                else "CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY"
            )
            replay_base_end = optional_int(source_result.get("replay_end_frame_id")) or int(episode["close_frame_id"])
            replay_end_frame_id = max(
                replay_base_end,
                int(episode["close_frame_id"]) + FRAME_RATE_HZ * 2,
                int(entry["frame_id"]) + FRAME_RATE_HZ * 2 if entry else int(episode["close_frame_id"]),
            )
            final_result = {
                **source_result,
                "result_id": result_id,
                "classification": classification,
                "entry_status": entry_status,
                "source_classification": source_result.get("classification"),
                "base_result_id": source_result_id,
                "relation_node_id": node.inputs["relation_episodes"].source_node_id,
                "relation_anchor_source": str(episode.get("relation_anchor_source", "")),
                "relation_episode_selection": episode_selection,
                "relation_id": episode["relation_id"],
                "relation_version": episode["relation_version"],
                "relation_open_frame_id": int(episode["open_frame_id"]),
                "relation_open_confirm_frame_id": int(episode["open_confirm_frame_id"]),
                "relation_close_frame_id": int(episode["close_frame_id"]),
                "relation_duration_seconds": float(episode["duration_seconds"]),
                "relation_target_player_id": episode["target_player_id"],
                "relation_minimum_clearance_m": float(episode["minimum_clearance_m"]),
                "relation_limiting_defender_id": episode["limiting_defender_id"],
                "destination_side": episode["destination_side"],
                "destination_lane": episode["destination_lane"],
                "destination_region": episode["destination_region"],
                "destination_region_type": episode["destination_region_type"],
                "destination_region_bounds": episode["destination_region_bounds"],
                "destination_entry_frame_id": int(entry["frame_id"]) if entry else None,
                "destination_entry_point": entry["point"] if entry else None,
                "time_to_entry_seconds": entry_evaluation["time_to_entry_seconds"],
                "entry_mode": entry_evaluation["entry_mode"],
                "destination_entry_horizon_seconds": horizon_seconds,
                "observed_window_start_frame_id": entry_evaluation["observed_window_start_frame_id"],
                "observed_window_end_frame_id": entry_evaluation["observed_window_end_frame_id"],
                "unknown_reason": entry_evaluation["unknown_reason"],
                "missing_ball_frame_count": entry_evaluation["missing_ball_frame_count"],
                "source_open_point": episode["source_open_point"],
                "target_open_point": episode["target_open_point"],
                "source_close_point": episode["source_close_point"],
                "target_close_point": episode["target_close_point"],
                "accepted": True,
                "replay_end_frame_id": min(int(state.frame_ids[-1]), replay_end_frame_id),
            }
            final_results.append(final_result)
            if not generic_entry_output:
                final_traces.extend(
                    experimental_predicate_traces_for_result(
                        state=state,
                        anchor_record=source_result,
                        source_result=source_result,
                        result=final_result,
                        episode=episode,
                        destination_entered=destination_entered,
                    )
                )

    final_results.sort(
        key=relation_destination_result_sort_key
    )
    state.accepted = final_results
    state.predicate_traces = final_traces
    signal_values = [
        None
        if generic_entry_output and str(item["entry_status"]) == "UNKNOWN"
        else str(item[output_name])
        for item in final_results
    ]
    state.signals[node.node_id] = {
        output_name: FrameSignal(
            frame_ids=[
                int(item.get("destination_entry_frame_id") or item["relation_close_frame_id"])
                for item in final_results
            ],
            values=signal_values,
            unknown_mask=[value is None for value in signal_values],
            unit=node.outputs[0].unit,
            entity_scope=node.outputs[0].entity_scope,
        ),
        f"{output_name}_records": final_results,
    }


def relation_destination_result_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    legacy_score = item.get("block_shift_score")
    legacy_frame = item.get("wide_entry_frame_id")
    if legacy_score is not None and legacy_frame is not None:
        return (
            0,
            -float(legacy_score),
            str(item["match_id"]),
            str(item["period"]),
            int(legacy_frame),
            str(item["relation_id"]),
        )
    return (
        1,
        str(item["match_id"]),
        str(item["period"]),
        int(item["anchor_frame_id"]),
        {"PASS": 0, "UNKNOWN": 1, "FAIL": 2}.get(str(item.get("entry_status")), 3),
        int(item.get("destination_entry_frame_id") or item["relation_open_frame_id"]),
        -relation_progression_m(item),
        int(item["relation_open_frame_id"]),
        str(item["relation_id"]),
    )




def relation_side_matches(
    *,
    episode: dict[str, Any],
    source_result: dict[str, Any] | None,
    side_filter: str,
) -> bool:
    if side_filter == "any":
        return True
    if source_result is None:
        return False
    ball_side = str(source_result.get("ball_side"))
    destination = str(episode.get("destination_side"))
    if side_filter == "opposite_ball_side":
        return destination == opposite_side(ball_side)
    if side_filter == "same_ball_side":
        return destination == ball_side
    raise RuntimeError(f"Unsupported relation side_filter {side_filter}")


def opposite_side(side: str) -> str:
    if side == "left":
        return "right"
    if side == "right":
        return "left"
    return "central"


def first_ball_entry_into_destination_region(
    *,
    state: PeriodState,
    episode: dict[str, Any],
    horizon_seconds: float,
) -> dict[str, Any] | None:
    evaluation = ball_entry_evaluation_into_destination_region(
        state=state,
        episode=episode,
        horizon_seconds=horizon_seconds,
    )
    return evaluation["entry"] if evaluation["entry_status"] == "PASS" else None


def ball_entry_evaluation_into_destination_region(
    *,
    state: PeriodState,
    episode: dict[str, Any],
    horizon_seconds: float,
) -> dict[str, Any]:
    start_frame_id = int(episode["open_frame_id"])
    requested_end_frame_id = start_frame_id + int(round(horizon_seconds * FRAME_RATE_HZ))
    available_end_frame_id = int(state.frame_ids[-1])
    observed_end_frame_id = min(available_end_frame_id, requested_end_frame_id)
    bounds = episode.get("destination_region_bounds") or destination_region_bounds(
        str(episode["destination_side"]),
        str(episode["destination_lane"]),
    )
    min_y = float(bounds["min_y_m"])
    max_y = float(bounds["max_y_m"])
    ball = state.positions[
        (state.positions.entity_type == "ball")
        & (state.positions.frame_id >= start_frame_id)
        & (state.positions.frame_id <= observed_end_frame_id)
    ].sort_values("frame_id")
    for row in ball.itertuples(index=False):
        y_m = float(row.y_m)
        if min_y <= y_m <= max_y:
            entry = {
                "frame_id": int(row.frame_id),
                "point": {"x_m": round(float(row.x_m), 3), "y_m": round(y_m, 3)},
                "region": episode["destination_region"],
                "region_type": episode.get("destination_region_type", "side_lane_band"),
                "region_bounds": bounds,
            }
            return {
                "entry_status": "PASS",
                "entry": entry,
                "entry_mode": "PRESENT_AT_OPEN"
                if int(row.frame_id) == start_frame_id
                else "ENTERED_AFTER_OPEN",
                "time_to_entry_seconds": round((int(row.frame_id) - start_frame_id) / FRAME_RATE_HZ, 3),
                "observed_window_start_frame_id": start_frame_id,
                "observed_window_end_frame_id": observed_end_frame_id,
                "unknown_reason": None,
                "missing_ball_frame_count": 0,
            }

    expected_frames = {
        int(frame_id)
        for frame_id in state.frame_ids
        if start_frame_id <= int(frame_id) <= observed_end_frame_id
    }
    observed_ball_frames = {int(frame_id) for frame_id in ball.frame_id.tolist()}
    missing_ball_frames = expected_frames - observed_ball_frames
    unknown_reasons: list[str] = []
    if not expected_frames:
        unknown_reasons.append("no_evaluated_frames")
    if requested_end_frame_id > available_end_frame_id:
        unknown_reasons.append("window_extends_beyond_available_tracking")
    if missing_ball_frames:
        unknown_reasons.append("missing_ball_frames")
    if unknown_reasons:
        return {
            "entry_status": "UNKNOWN",
            "entry": None,
            "entry_mode": "UNKNOWN",
            "time_to_entry_seconds": None,
            "observed_window_start_frame_id": start_frame_id,
            "observed_window_end_frame_id": observed_end_frame_id,
            "unknown_reason": ",".join(unknown_reasons),
            "missing_ball_frame_count": len(missing_ball_frames),
        }
    gated = gate_state_absence_status(
        state=state,
        start_frame_id=start_frame_id,
        end_frame_id=observed_end_frame_id,
        modalities=(ObservationModality.BALL,),
        status="FAIL",
        reason="destination_region_not_entered",
    )
    return {
        "entry_status": gated.status,
        "entry": None,
        "entry_mode": "NOT_ENTERED" if gated.status == "FAIL" else "UNKNOWN",
        "time_to_entry_seconds": None,
        "observed_window_start_frame_id": start_frame_id,
        "observed_window_end_frame_id": observed_end_frame_id,
        "unknown_reason": None if gated.status == "FAIL" else gated.reason,
        "missing_ball_frame_count": 0,
    }


def experimental_predicate_traces_for_result(
    *,
    state: PeriodState,
    anchor_record: dict[str, Any],
    source_result: dict[str, Any],
    result: dict[str, Any],
    episode: dict[str, Any],
    destination_entered: bool,
) -> list[PredicateTrace]:
    rewritten: list[PredicateTrace] = []
    anchor = runtime_anchor_from_record(
        state=state,
        node_id="relation_source",
        output_name="anchor",
        index=0,
        record=anchor_record,
    )
    source_traces = (
        predicate_traces_for_anchor(state, anchor, source_result)
        if anchor is not None
        else []
    )
    for trace in source_traces:
        payload = trace.model_dump(mode="python", exclude_none=True)
        payload["source_evidence"] = {
            **payload.get("source_evidence", {}),
            "result_id": result["result_id"],
            "base_result_id": source_result["result_id"],
            "experimental_plan_status": "experimental",
        }
        rewritten.append(PredicateTrace.model_validate(payload))

    rewritten.append(
        PredicateTrace(
            predicate_id="has_opposite_corridor",
            status="PASS",
            value=typed_number(1, Unit.COUNT),
            threshold=typed_number(1, Unit.COUNT),
            unit=Unit.COUNT,
            frame_id=int(episode["open_confirm_frame_id"]),
            window={
                "start_frame_id": int(episode["open_frame_id"]),
                "end_frame_id": int(episode["close_frame_id"]),
            },
            source_evidence={
                "result_id": result["result_id"],
                "base_result_id": source_result["result_id"],
                "relation_id": episode["relation_id"],
                "source_node_id": result["relation_node_id"],
                "destination_region": episode["destination_region"],
                "experimental_plan_status": "experimental",
            },
        )
    )
    rewritten.append(
        PredicateTrace(
            predicate_id="destination_region_entered",
            status="PASS" if destination_entered else "FAIL",
            value=typed_enum(
                result["destination_region"] if destination_entered else "NO_ENTRY"
            ),
            threshold=typed_enum(result["destination_region"]),
            unit=Unit.NONE,
            frame_id=result["destination_entry_frame_id"],
            window={
                "start_frame_id": int(episode["open_frame_id"]),
                "end_frame_id": min(
                    int(state.frame_ids[-1]),
                    int(
                        int(episode["open_frame_id"])
                        + round(result["destination_entry_horizon_seconds"] * FRAME_RATE_HZ)
                    ),
                ),
            },
            source_evidence={
                "result_id": result["result_id"],
                "base_result_id": source_result["result_id"],
                "relation_id": episode["relation_id"],
                "destination_region": result["destination_region"],
                "destination_entry_point": result["destination_entry_point"],
                "source_node_id": "relation_destination_entry_classification",
                "experimental_plan_status": "experimental",
            },
        )
    )
    return rewritten
