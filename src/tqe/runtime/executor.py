"""M1.1 deterministic query runtime.

Gate B executes the approved M1 primitive chain from a bound plan. The executor
is deliberately keyed by primitive/operator catalog entries, not recipe IDs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
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
from tqe.runtime.binder import HOST_RUNTIME_PARAMETER_DEFAULTS, bind_document_from_path
from tqe.runtime.ir import (
    BoundCatalogNode,
    BoundPredicateNode,
    BoundQueryPlan,
    BoundPlanNode,
    ClassificationRule,
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
from tqe.runtime.values import FrameSignal, RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw
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
DEFAULT_CANONICAL_ROOT = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
DEFAULT_RAW_ROOT = Path(os.environ.get("TQE_RAW_ROOT", str(Path("data/raw/idsse") / SOURCE_VERSION)))
GENERIC_EXECUTION_PROFILE = "generic"
LEGACY_M1_PARITY_PROFILE = "legacy_m1_parity"


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
    semantic_key: str
    match_id: str
    period: str
    anchor_frame_id: int
    source_node_id: str
    output_name: str
    start_frame_id: int | None
    end_frame_id: int | None
    attributes: dict[str, Any]


@dataclass(frozen=True)
class NodeExecutionResult:
    node_id: str
    inputs: dict[str, RuntimeValue]
    parameters: dict[str, TypedValue]
    outputs: dict[str, Any]
    runtime_values: dict[str, RuntimeValue]
    warnings: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalPredicateResult:
    episodes: list[dict[str, Any]]
    unknown_intervals: list[dict[str, Any]]
    fail_intervals: list[dict[str, Any]]
    evaluated_frame_ids: list[int]

    def output_records(self) -> list[dict[str, Any]]:
        return [
            *[
                {**episode, "temporal_status": "PASS"}
                for episode in self.episodes
            ],
            *[
                {**interval, "temporal_status": "UNKNOWN"}
                for interval in self.unknown_intervals
            ],
            *[
                {**interval, "temporal_status": "FAIL"}
                for interval in self.fail_intervals
            ],
        ]


@dataclass(frozen=True)
class MatchContext:
    match_id: str
    period: str
    frame_ids: tuple[int, ...]
    params: RuntimeParameters


PrimitiveImplementation = Callable[[PeriodState, BoundCatalogNode], None]
RelationImplementation = Callable[[PeriodState, BoundCatalogNode], None]
PredicateImplementation = Callable[[PeriodState, BoundPredicateNode], None]


class TacticalQueryExecutor:
    def __init__(
        self,
        *,
        canonical_root: Path = DEFAULT_CANONICAL_ROOT,
        raw_root: Path = DEFAULT_RAW_ROOT,
        compatibility_profile: str = GENERIC_EXECUTION_PROFILE,
    ) -> None:
        self.canonical_root = canonical_root
        self.raw_root = raw_root
        if compatibility_profile not in {GENERIC_EXECUTION_PROFILE, LEGACY_M1_PARITY_PROFILE}:
            raise RuntimeError(f"Unsupported compatibility profile {compatibility_profile}")
        self.compatibility_profile = compatibility_profile
        self.primitives: dict[str, PrimitiveImplementation] = {
            "possession_segment": primitive_possession_segment,
            "ball_lateral_fraction": primitive_ball_lateral_fraction,
            "defensive_outfield_centroid": primitive_defensive_outfield_centroid,
            "signed_lateral_shift": primitive_signed_lateral_shift,
            "outcome_classification": primitive_outcome_classification,
            "relation_destination_entry": primitive_relation_destination_entry_classification,
            "relation_destination_entry_classification": primitive_relation_destination_entry_classification,
            "wide_channel_dwell": primitive_noop,
            "shift_persistence": primitive_noop,
            "robust_team_width": primitive_noop,
            "analysis_rate": primitive_noop,
        }
        self.relations: dict[str, RelationImplementation] = {
            "geometric_progressive_corridor": relation_geometric_progressive_corridor,
            "geometric_progressive_corridor_from_anchor_set": relation_geometric_progressive_corridor,
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
                    "compatibility_profile": self.compatibility_profile,
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
                    "compatibility_profile": self.compatibility_profile,
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
                compatibility_profile=self.compatibility_profile,
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
        evidence_failures = unresolved_requested_evidence(results, bound_plan)
        if evidence_failures:
            unknown_policy_status = ExecutionStatus.INCOMPLETE

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
                    "requested_evidence": result.get("requested_evidence")
                    if isinstance(result.get("requested_evidence"), dict)
                    else project_requested_evidence(result, bound_plan),
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
                "compatibility_profile": self.compatibility_profile,
                "max_results": bound_plan.max_results,
                "runtime_result_count": len(query_results),
                "runtime_value_count": runtime_value_count,
                "unknown_policy": bound_plan.unknown_evidence_policy.value,
                "unknown_trace_count": sum(1 for trace in trace_records if trace.status == "UNKNOWN"),
                "requested_evidence_failure_count": len(evidence_failures),
                "requested_evidence_failures": evidence_failures[:20],
                "runtime_trace_hash": stable_hash(trace_payload),
            },
        )

    def _execute_match(
        self,
        *,
        bound_plan: BoundQueryPlan,
        match_id: str,
        params: RuntimeParameters,
        compatibility_profile: str,
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
                compatibility_profile=compatibility_profile,
            )
            if compatibility_profile == LEGACY_M1_PARITY_PROFILE:
                accepted.extend(state.accepted)
                traces.extend(
                    accepted_predicate_traces(
                        state,
                        bound_plan=bound_plan,
                        compatibility_profile=compatibility_profile,
                    )
                )
            else:
                period_results, period_traces = emit_generic_results_from_rules(
                    state=state,
                    bound_plan=bound_plan,
                    compatibility_profile=compatibility_profile,
                )
                accepted.extend(period_results)
                traces.extend(period_traces)
            runtime_value_count += sum(len(outputs) for outputs in state.runtime_values.values())
        if compatibility_profile == LEGACY_M1_PARITY_PROFILE:
            accepted.sort(
                key=lambda item: (
                    -float(item["block_shift_score"]),
                    item["match_id"],
                    item["period"],
                    item["wide_entry_frame_id"],
                )
            )
        else:
            accepted.sort(
                key=lambda item: (
                    item["match_id"],
                    item["period"],
                    int(item["anchor_frame_id"]),
                    item["classification"],
                    item["result_id"],
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
            compatibility_profile=self.compatibility_profile,
        )
        return evaluate_target_in_state(
            bound_plan=bound_plan,
            state=state,
            target=target,
            compatibility_profile=self.compatibility_profile,
        )

    def _execute_period(
        self,
        *,
        bound_plan: BoundQueryPlan,
        match_id: str,
        period: str,
        params: RuntimeParameters,
        compatibility_profile: str | None = None,
    ) -> PeriodState:
        profile = compatibility_profile or self.compatibility_profile
        state = self._period_state(
            match_id=match_id,
            period=period,
            perspective_team_role=bound_plan.perspective_team_role,
            recipe_id=bound_plan.recipe_id,
            recipe_version=bound_plan.recipe_version,
            params=params,
        )
        for node in bound_plan.nodes:
            self._execute_node(state=state, node=node, compatibility_profile=profile)
            enforce_runtime_complexity_limits(
                state=state,
                node=node,
                bound_plan=bound_plan,
            )
        return state

    def _execute_node(
        self,
        *,
        state: PeriodState,
        node: BoundPlanNode,
        compatibility_profile: str | None = None,
    ) -> NodeExecutionResult:
        profile = compatibility_profile or self.compatibility_profile
        inputs = resolved_node_inputs(state, node)
        parameters = resolved_node_parameters(node)
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
        elif isinstance(node, BoundPredicateNode):
            implementation = self.predicates.get(node.operator.name)
            if implementation is None:
                raise RuntimeError(f"No predicate implementation for {node.operator.name}")
            if profile == LEGACY_M1_PARITY_PROFILE and node.operator.name == "persists_for" and legacy_m1_record_persists_for_adapter(
                state=state,
                node=node,
            ):
                runtime_values = record_runtime_values(state, node)
                return NodeExecutionResult(
                    node_id=node.node_id,
                    inputs=inputs,
                    parameters=parameters,
                    outputs=state.signals.get(node.node_id, {}),
                    runtime_values=runtime_values,
                    provenance={"node_kind": node.kind.value, "compatibility_profile": profile, "adapter": "legacy_m1_record_persists_for"},
                )
            if profile == LEGACY_M1_PARITY_PROFILE and node.operator.name == "persists_for" and legacy_m1_frame_signal_persists_for_adapter(
                state=state,
                node=node,
            ):
                runtime_values = record_runtime_values(state, node)
                return NodeExecutionResult(
                    node_id=node.node_id,
                    inputs=inputs,
                    parameters=parameters,
                    outputs=state.signals.get(node.node_id, {}),
                    runtime_values=runtime_values,
                    provenance={"node_kind": node.kind.value, "compatibility_profile": profile, "adapter": "legacy_m1_frame_signal_persists_for"},
                )
            context = MatchContext(
                match_id=state.match_id,
                period=state.period,
                frame_ids=tuple(int(frame_id) for frame_id in state.frame_ids),
                params=state.params,
            )
            state.signals[node.node_id] = execute_predicate_with_resolved_inputs(
                context=context,
                node=node,
                inputs=inputs,
                parameters=parameters,
            )
        else:
            raise RuntimeError(f"Unsupported bound node {node}")
        runtime_values = record_runtime_values(state, node)
        return NodeExecutionResult(
            node_id=node.node_id,
            inputs=inputs,
            parameters=parameters,
            outputs=state.signals.get(node.node_id, {}),
            runtime_values=runtime_values,
            provenance={"node_kind": node.kind.value, "compatibility_profile": profile, "adapter": None},
        )

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
    values = {
        name: parameter.default.value
        for name, parameter in HOST_RUNTIME_PARAMETER_DEFAULTS.items()
        if parameter.default is not None
    }
    values.update({item.name: item.value.value for item in bound_plan.resolved_parameters})
    return RuntimeParameters(
        values=values
    )


def evaluate_target_in_state(
    *,
    bound_plan: BoundQueryPlan,
    state: PeriodState,
    target: EvaluationTarget,
    compatibility_profile: str = GENERIC_EXECUTION_PROFILE,
) -> dict[str, Any]:
    target_frame_id = int(round(target.approximate_time_ms / 1000.0 * FRAME_RATE_HZ))
    radius_frames = int(round(target.search_radius_ms / 1000.0 * FRAME_RATE_HZ))
    anchors = runtime_anchors(state, bound_plan.anchor_source)
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
    result = (
        anchor_record.get("_runtime_result")
        if compatibility_profile == LEGACY_M1_PARITY_PROFILE
        else None
    ) or generic_target_result(anchor_record)
    traces = predicate_traces_for_anchor(
        state,
        closest,
        result,
        bound_plan=bound_plan,
        compatibility_profile=compatibility_profile,
    )
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
            "anchor_frame_id": closest.anchor_frame_id,
            "frame_distance": abs(closest.anchor_frame_id - target_frame_id),
            "accepted": accepted,
            "rejection_reason": result.get("near_miss_reason"),
            "classification": result.get("classification"),
        },
        "predicate_traces": trace_payload,
        "failed_predicates": failed,
    }


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
        decisions = result.get("classification_rule_decisions")
        if isinstance(decisions, list) and all(isinstance(item, dict) for item in decisions):
            result["matched_classification_rules"] = [
                str(item["label"])
                for item in decisions
                if item.get("label") is not None
            ]
        else:
            result["matched_classification_rules"] = matching_classification_rules(
                result=result,
                traces=traces_by_result.get(result_id, []),
                bound_plan=bound_plan,
            )

    if bound_plan.unknown_evidence_policy == UnknownEvidencePolicy.INVALIDATE_EXECUTION:
        if any(trace.status == "UNKNOWN" for trace in trace_records):
            return filtered, trace_records, ExecutionStatus.INCOMPLETE
    if bound_plan.unknown_evidence_policy == UnknownEvidencePolicy.EXCLUDE_CANDIDATE:
        unknown_ids = {
            str(trace.source_evidence.get("result_id"))
            for trace in trace_records
            if trace.status == "UNKNOWN"
        }
        if unknown_ids:
            filtered = [result for result in filtered if str(result["result_id"]) not in unknown_ids]
            kept_ids = {str(result["result_id"]) for result in filtered}
            filtered_traces = [
                trace for trace in filtered_traces if str(trace.source_evidence.get("result_id")) in kept_ids
            ]
            filtered_traces.extend(
                [
                    trace
                    for trace in trace_records
                    if trace.status == "UNKNOWN"
                    and str(trace.source_evidence.get("result_id")) not in kept_ids
                ]
            )
    return filtered, filtered_traces, ExecutionStatus.PASS


def emit_generic_results_from_rules(
    *,
    state: PeriodState,
    bound_plan: BoundQueryPlan,
    compatibility_profile: str,
) -> tuple[list[dict[str, Any]], list[PredicateTrace]]:
    anchors = runtime_anchors(state, bound_plan.anchor_source)
    emitted: list[dict[str, Any]] = []
    traces: list[PredicateTrace] = []
    for anchor in anchors:
        base_result = generic_result_base(
            state=state,
            bound_plan=bound_plan,
            anchor=anchor,
        )
        anchor_traces = predicate_traces_for_anchor(
            state,
            anchor,
            base_result,
            bound_plan=bound_plan,
            compatibility_profile=compatibility_profile,
        )
        anchor_traces.extend(
            missing_target_predicate_traces(
                bound_plan=bound_plan,
                state=state,
                anchor=anchor,
                result=base_result,
                existing_predicate_ids={trace.predicate_id for trace in anchor_traces},
            )
        )
        rule_decisions = rule_decisions_for_traces(
            traces=anchor_traces,
            bound_plan=bound_plan,
        )
        labels = [decision["label"] for decision in rule_decisions]
        traces.extend(
            [
                trace.model_copy(
                    update={
                        "source_evidence": {
                            **trace.source_evidence,
                            "result_id": base_result["result_id"],
                            "emitted_result": bool(labels),
                        }
                    }
                )
                for trace in anchor_traces
                if trace.status == "UNKNOWN"
            ]
        )
        if not labels:
            continue
        classification = labels[0]
        result = {
            **base_result,
            "classification": classification,
            "accepted": True,
            "matched_classification_rules": labels,
            "classification_rule_decisions": rule_decisions,
            "rule_match_status": rule_decisions[0]["rule_match_status"],
            "unknown_required_predicates": rule_decisions[0]["unknown_required_predicates"],
            "requested_evidence": project_requested_evidence_from_runtime(
                state=state,
                anchor=anchor,
                bound_plan=bound_plan,
            ),
            "provenance": {
                "emitter": "generic_rule_emitter",
                "anchor_source": f"{bound_plan.anchor_source.source_node_id}.{bound_plan.anchor_source.output_name}"
                if bound_plan.anchor_source is not None
                else None,
                "compatibility_profile": compatibility_profile,
            },
        }
        emitted.append(result)
        traces.extend(
            [
                trace.model_copy(
                    update={
                        "source_evidence": {
                            **trace.source_evidence,
                            "result_id": result["result_id"],
                        }
                    }
                )
                for trace in anchor_traces
            ]
        )
    return emitted, traces


def generic_result_base(
    *,
    state: PeriodState,
    bound_plan: BoundQueryPlan,
    anchor: RuntimeAnchor,
) -> dict[str, Any]:
    result_id = hashlib.sha256(
        (
            f"{bound_plan.bound_plan_hash}:generic:"
            f"{anchor.match_id}:{anchor.period}:{anchor.anchor_id}"
        ).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "result_id": result_id,
        "classification": None,
        "match_id": anchor.match_id,
        "period": anchor.period,
        "anchor_frame_id": anchor.anchor_frame_id,
        "anchor_id": anchor.anchor_id,
        "accepted": False,
        "perspective_team_role": state.perspective_team_role,
        "defending_team_role": state.defending_team_role,
    }


def rule_labels_for_traces(
    *,
    traces: list[PredicateTrace],
    bound_plan: BoundQueryPlan,
) -> list[str]:
    return [decision["label"] for decision in rule_decisions_for_traces(traces=traces, bound_plan=bound_plan)]


def rule_decisions_for_traces(
    *,
    traces: list[PredicateTrace],
    bound_plan: BoundQueryPlan,
) -> list[dict[str, Any]]:
    status_by_predicate = {trace.predicate_id: trace.status for trace in traces}
    matching: list[tuple[int, int, ClassificationRule, str, list[str]]] = []
    rule_order = {id(rule): index for index, rule in enumerate(bound_plan.classification_rules)}
    for rule in bound_plan.classification_rules:
        statuses = [status_by_predicate.get(predicate_id, "UNKNOWN") for predicate_id in rule.predicate_ids]
        if any(status == "FAIL" for status in statuses):
            continue
        unknown_predicates = [
            predicate_id
            for predicate_id in rule.predicate_ids
            if status_by_predicate.get(predicate_id, "UNKNOWN") == "UNKNOWN"
        ]
        if any(status == "UNKNOWN" for status in statuses):
            if bound_plan.unknown_evidence_policy == UnknownEvidencePolicy.INCLUDE_WITH_WARNING:
                matching.append((len(rule.predicate_ids), rule_order[id(rule)], rule, "WARNING", unknown_predicates))
            continue
        matching.append((len(rule.predicate_ids), rule_order[id(rule)], rule, "PASS", []))
    matching.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "label": rule.label,
            "rule_match_status": match_status,
            "unknown_required_predicates": unknown_predicates,
            "predicate_ids": list(rule.predicate_ids),
        }
        for _specificity, _order, rule, match_status, unknown_predicates in matching
    ]


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
        key = request.alias or f"{request.source.source_node_id}.{request.field}"
        projected[key] = result.get(request.field)
    return projected


def project_requested_evidence_from_runtime(
    *,
    state: PeriodState,
    anchor: RuntimeAnchor,
    bound_plan: BoundQueryPlan,
) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for request in bound_plan.requested_evidence:
        key = request.alias or f"{request.source.source_node_id}.{request.field}"
        runtime_value = state.runtime_values.get(request.source.source_node_id, {}).get(request.source.output_name)
        selected_relation_id = selected_relation_id_for_evidence_request(
            state=state,
            anchor=anchor,
            bound_plan=bound_plan,
            source_node_id=request.source.source_node_id,
            output_name=request.source.output_name,
        )
        projected[key] = evidence_value_for_anchor(
            runtime_value=runtime_value,
            anchor=anchor,
            field=request.field,
            selected_relation_id=selected_relation_id,
        )
    return projected


def unresolved_requested_evidence(
    results: list[dict[str, Any]],
    bound_plan: BoundQueryPlan,
) -> list[dict[str, Any]]:
    required_aliases = {
        request.alias or f"{request.source.source_node_id}.{request.field}"
        for request in bound_plan.requested_evidence
        if request.required
    }
    failures: list[dict[str, Any]] = []
    for result in results:
        requested = result.get("requested_evidence")
        if not isinstance(requested, dict):
            continue
        missing = sorted(
            key
            for key, value in requested.items()
            if key in required_aliases and value is None
        )
        if missing:
            failures.append(
                {
                    "result_id": str(result.get("result_id")),
                    "classification": str(result.get("classification")),
                    "missing_aliases": missing,
                }
            )
    return failures


def selected_relation_id_for_anchor(
    *,
    state: PeriodState,
    anchor: RuntimeAnchor,
    source_node_id: str | None = None,
    output_name: str | None = None,
) -> str | None:
    for node_id, outputs in state.runtime_values.items():
        for runtime_value in outputs.values():
            for record in runtime_records(runtime_value):
                if record.get("predicate_id") is None:
                    continue
                source_record = record.get("source_record") if isinstance(record.get("source_record"), dict) else record
                if not record_matches_anchor(source_record, anchor):
                    continue
                source_evidence = record.get("source_evidence")
                if not witness_source_matches(
                    source_evidence=source_evidence,
                    requested_source_node_id=source_node_id,
                    requested_output_name=output_name,
                ):
                    continue
                if isinstance(source_evidence, dict) and source_evidence.get("witness_relation_id") is not None:
                    return str(source_evidence["witness_relation_id"])
    for node_id, outputs in state.runtime_values.items():
        if source_node_id is not None and node_id != source_node_id:
            continue
        runtime_value = outputs.get("anchor_evaluations")
        if runtime_value is None:
            continue
        for record in runtime_records(runtime_value):
            if record_matches_anchor(record, anchor) and record.get("witness_relation_id") is not None:
                return str(record["witness_relation_id"])
    fallback_output_names = [output_name] if output_name is not None else []
    fallback_output_names.extend(name for name in ("classification", "entry_status") if name not in fallback_output_names)
    for node_id, outputs in state.runtime_values.items():
        if source_node_id is not None and node_id != source_node_id:
            continue
        for fallback_output_name in fallback_output_names:
            runtime_value = outputs.get(fallback_output_name)
            if runtime_value is None:
                continue
            for record in runtime_records(runtime_value):
                if record_matches_anchor(record, anchor) and record.get("relation_id") is not None:
                    return str(record["relation_id"])
    return None


def selected_relation_id_for_evidence_request(
    *,
    state: PeriodState,
    anchor: RuntimeAnchor,
    bound_plan: BoundQueryPlan,
    source_node_id: str | None = None,
    output_name: str | None = None,
) -> str | None:
    destination_relation_id = destination_entry_relation_id_for_source(
        state=state,
        anchor=anchor,
        bound_plan=bound_plan,
        source_node_id=source_node_id,
        output_name=output_name,
    )
    if destination_relation_id is not None:
        return destination_relation_id
    return selected_relation_id_for_anchor(
        state=state,
        anchor=anchor,
        source_node_id=source_node_id,
        output_name=output_name,
    )


def destination_entry_relation_id_for_source(
    *,
    state: PeriodState,
    anchor: RuntimeAnchor,
    bound_plan: BoundQueryPlan,
    source_node_id: str | None,
    output_name: str | None,
) -> str | None:
    if source_node_id is None or output_name != "episodes":
        return None
    for node in bound_plan.nodes:
        if not isinstance(node, BoundCatalogNode):
            continue
        if node.catalog_ref != "relation_destination_entry":
            continue
        source_ref = node.inputs.get("relation_episodes")
        if source_ref is None:
            continue
        if source_ref.source_node_id != source_node_id or source_ref.output_name != output_name:
            continue
        runtime_value = state.runtime_values.get(node.node_id, {}).get("entry_status")
        if runtime_value is None:
            continue
        for record in runtime_records(runtime_value):
            if record_matches_anchor(record, anchor) and record.get("relation_id") is not None:
                return str(record["relation_id"])
    return None


def witness_source_matches(
    *,
    source_evidence: Any,
    requested_source_node_id: str | None,
    requested_output_name: str | None,
) -> bool:
    if requested_source_node_id is None or not isinstance(source_evidence, dict):
        return True
    if source_evidence.get("source_node_id") != requested_source_node_id:
        return False
    source_output = source_evidence.get("source_output_name")
    if requested_output_name in {None, source_output}:
        return True
    if requested_output_name == "episodes" and source_output == "anchor_evaluations":
        return True
    return False


def evidence_value_for_anchor(
    *,
    runtime_value: RuntimeValue | None,
    anchor: RuntimeAnchor,
    field: str,
    selected_relation_id: str | None = None,
) -> Any:
    if runtime_value is None:
        return None
    for record in runtime_records(runtime_value):
        if (
            selected_relation_id is not None
            and record.get("relation_id") is not None
            and str(record["relation_id"]) != selected_relation_id
        ):
            continue
        if record_matches_anchor(record, anchor):
            return record.get(field)
    if isinstance(runtime_value.value, FrameSignal):
        try:
            index = runtime_value.value.frame_ids.index(anchor.anchor_frame_id)
        except ValueError:
            return None
        if field == runtime_value.output.name or field in {"value", "classification"}:
            return runtime_value.value.values[index]
    return None


def record_matches_anchor(record: dict[str, Any], anchor: RuntimeAnchor) -> bool:
    if not isinstance(record, dict):
        return False
    if str(record.get("anchor_id") or "") == anchor.anchor_id:
        return True
    if optional_int(record.get("anchor_frame_id")) == anchor.anchor_frame_id:
        return True
    source = record.get("source_result")
    if isinstance(source, dict) and record_matches_anchor(source, anchor):
        return True
    for source_record in record.get("source_records") or []:
        if isinstance(source_record, dict) and record_matches_anchor(source_record, anchor):
            return True
    return False


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


def enforce_runtime_complexity_limits(
    *,
    state: PeriodState,
    node: BoundPlanNode,
    bound_plan: BoundQueryPlan,
) -> None:
    if not isinstance(node, BoundCatalogNode) or node.kind != NodeKind.RELATION:
        return
    limit = int(bound_plan.complexity_limits.max_relations_per_anchor)
    runtime_value = state.runtime_values.get(node.node_id, {}).get("episodes")
    if runtime_value is None:
        return
    counts: Counter[str] = Counter()
    for record in runtime_records(runtime_value):
        key = str(record.get("anchor_id") or record.get("result_id") or record.get("anchor_frame_id") or "")
        if key:
            counts[key] += 1
    violations = {
        anchor_key: count
        for anchor_key, count in counts.items()
        if count > limit
    }
    if violations:
        sample_key, sample_count = sorted(violations.items(), key=lambda item: (-item[1], item[0]))[0]
        raise RuntimeError(
            f"{node.node_id} exceeded max_relations_per_anchor={limit}; "
            f"anchor {sample_key} produced {sample_count} relations"
        )


def runtime_records(value: RuntimeValue) -> list[dict[str, Any]]:
    if value.records and all(isinstance(item, dict) for item in value.records):
        return value.records
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


def predicate_frame_signal_from_source(
    source_value: RuntimeValue,
    passed: list[bool | None],
    node: BoundPredicateNode,
) -> FrameSignal:
    return FrameSignal(
        frame_ids=source_value.value.frame_ids
        if isinstance(source_value.value, FrameSignal)
        else list(range(len(passed))),
        values=passed,
        unknown_mask=[status is None for status in passed],
        unit=node.output.unit,
        entity_scope=node.output.entity_scope,
    )


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
    minimum_frames: int,
    analysis_rate_hz: int,
) -> dict[str, Any]:
    series = record.get("truth_series")
    if not isinstance(series, pd.Series):
        return {"persistent": False, "duration_seconds": None, "start_frame_id": None, "end_frame_id": None}
    return boolean_persistence_evidence(series, minimum_frames, analysis_rate_hz)


def legacy_m1_record_persists_for_adapter(*, state: PeriodState, node: BoundPredicateNode) -> bool:
    duration_seconds = float(node.duration.value) if isinstance(node.duration, TypedValue) else None
    if duration_seconds is None:
        raise RuntimeError(f"{node.node_id} requires duration")
    runtime_value = source_runtime_value(state, node)
    values = runtime_frame_values(runtime_value)
    if not isinstance(values, list):
        return False
    records = runtime_records(runtime_value)
    if not (
        records
        and len(records) == len(values)
        and all(
            isinstance(record.get("truth_series"), pd.Series)
            and isinstance(record.get("measure_series"), pd.Series)
            for record in records
        )
    ):
        return False
    analysis_rate_hz = state.params.integer("analysis_rate_hz")
    minimum_frames = int(round(duration_seconds * analysis_rate_hz))
    accepted_records: list[dict[str, Any]] = []
    for record, source_status in zip(records, values, strict=True):
        persistence = record_persistence_evidence(
            record=record,
            minimum_frames=minimum_frames,
            analysis_rate_hz=analysis_rate_hz,
        )
        persistent = bool(persistence["persistent"])
        record["predicate_persistent"] = persistent
        record["predicate_persistence_seconds"] = persistence["duration_seconds"]
        record["predicate_persistence_start_frame_id"] = persistence["start_frame_id"]
        record["predicate_persistence_end_frame_id"] = persistence["end_frame_id"]
        record["predicate_gate_passed"] = bool(source_status is True and persistent)
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
                "adapter": "legacy_m1_record_persists_for",
            },
        )
        if record["predicate_gate_passed"]:
            accepted_records.append(record)
    state.signals[node.node_id] = {
        "predicate": accepted_records,
        "episodes": accepted_records,
        "predicate_records": accepted_records,
    }
    return True


def legacy_m1_frame_signal_persists_for_adapter(*, state: PeriodState, node: BoundPredicateNode) -> bool:
    duration_seconds = float(node.duration.value) if isinstance(node.duration, TypedValue) else None
    if duration_seconds is None:
        raise RuntimeError(f"{node.node_id} requires duration")
    runtime_value = source_runtime_value(state, node)
    values = runtime_frame_values(runtime_value)
    if not isinstance(values, list) or not all(value is None or isinstance(value, bool) for value in values):
        return False
    source_facts = runtime_records(runtime_value)
    if not source_facts:
        return False
    if any(isinstance(record.get("measure_series"), pd.Series) for record in source_facts):
        return False
    if not all(isinstance(record, dict) and "status" in record for record in source_facts):
        return False
    analysis_rate_hz = state.params.integer("analysis_rate_hz")
    minimum_frames = int(round(duration_seconds * analysis_rate_hz))
    frame_ids = frame_ids_for_runtime_value(
        runtime_value,
        MatchContext(
            match_id=state.match_id,
            period=state.period,
            frame_ids=tuple(int(frame_id) for frame_id in state.frame_ids),
            params=state.params,
        ),
    )
    episodes = episode_records_from_frame_ids_and_mask(
        frame_ids=frame_ids,
        mask=np.asarray([value is True for value in values], dtype=bool),
        minimum_frames=minimum_frames,
    )
    for episode in episodes:
        episode.setdefault("_predicate_status", {})
        start_index = int(episode["start_index"])
        if start_index < len(source_facts):
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
                "adapter": "legacy_m1_frame_signal_persists_for",
            },
        )
    state.signals[node.node_id] = {"predicate": episodes, "episodes": episodes}
    return True


def record_runtime_values(state: PeriodState, node: BoundPlanNode) -> dict[str, RuntimeValue]:
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
            records=raw_outputs.get(f"{output.name}_records") or raw_outputs.get("predicate_facts"),
        )
    state.runtime_values[node.node_id] = values
    return values


def resolved_node_inputs(state: PeriodState, node: BoundPlanNode) -> dict[str, RuntimeValue]:
    if isinstance(node, BoundCatalogNode):
        return {
            name: catalog_input_value(state, node, name)
            for name in sorted(node.inputs)
        }
    if isinstance(node, BoundPredicateNode):
        return {node.input.output_name: source_runtime_value(state, node)}
    return {}


def resolved_node_parameters(node: BoundPlanNode) -> dict[str, TypedValue]:
    if isinstance(node, BoundCatalogNode):
        return dict(node.resolved_parameters)
    if isinstance(node, BoundPredicateNode):
        parameters: dict[str, TypedValue] = {}
        if node.compare is not None:
            parameters["compare"] = node.compare
        if node.duration is not None:
            parameters["duration"] = node.duration
        return parameters
    return {}


def execute_predicate_with_resolved_inputs(
    *,
    context: MatchContext,
    node: BoundPredicateNode,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> dict[str, Any]:
    if not inputs:
        raise RuntimeError(f"{node.node_id} requires one resolved input")
    runtime_value = next(iter(inputs.values()))
    if node.operator.name in {"gt", "gte", "lte"}:
        compare = parameters.get("compare")
        if compare is None:
            raise RuntimeError(f"{node.node_id} requires compare")
        threshold = float(compare.value)
        values = numeric_runtime_values(runtime_value, node.node_id)
        if node.operator.name == "gt":
            passed = [None if value is None else value > threshold for value in values]
        elif node.operator.name == "gte":
            passed = [None if value is None else value >= threshold for value in values]
        else:
            passed = [None if value is None else value <= threshold for value in values]
        output: dict[str, Any] = {
            "predicate": predicate_frame_signal_from_source(runtime_value, passed, node)
        }
        records = runtime_records(runtime_value)
        if records and len(records) == len(passed):
            for record, status, value in zip(records, passed, values, strict=True):
                measure_series = record.get("measure_series")
                if isinstance(measure_series, pd.Series):
                    record["truth_series"] = measure_series.apply(
                        lambda item: None if is_nan_number(item) else bool(float(item) >= threshold)
                    )
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
            output["predicate_facts"] = comparison_predicate_facts_from_context(
                context=context,
                node=node,
                values=values,
                statuses=passed,
                threshold=threshold,
            )
        return output
    if node.operator.name in {"eq", "neq"}:
        values = runtime_frame_values(runtime_value)
        if not isinstance(values, list):
            raise RuntimeError(f"{node.node_id} expected list-backed source values")
        compare = parameters.get("compare")
        compare_value = compare.value if compare is not None else None
        if node.operator.name == "eq":
            passed = [None if value is None else value == compare_value for value in values]
        else:
            passed = [None if value is None else value != compare_value for value in values]
        output: dict[str, Any] = {
            "predicate": predicate_frame_signal_from_source(runtime_value, passed, node)
        }
        records = runtime_records(runtime_value)
        if records and len(records) == len(passed):
            predicate_records: list[dict[str, Any]] = []
            for record, status, value in zip(records, passed, values, strict=False):
                predicate_records.append(
                    predicate_record_for_source_record(
                        source_record=record,
                        node=node,
                        status=predicate_status_label(status),
                        value=typed_enum(str(value)) if value is not None else None,
                        threshold=typed_enum(str(compare_value)),
                        unit=Unit.NONE,
                        frame_id=optional_int(record.get("destination_entry_frame_id"))
                        or optional_int(record.get("outcome_frame_id"))
                        or optional_int(record.get("anchor_frame_id")),
                        source_evidence={
                            "source_node_id": node.input.source_node_id,
                            "source_output_name": node.input.output_name,
                            "witness_relation_id": record.get("relation_id"),
                            "reason": "outcome_not_evaluated" if value is None else None,
                        },
                    )
                )
            output["items"] = [record for record, status in zip(records, passed, strict=False) if status]
            output["predicate_records"] = predicate_records
        return output
    if node.operator.name == "persists_for":
        duration = parameters.get("duration")
        if duration is None:
            raise RuntimeError(f"{node.node_id} requires duration")
        if not isinstance(runtime_value.value, FrameSignal):
            raise RuntimeError(f"Unsupported persists_for source for {node.node_id}")
        temporal = execute_persists_for(
            signal=runtime_value.value,
            duration=duration,
            analysis_rate_hz=context.params.integer("analysis_rate_hz"),
        )
        records = attach_source_records_to_temporal_records(
            temporal.output_records(),
            source_records=runtime_records(runtime_value),
        )
        return {
            "predicate": records,
            "episodes": records,
            "passing_episodes": temporal.episodes,
            "unknown_intervals": temporal.unknown_intervals,
        }
    if node.operator.name == "exists":
        source = runtime_value.value
        if isinstance(source, list):
            records = [record for record in source if isinstance(record, dict)]
            coverage = relation_anchor_evaluation_records(records)
            if coverage:
                return exists_from_anchor_evaluations(
                    node=node,
                    records=coverage,
                )
            frame_ids = [
                source_record_frame_id(record)
                for record in records
            ]
            usable = [
                (record, int(frame_id))
                for record, frame_id in zip(records, frame_ids, strict=False)
                if frame_id is not None
            ]
            if usable:
                return {
                    "predicate": FrameSignal(
                        frame_ids=[frame_id for _record, frame_id in usable],
                        values=[True for _record, _frame_id in usable],
                        unknown_mask=[False for _record, _frame_id in usable],
                        unit=node.output.unit,
                        entity_scope=node.output.entity_scope,
                    ),
                    "predicate_records": [
                        predicate_record_for_source_record(
                            source_record=record,
                            node=node,
                            status="PASS",
                            value=TypedValue(payload_type=PayloadType.BOOLEAN, value=True, unit=Unit.NONE),
                            threshold=None,
                            unit=Unit.NONE,
                            frame_id=frame_id,
                            source_evidence={
                                "source_node_id": node.input.source_node_id,
                                "source_output_name": node.input.output_name,
                            },
                        )
                        for record, frame_id in usable
                    ],
                    "episodes": source,
                }
            return {"predicate": bool(source), "episodes": source}
        raise RuntimeError(f"Unsupported exists source for {node.node_id}")
    if node.operator.name == "count_at_least":
        source = runtime_value.value
        compare = parameters.get("compare")
        if compare is None or not isinstance(source, list):
            raise RuntimeError(f"Unsupported count_at_least source for {node.node_id}")
        records = [record for record in source if isinstance(record, dict)]
        coverage = relation_anchor_evaluation_records(records)
        if coverage:
            return count_at_least_from_anchor_evaluations(
                node=node,
                records=coverage,
                threshold=int(round(float(compare.value))),
            )
        return {"predicate": len(source) >= int(round(float(compare.value)))}
    raise RuntimeError(f"Unsupported predicate operator {node.operator.name}")


def relation_anchor_evaluation_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("evaluation_status") in {"PASS", "FAIL", "UNKNOWN"}
        and "anchor_frame_id" in record
        and "relation_count" in record
    ]


def exists_from_anchor_evaluations(
    *,
    node: BoundPredicateNode,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    statuses = [anchor_evaluation_status(record) for record in records]
    return predicate_output_from_anchor_evaluations(
        node=node,
        records=records,
        statuses=statuses,
        values=[None if status is None else bool(status) for status in statuses],
        threshold=None,
    )


def count_at_least_from_anchor_evaluations(
    *,
    node: BoundPredicateNode,
    records: list[dict[str, Any]],
    threshold: int,
) -> dict[str, Any]:
    statuses: list[bool | None] = []
    values: list[int | None] = []
    for record in records:
        if str(record.get("evaluation_status")) == "UNKNOWN":
            statuses.append(None)
            values.append(None)
            continue
        count = optional_int(record.get("relation_count"))
        if count is None:
            statuses.append(None)
            values.append(None)
            continue
        statuses.append(count >= threshold)
        values.append(count)
    return predicate_output_from_anchor_evaluations(
        node=node,
        records=records,
        statuses=statuses,
        values=values,
        threshold=TypedValue(payload_type=PayloadType.NUMBER, value=threshold, unit=Unit.COUNT),
    )


def anchor_evaluation_status(record: dict[str, Any]) -> bool | None:
    status = str(record.get("evaluation_status"))
    if status == "PASS":
        return True
    if status == "FAIL":
        return False
    return None


def predicate_output_from_anchor_evaluations(
    *,
    node: BoundPredicateNode,
    records: list[dict[str, Any]],
    statuses: list[bool | None],
    values: list[Any],
    threshold: TypedValue | None,
) -> dict[str, Any]:
    usable = [
        (record, status, value, optional_int(record.get("anchor_frame_id")))
        for record, status, value in zip(records, statuses, values, strict=True)
    ]
    usable = [
        (record, status, value, frame_id)
        for record, status, value, frame_id in usable
        if frame_id is not None
    ]
    predicate_records: list[dict[str, Any]] = []
    for record, status, value, frame_id in usable:
        predicate_records.append(
            predicate_record_for_source_record(
                source_record=record,
                node=node,
                status=predicate_status_label(status),
                value=predicate_anchor_evaluation_value(value),
                threshold=threshold,
                unit=threshold.unit if threshold is not None else Unit.NONE,
                frame_id=frame_id,
                source_evidence={
                    "source_node_id": node.input.source_node_id,
                    "source_output_name": node.input.output_name,
                    "witness_relation_id": record.get("witness_relation_id"),
                    "relation_count": record.get("relation_count"),
                    "evaluation_status": record.get("evaluation_status"),
                    "unknown_reason": record.get("unknown_reason"),
                },
            )
        )
    return {
        "predicate": FrameSignal(
            frame_ids=[int(frame_id) for _record, _status, _value, frame_id in usable],
            values=[status for _record, status, _value, _frame_id in usable],
            unknown_mask=[status is None for _record, status, _value, _frame_id in usable],
            unit=node.output.unit,
            entity_scope=node.output.entity_scope,
        ),
        "predicate_records": predicate_records,
        "items": [
            record
            for record, status, _value, _frame_id in usable
            if status is True
        ],
    }


def predicate_anchor_evaluation_value(value: Any) -> TypedValue | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return TypedValue(payload_type=PayloadType.BOOLEAN, value=value, unit=Unit.NONE)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return TypedValue(payload_type=PayloadType.NUMBER, value=float(value), unit=Unit.COUNT)
    return None


def numeric_runtime_values(runtime_value: RuntimeValue, node_id: str) -> list[float | None]:
    value = runtime_frame_values(runtime_value)
    if not isinstance(value, list):
        raise RuntimeError(f"{node_id} expected list-backed numeric runtime value")
    values: list[float | None] = []
    for item in value:
        if item is None or is_nan_number(item):
            values.append(None)
        elif isinstance(item, bool) or not isinstance(item, int | float):
            raise RuntimeError(f"{node_id} expected numeric source values")
        else:
            values.append(float(item))
    return values


def comparison_predicate_facts_from_context(
    *,
    context: MatchContext,
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
                "frame_id": int(context.frame_ids[index]) if index < len(context.frame_ids) else None,
                "window": None,
                "source_evidence": {
                    "source_node_id": node.input.source_node_id,
                    "source_output_name": node.input.output_name,
                },
            }
        )
    return facts


def frame_ids_for_runtime_value(runtime_value: RuntimeValue, context: MatchContext) -> list[int]:
    if isinstance(runtime_value.value, FrameSignal):
        return runtime_value.value.frame_ids
    values = runtime_frame_values(runtime_value)
    if isinstance(values, list) and len(values) <= len(context.frame_ids):
        return [int(frame_id) for frame_id in context.frame_ids[: len(values)]]
    raise RuntimeError("cannot infer frame IDs for runtime value")


def episode_records_from_frame_ids_and_mask(
    *,
    frame_ids: list[int],
    mask: np.ndarray,
    minimum_frames: int,
) -> list[dict[str, int]]:
    return [
        {
            "start_index": int(start),
            "end_index": int(end),
            "start_frame_id": int(frame_ids[start]),
            "end_frame_id": int(frame_ids[end]),
        }
        for start, end in segment_true(mask, minimum_frames)
    ]


def execute_persists_for(
    *,
    signal: FrameSignal,
    duration: TypedValue,
    analysis_rate_hz: int,
) -> TemporalPredicateResult:
    values = signal.values
    if not all(value is None or isinstance(value, bool) for value in values):
        raise RuntimeError("persists_for requires a Boolean frame signal")
    minimum_frames = duration_to_frames(duration, analysis_rate_hz)
    pass_episodes = episode_records_from_frame_ids_and_mask(
        frame_ids=signal.frame_ids,
        mask=np.asarray([value is True for value in values], dtype=bool),
        minimum_frames=minimum_frames,
    )
    pass_mask = np.zeros(len(values), dtype=bool)
    for episode in pass_episodes:
        pass_mask[int(episode["start_index"]) : int(episode["end_index"]) + 1] = True
    unknown_mask = np.asarray(
        [
            not bool(pass_mask[index]) and persistence_status_at_index(values, index, minimum_frames) == "UNKNOWN"
            for index in range(len(values))
        ],
        dtype=bool,
    )
    unknown_intervals = episode_records_from_frame_ids_and_mask(
        frame_ids=signal.frame_ids,
        mask=unknown_mask,
        minimum_frames=1,
    )
    fail_intervals = episode_records_from_frame_ids_and_mask(
        frame_ids=signal.frame_ids,
        mask=~pass_mask & ~unknown_mask,
        minimum_frames=1,
    )
    return TemporalPredicateResult(
        episodes=pass_episodes,
        unknown_intervals=unknown_intervals,
        fail_intervals=fail_intervals,
        evaluated_frame_ids=[int(frame_id) for frame_id in signal.frame_ids],
    )


def duration_to_frames(duration: TypedValue, analysis_rate_hz: int) -> int:
    value = float(duration.value)
    if value <= 0:
        raise RuntimeError("persists_for duration must be positive")
    if duration.unit == Unit.SECOND:
        frames = math.ceil(value * analysis_rate_hz)
    elif duration.unit == Unit.MILLISECOND:
        frames = math.ceil(value / 1000.0 * analysis_rate_hz)
    elif duration.unit == Unit.FRAME:
        frames = math.ceil(value)
    else:
        raise RuntimeError(f"Unsupported persists_for duration unit {duration.unit.value}")
    if frames <= 0:
        raise RuntimeError("persists_for duration must cover at least one frame")
    return frames


def persistence_status_at_index(
    values: list[Any],
    index: int,
    minimum_frames: int,
) -> str:
    start_min = max(0, index - minimum_frames + 1)
    start_max = min(index, len(values) - minimum_frames)
    for start in range(start_min, start_max + 1):
        window = values[start : start + minimum_frames]
        if all(value is True for value in window):
            return "PASS"
    for start in range(start_min, start_max + 1):
        window = values[start : start + minimum_frames]
        if all(value is not False for value in window) and any(value is None for value in window):
            return "UNKNOWN"
    return "FAIL"


def primitive_noop(state: PeriodState, node: BoundCatalogNode) -> None:
    state.signals.setdefault(node.node_id, {})


def primitive_possession_segment(state: PeriodState, node: BoundCatalogNode) -> None:
    possession_mask = (state.possession_role == state.perspective_team_role) & state.ball_alive
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
            "entity_refs": [state.perspective_team_id],
        }
        for start, end in segment_true(possession_mask, minimum_frames)
    ]
    state.signals[node.node_id] = {"episodes": segments, "anchors": segments}


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

    horizon_seconds = node_parameter_number(node, "destination_entry_horizon_seconds", 6.0)
    result_seed = node.resolved_parameters.get("result_id_seed")
    seed = str(result_seed.value) if result_seed is not None else state.params.text("result_id_seed_hash")
    episode_selection = node_parameter_text(
        node,
        "episode_selection",
        "entry_first_then_progression" if generic_entry_output else "first_by_duration_clearance",
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
            measure_series = record.get("measure_series")
            if isinstance(measure_series, pd.Series):
                record["truth_series"] = measure_series.apply(
                    lambda item: None if is_nan_number(item) else bool(float(item) >= threshold)
                )
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
    values = runtime_frame_values(runtime_value)
    if not isinstance(values, list):
        raise RuntimeError(f"{node.node_id} expected list-backed source values")
    compare = node.compare.value if isinstance(node.compare, TypedValue) else None
    passed = [None if value is None else value == compare for value in values]
    state.signals[node.node_id] = {
        "predicate": predicate_frame_signal_from_source(runtime_value, passed, node),
    }


def predicate_neq(state: PeriodState, node: BoundPredicateNode) -> None:
    runtime_value = source_runtime_value(state, node)
    values = runtime_frame_values(runtime_value)
    if not isinstance(values, list):
        raise RuntimeError(f"{node.node_id} expected list-backed source values")
    compare = node.compare.value if isinstance(node.compare, TypedValue) else None
    passed = [None if value is None else value != compare for value in values]
    output: dict[str, Any] = {
        "predicate": predicate_frame_signal_from_source(runtime_value, passed, node),
    }
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
    runtime_value = source_runtime_value(state, node)
    if not isinstance(runtime_value.value, FrameSignal):
        raise RuntimeError(f"Unsupported persists_for source for {node.node_id}")
    temporal = execute_persists_for(
        signal=runtime_value.value,
        duration=node.duration,
        analysis_rate_hz=state.params.integer("analysis_rate_hz"),
    )
    state.signals[node.node_id] = {
        "predicate": temporal.output_records(),
        "episodes": temporal.output_records(),
        "passing_episodes": temporal.episodes,
        "unknown_intervals": temporal.unknown_intervals,
    }


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


def attach_source_records_to_temporal_records(
    records: list[dict[str, Any]],
    *,
    source_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not source_records:
        return records
    enriched: list[dict[str, Any]] = []
    for record in records:
        start = optional_int(record.get("start_frame_id"))
        end = optional_int(record.get("end_frame_id"))
        if start is None or end is None:
            enriched.append(record)
            continue
        matches = [
            source
            for source in source_records
            if source_record_frame_id(source) is not None
            and start <= int(source_record_frame_id(source)) <= end
        ]
        enriched.append({**record, "source_records": matches} if matches else record)
    return enriched


def source_record_frame_id(record: dict[str, Any]) -> int | None:
    for key in ("anchor_frame_id", "frame_id", "wide_entry_frame_id", "start_frame_id"):
        frame_id = optional_int(record.get(key))
        if frame_id is not None:
            return frame_id
    source = record.get("source_result")
    if isinstance(source, dict):
        frame_id = source_record_frame_id(source)
        if frame_id is not None:
            return frame_id
    return None


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


def runtime_anchors(state: PeriodState, anchor_source: Any) -> list[RuntimeAnchor]:
    anchors: list[RuntimeAnchor] = []
    seen: set[str] = set()
    if anchor_source is None:
        return anchors
    try:
        runtime_value = state.runtime_values[anchor_source.source_node_id][anchor_source.output_name]
    except KeyError:
        return anchors
    for index, record in enumerate(runtime_records(runtime_value)):
        anchor = runtime_anchor_from_record(
            state=state,
            node_id=anchor_source.source_node_id,
            output_name=anchor_source.output_name,
            index=index,
            record=record,
        )
        if anchor is None or anchor.semantic_key in seen:
            continue
        seen.add(anchor.semantic_key)
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
    canonical = anchor_record_id(
        match_id=match_id,
        period=period,
        anchor_frame_id=anchor_frame_id,
        start_frame_id=optional_int(record.get("start_frame_id")),
        end_frame_id=optional_int(record.get("end_frame_id")),
        entity_refs=record.get("entity_refs"),
    )
    return RuntimeAnchor(
        anchor_id=canonical,
        semantic_key=canonical,
        match_id=match_id,
        period=period,
        anchor_frame_id=anchor_frame_id,
        source_node_id=node_id,
        output_name=output_name,
        start_frame_id=optional_int(record.get("start_frame_id") or record.get("possession_start_frame_id")),
        end_frame_id=optional_int(record.get("end_frame_id") or record.get("possession_end_frame_id")),
        attributes=record,
    )


def generic_target_result(anchor_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "result_id": str(anchor_record.get("anchor_id", "")),
        "classification": anchor_record.get("classification"),
        "accepted": False,
        "anchor_frame_id": anchor_record.get("anchor_frame_id"),
    }


def anchor_record_id(
    *,
    match_id: str,
    period: str,
    anchor_frame_id: int,
    start_frame_id: int | None,
    end_frame_id: int | None,
    entity_refs: Any,
) -> str:
    return canonical_anchor_record_id(
        {
            "match_id": match_id,
            "period": period,
            "anchor_frame_id": int(anchor_frame_id),
            "start_frame_id": start_frame_id,
            "end_frame_id": end_frame_id,
            "entity_refs": entity_refs if isinstance(entity_refs, list) else [],
        }
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


def accepted_predicate_traces(
    state: PeriodState,
    *,
    bound_plan: BoundQueryPlan | None = None,
    compatibility_profile: str = LEGACY_M1_PARITY_PROFILE,
) -> list[PredicateTrace]:
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
            traces.extend(
                predicate_traces_for_anchor(
                    state,
                    anchor,
                    result,
                    bound_plan=bound_plan,
                    compatibility_profile=compatibility_profile,
                )
            )
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
    bound_plan: BoundQueryPlan | None = None,
    compatibility_profile: str = GENERIC_EXECUTION_PROFILE,
) -> list[PredicateTrace]:
    runtime_traces = (
        predicate_traces_from_declared_runtime_outputs(
            bound_plan=bound_plan,
            state=state,
            anchor=anchor,
            result=result,
        )
        if bound_plan is not None
        else []
    )
    legacy_traces = (
        predicate_traces_from_status_records(
            state=state,
            anchor=anchor,
            result=result,
        )
        if compatibility_profile == LEGACY_M1_PARITY_PROFILE
        else []
    )
    if runtime_traces:
        legacy_by_id = {trace.predicate_id: trace for trace in legacy_traces}
        merged: list[PredicateTrace] = []
        for trace in runtime_traces:
            legacy = legacy_by_id.pop(trace.predicate_id, None)
            if legacy is not None and compatibility_profile == LEGACY_M1_PARITY_PROFILE:
                merged.append(legacy)
            elif legacy is not None and trace.status == "UNKNOWN":
                merged.append(legacy)
            else:
                merged.append(trace)
        merged.extend(legacy_by_id.values())
        return merged
    return legacy_traces


def predicate_traces_from_declared_runtime_outputs(
    *,
    bound_plan: BoundQueryPlan,
    state: PeriodState,
    anchor: RuntimeAnchor,
    result: dict[str, Any],
) -> list[PredicateTrace]:
    traces: list[PredicateTrace] = []
    result_id = str(result.get("result_id") or anchor.anchor_id)
    common = {
        "result_id": result_id,
        "candidate_key": anchor.anchor_id,
        "anchor_id": anchor.anchor_id,
        "match_id": anchor.match_id,
        "period": anchor.period,
        "anchor_frame_id": anchor.anchor_frame_id,
    }
    for node in bound_plan.nodes:
        if not isinstance(node, BoundPredicateNode):
            continue
        runtime_value = state.runtime_values.get(node.node_id, {}).get(node.output.name)
        if runtime_value is None:
            continue
        trace = predicate_trace_from_runtime_value(
            node=node,
            runtime_value=runtime_value,
            anchor=anchor,
            result_id=result_id,
            common_evidence=common,
        )
        if trace is not None:
            traces.append(trace)
    return traces


def predicate_record_for_source_record(
    *,
    source_record: dict[str, Any],
    node: BoundPredicateNode,
    status: str,
    value: TypedValue | None,
    threshold: TypedValue | None,
    unit: Unit,
    frame_id: int | None,
    source_evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "predicate_id": node.node_id,
        "status": status,
        "value": value.model_dump(mode="json") if value is not None else None,
        "threshold": threshold.model_dump(mode="json") if threshold is not None else None,
        "unit": unit.value,
        "frame_id": frame_id,
        "window": None,
        "source_evidence": {key: item for key, item in source_evidence.items() if item is not None},
        "source_record": source_record,
    }


def predicate_trace_from_runtime_value(
    *,
    node: BoundPredicateNode,
    runtime_value: RuntimeValue,
    anchor: RuntimeAnchor,
    result_id: str,
    common_evidence: dict[str, Any],
) -> PredicateTrace | None:
    source_evidence = {
        **common_evidence,
        "source_node_id": node.input.source_node_id,
        "source_output_name": node.input.output_name,
        "trace_source": f"{node.node_id}.{node.output.name}",
    }
    record_trace = predicate_trace_from_runtime_record(
        node=node,
        runtime_value=runtime_value,
        anchor=anchor,
        source_evidence=source_evidence,
    )
    if record_trace is not None:
        return record_trace
    if isinstance(runtime_value.value, FrameSignal):
        try:
            index = runtime_value.value.frame_ids.index(anchor.anchor_frame_id)
        except ValueError:
            return PredicateTrace(
                predicate_id=node.node_id,
                status="UNKNOWN",
                value=None,
                threshold=node.compare if isinstance(node.compare, TypedValue) else node.duration,
                unit=node.output.unit,
                frame_id=anchor.anchor_frame_id,
                source_evidence={**source_evidence, "reason": "anchor_frame_missing_from_predicate_signal"},
            )
        raw = runtime_value.value.values[index]
        if raw is None:
            status = "UNKNOWN"
            value = None
        elif isinstance(raw, bool):
            status = "PASS" if raw else "FAIL"
            value = TypedValue(payload_type=PayloadType.BOOLEAN, value=raw, unit=Unit.NONE)
        else:
            status = "UNKNOWN"
            value = None
        return PredicateTrace(
            predicate_id=node.node_id,
            status=status,
            value=value,
            threshold=node.compare if isinstance(node.compare, TypedValue) else node.duration,
            unit=node.output.unit,
            frame_id=anchor.anchor_frame_id,
            source_evidence=source_evidence,
        )
    if isinstance(runtime_value.value, list):
        matched = None
        has_temporal_status = False
        for episode in runtime_value.value:
            if not isinstance(episode, dict):
                continue
            if "temporal_status" in episode:
                has_temporal_status = True
            start = optional_int(episode.get("start_frame_id"))
            end = optional_int(episode.get("end_frame_id"))
            if start is not None and end is not None and start <= anchor.anchor_frame_id <= end:
                matched = episode
                break
        if has_temporal_status:
            if matched is None:
                status = "UNKNOWN"
                matched_window = None
            else:
                status = str(matched.get("temporal_status") or "PASS")
                matched_window = matched
        else:
            status = "PASS" if matched is not None else "FAIL"
            matched_window = matched
        return PredicateTrace(
            predicate_id=node.node_id,
            status=status,
            value=TypedValue(payload_type=PayloadType.BOOLEAN, value=status == "PASS", unit=Unit.NONE)
            if status in {"PASS", "FAIL"}
            else None,
            threshold=node.compare if isinstance(node.compare, TypedValue) else node.duration,
            unit=node.output.unit,
            frame_id=anchor.anchor_frame_id,
            window={
                "start_frame_id": matched_window.get("start_frame_id"),
                "end_frame_id": matched_window.get("end_frame_id"),
            }
            if isinstance(matched_window, dict)
            else None,
            source_evidence=source_evidence,
        )
    return None


def predicate_trace_from_runtime_record(
    *,
    node: BoundPredicateNode,
    runtime_value: RuntimeValue,
    anchor: RuntimeAnchor,
    source_evidence: dict[str, Any],
) -> PredicateTrace | None:
    for record in runtime_records(runtime_value):
        if record.get("predicate_id") != node.node_id:
            continue
        source_record = record.get("source_record") if isinstance(record.get("source_record"), dict) else record
        if not record_matches_anchor(source_record, anchor):
            continue
        return PredicateTrace(
            predicate_id=node.node_id,
            status=record["status"],
            value=TypedValue.model_validate(record["value"])
            if record.get("value") is not None
            else None,
            threshold=TypedValue.model_validate(record["threshold"])
            if record.get("threshold") is not None
            else None,
            unit=Unit(record.get("unit", Unit.NONE.value)),
            frame_id=optional_int(record.get("frame_id")) or anchor.anchor_frame_id,
            window=record.get("window"),
            source_evidence={
                **source_evidence,
                **{
                    key: value
                    for key, value in dict(record.get("source_evidence") or {}).items()
                    if value is not None
                },
            },
        )
    return None


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
    return {
        "entry_status": "FAIL",
        "entry": None,
        "entry_mode": "NOT_ENTERED",
        "time_to_entry_seconds": None,
        "observed_window_start_frame_id": start_frame_id,
        "observed_window_end_frame_id": observed_end_frame_id,
        "unknown_reason": None,
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
    execution = TacticalQueryExecutor(
        canonical_root=canonical_root,
        raw_root=raw_root,
        compatibility_profile=LEGACY_M1_PARITY_PROFILE,
    ).execute(bound)
    return bound, execution


def execute_plan_from_path(
    plan_path: Path,
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    raw_root: Path = DEFAULT_RAW_ROOT,
) -> tuple[BoundQueryPlan, QueryExecution]:
    bound = bind_document_from_path(plan_path)
    execution = TacticalQueryExecutor(
        canonical_root=canonical_root,
        raw_root=raw_root,
    ).execute(bound)
    return bound, execution


def execute_legacy_m1_plan_from_path(
    plan_path: Path,
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    raw_root: Path = DEFAULT_RAW_ROOT,
) -> tuple[BoundQueryPlan, QueryExecution]:
    bound = bind_document_from_path(plan_path)
    execution = TacticalQueryExecutor(
        canonical_root=canonical_root,
        raw_root=raw_root,
        compatibility_profile=LEGACY_M1_PARITY_PROFILE,
    ).execute(bound)
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


def boolean_persistence_evidence(
    values: pd.Series,
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

    for frame_id, value in values.items():
        passes = value is True
        if passes:
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
