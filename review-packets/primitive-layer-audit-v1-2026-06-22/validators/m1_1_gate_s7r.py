"""Verify M1.1S Gate S7R: relation coverage and witness semantics."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import BindError, bind_document
from tqe.runtime.executor import (
    MatchContext,
    TacticalQueryExecutor,
    apply_result_semantics,
    execute_plan_from_path,
    execute_predicate_with_resolved_inputs,
    execution_result_rows,
    project_requested_evidence_from_runtime,
    runtime_parameters,
)
from tqe.runtime.ir import (
    BoundPredicateNode,
    EvaluationTarget,
    ExecutionStatus,
    PayloadType,
    PredicateTrace,
    TacticalQueryDocument,
    TypedValue,
    Unit,
    UnknownEvidencePolicy,
)
from tqe.runtime.relations import anchor_evaluation_for_result
from tqe.runtime.values import RuntimeValue

PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
REPORT_PATH = Path("artifacts/m1.1/gate-s7r-verification-report.json")


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
    bound, execution = execute_plan_from_path(PLAN_PATH)
    rows = execution_result_rows(execution)
    executor = TacticalQueryExecutor()
    params = runtime_parameters(bound)
    state = executor._execute_period(  # noqa: SLF001 - verifier inspects runtime contract.
        bound_plan=bound,
        match_id=bound.match_ids[0],
        period=bound.periods[0],
        params=params,
    )
    coverage = state.runtime_values["progressive_corridor"]["anchor_evaluations"].value
    episodes = state.runtime_values["progressive_corridor"]["episodes"].value

    checks.extend(validate_plan_uses_coverage(bound, rows, execution.predicate_traces))
    checks.extend(validate_canonical_pass_fail_coverage(coverage))
    checks.extend(validate_mixed_relation_evidence_semantics())
    checks.extend(validate_tightened_threshold_fails())
    checks.extend(validate_unknown_coverage_predicates(bound, state))
    checks.extend(validate_unknown_policy_semantics(bound))
    checks.extend(validate_witness_evidence(state, bound, coverage, episodes, rows))
    checks.extend(validate_witness_evidence_is_source_scoped(state, bound, coverage, episodes))
    checks.extend(validate_count_at_least_anchor_relative(bound, state))
    checks.extend(validate_raw_relation_episode_inputs_rejected())
    checks.extend(validate_non_match_inspection_failure())
    checks.extend(validate_agent_safety_limits())
    checks.extend(validate_warning_rule_preservation(bound))

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S7R2_relation_coverage_witness_agent_safety",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "execution": {
            "plan_path": str(PLAN_PATH),
            "result_count": len(rows),
            "trace_count": len(execution.predicate_traces),
            "coverage_status_counts": dict(sorted(Counter(item["evaluation_status"] for item in coverage).items())),
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_plan_uses_coverage(bound: Any, rows: list[dict[str, Any]], traces: list[Any]) -> list[dict[str, Any]]:
    predicate = next(node for node in bound.nodes if isinstance(node, BoundPredicateNode))
    trace_witnesses = [
        trace.source_evidence.get("witness_relation_id")
        for trace in traces
        if trace.predicate_id == "has_progressive_corridor"
    ]
    valid = (
        predicate.input.source_node_id == "progressive_corridor"
        and predicate.input.output_name == "anchor_evaluations"
        and rows
        and trace_witnesses
        and all(item for item in trace_witnesses)
    )
    return [
        pass_check(
            "s7r.plan_predicate_consumes_anchor_evaluations",
            "S6 exists predicate consumes declared anchor coverage and traces witness IDs",
            {"result_count": len(rows), "witness_count": len(trace_witnesses)},
        )
        if valid
        else fail_check(
            "s7r.plan_predicate_consumes_anchor_evaluations",
            "S6 exists predicate still lacks coverage or witness trace evidence",
            {"input": f"{predicate.input.source_node_id}.{predicate.input.output_name}", "witnesses": trace_witnesses[:5]},
        )
    ]


def validate_canonical_pass_fail_coverage(coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(item["evaluation_status"] for item in coverage)
    fail_record = next((item for item in coverage if item["evaluation_status"] == "FAIL"), None)
    pass_record = next((item for item in coverage if item["evaluation_status"] == "PASS"), None)
    valid = (
        counts["PASS"] > 0
        and counts["FAIL"] > 0
        and pass_record is not None
        and pass_record.get("witness_relation_id")
        and fail_record is not None
        and fail_record.get("relation_count") == 0
        and fail_record.get("witness_relation_id") is None
    )
    return [
        pass_check(
            "s7r.canonical_relation_coverage_pass_fail",
            "canonical possession anchors produce explicit PASS and definitive FAIL relation coverage",
            {"counts": dict(sorted(counts.items()))},
        )
        if valid
        else fail_check(
            "s7r.canonical_relation_coverage_pass_fail",
            "canonical coverage does not distinguish PASS and FAIL correctly",
            {"counts": dict(sorted(counts.items())), "fail_record": fail_record},
        )
    ]


def validate_tightened_threshold_fails() -> list[dict[str, Any]]:
    payload = plan_payload()
    for parameter in payload["recipe"]["parameters"]:
        if parameter["name"] == "corridor_minimum_clearance_m":
            parameter["default"] = {"payload_type": "number", "unit": "metre", "value": 40.0}
    bound = bind_document(TacticalQueryDocument.model_validate(payload))
    executor = TacticalQueryExecutor()
    state = executor._execute_period(  # noqa: SLF001
        bound_plan=bound,
        match_id=bound.match_ids[0],
        period=bound.periods[0],
        params=runtime_parameters(bound),
    )
    coverage = state.runtime_values["progressive_corridor"]["anchor_evaluations"].value
    counts = Counter(item["evaluation_status"] for item in coverage)
    rows = execution_result_rows(executor.execute(bound))
    return [
        pass_check(
            "s7r.threshold_tightening_yields_fail_not_unknown",
            "tightening relation clearance turns evaluated anchors into FAIL rather than UNKNOWN",
            {"coverage_counts": dict(sorted(counts.items())), "result_count": len(rows)},
        )
        if counts["FAIL"] > 0 and counts["UNKNOWN"] == 0 and len(rows) == 0
        else fail_check(
            "s7r.threshold_tightening_yields_fail_not_unknown",
            "tightened relation threshold did not produce definitive failed coverage",
            {"coverage_counts": dict(sorted(counts.items())), "result_count": len(rows)},
        )
    ]


def validate_mixed_relation_evidence_semantics() -> list[dict[str, Any]]:
    result = {
        "result_id": "synthetic_anchor",
        "match_id": "J03WOY",
        "period": "firstHalf",
        "perspective_team_role": "home",
        "defending_team_role": "away",
        "anchor_frame_id": 100,
    }
    mixed_fail = anchor_evaluation_for_result(result, [], Counter({"FAIL": 100, "UNKNOWN": 1}))
    mixed_pass_without_episode = anchor_evaluation_for_result(result, [], Counter({"PASS": 1, "UNKNOWN": 1}))
    clean_fail = anchor_evaluation_for_result(result, [], Counter({"FAIL": 101}))
    proven_pass = anchor_evaluation_for_result(
        result,
        [
            {
                "relation_id": "rel_proven",
                "duration_seconds": 0.4,
                "minimum_clearance_m": 7.0,
                "open_frame_id": 100,
            }
        ],
        Counter({"PASS": 2, "UNKNOWN": 1}),
    )
    valid = (
        mixed_fail["evaluation_status"] == "UNKNOWN"
        and mixed_pass_without_episode["evaluation_status"] == "UNKNOWN"
        and clean_fail["evaluation_status"] == "FAIL"
        and proven_pass["evaluation_status"] == "PASS"
        and proven_pass["witness_relation_id"] == "rel_proven"
    )
    return [
        pass_check(
            "s7r2.mixed_relation_evidence_unknown_semantics",
            "mixed missing relation evidence becomes UNKNOWN unless a qualifying relation is proven",
            {
                "mixed_fail_status": mixed_fail["evaluation_status"],
                "mixed_pass_without_episode_status": mixed_pass_without_episode["evaluation_status"],
                "clean_fail_status": clean_fail["evaluation_status"],
                "proven_pass_status": proven_pass["evaluation_status"],
            },
        )
        if valid
        else fail_check(
            "s7r2.mixed_relation_evidence_unknown_semantics",
            "mixed relation evidence did not preserve UNKNOWN/PASS/FAIL semantics",
            {
                "mixed_fail": mixed_fail,
                "mixed_pass_without_episode": mixed_pass_without_episode,
                "clean_fail": clean_fail,
                "proven_pass": proven_pass,
            },
        )
    ]


def validate_unknown_coverage_predicates(bound: Any, state: Any) -> list[dict[str, Any]]:
    predicate = next(node for node in bound.nodes if isinstance(node, BoundPredicateNode))
    runtime_output = state.runtime_values["progressive_corridor"]["anchor_evaluations"].output
    records = [
        coverage_record("a_pass", 100, "PASS", relation_count=2, witness_relation_id="rel_pass"),
        coverage_record("a_fail", 200, "FAIL", relation_count=0, witness_relation_id=None),
        coverage_record("a_unknown", 300, "UNKNOWN", relation_count=0, witness_relation_id=None),
    ]
    output = execute_predicate_with_resolved_inputs(
        context=MatchContext(
            match_id=bound.match_ids[0],
            period=bound.periods[0],
            frame_ids=(100, 200, 300),
            params=runtime_parameters(bound),
        ),
        node=predicate,
        inputs={"anchor_evaluations": RuntimeValue(output=runtime_output, value=records)},
        parameters={},
    )
    statuses = [record["status"] for record in output["predicate_records"]]
    witnesses = [record["source_evidence"].get("witness_relation_id") for record in output["predicate_records"]]
    return [
        pass_check(
            "s7r.exists_tristate_from_anchor_coverage",
            "exists maps anchor coverage to PASS, FAIL, and UNKNOWN without collapsing absence",
            {"statuses": statuses, "witnesses": witnesses},
        )
        if statuses == ["PASS", "FAIL", "UNKNOWN"] and witnesses[0] == "rel_pass"
        else fail_check(
            "s7r.exists_tristate_from_anchor_coverage",
            "exists did not preserve tri-state anchor coverage",
            {"statuses": statuses, "witnesses": witnesses},
        )
    ]


def validate_unknown_policy_semantics(bound: Any) -> list[dict[str, Any]]:
    traces = [
        PredicateTrace(
            predicate_id="has_progressive_corridor",
            status="UNKNOWN",
            value=None,
            threshold=None,
            unit=Unit.NONE,
            frame_id=100,
            source_evidence={"result_id": "r1"},
        )
    ]
    result = {
        "result_id": "r1",
        "classification": "PROGRESSIVE_CORRIDOR_AVAILABLE",
        "match_id": bound.match_ids[0],
        "period": bound.periods[0],
        "anchor_frame_id": 100,
        "classification_rule_decisions": [
            {
                "label": "PROGRESSIVE_CORRIDOR_AVAILABLE",
                "rule_match_status": "WARNING",
                "unknown_required_predicates": ["has_progressive_corridor"],
            }
        ],
    }
    outcomes: dict[str, Any] = {}
    policies = {
        "exclude_candidate": UnknownEvidencePolicy.EXCLUDE_CANDIDATE,
        "include_with_warning": UnknownEvidencePolicy.INCLUDE_WITH_WARNING,
        "invalidate_execution": UnknownEvidencePolicy.INVALIDATE_EXECUTION,
    }
    for policy, enum_value in policies.items():
        policy_bound = bound.model_copy(update={"unknown_evidence_policy": enum_value})
        kept, kept_traces, status = apply_result_semantics(
            results=[deepcopy(result)],
            trace_records=traces,
            bound_plan=policy_bound,
        )
        outcomes[policy] = {
            "result_count": len(kept),
            "trace_count": len(kept_traces),
            "status": status.value,
        }
    valid = (
        outcomes["exclude_candidate"]["result_count"] == 0
        and outcomes["include_with_warning"]["result_count"] == 1
        and outcomes["include_with_warning"]["status"] == "pass"
        and outcomes["invalidate_execution"]["status"] == "incomplete"
    )
    return [
        pass_check(
            "s7r.unknown_policy_semantics",
            "unknown evidence policies behave distinctly for genuine UNKNOWN predicate traces",
            outcomes,
        )
        if valid
        else fail_check(
            "s7r.unknown_policy_semantics",
            "unknown evidence policies did not behave as required",
            outcomes,
        )
    ]


def validate_witness_evidence(
    state: Any,
    bound: Any,
    coverage: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    episodes_by_result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        episodes_by_result[str(episode["result_id"])].append(episode)
    multi = next(
        item for item in coverage
        if item["evaluation_status"] == "PASS" and len(episodes_by_result[str(item["result_id"])]) > 1
    )
    anchor = next(anchor for anchor in runtime_anchors_for_state(state, bound) if anchor.anchor_id == multi["anchor_id"])
    before = project_requested_evidence_from_runtime(state=state, anchor=anchor, bound_plan=bound)
    state.runtime_values["progressive_corridor"]["episodes"] = RuntimeValue(
        output=state.runtime_values["progressive_corridor"]["episodes"].output,
        value=list(reversed(episodes)),
    )
    after = project_requested_evidence_from_runtime(state=state, anchor=anchor, bound_plan=bound)
    valid = (
        before == after
        and before.get("relation_id") == multi.get("witness_relation_id")
        and any(row.get("requested_evidence", {}).get("relation_id") == multi.get("witness_relation_id") for row in rows)
    )
    return [
        pass_check(
            "s7r.witness_relation_controls_evidence",
            "multiple relation episodes project evidence from the declared witness, independent of list order",
            {"anchor_id": multi["anchor_id"], "witness_relation_id": multi.get("witness_relation_id")},
        )
        if valid
        else fail_check(
            "s7r.witness_relation_controls_evidence",
            "requested evidence changed under episode reordering or ignored the witness",
            {"before": before, "after": after, "witness": multi.get("witness_relation_id")},
        )
    ]


def validate_witness_evidence_is_source_scoped(
    state: Any,
    bound: Any,
    coverage: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    episodes_by_result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        episodes_by_result[str(episode["result_id"])].append(episode)
    multi = next(
        item for item in coverage
        if item["evaluation_status"] == "PASS" and len(episodes_by_result[str(item["result_id"])]) > 1
    )
    anchor = next(anchor for anchor in runtime_anchors_for_state(state, bound) if anchor.anchor_id == multi["anchor_id"])
    wrong_relation_id = "wrong_relation_for_same_anchor"
    anchor_eval_output = state.runtime_values["progressive_corridor"]["anchor_evaluations"].output
    episode_output = state.runtime_values["progressive_corridor"]["episodes"].output
    fake_predicate_record = {
        "predicate_id": "other_relation_exists",
        "status": "PASS",
        "value": {"payload_type": "boolean", "unit": "none", "value": True},
        "threshold": None,
        "unit": "none",
        "frame_id": anchor.anchor_frame_id,
        "source_evidence": {
            "source_node_id": "other_relation",
            "source_output_name": "anchor_evaluations",
            "witness_relation_id": wrong_relation_id,
        },
        "source_record": {
            "anchor_id": anchor.anchor_id,
            "anchor_frame_id": anchor.anchor_frame_id,
            "result_id": anchor.anchor_id,
        },
    }
    fake_episode = {
        "relation_id": wrong_relation_id,
        "result_id": anchor.anchor_id,
        "anchor_id": anchor.anchor_id,
        "anchor_frame_id": anchor.anchor_frame_id,
        "target_player_id": "wrong_target",
        "destination_region": "wrong_region",
        "duration_seconds": 9.9,
        "minimum_clearance_m": 99.0,
    }
    original_runtime_values = state.runtime_values
    try:
        state.runtime_values = {
            "other_relation": {
                "predicate": RuntimeValue(output=anchor_eval_output, value=[fake_predicate_record]),
                "anchor_evaluations": RuntimeValue(
                    output=anchor_eval_output,
                    value=[
                        {
                            "anchor_id": anchor.anchor_id,
                            "anchor_frame_id": anchor.anchor_frame_id,
                            "result_id": anchor.anchor_id,
                            "evaluation_status": "PASS",
                            "relation_count": 1,
                            "witness_relation_id": wrong_relation_id,
                        }
                    ],
                ),
                "episodes": RuntimeValue(output=episode_output, value=[fake_episode]),
            },
            **original_runtime_values,
        }
        projected = project_requested_evidence_from_runtime(state=state, anchor=anchor, bound_plan=bound)
    finally:
        state.runtime_values = original_runtime_values
    valid = projected.get("relation_id") == multi.get("witness_relation_id") and projected.get("relation_id") != wrong_relation_id
    return [
        pass_check(
            "s7r2.witness_selection_scoped_to_evidence_source",
            "relation evidence uses the witness from its requested source node, not another relation node",
            {
                "projected_relation_id": projected.get("relation_id"),
                "expected_relation_id": multi.get("witness_relation_id"),
                "wrong_relation_id": wrong_relation_id,
            },
        )
        if valid
        else fail_check(
            "s7r2.witness_selection_scoped_to_evidence_source",
            "relation evidence used a witness from the wrong source",
            {"projected": projected, "expected": multi.get("witness_relation_id"), "wrong": wrong_relation_id},
        )
    ]


def validate_count_at_least_anchor_relative(bound: Any, state: Any) -> list[dict[str, Any]]:
    predicate = next(node for node in bound.nodes if isinstance(node, BoundPredicateNode))
    count_node = predicate.model_copy(update={"operator": predicate.operator.model_copy(update={"name": "count_at_least"})})
    runtime_value = state.runtime_values["progressive_corridor"]["anchor_evaluations"]
    output = execute_predicate_with_resolved_inputs(
        context=MatchContext(
            match_id=bound.match_ids[0],
            period=bound.periods[0],
            frame_ids=tuple(int(frame_id) for frame_id in state.frame_ids),
            params=runtime_parameters(bound),
        ),
        node=count_node,
        inputs={"anchor_evaluations": runtime_value},
        parameters={"compare": count_threshold(2)},
    )
    statuses = Counter(record["status"] for record in output["predicate_records"])
    valid = statuses["PASS"] > 0 and statuses["FAIL"] > 0 and statuses["UNKNOWN"] == 0
    return [
        pass_check(
            "s7r.count_at_least_anchor_relative_tristate",
            "count_at_least compares relation_count per anchor rather than global collection size",
            {"statuses": dict(sorted(statuses.items()))},
        )
        if valid
        else fail_check(
            "s7r.count_at_least_anchor_relative_tristate",
            "count_at_least did not behave as anchor-relative tri-state predicate",
            {"statuses": dict(sorted(statuses.items()))},
        )
    ]


def validate_raw_relation_episode_inputs_rejected() -> list[dict[str, Any]]:
    exists_payload = plan_payload()
    exists_payload["draft_plan"]["nodes"][2]["input"]["output_name"] = "episodes"
    exists_failed = False
    try:
        bind_document(TacticalQueryDocument.model_validate(exists_payload))
    except BindError:
        exists_failed = True

    count_payload = plan_payload()
    count_payload["draft_plan"]["nodes"][2]["input"]["output_name"] = "episodes"
    count_payload["draft_plan"]["nodes"][2]["operator"] = {"name": "count_at_least", "version": "1.0.0"}
    count_payload["draft_plan"]["nodes"][2]["compare"] = {
        "payload_type": "number",
        "unit": "count",
        "value": 1,
    }
    count_failed = False
    try:
        bind_document(TacticalQueryDocument.model_validate(count_payload))
    except BindError:
        count_failed = True

    valid = exists_failed and count_failed
    return [
        pass_check(
            "s7r2.raw_relation_episode_collection_predicates_rejected",
            "agent-visible exists/count_at_least reject raw relation episode inputs",
            {"exists_failed": exists_failed, "count_at_least_failed": count_failed},
        )
        if valid
        else fail_check(
            "s7r2.raw_relation_episode_collection_predicates_rejected",
            "raw relation episode predicates still bind successfully",
            {"exists_failed": exists_failed, "count_at_least_failed": count_failed},
        )
    ]


def validate_non_match_inspection_failure() -> list[dict[str, Any]]:
    payload = plan_payload()
    for parameter in payload["recipe"]["parameters"]:
        if parameter["name"] == "corridor_minimum_clearance_m":
            parameter["default"] = {"payload_type": "number", "unit": "metre", "value": 40.0}
    bound = bind_document(TacticalQueryDocument.model_validate(payload))
    executor = TacticalQueryExecutor()
    state = executor._execute_period(  # noqa: SLF001
        bound_plan=bound,
        match_id=bound.match_ids[0],
        period=bound.periods[0],
        params=runtime_parameters(bound),
    )
    fail_record = next(item for item in state.runtime_values["progressive_corridor"]["anchor_evaluations"].value if item["evaluation_status"] == "FAIL")
    inspection = executor.evaluate_target(
        bound,
        EvaluationTarget(
            target_id="s7r_fail_anchor",
            match_id=str(fail_record["match_id"]),
            period=str(fail_record["period"]),
            approximate_time_ms=int(round(int(fail_record["anchor_frame_id"]) / 25.0 * 1000.0)),
            search_radius_ms=40,
        ),
    )
    statuses = [item["status"] for item in inspection.get("failed_predicates", [])]
    return [
        pass_check(
            "s7r.generic_non_match_inspection_definitive_fail",
            "generic target inspection reports definitive FAIL for evaluated no-corridor anchors",
            {"inspection_status": inspection.get("status"), "failed_statuses": statuses},
        )
        if inspection.get("status") == "NON_MATCH" and "FAIL" in statuses
        else fail_check(
            "s7r.generic_non_match_inspection_definitive_fail",
            "generic inspection did not expose definitive failed relation predicate",
            {"inspection": inspection},
        )
    ]


def validate_agent_safety_limits() -> list[dict[str, Any]]:
    payload = plan_payload()
    payload["draft_plan"]["complexity_limits"]["max_relations_per_anchor"] = 1
    runtime_failed = False
    runtime_message = ""
    try:
        TacticalQueryExecutor().execute(bind_document(TacticalQueryDocument.model_validate(payload)))
    except RuntimeError as error:
        runtime_failed = "max_relations_per_anchor" in str(error)
        runtime_message = str(error)

    static_payload = plan_payload()
    static_payload["draft_plan"]["complexity_limits"]["max_execution_cost"] = 1
    static_failed = False
    try:
        bind_document(TacticalQueryDocument.model_validate(static_payload))
    except BindError as error:
        static_failed = "complexity_execution_cost_exceeded" in {issue.code for issue in error.issues}

    ceiling_payload = plan_payload()
    ceiling_payload["draft_plan"]["complexity_limits"]["max_execution_cost"] = 1_000_000_000
    ceiling_payload["draft_plan"]["complexity_limits"]["max_relations_per_anchor"] = 1_000_000
    ceiling_failed = False
    ceiling_codes: set[str] = set()
    try:
        bind_document(TacticalQueryDocument.model_validate(ceiling_payload))
    except BindError as error:
        ceiling_codes = {issue.code for issue in error.issues}
        ceiling_failed = {
            "complexity_max_execution_cost_ceiling_exceeded",
            "complexity_max_relations_per_anchor_ceiling_exceeded",
        }.issubset(ceiling_codes)

    valid = runtime_failed and static_failed and ceiling_failed
    return [
        pass_check(
            "s7r.agent_safety_limits_enforced",
            "relation expansion, execution-cost, and trusted host ceilings fail visibly",
            {
                "runtime_message": runtime_message,
                "static_failed": static_failed,
                "ceiling_codes": sorted(ceiling_codes),
            },
        )
        if valid
        else fail_check(
            "s7r.agent_safety_limits_enforced",
            "agent safety limits are not enforced visibly",
            {
                "runtime_message": runtime_message,
                "runtime_failed": runtime_failed,
                "static_failed": static_failed,
                "ceiling_failed": ceiling_failed,
                "ceiling_codes": sorted(ceiling_codes),
            },
        )
    ]


def validate_warning_rule_preservation(bound: Any) -> list[dict[str, Any]]:
    traces = [
        PredicateTrace(
            predicate_id="has_progressive_corridor",
            status="UNKNOWN",
            value=None,
            threshold=None,
            unit=Unit.NONE,
            frame_id=100,
            source_evidence={"result_id": "r_warning"},
        )
    ]
    result = {
        "result_id": "r_warning",
        "classification": "PROGRESSIVE_CORRIDOR_AVAILABLE",
        "match_id": bound.match_ids[0],
        "period": bound.periods[0],
        "anchor_frame_id": 100,
        "classification_rule_decisions": [
            {
                "label": "PROGRESSIVE_CORRIDOR_AVAILABLE",
                "rule_match_status": "WARNING",
                "unknown_required_predicates": ["has_progressive_corridor"],
            }
        ],
        "rule_match_status": "WARNING",
        "unknown_required_predicates": ["has_progressive_corridor"],
    }
    policy_bound = bound.model_copy(update={"unknown_evidence_policy": UnknownEvidencePolicy.INCLUDE_WITH_WARNING})
    kept, _traces, status = apply_result_semantics(
        results=[result],
        trace_records=traces,
        bound_plan=policy_bound,
    )
    valid = (
        status == ExecutionStatus.PASS
        and len(kept) == 1
        and kept[0].get("matched_classification_rules") == ["PROGRESSIVE_CORRIDOR_AVAILABLE"]
        and kept[0].get("rule_match_status") == "WARNING"
        and kept[0].get("unknown_required_predicates") == ["has_progressive_corridor"]
    )
    return [
        pass_check(
            "s7r.include_warning_rule_decision_preserved",
            "INCLUDE_WITH_WARNING preserves rule decision and unknown required predicates",
            {"kept": kept},
        )
        if valid
        else fail_check(
            "s7r.include_warning_rule_decision_preserved",
            "warning rule decision was lost or recomputed as PASS-only",
            {"kept": kept, "status": status.value},
        )
    ]


def coverage_record(
    anchor_id: str,
    frame_id: int,
    status: str,
    *,
    relation_count: int,
    witness_relation_id: str | None,
) -> dict[str, Any]:
    return {
        "result_id": anchor_id,
        "anchor_id": anchor_id,
        "match_id": "J03WOY",
        "period": "firstHalf",
        "anchor_frame_id": frame_id,
        "evaluation_status": status,
        "relation_count": relation_count,
        "witness_relation_id": witness_relation_id,
        "unknown_reason": "synthetic_unavailable" if status == "UNKNOWN" else None,
    }


def count_threshold(value: int) -> Any:
    return TypedValue(payload_type=PayloadType.NUMBER, value=value, unit=Unit.COUNT)


def runtime_anchors_for_state(state: Any, bound: Any) -> list[Any]:
    from tqe.runtime.executor import runtime_anchors

    return runtime_anchors(state, bound.anchor_source)


def plan_payload() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
