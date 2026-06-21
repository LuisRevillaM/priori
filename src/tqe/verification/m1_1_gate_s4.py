"""Verify M1.1S Gate S4: rule-driven generic result emission."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import (
    TacticalQueryExecutor,
    emit_generic_results_from_rules,
    execute_default_plan,
    execute_plan_from_path,
    execution_result_rows,
    runtime_parameters,
    rule_labels_for_traces,
)
from tqe.runtime.ir import (
    ClassificationRule,
    ExecutionMode,
    ExecutionStatus,
    PredicateTrace,
    TacticalQueryDocument,
    UnknownEvidencePolicy,
)

PLAN_PATH = Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
REPORT_PATH = Path("artifacts/m1.1/gate-s4-verification-report.json")


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

    checks.extend(validate_real_generic_rows(execution, rows))
    checks.extend(validate_classification_rules_control_labels(rows))
    checks.extend(validate_classification_conflict_semantics(bound))
    checks.extend(validate_required_predicate_changes_inclusion())
    checks.extend(validate_unknown_policy_semantics(bound))
    checks.extend(validate_evidence_projection(rows))
    checks.extend(validate_side_channel_perturbation_independence(bound))
    checks.extend(validate_no_required_m1_fields(rows))
    checks.extend(validate_generic_profile_and_no_legacy_adapter(execution))
    checks.extend(validate_determinism())
    checks.extend(validate_limits_and_modes(bound))
    checks.extend(validate_legacy_parity_is_explicit())

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S4_rule_driven_result_emission",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "execution": {
            "plan_path": str(PLAN_PATH),
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "result_count": len(rows),
            "trace_count": len(execution.predicate_traces),
            "compatibility_profile": execution.provenance.get("compatibility_profile"),
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_real_generic_rows(execution: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label = Counter(str(row["classification"]) for row in rows)
    return [
        pass_check(
            "generic.real_rows",
            "generic execution emits real QueryResult rows from canonical match data",
            {"result_count": len(rows), "by_label": dict(sorted(by_label.items()))},
        )
        if execution.status == ExecutionStatus.PASS
        and execution.provenance.get("compatibility_profile") == "generic"
        and len(rows) > 0
        else fail_check(
            "generic.real_rows",
            "generic execution did not emit real rows",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "compatibility_profile": execution.provenance.get("compatibility_profile"),
            },
        )
    ]


def validate_classification_rules_control_labels(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {str(row["classification"]) for row in rows}
    matched = [
        row
        for row in rows
        if row.get("classification") in set(row.get("matched_classification_rules") or [])
    ]
    expected = {"DESTINATION_ENTERED", "CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY"}
    return [
        pass_check(
            "rules.labels",
            "classification labels come from matching classification rules",
            {"labels": sorted(labels), "matched_count": len(matched)},
        )
        if expected.issubset(labels) and len(matched) == len(rows)
        else fail_check(
            "rules.labels",
            "classification labels are missing or not rule matched",
            {"labels": sorted(labels), "matched_count": len(matched), "result_count": len(rows)},
        )
    ]


def validate_classification_conflict_semantics(bound: Any) -> list[dict[str, Any]]:
    corridor = ClassificationRule(
        label="CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY",
        predicate_ids=["p1"],
        description="Equal-specificity first rule.",
    )
    destination = ClassificationRule(
        label="DESTINATION_ENTERED",
        predicate_ids=["p1"],
        description="Equal-specificity second rule.",
    )
    destination_specific = ClassificationRule(
        label="DESTINATION_ENTERED",
        predicate_ids=["p1", "p2"],
        description="More-specific rule.",
    )
    traces = [
        PredicateTrace(predicate_id="p1", status="PASS"),
        PredicateTrace(predicate_id="p2", status="PASS"),
    ]
    equal_forward = rule_labels_for_traces(
        traces=traces,
        bound_plan=bound.model_copy(update={"classification_rules": [corridor, destination]}),
    )
    equal_reverse = rule_labels_for_traces(
        traces=traces,
        bound_plan=bound.model_copy(update={"classification_rules": [destination, corridor]}),
    )
    specific_first = rule_labels_for_traces(
        traces=traces,
        bound_plan=bound.model_copy(update={"classification_rules": [corridor, destination_specific]}),
    )
    return [
        pass_check(
            "rules.conflict_semantics",
            "classification conflict resolution is explicit: specificity first, then plan order",
            {
                "equal_forward": equal_forward,
                "equal_reverse": equal_reverse,
                "specific_first": specific_first,
            },
        )
        if equal_forward[:2]
        == ["CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY", "DESTINATION_ENTERED"]
        and equal_reverse[:2] == ["DESTINATION_ENTERED", "CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY"]
        and specific_first[0] == "DESTINATION_ENTERED"
        else fail_check(
            "rules.conflict_semantics",
            "classification conflict resolution did not follow specificity and plan-order semantics",
            {
                "equal_forward": equal_forward,
                "equal_reverse": equal_reverse,
                "specific_first": specific_first,
            },
        )
    ]


def validate_required_predicate_changes_inclusion() -> list[dict[str, Any]]:
    payload = plan_payload()
    payload["draft_plan"]["classification_rules"] = [
        rule
        for rule in payload["draft_plan"]["classification_rules"]
        if rule["label"] == "DESTINATION_ENTERED"
    ]
    baseline = bind_document(TacticalQueryDocument.model_validate(payload))
    baseline_rows = execution_result_rows(TacticalQueryExecutor().execute(baseline))
    for node in payload["draft_plan"]["nodes"]:
        if node["node_id"] == "destination_region_entered":
            node["operator"] = {"name": "eq", "version": "1.0.0"}
    mutated = bind_document(TacticalQueryDocument.model_validate(payload))
    mutated_execution = TacticalQueryExecutor().execute(mutated)
    mutated_rows = execution_result_rows(mutated_execution)
    before = Counter(str(row["classification"]) for row in baseline_rows)
    after = Counter(str(row["classification"]) for row in mutated_rows)
    before_anchor_frames = {row["anchor_frame_id"] for row in baseline_rows}
    after_anchor_frames = {row["anchor_frame_id"] for row in mutated_rows}
    return [
        pass_check(
            "rules.required_predicate_changes_inclusion",
            "changing a required predicate from PASS to FAIL changes inclusion while retaining declared label",
            {
                "before": dict(sorted(before.items())),
                "after": dict(sorted(after.items())),
                "retained_anchor_count": len(before_anchor_frames.intersection(after_anchor_frames)),
            },
        )
        if after["DESTINATION_ENTERED"] < before["DESTINATION_ENTERED"]
        and set(after).issubset({"DESTINATION_ENTERED"})
        and not before_anchor_frames.intersection(after_anchor_frames)
        else fail_check(
            "rules.required_predicate_changes_inclusion",
            "predicate mutation did not change inclusion as expected",
            {
                "before": dict(sorted(before.items())),
                "after": dict(sorted(after.items())),
                "retained_anchor_count": len(before_anchor_frames.intersection(after_anchor_frames)),
            },
        )
    ]


def validate_unknown_policy_semantics(bound: Any) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for policy, expected_status, expect_results in [
        (UnknownEvidencePolicy.EXCLUDE_CANDIDATE, ExecutionStatus.PASS, False),
        (UnknownEvidencePolicy.INCLUDE_WITH_WARNING, ExecutionStatus.PASS, True),
        (UnknownEvidencePolicy.INVALIDATE_EXECUTION, ExecutionStatus.INCOMPLETE, False),
    ]:
        policy_bound = unknown_policy_probe_bound(policy)
        execution = TacticalQueryExecutor().execute(policy_bound)
        rows = execution_result_rows(execution)
        unknown_traces = [trace for trace in execution.predicate_traces if trace.status == "UNKNOWN"]
        checks.append(
            pass_check(
                f"unknown_policy.{policy.value}",
                "unknown evidence policy controls generic result emission end to end",
                {
                    "status": execution.status.value,
                    "result_count": len(rows),
                    "unknown_trace_count": len(unknown_traces),
                },
            )
            if execution.status == expected_status
            and bool(rows) is expect_results
            and bool(unknown_traces)
            else fail_check(
                f"unknown_policy.{policy.value}",
                "unknown evidence policy did not control generic execution end to end",
                {
                    "expected_status": expected_status.value,
                    "actual_status": execution.status.value,
                    "result_count": len(rows),
                    "unknown_trace_count": len(unknown_traces),
                },
            )
        )
    return checks


def unknown_policy_probe_bound(policy: UnknownEvidencePolicy) -> Any:
    payload = plan_payload()
    payload["draft_plan"]["unknown_evidence_policy"] = policy.value
    payload["draft_plan"]["anchor_source"] = {"source_node_id": "possession", "output_name": "anchors"}
    payload["draft_plan"]["requested_evidence"] = []
    payload["draft_plan"]["classification_rules"] = [
        {
            "label": "DESTINATION_ENTERED",
            "predicate_ids": ["destination_region_entered"],
            "description": "Probe anchors whose required destination predicate is unknown.",
        }
    ]
    return bind_document(TacticalQueryDocument.model_validate(payload))


def validate_evidence_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = [
        row["result_id"]
        for row in rows
        if not row.get("requested_evidence", {}).get("relation_id")
        or row.get("requested_evidence", {}).get("destination_region") is None
        or row.get("requested_evidence", {}).get("relation_duration_seconds") is None
        or row.get("requested_evidence", {}).get("destination_classification") != row["classification"]
    ]
    node_id_keys = [
        key
        for row in rows
        for key in row.get("requested_evidence", {})
        if "." in key
    ]
    return [
        pass_check(
            "evidence.declared_runtime_outputs",
            "requested evidence resolves through stable aliases from declared runtime outputs",
            {"result_count": len(rows)},
        )
        if not failures and not node_id_keys and rows
        else fail_check(
            "evidence.declared_runtime_outputs",
            "one or more rows lack declared requested evidence or expose node-ID keys",
            {"failure_sample": failures[:10], "node_id_keys": sorted(set(node_id_keys)), "result_count": len(rows)},
        )
    ]


def validate_side_channel_perturbation_independence(bound: Any) -> list[dict[str, Any]]:
    executor = TacticalQueryExecutor()
    params = runtime_parameters(bound)
    state = executor._execute_period(  # noqa: SLF001 - verifier intentionally inspects generic state.
        bound_plan=bound,
        match_id=bound.match_ids[0],
        period=bound.periods[0],
        params=params,
    )
    before_results, before_traces = emit_generic_results_from_rules(
        state=state,
        bound_plan=bound,
        compatibility_profile="generic",
    )
    state.candidates = [{"result_id": "poison_candidate"}]
    state.accepted = [{"result_id": "poison_accepted"}]
    state.predicate_traces = [PredicateTrace(predicate_id="poison", status="FAIL")]
    for outputs in state.runtime_values.values():
        for runtime_value in outputs.values():
            for record in runtime_value.records:
                record["_runtime_result"] = {"classification": "POISON"}
                record["_predicate_status"] = {"poison": {"status": "PASS"}}
            if isinstance(runtime_value.value, list):
                for item in runtime_value.value:
                    if isinstance(item, dict):
                        item["_runtime_result"] = {"classification": "POISON"}
                        item["_predicate_status"] = {"poison": {"status": "PASS"}}
    after_results, after_traces = emit_generic_results_from_rules(
        state=state,
        bound_plan=bound,
        compatibility_profile="generic",
    )
    before = normalized_generic_emission(before_results, before_traces)
    after = normalized_generic_emission(after_results, after_traces)
    return [
        pass_check(
            "generic.side_channels_ignored",
            "generic emitted rows, classifications, and traces ignore legacy side channels",
            {"result_count": len(before_results), "trace_count": len(before_traces)},
        )
        if before == after and before_results
        else fail_check(
            "generic.side_channels_ignored",
            "generic emission changed after side-channel perturbation",
            {"before_result_count": len(before_results), "after_result_count": len(after_results)},
        )
    ]


def normalized_generic_emission(
    results: list[dict[str, Any]],
    traces: list[PredicateTrace],
) -> dict[str, Any]:
    return {
        "results": [
            {
                "result_id": result["result_id"],
                "classification": result["classification"],
                "anchor_frame_id": result["anchor_frame_id"],
                "requested_evidence": result.get("requested_evidence"),
            }
            for result in results
        ],
        "traces": [
            {
                "predicate_id": trace.predicate_id,
                "status": trace.status,
                "frame_id": trace.frame_id,
                "result_id": trace.source_evidence.get("result_id"),
            }
            for trace in traces
        ],
    }


def validate_no_required_m1_fields(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    forbidden = {"block_shift_score", "wide_entry_frame_id", "signed_shift_metres"}
    violations = [
        {"result_id": row["result_id"], "fields": sorted(forbidden.intersection(row))}
        for row in rows
        if forbidden.intersection(row)
    ]
    return [
        pass_check(
            "generic.no_required_m1_fields",
            "generic result rows do not expose required M1 result fields",
        )
        if not violations
        else fail_check(
            "generic.no_required_m1_fields",
            "generic result rows still expose M1-specific fields",
            {"violations": violations[:10]},
        )
    ]


def validate_generic_profile_and_no_legacy_adapter(execution: Any) -> list[dict[str, Any]]:
    adapter_hits = [
        trace.model_dump(mode="json", exclude_none=True)
        for trace in execution.predicate_traces
        if "legacy_m1" in json.dumps(trace.source_evidence, sort_keys=True)
    ]
    return [
        pass_check(
            "generic.no_legacy_adapter",
            "generic execution reports generic profile and traces contain no legacy adapter evidence",
            {"trace_count": len(execution.predicate_traces)},
        )
        if execution.provenance.get("compatibility_profile") == "generic" and not adapter_hits
        else fail_check(
            "generic.no_legacy_adapter",
            "generic execution used or reported legacy behavior",
            {
                "compatibility_profile": execution.provenance.get("compatibility_profile"),
                "adapter_hit_count": len(adapter_hits),
            },
        )
    ]


def validate_determinism() -> list[dict[str, Any]]:
    first_rows = execution_result_rows(execute_plan_from_path(PLAN_PATH)[1])
    second_rows = execution_result_rows(execute_plan_from_path(PLAN_PATH)[1])
    first_ids = [row["result_id"] for row in first_rows]
    second_ids = [row["result_id"] for row in second_rows]
    return [
        pass_check(
            "execution.deterministic_ids_order",
            "generic result IDs and ordering are deterministic",
            {"result_count": len(first_ids)},
        )
        if first_ids == second_ids and first_ids
        else fail_check(
            "execution.deterministic_ids_order",
            "generic result IDs or ordering changed across runs",
            {"first": first_ids[:10], "second": second_ids[:10]},
        )
    ]


def validate_limits_and_modes(bound: Any) -> list[dict[str, Any]]:
    executor = TacticalQueryExecutor()
    limited = executor.execute(bound.model_copy(update={"max_results": 3}))
    bind_only = executor.execute(bound.model_copy(update={"execution_mode": ExecutionMode.BIND_ONLY}))
    dry_run = executor.execute(bound.model_copy(update={"execution_mode": ExecutionMode.DRY_RUN}))
    checks = [
        pass_check(
            "execution.max_results",
            "generic max_results truncates emitted results",
            {"result_count": len(limited.results)},
        )
        if len(limited.results) == 3
        else fail_check(
            "execution.max_results",
            "generic max_results was not honored",
            {"result_count": len(limited.results)},
        ),
        pass_check("execution.bind_only", "bind_only does not execute results")
        if bind_only.status == ExecutionStatus.NOT_STARTED and not bind_only.results
        else fail_check("execution.bind_only", "bind_only emitted results"),
        pass_check("execution.dry_run", "dry_run validates without results")
        if dry_run.status == ExecutionStatus.PASS and not dry_run.results
        else fail_check("execution.dry_run", "dry_run emitted results or failed"),
    ]
    return checks


def validate_legacy_parity_is_explicit() -> list[dict[str, Any]]:
    _bound, execution = execute_default_plan()
    rows = execution_result_rows(execution)
    return [
        pass_check(
            "legacy.explicit_parity_preserved",
            "frozen M1 parity remains exact through the explicit legacy helper",
            {
                "result_count": len(rows),
                "trace_count": len(execution.predicate_traces),
                "compatibility_profile": execution.provenance.get("compatibility_profile"),
            },
        )
        if len(rows) == 180
        and len(execution.predicate_traces) == 900
        and execution.provenance.get("compatibility_profile") == "legacy_m1_parity"
        else fail_check(
            "legacy.explicit_parity_preserved",
            "legacy helper did not preserve frozen parity",
            {
                "result_count": len(rows),
                "trace_count": len(execution.predicate_traces),
                "compatibility_profile": execution.provenance.get("compatibility_profile"),
            },
        )
    ]


def plan_payload() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
