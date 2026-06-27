"""AFL-08 acceleration primitive gap-closure verifier.

This slice closes the first SCL-named missing-substrate gap by adding an
observed speed-change primitive. The claim is deliberately narrow:
two-window speed derivative evidence only, with conservative UNKNOWN handling
for missing or implausible tracking.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import (
    GENERIC_EXECUTION_PROFILE,
    DEFAULT_CANONICAL_ROOT,
    DEFAULT_RAW_ROOT,
    TacticalQueryExecutor,
    execution_result_rows,
    runtime_parameters,
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash


REPORT_PATH = Path("artifacts/autonomous/afl-acceleration-verification-report.json")
SEARCH_ROW_LEDGER_PATH = Path("generated/semantic-contract-scl0/search-run/row-ledger.json")
ACCELERATION_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_020_blind_a_v0.json")
DECELERATION_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_021_blind_a_v0.json")
THRESHOLD_VERSION = (
    "acceleration.v0.1.0:"
    "lookback=0.4:"
    "min_delta_speed=0.4:"
    "min_abs_acceleration=0.75:"
    "max_speed=10.0:"
    "max_abs_acceleration=12.0"
)

ACCELERATION_TARGETS = {
    "scl1_020_blind_a_v0",
    "scl1_020_blind_b_v0",
    "scl1_021_blind_a_v0",
    "scl1_021_blind_b_v0",
}

REQUIRED_EVIDENCE_FIELDS = {
    "acceleration_reason",
    "acceleration_frame_id",
    "acceleration_entity_id",
    "previous_speed_mps",
    "current_speed_mps",
    "delta_speed_mps",
    "acceleration_mps2",
    "acceleration_model",
    "smoothing_policy",
    "noise_policy",
    "tracking_quality_status",
    "coverage_status",
    "acceleration_verdict_bias",
}

PROHIBITED_CLAIMS = {
    "effort_inferred",
    "sprint_quality_inferred",
    "physical_capacity_inferred",
    "player_intent_inferred",
    "pressure_breaking_quality_inferred",
    "tactical_causation_inferred",
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


def primitive_records(path: Path, executor: TacticalQueryExecutor) -> list[dict[str, Any]]:
    payload = load_json(path)
    document = TacticalQueryDocument.model_validate(payload)
    bound_plan = bind_document(document)
    params = runtime_parameters(bound_plan)
    records: list[dict[str, Any]] = []
    for match_id in bound_plan.match_ids:
        for period in bound_plan.periods:
            state = executor._execute_period(  # noqa: SLF001 - verifier-only inspection of primitive evidence.
                bound_plan=bound_plan,
                match_id=match_id,
                period=period,
                params=params,
                compatibility_profile=GENERIC_EXECUTION_PROFILE,
            )
            records.extend(state.signals.get("acceleration", {}).get("anchor_evaluations", []))
    return records


def status_counts(records: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get(field_name, "UNKNOWN")) for record in records).items()))


def reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("acceleration_reason", "unknown")) for record in records).items()))


def evidence_presence(records: list[dict[str, Any]]) -> dict[str, bool]:
    sample = records[:200]
    return {
        field: any(record.get(field) not in {None, ""} for record in sample)
        for field in sorted(REQUIRED_EVIDENCE_FIELDS)
    }


def verify_search_flip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(SEARCH_ROW_LEDGER_PATH)
    by_target = {str(row.get("target_id")): row for row in rows}
    findings: list[dict[str, Any]] = []
    target_summary: dict[str, Any] = {}
    for target_id in sorted(ACCELERATION_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "acceleration_target_missing", "target_id": target_id})
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
            findings.append({"code": "acceleration_target_not_reachable", "target_id": target_id, "result": row.get("result")})
        if "acceleration" not in set(row.get("providers_used") or []):
            findings.append({"code": "acceleration_provider_not_used", "target_id": target_id, "providers_used": row.get("providers_used")})
        if row.get("requested_evidence_failure_count") not in {0, None}:
            findings.append({"code": "acceleration_requested_evidence_missing", "target_id": target_id})
        rules = set(row.get("rules_used") or [])
        if "provider_field_backward_search" not in rules:
            findings.append({"code": "generic_search_rule_missing", "target_id": target_id, "rules_used": sorted(rules)})
    return findings, target_summary


def verify_acceleration() -> dict[str, Any]:
    executor = TacticalQueryExecutor(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", str(DEFAULT_CANONICAL_ROOT))),
        raw_root=Path(os.environ.get("TQE_RAW_ROOT", str(DEFAULT_RAW_ROOT))),
    )
    search_findings, target_summary = verify_search_flip()
    acceleration_payload, acceleration_execution, acceleration_rows = execute_document(ACCELERATION_PLAN_PATH, executor)
    deceleration_payload, deceleration_execution, deceleration_rows = execute_document(DECELERATION_PLAN_PATH, executor)
    acceleration_records = primitive_records(ACCELERATION_PLAN_PATH, executor)
    deceleration_records = primitive_records(DECELERATION_PLAN_PATH, executor)
    combined_records = [*acceleration_records, *deceleration_records]

    evidence = evidence_presence(combined_records)
    findings: list[dict[str, Any]] = [*search_findings]
    for label, execution, rows in [
        ("acceleration", acceleration_execution, acceleration_rows),
        ("deceleration", deceleration_execution, deceleration_rows),
    ]:
        if execution.status != ExecutionStatus.PASS:
            findings.append({"code": f"{label}_execution_not_pass", "status": execution.status.value})
        if int(execution.provenance.get("requested_evidence_failure_count") or 0) != 0:
            findings.append({"code": f"{label}_requested_evidence_missing"})
        if not rows:
            findings.append({"code": f"{label}_has_no_pass_rows"})
    missing_evidence = [field for field, present in evidence.items() if not present]
    if missing_evidence:
        findings.append({"code": "acceleration_evidence_fields_missing", "fields": missing_evidence})
    acceleration_counts = status_counts(combined_records, "acceleration_status")
    deceleration_counts = status_counts(combined_records, "deceleration_status")
    if "PASS" not in acceleration_counts or "FAIL" not in acceleration_counts:
        findings.append({"code": "acceleration_branch_distribution_incomplete", "counts": acceleration_counts})
    if "PASS" not in deceleration_counts or "FAIL" not in deceleration_counts:
        findings.append({"code": "deceleration_branch_distribution_incomplete", "counts": deceleration_counts})
    if "UNKNOWN" not in acceleration_counts or "UNKNOWN" not in deceleration_counts:
        findings.append(
            {
                "code": "unknown_branch_not_natural_in_sample",
                "message": "Real sample did not naturally produce UNKNOWN for both directional statuses.",
                "counts": {
                    "acceleration_status": acceleration_counts,
                    "deceleration_status": deceleration_counts,
                },
            }
        )

    report = {
        "schema_version": "afl.acceleration.v1",
        "milestone": "AFL-08 acceleration primitive / SCL named-gap closure",
        "status": "PASS" if not findings else "FAIL",
        "threshold_version": THRESHOLD_VERSION,
        "plans": {
            "acceleration": {
                "path": str(ACCELERATION_PLAN_PATH),
                "document_hash": stable_hash(acceleration_payload),
                "execution_status": acceleration_execution.status.value,
                "result_count": len(acceleration_rows),
                "requested_evidence_failure_count": int(acceleration_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
            "deceleration": {
                "path": str(DECELERATION_PLAN_PATH),
                "document_hash": stable_hash(deceleration_payload),
                "execution_status": deceleration_execution.status.value,
                "result_count": len(deceleration_rows),
                "requested_evidence_failure_count": int(deceleration_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
        },
        "scl_gap_closure": {
            "targets": target_summary,
            "closure_claim": "scl1_020 and scl1_021 flipped from missing_primitive to compiler_reachable through generic provider search.",
        },
        "primitive_probe": {
            "record_count": len(combined_records),
            "acceleration_status_counts": acceleration_counts,
            "deceleration_status_counts": deceleration_counts,
            "reason_counts": reason_counts(combined_records),
            "evidence_presence_sample": evidence,
            "model": "speed_delta_between_two_non_overlapping_displacement_velocity_windows",
            "smoothing_policy": "two_window_mean_displacement_velocity_no_additional_smoothing",
            "noise_policy": (
                "UNKNOWN if either velocity window lacks tracking endpoints or if observed speed/acceleration "
                "exceeds frozen plausibility limits; second derivatives amplify tracking noise."
            ),
            "thresholds": {
                "lookback_seconds": 0.4,
                "minimum_abs_delta_speed_mps": 0.4,
                "minimum_abs_acceleration_mps2": 0.75,
                "maximum_player_speed_mps": 10.0,
                "maximum_abs_acceleration_mps2": 12.0,
            },
        },
        "claim_boundary": {
            "allowed_claim": "Observed speed-up or slow-down exceeded frozen two-window speed-change thresholds.",
            "prohibited_claims": sorted(PROHIBITED_CLAIMS),
            "unknown_policy": "Missing endpoints or implausible speed/acceleration spikes produce UNKNOWN, not phantom bursts.",
        },
        "findings": findings,
    }
    return report


def main() -> int:
    report = verify_acceleration()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "findings_count": len(report["findings"]),
        "acceleration_results": report["plans"]["acceleration"]["result_count"],
        "deceleration_results": report["plans"]["deceleration"]["result_count"],
        "acceleration_status_counts": report["primitive_probe"]["acceleration_status_counts"],
        "deceleration_status_counts": report["primitive_probe"]["deceleration_status_counts"],
    }, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
