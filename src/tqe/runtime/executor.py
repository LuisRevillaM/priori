"""M1.1 deterministic query runtime.

Gate B executes the approved M1 primitive chain from a bound plan. The executor
is deliberately keyed by primitive/operator catalog entries, not recipe IDs.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import sys
from collections.abc import MutableMapping
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
from tqe.runtime.capabilities import (
    build_predicate_registry,
    build_primitive_registry,
    build_relation_registry,
)
from tqe.runtime.controlled_pass import (
    align_event_to_frame,
)
from tqe.runtime.lane_occupancy import LaneOccupancyConfig, evaluate_lane_occupancy
from tqe.runtime.local_number_relation import (
    LocalNumberConfig,
    evaluate_local_number_relation,
)
from tqe.runtime.one_touch import (
    EVENT_COLUMNS,
    evaluate_pass_chain,
)
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
from tqe.runtime.pass_bypass import (
    attack_x_sign_for,
)
from tqe.runtime.values import FrameSignal, RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw
from tqe.runtime.envelope import conformance_enabled, shadow_check_legacy_outputs

PERIODS = ("firstHalf", "secondHalf")
BALL_ENTITY_ID = "DFL-OBJ-0000XT"
BALL_TEAM_ID = "BALL"
FRAME_RATE_HZ = 25
PITCH_HALF_WIDTH_M = 34.0
PITCH_HALF_LENGTH_M = 52.5

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
    lookup_cache: dict[tuple[Any, ...], Any] = field(default_factory=dict)
    node_output_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    node_cache_summary: Counter[str] = field(default_factory=Counter)
    progress_events: list[dict[str, Any]] = field(default_factory=list)


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


class UndeclaredNodeParameterError(RuntimeError):
    """Raised when an implementation reads a parameter absent from the bound node."""


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
        enable_node_cache: bool | None = None,
        shared_node_output_cache: MutableMapping[str, dict[str, Any]] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        progress_log: bool | None = None,
    ) -> None:
        self.canonical_root = canonical_root
        self.raw_root = raw_root
        if compatibility_profile not in {GENERIC_EXECUTION_PROFILE, LEGACY_M1_PARITY_PROFILE}:
            raise RuntimeError(f"Unsupported compatibility profile {compatibility_profile}")
        self.compatibility_profile = compatibility_profile
        self.enable_node_cache = (
            os.environ.get("TQE_DISABLE_NODE_CACHE") != "1"
            if enable_node_cache is None
            else enable_node_cache
        )
        self.shared_node_output_cache = shared_node_output_cache
        self.progress_callback = progress_callback
        self.progress_log = (
            os.environ.get("TQE_PROGRESS_LOG") == "1"
            if progress_log is None
            else progress_log
        )
        registry_namespace = globals()
        self.primitives: dict[str, PrimitiveImplementation] = build_primitive_registry(registry_namespace)
        self.relations: dict[str, RelationImplementation] = build_relation_registry(registry_namespace)
        self.predicates: dict[str, PredicateImplementation] = build_predicate_registry(registry_namespace)

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
        progress_events: list[dict[str, Any]] = []
        node_cache_summary: Counter[str] = Counter()

        for match_id in bound_plan.match_ids:
            (
                match_results,
                match_traces,
                match_runtime_value_count,
                match_progress_events,
                match_node_cache_summary,
            ) = self._execute_match(
                bound_plan=bound_plan,
                match_id=match_id,
                params=params,
                compatibility_profile=self.compatibility_profile,
            )
            results.extend(match_results)
            trace_records.extend(match_traces)
            runtime_value_count += match_runtime_value_count
            progress_events.extend(match_progress_events)
            node_cache_summary.update(match_node_cache_summary)

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
                "node_cache": {
                    "enabled": self.enable_node_cache,
                    "hits": int(node_cache_summary.get("hit", 0)),
                    "local_hits": int(node_cache_summary.get("local_hit", 0)),
                    "shared_hits": int(node_cache_summary.get("shared_hit", 0)),
                    "misses": int(node_cache_summary.get("miss", 0)),
                    "disabled": int(node_cache_summary.get("disabled", 0)),
                    "bypassed": int(node_cache_summary.get("bypassed", 0)),
                },
                "progress_event_count": len(progress_events),
                "progress_events": progress_events,
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
    ) -> tuple[list[dict[str, Any]], list[PredicateTrace], int, list[dict[str, Any]], Counter[str]]:
        accepted: list[dict[str, Any]] = []
        traces: list[PredicateTrace] = []
        runtime_value_count = 0
        progress_events: list[dict[str, Any]] = []
        node_cache_summary: Counter[str] = Counter()
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
            progress_events.extend(state.progress_events)
            node_cache_summary.update(state.node_cache_summary)
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
        return accepted, traces, runtime_value_count, progress_events, node_cache_summary

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
        self._record_progress(
            state,
            {
                "event": "period_start",
                "match_id": match_id,
                "period": period,
                "node_count": len(bound_plan.nodes),
            },
        )
        for index, node in enumerate(bound_plan.nodes, start=1):
            self._execute_node(
                state=state,
                node=node,
                compatibility_profile=profile,
                node_index=index,
                node_count=len(bound_plan.nodes),
            )
            enforce_runtime_complexity_limits(
                state=state,
                node=node,
                bound_plan=bound_plan,
            )
        self._record_progress(
            state,
            {
                "event": "period_complete",
                "match_id": match_id,
                "period": period,
                "node_count": len(bound_plan.nodes),
                "runtime_node_count": len(state.runtime_values),
            },
        )
        return state

    def _execute_node(
        self,
        *,
        state: PeriodState,
        node: BoundPlanNode,
        compatibility_profile: str | None = None,
        node_index: int | None = None,
        node_count: int | None = None,
    ) -> NodeExecutionResult:
        profile = compatibility_profile or self.compatibility_profile
        inputs = resolved_node_inputs(state, node)
        parameters = resolved_node_parameters(node)
        progress_base = {
            "match_id": state.match_id,
            "period": state.period,
            "node_id": node.node_id,
            "node_kind": node.kind.value,
            "node_index": node_index,
            "node_count": node_count,
        }
        if isinstance(node, BoundCatalogNode):
            progress_base["catalog_ref"] = node.catalog_ref
            progress_base["version"] = node.version
        elif isinstance(node, BoundPredicateNode):
            progress_base["operator"] = node.operator.name
        self._record_progress(state, {"event": "node_start", **progress_base})

        cache_status = "bypassed"
        if isinstance(node, BoundCatalogNode):
            if node.kind == NodeKind.RELATION:
                implementation = self.relations.get(node.catalog_ref)
                if implementation is None:
                    raise RuntimeError(f"No relation implementation for {node.catalog_ref}")
            else:
                implementation = self.primitives.get(node.catalog_ref)
            if implementation is None:
                raise RuntimeError(f"No primitive implementation for {node.catalog_ref}")
            cache_key = catalog_node_cache_key(node)
            if self.enable_node_cache and profile == GENERIC_EXECUTION_PROFILE:
                if cache_key in state.node_output_cache:
                    state.signals[node.node_id] = copy.deepcopy(state.node_output_cache[cache_key])
                    cache_status = "hit"
                    state.node_cache_summary["hit"] += 1
                    state.node_cache_summary["local_hit"] += 1
                elif self.shared_node_output_cache is not None and (
                    shared_cache_key := shared_catalog_node_cache_key(state, node, cache_key)
                ) in self.shared_node_output_cache:
                    state.signals[node.node_id] = copy.deepcopy(self.shared_node_output_cache[shared_cache_key])
                    state.node_output_cache[cache_key] = copy.deepcopy(state.signals[node.node_id])
                    cache_status = "shared_hit"
                    state.node_cache_summary["hit"] += 1
                    state.node_cache_summary["shared_hit"] += 1
                else:
                    implementation(state, node)
                    state.node_output_cache[cache_key] = copy.deepcopy(state.signals[node.node_id])
                    if self.shared_node_output_cache is not None:
                        shared_cache_key = shared_catalog_node_cache_key(state, node, cache_key)
                        self.shared_node_output_cache[shared_cache_key] = copy.deepcopy(state.signals[node.node_id])
                    cache_status = "miss"
                    state.node_cache_summary["miss"] += 1
            else:
                implementation(state, node)
                cache_status = "disabled" if profile == GENERIC_EXECUTION_PROFILE else "bypassed"
                state.node_cache_summary[cache_status] += 1
        elif isinstance(node, BoundPredicateNode):
            implementation = self.predicates.get(node.operator.name)
            if implementation is None:
                raise RuntimeError(f"No predicate implementation for {node.operator.name}")
            if profile == LEGACY_M1_PARITY_PROFILE and node.operator.name == "persists_for" and legacy_m1_record_persists_for_adapter(
                state=state,
                node=node,
            ):
                runtime_values = record_runtime_values(state, node)
                self._record_progress(
                    state,
                    {
                        "event": "node_complete",
                        **progress_base,
                        "cache_status": "bypassed",
                        "output_names": sorted(runtime_values),
                    },
                )
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
                self._record_progress(
                    state,
                    {
                        "event": "node_complete",
                        **progress_base,
                        "cache_status": "bypassed",
                        "output_names": sorted(runtime_values),
                    },
                )
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
        if isinstance(node, BoundCatalogNode) and conformance_enabled():
            shadow_check_legacy_outputs(
                node=node,
                raw_outputs=state.signals.get(node.node_id, {}),
                runtime_values=runtime_values,
            )
        self._record_progress(
            state,
            {
                "event": "node_complete",
                **progress_base,
                "cache_status": cache_status,
                "output_names": sorted(runtime_values),
            },
        )
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

    def _record_progress(self, state: PeriodState, event: dict[str, Any]) -> None:
        sanitized = {key: value for key, value in event.items() if value is not None}
        state.progress_events.append(sanitized)
        if self.progress_callback is not None:
            self.progress_callback(dict(sanitized))
        if self.progress_log:
            print(
                json.dumps(sanitized, sort_keys=True, separators=(",", ":")),
                file=sys.stderr,
                flush=True,
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


def catalog_node_cache_key(node: BoundCatalogNode) -> str:
    payload = node.model_dump(mode="json", exclude={"node_id"})
    return stable_hash(
        {
            "kind": node.kind.value,
            "catalog_ref": node.catalog_ref,
            "version": node.version,
            "inputs": payload.get("inputs", {}),
            "input_types": payload.get("input_types", {}),
            "outputs": payload.get("outputs", []),
            "resolved_parameters": payload.get("resolved_parameters", {}),
        }
    )


def shared_catalog_node_cache_key(state: PeriodState, node: BoundCatalogNode, node_cache_key: str) -> str:
    return stable_hash(
        {
            "schema_version": "shared_catalog_node_output_cache.v0",
            "canonical_root": str(state.canonical_root.resolve()),
            "raw_tracking": str(state.raw_tracking.resolve()),
            "match_id": state.match_id,
            "period": state.period,
            "perspective_team_role": state.perspective_team_role,
            "defending_team_role": state.defending_team_role,
            "runtime_parameters": state.params.values,
            "catalog_ref": node.catalog_ref,
            "catalog_node_cache_key": node_cache_key,
        }
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


def comparison_operator_truth(operator_name: str, threshold: float) -> Callable[[float], bool]:
    """Return the truth function for a live numeric comparison operator.

    Used for both the per-record pass statuses and the persisted
    ``truth_series`` evidence so the two can never disagree on the operator.
    """

    if operator_name == "gt":
        return lambda value: bool(value > threshold)
    if operator_name == "gte":
        return lambda value: bool(value >= threshold)
    if operator_name == "lte":
        return lambda value: bool(value <= threshold)
    raise RuntimeError(f"unsupported comparison operator {operator_name}")


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
        comparator = comparison_operator_truth(node.operator.name, threshold)
        passed = [None if value is None else comparator(value) for value in values]
        output: dict[str, Any] = {
            "predicate": predicate_frame_signal_from_source(runtime_value, passed, node)
        }
        records = runtime_records(runtime_value)
        if records and len(records) == len(passed):
            for record, status, value in zip(records, passed, values, strict=True):
                measure_series = record.get("measure_series")
                if isinstance(measure_series, pd.Series):
                    record["truth_series"] = measure_series.apply(
                        lambda item: None if is_nan_number(item) else comparator(float(item))
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
        previous_role = str(state.possession_role[idx - 1])
        new_role = str(state.possession_role[idx])
        if previous_role != previous_role_required or new_role != new_role_required:
            continue
        frame_id = int(state.frame_ids[idx])
        previous_frame_id = int(state.frame_ids[idx - 1])
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
    return base("FAIL", "open_space_threshold_not_met", candidates=candidates)


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


def primitive_action_chain(state: PeriodState, node: BoundCatalogNode) -> None:
    action_value = catalog_input_value(state, node, "actions")
    actions = runtime_records(action_value)
    max_gap_seconds = node_parameter_number(node, "maximum_action_gap_seconds")
    chain_length = int(round(node_parameter_number(node, "chain_length")))
    if chain_length != 2:
        raise RuntimeError("action_chain v0.1 supports chain_length=2")
    records: list[dict[str, Any]] = []
    ordered = sorted(
        [record for record in actions if isinstance(record, dict)],
        key=lambda item: (
            float(item.get("event_gameclock_seconds") or -1),
            int(item.get("event_row_index") or -1),
        ),
    )
    for first, second in zip(ordered, ordered[1:], strict=False):
        if first.get("team_role") != second.get("team_role"):
            continue
        first_time = first.get("event_gameclock_seconds")
        second_time = second.get("event_gameclock_seconds")
        if first_time is None or second_time is None:
            continue
        gap_seconds = float(second_time) - float(first_time)
        if gap_seconds < 0:
            continue
        status = "PASS" if gap_seconds <= max_gap_seconds else "FAIL"
        reason = "actions_linked_in_order" if status == "PASS" else "action_gap_exceeded"
        anchor_frame_id = optional_int(second.get("anchor_frame_id"))
        start_frame_id = optional_int(first.get("anchor_frame_id"))
        if anchor_frame_id is None or start_frame_id is None:
            continue
        entity_refs = list(
            dict.fromkeys(
                [
                    *[str(item) for item in first.get("entity_refs") or []],
                    *[str(item) for item in second.get("entity_refs") or []],
                ]
            )
        )
        anchor_id = anchor_record_id(
            match_id=state.match_id,
            period=state.period,
            anchor_frame_id=anchor_frame_id,
            start_frame_id=start_frame_id,
            end_frame_id=anchor_frame_id,
            entity_refs=entity_refs,
        )
        records.append(
            {
                "anchor_id": anchor_id,
                "match_id": state.match_id,
                "period": state.period,
                "anchor_frame_id": anchor_frame_id,
                "start_frame_id": start_frame_id,
                "end_frame_id": anchor_frame_id,
                "entity_refs": entity_refs,
                "action_chain_status": status,
                "action_chain_reason": reason,
                "chain_length": chain_length,
                "maximum_action_gap_seconds": max_gap_seconds,
                "action_gap_seconds": gap_seconds,
                "first_action_anchor_id": first.get("anchor_id"),
                "second_action_anchor_id": second.get("anchor_id"),
                "first_action_row_index": first.get("event_row_index"),
                "second_action_row_index": second.get("event_row_index"),
                "team_role": first.get("team_role"),
            }
        )
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "action_chain_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if record["action_chain_status"] == "UNKNOWN" else record["action_chain_status"]
                for record in records
            ],
            unknown_mask=[record["action_chain_status"] == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "action_chain_status").entity_scope,
        ),
        "action_chain_status_records": records,
    }


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


def primitive_switch_of_play(state: PeriodState, node: BoundCatalogNode) -> None:
    anchor_value = catalog_input_value(state, node, "anchors")
    anchors = anchor_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires anchor records")
    minimum_lateral_displacement_m = node_parameter_number(node, "minimum_lateral_displacement_m")
    minimum_start_lateral_m = node_parameter_number(node, "minimum_start_lateral_m")
    minimum_end_lateral_m = node_parameter_number(node, "minimum_end_lateral_m")
    maximum_duration_seconds = node_parameter_number(node, "maximum_duration_seconds")
    records = [
        switch_of_play_anchor_record(
            state=state,
            anchor=anchor,
            minimum_lateral_displacement_m=minimum_lateral_displacement_m,
            minimum_start_lateral_m=minimum_start_lateral_m,
            minimum_end_lateral_m=minimum_end_lateral_m,
            maximum_duration_seconds=maximum_duration_seconds,
        )
        for anchor in anchors
        if isinstance(anchor, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["switch_status"]) == "UNKNOWN" else str(record["switch_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "switch_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "switch_status").entity_scope,
        ),
        "switch_status_records": records,
    }


def switch_of_play_anchor_record(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    minimum_lateral_displacement_m: float,
    minimum_start_lateral_m: float,
    minimum_end_lateral_m: float,
    maximum_duration_seconds: float,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(anchor.get("anchor_frame_id"))
    release_frame_id = optional_int(anchor.get("physical_release_frame_id"))
    reception_frame_id = optional_int(anchor.get("controlled_reception_frame_id"))
    if anchor_frame_id is None:
        return None
    release_point = point_from_record(anchor.get("release_ball_point"))
    reception_point = point_from_record(anchor.get("reception_ball_point"))
    if release_point is None and release_frame_id is not None:
        release_point = tuple_point_to_record(ball_point_at_frame(state, release_frame_id))
    if reception_point is None and reception_frame_id is not None:
        reception_point = tuple_point_to_record(ball_point_at_frame(state, reception_frame_id))
    duration_seconds = (
        None
        if release_frame_id is None or reception_frame_id is None
        else max(0.0, (int(reception_frame_id) - int(release_frame_id)) / FRAME_RATE_HZ)
    )
    status = "UNKNOWN"
    reason = "switch_endpoint_missing"
    release_side = None
    reception_side = None
    lateral_displacement_m = None
    if release_point is not None and reception_point is not None:
        release_y = float(release_point["y_m"])
        reception_y = float(reception_point["y_m"])
        release_side = lateral_side(release_y)
        reception_side = lateral_side(reception_y)
        lateral_displacement_m = abs(reception_y - release_y)
        if release_side == "CENTER" or reception_side == "CENTER":
            status = "FAIL"
            reason = "endpoint_not_wide_enough"
        elif release_side == reception_side:
            status = "FAIL"
            reason = "same_lateral_side"
        elif lateral_displacement_m < minimum_lateral_displacement_m:
            status = "FAIL"
            reason = "lateral_displacement_below_threshold"
        elif abs(release_y) < minimum_start_lateral_m or abs(reception_y) < minimum_end_lateral_m:
            status = "FAIL"
            reason = "endpoint_lateral_depth_below_threshold"
        elif duration_seconds is not None and duration_seconds > maximum_duration_seconds:
            status = "FAIL"
            reason = "switch_duration_exceeded"
        else:
            status = "PASS"
            reason = "opposite_side_ball_transfer_observed"
    return {
        **anchor,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(anchor.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": optional_int(anchor.get("start_frame_id")) or release_frame_id or anchor_frame_id,
        "end_frame_id": optional_int(anchor.get("end_frame_id")) or reception_frame_id or anchor_frame_id,
        "entity_refs": list(anchor.get("entity_refs") or []),
        "switch_status": status,
        "switch_reason": reason,
        "release_frame_id": release_frame_id,
        "reception_frame_id": reception_frame_id,
        "release_ball_point": release_point,
        "reception_ball_point": reception_point,
        "release_lateral_side": release_side,
        "reception_lateral_side": reception_side,
        "lateral_displacement_m": None if lateral_displacement_m is None else round(float(lateral_displacement_m), 3),
        "switch_duration_seconds": None if duration_seconds is None else round(float(duration_seconds), 3),
        "minimum_lateral_displacement_m": minimum_lateral_displacement_m,
        "minimum_start_lateral_m": minimum_start_lateral_m,
        "minimum_end_lateral_m": minimum_end_lateral_m,
        "maximum_duration_seconds": maximum_duration_seconds,
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



def time_to_arrival_candidates(
    *,
    state: PeriodState,
    anchor: dict[str, Any],
    frame_id: int,
    candidate_scope: str,
) -> tuple[list[dict[str, Any]], set[str]]:
    if candidate_scope == "defending_outfield":
        team_role = state.defending_team_role
        known_ids = outfield_player_ids(state.canonical_root, state.match_id, team_role)
        return player_records_at_frame_for_team(state, frame_id, team_role), known_ids
    if candidate_scope == "perspective_outfield":
        team_role = state.perspective_team_role
        known_ids = outfield_player_ids(state.canonical_root, state.match_id, team_role)
        return player_records_at_frame_for_team(state, frame_id, team_role), known_ids
    if candidate_scope == "all_outfield":
        perspective = outfield_player_ids(state.canonical_root, state.match_id, state.perspective_team_role)
        defending = outfield_player_ids(state.canonical_root, state.match_id, state.defending_team_role)
        known_ids = perspective | defending
        records = [
            record
            for record in player_records_at_frame(state, frame_id).values()
            if str(record.get("player_id")) in known_ids
        ]
        return records, known_ids
    if candidate_scope in {"opposition_outfield_to_anchor_team", "same_team_outfield_as_anchor"}:
        anchor_team_role = str(anchor.get("team_role") or "")
        if anchor_team_role not in {"home", "away"}:
            return [], set()
        if candidate_scope == "same_team_outfield_as_anchor":
            team_role = anchor_team_role
        else:
            team_role = "away" if anchor_team_role == "home" else "home"
        known_ids = outfield_player_ids(state.canonical_root, state.match_id, team_role)
        return player_records_at_frame_for_team(state, frame_id, team_role), known_ids
    raise RuntimeError(f"Unsupported time_to_arrival candidate_scope: {candidate_scope}")
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


def primitive_carry_episode(state: PeriodState, node: BoundCatalogNode) -> None:
    anchors_value = catalog_input_value(state, node, "controlled_pass_anchors")
    anchors = anchors_value.value
    if not isinstance(anchors, list):
        raise RuntimeError(f"{node.node_id} requires controlled_pass anchor records")
    pass_records = [
        record
        for record in anchors
        if isinstance(record, dict)
        and str(record.get("controlled_pass_status")) == "PASS"
        and optional_int(record.get("controlled_reception_frame_id")) is not None
        and optional_int(record.get("physical_release_frame_id")) is not None
    ]
    pass_records.sort(
        key=lambda record: (
            int(optional_int(record.get("physical_release_frame_id")) or 0),
            int(record.get("event_row_index") or 0),
            str(record.get("pass_episode_id") or ""),
        )
    )
    orientation = parquet_rows(state.canonical_root / "orientation.parquet")
    records = [
        carry_episode_anchor_record(
            state=state,
            start_pass=start_pass,
            pass_records=pass_records,
            attack_x_sign=attack_x_sign_for(
                orientation,
                state.match_id,
                state.period,
                str(start_pass.get("team_role") or state.perspective_team_role),
            ),
            maximum_carry_seconds=node_parameter_number(node, "maximum_carry_seconds"),
            minimum_displacement_m=node_parameter_number(node, "minimum_displacement_m"),
            control_distance_m=node_parameter_number(node, "control_distance_m"),
            nearest_teammate_margin_m=node_parameter_number(node, "nearest_teammate_margin_m"),
            maximum_ball_player_speed_delta_mps=node_parameter_number(
                node,
                "maximum_ball_player_speed_delta_mps"
            ),
            minimum_controlled_frame_ratio=node_parameter_number(node, "minimum_controlled_frame_ratio"),
            minimum_comoving_frame_ratio=node_parameter_number(node, "minimum_comoving_frame_ratio"),
            maximum_missing_frame_ratio=node_parameter_number(node, "maximum_missing_frame_ratio"),
        )
        for start_pass in pass_records
    ]
    records = [record for record in records if record is not None]
    episodes = [record for record in records if str(record.get("carry_status")) == "PASS"]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    status_values = [
        None if str(record["carry_status"]) == "UNKNOWN" else str(record["carry_status"])
        for record in records
    ]
    state.signals[node.node_id] = {
        "episodes": episodes,
        "episodes_records": episodes,
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "carry_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "carry_status").entity_scope,
        ),
        "carry_status_records": records,
        "displacement_m": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("displacement_m") for record in records],
            unknown_mask=[record.get("displacement_m") is None for record in records],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "displacement_m").entity_scope,
        ),
        "displacement_m_records": records,
        "forward_progression_m": FrameSignal(
            frame_ids=frame_ids,
            values=[record.get("carry_forward_progression_m") for record in records],
            unknown_mask=[record.get("carry_forward_progression_m") is None for record in records],
            unit=Unit.METRE,
            entity_scope=catalog_output(node, "forward_progression_m").entity_scope,
        ),
        "forward_progression_m_records": records,
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


def carry_episode_anchor_record(
    *,
    state: PeriodState,
    start_pass: dict[str, Any],
    pass_records: list[dict[str, Any]],
    attack_x_sign: int | None,
    maximum_carry_seconds: float,
    minimum_displacement_m: float,
    control_distance_m: float,
    nearest_teammate_margin_m: float,
    maximum_ball_player_speed_delta_mps: float,
    minimum_controlled_frame_ratio: float,
    minimum_comoving_frame_ratio: float,
    maximum_missing_frame_ratio: float,
) -> dict[str, Any] | None:
    start_frame_id = optional_int(start_pass.get("controlled_reception_frame_id"))
    carrier_id = str(start_pass.get("receiver_id") or "")
    team_role = str(start_pass.get("team_role") or "")
    if start_frame_id is None or not carrier_id or not team_role:
        return None
    maximum_end_frame_id = int(start_frame_id + math.ceil(maximum_carry_seconds * FRAME_RATE_HZ - 1e-9))
    terminal = terminal_pass_after_reception(
        start_pass=start_pass,
        pass_records=pass_records,
        carrier_id=carrier_id,
        team_role=team_role,
        start_frame_id=start_frame_id,
        maximum_end_frame_id=maximum_end_frame_id,
    )
    terminal_record = terminal.get("record")
    terminal_release_frame_id = optional_int(terminal_record.get("physical_release_frame_id")) if isinstance(terminal_record, dict) else None
    end_frame_id = terminal_release_frame_id or min(maximum_end_frame_id, int(state.frame_ids[-1]))
    continuity = carry_possession_continuity(
        state=state,
        team_role=team_role,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
    )
    control = carry_control_continuity(
        state=state,
        carrier_id=carrier_id,
        team_role=team_role,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        control_distance_m=control_distance_m,
        nearest_teammate_margin_m=nearest_teammate_margin_m,
        maximum_ball_player_speed_delta_mps=maximum_ball_player_speed_delta_mps,
        minimum_controlled_frame_ratio=minimum_controlled_frame_ratio,
        minimum_comoving_frame_ratio=minimum_comoving_frame_ratio,
        maximum_missing_frame_ratio=maximum_missing_frame_ratio,
    )
    start_point = point_from_record(start_pass.get("reception_receiver_point")) or tuple_point_to_record(
        cached_player_position_at_frame(state, start_frame_id, carrier_id)
    )
    end_point = (
        point_from_record(terminal_record.get("release_passer_point"))
        if isinstance(terminal_record, dict)
        else None
    ) or tuple_point_to_record(cached_player_position_at_frame(state, end_frame_id, carrier_id))
    displacement_m = point_distance(start_point, end_point)
    forward_progression_m = (
        None
        if start_point is None or end_point is None or attack_x_sign not in {-1, 1}
        else round((float(end_point["x_m"]) - float(start_point["x_m"])) * int(attack_x_sign), 3)
    )
    if terminal.get("status") != "PASS":
        status = "FAIL"
        reason = str(terminal.get("reason") or "terminal_pass_not_found")
    elif continuity["status"] != "PASS":
        status = str(continuity["status"])
        reason = str(continuity["reason"])
    elif control["status"] != "PASS":
        status = str(control["status"])
        reason = str(control["reason"])
    elif attack_x_sign not in {-1, 1}:
        status = "UNKNOWN"
        reason = "attacking_direction_missing"
    elif displacement_m is None:
        status = "UNKNOWN"
        reason = "carry_endpoint_missing"
    elif displacement_m < minimum_displacement_m:
        status = "FAIL"
        reason = "minimum_displacement_not_met"
    else:
        status = "PASS"
        reason = "carry_observed"
    anchor_id = anchor_record_id(
        match_id=state.match_id,
        period=state.period,
        anchor_frame_id=start_frame_id,
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        entity_refs=[carrier_id],
    )
    return {
        "anchor_id": anchor_id,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_frame_id": start_frame_id,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "entity_refs": [carrier_id],
        "carry_episode_id": f"carry:{state.match_id}:{state.period}:{carrier_id}:{start_frame_id}:{end_frame_id}",
        "source_reception_pass_id": start_pass.get("pass_episode_id"),
        "terminal_pass_id": terminal_record.get("pass_episode_id") if isinstance(terminal_record, dict) else None,
        "carrier_id": carrier_id,
        "team_role": team_role,
        "carry_status": status,
        "carry_reason": reason,
        "control_model": "controlled_pass_distance_plus_comovement_v0_1",
        "control_bias": "conservative_clear_control_only",
        "control_distance_m": round(float(control_distance_m), 3),
        "nearest_teammate_margin_m": round(float(nearest_teammate_margin_m), 3),
        "maximum_ball_player_speed_delta_mps": round(float(maximum_ball_player_speed_delta_mps), 3),
        "minimum_controlled_frame_ratio": round(float(minimum_controlled_frame_ratio), 3),
        "minimum_comoving_frame_ratio": round(float(minimum_comoving_frame_ratio), 3),
        "maximum_missing_frame_ratio": round(float(maximum_missing_frame_ratio), 3),
        "minimum_displacement_m": round(float(minimum_displacement_m), 3),
        "maximum_carry_seconds": round(float(maximum_carry_seconds), 3),
        "carry_start_frame_id": start_frame_id,
        "carry_end_frame_id": end_frame_id,
        "start_match_time_ms": frame_match_time_ms(state, start_frame_id),
        "end_match_time_ms": frame_match_time_ms(state, end_frame_id),
        "carry_duration_seconds": round(max(0.0, (end_frame_id - start_frame_id) / FRAME_RATE_HZ), 3),
        "start_point": start_point,
        "end_point": end_point,
        "displacement_m": displacement_m,
        "carry_forward_progression_m": forward_progression_m,
        "attacking_direction": attack_x_sign,
        "possession_continuity_status": continuity["status"],
        "possession_continuity_reason": continuity["reason"],
        "control_continuity_status": control["status"],
        "control_continuity_reason": control["reason"],
        "controlled_frame_ratio": control["controlled_frame_ratio"],
        "comoving_frame_ratio": control["comoving_frame_ratio"],
        "missing_frame_ratio": control["missing_frame_ratio"],
        "observed_frame_count": control["observed_frame_count"],
        "controlled_frame_count": control["controlled_frame_count"],
        "comoving_frame_count": control["comoving_frame_count"],
        "velocity_observed_frame_count": control["velocity_observed_frame_count"],
        "missing_frame_count": control["missing_frame_count"],
        "terminal_detection_status": terminal.get("status"),
        "terminal_detection_reason": terminal.get("reason"),
        "terminal_passer_id": terminal_record.get("passer_id") if isinstance(terminal_record, dict) else None,
        "terminal_receiver_id": terminal_record.get("receiver_id") if isinstance(terminal_record, dict) else None,
        "terminal_release_frame_id": terminal_release_frame_id,
        "terminal_reception_frame_id": optional_int(terminal_record.get("controlled_reception_frame_id"))
        if isinstance(terminal_record, dict)
        else None,
    }


def terminal_pass_after_reception(
    *,
    start_pass: dict[str, Any],
    pass_records: list[dict[str, Any]],
    carrier_id: str,
    team_role: str,
    start_frame_id: int,
    maximum_end_frame_id: int,
) -> dict[str, Any]:
    start_pass_id = str(start_pass.get("pass_episode_id") or "")
    for candidate in pass_records:
        candidate_id = str(candidate.get("pass_episode_id") or "")
        if candidate_id == start_pass_id:
            continue
        release_frame_id = optional_int(candidate.get("physical_release_frame_id"))
        if release_frame_id is None or release_frame_id <= start_frame_id:
            continue
        if release_frame_id > maximum_end_frame_id:
            break
        if str(candidate.get("passer_id") or "") != carrier_id or str(candidate.get("team_role") or "") != team_role:
            return {"status": "FAIL", "reason": "next_confirmed_pass_by_other_player", "record": candidate}
        return {"status": "PASS", "reason": "terminal_same_player_pass", "record": candidate}
    return {"status": "FAIL", "reason": "terminal_pass_not_found_within_window", "record": None}


def carry_possession_continuity(
    *,
    state: PeriodState,
    team_role: str,
    start_frame_id: int,
    end_frame_id: int,
) -> dict[str, str]:
    indexes = analysis_indexes_between(state, start_frame_id, end_frame_id)
    if not indexes:
        return {"status": "UNKNOWN", "reason": "frame_window_missing"}
    alive = state.ball_alive[indexes[0] : indexes[-1] + 1]
    roles = state.possession_role[indexes[0] : indexes[-1] + 1]
    if len(alive) == 0 or len(roles) == 0:
        return {"status": "UNKNOWN", "reason": "possession_window_missing"}
    if not bool(np.all(alive)):
        return {"status": "FAIL", "reason": "ball_not_alive_during_carry"}
    if not bool(np.all(roles == team_role)):
        return {"status": "FAIL", "reason": "possession_changed_during_carry"}
    return {"status": "PASS", "reason": "same_team_possession_continuity_observed"}


def carry_control_continuity(
    *,
    state: PeriodState,
    carrier_id: str,
    team_role: str,
    start_frame_id: int,
    end_frame_id: int,
    control_distance_m: float,
    nearest_teammate_margin_m: float,
    maximum_ball_player_speed_delta_mps: float,
    minimum_controlled_frame_ratio: float,
    minimum_comoving_frame_ratio: float,
    maximum_missing_frame_ratio: float,
) -> dict[str, Any]:
    indexes = analysis_indexes_between(state, start_frame_id, end_frame_id)
    if not indexes:
        return carry_control_summary("UNKNOWN", "frame_window_missing")
    frame_ids = [int(state.frame_ids[index]) for index in indexes]
    player_maps, ball_points = coordinate_maps_by_frame(state)
    missing = observed = controlled = velocity_observed = comoving = 0
    previous_ball: tuple[float, float] | None = None
    previous_player: tuple[float, float] | None = None
    for frame_id in frame_ids:
        ball = ball_points.get(frame_id)
        frame_players = player_maps.get(frame_id, {})
        record = frame_players.get(carrier_id)
        player = (
            None
            if record is None or record.get("x_m") is None or record.get("y_m") is None
            else (float(record["x_m"]), float(record["y_m"]))
        )
        if ball is None or player is None or record is None or str(record.get("team_role")) != team_role:
            missing += 1
            previous_ball = ball
            previous_player = player
            continue
        observed += 1
        distance_m = math.hypot(ball[0] - player[0], ball[1] - player[1])
        if distance_m <= control_distance_m and nearest_teammate_allows_carry_control(
            frame_players=frame_players,
            team_role=team_role,
            ball_point=ball,
            player_distance_m=distance_m,
            nearest_teammate_margin_m=nearest_teammate_margin_m,
        ):
            controlled += 1
        if previous_ball is not None and previous_player is not None:
            dt_seconds = 1.0 / FRAME_RATE_HZ
            ball_vx = (ball[0] - previous_ball[0]) / dt_seconds
            ball_vy = (ball[1] - previous_ball[1]) / dt_seconds
            player_vx = (player[0] - previous_player[0]) / dt_seconds
            player_vy = (player[1] - previous_player[1]) / dt_seconds
            velocity_observed += 1
            if math.hypot(ball_vx - player_vx, ball_vy - player_vy) <= maximum_ball_player_speed_delta_mps:
                comoving += 1
        previous_ball = ball
        previous_player = player
    total = len(frame_ids)
    if total == 0:
        return carry_control_summary("UNKNOWN", "frame_window_missing")
    missing_ratio = round(missing / total, 3)
    controlled_ratio = round(controlled / observed, 3) if observed else None
    comoving_ratio = round(comoving / velocity_observed, 3) if velocity_observed else None
    if missing_ratio > maximum_missing_frame_ratio:
        status, reason = "UNKNOWN", "tracking_missing_during_carry"
    elif not observed or controlled_ratio is None or comoving_ratio is None:
        status, reason = "UNKNOWN", "control_evidence_missing"
    elif controlled_ratio < minimum_controlled_frame_ratio:
        status, reason = "FAIL", "ball_not_continuously_under_control"
    elif comoving_ratio < minimum_comoving_frame_ratio:
        status, reason = "FAIL", "ball_not_comoving_with_carrier"
    else:
        status, reason = "PASS", "continuous_clear_control_observed"
    return carry_control_summary(
        status,
        reason,
        observed_frame_count=observed,
        controlled_frame_count=controlled,
        comoving_frame_count=comoving,
        velocity_observed_frame_count=velocity_observed,
        missing_frame_count=missing,
        total_frame_count=total,
        controlled_frame_ratio=controlled_ratio,
        comoving_frame_ratio=comoving_ratio,
        missing_frame_ratio=missing_ratio,
    )


def carry_control_summary(
    status: str,
    reason: str,
    *,
    observed_frame_count: int = 0,
    controlled_frame_count: int = 0,
    comoving_frame_count: int = 0,
    velocity_observed_frame_count: int = 0,
    missing_frame_count: int = 0,
    total_frame_count: int = 0,
    controlled_frame_ratio: float | None = None,
    comoving_frame_ratio: float | None = None,
    missing_frame_ratio: float | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "observed_frame_count": observed_frame_count,
        "controlled_frame_count": controlled_frame_count,
        "comoving_frame_count": comoving_frame_count,
        "velocity_observed_frame_count": velocity_observed_frame_count,
        "missing_frame_count": missing_frame_count,
        "total_frame_count": total_frame_count,
        "controlled_frame_ratio": controlled_frame_ratio,
        "comoving_frame_ratio": comoving_frame_ratio,
        "missing_frame_ratio": missing_frame_ratio,
    }


def nearest_teammate_allows_carry_control(
    *,
    frame_players: dict[str, dict[str, Any]],
    team_role: str,
    ball_point: tuple[float, float],
    player_distance_m: float,
    nearest_teammate_margin_m: float,
) -> bool:
    distances = [
        math.hypot(float(record["x_m"]) - ball_point[0], float(record["y_m"]) - ball_point[1])
        for record in frame_players.values()
        if str(record.get("team_role")) == team_role
        and record.get("x_m") is not None
        and record.get("y_m") is not None
    ]
    return bool(distances) and player_distance_m <= min(distances) + nearest_teammate_margin_m


def analysis_indexes_between(state: PeriodState, start_frame_id: int, end_frame_id: int) -> list[int]:
    if end_frame_id < start_frame_id:
        return []
    return [
        index
        for index, frame_id in enumerate(state.frame_ids)
        if int(start_frame_id) <= int(frame_id) <= int(end_frame_id)
    ]


def point_distance(a: dict[str, float] | None, b: dict[str, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return round(math.hypot(float(a["x_m"]) - float(b["x_m"]), float(a["y_m"]) - float(b["y_m"])), 3)


def ball_x_at_frame(positions: pd.DataFrame, frame_id: int) -> float | None:
    rows = positions[
        (positions["frame_id"] == frame_id)
        & (positions["entity_type"] == "ball")
    ]
    if rows.empty:
        return None
    value = rows.iloc[0]["x_m"]
    return None if pd.isna(value) else float(value)


def coordinate_maps_by_frame(
    state: PeriodState,
) -> tuple[dict[int, dict[str, dict[str, Any]]], dict[int, tuple[float, float]]]:
    key = ("coordinate_maps_by_frame",)
    if key not in state.lookup_cache:
        player_records: dict[int, dict[str, dict[str, Any]]] = {}
        ball_points: dict[int, tuple[float, float]] = {}
        for row in state.positions.itertuples(index=False):
            frame_id = int(row.frame_id)
            if str(row.entity_type) == "ball":
                if not pd.isna(row.x_m) and not pd.isna(row.y_m):
                    ball_points[frame_id] = (float(row.x_m), float(row.y_m))
                continue
            if str(row.entity_type) != "player":
                continue
            if pd.isna(row.x_m) or pd.isna(row.y_m):
                x_m = None
                y_m = None
            else:
                x_m = float(row.x_m)
                y_m = float(row.y_m)
            player_records.setdefault(frame_id, {})[str(row.entity_id)] = {
                "player_id": str(row.entity_id),
                "frame_id": frame_id,
                "team_id": str(row.team_id),
                "team_role": str(row.team_role),
                "x_m": x_m,
                "y_m": y_m,
            }
        state.lookup_cache[key] = (player_records, ball_points)
    return state.lookup_cache[key]


def positions_by_frame_index(state: PeriodState) -> pd.DataFrame:
    key = ("positions_by_frame_index",)
    if key not in state.lookup_cache:
        state.lookup_cache[key] = state.positions.set_index("frame_id", drop=False).sort_index()
    return state.lookup_cache[key]


def ball_point_at_frame(state: PeriodState, frame_id: int) -> tuple[float, float] | None:
    key = ("ball_point_at_frame", int(frame_id))
    if key not in state.lookup_cache:
        rows = rows_at_frame(state, frame_id)
        ball_rows = rows[rows["entity_type"] == "ball"]
        if ball_rows.empty:
            state.lookup_cache[key] = None
        else:
            row = ball_rows.iloc[0]
            state.lookup_cache[key] = (
                None
                if pd.isna(row.x_m) or pd.isna(row.y_m)
                else (float(row.x_m), float(row.y_m))
            )
    return state.lookup_cache[key]


def cached_ball_x_at_frame(state: PeriodState, frame_id: int) -> float | None:
    key = ("ball_x_at_frame", int(frame_id))
    if key not in state.lookup_cache:
        rows = rows_at_frame(state, frame_id)
        ball_rows = rows[rows["entity_type"] == "ball"]
        if ball_rows.empty:
            state.lookup_cache[key] = None
        else:
            value = ball_rows.iloc[0]["x_m"]
            state.lookup_cache[key] = None if pd.isna(value) else float(value)
    return state.lookup_cache[key]


def tracked_point_at_frame(state: PeriodState, frame_id: int, entity_id: str) -> tuple[float, float] | None:
    if not entity_id:
        return None
    if entity_id == BALL_ENTITY_ID or entity_id == "ball":
        return ball_point_at_frame(state, frame_id)
    record = player_records_at_frame(state, frame_id).get(str(entity_id))
    if record is None or record.get("x_m") is None or record.get("y_m") is None:
        return None
    return (float(record["x_m"]), float(record["y_m"]))


def rows_by_frame(state: PeriodState) -> dict[int, pd.DataFrame]:
    key = ("rows_by_frame",)
    if key not in state.lookup_cache:
        state.lookup_cache[key] = {
            int(frame_id): rows
            for frame_id, rows in state.positions.groupby("frame_id", sort=False)
        }
    return state.lookup_cache[key]


def rows_at_frame(state: PeriodState, frame_id: int) -> pd.DataFrame:
    key = ("rows_at_frame", int(frame_id))
    if key not in state.lookup_cache:
        indexed = positions_by_frame_index(state)
        try:
            rows = indexed.loc[int(frame_id)]
        except KeyError:
            rows = state.positions.iloc[0:0]
        if isinstance(rows, pd.Series):
            rows = rows.to_frame().T
        state.lookup_cache[key] = rows
    return state.lookup_cache[key]


def player_records_at_frame(state: PeriodState, frame_id: int) -> dict[str, dict[str, Any]]:
    key = ("player_records_at_frame", int(frame_id))
    if key not in state.lookup_cache:
        rows = rows_at_frame(state, frame_id)
        rows = rows[rows["entity_type"] == "player"]
        records: dict[str, dict[str, Any]] = {}
        for row in rows.itertuples(index=False):
            if pd.isna(row.x_m) or pd.isna(row.y_m):
                x_m = None
                y_m = None
            else:
                x_m = float(row.x_m)
                y_m = float(row.y_m)
            records[str(row.entity_id)] = {
                "player_id": str(row.entity_id),
                "frame_id": int(row.frame_id),
                "team_id": str(row.team_id),
                "team_role": str(row.team_role),
                "x_m": x_m,
                "y_m": y_m,
            }
        state.lookup_cache[key] = records
    return state.lookup_cache[key]


def player_records_at_frame_for_team(
    state: PeriodState,
    frame_id: int,
    team_role: str,
) -> list[dict[str, Any]]:
    key = ("player_records_at_frame_for_team", int(frame_id), team_role)
    if key not in state.lookup_cache:
        state.lookup_cache[key] = [
            record
            for record in player_records_at_frame(state, frame_id).values()
            if record["team_role"] == team_role
        ]
    return state.lookup_cache[key]


def defending_positions_at_frame(
    positions: pd.DataFrame,
    frame_id: int,
    team_role: str,
    outfield_ids: set[str],
) -> dict[str, tuple[float, float]]:
    rows = positions[
        (positions["frame_id"] == frame_id)
        & (positions["entity_type"] == "player")
        & (positions["team_role"] == team_role)
    ]
    if outfield_ids:
        rows = rows[rows["entity_id"].astype(str).isin(outfield_ids)]
    observed: dict[str, tuple[float, float]] = {}
    for row in rows.itertuples(index=False):
        if pd.isna(row.x_m) or pd.isna(row.y_m):
            continue
        observed[str(row.entity_id)] = (float(row.x_m), float(row.y_m))
    return observed


def cached_defending_positions_at_frame(
    state: PeriodState,
    frame_id: int,
    team_role: str,
    outfield_ids: set[str],
) -> dict[str, tuple[float, float]]:
    key = (
        "defending_positions_at_frame",
        int(frame_id),
        team_role,
        tuple(sorted(str(value) for value in outfield_ids)),
    )
    if key not in state.lookup_cache:
        observed: dict[str, tuple[float, float]] = {}
        allowed_ids = {str(value) for value in outfield_ids}
        for record in player_records_at_frame_for_team(state, frame_id, team_role):
            if allowed_ids and record["player_id"] not in allowed_ids:
                continue
            if record["x_m"] is None or record["y_m"] is None:
                continue
            observed[record["player_id"]] = (float(record["x_m"]), float(record["y_m"]))
        state.lookup_cache[key] = observed
    return state.lookup_cache[key]


def player_position_at_frame(
    positions: pd.DataFrame,
    frame_id: int,
    entity_id: str,
) -> tuple[float, float] | None:
    rows = positions[
        (positions["frame_id"] == frame_id)
        & (positions["entity_type"] == "player")
        & (positions["entity_id"].astype(str) == str(entity_id))
    ]
    if rows.empty:
        return None
    row = rows.iloc[0]
    if pd.isna(row.x_m) or pd.isna(row.y_m):
        return None
    return (float(row.x_m), float(row.y_m))


def cached_player_position_at_frame(
    state: PeriodState,
    frame_id: int,
    entity_id: str,
) -> tuple[float, float] | None:
    key = ("player_position_at_frame", int(frame_id), str(entity_id))
    if key not in state.lookup_cache:
        record = player_records_at_frame(state, frame_id).get(str(entity_id))
        state.lookup_cache[key] = (
            None
            if record is None or record["x_m"] is None or record["y_m"] is None
            else (float(record["x_m"]), float(record["y_m"]))
        )
    return state.lookup_cache[key]


def primitive_pass_chain_episode(state: PeriodState, node: BoundCatalogNode) -> None:
    relay_value = catalog_input_value(state, node, "relay_anchors")
    terminal_value = catalog_input_value(state, node, "terminal_controlled_pass_anchors")
    relay_records = relay_value.value
    terminal_records = terminal_value.value
    if not isinstance(relay_records, list) or not isinstance(terminal_records, list):
        raise RuntimeError(f"{node.node_id} requires relay and terminal controlled-pass records")
    terminal_by_pass_id = {
        str(record.get("pass_episode_id")): record
        for record in terminal_records
        if isinstance(record, dict) and record.get("pass_episode_id") is not None
    }
    records = [
        pass_chain_anchor_record(
            state=state,
            relay_record=relay_record,
            terminal_record=terminal_by_pass_id.get(str(relay_record.get("relay_pass_episode_id")))
            if isinstance(relay_record, dict)
            else None,
        )
        for relay_record in relay_records
        if isinstance(relay_record, dict)
    ]
    records = [record for record in records if record is not None]
    frame_ids = [int(record["anchor_frame_id"]) for record in records]
    state.signals[node.node_id] = {
        "anchor_evaluations": records,
        "anchor_evaluations_records": records,
        "pass_chain_status": FrameSignal(
            frame_ids=frame_ids,
            values=[
                None if str(record["pass_chain_status"]) == "UNKNOWN" else str(record["pass_chain_status"])
                for record in records
            ],
            unknown_mask=[str(record["pass_chain_status"]) == "UNKNOWN" for record in records],
            unit=Unit.NONE,
            entity_scope=catalog_output(node, "pass_chain_status").entity_scope,
        ),
        "pass_chain_status_records": records,
    }


def pass_chain_anchor_record(
    *,
    state: PeriodState,
    relay_record: dict[str, Any],
    terminal_record: dict[str, Any] | None,
) -> dict[str, Any] | None:
    anchor_frame_id = optional_int(relay_record.get("anchor_frame_id"))
    if anchor_frame_id is None:
        return None
    evaluation = evaluate_pass_chain(
        relay_evidence=relay_record,
        terminal_controlled_pass_evidence=terminal_record,
    )
    terminal_reception_frame_id = (
        optional_int(terminal_record.get("controlled_reception_frame_id"))
        if terminal_record is not None
        else None
    )
    return {
        **relay_record,
        "match_id": state.match_id,
        "period": state.period,
        "anchor_id": str(relay_record.get("anchor_id")),
        "anchor_frame_id": anchor_frame_id,
        "pass_chain_status": str(evaluation["pass_chain_status"]),
        "pass_chain_reason": evaluation["pass_chain_reason"],
        "terminal_pass_episode_id": relay_record.get("relay_pass_episode_id"),
        "terminal_receiver_id": None if terminal_record is None else terminal_record.get("receiver_id"),
        "terminal_controlled_reception_frame_id": terminal_reception_frame_id,
        "terminal_reception_match_time_ms": frame_match_time_ms(state, terminal_reception_frame_id),
        "terminal_forward_progression_m": None if terminal_record is None else terminal_record.get("forward_progression_m"),
        "terminal_controlled_pass_record_found": terminal_record is not None,
        "terminal_controlled_pass_status": None if terminal_record is None else terminal_record.get("controlled_pass_status"),
        "terminal_reception_ball_point": None if terminal_record is None else terminal_record.get("reception_ball_point"),
        "terminal_reception_receiver_point": None
        if terminal_record is None
        else terminal_record.get("reception_receiver_point"),
    }


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


def observed_outfield_positions_at_frame(
    positions: pd.DataFrame,
    frame_id: int,
    team_role: str,
    outfield_ids: set[str],
) -> list[dict[str, Any]]:
    if not outfield_ids:
        return []
    rows = positions[
        (positions["frame_id"] == frame_id)
        & (positions["entity_type"] == "player")
        & (positions["team_role"] == team_role)
    ]
    rows = rows[rows["entity_id"].astype(str).isin(outfield_ids)]
    result: list[dict[str, Any]] = []
    for row in rows.itertuples(index=False):
        result.append(
            {
                "player_id": str(row.entity_id),
                "frame_id": int(row.frame_id),
                "team_role": str(row.team_role),
                "x_m": None if pd.isna(row.x_m) else float(row.x_m),
                "y_m": None if pd.isna(row.y_m) else float(row.y_m),
            }
        )
    return result


def cached_observed_outfield_positions_at_frame(
    state: PeriodState,
    frame_id: int,
    team_role: str,
    outfield_ids: set[str],
) -> list[dict[str, Any]]:
    key = (
        "observed_outfield_positions_at_frame",
        int(frame_id),
        team_role,
        tuple(sorted(str(value) for value in outfield_ids)),
    )
    if key not in state.lookup_cache:
        allowed_ids = {str(value) for value in outfield_ids}
        state.lookup_cache[key] = [
            {
                "player_id": record["player_id"],
                "frame_id": record["frame_id"],
                "team_role": record["team_role"],
                "x_m": record["x_m"],
                "y_m": record["y_m"],
            }
            for record in player_records_at_frame_for_team(state, frame_id, team_role)
            if record["player_id"] in allowed_ids
        ]
    return state.lookup_cache[key]


def observed_outfield_positions_between_frames(
    positions: pd.DataFrame,
    *,
    start_frame_id: int,
    end_frame_id: int,
    team_role: str,
    outfield_ids: set[str],
    excluded_player_ids: set[str],
) -> list[dict[str, Any]]:
    if not outfield_ids:
        return []
    rows = positions[
        (positions["frame_id"] >= start_frame_id)
        & (positions["frame_id"] <= end_frame_id)
        & (positions["entity_type"] == "player")
        & (positions["team_role"] == team_role)
    ]
    rows = rows[rows["entity_id"].astype(str).isin(outfield_ids - excluded_player_ids)]
    result: list[dict[str, Any]] = []
    for row in rows.itertuples(index=False):
        result.append(
            {
                "player_id": str(row.entity_id),
                "frame_id": int(row.frame_id),
                "team_id": str(row.team_id),
                "team_role": str(row.team_role),
                "x_m": None if pd.isna(row.x_m) else float(row.x_m),
                "y_m": None if pd.isna(row.y_m) else float(row.y_m),
            }
        )
    return result


def observed_player_point_at_frame(
    positions: pd.DataFrame,
    *,
    frame_id: int,
    player_id: Any,
) -> dict[str, float] | None:
    if player_id is None:
        return None
    rows = positions[
        (positions["frame_id"] == frame_id)
        & (positions["entity_type"] == "player")
        & (positions["entity_id"].astype(str) == str(player_id))
    ]
    if rows.empty:
        return None
    row = rows.iloc[0]
    if pd.isna(row.x_m) or pd.isna(row.y_m):
        return None
    return point_from_xy(row.x_m, row.y_m)


def cached_observed_player_point_at_frame(
    state: PeriodState,
    *,
    frame_id: int,
    player_id: Any,
) -> dict[str, float] | None:
    key = ("observed_player_point_at_frame", int(frame_id), None if player_id is None else str(player_id))
    if key not in state.lookup_cache:
        record = None if player_id is None else player_records_at_frame(state, frame_id).get(str(player_id))
        state.lookup_cache[key] = (
            None
            if record is None or record["x_m"] is None or record["y_m"] is None
            else point_from_xy(record["x_m"], record["y_m"])
        )
    return state.lookup_cache[key]


def anchor_reference_point(anchor: dict[str, Any]) -> dict[str, float] | None:
    point = anchor.get("reception_receiver_point")
    if isinstance(point, dict) and point.get("x_m") is not None and point.get("y_m") is not None:
        return point_from_xy(point.get("x_m"), point.get("y_m"))
    point = anchor.get("reception_ball_point")
    if isinstance(point, dict) and point.get("x_m") is not None and point.get("y_m") is not None:
        return point_from_xy(point.get("x_m"), point.get("y_m"))
    x_value = anchor.get("receiver_x_m")
    if x_value is None:
        x_value = anchor.get("reception_receiver_x_m")
    y_value = anchor.get("receiver_y_m")
    if y_value is None:
        y_value = anchor.get("reception_receiver_y_m")
    return point_from_xy(x_value, y_value)


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


def catalog_output(node: BoundCatalogNode, name: str) -> Any:
    for output in node.outputs:
        if output.name == name:
            return output
    raise RuntimeError(f"{node.node_id} did not declare output {name}")


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


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(numeric) else numeric


def point_from_record(value: Any) -> dict[str, float] | None:
    if isinstance(value, dict):
        return point_from_xy(value.get("x_m"), value.get("y_m"))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return point_from_xy(value[0], value[1])
    return None


def tuple_point_to_record(value: tuple[float, float] | None) -> dict[str, float] | None:
    if value is None:
        return None
    return {"x_m": float(value[0]), "y_m": float(value[1])}


def lateral_side(y_m: float, *, center_tolerance_m: float = 1.0) -> str:
    if y_m > center_tolerance_m:
        return "RIGHT"
    if y_m < -center_tolerance_m:
        return "LEFT"
    return "CENTER"


def records_by_anchor_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        anchor_id = record.get("anchor_id")
        if anchor_id is None:
            continue
        indexed.setdefault(str(anchor_id), record)
    return indexed


def point_from_xy(x_value: Any, y_value: Any) -> dict[str, float] | None:
    try:
        if x_value is None or y_value is None or pd.isna(x_value) or pd.isna(y_value):
            return None
        return {"x_m": float(x_value), "y_m": float(y_value)}
    except (TypeError, ValueError):
        return None


def frame_match_time_ms(state: PeriodState, frame_id: int | None) -> int | None:
    if frame_id is None or len(state.frame_ids) == 0:
        return None
    first_frame_id = int(state.frame_ids[0])
    return int(round((int(frame_id) - first_frame_id) / FRAME_RATE_HZ * 1000))


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


def node_parameter_number(node: BoundCatalogNode, name: str) -> float:
    value = required_node_parameter(node, name)
    if value.payload_type != PayloadType.NUMBER:
        raise RuntimeError(f"{node.catalog_ref}.{node.node_id}.{name} must be numeric")
    return float(value.value)


def node_parameter_integer(node: BoundCatalogNode, name: str) -> int:
    return int(round(node_parameter_number(node, name)))


def node_parameter_text(node: BoundCatalogNode, name: str) -> str:
    value = required_node_parameter(node, name)
    if value.payload_type not in {PayloadType.ENUM, PayloadType.RELATION_REF}:
        raise RuntimeError(f"{node.catalog_ref}.{node.node_id}.{name} must be textual")
    return str(value.value)


def required_node_parameter(node: BoundCatalogNode, name: str) -> TypedValue:
    value = node.resolved_parameters.get(name)
    if value is None:
        raise UndeclaredNodeParameterError(
            (
                f"{node.catalog_ref}.{node.node_id} read undeclared parameter {name}; "
                "binder did not resolve a catalog declaration or default"
            )
        )
    return value


def node_parameter_event_type_filter(node: BoundCatalogNode) -> tuple[str, ...]:
    return (node_parameter_text(node, "event_type_filter"),)


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
