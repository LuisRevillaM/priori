"""AFL-08 off_ball_run primitive gap-closure verifier.

This slice closes the base observed off-ball movement episode gap. The claim is
deliberately narrow: endpoint-window movement by an outfield player away from
the ball. Purpose, marker-dragging, decoy, space creation, role, intent,
quality, and tactical causation remain outside this primitive.
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
    off_ball_run_anchor_record,
    runtime_parameters,
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import generate_scp0_artifacts


REPORT_PATH = Path("artifacts/autonomous/afl-off-ball-run-verification-report.json")
SEARCH_ROW_LEDGER_PATH = Path("generated/semantic-contract-scl0/search-run/row-ledger.json")
OFF_BALL_RUN_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_018_blind_a_v0.json")
THRESHOLD_VERSION = (
    "off_ball_run.v0.1.0:"
    "lookahead=1.2:"
    "min_displacement=4.0:"
    "min_speed=3.0:"
    "min_ball_distance=5.0:"
    "min_observed_candidates=6:"
    "max_missing_candidate_ratio=0.35:"
    "model=anchor_scoped_outfield_endpoint_displacement"
)

OFF_BALL_RUN_REACHABLE_TARGETS = {
    "scl1_018_blind_a_v0",
    "scl1_018_blind_b_v0",
}
RUN_PURPOSE_GAP_TARGETS = {
    "scl1_030_blind_a_v0",
    "scl1_030_blind_b_v0",
}

REQUIRED_EVIDENCE_FIELDS = {
    "source_anchor_id",
    "off_ball_run_status",
    "off_ball_run_reason",
    "run_player_id",
    "run_start_frame_id",
    "run_end_frame_id",
    "run_duration_seconds",
    "run_displacement_m",
    "run_forward_progression_m",
    "run_lateral_displacement_m",
    "run_speed_mps",
    "run_start_ball_distance_m",
    "run_end_ball_distance_m",
    "candidate_scope",
    "candidate_team_role",
    "coverage_status",
    "off_ball_run_model",
    "off_ball_distance_policy",
    "off_ball_run_claim_boundary",
}

PROHIBITED_CLAIMS = {
    "run_type_inferred",
    "run_purpose_inferred",
    "decoy_inferred",
    "marker_dragging_inferred",
    "space_creation_inferred",
    "player_role_inferred",
    "player_intent_inferred",
    "tactical_causation_inferred",
    "run_quality_inferred",
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
            records.extend(state.signals.get("off_ball_run", {}).get("anchor_evaluations", []))
            if unknown_fixture is None:
                unknown_fixture = off_ball_run_anchor_record(
                    state=state,
                    anchor={
                        "anchor_id": "off_ball_run_unknown_window_fixture",
                        "anchor_frame_id": int(state.frame_ids[-1]),
                        "start_frame_id": int(state.frame_ids[-1]),
                        "end_frame_id": int(state.frame_ids[-1]),
                        "entity_refs": [],
                        "team_role": state.perspective_team_role,
                    },
                    frame_field="anchor_frame_id",
                    candidate_scope="same_team_outfield_as_anchor",
                    lookahead_seconds=1.2,
                    minimum_run_displacement_m=4.0,
                    minimum_run_speed_mps=3.0,
                    minimum_ball_distance_m=5.0,
                    minimum_observed_candidates=6,
                    maximum_missing_candidate_ratio=0.35,
                )
    return records, unknown_fixture


def status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("off_ball_run_status", "UNKNOWN")) for record in records).items()))


def reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("off_ball_run_reason", "unknown")) for record in records).items()))


def evidence_presence(records: list[dict[str, Any]]) -> dict[str, bool]:
    pass_records = [record for record in records if record.get("off_ball_run_status") == "PASS"][:200]
    return {
        field: any(record.get(field) not in {None, ""} for record in pass_records)
        for field in sorted(REQUIRED_EVIDENCE_FIELDS)
    }


def verify_search_flip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(SEARCH_ROW_LEDGER_PATH)
    by_target = {str(row.get("target_id")): row for row in rows}
    findings: list[dict[str, Any]] = []
    target_summary: dict[str, Any] = {}
    for target_id in sorted(OFF_BALL_RUN_REACHABLE_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "off_ball_run_target_missing", "target_id": target_id})
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
            findings.append({"code": "off_ball_run_target_not_reachable", "target_id": target_id, "result": row.get("result")})
        if "off_ball_run" not in set(row.get("providers_used") or []):
            findings.append({"code": "off_ball_run_provider_not_used", "target_id": target_id, "providers_used": row.get("providers_used")})
        if row.get("requested_evidence_failure_count") not in {0, None}:
            findings.append({"code": "off_ball_run_requested_evidence_missing", "target_id": target_id})
        if "provider_field_backward_search" not in set(row.get("rules_used") or []):
            findings.append({"code": "generic_search_rule_missing", "target_id": target_id})
    for target_id in sorted(RUN_PURPOSE_GAP_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "off_ball_run_purpose_gap_target_missing", "target_id": target_id})
            continue
        target_summary[target_id] = {
            "result": row.get("result"),
            "failure_taxonomy": row.get("failure_taxonomy"),
            "providers_used": row.get("providers_used"),
            "rules_used": row.get("rules_used"),
        }
        if row.get("result") == "compiler_reachable":
            findings.append({"code": "off_ball_run_purpose_became_reachable", "target_id": target_id})
        if row.get("failure_taxonomy") != "missing_primitive":
            findings.append({"code": "off_ball_run_purpose_wrong_gap_taxonomy", "target_id": target_id, "failure_taxonomy": row.get("failure_taxonomy")})
    return findings, target_summary


def verify_off_ball_run() -> dict[str, Any]:
    _registry, _runtime_manifest, registry_lock, parity_report = generate_scp0_artifacts(write=True)
    executor = TacticalQueryExecutor(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", str(DEFAULT_CANONICAL_ROOT))),
        raw_root=Path(os.environ.get("TQE_RAW_ROOT", str(DEFAULT_RAW_ROOT))),
    )
    search_findings, target_summary = verify_search_flip()
    payload, execution, rows = execute_document(OFF_BALL_RUN_PLAN_PATH, executor)
    records, unknown_fixture = primitive_probe(OFF_BALL_RUN_PLAN_PATH, executor)

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
        findings.append({"code": "off_ball_run_execution_not_pass", "status": execution.status.value})
    if int(execution.provenance.get("requested_evidence_failure_count") or 0) != 0:
        findings.append({"code": "off_ball_run_requested_evidence_missing"})
    if not rows:
        findings.append({"code": "off_ball_run_has_no_pass_rows"})

    evidence = evidence_presence(records)
    missing_evidence = [field for field, present in evidence.items() if not present]
    if missing_evidence:
        findings.append({"code": "off_ball_run_evidence_fields_missing", "fields": missing_evidence})
    counts = status_counts(records)
    if "PASS" not in counts or "FAIL" not in counts:
        findings.append({"code": "off_ball_run_branch_distribution_incomplete", "counts": counts})
    unknown_exercised = "UNKNOWN" in counts or (
        unknown_fixture is not None and unknown_fixture.get("off_ball_run_status") == "UNKNOWN"
    )
    if not unknown_exercised:
        findings.append({"code": "unknown_branch_not_exercised", "counts": counts})

    pass_records = [record for record in records if record.get("off_ball_run_status") == "PASS"]
    if any(float(record.get("run_displacement_m") or 0.0) < float(record.get("minimum_run_displacement_m") or 4.0) for record in pass_records):
        findings.append({"code": "pass_record_displacement_below_threshold"})
    if any(float(record.get("run_speed_mps") or 0.0) < float(record.get("minimum_run_speed_mps") or 3.0) for record in pass_records):
        findings.append({"code": "pass_record_speed_below_threshold"})
    if any(float(record.get("run_start_ball_distance_m") or 0.0) < float(record.get("minimum_ball_distance_m") or 5.0) for record in pass_records):
        findings.append({"code": "pass_record_start_ball_distance_below_threshold"})
    if any(float(record.get("run_end_ball_distance_m") or 0.0) < float(record.get("minimum_ball_distance_m") or 5.0) for record in pass_records):
        findings.append({"code": "pass_record_end_ball_distance_below_threshold"})
    if any(record.get("coverage_status") != "PASS" for record in pass_records):
        findings.append({"code": "pass_record_coverage_not_pass"})

    report = {
        "schema_version": "afl.off_ball_run.v1",
        "registry_lock": registry_lock.model_dump(mode="json"),
        "milestone": "AFL-08 off_ball_run primitive / SCL named-gap closure",
        "status": "PASS" if not findings else "FAIL",
        "threshold_version": THRESHOLD_VERSION,
        "plans": {
            "off_ball_run": {
                "path": str(OFF_BALL_RUN_PLAN_PATH),
                "document_hash": stable_hash(payload),
                "execution_status": execution.status.value,
                "result_count": len(rows),
                "requested_evidence_failure_count": int(execution.provenance.get("requested_evidence_failure_count") or 0),
            },
        },
        "scl_gap_closure": {
            "targets": target_summary,
            "closure_claim": (
                "scl1_018 flipped from missing_primitive to compiler_reachable through generic provider search; "
                "scl1_030 decoy/marker-dragging purpose remains an honest missing primitive."
            ),
        },
        "primitive_probe": {
            "record_count": len(records),
            "status_counts": counts,
            "reason_counts": reason_counts(records),
            "evidence_presence_sample": evidence,
            "unknown_fixture": None
            if unknown_fixture is None
            else {
                "off_ball_run_status": unknown_fixture.get("off_ball_run_status"),
                "off_ball_run_reason": unknown_fixture.get("off_ball_run_reason"),
            },
            "model": "anchor_scoped_outfield_endpoint_displacement_v0_1",
            "coverage_policy": (
                "PASS/FAIL only when enough declared-scope outfield candidates are observed at both endpoints; "
                "missing ball/window/candidate coverage is UNKNOWN."
            ),
        },
        "claim_boundary": {
            "allowed_claim": "Observed off-ball endpoint-window movement by a non-ball actor under frozen displacement, speed, and ball-distance thresholds.",
            "prohibited_claims": sorted(PROHIBITED_CLAIMS),
            "unknown_policy": "Missing ball endpoints, end-of-period windows, or insufficient candidate tracking produce UNKNOWN, not a run/no-run claim.",
        },
        "findings": findings,
    }
    return report


def main() -> int:
    report = verify_off_ball_run()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "findings_count": len(report["findings"]),
                "off_ball_run_results": report["plans"]["off_ball_run"]["result_count"],
                "status_counts": report["primitive_probe"]["status_counts"],
                "reason_counts": report["primitive_probe"]["reason_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
