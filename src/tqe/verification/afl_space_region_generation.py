"""AFL-08 sampled open-space region primitive verifier.

This slice closes observed open/free-space geometry for SCL concepts. It does
not close space creation, exploitation, pitch-control value, or tactical purpose.
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
    runtime_parameters,
    space_region_generation_anchor_record,
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import generate_scp0_artifacts


REPORT_PATH = Path("artifacts/autonomous/afl-space-region-generation-verification-report.json")
SEARCH_ROW_LEDGER_PATH = Path("generated/semantic-contract-scl0/search-run/row-ledger.json")
OPEN_SPACE_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_027_blind_a_v0.json")
AVAILABLE_SPACE_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_031_blind_a_v0.json")
THRESHOLD_VERSION = (
    "space_region_generation.v0.1.0:"
    "frame=anchor_frame_id:"
    "zone=any:"
    "grid=8.0:"
    "min_opp=8.0:"
    "min_teammate=4.0:"
    "min_points=1:"
    "min_observed_per_team=6:"
    "model=sampled_grid_distance_from_observed_outfield_players"
)

SPACE_REGION_REACHABLE_TARGETS = {
    "scl1_027_blind_a_v0",
    "scl1_027_blind_b_v0",
    "scl1_031_blind_a_v0",
    "scl1_031_blind_b_v0",
}
SPACE_CREATION_GAP_TARGETS = {
    "scl1_028_blind_a_v0",
    "scl1_028_blind_b_v0",
}

REQUIRED_EVIDENCE_FIELDS = {
    "open_space_status",
    "open_space_reason",
    "space_frame_id",
    "zone_scope",
    "grid_step_m",
    "minimum_opponent_distance_m",
    "minimum_teammate_distance_m",
    "open_space_region_count",
    "representative_open_space_point",
    "representative_nearest_opponent_distance_m",
    "representative_nearest_teammate_distance_m",
    "open_space_candidate_points",
    "space_region_model",
    "space_region_claim_boundary",
    "coverage_status",
}

PROHIBITED_CLAIMS = {
    "space_value_inferred",
    "pitch_control_inferred",
    "space_creation_inferred",
    "space_exploitation_inferred",
    "player_intent_inferred",
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


def primitive_probe(
    path: Path,
    executor: TacticalQueryExecutor,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    payload = load_json(path)
    document = TacticalQueryDocument.model_validate(payload)
    bound_plan = bind_document(document)
    params = runtime_parameters(bound_plan)
    records: list[dict[str, Any]] = []
    fail_fixture: dict[str, Any] | None = None
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
            period_records = state.signals.get("space_region_generation", {}).get("anchor_evaluations", [])
            records.extend(period_records)
            anchor = (
                period_records[0]
                if period_records
                else {
                    "anchor_id": "space_region_fixture",
                    "anchor_frame_id": int(state.frame_ids[0]),
                    "start_frame_id": int(state.frame_ids[0]),
                    "end_frame_id": int(state.frame_ids[0]),
                    "entity_refs": [],
                    "team_role": state.perspective_team_role,
                }
            )
            if fail_fixture is None:
                fail_fixture = space_region_generation_anchor_record(
                    state=state,
                    anchor=dict(anchor),
                    frame_field="anchor_frame_id",
                    zone_scope="any",
                    grid_step_m=20.0,
                    minimum_opponent_distance_m=200.0,
                    minimum_teammate_distance_m=200.0,
                    minimum_open_points=1,
                    maximum_candidate_points=5,
                    minimum_observed_players_per_team=1,
                )
            if unknown_fixture is None:
                unknown_fixture = space_region_generation_anchor_record(
                    state=state,
                    anchor=dict(anchor),
                    frame_field="anchor_frame_id",
                    zone_scope="any",
                    grid_step_m=0.0,
                    minimum_opponent_distance_m=8.0,
                    minimum_teammate_distance_m=4.0,
                    minimum_open_points=1,
                    maximum_candidate_points=5,
                    minimum_observed_players_per_team=1,
                )
    return records, fail_fixture, unknown_fixture


def status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("open_space_status", "UNKNOWN")) for record in records).items()))


def reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("open_space_reason", "unknown")) for record in records).items()))


def evidence_presence(records: list[dict[str, Any]]) -> dict[str, bool]:
    pass_records = [record for record in records if record.get("open_space_status") == "PASS"][:200]
    return {
        field: any(has_evidence_value(record.get(field)) for record in pass_records)
        for field in sorted(REQUIRED_EVIDENCE_FIELDS)
    }


def has_evidence_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list) and not value:
        return False
    return True


def verify_search_flip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(SEARCH_ROW_LEDGER_PATH)
    by_target = {str(row.get("target_id")): row for row in rows}
    findings: list[dict[str, Any]] = []
    target_summary: dict[str, Any] = {}
    for target_id in sorted(SPACE_REGION_REACHABLE_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "space_region_target_missing", "target_id": target_id})
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
            findings.append({"code": "space_region_target_not_reachable", "target_id": target_id, "result": row.get("result")})
        if "space_region_generation" not in set(row.get("providers_used") or []):
            findings.append({"code": "space_region_provider_not_used", "target_id": target_id, "providers_used": row.get("providers_used")})
        if row.get("requested_evidence_failure_count") not in {0, None}:
            findings.append({"code": "space_region_requested_evidence_missing", "target_id": target_id})
        if "provider_field_backward_search" not in set(row.get("rules_used") or []):
            findings.append({"code": "generic_search_rule_missing", "target_id": target_id})
    for target_id in sorted(SPACE_CREATION_GAP_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "space_creation_gap_target_missing", "target_id": target_id})
            continue
        target_summary[target_id] = {
            "result": row.get("result"),
            "failure_taxonomy": row.get("failure_taxonomy"),
            "providers_used": row.get("providers_used"),
            "rules_used": row.get("rules_used"),
        }
        if row.get("result") == "compiler_reachable":
            findings.append({"code": "space_creation_became_reachable", "target_id": target_id})
        if row.get("failure_taxonomy") != "missing_primitive":
            findings.append({"code": "space_creation_wrong_gap_taxonomy", "target_id": target_id, "failure_taxonomy": row.get("failure_taxonomy")})
    return findings, target_summary


def verify_space_region_generation() -> dict[str, Any]:
    _registry, _runtime_manifest, registry_lock, parity_report = generate_scp0_artifacts(write=True)
    executor = TacticalQueryExecutor(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", str(DEFAULT_CANONICAL_ROOT))),
        raw_root=Path(os.environ.get("TQE_RAW_ROOT", str(DEFAULT_RAW_ROOT))),
    )
    search_findings, target_summary = verify_search_flip()
    open_payload, open_execution, open_rows = execute_document(OPEN_SPACE_PLAN_PATH, executor)
    available_payload, available_execution, available_rows = execute_document(AVAILABLE_SPACE_PLAN_PATH, executor)
    records, fail_fixture, unknown_fixture = primitive_probe(OPEN_SPACE_PLAN_PATH, executor)
    fixture_records = [record for record in [fail_fixture, unknown_fixture] if record is not None]

    findings: list[dict[str, Any]] = [*search_findings]
    if parity_report.status != "PASS":
        findings.append(
            {
                "code": "scp0_parity_failed",
                "parity_status": parity_report.status,
                "parity_finding_count": len(parity_report.findings),
            }
        )
    for label, execution, rows in [
        ("open_space_region", open_execution, open_rows),
        ("available_space_region", available_execution, available_rows),
    ]:
        if execution.status != ExecutionStatus.PASS:
            findings.append({"code": f"{label}_execution_not_pass", "status": execution.status.value})
        if int(execution.provenance.get("requested_evidence_failure_count") or 0) != 0:
            findings.append({"code": f"{label}_requested_evidence_missing"})
        if not rows:
            findings.append({"code": f"{label}_has_no_result_rows"})

    evidence = evidence_presence(records)
    missing_evidence = [field for field, present in evidence.items() if not present]
    if missing_evidence:
        findings.append({"code": "space_region_evidence_fields_missing", "fields": missing_evidence})

    default_counts = status_counts(records)
    branch_counts = status_counts([*records, *fixture_records])
    if "PASS" not in default_counts:
        findings.append({"code": "space_region_default_pass_branch_missing", "counts": default_counts})
    if not {"PASS", "FAIL", "UNKNOWN"}.issubset(branch_counts):
        findings.append({"code": "space_region_branch_distribution_incomplete", "counts": branch_counts})

    pass_records = [record for record in records if record.get("open_space_status") == "PASS"]
    if any(int(record.get("open_space_region_count") or 0) < int(record.get("minimum_open_points") or 1) for record in pass_records):
        findings.append({"code": "pass_record_below_minimum_open_points"})
    if any(not has_evidence_value(record.get("representative_open_space_point")) for record in pass_records):
        findings.append({"code": "pass_record_missing_representative_point"})
    if any(record.get("coverage_status") != "PASS" for record in pass_records):
        findings.append({"code": "pass_record_coverage_not_pass"})
    if any(
        float(record.get("representative_nearest_opponent_distance_m") or 0.0)
        < float(record.get("minimum_opponent_distance_m") or 8.0)
        for record in pass_records
    ):
        findings.append({"code": "pass_record_opponent_distance_below_threshold"})
    if any(
        float(record.get("representative_nearest_teammate_distance_m") or 0.0)
        < float(record.get("minimum_teammate_distance_m") or 4.0)
        for record in pass_records
    ):
        findings.append({"code": "pass_record_teammate_distance_below_threshold"})

    report = {
        "schema_version": "afl.space_region_generation.v1",
        "registry_lock": registry_lock.model_dump(mode="json"),
        "milestone": "AFL-08 space_region_generation primitive / SCL named-gap closure",
        "status": "PASS" if not findings else "FAIL",
        "threshold_version": THRESHOLD_VERSION,
        "plans": {
            "open_space_region": {
                "path": str(OPEN_SPACE_PLAN_PATH),
                "document_hash": stable_hash(open_payload),
                "execution_status": open_execution.status.value,
                "result_count": len(open_rows),
                "requested_evidence_failure_count": int(open_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
            "available_space_region": {
                "path": str(AVAILABLE_SPACE_PLAN_PATH),
                "document_hash": stable_hash(available_payload),
                "execution_status": available_execution.status.value,
                "result_count": len(available_rows),
                "requested_evidence_failure_count": int(available_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
        },
        "scl_gap_closure": {
            "targets": target_summary,
            "closure_claim": (
                "scl1_027 and scl1_031 compile to observed sampled open-space geometry through generic provider search; "
                "scl1_028 space creation remains an honest missing primitive/effect gap."
            ),
        },
        "primitive_probe": {
            "record_count": len(records),
            "default_status_counts": default_counts,
            "branch_status_counts_with_fixtures": branch_counts,
            "reason_counts": reason_counts(records),
            "fixture_reasons": {
                "fail": None if fail_fixture is None else fail_fixture.get("open_space_reason"),
                "unknown": None if unknown_fixture is None else unknown_fixture.get("open_space_reason"),
            },
            "evidence_presence_sample": evidence,
            "model": "sampled_grid_distance_from_observed_outfield_players_v0_1",
            "coverage_policy": "PASS/FAIL only when both teams have enough observed outfield players and direction/grid inputs are valid.",
        },
        "claim_boundary": {
            "allowed_claim": "Observed sampled open-space candidate geometry under frozen grid and nearest-player thresholds.",
            "prohibited_claims": sorted(PROHIBITED_CLAIMS),
            "unknown_policy": "Invalid direction, invalid grid, or insufficient observed player tracking produces UNKNOWN, not open/closed-space.",
        },
        "findings": findings,
    }
    return report


def main() -> int:
    report = verify_space_region_generation()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "findings_count": len(report["findings"]),
                "open_space_results": report["plans"]["open_space_region"]["result_count"],
                "available_space_results": report["plans"]["available_space_region"]["result_count"],
                "default_status_counts": report["primitive_probe"]["default_status_counts"],
                "branch_status_counts_with_fixtures": report["primitive_probe"]["branch_status_counts_with_fixtures"],
                "fixture_reasons": report["primitive_probe"]["fixture_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
