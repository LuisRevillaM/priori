"""AFL-08 set-piece structure primitive verifier.

This slice closes the observed set-piece shape part of the SCL set-piece gap.
The claim is deliberately narrow: provider restart/set-piece event identity plus
at-frame attacking and defending outfield width/depth/centroid evidence.
Routine variants, planned plays, marking schemes, roles, intent, quality, and
tactical causation remain outside this primitive.
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
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash


REPORT_PATH = Path("artifacts/autonomous/afl-set-piece-structure-verification-report.json")
SEARCH_ROW_LEDGER_PATH = Path("generated/semantic-contract-scl0/search-run/row-ledger.json")
ATTACKING_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_023_blind_a_v0.json")
DEFENDING_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_024_blind_a_v0.json")
THRESHOLD_VERSION = (
    "set_piece_structure.v0.1.0:"
    "recognized_prefixes=CornerKick,FreeKick,GoalKick,ThrowIn,KickOff,Penalty_:"
    "min_observed_outfield=6:"
    "shape_model=width_depth_centroid_at_event_anchor"
)

SET_PIECE_REACHABLE_TARGETS = {
    "scl1_023_blind_a_v0",
    "scl1_023_blind_b_v0",
    "scl1_024_blind_a_v0",
    "scl1_024_blind_b_v0",
}
SET_PIECE_ROUTINE_GAP_TARGETS = {
    "scl1_022_blind_a_v0",
    "scl1_022_blind_b_v0",
}

REQUIRED_EVIDENCE_FIELDS = {
    "set_piece_structure_status",
    "set_piece_structure_reason",
    "set_piece_restart_type",
    "event_type",
    "event_anchor_frame_id",
    "set_piece_attacking_team_role",
    "set_piece_defending_team_role",
    "attacking_shape_width_m",
    "attacking_shape_depth_m",
    "defending_shape_width_m",
    "defending_shape_depth_m",
    "coverage_status",
    "structure_model",
    "coordinate_system",
    "set_piece_structure_claim_boundary",
}

PROHIBITED_CLAIMS = {
    "routine_variant_inferred",
    "planned_play_inferred",
    "delivery_pattern_inferred",
    "marking_assignment_inferred",
    "player_role_inferred",
    "player_intent_inferred",
    "tactical_causation_inferred",
    "set_piece_quality_inferred",
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
            records.extend(state.signals.get("set_piece_structure", {}).get("anchor_evaluations", []))
    return records


def status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("set_piece_structure_status", "UNKNOWN")) for record in records).items()))


def restart_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("set_piece_restart_type", "unknown")) for record in records).items()))


def reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("set_piece_structure_reason", "unknown")) for record in records).items()))


def evidence_presence(records: list[dict[str, Any]]) -> dict[str, bool]:
    pass_records = [record for record in records if record.get("set_piece_structure_status") == "PASS"][:200]
    return {
        field: any(record.get(field) not in {None, ""} for record in pass_records)
        for field in sorted(REQUIRED_EVIDENCE_FIELDS)
    }


def verify_search_flip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(SEARCH_ROW_LEDGER_PATH)
    by_target = {str(row.get("target_id")): row for row in rows}
    findings: list[dict[str, Any]] = []
    target_summary: dict[str, Any] = {}
    for target_id in sorted(SET_PIECE_REACHABLE_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "set_piece_target_missing", "target_id": target_id})
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
            findings.append({"code": "set_piece_shape_target_not_reachable", "target_id": target_id, "result": row.get("result")})
        if "set_piece_structure" not in set(row.get("providers_used") or []):
            findings.append({"code": "set_piece_provider_not_used", "target_id": target_id, "providers_used": row.get("providers_used")})
        if row.get("requested_evidence_failure_count") not in {0, None}:
            findings.append({"code": "set_piece_requested_evidence_missing", "target_id": target_id})
        if "provider_field_backward_search" not in set(row.get("rules_used") or []):
            findings.append({"code": "generic_search_rule_missing", "target_id": target_id})
    for target_id in sorted(SET_PIECE_ROUTINE_GAP_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "set_piece_routine_target_missing", "target_id": target_id})
            continue
        target_summary[target_id] = {
            "result": row.get("result"),
            "failure_taxonomy": row.get("failure_taxonomy"),
            "providers_used": row.get("providers_used"),
            "rules_used": row.get("rules_used"),
        }
        if row.get("result") == "compiler_reachable":
            findings.append({"code": "set_piece_routine_became_reachable", "target_id": target_id})
        if row.get("failure_taxonomy") != "missing_primitive":
            findings.append({"code": "set_piece_routine_wrong_gap_taxonomy", "target_id": target_id, "failure_taxonomy": row.get("failure_taxonomy")})
    return findings, target_summary


def verify_set_piece_structure() -> dict[str, Any]:
    executor = TacticalQueryExecutor(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", str(DEFAULT_CANONICAL_ROOT))),
        raw_root=Path(os.environ.get("TQE_RAW_ROOT", str(DEFAULT_RAW_ROOT))),
    )
    search_findings, target_summary = verify_search_flip()
    attacking_payload, attacking_execution, attacking_rows = execute_document(ATTACKING_PLAN_PATH, executor)
    defending_payload, defending_execution, defending_rows = execute_document(DEFENDING_PLAN_PATH, executor)
    records = primitive_records(ATTACKING_PLAN_PATH, executor)

    findings: list[dict[str, Any]] = [*search_findings]
    for label, execution, rows in [
        ("attacking_shape", attacking_execution, attacking_rows),
        ("defending_shape", defending_execution, defending_rows),
    ]:
        if execution.status != ExecutionStatus.PASS:
            findings.append({"code": f"{label}_execution_not_pass", "status": execution.status.value})
        if int(execution.provenance.get("requested_evidence_failure_count") or 0) != 0:
            findings.append({"code": f"{label}_requested_evidence_missing"})
        if not rows:
            findings.append({"code": f"{label}_has_no_pass_rows"})

    counts = status_counts(records)
    if not {"PASS", "FAIL", "UNKNOWN"}.issubset(counts):
        findings.append({"code": "set_piece_status_distribution_incomplete", "counts": counts})
    restarts = restart_counts(records)
    for required_restart in ["corner_kick", "free_kick", "goal_kick", "throw_in"]:
        if restarts.get(required_restart, 0) == 0:
            findings.append({"code": "restart_family_missing", "restart_type": required_restart, "counts": restarts})

    evidence = evidence_presence(records)
    missing_evidence = [field for field, present in evidence.items() if not present]
    if missing_evidence:
        findings.append({"code": "set_piece_evidence_fields_missing", "fields": missing_evidence})

    pass_records = [record for record in records if record.get("set_piece_structure_status") == "PASS"]
    if any(int(record.get("attacking_observed_player_count") or 0) < int(record.get("minimum_observed_outfield_players") or 6) for record in pass_records):
        findings.append({"code": "pass_record_attacking_coverage_below_minimum"})
    if any(int(record.get("defending_observed_player_count") or 0) < int(record.get("minimum_observed_outfield_players") or 6) for record in pass_records):
        findings.append({"code": "pass_record_defending_coverage_below_minimum"})
    if any(record.get("coverage_status") != "PASS" for record in pass_records):
        findings.append({"code": "pass_record_coverage_not_pass"})
    if any(record.get("set_piece_restart_type") == "non_set_piece" for record in pass_records):
        findings.append({"code": "non_set_piece_marked_pass"})

    report = {
        "schema_version": "afl.set_piece_structure.v1",
        "milestone": "AFL-08 set_piece_structure primitive / SCL named-gap closure",
        "status": "PASS" if not findings else "FAIL",
        "threshold_version": THRESHOLD_VERSION,
        "plans": {
            "attacking_shape": {
                "path": str(ATTACKING_PLAN_PATH),
                "document_hash": stable_hash(attacking_payload),
                "execution_status": attacking_execution.status.value,
                "result_count": len(attacking_rows),
                "requested_evidence_failure_count": int(attacking_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
            "defending_shape": {
                "path": str(DEFENDING_PLAN_PATH),
                "document_hash": stable_hash(defending_payload),
                "execution_status": defending_execution.status.value,
                "result_count": len(defending_rows),
                "requested_evidence_failure_count": int(defending_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
        },
        "scl_gap_closure": {
            "targets": target_summary,
            "closure_claim": (
                "scl1_023 and scl1_024 flipped from missing_primitive to compiler_reachable through generic provider search; "
                "scl1_022 routine/variant typing remains an honest missing primitive."
            ),
        },
        "primitive_probe": {
            "record_count": len(records),
            "status_counts": counts,
            "restart_counts": restarts,
            "reason_counts": reason_counts(records),
            "evidence_presence_sample": evidence,
            "model": "provider_restart_event_plus_anchor_frame_outfield_width_depth_centroid",
            "coverage_policy": "PASS only when recognized restart event has at least six observed outfield players for both event team and opponent.",
        },
        "claim_boundary": {
            "allowed_claim": "Observed provider restart/set-piece event with at-frame attacking and defending outfield arrangement evidence.",
            "prohibited_claims": sorted(PROHIBITED_CLAIMS),
            "unknown_policy": "Recognized restarts with insufficient observed outfield players produce UNKNOWN, not a structure claim.",
        },
        "findings": findings,
    }
    return report


def main() -> int:
    report = verify_set_piece_structure()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "findings_count": len(report["findings"]),
                "attacking_shape_results": report["plans"]["attacking_shape"]["result_count"],
                "defending_shape_results": report["plans"]["defending_shape"]["result_count"],
                "status_counts": report["primitive_probe"]["status_counts"],
                "restart_counts": report["primitive_probe"]["restart_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
