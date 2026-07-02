"""AFL-08 marking proximity gap-closure verifier.

This slice closes observed nearest-opposition proximity for marked/unmarked
player queries. It deliberately does not close marker assignment, marking
scheme, man-vs-zone responsibility, role, intent, quality, or causation.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import (
    DEFAULT_CANONICAL_ROOT,
    DEFAULT_RAW_ROOT,
    GENERIC_EXECUTION_PROFILE,
    TacticalQueryExecutor,
    execution_result_rows,
    marking_anchor_record,
    runtime_parameters,
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import generate_scp0_artifacts
from tqe.write_mode import output_path, write_mode


REPORT_PATH = Path("artifacts/autonomous/afl-marking-verification-report.json")
SEARCH_ROW_LEDGER_PATH = Path("generated/semantic-contract-scl0/search-run/row-ledger.json")
MARKING_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_017_blind_a_v0.json")
THRESHOLD_VERSION = (
    "marking.v0.1.0:"
    "frame=anchor_frame_id:"
    "target=receiver_id:"
    "candidate_scope=opposition_outfield_to_anchor_team:"
    "max_distance=3.0:"
    "min_observed_candidates=6:"
    "model=nearest_observed_opposition_distance_at_anchor"
)

MARKING_REACHABLE_TARGETS = {
    "scl1_017_blind_a_v0",
    "scl1_017_blind_b_v0",
}
ASSIGNMENT_GAP_TARGETS = {
    "scl1_016_blind_a_v0",
    "scl1_016_blind_b_v0",
}

REQUIRED_EVIDENCE_FIELDS = {
    "marking_status",
    "unmarked_status",
    "marking_reason",
    "marking_frame_id",
    "target_player_id",
    "nearest_marker_id",
    "nearest_marker_distance_m",
    "maximum_marking_distance_m",
    "candidate_scope",
    "target_player_team_role",
    "candidate_team_role",
    "observed_marker_candidate_count",
    "coverage_status",
    "marking_model",
    "marking_assignment_policy",
    "marking_claim_boundary",
}

PROHIBITED_CLAIMS = {
    "marking_assignment_inferred",
    "marking_scheme_inferred",
    "man_or_zone_responsibility_inferred",
    "player_role_inferred",
    "player_intent_inferred",
    "communication_inferred",
    "tactical_causation_inferred",
    "marking_quality_inferred",
    "optimality_inferred",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def execute_document(path: Path, executor: TacticalQueryExecutor) -> tuple[dict[str, Any], Any, list[dict[str, Any]]]:
    payload = load_json(path)
    document = TacticalQueryDocument.model_validate(payload)
    bound_plan = bind_document(document)
    execution = executor.execute(bound_plan)
    return payload, execution, execution_result_rows(execution)


def primitive_probe(path: Path, executor: TacticalQueryExecutor) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payload = load_json(path)
    document = TacticalQueryDocument.model_validate(payload)
    bound_plan = bind_document(document)
    params = runtime_parameters(bound_plan)
    records: list[dict[str, Any]] = []
    unknown_fixture: dict[str, Any] | None = None
    for match_id in bound_plan.match_ids:
        for period in bound_plan.periods:
            state = executor._execute_period(  # noqa: SLF001 - verifier-only inspection of primitive evidence.
                bound_plan=bound_plan,
                match_id=match_id,
                period=period,
                params=params,
                compatibility_profile=GENERIC_EXECUTION_PROFILE,
            )
            records.extend(state.signals.get("marking", {}).get("anchor_evaluations", []))
            if unknown_fixture is None:
                unknown_fixture = marking_anchor_record(
                    state=state,
                    anchor={
                        "anchor_id": "marking_unknown_fixture",
                        "anchor_frame_id": int(state.frame_ids[0]),
                        "start_frame_id": int(state.frame_ids[0]),
                        "end_frame_id": int(state.frame_ids[0]),
                        "entity_refs": [],
                        "team_role": state.perspective_team_role,
                        "receiver_id": "__missing_player__",
                    },
                    frame_field="anchor_frame_id",
                    target_player_id_field="receiver_id",
                    candidate_scope="opposition_outfield_to_anchor_team",
                    maximum_marking_distance_m=3.0,
                    minimum_observed_marker_candidates=6,
                )
    return records, unknown_fixture


def status_counts(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get(field, "UNKNOWN")) for record in records).items()))


def reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("marking_reason", "unknown")) for record in records).items()))


def evidence_presence(records: list[dict[str, Any]]) -> dict[str, bool]:
    sample = [
        record
        for record in records
        if record.get("marking_status") in {"PASS", "FAIL"} and record.get("unmarked_status") in {"PASS", "FAIL"}
    ][:200]
    return {
        field: any(record.get(field) not in {None, ""} for record in sample)
        for field in sorted(REQUIRED_EVIDENCE_FIELDS)
    }


def verify_search_flip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(SEARCH_ROW_LEDGER_PATH)
    by_target = {str(row.get("target_id")): row for row in rows}
    findings: list[dict[str, Any]] = []
    target_summary: dict[str, Any] = {}
    for target_id in sorted(MARKING_REACHABLE_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "marking_target_missing", "target_id": target_id})
            continue
        target_summary[target_id] = {
            "result": row.get("result"),
            "failure_taxonomy": row.get("failure_taxonomy"),
            "providers_used": row.get("providers_used"),
            "rules_used": row.get("rules_used"),
            "result_count": row.get("result_count"),
            "requested_evidence_failure_count": row.get("requested_evidence_failure_count"),
        }
        if row.get("result") != "compiler_reachable":
            findings.append({"code": "marking_target_not_reachable", "target_id": target_id, "result": row.get("result")})
        if "marking" not in set(row.get("providers_used") or []):
            findings.append({"code": "marking_provider_not_used", "target_id": target_id, "providers_used": row.get("providers_used")})
        if row.get("requested_evidence_failure_count") not in {0, None}:
            findings.append({"code": "marking_requested_evidence_missing", "target_id": target_id})
        if "provider_field_backward_search" not in set(row.get("rules_used") or []):
            findings.append({"code": "generic_search_rule_missing", "target_id": target_id})
    for target_id in sorted(ASSIGNMENT_GAP_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "marking_assignment_gap_target_missing", "target_id": target_id})
            continue
        target_summary[target_id] = {
            "result": row.get("result"),
            "failure_taxonomy": row.get("failure_taxonomy"),
            "providers_used": row.get("providers_used"),
            "rules_used": row.get("rules_used"),
        }
        if row.get("result") == "compiler_reachable":
            findings.append({"code": "marking_assignment_became_reachable", "target_id": target_id})
        if row.get("failure_taxonomy") != "missing_primitive":
            findings.append({"code": "marking_assignment_wrong_gap_taxonomy", "target_id": target_id, "failure_taxonomy": row.get("failure_taxonomy")})
    return findings, target_summary


def verify_marking() -> dict[str, Any]:
    _registry, _runtime_manifest, registry_lock, parity_report = generate_scp0_artifacts(write=write_mode())
    executor = TacticalQueryExecutor(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", str(DEFAULT_CANONICAL_ROOT))),
        raw_root=Path(os.environ.get("TQE_RAW_ROOT", str(DEFAULT_RAW_ROOT))),
    )
    search_findings, target_summary = verify_search_flip()
    payload, execution, rows = execute_document(MARKING_PLAN_PATH, executor)
    records, unknown_fixture = primitive_probe(MARKING_PLAN_PATH, executor)

    findings: list[dict[str, Any]] = [*search_findings]
    if parity_report.status != "PASS":
        findings.append(
            {
                "code": "scp0_parity_failed",
                "parity_status": parity_report.status,
                "parity_finding_count": len(parity_report.findings),
            }
        )
    if execution.status != ExecutionStatus.PASS:
        findings.append({"code": "marking_execution_not_pass", "status": execution.status.value})
    if int(execution.provenance.get("requested_evidence_failure_count") or 0) != 0:
        findings.append({"code": "marking_requested_evidence_missing"})
    if not rows:
        findings.append({"code": "marking_has_no_result_rows"})

    evidence = evidence_presence(records)
    missing_evidence = [field for field, present in evidence.items() if not present]
    if missing_evidence:
        findings.append({"code": "marking_evidence_fields_missing", "fields": missing_evidence})

    marking_counts = status_counts(records, "marking_status")
    unmarked_counts = status_counts(records, "unmarked_status")
    if "PASS" not in marking_counts or "FAIL" not in marking_counts:
        findings.append({"code": "marking_branch_distribution_incomplete", "counts": marking_counts})
    if "PASS" not in unmarked_counts or "FAIL" not in unmarked_counts:
        findings.append({"code": "unmarked_branch_distribution_incomplete", "counts": unmarked_counts})
    unknown_exercised = "UNKNOWN" in marking_counts or (
        unknown_fixture is not None and unknown_fixture.get("marking_status") == "UNKNOWN"
    )
    if not unknown_exercised:
        findings.append({"code": "unknown_branch_not_exercised", "counts": marking_counts})

    marked_records = [record for record in records if record.get("marking_status") == "PASS"]
    unmarked_records = [record for record in records if record.get("unmarked_status") == "PASS"]
    if any(float(record.get("nearest_marker_distance_m") or 999.0) > float(record.get("maximum_marking_distance_m") or 3.0) for record in marked_records):
        findings.append({"code": "marked_record_distance_above_threshold"})
    if any(float(record.get("nearest_marker_distance_m") or 0.0) <= float(record.get("maximum_marking_distance_m") or 3.0) for record in unmarked_records):
        findings.append({"code": "unmarked_record_distance_within_threshold"})
    if any(record.get("coverage_status") != "PASS" for record in [*marked_records, *unmarked_records]):
        findings.append({"code": "evaluated_record_coverage_not_pass"})

    report = {
        "schema_version": "afl.marking.v1",
        "registry_lock": registry_lock.model_dump(mode="json"),
        "milestone": "AFL-08 marking proximity / SCL named-gap closure",
        "status": "PASS" if not findings else "FAIL",
        "threshold_version": THRESHOLD_VERSION,
        "plans": {
            "marking": {
                "path": str(MARKING_PLAN_PATH),
                "document_hash": stable_hash(payload),
                "execution_status": execution.status.value,
                "result_count": len(rows),
                "requested_evidence_failure_count": int(execution.provenance.get("requested_evidence_failure_count") or 0),
            },
        },
        "scl_gap_closure": {
            "targets": target_summary,
            "closure_claim": (
                "scl1_017 flipped from missing/partial to compiler_reachable through generic provider search; "
                "scl1_016 marker-assignment responsibility remains an honest missing primitive."
            ),
        },
        "primitive_probe": {
            "record_count": len(records),
            "marking_status_counts": marking_counts,
            "unmarked_status_counts": unmarked_counts,
            "reason_counts": reason_counts(records),
            "evidence_presence_sample": evidence,
            "unknown_fixture": None
            if unknown_fixture is None
            else {
                "marking_status": unknown_fixture.get("marking_status"),
                "unmarked_status": unknown_fixture.get("unmarked_status"),
                "marking_reason": unknown_fixture.get("marking_reason"),
            },
            "model": "nearest_observed_opposition_distance_at_anchor_v0_1",
            "coverage_policy": "PASS/FAIL only when target tracking and enough observed opposition outfield candidates are present.",
        },
        "claim_boundary": {
            "allowed_claim": "Observed nearest-opposition proximity to a target player under a frozen distance threshold.",
            "prohibited_claims": sorted(PROHIBITED_CLAIMS),
            "unknown_policy": "Missing target tracking or insufficient candidate tracking produces UNKNOWN, not marked/unmarked.",
        },
        "findings": findings,
    }
    return report


def main() -> int:
    report = verify_marking()
    report_path = output_path(REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "findings_count": len(report["findings"]),
                "marking_results": report["plans"]["marking"]["result_count"],
                "marking_status_counts": report["primitive_probe"]["marking_status_counts"],
                "unmarked_status_counts": report["primitive_probe"]["unmarked_status_counts"],
                "reason_counts": report["primitive_probe"]["reason_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
