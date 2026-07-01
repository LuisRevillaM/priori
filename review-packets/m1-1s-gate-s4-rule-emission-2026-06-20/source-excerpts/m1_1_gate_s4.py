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
    execute_default_plan,
    execute_plan_from_path,
    execution_result_rows,
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
    checks.extend(validate_required_predicate_changes_inclusion())
    checks.extend(validate_unknown_policy_semantics(bound))
    checks.extend(validate_evidence_projection(rows))
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
        if row.get("matched_classification_rules") == [row.get("classification")]
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


def validate_required_predicate_changes_inclusion() -> list[dict[str, Any]]:
    baseline_rows = execution_result_rows(execute_plan_from_path(PLAN_PATH)[1])
    payload = plan_payload()
    for rule in payload["draft_plan"]["classification_rules"]:
        if rule["label"] == "DESTINATION_ENTERED":
            rule["predicate_ids"] = [
                predicate_id
                for predicate_id in rule["predicate_ids"]
                if predicate_id != "destination_region_entered"
            ]
    mutated = bind_document(TacticalQueryDocument.model_validate(payload))
    mutated_execution = TacticalQueryExecutor().execute(mutated)
    mutated_rows = execution_result_rows(mutated_execution)
    before = Counter(str(row["classification"]) for row in baseline_rows)
    after = Counter(str(row["classification"]) for row in mutated_rows)
    return [
        pass_check(
            "rules.required_predicate_changes_inclusion",
            "changing a required predicate changes inclusion while retaining declared labels",
            {"before": dict(sorted(before.items())), "after": dict(sorted(after.items()))},
        )
        if after != before and set(after).issubset(set(before))
        else fail_check(
            "rules.required_predicate_changes_inclusion",
            "predicate mutation did not change inclusion as expected",
            {"before": dict(sorted(before.items())), "after": dict(sorted(after.items()))},
        )
    ]


def validate_unknown_policy_semantics(bound: Any) -> list[dict[str, Any]]:
    traces = [
        PredicateTrace(predicate_id="p1", status="PASS"),
        PredicateTrace(predicate_id="p2", status="UNKNOWN"),
        PredicateTrace(predicate_id="p3", status="FAIL"),
    ]
    rules = [
        ClassificationRule(label="A_PASS_UNKNOWN", predicate_ids=["p1", "p2"], description="probe"),
        ClassificationRule(label="B_PASS_FAIL", predicate_ids=["p1", "p3"], description="probe"),
    ]
    checks: list[dict[str, Any]] = []
    for policy, expected in [
        (UnknownEvidencePolicy.EXCLUDE_CANDIDATE, []),
        (UnknownEvidencePolicy.INCLUDE_WITH_WARNING, ["A_PASS_UNKNOWN"]),
    ]:
        policy_bound = bound.model_copy(
            update={"unknown_evidence_policy": policy, "classification_rules": rules}
        )
        labels = rule_labels_for_traces(traces=traces, bound_plan=policy_bound)
        checks.append(
            pass_check(
                f"unknown_policy.{policy.value}",
                "unknown evidence policy controls rule labels",
                {"labels": labels},
            )
            if labels == expected
            else fail_check(
                f"unknown_policy.{policy.value}",
                "unknown evidence policy did not control labels",
                {"expected": expected, "actual": labels},
            )
        )
    return checks


def validate_evidence_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = [
        row["result_id"]
        for row in rows
        if not row.get("requested_evidence", {}).get("opposite_corridor.relation_id")
        or row.get("requested_evidence", {}).get("opposite_corridor.destination_region") is None
        or row.get("requested_evidence", {}).get("opposite_corridor.duration_seconds") is None
        or row.get("requested_evidence", {}).get("destination_entry.classification") != row["classification"]
    ]
    return [
        pass_check(
            "evidence.declared_runtime_outputs",
            "requested evidence resolves from declared runtime outputs",
            {"result_count": len(rows)},
        )
        if not failures and rows
        else fail_check(
            "evidence.declared_runtime_outputs",
            "one or more rows lack declared requested evidence",
            {"failure_sample": failures[:10], "result_count": len(rows)},
        )
    ]


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
