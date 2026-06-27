"""AFL-08 off_ball_run_type observed-path gap-closure verifier.

This slice closes only literal observed path geometry over already observed
off-ball runs: run-in-behind and diagonal run. Purpose and role labels such as
decoy, marker dragging, overlap/underlap role, third-player purpose, intent,
quality, and tactical causation remain explicit gaps.
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
    off_ball_run_type_anchor_record,
    runtime_parameters,
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash


REPORT_PATH = Path("artifacts/autonomous/afl-off-ball-run-type-verification-report.json")
SEARCH_ROW_LEDGER_PATH = Path("generated/semantic-contract-scl0/search-run/row-ledger.json")
RUN_IN_BEHIND_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_019_blind_a_v0.json")
DIAGONAL_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_029_blind_a_v0.json")
THRESHOLD_VERSION = (
    "off_ball_run_type.v0.1.0:"
    "min_forward=4.0:"
    "min_lateral=2.0:"
    "min_observed_defenders=6:"
    "model=observed_off_ball_run_endpoint_path_geometry"
)

PATH_TYPE_REACHABLE_TARGETS = {
    "scl1_019_blind_a_v0",
    "scl1_019_blind_b_v0",
    "scl1_029_blind_a_v0",
    "scl1_029_blind_b_v0",
}
PURPOSE_GAP_TARGETS = {
    "scl1_030_blind_a_v0",
    "scl1_030_blind_b_v0",
}

REQUIRED_EVIDENCE_FIELDS = {
    "off_ball_run_type_status",
    "off_ball_run_type_reason",
    "run_in_behind_status",
    "diagonal_run_status",
    "observed_run_type_labels",
    "run_player_id",
    "run_start_frame_id",
    "run_end_frame_id",
    "run_forward_progression_m",
    "run_lateral_displacement_m",
    "defensive_line_start_x_m",
    "defensive_line_end_x_m",
    "attacking_direction",
    "run_start_beyond_line",
    "run_end_beyond_line",
    "coverage_status",
    "off_ball_run_type_model",
    "off_ball_run_type_claim_boundary",
}

PROHIBITED_CLAIMS = {
    "decoy_inferred",
    "marker_dragging_inferred",
    "space_creation_inferred",
    "overlap_role_inferred",
    "underlap_role_inferred",
    "third_player_purpose_inferred",
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
            records.extend(state.signals.get("off_ball_run_type", {}).get("anchor_evaluations", []))
            if unknown_fixture is None:
                unknown_fixture = off_ball_run_type_anchor_record(
                    state=state,
                    run={
                        "anchor_id": "off_ball_run_type_unknown_fixture",
                        "anchor_frame_id": int(state.frame_ids[0]),
                        "run_start_frame_id": int(state.frame_ids[0]),
                        "run_end_frame_id": int(state.frame_ids[0]),
                        "off_ball_run_status": "UNKNOWN",
                        "run_player_id": "__unknown__",
                        "candidate_team_role": state.perspective_team_role,
                    },
                    minimum_forward_progression_m=4.0,
                    minimum_lateral_displacement_m=2.0,
                    minimum_observed_defenders=6,
                )
    return records, unknown_fixture


def status_counts(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get(field, "UNKNOWN")) for record in records).items()))


def reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("off_ball_run_type_reason", "unknown")) for record in records).items()))


def evidence_presence(records: list[dict[str, Any]]) -> dict[str, bool]:
    sample = [record for record in records if record.get("off_ball_run_type_status") in {"PASS", "FAIL"}][:200]
    return {
        field: any(is_present(record.get(field)) for record in sample)
        for field in sorted(REQUIRED_EVIDENCE_FIELDS)
    }


def is_present(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def verify_search_flip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(SEARCH_ROW_LEDGER_PATH)
    by_target = {str(row.get("target_id")): row for row in rows}
    findings: list[dict[str, Any]] = []
    target_summary: dict[str, Any] = {}
    for target_id in sorted(PATH_TYPE_REACHABLE_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "off_ball_run_type_target_missing", "target_id": target_id})
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
            findings.append({"code": "off_ball_run_type_target_not_reachable", "target_id": target_id, "result": row.get("result")})
        providers = set(row.get("providers_used") or [])
        if not {"off_ball_run", "off_ball_run_type"}.issubset(providers):
            findings.append({"code": "off_ball_run_type_provider_chain_missing", "target_id": target_id, "providers_used": row.get("providers_used")})
        if row.get("requested_evidence_failure_count") not in {0, None}:
            findings.append({"code": "off_ball_run_type_requested_evidence_missing", "target_id": target_id})
        if "provider_field_backward_search" not in set(row.get("rules_used") or []):
            findings.append({"code": "generic_search_rule_missing", "target_id": target_id})
    for target_id in sorted(PURPOSE_GAP_TARGETS):
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


def verify_off_ball_run_type() -> dict[str, Any]:
    executor = TacticalQueryExecutor(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", str(DEFAULT_CANONICAL_ROOT))),
        raw_root=Path(os.environ.get("TQE_RAW_ROOT", str(DEFAULT_RAW_ROOT))),
    )
    search_findings, target_summary = verify_search_flip()
    behind_payload, behind_execution, behind_rows = execute_document(RUN_IN_BEHIND_PLAN_PATH, executor)
    diagonal_payload, diagonal_execution, diagonal_rows = execute_document(DIAGONAL_PLAN_PATH, executor)
    records, unknown_fixture = primitive_probe(DIAGONAL_PLAN_PATH, executor)

    findings: list[dict[str, Any]] = [*search_findings]
    for label, execution in [("run_in_behind", behind_execution), ("diagonal", diagonal_execution)]:
        if execution.status != ExecutionStatus.PASS:
            findings.append({"code": f"{label}_execution_not_pass", "status": execution.status.value})
        if int(execution.provenance.get("requested_evidence_failure_count") or 0) != 0:
            findings.append({"code": f"{label}_requested_evidence_missing"})

    evidence = evidence_presence(records)
    missing_evidence = [field for field, present in evidence.items() if not present]
    if missing_evidence:
        findings.append({"code": "off_ball_run_type_evidence_fields_missing", "fields": missing_evidence})

    type_counts = status_counts(records, "off_ball_run_type_status")
    behind_counts = status_counts(records, "run_in_behind_status")
    diagonal_counts = status_counts(records, "diagonal_run_status")
    if "PASS" not in diagonal_counts or "FAIL" not in diagonal_counts:
        findings.append({"code": "diagonal_branch_distribution_incomplete", "counts": diagonal_counts})
    if "PASS" not in behind_counts or "FAIL" not in behind_counts:
        findings.append({"code": "run_in_behind_branch_distribution_incomplete", "counts": behind_counts})
    unknown_exercised = "UNKNOWN" in type_counts or (
        unknown_fixture is not None and unknown_fixture.get("off_ball_run_type_status") == "UNKNOWN"
    )
    if not unknown_exercised:
        findings.append({"code": "unknown_branch_not_exercised", "counts": type_counts})

    for record in records:
        if record.get("diagonal_run_status") == "PASS":
            if float(record.get("run_forward_progression_m") or 0.0) < 4.0:
                findings.append({"code": "diagonal_pass_forward_progression_below_threshold"})
                break
            if float(record.get("run_lateral_displacement_m") or 0.0) < 2.0:
                findings.append({"code": "diagonal_pass_lateral_displacement_below_threshold"})
                break
    for record in records:
        if record.get("run_in_behind_status") == "PASS":
            if record.get("run_start_beyond_line") is not False or record.get("run_end_beyond_line") is not True:
                findings.append({"code": "run_in_behind_pass_does_not_cross_line"})
                break
            if float(record.get("run_forward_progression_m") or 0.0) < 4.0:
                findings.append({"code": "run_in_behind_forward_progression_below_threshold"})
                break

    report = {
        "schema_version": "afl.off_ball_run_type.v1",
        "milestone": "AFL-08 off_ball_run_type observed-path / SCL named-gap closure",
        "status": "PASS" if not findings else "FAIL",
        "threshold_version": THRESHOLD_VERSION,
        "plans": {
            "run_in_behind": {
                "path": str(RUN_IN_BEHIND_PLAN_PATH),
                "document_hash": stable_hash(behind_payload),
                "execution_status": behind_execution.status.value,
                "result_count": len(behind_rows),
                "requested_evidence_failure_count": int(behind_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
            "diagonal": {
                "path": str(DIAGONAL_PLAN_PATH),
                "document_hash": stable_hash(diagonal_payload),
                "execution_status": diagonal_execution.status.value,
                "result_count": len(diagonal_rows),
                "requested_evidence_failure_count": int(diagonal_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
        },
        "scl_gap_closure": {
            "targets": target_summary,
            "closure_claim": (
                "scl1_019 and scl1_029 flipped to compiler_reachable through generic provider search over "
                "off_ball_run -> off_ball_run_type; scl1_030 decoy/marker-dragging purpose remains an honest missing primitive."
            ),
        },
        "primitive_probe": {
            "record_count": len(records),
            "off_ball_run_type_status_counts": type_counts,
            "run_in_behind_status_counts": behind_counts,
            "diagonal_run_status_counts": diagonal_counts,
            "reason_counts": reason_counts(records),
            "evidence_presence_sample": evidence,
            "unknown_fixture": None
            if unknown_fixture is None
            else {
                "off_ball_run_type_status": unknown_fixture.get("off_ball_run_type_status"),
                "run_in_behind_status": unknown_fixture.get("run_in_behind_status"),
                "diagonal_run_status": unknown_fixture.get("diagonal_run_status"),
                "off_ball_run_type_reason": unknown_fixture.get("off_ball_run_type_reason"),
            },
            "model": "observed_off_ball_run_endpoint_path_geometry_v0_1",
            "coverage_policy": "Line-relative labels become UNKNOWN when defensive line coverage is insufficient; observed path labels never infer purpose or role.",
        },
        "claim_boundary": {
            "allowed_claim": "Observed off-ball run path geometry for literal run-in-behind and diagonal labels under frozen thresholds.",
            "prohibited_claims": sorted(PROHIBITED_CLAIMS),
            "unknown_policy": "Missing base run evidence, endpoints, team direction, or defensive-line coverage produces UNKNOWN, not a path/purpose claim.",
        },
        "findings": findings,
    }
    return report


def main() -> int:
    report = verify_off_ball_run_type()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "findings_count": len(report["findings"]),
                "run_in_behind_results": report["plans"]["run_in_behind"]["result_count"],
                "diagonal_results": report["plans"]["diagonal"]["result_count"],
                "off_ball_run_type_status_counts": report["primitive_probe"]["off_ball_run_type_status_counts"],
                "run_in_behind_status_counts": report["primitive_probe"]["run_in_behind_status_counts"],
                "diagonal_run_status_counts": report["primitive_probe"]["diagonal_run_status_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
