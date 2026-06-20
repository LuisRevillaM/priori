"""Verify M1.1S Gate S3R: explicit anchors and generic temporal semantics."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.binder import bind_document, bind_document_from_path
from tqe.runtime.catalog import output
from tqe.runtime.executor import (
    FRAME_RATE_HZ,
    PeriodState,
    RuntimeParameters,
    TacticalQueryExecutor,
    GENERIC_EXECUTION_PROFILE,
    anchor_record_id,
    evaluate_target_in_state,
    execute_persists_for,
    execute_predicate_with_resolved_inputs,
    execution_result_rows,
    predicate_persists_for,
    runtime_anchors,
    runtime_parameters,
    typed_number,
)
from tqe.runtime.ir import (
    BoundPredicateNode,
    Cardinality,
    EntityScope,
    EvaluationTarget,
    PayloadType,
    SignalRef,
    TacticalQueryDocument,
    TemporalContainer,
    Unit,
)
from tqe.runtime.values import FrameSignal, RuntimeValue, runtime_value_from_raw
from tqe.verification.m1_1_gate_r5 import clone_plan_payload, renamed_node_payload

APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
REPORT_PATH = Path("artifacts/m1.1/gate-s3r-verification-report.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    bound = bind_document_from_path(APPROVED_PLAN_PATH)
    executor = TacticalQueryExecutor()
    state = executor._execute_period(  # noqa: SLF001 - verifier inspects runtime contract.
        bound_plan=bound,
        match_id="J03WOY",
        period="firstHalf",
        params=runtime_parameters(bound),
    )

    checks.extend(validate_explicit_anchor_source(bound, state))
    checks.extend(validate_anchor_identity_rename_stability(executor, bound))
    checks.extend(validate_anchor_dedup_and_side_channel_independence(bound))
    checks.extend(validate_invalid_anchor_id_rejected())
    checks.extend(validate_non_m1_anchor_target_and_trace(bound))
    checks.extend(validate_generic_temporal_semantics(bound))
    checks.extend(validate_generic_profile_rejects_legacy_shape(bound))
    checks.extend(validate_frame_length_mismatch_rejected())
    checks.extend(validate_generic_source_no_forbidden_assumptions())
    checks.extend(validate_node_execution_result_contract(executor, bound))
    checks.extend(validate_approved_plan_parity(bound, executor))

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S3R_explicit_anchor_contract_generic_temporal_semantics",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_explicit_anchor_source(bound: Any, state: PeriodState) -> list[dict[str, Any]]:
    anchors = runtime_anchors(state, bound.anchor_source)
    sources = sorted({f"{anchor.source_node_id}.{anchor.output_name}" for anchor in anchors})
    return [
        pass_check(
            "anchors.explicit_plan_anchor_source",
            "runtime anchor discovery uses the plan-designated anchor source only",
            {"anchor_source": bound.anchor_source.model_dump(mode="json"), "sources": sources, "count": len(anchors)},
        )
        if bound.anchor_source == SignalRef(source_node_id="signed_shift", output_name="anchors")
        and sources == ["signed_shift.anchors"]
        and anchors
        else fail_check(
            "anchors.explicit_plan_anchor_source",
            "anchor discovery is missing or not bound to the explicit plan anchor source",
            {"anchor_source": getattr(bound.anchor_source, "model_dump", lambda **_: None)(mode="json") if bound.anchor_source else None, "sources": sources},
        )
    ]


def validate_anchor_identity_rename_stability(
    executor: TacticalQueryExecutor,
    bound: Any,
) -> list[dict[str, Any]]:
    payload = renamed_node_payload(clone_plan_payload(APPROVED_PLAN_PATH))
    renamed_bound = bind_document(TacticalQueryDocument.model_validate(payload))
    params = runtime_parameters(bound)
    renamed_params = runtime_parameters(renamed_bound)
    original = executor._execute_period(  # noqa: SLF001
        bound_plan=bound,
        match_id="J03WOY",
        period="firstHalf",
        params=params,
    )
    renamed = executor._execute_period(  # noqa: SLF001
        bound_plan=renamed_bound,
        match_id="J03WOY",
        period="firstHalf",
        params=renamed_params,
    )
    original_ids = sorted(anchor.anchor_id for anchor in runtime_anchors(original, bound.anchor_source))
    renamed_ids = sorted(anchor.anchor_id for anchor in runtime_anchors(renamed, renamed_bound.anchor_source))
    return [
        pass_check(
            "anchors.semantic_ids_survive_node_rename",
            "renaming and reordering-independent node identity does not change anchor IDs",
            {"anchor_count": len(original_ids)},
        )
        if original_ids and original_ids == renamed_ids
        else fail_check(
            "anchors.semantic_ids_survive_node_rename",
            "anchor IDs changed after node rename",
            {"original_sample": original_ids[:10], "renamed_sample": renamed_ids[:10]},
        )
    ]


def validate_anchor_dedup_and_side_channel_independence(bound: Any) -> list[dict[str, Any]]:
    state = synthetic_period_state()
    record = synthetic_anchor_record(125)
    duplicate = dict(record)
    duplicate["anchor_id"] = "producer_controlled_conflicting_id"
    duplicate["ignored_extra"] = "same_physical_anchor"
    state.runtime_values["anchor_node"] = {
        "anchors": RuntimeValue(
            output=anchor_output(),
            value=[record, duplicate],
        )
    }
    state.candidates = [dict(record), dict(duplicate)]
    state.accepted = [dict(record)]
    before = runtime_anchors(state, SignalRef(source_node_id="anchor_node", output_name="anchors"))
    state.candidates = []
    state.accepted = []
    after = runtime_anchors(state, SignalRef(source_node_id="anchor_node", output_name="anchors"))
    return [
        pass_check(
            "anchors.deduplicate_and_ignore_side_channels",
            "semantic duplicates deduplicate and anchor discovery does not depend on state side channels",
            {"before": [anchor.anchor_id for anchor in before], "after": [anchor.anchor_id for anchor in after]},
        )
        if [anchor.anchor_id for anchor in before] == [record["anchor_id"]]
        and [anchor.anchor_id for anchor in after] == [record["anchor_id"]]
        else fail_check(
            "anchors.deduplicate_and_ignore_side_channels",
            "anchor dedupe or state side-channel independence failed",
            {"before": [anchor.anchor_id for anchor in before], "after": [anchor.anchor_id for anchor in after]},
        )
    ]


def validate_invalid_anchor_id_rejected() -> list[dict[str, Any]]:
    record = synthetic_anchor_record(125)
    record["anchor_id"] = "not_the_canonical_id"
    try:
        runtime_value_from_raw(
            node_id="anchor_node",
            output=anchor_output(),
            raw_value=[record],
        )
    except RuntimeError as error:
        return [
            pass_check(
                "anchors.invalid_supplied_id_rejected",
                "producer-supplied anchor IDs must match the canonical semantic hash",
                {"error": str(error)},
            )
        ]
    return [
        fail_check(
            "anchors.invalid_supplied_id_rejected",
            "runtime accepted a producer-controlled non-canonical anchor ID",
        )
    ]


def validate_non_m1_anchor_target_and_trace(bound: Any) -> list[dict[str, Any]]:
    state = synthetic_period_state()
    record = synthetic_anchor_record(125)
    state.runtime_values["anchor_node"] = {
        "anchors": RuntimeValue(output=anchor_output(), value=[record])
    }
    predicate_by_id = {
        node.node_id: node
        for node in bound.nodes
        if isinstance(node, BoundPredicateNode)
    }
    pass_node = predicate_by_id["wide_entry_threshold"]
    unknown_source_node = predicate_by_id["shift_threshold"]
    unknown_persist_node = predicate_by_id["shift_persists"].model_copy(
        update={"duration": typed_number(0.2, Unit.SECOND)}
    )
    fail_node = predicate_by_id["not_stoppage"]
    state.runtime_values[pass_node.input.source_node_id] = {
        pass_node.input.output_name: RuntimeValue(
            output=pass_node.input_type,
            value=FrameSignal(
                frame_ids=[125],
                values=[0.7],
                unknown_mask=[False],
                unit=pass_node.input_type.unit,
                entity_scope=pass_node.input_type.entity_scope,
            ),
        )
    }
    state.runtime_values[unknown_source_node.input.source_node_id] = {
        unknown_source_node.input.output_name: RuntimeValue(
            output=unknown_source_node.input_type,
            value=FrameSignal(
                frame_ids=[125],
                values=[None],
                unknown_mask=[True],
                unit=unknown_source_node.input_type.unit,
                entity_scope=unknown_source_node.input_type.entity_scope,
            ),
            records=[{"status": "PASS", "measure_series": pd.Series([1.0])}],
        )
    }
    state.runtime_values[fail_node.input.source_node_id] = {
        fail_node.input.output_name: RuntimeValue(
            output=fail_node.input_type,
            value=FrameSignal(
                frame_ids=[125],
                values=["STOPPAGE"],
                unknown_mask=[False],
                unit=fail_node.input_type.unit,
                entity_scope=fail_node.input_type.entity_scope,
            ),
        )
    }
    executor = TacticalQueryExecutor(compatibility_profile=GENERIC_EXECUTION_PROFILE)
    executed = [
        executor._execute_node(state=state, node=pass_node, compatibility_profile=GENERIC_EXECUTION_PROFILE),  # noqa: SLF001
        executor._execute_node(state=state, node=unknown_source_node, compatibility_profile=GENERIC_EXECUTION_PROFILE),  # noqa: SLF001
        executor._execute_node(state=state, node=unknown_persist_node, compatibility_profile=GENERIC_EXECUTION_PROFILE),  # noqa: SLF001
        executor._execute_node(state=state, node=fail_node, compatibility_profile=GENERIC_EXECUTION_PROFILE),  # noqa: SLF001
    ]
    synthetic_bound = bound.model_copy(
        update={
            "anchor_source": SignalRef(source_node_id="anchor_node", output_name="anchors"),
            "nodes": [pass_node, unknown_source_node, unknown_persist_node, fail_node],
        }
    )
    target = EvaluationTarget(
        target_id="non_m1_anchor_probe",
        match_id="synthetic",
        period="firstHalf",
        approximate_time_ms=int(round(125 / FRAME_RATE_HZ * 1000)),
        search_radius_ms=250,
    )
    result = evaluate_target_in_state(
        bound_plan=synthetic_bound,
        state=state,
        target=target,
        compatibility_profile=GENERIC_EXECUTION_PROFILE,
    )
    state.candidates = [{"_predicate_status": {"fake": {"status": "PASS"}}}]
    state.accepted = [{"_runtime_result": {"accepted": True}}]
    state.predicate_traces = []
    record["_runtime_result"] = {"accepted": True, "classification": "SIDE_CHANNEL"}
    record["_predicate_status"] = {"fake": {"status": "PASS"}}
    perturbed = evaluate_target_in_state(
        bound_plan=synthetic_bound,
        state=state,
        target=target,
        compatibility_profile=GENERIC_EXECUTION_PROFILE,
    )
    traces = result["predicate_traces"]
    statuses = {trace["predicate_id"]: trace["status"] for trace in traces}
    perturbed_statuses = {trace["predicate_id"]: trace["status"] for trace in perturbed["predicate_traces"]}
    source_text = inspect.getsource(evaluate_target_in_state)
    return [
        pass_check(
            "anchors.non_m1_anchor_targetable_and_traceable",
            "a non-M1 anchor gets engine-derived PASS, FAIL, and UNKNOWN traces from actual generic node execution",
            {
                "status": result["status"],
                "statuses": statuses,
                "perturbed_statuses": perturbed_statuses,
                "provenance": [item.provenance for item in executed],
            },
        )
        if result["status"] == "NON_MATCH"
        and result["closest_candidate"]["anchor_id"] == record["anchor_id"]
        and traces
        and statuses.get(pass_node.node_id) == "PASS"
        and statuses.get(unknown_persist_node.node_id) == "UNKNOWN"
        and statuses.get(fail_node.node_id) == "FAIL"
        and statuses == perturbed_statuses
        and all(item.provenance.get("adapter") is None for item in executed)
        and "wide_entry" not in source_text
        and "base_result_fields" not in source_text
        else fail_check(
            "anchors.non_m1_anchor_targetable_and_traceable",
            "non-M1 anchor target/trace path failed or still contains M1 assumptions",
            {"result": result, "source_contains_wide_entry": "wide_entry" in source_text},
        )
    ]


def validate_generic_temporal_semantics(bound: Any) -> list[dict[str, Any]]:
    node = next(
        node
        for node in bound.nodes
        if isinstance(node, BoundPredicateNode) and node.operator.name == "persists_for"
    ).model_copy(update={"duration": typed_number(0.4, Unit.SECOND)})
    state = synthetic_period_state()
    values = [True, True, None, True, True, True, False, True]
    signal = FrameSignal(
        frame_ids=[100, 101, 102, 103, 104, 105, 106, 107],
        values=values,
        unknown_mask=[value is None for value in values],
        unit=node.input_type.unit,
        entity_scope=node.input_type.entity_scope,
    )
    state.runtime_values[node.input.source_node_id] = {
        node.input.output_name: RuntimeValue(
            output=node.input_type,
            value=signal,
            records=[{"truth_series": pd.Series([True, True, True])}],
        )
    }
    executor = TacticalQueryExecutor(compatibility_profile=GENERIC_EXECUTION_PROFILE)
    result = executor._execute_node(state=state, node=node, compatibility_profile=GENERIC_EXECUTION_PROFILE)  # noqa: SLF001
    episodes = state.signals[node.node_id]["episodes"]
    windows = [
        (episode["temporal_status"], episode["start_frame_id"], episode["end_frame_id"])
        for episode in episodes
    ]
    source = inspect.getsource(predicate_persists_for)
    shared_source = inspect.getsource(execute_persists_for)
    forbidden = ["wide_entry", "block_shift", "shift_gate", "persistence_series", "quality_status", "runtime_records", "_predicate_status", "truth_series"]
    hits = [token for token in forbidden if token in source + shared_source]
    return [
        pass_check(
            "temporal.persists_for_generic_tri_state",
            "persists_for uses one generic temporal implementation, ignores arbitrary records, and preserves UNKNOWN intervals",
            {"windows": windows, "provenance": result.provenance},
        )
        if windows == [("PASS", 100, 101), ("PASS", 103, 105), ("UNKNOWN", 102, 102)]
        and result.provenance.get("adapter") is None
        and not hits
        else fail_check(
            "temporal.persists_for_generic_tri_state",
            "generic persists_for semantics failed",
            {"windows": windows, "forbidden_hits": hits},
        )
    ]


def validate_generic_profile_rejects_legacy_shape(bound: Any) -> list[dict[str, Any]]:
    node = next(
        node
        for node in bound.nodes
        if isinstance(node, BoundPredicateNode) and node.operator.name == "persists_for"
    ).model_copy(update={"duration": typed_number(0.2, Unit.SECOND)})
    state = synthetic_period_state()
    signal = FrameSignal(
        frame_ids=[100, 101, 102],
        values=[True, True, True],
        unknown_mask=[False, False, False],
        unit=node.input_type.unit,
        entity_scope=node.input_type.entity_scope,
    )
    legacy_shaped_records = [
        {"status": "PASS", "measure_series": pd.Series([9.0]), "truth_series": pd.Series([True])}
        for _ in signal.values
    ]
    state.runtime_values[node.input.source_node_id] = {
        node.input.output_name: RuntimeValue(
            output=node.input_type,
            value=signal,
            records=legacy_shaped_records,
        )
    }
    executor = TacticalQueryExecutor(compatibility_profile=GENERIC_EXECUTION_PROFILE)
    result = executor._execute_node(state=state, node=node, compatibility_profile=GENERIC_EXECUTION_PROFILE)  # noqa: SLF001
    windows = [
        (episode["temporal_status"], episode["start_frame_id"], episode["end_frame_id"])
        for episode in state.signals[node.node_id]["episodes"]
    ]
    return [
        pass_check(
            "temporal.generic_profile_never_shape_selects_legacy_adapter",
            "generic execution ignores legacy-shaped records and uses no compatibility adapter",
            {"windows": windows, "provenance": result.provenance},
        )
        if windows == [("PASS", 100, 102)] and result.provenance.get("adapter") is None
        else fail_check(
            "temporal.generic_profile_never_shape_selects_legacy_adapter",
            "generic execution changed under legacy-shaped records",
            {"windows": windows, "provenance": result.provenance},
        )
    ]


def validate_frame_length_mismatch_rejected() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        runtime_value_from_raw(
            node_id="frame_mismatch_probe",
            output=output(
                name="predicate",
                temporal_type=TemporalContainer.FRAME_SIGNAL,
                payload_type=PayloadType.BOOLEAN,
                cardinality=Cardinality.SINGLE,
                entity_scope=EntityScope.FRAME,
            ),
            raw_value=[True, False],
            frame_ids=[10, 11, 12],
        )
    except RuntimeError as error:
        checks.append(
            pass_check(
                "frame_signal.length_mismatch_rejected",
                "frame-signal values cannot silently fall back to synthetic frame IDs",
                {"error": str(error)},
            )
        )
    else:
        checks.append(
            fail_check(
                "frame_signal.length_mismatch_rejected",
                "frame-signal values with mismatched frame IDs were accepted",
            )
        )
    try:
        runtime_value_from_raw(
            node_id="frame_missing_ids_probe",
            output=output(
                name="predicate",
                temporal_type=TemporalContainer.FRAME_SIGNAL,
                payload_type=PayloadType.BOOLEAN,
                cardinality=Cardinality.SINGLE,
                entity_scope=EntityScope.FRAME,
            ),
            raw_value=[True, False],
        )
    except RuntimeError as error:
        checks.append(
            pass_check(
                "frame_signal.sequence_requires_explicit_frame_ids",
                "multi-valued frame signals cannot invent synthetic temporal identity",
                {"error": str(error)},
            )
        )
    else:
        checks.append(
            fail_check(
                "frame_signal.sequence_requires_explicit_frame_ids",
                "frame-signal sequence without frame IDs was accepted",
            )
        )
    return checks


def validate_generic_source_no_forbidden_assumptions() -> list[dict[str, Any]]:
    functions = [
        runtime_anchors,
        evaluate_target_in_state,
        predicate_persists_for,
    ]
    forbidden = ["wide_entry", "block_shift", "shift_gate"]
    hits: dict[str, list[str]] = {}
    for function in functions:
        source = inspect.getsource(function)
        found = [token for token in forbidden if token in source]
        if found:
            hits[function.__name__] = found
    return [
        pass_check(
            "generic_anchor_trace_source.no_m1_assumptions",
            "generic anchor/target code has no wide_entry, block_shift, or shift_gate assumptions",
            {"checked": [function.__name__ for function in functions]},
        )
        if not hits
        else fail_check(
            "generic_anchor_trace_source.no_m1_assumptions",
            "generic anchor/target code still contains M1-specific assumptions",
            {"hits": hits},
        )
    ]


def validate_node_execution_result_contract(
    executor: TacticalQueryExecutor,
    bound: Any,
) -> list[dict[str, Any]]:
    params = runtime_parameters(bound)
    state = executor._period_state(  # noqa: SLF001
        match_id="J03WOY",
        period="firstHalf",
        perspective_team_role=bound.perspective_team_role,
        recipe_id=bound.recipe_id,
        recipe_version=bound.recipe_version,
        params=params,
    )
    results = []
    for node in bound.nodes:
        result = executor._execute_node(state=state, node=node)  # noqa: SLF001
        results.append(result)
    input_counts = {result.node_id: len(result.inputs) for result in results}
    output_counts = {result.node_id: len(result.runtime_values) for result in results}
    explicit_source = inspect.getsource(execute_predicate_with_resolved_inputs)
    forbidden = ["state.runtime_values", "state.signals", "state.candidates", "state.accepted"]
    hits = [token for token in forbidden if token in explicit_source]
    return [
        pass_check(
            "nodes.execution_result_contract",
            "predicate execution receives explicit inputs and parameters and returns declared runtime values",
            {"input_counts": input_counts, "output_counts": output_counts},
        )
        if all(isinstance(result.outputs, dict) and result.runtime_values for result in results)
        and input_counts.get("outcome") == 1
        and not hits
        else fail_check(
            "nodes.execution_result_contract",
            "node execution result contract is incomplete",
            {"input_counts": input_counts, "output_counts": output_counts, "forbidden_hits": hits},
        )
    ]


def validate_approved_plan_parity(bound: Any, executor: TacticalQueryExecutor) -> list[dict[str, Any]]:
    execution = executor.execute(bound)
    rows = execution_result_rows(execution)
    return [
        pass_check(
            "approved_plan.parity_preserved",
            "approved plan still returns the frozen 180 results and 900 predicate traces",
            {"result_count": len(rows), "trace_count": len(execution.predicate_traces)},
        )
        if len(rows) == 180 and len(execution.predicate_traces) == 900
        else fail_check(
            "approved_plan.parity_preserved",
            "approved plan parity changed",
            {"result_count": len(rows), "trace_count": len(execution.predicate_traces)},
        )
    ]


def anchor_output() -> Any:
    return output(
        name="anchors",
        temporal_type=TemporalContainer.EPISODE_SET,
        payload_type=PayloadType.ANCHOR_REF,
        cardinality=Cardinality.COLLECTION,
        entity_scope=EntityScope.ANCHOR,
    )


def synthetic_anchor_record(frame_id: int) -> dict[str, Any]:
    payload = {
        "match_id": "synthetic",
        "period": "firstHalf",
        "anchor_frame_id": frame_id,
        "start_frame_id": frame_id - 5,
        "end_frame_id": frame_id + 5,
        "entity_refs": ["synthetic_entity"],
    }
    payload["anchor_id"] = anchor_record_id(
        match_id=str(payload["match_id"]),
        period=str(payload["period"]),
        anchor_frame_id=int(payload["anchor_frame_id"]),
        start_frame_id=int(payload["start_frame_id"]),
        end_frame_id=int(payload["end_frame_id"]),
        entity_refs=payload["entity_refs"],
    )
    return {
        **payload,
    }


def synthetic_period_state() -> PeriodState:
    return PeriodState(
        match_id="synthetic",
        period="firstHalf",
        params=RuntimeParameters(values={"analysis_rate_hz": 5}),
        recipe_id="synthetic_recipe",
        recipe_version="1.0.0",
        perspective_team_role="home",
        perspective_team_id="home_team",
        defending_team_role="away",
        defending_team_id="away_team",
        canonical_root=Path("."),
        raw_tracking=Path("."),
        positions=pd.DataFrame(),
        frame_ids=np.arange(100, 108, dtype=np.int64),
        ball_y=np.array([], dtype=float),
        possession_role=np.array([], dtype=object),
        ball_alive=np.array([], dtype=bool),
        defender_count=pd.Series(dtype=int),
        defender_centroid_y=pd.Series(dtype=float),
    )


def main() -> None:
    report = build_report()
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
