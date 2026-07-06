"""M1.1 deterministic query runtime.

Gate B executes the approved M1 primitive chain from a bound plan. The executor
is deliberately keyed by primitive/operator catalog entries, not recipe IDs.
"""

from __future__ import annotations

import copy
import concurrent.futures
import hashlib
import json
import math
import os
import sys
import time
from collections.abc import MutableMapping
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from lxml import etree

from tqe.idsse.source_lock import SOURCE_VERSION
from tqe.runtime.binder import HOST_RUNTIME_PARAMETER_DEFAULTS, bind_document_from_path
from tqe.runtime.capabilities import (
    build_primitive_registry,
    build_relation_registry,
)
from tqe.runtime.ir import (
    BoundCatalogNode,
    BoundOperatorNode,
    BoundPredicateNode,
    BoundQueryPlan,
    BoundPlanNode,
    ClassificationRule,
    CoverageDeclaration,
    EntityScope,
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
from tqe.runtime.operators import OperatorImplementation, OperatorKey, build_operator_registry
from tqe.runtime import legacy_m1
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
DEFAULT_DATA_MANIFEST_PATH = Path(os.environ.get("TQE_DATA_MANIFEST_PATH", "data/manifest.json"))
GENERIC_EXECUTION_PROFILE = "generic"
SUPPORTED_PREDICATE_OPERATORS = frozenset(
    {
        "gt",
        "gte",
        "lte",
        "eq",
        "neq",
        "persists_for",
        "exists",
        "count_at_least",
    }
)
CACHE_SCHEMA_VERSION = "perf1_node_cache_key.v1"
CACHE_ENTRY_SCHEMA_VERSION = "perf1_node_cache_entry.v1"


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
    data_scope_manifest_entries: list[dict[str, Any]]
    positions: pd.DataFrame
    frame_ids: np.ndarray
    ball_y: np.ndarray
    possession_role: np.ndarray
    ball_alive: np.ndarray
    defender_count: pd.Series
    defender_centroid_y: pd.Series
    canonical_data_manifest_hash: str = ""
    signals: dict[str, Any] = field(default_factory=dict)
    runtime_values: dict[str, dict[str, RuntimeValue]] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    accepted: list[dict[str, Any]] = field(default_factory=list)
    near_misses: list[dict[str, Any]] = field(default_factory=list)
    predicate_traces: list[PredicateTrace] = field(default_factory=list)
    lookup_cache: dict[tuple[Any, ...], Any] = field(default_factory=dict)
    node_output_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    node_cache_keys: dict[str, str] = field(default_factory=dict)
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


class PersistentNodeOutputCache:
    """Self-describing disk cache for deterministic node outputs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        safe = "".join(char for char in key if char.isalnum()) or stable_hash(key)
        return self.root / safe[:2] / f"{safe}.json"

    def load(self, *, key: str, preimage: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        path = self.path_for(key)
        if not path.exists():
            return None, "persistent_miss"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, "detected_never_served"
        if payload.get("schema_version") != CACHE_ENTRY_SCHEMA_VERSION:
            return None, "detected_never_served"
        stored_preimage = payload.get("key_preimage")
        serialized_output = payload.get("output")
        if not isinstance(stored_preimage, dict) or not isinstance(serialized_output, dict):
            return None, "detected_never_served"
        if stable_hash(stored_preimage) != key or stored_preimage != preimage:
            return None, "detected_never_served"
        if payload.get("output_content_hash") != stable_hash(serialized_output):
            return None, "detected_never_served"
        return decode_cache_output(serialized_output), "persistent_hit"

    def store(self, *, key: str, preimage: dict[str, Any], output: dict[str, Any]) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized_output = encode_cache_output(output)
        payload = {
            "schema_version": CACHE_ENTRY_SCHEMA_VERSION,
            "cache_key": key,
            "key_preimage": preimage,
            "producing_code_epoch": preimage["code_epoch"],
            "output_content_hash": stable_hash(serialized_output),
            "output": serialized_output,
        }
        tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)


def encode_cache_output(value: Any) -> Any:
    if isinstance(value, FrameSignal):
        return {
            "__tqe_cache_type__": "FrameSignal",
            "frame_ids": [int(item) for item in value.frame_ids],
            "values": encode_cache_output(value.values),
            "unknown_mask": [bool(item) for item in value.unknown_mask],
            "unit": value.unit.value,
            "entity_scope": value.entity_scope.value,
        }
    if isinstance(value, dict):
        return {str(key): encode_cache_output(child) for key, child in value.items()}
    if isinstance(value, list):
        return [encode_cache_output(child) for child in value]
    if isinstance(value, tuple):
        return [encode_cache_output(child) for child in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return encode_cache_output(value.tolist())
    if isinstance(value, Unit | EntityScope):
        return value.value
    return value


def decode_cache_output(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("__tqe_cache_type__") == "FrameSignal":
            return FrameSignal(
                frame_ids=[int(item) for item in value["frame_ids"]],
                values=decode_cache_output(value["values"]),
                unknown_mask=[bool(item) for item in value["unknown_mask"]],
                unit=Unit(value["unit"]),
                entity_scope=EntityScope(value["entity_scope"]),
            )
        return {str(key): decode_cache_output(child) for key, child in value.items()}
    if isinstance(value, list):
        return [decode_cache_output(child) for child in value]
    return value


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


class TacticalQueryExecutor:
    def __init__(
        self,
        *,
        canonical_root: Path = DEFAULT_CANONICAL_ROOT,
        raw_root: Path = DEFAULT_RAW_ROOT,
        compatibility_profile: str = GENERIC_EXECUTION_PROFILE,
        enable_node_cache: bool | None = None,
        shared_node_output_cache: MutableMapping[str, dict[str, Any]] | None = None,
        node_cache_root: Path | None = None,
        parallel_workers: int | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        progress_log: bool | None = None,
    ) -> None:
        self.canonical_root = canonical_root
        self.raw_root = raw_root
        self.canonical_data_manifest_hash = canonical_data_manifest_hash(canonical_root)
        if compatibility_profile not in {GENERIC_EXECUTION_PROFILE, legacy_m1.LEGACY_M1_PARITY_PROFILE}:
            raise RuntimeError(f"Unsupported compatibility profile {compatibility_profile}")
        self.compatibility_profile = compatibility_profile
        self.enable_node_cache = (
            os.environ.get("TQE_DISABLE_NODE_CACHE") != "1"
            if enable_node_cache is None
            else enable_node_cache
        )
        self.shared_node_output_cache = shared_node_output_cache
        self.persistent_node_output_cache = (
            PersistentNodeOutputCache(node_cache_root)
            if node_cache_root is not None
            else default_persistent_node_output_cache()
        )
        self.parallel_workers = normalize_worker_count(
            parallel_workers
            if parallel_workers is not None
            else os.environ.get("TQE_EXECUTION_WORKERS")
        )
        self.progress_callback = progress_callback
        self.progress_log = (
            os.environ.get("TQE_PROGRESS_LOG") == "1"
            if progress_log is None
            else progress_log
        )
        registry_namespace = globals()
        self.primitives: dict[str, PrimitiveImplementation] = build_primitive_registry(registry_namespace)
        self.relations: dict[str, RelationImplementation] = build_relation_registry(registry_namespace)
        self.operators: dict[OperatorKey, OperatorImplementation] = build_operator_registry(registry_namespace)

    def execute(self, bound_plan: BoundQueryPlan) -> QueryExecution:
        execute_started = time.perf_counter()
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

        period_execution_started = time.perf_counter()
        if self.parallel_workers > 1 and len(bound_plan.match_ids) * len(bound_plan.periods) > 1:
            (
                results,
                trace_records,
                runtime_value_count,
                progress_events,
                node_cache_summary,
            ) = self._execute_periods_parallel(
                bound_plan=bound_plan,
                params=params,
                compatibility_profile=self.compatibility_profile,
            )
        else:
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
        period_execution_ms = elapsed_ms(period_execution_started)

        merge_started = time.perf_counter()
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
        merge_apply_result_semantics_ms = elapsed_ms(merge_started)

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
                    "persistent_hits": int(node_cache_summary.get("persistent_hit", 0)),
                    "misses": int(node_cache_summary.get("miss", 0)),
                    "disabled": int(node_cache_summary.get("disabled", 0)),
                    "bypassed": int(node_cache_summary.get("bypassed", 0)),
                    "detected_never_served": int(node_cache_summary.get("detected_never_served", 0)),
                },
                "execution_parallelism": {
                    "workers": self.parallel_workers,
                    "backend": parallel_backend_from_progress(progress_events, self.parallel_workers),
                    "period_state_independence": (
                        "Each worker constructs a fresh PeriodState for one "
                        "match_id/period, reading only scope-local canonical/raw "
                        "files and returning serializable outputs; no PeriodState "
                        "object is shared across workers."
                    ),
                    "merge_order": "bound_plan.match_ids order, then bound_plan.periods order, then existing result sort law",
                },
                "progress_event_count": len(progress_events),
                "progress_events": progress_events,
                "unknown_policy": bound_plan.unknown_evidence_policy.value,
                "unknown_trace_count": sum(1 for trace in trace_records if trace.status == "UNKNOWN"),
                "requested_evidence_failure_count": len(evidence_failures),
                "requested_evidence_failures": evidence_failures[:20],
                "runtime_trace_hash": stable_hash(trace_payload),
            },
            timing_ms={
                "schema_version": "perf1_execution_timing.v1",
                "total_ms": elapsed_ms(execute_started),
                "period_execution_ms": period_execution_ms,
                "merge_apply_result_semantics_ms": merge_apply_result_semantics_ms,
                "periods": period_timing_rows(progress_events),
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
            if compatibility_profile == legacy_m1.LEGACY_M1_PARITY_PROFILE:
                accepted.extend(state.accepted)
                traces.extend(
                    legacy_m1.accepted_predicate_traces(
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
        if compatibility_profile == legacy_m1.LEGACY_M1_PARITY_PROFILE:
            accepted.sort(key=legacy_m1.legacy_m1_result_key)
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

    def _execute_periods_parallel(
        self,
        *,
        bound_plan: BoundQueryPlan,
        params: RuntimeParameters,
        compatibility_profile: str,
    ) -> tuple[list[dict[str, Any]], list[PredicateTrace], int, list[dict[str, Any]], Counter[str]]:
        tasks: list[dict[str, Any]] = []
        for match_index, match_id in enumerate(bound_plan.match_ids):
            for period_index, period in enumerate(bound_plan.periods):
                tasks.append(
                    {
                        "match_index": match_index,
                        "period_index": period_index,
                        "match_id": match_id,
                        "period": period,
                        "bound_plan": bound_plan.model_dump(mode="json"),
                        "canonical_root": str(self.canonical_root),
                        "raw_root": str(self.raw_root),
                        "compatibility_profile": compatibility_profile,
                        "enable_node_cache": self.enable_node_cache,
                        "node_cache_root": None
                        if self.persistent_node_output_cache is None
                        else str(self.persistent_node_output_cache.root),
                    }
                )
        worker_count = min(self.parallel_workers, len(tasks))
        period_outputs: list[dict[str, Any]] = []
        pool, parallel_backend = period_worker_pool(worker_count)
        with pool:
            futures = [pool.submit(_execute_period_worker, task) for task in tasks]
            for future in concurrent.futures.as_completed(futures):
                period_outputs.append(future.result())

        by_match_period = {
            (int(item["match_index"]), int(item["period_index"])): item
            for item in period_outputs
        }
        accepted: list[dict[str, Any]] = []
        traces: list[PredicateTrace] = []
        runtime_value_count = 0
        progress_events: list[dict[str, Any]] = [
            {
                "event": "parallel_executor_backend",
                "backend": parallel_backend,
                "workers": worker_count,
            }
        ]
        node_cache_summary: Counter[str] = Counter()
        for match_index, _match_id in enumerate(bound_plan.match_ids):
            match_results: list[dict[str, Any]] = []
            match_traces: list[PredicateTrace] = []
            for period_index, _period in enumerate(bound_plan.periods):
                item = by_match_period[(match_index, period_index)]
                match_results.extend(item["results"])
                match_traces.extend(PredicateTrace.model_validate(trace) for trace in item["traces"])
                runtime_value_count += int(item["runtime_value_count"])
                progress_events.extend(item["progress_events"])
                node_cache_summary.update(Counter(item["node_cache_summary"]))
            if compatibility_profile == legacy_m1.LEGACY_M1_PARITY_PROFILE:
                match_results.sort(key=legacy_m1.legacy_m1_result_key)
            else:
                match_results.sort(
                    key=lambda result: (
                        result["match_id"],
                        result["period"],
                        int(result["anchor_frame_id"]),
                        result["classification"],
                        result["result_id"],
                    )
                )
            accepted.extend(match_results)
            traces.extend(match_traces)
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
        period_started = time.perf_counter()
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
                "duration_ms": elapsed_ms(period_started),
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
        elif isinstance(node, BoundOperatorNode):
            progress_base["operator"] = node.operator.name
        self._record_progress(state, {"event": "node_start", **progress_base})

        cache_status = "bypassed"
        derived_cache = derive_node_cache_key(
            node=node,
            state=state,
            upstream_lineage=node_upstream_lineage(state, node),
        )
        cache_key = derived_cache["cache_key"]
        cache_preimage = derived_cache["preimage"]
        safe_shared_cache = self.shared_node_output_cache if isinstance(self.shared_node_output_cache, dict) else None
        if isinstance(node, BoundCatalogNode):
            if node.kind == NodeKind.RELATION:
                implementation = self.relations.get(node.catalog_ref)
                if implementation is None:
                    raise RuntimeError(f"No relation implementation for {node.catalog_ref}")
            else:
                implementation = self.primitives.get(node.catalog_ref)
            if implementation is None:
                raise RuntimeError(f"No primitive implementation for {node.catalog_ref}")
            if self.enable_node_cache and profile == GENERIC_EXECUTION_PROFILE:
                if cache_key in state.node_output_cache:
                    state.signals[node.node_id] = copy.deepcopy(state.node_output_cache[cache_key])
                    cache_status = "hit"
                    state.node_cache_summary["hit"] += 1
                    state.node_cache_summary["local_hit"] += 1
                elif safe_shared_cache is not None and cache_key in safe_shared_cache:
                    state.signals[node.node_id] = copy.deepcopy(safe_shared_cache[cache_key])
                    state.node_output_cache[cache_key] = copy.deepcopy(state.signals[node.node_id])
                    cache_status = "shared_hit"
                    state.node_cache_summary["hit"] += 1
                    state.node_cache_summary["shared_hit"] += 1
                elif self.persistent_node_output_cache is not None:
                    output, persistent_status = self.persistent_node_output_cache.load(
                        key=cache_key,
                        preimage=cache_preimage,
                    )
                    if output is not None:
                        state.signals[node.node_id] = output
                        state.node_output_cache[cache_key] = copy.deepcopy(output)
                        cache_status = "persistent_hit"
                        state.node_cache_summary["hit"] += 1
                        state.node_cache_summary["persistent_hit"] += 1
                    else:
                        if persistent_status == "detected_never_served":
                            state.node_cache_summary["detected_never_served"] += 1
                            self._record_progress(
                                state,
                                {
                                    "event": "node_cache_detected_never_served",
                                    **progress_base,
                                    "cache_key": cache_key,
                                },
                            )
                        implementation(state, node)
                        state.node_output_cache[cache_key] = copy.deepcopy(state.signals[node.node_id])
                        if safe_shared_cache is not None:
                            safe_shared_cache[cache_key] = copy.deepcopy(state.signals[node.node_id])
                        self.persistent_node_output_cache.store(
                            key=cache_key,
                            preimage=cache_preimage,
                            output=copy.deepcopy(state.signals[node.node_id]),
                        )
                        cache_status = "miss"
                        state.node_cache_summary["miss"] += 1
                else:
                    implementation(state, node)
                    state.node_output_cache[cache_key] = copy.deepcopy(state.signals[node.node_id])
                    if safe_shared_cache is not None:
                        safe_shared_cache[cache_key] = copy.deepcopy(state.signals[node.node_id])
                    cache_status = "miss"
                    state.node_cache_summary["miss"] += 1
            else:
                implementation(state, node)
                cache_status = "disabled" if profile == GENERIC_EXECUTION_PROFILE else "bypassed"
                state.node_cache_summary[cache_status] += 1
        elif isinstance(node, BoundPredicateNode):
            if node.operator.name not in SUPPORTED_PREDICATE_OPERATORS:
                raise RuntimeError(f"No predicate implementation for {node.operator.name}")
            legacy_result = legacy_m1.legacy_m1_predicate_node_result(
                state=state,
                node=node,
                profile=profile,
                inputs=inputs,
                parameters=parameters,
                progress_base=progress_base,
                record_progress=self._record_progress,
            )
            if legacy_result is not None:
                state.node_cache_keys[node.node_id] = cache_key
                return legacy_result
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
        elif isinstance(node, BoundOperatorNode):
            implementation = self.operators.get((node.operator.name, node.operator.version))
            if implementation is None:
                raise RuntimeError(
                    f"No composition operator implementation for {node.operator.name}@{node.operator.version}"
                )
            implementation(state=state, node=node, inputs=inputs, parameters=parameters)
        else:
            raise RuntimeError(f"Unsupported bound node {node}")
        runtime_values = record_runtime_values(state, node)
        if isinstance(node, BoundCatalogNode) and conformance_enabled():
            shadow_check_legacy_outputs(
                node=node,
                raw_outputs=state.signals.get(node.node_id, {}),
                runtime_values=runtime_values,
            )
        state.node_cache_keys[node.node_id] = cache_key
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
            data_scope_manifest_entries=data_scope_manifest_entries(
                canonical_root=self.canonical_root,
                raw_tracking=raw_tracking,
                match_id=match_id,
                period=period,
            ),
            canonical_data_manifest_hash=self.canonical_data_manifest_hash,
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


def _execute_period_worker(payload: dict[str, Any]) -> dict[str, Any]:
    bound_plan = BoundQueryPlan.model_validate(payload["bound_plan"])
    executor = TacticalQueryExecutor(
        canonical_root=Path(payload["canonical_root"]),
        raw_root=Path(payload["raw_root"]),
        compatibility_profile=str(payload["compatibility_profile"]),
        enable_node_cache=bool(payload["enable_node_cache"]),
        node_cache_root=Path(payload["node_cache_root"]) if payload.get("node_cache_root") else None,
        parallel_workers=1,
    )
    state = executor._execute_period(
        bound_plan=bound_plan,
        match_id=str(payload["match_id"]),
        period=str(payload["period"]),
        params=runtime_parameters(bound_plan),
        compatibility_profile=str(payload["compatibility_profile"]),
    )
    if str(payload["compatibility_profile"]) == legacy_m1.LEGACY_M1_PARITY_PROFILE:
        results = list(state.accepted)
        traces = legacy_m1.accepted_predicate_traces(
            state,
            bound_plan=bound_plan,
            compatibility_profile=str(payload["compatibility_profile"]),
        )
    else:
        results, traces = emit_generic_results_from_rules(
            state=state,
            bound_plan=bound_plan,
            compatibility_profile=str(payload["compatibility_profile"]),
        )
    return {
        "match_index": int(payload["match_index"]),
        "period_index": int(payload["period_index"]),
        "results": results,
        "traces": [trace.model_dump(mode="json", exclude_none=True) for trace in traces],
        "runtime_value_count": sum(len(outputs) for outputs in state.runtime_values.values()),
        "progress_events": state.progress_events,
        "node_cache_summary": dict(state.node_cache_summary),
    }


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


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


def period_worker_pool(worker_count: int) -> tuple[concurrent.futures.Executor, str]:
    try:
        return concurrent.futures.ProcessPoolExecutor(max_workers=worker_count), "process"
    except PermissionError:
        return (
            concurrent.futures.ThreadPoolExecutor(max_workers=worker_count),
            "thread_fallback_process_pool_unavailable",
        )


def parallel_backend_from_progress(progress_events: list[dict[str, Any]], workers: int) -> str:
    for event in progress_events:
        if event.get("event") == "parallel_executor_backend":
            return str(event.get("backend"))
    return "serial" if workers <= 1 else "not_recorded"


def period_timing_rows(progress_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in progress_events:
        if event.get("event") != "period_complete":
            continue
        rows.append(
            {
                "match_id": str(event.get("match_id")),
                "period": str(event.get("period")),
                "duration_ms": float(event.get("duration_ms", 0.0)),
                "node_count": int(event.get("node_count", 0)),
                "runtime_node_count": int(event.get("runtime_node_count", 0)),
            }
        )
    return rows


def derive_node_cache_key(
    *,
    node: BoundPlanNode,
    state: Any,
    upstream_lineage: list[dict[str, Any]],
    cache_schema_version: str = CACHE_SCHEMA_VERSION,
    code_epoch: str | None = None,
) -> dict[str, Any]:
    preimage = {
        "cache_schema_version": cache_schema_version,
        "code_epoch": code_epoch or runtime_code_epoch(),
        "node_semantic_identity": node_semantic_identity(node, state),
        "upstream_lineage": upstream_lineage,
        "data_scope": {
            "match_id": str(state.match_id),
            "period": str(state.period),
            "manifest_entries": list(getattr(state, "data_scope_manifest_entries", [])),
        },
        "perspective_bindings": {
            "perspective_team_role": str(state.perspective_team_role),
            "perspective_team_id": str(getattr(state, "perspective_team_id", "")),
            "defending_team_role": str(state.defending_team_role),
            "defending_team_id": str(getattr(state, "defending_team_id", "")),
        },
    }
    return {"cache_key": stable_hash(preimage), "preimage": preimage}


def node_semantic_identity(node: BoundPlanNode, state: Any) -> dict[str, Any]:
    payload = node.model_dump(mode="json", exclude={"node_id"})
    if isinstance(node, BoundCatalogNode):
        family = {
            "kind": node.kind.value,
            "catalog_ref": node.catalog_ref,
            "version": node.version,
            "inputs": payload.get("inputs", {}),
            "input_types": payload.get("input_types", {}),
            "outputs": payload.get("outputs", []),
            "resolved_parameters": payload.get("resolved_parameters", {}),
        }
    elif isinstance(node, BoundPredicateNode):
        family = {
            "kind": node.kind.value,
            "operator": payload.get("operator", {}),
            "input": payload.get("input", {}),
            "input_type": payload.get("input_type", {}),
            "compare": payload.get("compare"),
            "duration": payload.get("duration"),
            "output": payload.get("output", {}),
        }
    elif isinstance(node, BoundOperatorNode):
        family = {
            "kind": node.kind.value,
            "operator": payload.get("operator", {}),
            "inputs": payload.get("inputs", {}),
            "input_types": payload.get("input_types", {}),
            "outputs": payload.get("outputs", []),
            "resolved_parameters": payload.get("resolved_parameters", {}),
        }
    else:
        raise RuntimeError(f"Unsupported cache-key node {node}")
    return {
        **family,
        "runtime_parameters_expanded_defaults": dict(sorted(state.params.values.items())),
    }


def node_upstream_lineage(state: PeriodState, node: BoundPlanNode) -> list[dict[str, Any]]:
    if isinstance(node, BoundPredicateNode):
        refs = {"input": node.input}
    else:
        refs = getattr(node, "inputs", {})
    lineage: list[dict[str, Any]] = []
    for input_name, ref in sorted(refs.items()):
        source_node_id = ref.source_node_id
        if source_node_id not in state.node_cache_keys:
            raise RuntimeError(f"{node.node_id} input {input_name} references unexecuted node {source_node_id}")
        lineage.append(
            {
                "input_name": input_name,
                "source_node_id": source_node_id,
                "output_name": ref.output_name,
                "cache_key": state.node_cache_keys[source_node_id],
            }
        )
    return lineage


def catalog_node_cache_key(node: BoundCatalogNode) -> str:
    state = synthetic_cache_state()
    return derive_node_cache_key(node=node, state=state, upstream_lineage=[])["cache_key"]


def synthetic_cache_state() -> Any:
    return type(
        "SyntheticCacheState",
        (),
        {
            "match_id": "synthetic",
            "period": "firstHalf",
            "params": RuntimeParameters(values={}),
            "data_scope_manifest_entries": [],
            "perspective_team_role": "home",
            "perspective_team_id": "",
            "defending_team_role": "away",
            "defending_team_id": "",
        },
    )()


def normalize_worker_count(value: int | str | None) -> int:
    if value is None or value == "":
        return 1
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, parsed)


def default_persistent_node_output_cache() -> PersistentNodeOutputCache | None:
    explicit = os.environ.get("TQE_NODE_CACHE_ROOT")
    if explicit:
        return PersistentNodeOutputCache(Path(explicit))
    cache_root = os.environ.get("TQE_CACHE_ROOT")
    if cache_root:
        return PersistentNodeOutputCache(Path(cache_root) / "node-output")
    return None


@lru_cache(maxsize=1)
def runtime_code_epoch() -> str:
    root = Path(__file__).resolve().parent
    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_path(path),
            }
        )
    return stable_hash(
        {
            "schema_version": "runtime_code_epoch.v1",
            "source_root": "src/tqe/runtime",
            "files": entries,
        }
    )


def canonical_data_manifest_hash(canonical_root: Path) -> str:
    root = canonical_root.resolve()
    data_manifest = repo_relative_path(Path(os.environ.get("TQE_DATA_MANIFEST_PATH", str(DEFAULT_DATA_MANIFEST_PATH))))
    if data_manifest.is_file() and manifest_covers_root(data_manifest, root):
        verify_data_manifest_for_root(data_manifest, root, deep_verify=os.environ.get("TQE_DEEP_VERIFY") == "1")
        return file_content_hash(
            data_manifest,
            schema_version="canonical_data_manifest_file.v1",
        )
    candidates = (
        root / "manifest.json",
        root / "canonical_manifest.json",
        root / "canonical-manifest.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return file_content_hash(
                candidate,
                schema_version="canonical_data_manifest_file.v1",
            )
    if not root.exists():
        return stable_hash(
            {
                "schema_version": "canonical_data_manifest_tree.v1",
                "canonical_root": str(root),
                "exists": False,
            }
        )
    digest = hashlib.sha256()
    digest.update(b"canonical_data_manifest_tree.v1\0")
    digest.update(str(root).encode("utf-8"))
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(b"\0path\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0content\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def repo_relative_path(path: Path) -> Path:
    return path if path.is_absolute() else Path(__file__).resolve().parents[3] / path


def manifest_covers_root(manifest_path: Path, root: Path) -> bool:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for entry in payload.get("files", []):
        entry_path = manifest_entry_path(entry, manifest_path)
        try:
            entry_path.resolve().relative_to(root)
            return True
        except ValueError:
            continue
    return False


def verify_data_manifest_for_root(manifest_path: Path, root: Path, *, deep_verify: bool) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "entrelineas_data_manifest.v1":
        raise RuntimeError(f"Unsupported data manifest schema: {payload.get('schema_version')}")
    entries: dict[str, dict[str, Any]] = {}
    for entry in payload.get("files", []):
        entry_path = manifest_entry_path(entry, manifest_path)
        try:
            relative = entry_path.resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        if relative in entries:
            raise RuntimeError(f"Duplicate data manifest entry for {relative}")
        entries[relative] = entry

    actual_files = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
    }
    missing = sorted(set(entries) - set(actual_files))
    extra = sorted(set(actual_files) - set(entries))
    if missing or extra:
        raise RuntimeError(
            "Data manifest file set mismatch: "
            f"missing={missing[:5]} extra={extra[:5]}"
        )

    for relative, path in sorted(actual_files.items()):
        entry = entries[relative]
        expected_size = int(entry.get("size", -1))
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise RuntimeError(
                f"Data manifest size mismatch for {relative}: "
                f"expected {expected_size}, actual {actual_size}"
            )
        expected_sha = str(entry.get("sha256") or "")
        if not expected_sha:
            raise RuntimeError(f"Data manifest entry missing sha256 for {relative}")
        if deep_verify and sha256_path(path) != expected_sha:
            raise RuntimeError(f"Data manifest sha256 mismatch for {relative}")


def manifest_entry_path(entry: dict[str, Any], manifest_path: Path) -> Path:
    value = Path(str(entry.get("path") or ""))
    if value.is_absolute():
        return value
    return repo_relative_path(value)


def data_scope_manifest_entries(
    *,
    canonical_root: Path,
    raw_tracking: Path,
    match_id: str,
    period: str,
) -> list[dict[str, Any]]:
    paths = [
        canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet",
        canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet",
        canonical_root / "events" / f"match_id={match_id}.parquet",
        canonical_root / "orientation.parquet",
        canonical_root / "players.parquet",
        canonical_root / "teams.parquet",
        canonical_root / "matches.parquet",
        raw_tracking,
    ]
    manifest_path = repo_relative_path(Path(os.environ.get("TQE_DATA_MANIFEST_PATH", str(DEFAULT_DATA_MANIFEST_PATH))))
    manifest_entries = data_manifest_entry_index(str(manifest_path.resolve()), str(canonical_root.resolve()))
    entries = [
        manifest_or_file_entry(path=path, root=canonical_root, manifest_entries=manifest_entries)
        for path in paths
    ]
    return sorted(entries, key=lambda item: item["path"])


@lru_cache(maxsize=16)
def data_manifest_entry_index(manifest_path_str: str, canonical_root_str: str) -> dict[str, dict[str, Any]]:
    manifest_path = Path(manifest_path_str)
    canonical_root = Path(canonical_root_str)
    if not manifest_path.is_file():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for entry in payload.get("files", []):
        entry_path = manifest_entry_path(entry, manifest_path)
        try:
            relative = entry_path.resolve().relative_to(canonical_root).as_posix()
        except ValueError:
            continue
        entries[relative] = {
            "path": entry_path.as_posix(),
            "size": int(entry.get("size", -1)),
            "sha256": str(entry.get("sha256") or ""),
        }
    return entries


def manifest_or_file_entry(
    *,
    path: Path,
    root: Path,
    manifest_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = path.as_posix()
    if relative in manifest_entries:
        entry = dict(manifest_entries[relative])
        entry["path"] = relative
        entry["source"] = "data_manifest"
        return entry
    exists = path.exists()
    return {
        "path": relative,
        "source": "file_stat_sha256",
        "exists": exists,
        "size": path.stat().st_size if exists else None,
        "sha256": sha256_path(path) if exists and path.is_file() else None,
    }


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_content_hash(path: Path, *, schema_version: str) -> str:
    digest = hashlib.sha256()
    digest.update(schema_version.encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.name.encode("utf-8"))
    digest.update(b"\0")
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shared_catalog_node_cache_key(state: PeriodState, node: BoundCatalogNode, node_cache_key: str) -> str:
    if not getattr(state, "data_scope_manifest_entries", None):
        state.data_scope_manifest_entries = data_scope_manifest_entries(
            canonical_root=state.canonical_root,
            raw_tracking=state.raw_tracking,
            match_id=state.match_id,
            period=state.period,
        )
    return derive_node_cache_key(
        node=node,
        state=state,
        upstream_lineage=[],
    )["cache_key"]


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
    result = legacy_m1.legacy_m1_target_result(anchor_record, compatibility_profile) or generic_target_result(anchor_record)
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
) -> str | None:
    if source_node_id is None:
        return None
    runtime_value = state.runtime_values.get(source_node_id, {}).get("anchor_evaluations")
    if runtime_value is None:
        return None
    for record in runtime_records(runtime_value):
        if record_matches_anchor(record, anchor) and record.get("witness_relation_id") is not None:
            return str(record["witness_relation_id"])
    return None


def selected_relation_id_for_evidence_request(
    *,
    state: PeriodState,
    anchor: RuntimeAnchor,
    bound_plan: BoundQueryPlan,
    source_node_id: str | None = None,
) -> str | None:
    del bound_plan
    return selected_relation_id_for_anchor(
        state=state,
        anchor=anchor,
        source_node_id=source_node_id,
    )


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
    source = record.get("source_result")
    if isinstance(source, dict) and record_matches_anchor(source, anchor):
        return True
    for source_record in record.get("source_records") or []:
        if isinstance(source_record, dict) and record_matches_anchor(source_record, anchor):
            return True
    return False


def legacy_trace_record_matches_anchor(record: dict[str, Any], anchor: RuntimeAnchor) -> bool:
    """Bridge legacy predicate trace records that predate explicit anchor IDs.

    Witness selection must use strict ``record_matches_anchor`` semantics. Some
    record-backed predicate traces, however, were minted before ``anchor_id``
    was stamped onto trace source records. For that trace-only path, preserve
    identity by result id when available, then by the match/period/frame triple
    those legacy records already carry.
    """
    if record_matches_anchor(record, anchor):
        return True
    if not isinstance(record, dict) or "anchor_id" in record:
        return False
    source_evidence = record.get("source_evidence") if isinstance(record.get("source_evidence"), dict) else {}
    anchor_result_id = anchor.attributes.get("result_id")
    record_result_id = record.get("result_id") or source_evidence.get("result_id")
    if anchor_result_id is not None and record_result_id is not None:
        return str(record_result_id) == str(anchor_result_id)
    record_match_id = record.get("match_id") or source_evidence.get("match_id")
    record_period = record.get("period") or source_evidence.get("period")
    record_frame_id = optional_int(record.get("anchor_frame_id") or source_evidence.get("anchor_frame_id"))
    return (
        str(record_match_id or "") == anchor.match_id
        and str(record_period or "") == anchor.period
        and record_frame_id == anchor.anchor_frame_id
    )


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
    runtime_outputs = state.runtime_values.get(node.node_id, {})
    runtime_value = runtime_outputs.get("episodes")
    anchor_evaluations = runtime_outputs.get("anchor_evaluations")
    counts: Counter[str] = Counter()
    if runtime_value is not None:
        for record in runtime_records(runtime_value):
            key = str(record.get("anchor_id") or record.get("result_id") or record.get("anchor_frame_id") or "")
            if key:
                counts[key] += 1
    count_violations = {
        anchor_key: count
        for anchor_key, count in counts.items()
        if count > limit
    }
    coverage_violations: dict[str, int] = {}
    if anchor_evaluations is not None and anchor_evaluations.output.coverage is not None:
        count_field = anchor_evaluations.output.coverage.count_field
        if count_field is not None:
            for record in runtime_records(anchor_evaluations):
                raw_count = record.get(count_field)
                if raw_count is None:
                    continue
                try:
                    count = int(raw_count)
                except (TypeError, ValueError):
                    continue
                if count > limit:
                    key = str(record.get("anchor_id") or record.get("result_id") or record.get("anchor_frame_id") or "")
                    coverage_violations[key or "<unknown>"] = count
    violations = {**count_violations, **coverage_violations}
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


def record_runtime_values(state: PeriodState, node: BoundPlanNode) -> dict[str, RuntimeValue]:
    raw_outputs = state.signals.get(node.node_id)
    if raw_outputs is None:
        raise RuntimeError(f"{node.node_id} did not emit any outputs")
    if isinstance(node, BoundCatalogNode | BoundOperatorNode):
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
    if isinstance(node, BoundCatalogNode | BoundOperatorNode):
        return {
            name: catalog_input_value(state, node, name)
            for name in sorted(node.inputs)
        }
    if isinstance(node, BoundPredicateNode):
        return {node.input.output_name: source_runtime_value(state, node)}
    return {}


def resolved_node_parameters(node: BoundPlanNode) -> dict[str, TypedValue]:
    if isinstance(node, BoundCatalogNode | BoundOperatorNode):
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
                        frame_id=source_record_frame_id(record),
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
            coverage = require_anchor_evaluation_records(node=node, records=records)
            return exists_from_anchor_evaluations(
                node=node,
                records=coverage,
            )
        raise RuntimeError(f"Unsupported exists source for {node.node_id}")
    if node.operator.name == "count_at_least":
        source = runtime_value.value
        compare = parameters.get("compare")
        if compare is None or not isinstance(source, list):
            raise RuntimeError(f"Unsupported count_at_least source for {node.node_id}")
        records = [record for record in source if isinstance(record, dict)]
        coverage = require_anchor_evaluation_records(node=node, records=records)
        return count_at_least_from_anchor_evaluations(
            node=node,
            records=coverage,
            threshold=int(round(float(compare.value))),
        )
    raise RuntimeError(f"Unsupported predicate operator {node.operator.name}")


def require_anchor_evaluation_records(
    *,
    node: BoundPredicateNode,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage = declared_anchor_evaluation_records(node=node, records=records)
    if len(coverage) != len(records):
        raise RuntimeError(
            f"{node.node_id} expected declared anchor-evaluation records for {node.operator.name}"
        )
    return coverage


def declared_anchor_evaluation_records(
    *,
    node: BoundPredicateNode,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage = node.input_type.coverage
    if coverage is None:
        raise RuntimeError(f"{node.node_id} source lacks declared anchor-evaluation coverage")
    return [
        record
        for record in records
        if anchor_evaluation_status_label(record, coverage) in {"PASS", "FAIL", "UNKNOWN"}
        and "anchor_frame_id" in record
    ]


def exists_from_anchor_evaluations(
    *,
    node: BoundPredicateNode,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    coverage = node.input_type.coverage
    if coverage is None:
        raise RuntimeError(f"{node.node_id} exists source lacks declared coverage")
    statuses = [anchor_evaluation_status(record, coverage) for record in records]
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
    coverage = node.input_type.coverage
    if coverage is None or coverage.count_field is None:
        raise RuntimeError(f"{node.node_id} count_at_least source lacks declared count coverage")
    statuses: list[bool | None] = []
    values: list[int | None] = []
    for record in records:
        if anchor_evaluation_status_label(record, coverage) == "UNKNOWN":
            statuses.append(None)
            values.append(None)
            continue
        count = optional_int(record.get(coverage.count_field))
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


def anchor_evaluation_status(record: dict[str, Any], coverage: CoverageDeclaration) -> bool | None:
    status = anchor_evaluation_status_label(record, coverage)
    if status == "PASS":
        return True
    if status == "FAIL":
        return False
    return None


def anchor_evaluation_status_label(record: dict[str, Any], coverage: CoverageDeclaration) -> str:
    raw = record.get(coverage.status_field)
    status = "" if raw is None else str(raw)
    if status in set(coverage.pass_values):
        return "PASS"
    if status in set(coverage.fail_values):
        return "FAIL"
    if status in set(coverage.unknown_values):
        return "UNKNOWN"
    return "UNKNOWN"


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
    coverage = node.input_type.coverage
    for record, status, value, frame_id in usable:
        status_label = anchor_evaluation_status_label(record, coverage) if coverage is not None else None
        count_value = record.get(coverage.count_field) if coverage is not None and coverage.count_field is not None else None
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
                    "relation_count": count_value,
                    "evaluation_status": status_label,
                    "coverage_status_field": coverage.status_field if coverage is not None else None,
                    "coverage_count_field": coverage.count_field if coverage is not None else None,
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


















































def arrival_candidates(
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
    raise RuntimeError(f"Unsupported arrival candidate_scope: {candidate_scope}")






















































def ball_x_at_frame(positions: pd.DataFrame, frame_id: int) -> float | None:
    rows = positions[
        (positions["frame_id"] == frame_id)
        & (positions["entity_type"] == "ball")
    ]
    if rows.empty:
        return None
    value = rows.iloc[0]["x_m"]
    return None if pd.isna(value) else float(value)




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


def catalog_output(node: BoundCatalogNode, name: str) -> Any:
    for output in node.outputs:
        if output.name == name:
            return output
    raise RuntimeError(f"{node.node_id} did not declare output {name}")
























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


def predicate_traces_for_anchor(
    state: PeriodState,
    anchor: RuntimeAnchor,
    result: dict[str, Any],
    bound_plan: BoundQueryPlan | None = None,
    compatibility_profile: str = GENERIC_EXECUTION_PROFILE,
) -> list[PredicateTrace]:
    if compatibility_profile == legacy_m1.LEGACY_M1_PARITY_PROFILE:
        return legacy_m1.predicate_traces_for_anchor(
            state,
            anchor,
            result,
            bound_plan=bound_plan,
            compatibility_profile=compatibility_profile,
        )
    if bound_plan is None:
        return []
    return predicate_traces_from_declared_runtime_outputs(
        bound_plan=bound_plan,
        state=state,
        anchor=anchor,
        result=result,
    )


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
                status = "FAIL"
                matched_window = None
                reason = None
            else:
                status = str(matched.get("temporal_status") or "PASS")
                matched_window = matched
                reason = None
        else:
            status = "PASS" if matched is not None else "FAIL"
            matched_window = matched
            reason = None
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
            source_evidence={**source_evidence, "reason": reason} if reason is not None else source_evidence,
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
        if not legacy_trace_record_matches_anchor(source_record, anchor):
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




def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
