"""M1.1 deterministic query runtime.

Gate B executes the approved M1 primitive chain from a bound plan. The executor
is deliberately keyed by primitive/operator catalog entries, not recipe IDs.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from lxml import etree

from tqe.idsse.source_lock import SOURCE_VERSION
from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.ir import (
    BoundCatalogNode,
    BoundPredicateNode,
    BoundQueryPlan,
    ExecutionStatus,
    QueryExecution,
    QueryResult,
    TypedValue,
    stable_hash,
)

PERIODS = ("firstHalf", "secondHalf")
BALL_ENTITY_ID = "DFL-OBJ-0000XT"
BALL_TEAM_ID = "BALL"
FRAME_RATE_HZ = 25
PITCH_HALF_WIDTH_M = 34.0

DEFAULT_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")
DEFAULT_RAW_ROOT = Path("data/raw/idsse") / SOURCE_VERSION


@dataclass(frozen=True)
class RuntimeParameters:
    values: dict[str, Any]

    def number(self, name: str) -> float:
        value = self.values[name]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise RuntimeError(f"{name} must be numeric")
        return float(value)

    def integer(self, name: str) -> int:
        return int(round(self.number(name)))

    def text(self, name: str) -> str:
        value = self.values[name]
        if not isinstance(value, str):
            raise RuntimeError(f"{name} must be text")
        return value


@dataclass
class PeriodState:
    match_id: str
    period: str
    params: RuntimeParameters
    recipe_id: str
    recipe_version: str
    perspective_team_role: str
    perspective_team_id: str
    defending_team_role: str
    defending_team_id: str
    raw_tracking: Path
    positions: pd.DataFrame
    frame_ids: np.ndarray
    ball_y: np.ndarray
    possession_role: np.ndarray
    ball_alive: np.ndarray
    defender_count: pd.Series
    defender_centroid_y: pd.Series
    signals: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    accepted: list[dict[str, Any]] = field(default_factory=list)
    near_misses: list[dict[str, Any]] = field(default_factory=list)


PrimitiveImplementation = Callable[[PeriodState, BoundCatalogNode], None]
PredicateImplementation = Callable[[PeriodState, BoundPredicateNode], None]


class TacticalQueryExecutor:
    def __init__(
        self,
        *,
        canonical_root: Path = DEFAULT_CANONICAL_ROOT,
        raw_root: Path = DEFAULT_RAW_ROOT,
    ) -> None:
        self.canonical_root = canonical_root
        self.raw_root = raw_root
        self.primitives: dict[str, PrimitiveImplementation] = {
            "possession_segment": primitive_possession_segment,
            "ball_lateral_fraction": primitive_ball_lateral_fraction,
            "defensive_outfield_centroid": primitive_defensive_outfield_centroid,
            "signed_lateral_shift": primitive_signed_lateral_shift,
            "outcome_classification": primitive_outcome_classification,
            "wide_channel_dwell": primitive_noop,
            "shift_persistence": primitive_noop,
            "robust_team_width": primitive_noop,
            "analysis_rate": primitive_noop,
        }
        self.predicates: dict[str, PredicateImplementation] = {
            "gt": predicate_gt,
            "gte": predicate_gte,
            "lte": predicate_lte,
            "eq": predicate_eq,
            "neq": predicate_neq,
            "persists_for": predicate_persists_for,
            "exists": predicate_noop,
            "count_at_least": predicate_noop,
        }

    def execute(self, bound_plan: BoundQueryPlan) -> QueryExecution:
        params = runtime_parameters(bound_plan)
        results: list[dict[str, Any]] = []
        trace_records: list[dict[str, Any]] = []

        for match_id in bound_plan.match_ids:
            match_results, match_traces = self._execute_match(
                bound_plan=bound_plan,
                match_id=match_id,
                params=params,
            )
            results.extend(match_results)
            trace_records.extend(match_traces)

        query_results = [
            QueryResult(
                result_id=result["result_id"],
                classification=result["classification"],
                match_id=result["match_id"],
                period=result["period"],
                anchor_frame_id=result["anchor_frame_id"],
                evidence={key: value for key, value in result.items() if key != "result_id"},
            )
            for result in results
        ]
        execution_id = hashlib.sha256(
            json.dumps(
                {
                    "bound_plan_hash": bound_plan.bound_plan_hash,
                    "result_ids": [result.result_id for result in query_results],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:16]
        return QueryExecution(
            execution_id=execution_id,
            status=ExecutionStatus.PASS,
            plan_hash=bound_plan.plan_hash,
            bound_plan_hash=bound_plan.bound_plan_hash,
            results=query_results,
            predicate_traces=[],
            provenance={
                "generated_at": utc_now_iso(),
                "canonical_root": str(self.canonical_root),
                "raw_root": str(self.raw_root),
                "runtime_result_count": len(query_results),
                "runtime_trace_hash": stable_hash(trace_records),
            },
        )

    def _execute_match(
        self,
        *,
        bound_plan: BoundQueryPlan,
        match_id: str,
        params: RuntimeParameters,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []
        for period in bound_plan.periods:
            state = self._period_state(
                match_id=match_id,
                period=period,
                perspective_team_role=bound_plan.perspective_team_role,
                recipe_id=bound_plan.recipe_id,
                recipe_version=bound_plan.recipe_version,
                params=params,
            )
            for node in bound_plan.nodes:
                if isinstance(node, BoundCatalogNode):
                    implementation = self.primitives.get(node.catalog_ref)
                    if implementation is None:
                        raise RuntimeError(f"No primitive implementation for {node.catalog_ref}")
                    implementation(state, node)
                elif isinstance(node, BoundPredicateNode):
                    implementation = self.predicates.get(node.operator.name)
                    if implementation is None:
                        raise RuntimeError(f"No predicate implementation for {node.operator.name}")
                    implementation(state, node)
            accepted.extend(state.accepted)
            traces.extend(runtime_trace_rows(state))
        accepted.sort(
            key=lambda item: (
                -float(item["block_shift_score"]),
                item["match_id"],
                item["period"],
                item["wide_entry_frame_id"],
            )
        )
        return accepted, traces

    def _period_state(
        self,
        *,
        match_id: str,
        period: str,
        perspective_team_role: str,
        recipe_id: str,
        recipe_version: str,
        params: RuntimeParameters,
    ) -> PeriodState:
        positions_path = self.canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
        positions = parquet_rows(
            positions_path,
            ["frame_id", "team_id", "team_role", "entity_id", "entity_type", "x_m", "y_m"],
        )
        ball = (
            positions[positions.entity_type == "ball"][["frame_id", "x_m", "y_m"]]
            .sort_values("frame_id")
            .reset_index(drop=True)
        )
        raw_tracking = self.raw_root / match_id / "tracking.xml"
        state = stream_ball_state(raw_tracking, period)
        full_frame = ball.merge(state, on="frame_id").sort_values("frame_id").reset_index(drop=True)
        analysis_rate_hz = params.integer("analysis_rate_hz")
        if FRAME_RATE_HZ % analysis_rate_hz != 0:
            raise RuntimeError(f"analysis_rate_hz={analysis_rate_hz} must divide source {FRAME_RATE_HZ} Hz")
        analysis_step = FRAME_RATE_HZ // analysis_rate_hz
        frame = full_frame.iloc[::analysis_step].reset_index(drop=True)
        frame_ids = frame.frame_id.to_numpy(dtype=np.int64)
        frame_gaps_ms = np.diff(frame_ids) / FRAME_RATE_HZ * 1000.0
        if len(frame_gaps_ms) and float(np.max(frame_gaps_ms)) > params.number("maximum_analysis_gap_ms"):
            raise RuntimeError(f"Analysis stream gap exceeds maximum for {match_id} {period}")

        defending_role = "away" if perspective_team_role == "home" else "home"
        defending_outfield = outfield_player_ids(self.canonical_root, match_id, defending_role)
        defenders = positions[
            (positions.entity_type == "player")
            & (positions.team_role == defending_role)
            & (positions.entity_id.astype(str).isin(defending_outfield))
        ]
        return PeriodState(
            match_id=match_id,
            period=period,
            params=params,
            recipe_id=recipe_id,
            recipe_version=recipe_version,
            perspective_team_role=perspective_team_role,
            perspective_team_id=team_id(self.canonical_root, match_id, perspective_team_role),
            defending_team_role=defending_role,
            defending_team_id=team_id(self.canonical_root, match_id, defending_role),
            raw_tracking=raw_tracking,
            positions=positions,
            frame_ids=frame_ids,
            ball_y=frame.y_m.to_numpy(dtype=float),
            possession_role=frame.possession_team_role.to_numpy(dtype=object),
            ball_alive=frame.ball_alive.to_numpy(dtype=bool),
            defender_count=defenders.groupby("frame_id").entity_id.nunique(),
            defender_centroid_y=defenders.groupby("frame_id").y_m.mean().sort_index(),
        )


def runtime_parameters(bound_plan: BoundQueryPlan) -> RuntimeParameters:
    return RuntimeParameters(
        values={item.name: item.value.value for item in bound_plan.resolved_parameters}
    )


def primitive_noop(state: PeriodState, node: BoundCatalogNode) -> None:
    state.signals.setdefault(node.node_id, {})


def primitive_possession_segment(state: PeriodState, node: BoundCatalogNode) -> None:
    possession_mask = (state.possession_role == state.perspective_team_role) & state.ball_alive
    minimum_frames = int(round(state.params.number("minimum_possession_seconds") * state.params.integer("analysis_rate_hz")))
    segments = [
        {
            "start_index": start,
            "end_index": end,
            "start_frame_id": int(state.frame_ids[start]),
            "end_frame_id": int(state.frame_ids[end]),
        }
        for start, end in segment_true(possession_mask, minimum_frames)
    ]
    state.signals[node.node_id] = {"episodes": segments}


def primitive_ball_lateral_fraction(state: PeriodState, node: BoundCatalogNode) -> None:
    state.signals[node.node_id] = {
        "fraction": np.abs(state.ball_y) / PITCH_HALF_WIDTH_M,
        "ball_y": state.ball_y,
    }


def primitive_defensive_outfield_centroid(state: PeriodState, node: BoundCatalogNode) -> None:
    state.signals[node.node_id] = {"centroid_y": state.defender_centroid_y}


def primitive_signed_lateral_shift(state: PeriodState, node: BoundCatalogNode) -> None:
    candidates = state.signals.get("wide_entry_persists", {}).get("candidates", [])
    baseline_frames = int(round(state.params.number("baseline_window_seconds") * state.params.integer("analysis_rate_hz")))
    search_frames = int(round(state.params.number("shift_search_window_seconds") * state.params.integer("analysis_rate_hz")))
    shifted: list[dict[str, Any]] = []

    for candidate in candidates:
        segment_frame_ids = candidate["segment_frame_ids"]
        entry_idx = int(candidate["entry_index"])
        side_sign = int(candidate["side_sign"])
        baseline_start_frame = int(segment_frame_ids[max(0, entry_idx - baseline_frames)])
        baseline_end_frame = int(segment_frame_ids[entry_idx - 1])
        baseline_series = state.defender_centroid_y.loc[
            (state.defender_centroid_y.index >= baseline_start_frame)
            & (state.defender_centroid_y.index <= baseline_end_frame)
        ]
        if baseline_series.empty:
            continue
        baseline_centroid_y = float(baseline_series.mean())
        search_end = min(len(segment_frame_ids), entry_idx + search_frames)
        search_frame_ids = segment_frame_ids[entry_idx:search_end]
        search_series = state.defender_centroid_y.loc[
            state.defender_centroid_y.index.isin(search_frame_ids)
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
                "baseline_start_frame_id": baseline_start_frame,
                "baseline_end_frame_id": baseline_end_frame,
                "baseline_defensive_centroid_y_m": round(baseline_centroid_y, 3),
                "anchor_frame_id": anchor_frame_id,
                "signed_shift_metres": round(max_shift, 3),
                "block_shift_score": round(max_shift, 6),
                "quality_status": "pass" if enough_defenders else "fail",
                "enough_defenders": enough_defenders,
                "signed_shift_series": signed_shift,
            }
        )
    state.candidates = shifted
    state.signals[node.node_id] = {"signed_shift": shifted}


def primitive_outcome_classification(state: PeriodState, node: BoundCatalogNode) -> None:
    accepted: list[dict[str, Any]] = []
    near_misses: list[dict[str, Any]] = []
    query_hash = state.params.text("result_id_seed_hash")
    analysis_rate_hz = state.params.integer("analysis_rate_hz")
    dedupe_source_frames = int(round(state.params.number("dedupe_window_seconds") * FRAME_RATE_HZ))
    last_kept_by_segment: dict[tuple[int, int], int] = {}
    frame_index = {int(frame_id): index for index, frame_id in enumerate(state.frame_ids)}

    for candidate in state.candidates:
        segment_key = (
            int(candidate["possession_start_frame_id"]),
            int(candidate["possession_end_frame_id"]),
        )
        last_kept_entry = last_kept_by_segment.get(segment_key, -10**12)
        if int(candidate["wide_entry_frame_id"]) - last_kept_entry < dedupe_source_frames:
            continue
        if not candidate.get("shift_gate_passed"):
            if candidate["signed_shift_metres"] >= state.params.number("minimum_shift_metres") * 0.70:
                near_misses.append(
                    {
                        **base_result_fields(state, candidate, query_hash, analysis_rate_hz),
                        "near_miss_reason": "below_shift_or_persistence_threshold",
                        "persistent_shift": candidate.get("persistent_shift", False),
                        "enough_defenders": candidate["enough_defenders"],
                    }
                )
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
            "replay_start_frame_id": max(
                int(candidate["segment_frame_ids"][0]),
                int(candidate["baseline_start_frame_id"]) - FRAME_RATE_HZ * 2,
            ),
            "replay_end_frame_id": min(
                int(state.frame_ids[-1]),
                outcome_frame_id + FRAME_RATE_HZ * 2,
            ),
        }
        if result["accepted"]:
            accepted.append(result)
            last_kept_by_segment[segment_key] = int(candidate["wide_entry_frame_id"])
        else:
            near_misses.append({**result, "near_miss_reason": "excluded_outcome"})
    state.accepted = accepted
    state.near_misses = near_misses
    state.signals[node.node_id] = {"classification": accepted + near_misses}


def predicate_gte(state: PeriodState, node: BoundPredicateNode) -> None:
    source = state.signals[node.input.source_node_id][node.input.output_name]
    threshold = float(node.compare.value) if isinstance(node.compare, TypedValue) else None
    if threshold is None:
        raise RuntimeError(f"{node.node_id} requires a compare value")
    if isinstance(source, np.ndarray):
        state.signals[node.node_id] = {"predicate": source >= threshold}
        return
    if isinstance(source, list):
        for candidate in source:
            candidate[f"{node.node_id}_passed"] = float(candidate["signed_shift_metres"]) >= threshold
        state.signals[node.node_id] = {"predicate": source}
        return
    raise RuntimeError(f"Unsupported gte source for {node.node_id}")


def predicate_gt(state: PeriodState, node: BoundPredicateNode) -> None:
    source = state.signals[node.input.source_node_id][node.input.output_name]
    threshold = float(node.compare.value) if isinstance(node.compare, TypedValue) else None
    if threshold is None:
        raise RuntimeError(f"{node.node_id} requires a compare value")
    if isinstance(source, np.ndarray):
        state.signals[node.node_id] = {"predicate": source > threshold}
        return
    if isinstance(source, list):
        for candidate in source:
            candidate[f"{node.node_id}_passed"] = float(candidate["signed_shift_metres"]) > threshold
        state.signals[node.node_id] = {"predicate": source}
        return
    raise RuntimeError(f"Unsupported gt source for {node.node_id}")


def predicate_lte(state: PeriodState, node: BoundPredicateNode) -> None:
    source = state.signals[node.input.source_node_id][node.input.output_name]
    threshold = float(node.compare.value) if isinstance(node.compare, TypedValue) else None
    if threshold is None or not isinstance(source, np.ndarray):
        raise RuntimeError(f"Unsupported lte source for {node.node_id}")
    state.signals[node.node_id] = {"predicate": source <= threshold}


def predicate_eq(state: PeriodState, node: BoundPredicateNode) -> None:
    source = state.signals[node.input.source_node_id][node.input.output_name]
    if isinstance(source, np.ndarray):
        state.signals[node.node_id] = {"predicate": source == node.compare.value}
        return
    raise RuntimeError(f"Unsupported eq source for {node.node_id}")


def predicate_neq(state: PeriodState, node: BoundPredicateNode) -> None:
    source = state.signals[node.input.source_node_id][node.input.output_name]
    if isinstance(source, list):
        state.signals[node.node_id] = {
            "predicate": [
                item for item in source if item.get("classification") != node.compare.value
            ]
        }
        return
    if isinstance(source, np.ndarray):
        state.signals[node.node_id] = {"predicate": source != node.compare.value}
        return
    raise RuntimeError(f"Unsupported neq source for {node.node_id}")


def predicate_persists_for(state: PeriodState, node: BoundPredicateNode) -> None:
    source = state.signals[node.input.source_node_id][node.input.output_name]
    duration_seconds = float(node.duration.value) if isinstance(node.duration, TypedValue) else None
    if duration_seconds is None:
        raise RuntimeError(f"{node.node_id} requires duration")
    minimum_frames = int(round(duration_seconds * state.params.integer("analysis_rate_hz")))
    if isinstance(source, np.ndarray):
        if node.input.source_node_id == "wide_entry_threshold":
            candidates = wide_entry_candidates(state, source, minimum_frames)
            state.signals[node.node_id] = {"episodes": candidates, "candidates": candidates}
            return
        episodes = segment_true(source, minimum_frames)
        state.signals[node.node_id] = {"episodes": episodes}
        return
    if isinstance(source, list):
        threshold = state.params.number("minimum_shift_metres")
        for candidate in source:
            persistent = has_persistent_shift(
                candidate["signed_shift_series"],
                threshold,
                minimum_frames,
            )
            candidate["persistent_shift"] = persistent
            candidate["shift_gate_passed"] = bool(
                candidate.get("shift_threshold_passed")
                and persistent
                and candidate["enough_defenders"]
            )
        state.candidates = source
        state.signals[node.node_id] = {"episodes": source}
        return
    raise RuntimeError(f"Unsupported persists_for source for {node.node_id}")


def predicate_noop(state: PeriodState, node: BoundPredicateNode) -> None:
    state.signals.setdefault(node.node_id, {})


def wide_entry_candidates(
    state: PeriodState,
    wide_mask: np.ndarray,
    dwell_frames: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    possession_segments = state.signals.get("possession", {}).get("episodes", [])
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
                    "wide_entry_y_m": round(float(seg_ball_y[i]), 3),
                    "ball_side": "right" if side_sign > 0 else "left",
                }
            )
    return candidates


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


def execution_result_rows(execution: QueryExecution) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in execution.results:
        row = {"result_id": result.result_id, **result.evidence}
        rows.append(row)
    return rows


def select_proof_results(candidates: list[dict[str, Any]], params: RuntimeParameters) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    per_match: dict[str, int] = {}
    limit = params.integer("accepted_result_limit")
    per_match_limit = params.integer("accepted_per_match_limit")

    def try_add(candidate: dict[str, Any]) -> None:
        if len(selected) >= limit:
            return
        match_id = candidate["match_id"]
        if per_match.get(match_id, 0) >= per_match_limit:
            return
        if any(item["result_id"] == candidate["result_id"] for item in selected):
            return
        selected.append({**candidate, "proof_selected": True})
        per_match[match_id] = per_match.get(match_id, 0) + 1

    switched = [item for item in candidates if item["classification"] == "SWITCHED"]
    non_switched = [
        item
        for item in candidates
        if item["classification"] in {"RETAINED_NO_SWITCH", "LOST_BEFORE_SWITCH"}
    ]
    for bucket in (switched[:2], non_switched[:2], candidates):
        for candidate in bucket:
            try_add(candidate)
            if len(selected) >= limit:
                break
    selected.sort(key=lambda item: (item["match_id"], item["period"], item["wide_entry_frame_id"]))
    return selected


def runtime_trace_rows(state: PeriodState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in state.accepted:
        rows.append(
            {
                "result_id": result["result_id"],
                "match_id": result["match_id"],
                "period": result["period"],
                "wide_entry_frame_id": result["wide_entry_frame_id"],
                "anchor_frame_id": result["anchor_frame_id"],
                "predicates": [
                    {"id": "wide_entry_persists", "status": "PASS"},
                    {
                        "id": "shift_persists",
                        "status": "PASS",
                        "value": result["signed_shift_metres"],
                        "threshold": state.params.number("minimum_shift_metres"),
                        "unit": "metre",
                    },
                    {
                        "id": "not_stoppage",
                        "status": "PASS",
                        "value": result["classification"],
                    },
                ],
            }
        )
    return rows


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_class = Counter(str(item["classification"]) for item in results)
    by_match = Counter(str(item["match_id"]) for item in results)
    return {
        "count": len(results),
        "by_classification": dict(sorted(by_class.items())),
        "by_match": dict(sorted(by_match.items())),
    }


def execute_default_plan(
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    raw_root: Path = DEFAULT_RAW_ROOT,
    plan_path: Path = DEFAULT_PLAN_PATH,
) -> tuple[BoundQueryPlan, QueryExecution]:
    bound = bind_document_from_path(plan_path)
    execution = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root).execute(bound)
    return bound, execution


def parquet_rows(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    return pq.ParquetFile(path).read(columns=columns).to_pandas()


def stream_ball_state(raw_tracking_xml: Path, period: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with raw_tracking_xml.open("rb") as handle:
        for _, frame_set in etree.iterparse(handle, events=("end",), tag="FrameSet"):
            if frame_set.get("TeamId") == BALL_TEAM_ID and frame_set.get("GameSection") == period:
                for frame in frame_set.iterfind("Frame"):
                    possession_code = int(frame.get("BallPossession"))
                    rows.append(
                        {
                            "frame_id": int(frame.get("N")),
                            "timestamp_utc": str(frame.get("T")),
                            "possession_team_role": "home" if possession_code == 1 else "away",
                            "ball_alive": int(frame.get("BallStatus")) == 1,
                        }
                    )
                frame_set.clear()
                break
            frame_set.clear()
    if not rows:
        raise RuntimeError(f"No ball tracking state found for {raw_tracking_xml} {period}")
    return pd.DataFrame(rows)


def outfield_player_ids(canonical_root: Path, match_id: str, team_role: str) -> set[str]:
    players = parquet_rows(canonical_root / "players.parquet")
    selected = players[
        (players.match_id == match_id) & (players.team_role == team_role) & (~players.is_goalkeeper)
    ]
    return set(selected.player_id.astype(str))


def team_id(canonical_root: Path, match_id: str, team_role: str) -> str:
    teams = parquet_rows(canonical_root / "teams.parquet")
    selected = teams[(teams.match_id == match_id) & (teams.team_role == team_role)]
    if selected.empty:
        raise RuntimeError(f"Missing team {match_id} {team_role}")
    return str(selected.iloc[0].team_id)


def segment_true(mask: np.ndarray, minimum_frames: int) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for idx, ok in enumerate(mask):
        if ok and start is None:
            start = idx
        if (not ok or idx == len(mask) - 1) and start is not None:
            end = idx - 1 if not ok else idx
            if end - start + 1 >= minimum_frames:
                segments.append((start, end))
            start = None
    return segments


def has_persistent_shift(values: pd.Series, threshold: float, persistence_frames: int) -> bool:
    if len(values) < persistence_frames:
        return False
    return bool((values >= threshold).rolling(persistence_frames).sum().max() >= persistence_frames)


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


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
