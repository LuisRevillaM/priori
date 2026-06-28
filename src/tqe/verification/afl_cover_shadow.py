"""AFL-08 cover-shadow observed lane-geometry verifier.

This slice closes observed ball-target lane screening geometry for cover-shadow
and passing-lane-denial queries. It deliberately does not close defender intent,
tactical denial quality, pass probability, pitch-control value, scheme, moving-
ball interception, causation, or optimality.
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
    cover_shadow_anchor_record,
    execution_result_rows,
    runtime_parameters,
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash


REPORT_PATH = Path("artifacts/autonomous/afl-cover-shadow-verification-report.json")
SEARCH_ROW_LEDGER_PATH = Path("generated/semantic-contract-scl0/search-run/row-ledger.json")
COVER_SHADOW_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_014_blind_a_v0.json")
PASSING_LANE_PLAN_PATH = Path("generated/semantic-contract-scl0/search-run/plans/scl1_015_blind_a_v0.json")
THRESHOLD_VERSION = (
    "cover_shadow.v0.1.0:"
    "frame=anchor_frame_id:"
    "target=receiver_id:"
    "candidate_scope=opposition_outfield_to_anchor_team:"
    "max_lane_distance=2.0:"
    "min_projection=0.05:"
    "min_lane_length=5.0:"
    "min_observed_defenders=6:"
    "model=ball_target_lane_defender_projection"
)

COVER_SHADOW_REACHABLE_TARGETS = {
    "scl1_014_blind_a_v0",
    "scl1_014_blind_b_v0",
    "scl1_015_blind_a_v0",
    "scl1_015_blind_b_v0",
}

REQUIRED_EVIDENCE_FIELDS = {
    "cover_shadow_status",
    "passing_lane_denial_status",
    "cover_shadow_reason",
    "cover_shadow_frame_id",
    "target_entity_id",
    "ball_point",
    "target_point",
    "lane_length_m",
    "candidate_scope",
    "observed_defender_count",
    "maximum_lane_distance_m",
    "minimum_projection_fraction",
    "screening_defender_id",
    "screening_defender_distance_to_lane_m",
    "screening_defender_projection_fraction",
    "screening_defender_point",
    "screening_projection_point",
    "screening_defender_evidence",
    "cover_shadow_model",
    "coverage_status",
    "cover_shadow_claim_boundary",
}

PROHIBITED_CLAIMS = {
    "defender_intent_inferred",
    "tactical_denial_quality_inferred",
    "pass_probability_inferred",
    "pitch_control_value_inferred",
    "marking_assignment_inferred",
    "defensive_scheme_inferred",
    "moving_ball_interception_inferred",
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
            period_records = state.signals.get("cover_shadow", {}).get("anchor_evaluations", [])
            records.extend(period_records)
            evaluated = [
                record
                for record in period_records
                if record.get("cover_shadow_status") in {"PASS", "FAIL"}
            ]
            if fail_fixture is None:
                for anchor in evaluated or period_records:
                    candidate = cover_shadow_anchor_record(
                        state=state,
                        anchor=dict(anchor),
                        frame_field="anchor_frame_id",
                        target_entity_field="receiver_id",
                        candidate_scope="opposition_outfield_to_anchor_team",
                        maximum_lane_distance_m=0.001,
                        minimum_projection_fraction=0.49,
                        minimum_lane_length_m=5.0,
                        minimum_observed_defenders=1,
                    )
                    if candidate is None:
                        continue
                    fail_fixture = candidate
                    if candidate.get("cover_shadow_status") == "FAIL":
                        break
            if unknown_fixture is None:
                base_anchor = (period_records[0] if period_records else None) or {
                    "anchor_id": "cover_shadow_unknown_fixture",
                    "anchor_frame_id": int(state.frame_ids[0]),
                    "start_frame_id": int(state.frame_ids[0]),
                    "end_frame_id": int(state.frame_ids[0]),
                    "entity_refs": [],
                    "team_role": state.perspective_team_role,
                }
                unknown_anchor = {**dict(base_anchor), "receiver_id": "__missing_player__"}
                unknown_fixture = cover_shadow_anchor_record(
                    state=state,
                    anchor=unknown_anchor,
                    frame_field="anchor_frame_id",
                    target_entity_field="receiver_id",
                    candidate_scope="opposition_outfield_to_anchor_team",
                    maximum_lane_distance_m=2.0,
                    minimum_projection_fraction=0.05,
                    minimum_lane_length_m=5.0,
                    minimum_observed_defenders=1,
                )
    return records, fail_fixture, unknown_fixture


def status_counts(records: list[dict[str, Any]], field: str = "cover_shadow_status") -> dict[str, int]:
    return dict(sorted(Counter(str(record.get(field, "UNKNOWN")) for record in records).items()))


def reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("cover_shadow_reason", "unknown")) for record in records).items()))


def has_evidence_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list) and not value:
        return False
    return True


def evidence_presence(records: list[dict[str, Any]]) -> dict[str, bool]:
    pass_records = [record for record in records if record.get("cover_shadow_status") == "PASS"][:200]
    return {
        field: any(has_evidence_value(record.get(field)) for record in pass_records)
        for field in sorted(REQUIRED_EVIDENCE_FIELDS)
    }


def verify_search_flip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_json(SEARCH_ROW_LEDGER_PATH)
    by_target = {str(row.get("target_id")): row for row in rows}
    findings: list[dict[str, Any]] = []
    target_summary: dict[str, Any] = {}
    for target_id in sorted(COVER_SHADOW_REACHABLE_TARGETS):
        row = by_target.get(target_id)
        if row is None:
            findings.append({"code": "cover_shadow_target_missing", "target_id": target_id})
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
            findings.append({"code": "cover_shadow_target_not_reachable", "target_id": target_id, "result": row.get("result")})
        if "cover_shadow" not in set(row.get("providers_used") or []):
            findings.append({"code": "cover_shadow_provider_not_used", "target_id": target_id, "providers_used": row.get("providers_used")})
        if row.get("requested_evidence_failure_count") not in {0, None}:
            findings.append({"code": "cover_shadow_requested_evidence_missing", "target_id": target_id})
        if "provider_field_backward_search" not in set(row.get("rules_used") or []):
            findings.append({"code": "generic_search_rule_missing", "target_id": target_id})
    return findings, target_summary


def verify_cover_shadow() -> dict[str, Any]:
    executor = TacticalQueryExecutor(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", str(DEFAULT_CANONICAL_ROOT))),
        raw_root=Path(os.environ.get("TQE_RAW_ROOT", str(DEFAULT_RAW_ROOT))),
    )
    search_findings, target_summary = verify_search_flip()
    cover_payload, cover_execution, cover_rows = execute_document(COVER_SHADOW_PLAN_PATH, executor)
    lane_payload, lane_execution, lane_rows = execute_document(PASSING_LANE_PLAN_PATH, executor)
    records, fail_fixture, unknown_fixture = primitive_probe(COVER_SHADOW_PLAN_PATH, executor)
    fixture_records = [record for record in [fail_fixture, unknown_fixture] if record is not None]

    findings: list[dict[str, Any]] = [*search_findings]
    for label, execution, rows in [
        ("cover_shadow_region", cover_execution, cover_rows),
        ("passing_lane_denial", lane_execution, lane_rows),
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
        findings.append({"code": "cover_shadow_evidence_fields_missing", "fields": missing_evidence})

    default_counts = status_counts(records)
    branch_counts = status_counts([*records, *fixture_records])
    lane_counts = status_counts(records, "passing_lane_denial_status")
    if "PASS" not in default_counts:
        findings.append({"code": "cover_shadow_default_pass_branch_missing", "counts": default_counts})
    if not {"PASS", "FAIL", "UNKNOWN"}.issubset(branch_counts):
        findings.append({"code": "cover_shadow_branch_distribution_incomplete", "counts": branch_counts})

    pass_records = [record for record in records if record.get("cover_shadow_status") == "PASS"]
    if any(record.get("passing_lane_denial_status") != "PASS" for record in pass_records):
        findings.append({"code": "pass_record_lane_status_not_pass"})
    if any(record.get("screening_defender_id") in {None, ""} for record in pass_records):
        findings.append({"code": "pass_record_missing_screening_defender"})
    if any(record.get("coverage_status") == "UNKNOWN" for record in pass_records):
        findings.append({"code": "pass_record_coverage_unknown"})
    if any(
        float(record.get("screening_defender_distance_to_lane_m") or 999.0)
        > float(record.get("maximum_lane_distance_m") or 2.0)
        for record in pass_records
    ):
        findings.append({"code": "pass_record_distance_above_lane_threshold"})
    if any(
        not (
            float(record.get("minimum_projection_fraction") or 0.05)
            <= float(record.get("screening_defender_projection_fraction") or -1.0)
            <= 1.0 - float(record.get("minimum_projection_fraction") or 0.05)
        )
        for record in pass_records
    ):
        findings.append({"code": "pass_record_projection_outside_window"})

    report = {
        "schema_version": "afl.cover_shadow.v1",
        "milestone": "AFL-08 cover_shadow observed lane geometry / SCL named-gap closure",
        "status": "PASS" if not findings else "FAIL",
        "threshold_version": THRESHOLD_VERSION,
        "plans": {
            "cover_shadow_region": {
                "path": str(COVER_SHADOW_PLAN_PATH),
                "document_hash": stable_hash(cover_payload),
                "execution_status": cover_execution.status.value,
                "result_count": len(cover_rows),
                "requested_evidence_failure_count": int(cover_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
            "passing_lane_denial": {
                "path": str(PASSING_LANE_PLAN_PATH),
                "document_hash": stable_hash(lane_payload),
                "execution_status": lane_execution.status.value,
                "result_count": len(lane_rows),
                "requested_evidence_failure_count": int(lane_execution.provenance.get("requested_evidence_failure_count") or 0),
            },
        },
        "scl_gap_closure": {
            "targets": target_summary,
            "closure_claim": (
                "scl1_014 and scl1_015 compile to observed ball-target lane screening geometry through generic provider search. "
                "This closes cover-shadow/passing-lane geometry only, not denial intent, pass probability, pitch-control value, or moving-ball interception."
            ),
        },
        "primitive_probe": {
            "record_count": len(records),
            "default_status_counts": default_counts,
            "passing_lane_status_counts": lane_counts,
            "branch_status_counts_with_fixtures": branch_counts,
            "reason_counts": reason_counts(records),
            "fixture_reasons": {
                "fail": None if fail_fixture is None else fail_fixture.get("cover_shadow_reason"),
                "unknown": None if unknown_fixture is None else unknown_fixture.get("cover_shadow_reason"),
            },
            "evidence_presence_sample": evidence,
            "model": "ball_target_lane_defender_projection_v0_1",
            "coverage_policy": "PASS/FAIL only when ball, target, lane length, and enough observed candidate defenders are present.",
        },
        "claim_boundary": {
            "allowed_claim": "Observed defender screening geometry on the ball-target lane under frozen distance and projection thresholds.",
            "prohibited_claims": sorted(PROHIBITED_CLAIMS),
            "unknown_policy": "Missing ball/target tracking, too-short lanes, invalid thresholds, or insufficient observed defender tracking produces UNKNOWN, not lane-denial evidence.",
        },
        "findings": findings,
    }
    return report


def main() -> int:
    report = verify_cover_shadow()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "findings_count": len(report["findings"]),
                "cover_shadow_results": report["plans"]["cover_shadow_region"]["result_count"],
                "passing_lane_results": report["plans"]["passing_lane_denial"]["result_count"],
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
