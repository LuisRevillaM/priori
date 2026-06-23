"""M2A S1C high-bypass completed-pass result emission.

This module applies the first M2A recipe threshold on top of the reusable
controlled-pass and opponent-bypass measurements. It deliberately keeps Hermes
and all-corpus execution blocked; the accepted runtime scope remains J03WOY.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from tqe.runtime.controlled_pass import (
    ACCEPTED_MATCH_IDS,
    ACCEPTED_PERIODS,
    DEFAULT_CANONICAL_ROOT,
    ControlledPassOutput,
    evaluate_controlled_passes,
)
from tqe.runtime.ir import PayloadType, PredicateTrace, QueryResult, TypedValue, Unit
from tqe.runtime.pass_bypass import PassBypassOutput, evaluate_pass_bypass_measurements


RECIPE_ID = "high_bypass_completed_pass_v1"
RECIPE_VERSION = "0.1.0"
CLASSIFICATION = "HIGH_BYPASS_COMPLETED_PASS"

REQUIRED_EVIDENCE_ALIASES = (
    "pass_episode_id",
    "anchor_id",
    "event_row_index",
    "passer_id",
    "receiver_id",
    "release_frame_id",
    "reception_frame_id",
    "release_match_time_ms",
    "reception_match_time_ms",
    "controlled_pass_status",
    "release_control_status",
    "controlled_reception_status",
    "possession_continuity_status",
    "coverage_status",
    "release_ball_point",
    "reception_ball_point",
    "release_passer_point",
    "reception_receiver_point",
    "forward_progression_m",
    "opponents_bypassed_count",
    "bypassed_player_ids",
    "candidate_goal_side_player_ids",
    "expected_active_opposition_outfield_ids",
    "evaluated_opponent_ids",
    "missing_active_opponent_ids",
    "goal_side_buffer_m",
    "bypassed_buffer_m",
    "evaluation_coverage_status",
    "unknown_reason",
)


@dataclass(frozen=True)
class HighBypassConfig:
    minimum_forward_progression_m: float = 8.0
    minimum_bypassed_opponents: int = 5
    goal_side_buffer_m: float = 1.0
    bypassed_buffer_m: float = 1.0


@dataclass(frozen=True)
class HighBypassOutput:
    schema_version: str
    recipe_id: str
    recipe_version: str
    status: str
    accepted_scope: dict[str, Any]
    config: dict[str, Any]
    summary: dict[str, Any]
    results: list[dict[str, Any]]
    predicate_traces: list[dict[str, Any]]
    non_match_examples: list[dict[str, Any]]


def emit_high_bypass_completed_pass_results(
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    controlled_passes: ControlledPassOutput | None = None,
    bypass_measurements: PassBypassOutput | None = None,
    match_ids: tuple[str, ...] | list[str] = ACCEPTED_MATCH_IDS,
    periods: tuple[str, ...] | list[str] = ACCEPTED_PERIODS,
    config: HighBypassConfig = HighBypassConfig(),
) -> HighBypassOutput:
    requested_match_ids = tuple(str(item) for item in match_ids)
    requested_periods = tuple(str(item) for item in periods)
    validate_scope(requested_match_ids, requested_periods)
    controlled = controlled_passes or evaluate_controlled_passes(
        canonical_root=canonical_root,
        match_ids=requested_match_ids,
        periods=requested_periods,
    )
    bypass = bypass_measurements or evaluate_pass_bypass_measurements(
        canonical_root=canonical_root,
        controlled_passes=controlled,
        match_ids=requested_match_ids,
        periods=requested_periods,
    )
    validate_runtime_scope(controlled, bypass)

    episodes_by_id = {str(item["pass_episode_id"]): item for item in controlled.episodes}
    controlled_eval_by_id = {
        str(item["pass_episode_id"]): item for item in controlled.anchor_evaluations
    }
    results: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    non_match_examples: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    evidence_failures: list[dict[str, Any]] = []

    for measurement in sorted_measurements(bypass.anchor_evaluations):
        decision, reason = classify_measurement(
            measurement=measurement,
            controlled_evaluation=controlled_eval_by_id.get(str(measurement["pass_episode_id"])),
            config=config,
        )
        if decision != "PASS":
            reason_counts[reason] += 1
            if len(non_match_examples) < 50:
                non_match_examples.append(non_match_record(measurement, decision, reason))
            continue

        episode = episodes_by_id.get(str(measurement["pass_episode_id"]))
        if episode is None:
            reason_counts["controlled_pass_episode_missing"] += 1
            if len(non_match_examples) < 50:
                non_match_examples.append(
                    non_match_record(measurement, "UNKNOWN", "controlled_pass_episode_missing")
                )
            continue

        result = build_result(
            measurement=measurement,
            episode=episode,
            canonical_root=canonical_root,
            config=config,
        )
        failures = missing_evidence_aliases(result["requested_evidence"])
        if failures:
            evidence_failures.append({"result_id": result["result_id"], "missing_aliases": failures})
            reason_counts["requested_evidence_missing"] += 1
            if len(non_match_examples) < 50:
                non_match_examples.append(
                    {
                        "pass_episode_id": measurement["pass_episode_id"],
                        "match_id": measurement["match_id"],
                        "period": measurement["period"],
                        "status": "UNKNOWN",
                        "reason": "requested_evidence_missing",
                        "missing_aliases": failures,
                    }
                )
            continue

        results.append(result)
        traces.extend(build_predicate_traces(result, config))

    results.sort(
        key=lambda item: (
            str(item["match_id"]),
            str(item["period"]),
            int(item["release_frame_id"]),
            int(item["reception_frame_id"]),
            str(item["pass_episode_id"]),
        )
    )
    traces.sort(
        key=lambda item: (
            str(item.get("source_evidence", {}).get("result_id", "")),
            str(item.get("predicate_id", "")),
        )
    )
    return HighBypassOutput(
        schema_version="m2a.high_bypass_completed_pass.v1",
        recipe_id=RECIPE_ID,
        recipe_version=RECIPE_VERSION,
        status="pass" if not evidence_failures else "fail",
        accepted_scope={
            "match_ids": list(ACCEPTED_MATCH_IDS),
            "periods": list(ACCEPTED_PERIODS),
            "all_corpus_execution": "blocked_until_m2a_active_player_policy_extends_beyond_j03woy",
            "hermes_exposure": "blocked_until_human_visual_review_accepts_m2a",
        },
        config=asdict(config),
        summary={
            "controlled_anchor_evaluation_count": len(controlled.anchor_evaluations),
            "bypass_anchor_evaluation_count": len(bypass.anchor_evaluations),
            "result_count": len(results),
            "classification_counts": dict(Counter(item["classification"] for item in results)),
            "non_match_reason_counts": dict(sorted(reason_counts.items())),
            "requested_evidence_failure_count": len(evidence_failures),
            "requested_evidence_failures": evidence_failures,
            "trace_count": len(traces),
        },
        results=results,
        predicate_traces=traces,
        non_match_examples=non_match_examples,
    )


def classify_measurement(
    *,
    measurement: dict[str, Any],
    controlled_evaluation: dict[str, Any] | None,
    config: HighBypassConfig,
) -> tuple[str, str]:
    if controlled_evaluation is None:
        return "UNKNOWN", "controlled_pass_evaluation_missing"
    if controlled_evaluation.get("controlled_pass_status") != "PASS":
        return "UNKNOWN", "controlled_pass_not_proven"
    if measurement.get("evaluation_status") != "PASS":
        return "UNKNOWN", str(measurement.get("failure_reason") or "bypass_coverage_unknown")
    progression = measurement.get("forward_progression_m")
    if progression is None or float(progression) < config.minimum_forward_progression_m:
        return "FAIL", "forward_progression_below_threshold"
    if int(measurement.get("opponents_bypassed_count") or 0) < config.minimum_bypassed_opponents:
        return "FAIL", "opponents_bypassed_below_threshold"
    return "PASS", "matched"


def build_result(
    *,
    measurement: dict[str, Any],
    episode: dict[str, Any],
    canonical_root: Path,
    config: HighBypassConfig,
) -> dict[str, Any]:
    release_frame_id = int(measurement["release_frame_id"])
    reception_frame_id = int(measurement["reception_frame_id"])
    anchor_id = action_anchor_id(measurement)
    result_id = result_id_for(anchor_id)
    requested_evidence = build_requested_evidence(
        measurement=measurement,
        episode=episode,
        canonical_root=canonical_root,
        anchor_id=anchor_id,
        release_frame_id=release_frame_id,
        reception_frame_id=reception_frame_id,
    )
    row = {
        "result_id": result_id,
        "classification": CLASSIFICATION,
        "match_id": str(measurement["match_id"]),
        "period": str(measurement["period"]),
        "anchor_frame_id": reception_frame_id,
        "anchor_id": anchor_id,
        "source_controlled_pass_anchor_id": str(measurement["anchor_id"]),
        "pass_episode_id": str(measurement["pass_episode_id"]),
        "release_frame_id": release_frame_id,
        "reception_frame_id": reception_frame_id,
        "start_frame_id": release_frame_id,
        "end_frame_id": reception_frame_id,
        "classification_rule": CLASSIFICATION,
        "matched_classification_rules": [CLASSIFICATION],
        "recipe_id": RECIPE_ID,
        "recipe_version": RECIPE_VERSION,
        "minimum_forward_progression_m": config.minimum_forward_progression_m,
        "minimum_bypassed_opponents": config.minimum_bypassed_opponents,
        "requested_evidence": requested_evidence,
    }
    QueryResult(
        result_id=result_id,
        classification=CLASSIFICATION,
        match_id=str(measurement["match_id"]),
        period=str(measurement["period"]),
        anchor_frame_id=reception_frame_id,
        evidence={key: value for key, value in row.items() if key != "result_id"},
    )
    return row


def build_requested_evidence(
    *,
    measurement: dict[str, Any],
    episode: dict[str, Any],
    canonical_root: Path,
    anchor_id: str,
    release_frame_id: int,
    reception_frame_id: int,
) -> dict[str, Any]:
    match_id = str(measurement["match_id"])
    period = str(measurement["period"])
    return {
        "pass_episode_id": str(measurement["pass_episode_id"]),
        "anchor_id": anchor_id,
        "source_controlled_pass_anchor_id": str(measurement["anchor_id"]),
        "event_row_index": int(measurement["event_row_index"]),
        "passer_id": str(measurement["passer_id"]),
        "receiver_id": str(measurement["receiver_id"]),
        "release_frame_id": release_frame_id,
        "reception_frame_id": reception_frame_id,
        "release_match_time_ms": canonical_match_time_ms(canonical_root, match_id, period, release_frame_id),
        "reception_match_time_ms": canonical_match_time_ms(canonical_root, match_id, period, reception_frame_id),
        "controlled_pass_status": "PASS",
        "release_control_status": str(episode["release_control_status"]),
        "controlled_reception_status": str(episode["controlled_reception_status"]),
        "possession_continuity_status": str(episode["possession_continuity_status"]),
        "coverage_status": str(measurement["coverage_status"]),
        "release_ball_point": point(float(measurement["release_ball_x_m"]), float(measurement["release_ball_y_m"])),
        "reception_ball_point": point(float(measurement["reception_ball_x_m"]), float(measurement["reception_ball_y_m"])),
        "release_passer_point": point(float(episode["passer_x_m"]), float(episode["passer_y_m"])),
        "reception_receiver_point": point(float(episode["receiver_x_m"]), float(episode["receiver_y_m"])),
        "forward_progression_m": float(measurement["forward_progression_m"]),
        "opponents_bypassed_count": int(measurement["opponents_bypassed_count"]),
        "bypassed_player_ids": list(measurement["bypassed_player_ids"]),
        "candidate_goal_side_player_ids": list(measurement["candidate_goal_side_ids"]),
        "expected_active_opposition_outfield_ids": list(measurement["expected_active_opponent_ids"]),
        "evaluated_opponent_ids": list(measurement["evaluated_opponent_ids"]),
        "missing_active_opponent_ids": list(measurement["missing_active_opponent_ids"]),
        "goal_side_buffer_m": float(measurement["goal_side_buffer_m"]),
        "bypassed_buffer_m": float(measurement["bypassed_buffer_m"]),
        "evaluation_coverage_status": str(measurement["coverage_status"]),
        "unknown_reason": measurement.get("failure_reason"),
    }


def build_predicate_traces(result: dict[str, Any], config: HighBypassConfig) -> list[dict[str, Any]]:
    evidence = result["requested_evidence"]
    source = {
        "result_id": result["result_id"],
        "anchor_id": result["anchor_id"],
        "pass_episode_id": result["pass_episode_id"],
        "source_recipe_id": RECIPE_ID,
    }
    traces = [
        PredicateTrace(
            predicate_id="controlled_pass_status_is_pass",
            status="PASS",
            value=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            threshold=TypedValue(payload_type=PayloadType.ENUM, value="PASS"),
            unit=Unit.NONE,
            frame_id=int(evidence["release_frame_id"]),
            source_evidence=source,
        ),
        PredicateTrace(
            predicate_id="forward_progression_at_least_minimum",
            status="PASS",
            value=TypedValue(
                payload_type=PayloadType.NUMBER,
                value=float(evidence["forward_progression_m"]),
                unit=Unit.METRE,
            ),
            threshold=TypedValue(
                payload_type=PayloadType.NUMBER,
                value=float(config.minimum_forward_progression_m),
                unit=Unit.METRE,
            ),
            unit=Unit.METRE,
            frame_id=int(evidence["reception_frame_id"]),
            source_evidence=source,
        ),
        PredicateTrace(
            predicate_id="opponents_bypassed_at_least_minimum",
            status="PASS",
            value=TypedValue(
                payload_type=PayloadType.NUMBER,
                value=int(evidence["opponents_bypassed_count"]),
                unit=Unit.COUNT,
            ),
            threshold=TypedValue(
                payload_type=PayloadType.NUMBER,
                value=int(config.minimum_bypassed_opponents),
                unit=Unit.COUNT,
            ),
            unit=Unit.COUNT,
            frame_id=int(evidence["reception_frame_id"]),
            source_evidence=source,
        ),
    ]
    return [trace.model_dump(mode="json") for trace in traces]


def validate_scope(match_ids: tuple[str, ...], periods: tuple[str, ...]) -> None:
    unsupported_matches = sorted(set(match_ids) - set(ACCEPTED_MATCH_IDS))
    unsupported_periods = sorted(set(periods) - set(ACCEPTED_PERIODS))
    if unsupported_matches:
        raise RuntimeError(
            "M2A high-bypass S1C is accepted only for "
            f"{ACCEPTED_MATCH_IDS}; unsupported={unsupported_matches}"
        )
    if unsupported_periods:
        raise RuntimeError(
            "M2A high-bypass S1C is accepted only for "
            f"periods {ACCEPTED_PERIODS}; unsupported={unsupported_periods}"
        )


def validate_runtime_scope(controlled: ControlledPassOutput, bypass: PassBypassOutput) -> None:
    rows = list(controlled.anchor_evaluations) + list(controlled.episodes) + list(bypass.anchor_evaluations)
    match_ids = {str(item.get("match_id")) for item in rows if item.get("match_id") is not None}
    periods = {str(item.get("period")) for item in rows if item.get("period") is not None}
    validate_scope(tuple(match_ids), tuple(periods))


def sorted_measurements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda item: (
            str(item["match_id"]),
            str(item["period"]),
            int(item.get("physical_release_frame_id") or -1),
            int(item.get("controlled_reception_frame_id") or -1),
            str(item["pass_episode_id"]),
        ),
    )


def non_match_record(measurement: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "pass_episode_id": str(measurement.get("pass_episode_id")),
        "match_id": str(measurement.get("match_id")),
        "period": str(measurement.get("period")),
        "event_row_index": measurement.get("event_row_index"),
        "release_frame_id": measurement.get("physical_release_frame_id") or measurement.get("release_frame_id"),
        "reception_frame_id": measurement.get("controlled_reception_frame_id") or measurement.get("reception_frame_id"),
        "status": status,
        "reason": reason,
        "forward_progression_m": measurement.get("forward_progression_m"),
        "opponents_bypassed_count": measurement.get("opponents_bypassed_count"),
        "evaluation_coverage_status": measurement.get("coverage_status"),
    }


def missing_evidence_aliases(evidence: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for alias in REQUIRED_EVIDENCE_ALIASES:
        if alias not in evidence:
            missing.append(alias)
            continue
        value = evidence[alias]
        if value is None and alias != "unknown_reason":
            missing.append(alias)
    return missing


def action_anchor_id(measurement: dict[str, Any]) -> str:
    identity = {
        "match_id": str(measurement["match_id"]),
        "period": str(measurement["period"]),
        "pass_episode_id": str(measurement["pass_episode_id"]),
        "release_frame_id": int(measurement["release_frame_id"]),
        "reception_frame_id": int(measurement["reception_frame_id"]),
    }
    return "m2a_anchor_" + stable_hash(identity)[:16]


def result_id_for(anchor_id: str) -> str:
    return "m2a_result_" + stable_hash(
        {
            "recipe_id": RECIPE_ID,
            "recipe_version": RECIPE_VERSION,
            "classification": CLASSIFICATION,
            "anchor_id": anchor_id,
        }
    )[:16]


def point(x_m: float, y_m: float) -> dict[str, float]:
    return {"x_m": float(x_m), "y_m": float(y_m)}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@lru_cache(maxsize=64)
def frame_time_lookup(canonical_root_str: str, match_id: str, period: str) -> dict[int, int]:
    frame_path = Path(canonical_root_str) / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
    frames = pd.read_parquet(frame_path, columns=["frame_id"])
    frame_ids = sorted(int(item) for item in frames["frame_id"].tolist())
    if not frame_ids:
        return {}
    first_frame = frame_ids[0]
    return {frame_id: int(round((frame_id - first_frame) / 25.0 * 1000)) for frame_id in frame_ids}


def canonical_match_time_ms(
    canonical_root: Path,
    match_id: str,
    period: str,
    frame_id: int,
) -> int | None:
    return frame_time_lookup(str(canonical_root), match_id, period).get(int(frame_id))
