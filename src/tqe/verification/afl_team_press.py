"""AFL-08 team-press observed multi-defender geometry verifier.

This slice closes observed multi-defender pressure geometry around a carrier. It
does not close press traps, trigger plans, synchrony, coordinated schemes,
defensive intent, pressure quality, causation, or optimality.
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
    team_press_anchor_record,
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import generate_scp0_artifacts
from tqe.write_mode import output_path, write_mode


REPORT_PATH = Path("artifacts/autonomous/afl-team-press-verification-report.json")
SEARCH_ROW_LEDGER_PATH = Path("generated/semantic-contract-scl0/search-run/row-ledger.json")
TEAM_PRESS_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_025_blind_a_v0.json")
THRESHOLD_VERSION = (
    "team_press.v0.1.0:"
    "frame=anchor_frame_id:"
    "carrier=receiver_id:"
    "candidate_scope=defending_outfield:"
    "max_distance=7.0:"
    "min_closing=0.0:"
    "max_approach_angle=135.0:"
    "min_pressing_defenders=2:"
    "min_angle_spread=30.0:"
    "min_observed_defenders=6:"
    "lookback=0.4:"
    "model=multi_defender_pressure_geometry"
)

TEAM_PRESS_REACHABLE_TARGETS = {
    "scl1_025_blind_a_v0",
    "scl1_025_blind_b_v0",
}
TRAP_GAP_TARGETS = {
    "scl1_026_blind_a_v0",
    "scl1_026_blind_b_v0",
}

REQUIRED_EVIDENCE_FIELDS = {
    "team_press_status",
    "team_press_reason",
    "team_press_frame_id",
    "carrier_id",
    "pressure_actor_ids",
    "pressure_actor_count",
    "nearby_defender_ids",
    "nearby_defender_count",
    "observed_defender_count",
    "pressure_angle_spread_degrees",
    "pressure_actor_evidence",
    "maximum_press_distance_m",
    "minimum_closing_speed_mps",
    "maximum_approach_angle_degrees",
    "minimum_pressing_defenders",
    "minimum_angle_spread_degrees",
    "coverage_status",
    "team_press_model",
    "team_press_claim_boundary",
}

PROHIBITED_CLAIMS = {
    "press_trap_inferred",
    "pressing_trigger_inferred",
    "coordination_intent_inferred",
    "defensive_scheme_inferred",
    "defensive_communication_inferred",
    "player_intent_inferred",
    "tactical_causation_inferred",
    "pressure_quality_inferred",
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
            period_records = state.signals.get("team_press", {}).get("anchor_evaluations", [])
            records.extend(period_records)
            evaluated = [
                record
                for record in period_records
                if record.get("team_press_status") in {"PASS", "FAIL"}
            ]
            if fail_fixture is None:
                for anchor in evaluated or period_records:
                    candidate = team_press_anchor_record(
                        state=state,
                        anchor=dict(anchor),
                        frame_field="anchor_frame_id",
                        carrier_id_field="receiver_id",
                        maximum_press_distance_m=0.001,
                        minimum_closing_speed_mps=-5.0,
                        maximum_approach_angle_degrees=180.0,
                        minimum_pressing_defenders=2,
                        minimum_angle_spread_degrees=0.0,
                        minimum_observed_defenders=1,
                        lookback_seconds=0.4,
                        known_outfield_ids=set(str(item) for item in anchor.get("candidate_defender_ids") or []),
                    )
                    if candidate is None:
                        continue
                    fail_fixture = candidate
                    if candidate.get("team_press_status") == "FAIL":
                        break
            if unknown_fixture is None:
                base_anchor = (period_records[0] if period_records else None) or {
                    "anchor_id": "team_press_unknown_fixture",
                    "anchor_frame_id": int(state.frame_ids[0]),
                    "start_frame_id": int(state.frame_ids[0]),
                    "end_frame_id": int(state.frame_ids[0]),
                    "entity_refs": [],
                    "team_role": state.perspective_team_role,
                }
                unknown_anchor = {**dict(base_anchor), "receiver_id": "__missing_player__"}
                unknown_fixture = team_press_anchor_record(
                    state=state,
                    anchor=unknown_anchor,
                    frame_field="anchor_frame_id",
                    carrier_id_field="receiver_id",
                    maximum_press_distance_m=7.0,
                    minimum_closing_speed_mps=0.0,
                    maximum_approach_angle_degrees=135.0,
                    minimum_pressing_defenders=2,
                    minimum_angle_spread_degrees=30.0,
                    minimum_observed_defenders=1,
                    lookback_seconds=0.4,
                    known_outfield_ids=set(base_anchor.get("candidate_defender_ids") or []),
                )
    return records, fail_fixture, unknown_fixture


def status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("team_press_status", "UNKNOWN")) for record in records).items()))


def reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("team_press_reason", "unknown")) for record in records).items()))


def has_evidence_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list) and not value:
        return False
    return True


def evidence_presence(records: list[dict[str, Any]]) -> dict[str, bool]:
    pass_records = [record for record in records if record.get("team_press_status") == "PASS"][:200]
    return {
        field: any(has_evidence_value(record.get(field)) for record in pass_records)
        for field in sorted(REQUIRED_EVIDENCE_FIELDS)
    }


def verify_search_flip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(SEARCH_ROW_LEDGER_PATH)
    by_target = {str(row.get("target_id")): row for row in rows}
    findings: list[dict[str, Any]] = []
    target_summary: dict[str, Any] = {}
    for target_id in sorted(TEAM_PRESS_REACHABLE_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "team_press_target_missing", "target_id": target_id})
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
            findings.append({"code": "team_press_target_not_reachable", "target_id": target_id, "result": row.get("result")})
        if "team_press" not in set(row.get("providers_used") or []):
            findings.append({"code": "team_press_provider_not_used", "target_id": target_id, "providers_used": row.get("providers_used")})
        if row.get("requested_evidence_failure_count") not in {0, None}:
            findings.append({"code": "team_press_requested_evidence_missing", "target_id": target_id})
        if "provider_field_backward_search" not in set(row.get("rules_used") or []):
            findings.append({"code": "generic_search_rule_missing", "target_id": target_id})
    for target_id in sorted(TRAP_GAP_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "pressing_trap_gap_target_missing", "target_id": target_id})
            continue
        target_summary[target_id] = {
            "result": row.get("result"),
            "failure_taxonomy": row.get("failure_taxonomy"),
            "providers_used": row.get("providers_used"),
            "rules_used": row.get("rules_used"),
        }
        if row.get("result") == "compiler_reachable":
            findings.append({"code": "pressing_trap_became_reachable", "target_id": target_id})
        if row.get("failure_taxonomy") != "missing_primitive":
            findings.append({"code": "pressing_trap_wrong_gap_taxonomy", "target_id": target_id, "failure_taxonomy": row.get("failure_taxonomy")})
    return findings, target_summary


def verify_team_press() -> dict[str, Any]:
    _registry, _runtime_manifest, registry_lock, parity_report = generate_scp0_artifacts(write=write_mode())
    executor = TacticalQueryExecutor(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", str(DEFAULT_CANONICAL_ROOT))),
        raw_root=Path(os.environ.get("TQE_RAW_ROOT", str(DEFAULT_RAW_ROOT))),
    )
    search_findings, target_summary = verify_search_flip()
    payload, execution, rows = execute_document(TEAM_PRESS_PLAN_PATH, executor)
    records, fail_fixture, unknown_fixture = primitive_probe(TEAM_PRESS_PLAN_PATH, executor)
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
    if execution.status != ExecutionStatus.PASS:
        findings.append({"code": "team_press_execution_not_pass", "status": execution.status.value})
    if int(execution.provenance.get("requested_evidence_failure_count") or 0) != 0:
        findings.append({"code": "team_press_requested_evidence_missing"})
    if not rows:
        findings.append({"code": "team_press_has_no_result_rows"})

    evidence = evidence_presence(records)
    missing_evidence = [field for field, present in evidence.items() if not present]
    if missing_evidence:
        findings.append({"code": "team_press_evidence_fields_missing", "fields": missing_evidence})

    default_counts = status_counts(records)
    branch_counts = status_counts([*records, *fixture_records])
    if "PASS" not in default_counts:
        findings.append({"code": "team_press_default_pass_branch_missing", "counts": default_counts})
    if not {"PASS", "FAIL", "UNKNOWN"}.issubset(branch_counts):
        findings.append({"code": "team_press_branch_distribution_incomplete", "counts": branch_counts})

    pass_records = [record for record in records if record.get("team_press_status") == "PASS"]
    if any(int(record.get("pressure_actor_count") or 0) < int(record.get("minimum_pressing_defenders") or 2) for record in pass_records):
        findings.append({"code": "pass_record_below_minimum_actor_count"})
    if any(float(record.get("pressure_angle_spread_degrees") or 0.0) < float(record.get("minimum_angle_spread_degrees") or 30.0) for record in pass_records):
        findings.append({"code": "pass_record_below_angle_spread"})
    if any(record.get("coverage_status") == "UNKNOWN" for record in pass_records):
        findings.append({"code": "pass_record_coverage_unknown"})
    if any(not record.get("pressure_actor_ids") for record in pass_records):
        findings.append({"code": "pass_record_missing_pressure_actor_ids"})

    report = {
        "schema_version": "afl.team_press.v1",
        "registry_lock": registry_lock.model_dump(mode="json"),
        "milestone": "AFL-08 team_press observed multi-defender pressure geometry / SCL named-gap closure",
        "status": "PASS" if not findings else "FAIL",
        "threshold_version": THRESHOLD_VERSION,
        "plans": {
            "team_press_candidate": {
                "path": str(TEAM_PRESS_PLAN_PATH),
                "document_hash": stable_hash(payload),
                "execution_status": execution.status.value,
                "result_count": len(rows),
                "requested_evidence_failure_count": int(execution.provenance.get("requested_evidence_failure_count") or 0),
            },
        },
        "scl_gap_closure": {
            "targets": target_summary,
            "closure_claim": (
                "scl1_025 compiles to observed multi-defender pressure geometry through generic provider search; "
                "scl1_026 pressing trap remains an honest missing primitive/coordination-intent gap."
            ),
        },
        "primitive_probe": {
            "record_count": len(records),
            "default_status_counts": default_counts,
            "branch_status_counts_with_fixtures": branch_counts,
            "reason_counts": reason_counts(records),
            "fixture_reasons": {
                "fail": None if fail_fixture is None else fail_fixture.get("team_press_reason"),
                "unknown": None if unknown_fixture is None else unknown_fixture.get("team_press_reason"),
            },
            "evidence_presence_sample": evidence,
            "model": "multi_defender_pressure_geometry_v0_1",
            "coverage_policy": "PASS/FAIL only when carrier, enough defenders, and kinematic evidence are present.",
        },
        "claim_boundary": {
            "allowed_claim": "Observed multi-defender pressure geometry around a carrier under frozen distance, closing/approach, count, and angular-spread thresholds.",
            "prohibited_claims": sorted(PROHIBITED_CLAIMS),
            "unknown_policy": "Missing carrier tracking, insufficient defender tracking, or missing kinematic evidence produces UNKNOWN, not team-press evidence.",
        },
        "findings": findings,
    }
    return report


def main() -> int:
    report = verify_team_press()
    report_path = output_path(REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "findings_count": len(report["findings"]),
                "team_press_results": report["plans"]["team_press_candidate"]["result_count"],
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
