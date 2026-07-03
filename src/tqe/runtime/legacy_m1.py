"""Legacy M1 profile helpers quarantined from the generic executor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.ir import PredicateTrace, TypedValue, Unit

LEGACY_M1_PARITY_PROFILE = "legacy_m1_parity"
GENERIC_EXECUTION_PROFILE = "generic"


def _executor() -> Any:
    from tqe.runtime import executor  # noqa: PLC0415 - lazy import avoids executor/legacy cycle.

    return executor


def select_proof_results(candidates: list[dict[str, Any]], params: Any) -> list[dict[str, Any]]:
    """Select the frozen M1 proof-pack subset with legacy classification labels."""
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


def legacy_m1_result_key(item: dict[str, Any]) -> tuple[float, str, str, int]:
    return (
        -float(item["block_shift_score"]),
        str(item["match_id"]),
        str(item["period"]),
        int(item["wide_entry_frame_id"]),
    )


def legacy_m1_target_result(anchor_record: dict[str, Any], compatibility_profile: str) -> dict[str, Any] | None:
    if compatibility_profile != LEGACY_M1_PARITY_PROFILE:
        return None
    runtime_result = anchor_record.get("_runtime_result")
    return runtime_result if isinstance(runtime_result, dict) else None


def legacy_m1_record_persists_for_adapter(*, state: Any, node: Any) -> bool:
    ex = _executor()
    duration_seconds = float(node.duration.value) if isinstance(node.duration, TypedValue) else None
    if duration_seconds is None:
        raise RuntimeError(f"{node.node_id} requires duration")
    runtime_value = ex.source_runtime_value(state, node)
    values = ex.runtime_frame_values(runtime_value)
    if not isinstance(values, list):
        return False
    records = ex.runtime_records(runtime_value)
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
        persistence = ex.record_persistence_evidence(
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
        ex.record_candidate_predicate(
            candidate=record,
            node=node,
            status="PASS" if persistent else "FAIL",
            value=(
                ex.typed_number(float(persistence["duration_seconds"]), Unit.SECOND)
                if persistence["duration_seconds"] is not None
                else None
            ),
            threshold=ex.typed_number(duration_seconds, Unit.SECOND),
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


def legacy_m1_frame_signal_persists_for_adapter(*, state: Any, node: Any) -> bool:
    ex = _executor()
    duration_seconds = float(node.duration.value) if isinstance(node.duration, TypedValue) else None
    if duration_seconds is None:
        raise RuntimeError(f"{node.node_id} requires duration")
    runtime_value = ex.source_runtime_value(state, node)
    values = ex.runtime_frame_values(runtime_value)
    if not isinstance(values, list) or not all(value is None or isinstance(value, bool) for value in values):
        return False
    source_facts = ex.runtime_records(runtime_value)
    if not source_facts:
        return False
    if any(isinstance(record.get("measure_series"), pd.Series) for record in source_facts):
        return False
    if not all(isinstance(record, dict) and "status" in record for record in source_facts):
        return False
    analysis_rate_hz = state.params.integer("analysis_rate_hz")
    minimum_frames = int(round(duration_seconds * analysis_rate_hz))
    frame_ids = ex.frame_ids_for_runtime_value(
        runtime_value,
        ex.MatchContext(
            match_id=state.match_id,
            period=state.period,
            frame_ids=tuple(int(frame_id) for frame_id in state.frame_ids),
            params=state.params,
        ),
    )
    episodes = ex.episode_records_from_frame_ids_and_mask(
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
        ex.record_candidate_predicate(
            candidate=episode,
            node=node,
            status="PASS",
            value=ex.typed_number(round(float(duration), 3), Unit.SECOND),
            threshold=ex.typed_number(duration_seconds, Unit.SECOND),
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


def legacy_m1_predicate_node_result(
    *,
    state: Any,
    node: Any,
    profile: str,
    inputs: dict[str, Any],
    parameters: dict[str, Any],
    progress_base: dict[str, Any],
    record_progress: Any,
) -> Any:
    if profile != LEGACY_M1_PARITY_PROFILE or node.operator.name != "persists_for":
        return None
    ex = _executor()
    if legacy_m1_record_persists_for_adapter(state=state, node=node):
        adapter = "legacy_m1_record_persists_for"
    elif legacy_m1_frame_signal_persists_for_adapter(state=state, node=node):
        adapter = "legacy_m1_frame_signal_persists_for"
    else:
        return None
    runtime_values = ex.record_runtime_values(state, node)
    record_progress(
        state,
        {
            "event": "node_complete",
            **progress_base,
            "cache_status": "bypassed",
            "output_names": sorted(runtime_values),
        },
    )
    return ex.NodeExecutionResult(
        node_id=node.node_id,
        inputs=inputs,
        parameters=parameters,
        outputs=state.signals.get(node.node_id, {}),
        runtime_values=runtime_values,
        provenance={
            "node_kind": node.kind.value,
            "compatibility_profile": profile,
            "adapter": adapter,
        },
    )


def accepted_predicate_traces(
    state: Any,
    *,
    bound_plan: Any | None = None,
    compatibility_profile: str = LEGACY_M1_PARITY_PROFILE,
) -> list[PredicateTrace]:
    ex = _executor()
    if state.predicate_traces:
        return state.predicate_traces
    traces: list[PredicateTrace] = []
    for result in state.accepted:
        anchor = ex.runtime_anchor_from_record(
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
    state: Any,
    anchor: Any,
    result: dict[str, Any],
) -> list[PredicateTrace]:
    del state
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
    state: Any,
    anchor: Any,
    result: dict[str, Any],
    bound_plan: Any | None = None,
    compatibility_profile: str = GENERIC_EXECUTION_PROFILE,
) -> list[PredicateTrace]:
    ex = _executor()
    runtime_traces = (
        ex.predicate_traces_from_declared_runtime_outputs(
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


def execute_default_plan(
    *,
    canonical_root: Path | None = None,
    raw_root: Path | None = None,
    plan_path: Path | None = None,
) -> tuple[Any, Any]:
    ex = _executor()
    bound = bind_document_from_path(plan_path or ex.DEFAULT_PLAN_PATH)
    execution = ex.TacticalQueryExecutor(
        canonical_root=canonical_root or ex.DEFAULT_CANONICAL_ROOT,
        raw_root=raw_root or ex.DEFAULT_RAW_ROOT,
        compatibility_profile=LEGACY_M1_PARITY_PROFILE,
    ).execute(bound)
    return bound, execution


def execute_legacy_m1_plan_from_path(
    plan_path: Path,
    *,
    canonical_root: Path | None = None,
    raw_root: Path | None = None,
) -> tuple[Any, Any]:
    ex = _executor()
    bound = bind_document_from_path(plan_path)
    execution = ex.TacticalQueryExecutor(
        canonical_root=canonical_root or ex.DEFAULT_CANONICAL_ROOT,
        raw_root=raw_root or ex.DEFAULT_RAW_ROOT,
        compatibility_profile=LEGACY_M1_PARITY_PROFILE,
    ).execute(bound)
    return bound, execution
