"""M1.1 deterministic query runtime.

Gate B executes the approved M1 primitive chain from a bound plan. The executor
is deliberately keyed by primitive/operator catalog entries, not recipe IDs.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
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
    BoundPlanNode,
    EvaluationTarget,
    ExecutionMode,
    ExecutionStatus,
    NodeKind,
    PayloadType,
    PredicateTrace,
    QueryExecution,
    QueryResult,
    TypedValue,
    Unit,
    UnknownEvidencePolicy,
    stable_hash,
)
from tqe.runtime.values import FrameSignal, RuntimeValue, runtime_value_from_raw
from tqe.runtime.relations import (
    CorridorConfig,
    destination_region_bounds,
    evaluate_geometric_progressive_corridors,
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
    canonical_root: Path
    raw_tracking: Path
    positions: pd.DataFrame
    frame_ids: np.ndarray
    ball_y: np.ndarray
    possession_role: np.ndarray
    ball_alive: np.ndarray
    defender_count: pd.Series
    defender_centroid_y: pd.Series
    signals: dict[str, Any] = field(default_factory=dict)
    runtime_values: dict[str, dict[str, RuntimeValue]] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    accepted: list[dict[str, Any]] = field(default_factory=list)
    near_misses: list[dict[str, Any]] = field(default_factory=list)
    predicate_traces: list[PredicateTrace] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeAnchor:
    anchor_id: str
    match_id: str
    period: str
    anchor_frame_id: int
    source_node_id: str
    output_name: str
    start_frame_id: int | None
    end_frame_id: int | None
    attributes: dict[str, Any]


PrimitiveImplementation = Callable[[PeriodState, BoundCatalogNode], None]
RelationImplementation = Callable[[PeriodState, BoundCatalogNode], None]
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
            "relation_destination_entry_classification": primitive_relation_destination_entry_classification,
            "wide_channel_dwell": primitive_noop,
            "shift_persistence": primitive_noop,
            "robust_team_width": primitive_noop,
            "analysis_rate": primitive_noop,
        }
        self.relations: dict[str, RelationImplementation] = {
            "geometric_progressive_corridor": relation_geometric_progressive_corridor,
        }
        self.predicates: dict[str, PredicateImplementation] = {
            "gt": predicate_gt,
            "gte": predicate_gte,
            "lte": predicate_lte,
            "eq": predicate_eq,
            "neq": predicate_neq,
            "persists_for": predicate_persists_for,
            "exists": predicate_exists,
            "count_at_least": predicate_count_at_least,
        }

    def execute(self, bound_plan: BoundQueryPlan) -> QueryExecution:
        if bound_plan.execution_mode == ExecutionMode.BIND_ONLY:
            return QueryExecution(
                execution_id=hashlib.sha256(
                    f"bind_only:{bound_plan.bound_plan_hash}".encode("utf-8")
                ).hexdigest()[:16],
                status=ExecutionStatus.NOT_STARTED,
                plan_hash=bound_plan.plan_hash,
                bound_plan_hash=bound_plan.bound_plan_hash,
                provenance={
                    "generated_at": utc_now_iso(),
                    "plan_id": bound_plan.plan_id,
                    "plan_status": bound_plan.plan_status.value,
                    "execution_mode": bound_plan.execution_mode.value,
                    "runtime_result_count": 0,
                    "runtime_value_count": 0,
                    "skipped_reason": "bind_only",
                },
            )
        if bound_plan.execution_mode == ExecutionMode.DRY_RUN:
            return QueryExecution(
                execution_id=hashlib.sha256(
                    f"dry_run:{bound_plan.bound_plan_hash}".encode("utf-8")
                ).hexdigest()[:16],
                status=ExecutionStatus.PASS,
                plan_hash=bound_plan.plan_hash,
                bound_plan_hash=bound_plan.bound_plan_hash,
                provenance={
                    "generated_at": utc_now_iso(),
                    "plan_id": bound_plan.plan_id,
                    "plan_status": bound_plan.plan_status.value,
                    "execution_mode": bound_plan.execution_mode.value,
                    "runtime_result_count": 0,
                    "runtime_value_count": 0,
                    "skipped_reason": "dry_run",
                },
            )

        params = runtime_parameters(bound_plan)
        results: list[dict[str, Any]] = []
        trace_records: list[PredicateTrace] = []
        runtime_value_count = 0

        for match_id in bound_plan.match_ids:
            match_results, match_traces, match_runtime_value_count = self._execute_match(
                bound_plan=bound_plan,
                match_id=match_id,
                params=params,
            )
            results.extend(match_results)
            trace_records.extend(match_traces)
            runtime_value_count += match_runtime_value_count

        results, trace_records, unknown_policy_status = apply_result_semantics(
            results=results,
            trace_records=trace_records,
            bound_plan=bound_plan,
        )
        if len(results) > bound_plan.max_results:
            kept_ids = {str(result["result_id"]) for result in results[: bound_plan.max_results]}
            results = results[: bound_plan.max_results]
            trace_records = [
                trace
                for trace in trace_records
                if str(trace.source_evidence.get("result_id")) in kept_ids
            ]

        query_results = [
            QueryResult(
                result_id=result["result_id"],
                classification=result["classification"],
                match_id=result["match_id"],
                period=result["period"],
                anchor_frame_id=result["anchor_frame_id"],
                evidence={
                    **{
                        key: value
                        for key, value in result.items()
                        if key != "result_id" and not key.startswith("_")
                    },
                    "requested_evidence": project_requested_evidence(result, bound_plan),
                    "plan_status": bound_plan.plan_status.value,
                },
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
        trace_payload = [
            trace.model_dump(mode="json", exclude_none=True) for trace in trace_records
        ]
        return QueryExecution(
            execution_id=execution_id,
            status=unknown_policy_status,
            plan_hash=bound_plan.plan_hash,
            bound_plan_hash=bound_plan.bound_plan_hash,
            results=query_results,
            predicate_traces=trace_records,
            provenance={
                "generated_at": utc_now_iso(),
                "canonical_root": str(self.canonical_root),
                "raw_root": str(self.raw_root),
                "plan_id": bound_plan.plan_id,
                "plan_status": bound_plan.plan_status.value,
                "execution_mode": bound_plan.execution_mode.value,
                "max_results": bound_plan.max_results,
                "runtime_result_count": len(query_results),
                "runtime_value_count": runtime_value_count,
                "unknown_policy": bound_plan.unknown_evidence_policy.value,
                "unknown_trace_count": sum(1 for trace in trace_records if trace.status == "UNKNOWN"),
                "runtime_trace_hash": stable_hash(trace_payload),
            },
        )

    def _execute_match(
        self,
        *,
        bound_plan: BoundQueryPlan,
        match_id: str,
        params: RuntimeParameters,
    ) -> tuple[list[dict[str, Any]], list[PredicateTrace], int]:
        accepted: list[dict[str, Any]] = []
        traces: list[PredicateTrace] = []
        runtime_value_count = 0
        for period in bound_plan.periods:
            state = self._execute_period(
                bound_plan=bound_plan,
                match_id=match_id,
                period=period,
                params=params,
            )
            accepted.extend(state.accepted)
            traces.extend(accepted_predicate_traces(state))
            runtime_value_count += sum(len(outputs) for outputs in state.runtime_values.values())
        accepted.sort(
            key=lambda item: (
                -float(item["block_shift_score"]),
                item["match_id"],
                item["period"],
                item["wide_entry_frame_id"],
            )
        )
        return accepted, traces, runtime_value_count

    def evaluate_target(
        self,
        bound_plan: BoundQueryPlan,
        target: EvaluationTarget,
    ) -> dict[str, Any]:
        if target.match_id not in bound_plan.match_ids:
            raise RuntimeError(f"target match {target.match_id} is outside the bound invocation")
        if target.period not in bound_plan.periods:
            raise RuntimeError(f"target period {target.period} is outside the bound invocation")

        params = runtime_parameters(bound_plan)
        state = self._execute_period(
            bound_plan=bound_plan,
            match_id=target.match_id,
            period=target.period,
            params=params,
        )
        target_frame_id = int(round(target.approximate_time_ms / 1000.0 * FRAME_RATE_HZ))
        radius_frames = int(round(target.search_radius_ms / 1000.0 * FRAME_RATE_HZ))
        anchors = runtime_anchors(state)
        compatible = [
            anchor
            for anchor in anchors
            if abs(anchor.anchor_frame_id - target_frame_id) <= radius_frames
        ]
        if not compatible:
            return {
                "target": target.model_dump(mode="json"),
                "status": "NO_COMPATIBLE_ANCHOR",
                "target_frame_id": target_frame_id,
                "search_radius_frames": radius_frames,
                "candidate_count": 0,
                "closest_candidate": None,
                "predicate_traces": [],
                "failed_predicates": [],
            }

        closest = min(
            compatible,
            key=lambda anchor: abs(anchor.anchor_frame_id - target_frame_id),
        )
        anchor_record = closest.attributes
        result = anchor_record.get("_runtime_result") or base_result_fields(
            state,
            anchor_record,
            state.params.text("result_id_seed_hash"),
            state.params.integer("analysis_rate_hz"),
        )
        traces = predicate_traces_for_anchor(state, closest, result)
        traces.extend(
            missing_target_predicate_traces(
                bound_plan=bound_plan,
                state=state,
                anchor=closest,
                result=result,
                existing_predicate_ids={trace.predicate_id for trace in traces},
            )
        )
        trace_payload = [trace.model_dump(mode="json", exclude_none=True) for trace in traces]
        failed = [
            trace
            for trace in trace_payload
            if trace["status"] in {"FAIL", "UNKNOWN"}
        ]
        accepted = bool(result.get("accepted"))
        return {
            "target": target.model_dump(mode="json"),
            "status": "MATCH" if accepted else "NON_MATCH",
            "target_frame_id": target_frame_id,
            "search_radius_frames": radius_frames,
            "candidate_count": len(compatible),
            "closest_candidate": {
                "candidate_key": closest.anchor_id,
                "anchor_id": closest.anchor_id,
                "wide_entry_frame_id": int(anchor_record["wide_entry_frame_id"]),
                "anchor_frame_id": closest.anchor_frame_id,
                "frame_distance": abs(closest.anchor_frame_id - target_frame_id),
                "accepted": accepted,
                "rejection_reason": result.get("near_miss_reason"),
                "classification": result.get("classification"),
            },
            "predicate_traces": trace_payload,
            "failed_predicates": failed,
        }

    def _execute_period(
        self,
        *,
        bound_plan: BoundQueryPlan,
        match_id: str,
        period: str,
        params: RuntimeParameters,
    ) -> PeriodState:
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
                if node.kind == NodeKind.RELATION:
                    implementation = self.relations.get(node.catalog_ref)
                    if implementation is None:
                        raise RuntimeError(f"No relation implementation for {node.catalog_ref}")
                else:
                    implementation = self.primitives.get(node.catalog_ref)
                if implementation is None:
                    raise RuntimeError(f"No primitive implementation for {node.catalog_ref}")
                implementation(state, node)
                record_runtime_values(state, node)
            elif isinstance(node, BoundPredicateNode):
                implementation = self.predicates.get(node.operator.name)
                if implementation is None:
                    raise RuntimeError(f"No predicate implementation for {node.operator.name}")
                implementation(state, node)
                record_runtime_values(state, node)
        return state

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
            canonical_root=self.canonical_root,
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


def apply_result_semantics(
    *,
    results: list[dict[str, Any]],
    trace_records: list[PredicateTrace],
    bound_plan: BoundQueryPlan,
) -> tuple[list[dict[str, Any]], list[PredicateTrace], ExecutionStatus]:
    allowed_labels = {rule.label for rule in bound_plan.classification_rules}
    filtered = [result for result in results if str(result.get("classification")) in allowed_labels]
    kept_ids = {str(result["result_id"]) for result in filtered}
    filtered_traces = [
        trace for trace in trace_records if str(trace.source_evidence.get("result_id")) in kept_ids
    ]

    traces_by_result: dict[str, list[PredicateTrace]] = defaultdict(list)
    for trace in filtered_traces:
        result_id = str(trace.source_evidence.get("result_id"))
        if result_id:
            traces_by_result[result_id].append(trace)
    for result in filtered:
        result_id = str(result["result_id"])
        result["matched_classification_rules"] = matching_classification_rules(
            result=result,
            traces=traces_by_result.get(result_id, []),
            bound_plan=bound_plan,
        )

    if bound_plan.unknown_evidence_policy == UnknownEvidencePolicy.INVALIDATE_EXECUTION:
        if any(trace.status == "UNKNOWN" for trace in filtered_traces):
            return filtered, filtered_traces, ExecutionStatus.INCOMPLETE
    if bound_plan.unknown_evidence_policy == UnknownEvidencePolicy.EXCLUDE_CANDIDATE:
        unknown_ids = {
            str(trace.source_evidence.get("result_id"))
            for trace in filtered_traces
            if trace.status == "UNKNOWN"
        }
        if unknown_ids:
            filtered = [result for result in filtered if str(result["result_id"]) not in unknown_ids]
            kept_ids = {str(result["result_id"]) for result in filtered}
            filtered_traces = [
                trace for trace in filtered_traces if str(trace.source_evidence.get("result_id")) in kept_ids
            ]
    return filtered, filtered_traces, ExecutionStatus.PASS


def matching_classification_rules(
    *,
    result: dict[str, Any],
    traces: list[PredicateTrace],
    bound_plan: BoundQueryPlan,
) -> list[str]:
    status_by_predicate = {trace.predicate_id: trace.status for trace in traces}
    matches: list[str] = []
    for rule in bound_plan.classification_rules:
        if rule.label != result.get("classification"):
            continue
        if all(status_by_predicate.get(predicate_id) == "PASS" for predicate_id in rule.predicate_ids):
            matches.append(rule.label)
    return matches


def project_requested_evidence(
    result: dict[str, Any],
    bound_plan: BoundQueryPlan,
) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for request in bound_plan.requested_evidence:
        key = f"{request.source.source_node_id}.{request.field}"
        projected[key] = result.get(request.field)
    return projected


def catalog_input_value(
    state: PeriodState,
    node: BoundCatalogNode,
    input_name: str,
) -> RuntimeValue:
    reference = node.inputs.get(input_name)
    if reference is None:
        raise RuntimeError(f"{node.node_id} requires {input_name} input")
    try:
        return state.runtime_values[reference.source_node_id][reference.output_name]
    except KeyError as error:
        raise RuntimeError(
            f"{node.node_id} cannot resolve runtime input "
            f"{input_name}={reference.source_node_id}.{reference.output_name}"
        ) from error


def runtime_records(value: RuntimeValue) -> list[dict[str, Any]]:
    records = value.provenance.get("records")
    if isinstance(records, list) and all(isinstance(item, dict) for item in records):
        return records
    if isinstance(value.value, list) and all(isinstance(item, dict) for item in value.value):
        return value.value
    return []


def runtime_frame_values(value: RuntimeValue) -> list[Any]:
    return value.frame_values if isinstance(value.value, FrameSignal) else value.value


def source_runtime_value(state: PeriodState, node: BoundPredicateNode) -> RuntimeValue:
    try:
        return state.runtime_values[node.input.source_node_id][node.input.output_name]
    except KeyError as error:
        raise RuntimeError(
            f"{node.node_id} cannot resolve runtime value "
            f"{node.input.source_node_id}.{node.input.output_name}"
        ) from error


def numeric_source_values(state: PeriodState, node: BoundPredicateNode) -> list[float | None]:
    runtime_value = source_runtime_value(state, node)
    value = runtime_frame_values(runtime_value)
    if not isinstance(value, list):
        raise RuntimeError(f"{node.node_id} expected list-backed numeric runtime value")
    values: list[float | None] = []
    for item in value:
        if item is None or is_nan_number(item):
            values.append(None)
        elif isinstance(item, bool) or not isinstance(item, int | float):
            raise RuntimeError(f"{node.node_id} expected numeric source values")
        else:
            values.append(float(item))
    return values


def record_candidate_predicate(
    *,
    candidate: dict[str, Any],
    node: BoundPredicateNode,
    status: str,
    value: TypedValue | None,
    threshold: TypedValue | None,
    unit: Unit | None = None,
    frame_id: int | None = None,
    window: dict[str, Any] | None = None,
    source_evidence: dict[str, Any] | None = None,
) -> None:
    candidate.setdefault("_predicate_status", {})[node.node_id] = {
        "status": status,
        "value": value.model_dump(mode="json") if value is not None else None,
        "threshold": threshold.model_dump(mode="json") if threshold is not None else None,
        "unit": (unit or node.output.unit).value,
        "frame_id": frame_id,
        "window": window,
        "source_evidence": source_evidence or {},
    }


def comparison_predicate_facts(
    *,
    state: PeriodState,
    node: BoundPredicateNode,
    values: list[float | None],
    statuses: list[bool | None],
    threshold: float,
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for index, (value, status) in enumerate(zip(values, statuses, strict=True)):
        facts.append(
            {
                "status": predicate_status_label(status),
                "value": typed_number(float(value), node.input_type.unit).model_dump(mode="json")
                if value is not None
                else None,
                "threshold": typed_number(threshold, node.input_type.unit).model_dump(mode="json"),
                "unit": node.input_type.unit.value,
                "frame_id": int(state.frame_ids[index]) if index < len(state.frame_ids) else None,
                "window": None,
                "source_evidence": {
                    "source_node_id": node.input.source_node_id,
                    "source_output_name": node.input.output_name,
                },
            }
        )
    return facts


def predicate_status_label(status: bool | None) -> str:
    if status is None:
        return "UNKNOWN"
    return "PASS" if status else "FAIL"


def record_persistence_evidence(
    *,
    record: dict[str, Any],
    source_predicate_id: str,
    minimum_frames: int,
    analysis_rate_hz: int,
) -> dict[str, Any]:
    series = record.get("persistence_series")
    threshold = record_predicate_threshold(record, source_predicate_id)
    if not isinstance(series, pd.Series) or threshold is None:
        return {"persistent": False, "duration_seconds": None, "start_frame_id": None, "end_frame_id": None}
    return shift_persistence_evidence(series, threshold, minimum_frames, analysis_rate_hz)


def record_predicate_threshold(record: dict[str, Any], predicate_id: str) -> float | None:
    status = (record.get("_predicate_status") or {}).get(predicate_id)
    if not isinstance(status, dict):
        return None
    threshold = status.get("threshold")
    if not isinstance(threshold, dict):
        return None
    value = threshold.get("value")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def record_quality_passed(record: dict[str, Any]) -> bool:
    if "quality_status" in record:
        return record["quality_status"] == "pass"
    if "quality_passed" in record:
        return bool(record["quality_passed"])
    return True


def record_runtime_values(state: PeriodState, node: BoundPlanNode) -> None:
    raw_outputs = state.signals.get(node.node_id)
    if raw_outputs is None:
        raise RuntimeError(f"{node.node_id} did not emit any outputs")
    if isinstance(node, BoundCatalogNode):
        outputs = node.outputs
    else:
        outputs = [node.output]
    values: dict[str, RuntimeValue] = {}
    for output in outputs:
        raw_value = raw_outputs.get(output.name)
        if raw_value is None and output.temporal_type.name.endswith("EPISODE_SET"):
            raw_value = raw_outputs.get("episodes")
        if raw_value is None:
            raise RuntimeError(f"{node.node_id} did not emit required output {output.name}")
        values[output.name] = runtime_value_from_raw(
            node_id=node.node_id,
            output=output,
            raw_value=raw_value,
            frame_ids=[int(frame_id) for frame_id in state.frame_ids],
            records=raw_outputs.get(f"{output.name}_records"),
        )
    state.runtime_values[node.node_id] = values


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
                "baseline_start_frame_id": baseline_start_frame,
                "baseline_end_frame_id": baseline_end_frame,
                "shift_search_start_frame_id": int(search_frame_ids[0]),
                "shift_search_end_frame_id": int(search_frame_ids[-1]),
                "baseline_defensive_centroid_y_m": round(baseline_centroid_y, 3),
                "anchor_frame_id": anchor_frame_id,
                "signed_shift_metres": round(max_shift, 3),
                "block_shift_score": round(max_shift, 6),
                "quality_status": "pass" if enough_defenders else "fail",
                "enough_defenders": enough_defenders,
                "persistence_series": signed_shift,
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
    }


def primitive_outcome_classification(state: PeriodState, node: BoundCatalogNode) -> None:
    accepted: list[dict[str, Any]] = []
    near_misses: list[dict[str, Any]] = []
    accepted_shift_records = catalog_input_value(state, node, "accepted_shift_episodes").value
    signed_shift_value = catalog_input_value(state, node, "signed_shift")
    if not isinstance(accepted_shift_records, list):
        raise RuntimeError(f"{node.node_id} requires accepted shift episode records")
    if not isinstance(signed_shift_value.value, FrameSignal):
        raise RuntimeError(f"{node.node_id} requires signed shift frame signal")
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


def relation_anchor_source(node: BoundCatalogNode) -> str:
    anchor_reference = node.inputs.get("anchors")
    if anchor_reference is None:
        return "missing"
    return f"{anchor_reference.source_node_id}.{anchor_reference.output_name}"


def relation_anchor_results(state: PeriodState, node: BoundCatalogNode) -> list[dict[str, Any]]:
    raw_anchors = runtime_records(catalog_input_value(state, node, "anchors"))
    anchor_results = [
        anchor
        for anchor in raw_anchors
        if isinstance(anchor, dict) and relation_anchor_has_required_fields(anchor)
    ]
    anchor_results.sort(
        key=lambda item: (
            str(item["match_id"]),
            str(item["period"]),
            int(item["anchor_frame_id"]),
            str(item["result_id"]),
        )
    )
    return anchor_results


def relation_anchor_has_required_fields(anchor: dict[str, Any]) -> bool:
    required_fields = {
        "result_id",
        "match_id",
        "period",
        "perspective_team_role",
        "defending_team_role",
        "anchor_frame_id",
        "outcome_frame_id",
    }
    return required_fields.issubset(anchor)


def relation_geometric_progressive_corridor(state: PeriodState, node: BoundCatalogNode) -> None:
    source_results = relation_anchor_results(state, node)
    if not source_results:
        state.signals[node.node_id] = {
            "episodes": [],
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
        max_window_seconds=node_parameter_number(node, "max_window_seconds", 4.0),
        minimum_progression_m=node_parameter_number(node, "minimum_progression_m", 8.0),
        minimum_segment_length_m=node_parameter_number(node, "minimum_segment_length_m", 8.0),
        maximum_segment_length_m=node_parameter_number(node, "maximum_segment_length_m", 45.0),
        minimum_clearance_m=node_parameter_number(node, "minimum_clearance_m", 5.0),
        open_after_frames=node_parameter_integer(node, "open_after_frames", 2),
        close_after_frames=node_parameter_integer(node, "close_after_frames", 2),
    )
    relation_report = evaluate_geometric_progressive_corridors(
        results=source_results,
        canonical_root=state.canonical_root,
        config=config,
    )
    episodes = relation_report["episodes"]
    side_filter = node_parameter_text(node, "side_filter", "any")
    minimum_duration_seconds = node_parameter_number(node, "minimum_duration_seconds", 0.0)
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
    state.signals[node.node_id] = {
        "episodes": filtered,
        "source_results": source_results,
        "anchor_source": relation_anchor_source(node),
        "summary": {
            **relation_report["summary"],
            "filtered_episode_count": len(filtered),
            "filtered_result_count_with_episode": len({item["result_id"] for item in filtered}),
            "anchor_source": relation_anchor_source(node),
            "side_filter": side_filter,
            "minimum_duration_seconds": minimum_duration_seconds,
        },
        "config": relation_report["config"],
        "artifact_hash": relation_report["artifact_hash"],
    }


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


def primitive_relation_destination_entry_classification(
    state: PeriodState,
    node: BoundCatalogNode,
) -> None:
    relation_value = catalog_input_value(state, node, "relation_episodes")
    relation_episodes = relation_value.value
    if not isinstance(relation_episodes, list):
        raise RuntimeError(f"{node.node_id} requires relation episode records")
    episodes_by_result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in relation_episodes:
        episodes_by_result[str(episode["result_id"])].append(episode)

    horizon_seconds = node_parameter_number(node, "destination_entry_horizon_seconds", 6.0)
    seed = node_parameter_text(node, "result_id_seed", state.params.text("result_id_seed_hash"))
    episode_selection = node_parameter_text(node, "episode_selection", "first_by_duration_clearance")
    source_results = [
        episode["source_result"]
        for episode in relation_episodes
        if isinstance(episode.get("source_result"), dict)
    ]

    final_results: list[dict[str, Any]] = []
    final_traces: list[PredicateTrace] = []
    for source_result in source_results:
        source_result_id = str(source_result["result_id"])
        relation_candidates = episodes_by_result.get(source_result_id, [])
        if not relation_candidates:
            continue
        episode = select_relation_episode(relation_candidates, episode_selection)
        entry = first_ball_entry_into_destination_region(
            state=state,
            episode=episode,
            horizon_seconds=horizon_seconds,
        )
        destination_entered = entry is not None
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
        replay_end_frame_id = max(
            int(source_result["replay_end_frame_id"]),
            int(episode["close_frame_id"]) + FRAME_RATE_HZ * 2,
            int(entry["frame_id"]) + FRAME_RATE_HZ * 2 if entry else int(episode["close_frame_id"]),
        )
        final_result = {
            **source_result,
            "result_id": result_id,
            "classification": classification,
            "source_classification": source_result["classification"],
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
            "destination_entry_horizon_seconds": horizon_seconds,
            "source_open_point": episode["source_open_point"],
            "target_open_point": episode["target_open_point"],
            "source_close_point": episode["source_close_point"],
            "target_close_point": episode["target_close_point"],
            "accepted": True,
            "replay_end_frame_id": min(int(state.frame_ids[-1]), replay_end_frame_id),
        }
        final_results.append(final_result)
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
        key=lambda item: (
            -float(item["block_shift_score"]),
            item["match_id"],
            item["period"],
            int(item["wide_entry_frame_id"]),
            item["relation_id"],
        )
    )
    state.accepted = final_results
    state.predicate_traces = final_traces
    state.signals[node.node_id] = {
        "classification": FrameSignal(
            frame_ids=[
                int(item.get("destination_entry_frame_id") or item["relation_close_frame_id"])
                for item in final_results
            ],
            values=[str(item["classification"]) for item in final_results],
            unknown_mask=[False for _ in final_results],
            unit=node.outputs[0].unit,
            entity_scope=node.outputs[0].entity_scope,
        ),
        "classification_records": final_results,
    }


def predicate_gte(state: PeriodState, node: BoundPredicateNode) -> None:
    threshold = float(node.compare.value) if isinstance(node.compare, TypedValue) else None
    if threshold is None:
        raise RuntimeError(f"{node.node_id} requires a compare value")
    source_value = source_runtime_value(state, node)
    values = numeric_source_values(state, node)
    passed = [None if value is None else float(value) >= threshold for value in values]
    records = runtime_records(source_value)
    output: dict[str, Any] = {
        "predicate": FrameSignal(
            frame_ids=source_value.value.frame_ids
            if isinstance(source_value.value, FrameSignal)
            else list(range(len(passed))),
            values=passed,
            unknown_mask=[status is None for status in passed],
            unit=node.output.unit,
            entity_scope=node.output.entity_scope,
        )
    }
    if records and len(records) == len(passed):
        for record, status, value in zip(records, passed, values, strict=True):
            record_candidate_predicate(
                candidate=record,
                node=node,
                status=predicate_status_label(status),
                value=typed_number(float(value), node.input_type.unit) if value is not None else None,
                threshold=typed_number(threshold, node.input_type.unit),
                unit=node.input_type.unit,
                frame_id=int(record["anchor_frame_id"]) if "anchor_frame_id" in record else None,
                source_evidence={
                    "source_node_id": node.input.source_node_id,
                    "source_output_name": node.input.output_name,
                },
            )
        output["predicate_records"] = records
    else:
        output["predicate_facts"] = comparison_predicate_facts(
            state=state,
            node=node,
            values=values,
            statuses=passed,
            threshold=threshold,
        )
    state.signals[node.node_id] = output


def predicate_gt(state: PeriodState, node: BoundPredicateNode) -> None:
    threshold = float(node.compare.value) if isinstance(node.compare, TypedValue) else None
    if threshold is None:
        raise RuntimeError(f"{node.node_id} requires a compare value")
    values = numeric_source_values(state, node)
    passed = [None if value is None else float(value) > threshold for value in values]
    facts = comparison_predicate_facts(
        state=state,
        node=node,
        values=values,
        statuses=passed,
        threshold=threshold,
    )
    state.signals[node.node_id] = {
        "predicate": passed,
        "predicate_records": facts,
    }


def predicate_lte(state: PeriodState, node: BoundPredicateNode) -> None:
    threshold = float(node.compare.value) if isinstance(node.compare, TypedValue) else None
    if threshold is None:
        raise RuntimeError(f"{node.node_id} requires a compare value")
    values = numeric_source_values(state, node)
    passed = [None if value is None else float(value) <= threshold for value in values]
    facts = comparison_predicate_facts(
        state=state,
        node=node,
        values=values,
        statuses=passed,
        threshold=threshold,
    )
    state.signals[node.node_id] = {
        "predicate": passed,
        "predicate_records": facts,
    }


def predicate_eq(state: PeriodState, node: BoundPredicateNode) -> None:
    runtime_value = source_runtime_value(state, node)
    values = runtime_value.frame_values if isinstance(runtime_value.value, FrameSignal) else runtime_value.value
    if not isinstance(values, list):
        raise RuntimeError(f"{node.node_id} expected list-backed source values")
    compare = node.compare.value if isinstance(node.compare, TypedValue) else None
    state.signals[node.node_id] = {
        "predicate": [None if value is None else value == compare for value in values]
    }


def predicate_neq(state: PeriodState, node: BoundPredicateNode) -> None:
    runtime_value = source_runtime_value(state, node)
    values = runtime_frame_values(runtime_value)
    if not isinstance(values, list):
        raise RuntimeError(f"{node.node_id} expected list-backed source values")
    compare = node.compare.value if isinstance(node.compare, TypedValue) else None
    passed = [None if value is None else value != compare for value in values]
    output: dict[str, Any] = {"predicate": passed}
    items = runtime_records(runtime_value)
    if isinstance(items, list) and items and all(isinstance(item, dict) for item in items):
        for item, status, value in zip(items, passed, values, strict=False):
            if "_predicate_status" in item:
                record_candidate_predicate(
                    candidate=item,
                    node=node,
                    status=predicate_status_label(status),
                    value=typed_enum(str(value)) if value is not None else None,
                    threshold=typed_enum(str(compare)),
                    unit=Unit.NONE,
                    frame_id=int(item["outcome_frame_id"]) if item.get("outcome_frame_id") is not None else None,
                    source_evidence={
                        "source_node_id": node.input.source_node_id,
                        "source_output_name": node.input.output_name,
                        "reason": "outcome_not_evaluated" if value is None else None,
                    },
                )
        output["items"] = [item for item, status in zip(items, passed, strict=False) if status]
        output["predicate_records"] = output["items"]
    state.signals[node.node_id] = output


def predicate_persists_for(state: PeriodState, node: BoundPredicateNode) -> None:
    duration_seconds = float(node.duration.value) if isinstance(node.duration, TypedValue) else None
    if duration_seconds is None:
        raise RuntimeError(f"{node.node_id} requires duration")
    analysis_rate_hz = state.params.integer("analysis_rate_hz")
    minimum_frames = int(round(duration_seconds * analysis_rate_hz))
    runtime_value = source_runtime_value(state, node)
    values = runtime_frame_values(runtime_value)
    if not isinstance(values, list):
        raise RuntimeError(f"{node.node_id} expected list-backed source values")
    records = runtime_records(runtime_value)
    if (
        records
        and len(records) == len(values)
        and all(isinstance(record.get("persistence_series"), pd.Series) for record in records)
    ):
        accepted_records: list[dict[str, Any]] = []
        for record, source_status in zip(records, values, strict=True):
            persistence = record_persistence_evidence(
                record=record,
                source_predicate_id=node.input.source_node_id,
                minimum_frames=minimum_frames,
                analysis_rate_hz=state.params.integer("analysis_rate_hz"),
            )
            persistent = bool(persistence["persistent"])
            record["persistent_shift"] = persistent
            record["shift_persistence_seconds"] = persistence["duration_seconds"]
            record["shift_persistence_start_frame_id"] = persistence["start_frame_id"]
            record["shift_persistence_end_frame_id"] = persistence["end_frame_id"]
            record["predicate_gate_passed"] = bool(
                source_status is True
                and persistent
                and record_quality_passed(record)
            )
            record["shift_gate_passed"] = record["predicate_gate_passed"]
            record_candidate_predicate(
                candidate=record,
                node=node,
                status="PASS" if persistent else "FAIL",
                value=(
                    typed_number(float(persistence["duration_seconds"]), Unit.SECOND)
                    if persistence["duration_seconds"] is not None
                    else None
                ),
                threshold=typed_number(duration_seconds, Unit.SECOND),
                unit=Unit.SECOND,
                window={
                    "start_frame_id": persistence["start_frame_id"],
                    "end_frame_id": persistence["end_frame_id"],
                },
                source_evidence={
                    "source_node_id": node.input.source_node_id,
                    "source_output_name": node.input.output_name,
                },
            )
            if record["predicate_gate_passed"]:
                accepted_records.append(record)
        state.signals[node.node_id] = {
            "predicate": accepted_records,
            "episodes": accepted_records,
            "predicate_records": accepted_records,
        }
        return
    if all(value is None or isinstance(value, bool) for value in values):
        episodes = episode_records_from_mask(
            state,
            np.asarray([value is True for value in values], dtype=bool),
            minimum_frames,
        )
        source_facts = runtime_records(runtime_value)
        for episode in episodes:
            episode.setdefault("_predicate_status", {})
            start_index = int(episode["start_index"])
            if isinstance(source_facts, list) and start_index < len(source_facts):
                episode["_predicate_status"][node.input.source_node_id] = source_facts[start_index]
            duration = (int(episode["end_index"]) - start_index + 1) / analysis_rate_hz
            record_candidate_predicate(
                candidate=episode,
                node=node,
                status="PASS",
                value=typed_number(round(float(duration), 3), Unit.SECOND),
                threshold=typed_number(duration_seconds, Unit.SECOND),
                unit=Unit.SECOND,
                window={
                    "start_frame_id": int(episode["start_frame_id"]),
                    "end_frame_id": int(episode["end_frame_id"]),
                },
                source_evidence={
                    "source_node_id": node.input.source_node_id,
                    "source_output_name": node.input.output_name,
                },
            )
        state.signals[node.node_id] = {"predicate": episodes, "episodes": episodes}
        return
    raise RuntimeError(f"Unsupported persists_for source for {node.node_id}")


def predicate_noop(state: PeriodState, node: BoundPredicateNode) -> None:
    state.signals.setdefault(node.node_id, {})


def predicate_exists(state: PeriodState, node: BoundPredicateNode) -> None:
    source = source_runtime_value(state, node).value
    if isinstance(source, list):
        state.signals[node.node_id] = {"predicate": bool(source), "episodes": source}
        return
    raise RuntimeError(f"Unsupported exists source for {node.node_id}")


def predicate_count_at_least(state: PeriodState, node: BoundPredicateNode) -> None:
    source = source_runtime_value(state, node).value
    threshold = int(round(float(node.compare.value))) if isinstance(node.compare, TypedValue) else None
    if threshold is None or not isinstance(source, list):
        raise RuntimeError(f"Unsupported count_at_least source for {node.node_id}")
    state.signals[node.node_id] = {
        "predicate": len(source) >= threshold,
        "count": len(source),
        "episodes": source,
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


def episode_records_from_mask(
    state: PeriodState,
    mask: np.ndarray,
    minimum_frames: int,
) -> list[dict[str, int]]:
    return [
        {
            "start_index": int(start),
            "end_index": int(end),
            "start_frame_id": int(state.frame_ids[start]),
            "end_frame_id": int(state.frame_ids[end]),
        }
        for start, end in segment_true(mask, minimum_frames)
    ]


def wide_entry_candidates_from_episodes(
    state: PeriodState,
    *,
    entry_episodes: list[Any],
    possession_episodes: list[Any],
) -> list[dict[str, Any]]:
    wide_mask = np.zeros(len(state.frame_ids), dtype=bool)
    structured_episodes: list[dict[str, Any]] = []
    for episode in entry_episodes:
        start_index = episode_start_index(episode)
        end_index = episode_end_index(episode)
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


def episode_start_index(episode: Any) -> int | None:
    if isinstance(episode, dict):
        return int(episode["start_index"]) if "start_index" in episode else None
    if isinstance(episode, tuple | list) and len(episode) >= 1:
        return int(episode[0])
    return None


def episode_end_index(episode: Any) -> int | None:
    if isinstance(episode, dict):
        return int(episode["end_index"]) if "end_index" in episode else None
    if isinstance(episode, tuple | list) and len(episode) >= 2:
        return int(episode[1])
    return None


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


def runtime_anchors(state: PeriodState) -> list[RuntimeAnchor]:
    anchors: list[RuntimeAnchor] = []
    seen: set[str] = set()
    for node_id, outputs in state.runtime_values.items():
        for output_name, runtime_value in outputs.items():
            for index, record in enumerate(runtime_records(runtime_value)):
                anchor = runtime_anchor_from_record(
                    state=state,
                    node_id=node_id,
                    output_name=output_name,
                    index=index,
                    record=record,
                )
                if anchor is None or anchor.anchor_id in seen:
                    continue
                seen.add(anchor.anchor_id)
                anchors.append(anchor)
    anchors.sort(
        key=lambda item: (
            item.match_id,
            item.period,
            item.anchor_frame_id,
            item.source_node_id,
            item.output_name,
            item.anchor_id,
        )
    )
    return anchors


def runtime_anchor_from_record(
    *,
    state: PeriodState,
    node_id: str,
    output_name: str,
    index: int,
    record: dict[str, Any],
) -> RuntimeAnchor | None:
    if not isinstance(record, dict) or "anchor_frame_id" not in record:
        return None
    try:
        anchor_frame_id = int(record["anchor_frame_id"])
    except (TypeError, ValueError):
        return None
    match_id = str(record.get("match_id") or state.match_id)
    period = str(record.get("period") or state.period)
    anchor_id = record.get("anchor_id")
    if not isinstance(anchor_id, str) or not anchor_id:
        anchor_id = stable_hash(
            {
                "match_id": match_id,
                "period": period,
                "anchor_frame_id": anchor_frame_id,
                "source_node_id": node_id,
                "output_name": output_name,
                "index": index,
                "wide_entry_frame_id": record.get("wide_entry_frame_id"),
            }
        )[:16]
    return RuntimeAnchor(
        anchor_id=anchor_id,
        match_id=match_id,
        period=period,
        anchor_frame_id=anchor_frame_id,
        source_node_id=node_id,
        output_name=output_name,
        start_frame_id=optional_int(record.get("start_frame_id") or record.get("possession_start_frame_id")),
        end_frame_id=optional_int(record.get("end_frame_id") or record.get("possession_end_frame_id")),
        attributes=record,
    )


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def accepted_predicate_traces(state: PeriodState) -> list[PredicateTrace]:
    if state.predicate_traces:
        return state.predicate_traces
    traces: list[PredicateTrace] = []
    for result in state.accepted:
        anchor = runtime_anchor_from_record(
            state=state,
            node_id="accepted_results",
            output_name="result",
            index=len(traces),
            record=result,
        )
        if anchor is not None:
            traces.extend(predicate_traces_for_anchor(state, anchor, result))
    return traces


def predicate_traces_from_status_records(
    *,
    state: PeriodState,
    anchor: RuntimeAnchor,
    result: dict[str, Any],
) -> list[PredicateTrace]:
    anchor_record = anchor.attributes
    records = anchor_record.get("_predicate_status") or result.get("_predicate_status") or {}
    if not isinstance(records, dict) or not records:
        return []
    result_id = str(result.get("result_id") or anchor.anchor_id)
    common = {
        "result_id": result_id,
        "candidate_key": anchor.anchor_id,
        "anchor_id": anchor.anchor_id,
        "match_id": anchor.match_id,
        "period": anchor.period,
        "wide_entry_frame_id": int(anchor_record["wide_entry_frame_id"]),
        "anchor_frame_id": anchor.anchor_frame_id,
    }
    traces: list[PredicateTrace] = []
    for predicate_id, record in records.items():
        if not isinstance(record, dict):
            continue
        source_evidence = {
            **common,
            **{
                key: value
                for key, value in dict(record.get("source_evidence") or {}).items()
                if value is not None
            },
        }
        traces.append(
            PredicateTrace(
                predicate_id=str(predicate_id),
                status=record["status"],
                value=TypedValue.model_validate(record["value"])
                if record.get("value") is not None
                else None,
                threshold=TypedValue.model_validate(record["threshold"])
                if record.get("threshold") is not None
                else None,
                unit=Unit(record.get("unit", Unit.NONE.value)),
                frame_id=record.get("frame_id"),
                window=record.get("window"),
                source_evidence=source_evidence,
            )
        )
    return traces


def predicate_traces_for_anchor(
    state: PeriodState,
    anchor: RuntimeAnchor,
    result: dict[str, Any],
) -> list[PredicateTrace]:
    return predicate_traces_from_status_records(
        state=state,
        anchor=anchor,
        result=result,
    )


def missing_target_predicate_traces(
    *,
    bound_plan: BoundQueryPlan,
    state: PeriodState,
    anchor: RuntimeAnchor,
    result: dict[str, Any],
    existing_predicate_ids: set[str],
) -> list[PredicateTrace]:
    traces: list[PredicateTrace] = []
    anchor_record = anchor.attributes
    for node in bound_plan.nodes:
        if not isinstance(node, BoundPredicateNode) or node.node_id in existing_predicate_ids:
            continue
        traces.append(
            PredicateTrace(
                predicate_id=node.node_id,
                status="UNKNOWN",
                value=None,
                threshold=node.compare if isinstance(node.compare, TypedValue) else None,
                unit=node.output.unit,
                frame_id=anchor.anchor_frame_id,
                source_evidence={
                    "reason": "source_output_unavailable_for_target_candidate",
                    "result_id": str(result.get("result_id") or anchor.anchor_id),
                    "candidate_key": anchor.anchor_id,
                    "anchor_id": anchor.anchor_id,
                    "match_id": anchor.match_id,
                    "period": anchor.period,
                    "wide_entry_frame_id": int(anchor_record["wide_entry_frame_id"]),
                    "anchor_frame_id": anchor.anchor_frame_id,
                    "source_node_id": node.input.source_node_id,
                    "source_output_name": node.input.output_name,
                },
            )
        )
    return traces


def numeric_trace_status(value: Any, threshold: float, operator: str) -> str:
    if value is None or is_nan_number(value):
        return "UNKNOWN"
    if operator == "gt":
        return "PASS" if float(value) > threshold else "FAIL"
    if operator == "gte":
        return "PASS" if float(value) >= threshold else "FAIL"
    raise RuntimeError(f"Unsupported trace operator {operator}")


def typed_number(value: float, unit: Unit) -> TypedValue:
    return TypedValue(payload_type=PayloadType.NUMBER, value=value, unit=unit)


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type=PayloadType.ENUM, value=value, unit=Unit.NONE)


def node_parameter_number(node: BoundCatalogNode, name: str, default: float) -> float:
    value = node.resolved_parameters.get(name)
    if value is None:
        return default
    if value.payload_type != PayloadType.NUMBER:
        raise RuntimeError(f"{node.node_id}.{name} must be numeric")
    return float(value.value)


def node_parameter_integer(node: BoundCatalogNode, name: str, default: int) -> int:
    return int(round(node_parameter_number(node, name, float(default))))


def node_parameter_text(node: BoundCatalogNode, name: str, default: str) -> str:
    value = node.resolved_parameters.get(name)
    if value is None:
        return default
    if value.payload_type not in {PayloadType.ENUM, PayloadType.RELATION_REF}:
        raise RuntimeError(f"{node.node_id}.{name} must be textual")
    return str(value.value)


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
    start_frame_id = int(episode["open_frame_id"])
    end_frame_id = min(
        int(state.frame_ids[-1]),
        start_frame_id + int(round(horizon_seconds * FRAME_RATE_HZ)),
    )
    bounds = episode.get("destination_region_bounds") or destination_region_bounds(
        str(episode["destination_side"]),
        str(episode["destination_lane"]),
    )
    min_y = float(bounds["min_y_m"])
    max_y = float(bounds["max_y_m"])
    ball = state.positions[
        (state.positions.entity_type == "ball")
        & (state.positions.frame_id >= start_frame_id)
        & (state.positions.frame_id <= end_frame_id)
    ].sort_values("frame_id")
    for row in ball.itertuples(index=False):
        y_m = float(row.y_m)
        if min_y <= y_m <= max_y:
            return {
                "frame_id": int(row.frame_id),
                "point": {"x_m": round(float(row.x_m), 3), "y_m": round(y_m, 3)},
                "region": episode["destination_region"],
                "region_type": episode.get("destination_region_type", "side_lane_band"),
                "region_bounds": bounds,
            }
    return None


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


def is_nan_number(value: Any) -> bool:
    return isinstance(value, int | float) and math.isnan(float(value))


def candidate_key(state: PeriodState, candidate: dict[str, Any]) -> str:
    return (
        f"{state.match_id}:{state.period}:"
        f"{int(candidate['wide_entry_frame_id'])}:{int(candidate['anchor_frame_id'])}"
    )


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


def execute_plan_from_path(
    plan_path: Path,
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    raw_root: Path = DEFAULT_RAW_ROOT,
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
    return bool(shift_persistence_evidence(values, threshold, persistence_frames)["persistent"])


def shift_persistence_evidence(
    values: pd.Series,
    threshold: float,
    persistence_frames: int,
    analysis_rate_hz: int = FRAME_RATE_HZ,
) -> dict[str, Any]:
    if len(values) == 0:
        return {
            "persistent": False,
            "duration_seconds": 0.0,
            "start_frame_id": None,
            "end_frame_id": None,
        }

    best_start: int | None = None
    best_end: int | None = None
    best_count = 0
    current_start: int | None = None
    current_count = 0
    current_end: int | None = None

    for frame_id, passes in (values >= threshold).items():
        if bool(passes):
            if current_start is None:
                current_start = int(frame_id)
                current_count = 0
            current_count += 1
            current_end = int(frame_id)
            if current_count > best_count:
                best_count = current_count
                best_start = current_start
                best_end = current_end
        else:
            current_start = None
            current_count = 0
            current_end = None

    return {
        "persistent": best_count >= persistence_frames,
        "duration_seconds": round(best_count / analysis_rate_hz, 3),
        "start_frame_id": best_start,
        "end_frame_id": best_end,
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


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
