"""AFL-08 time_to_arrival substrate verifier.

This slice closes the Q4 lane-coverage typed gap by adding a conservative
static-point reachability primitive. It does not claim pitch control,
cover-shadow, player intent, or tactical causation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import (
    TacticalQueryExecutor,
    execution_result_rows,
    runtime_parameters,
    time_to_arrival_anchor_record,
)
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.verification.afl_substrate_q4 import (
    MATCH_IDS,
    _eq_predicate,
    _evidence,
    _number_param,
    _status_counts,
    q4_document,
)
from tqe.verification.afl_validation_factory import (
    ValidationFactorySpec,
    attach_validation_factory,
    validate_proof_carrying_records,
)


REPORT_PATH = Path("artifacts/autonomous/afl-time-to-arrival-verification-report.json")
EXPECTATION_PATH = Path("delivery/autonomous/afl09a/frozen-expectations/time_to_arrival_q4.json")
PLAN_ARTIFACT_PATH = Path("config/query-plans/q4_compact_then_switch_reachability.experimental.v1.json")

REQUIRED_PROHIBITED_CLAIMS = {
    "pitch_control_inferred",
    "lane_denial_quality_inferred",
    "cover_shadow_inferred",
    "moving_target_interception_inferred",
    "player_intent_inferred",
    "defender_intent_inferred",
    "decision_quality_inferred",
    "tactical_causation_inferred",
    "pass_probability_inferred",
    "pass_was_optimal",
}

VALIDATION_FACTORY_SPEC = ValidationFactorySpec(
    factory_id="afl09a.time_to_arrival_q4.0_1_0",
    subject_ref="recipe:q4_compact_then_switch_reachability_v1:0.1.0",
    expectation_path=EXPECTATION_PATH,
    source_verifier="tqe.verification.afl_time_to_arrival",
    threshold_version="time_to_arrival_q4.v0.1.0:max_arrival=2.0:max_speed=7.0",
    required_prohibited_claims=frozenset(REQUIRED_PROHIBITED_CLAIMS),
    required_check_keys=(
        "generic_execution",
        "time_to_arrival_clause_exercised",
        "q4_lane_coverage_gap_closed",
        "requested_evidence_complete",
        "result_or_honest_zero",
        "unknown_fixture_exercised",
    ),
)


def time_to_arrival_document() -> dict[str, Any]:
    payload = q4_document()
    recipe = payload["recipe"]
    recipe.update(
        {
            "recipe_id": "q4_compact_then_switch_reachability_v1",
            "recipe_version": "0.1.0",
            "display_name": "Compact Block Then Switch With Reachability",
            "description": (
                "Experimental Q4 composition: a controlled pass is observed as a switch of play, "
                "the defending outfield unit is compact at release, defending-team width increases after "
                "reception, and opposing observed outfield candidates cannot reach the switch receiver's "
                "static reception point within the declared threshold."
            ),
            "output_classifications": ["Q4_COMPACT_THEN_SWITCH_LANE_REACHABILITY"],
            "allowed_claims": [
                "A controlled pass moved the ball from one lateral side to the opposite side under declared thresholds.",
                "Defending outfield width/depth was measured from observed tracking positions.",
                "Observed defending-team width increased across the switch anchor under declared thresholds.",
                "Observed opposing outfield candidates were evaluated against a declared static-point arrival-time threshold.",
            ],
            "disallowed_claims": [
                "The system inferred pitch control, cover shadow, player intent, defender intent, or tactical causation.",
                "The system solved moving-target interception or pass probability.",
                "The switch was tactically optimal or caused the defensive change.",
            ],
            "limitations": [
                "time_to_arrival v0.1 is static-point reachability under a declared straight-line speed assumption.",
                "A reachable verdict is an optimistic point-mass bound because current heading and momentum are ignored in v0.1.",
                "FAIL means no observed candidate in the declared scope reached the static point within the threshold.",
                "It does not prove complete lane denial or coaching-quality coverage.",
            ],
        }
    )
    recipe["parameters"].extend(
        [
            _number_param(
                "coverage_maximum_arrival_seconds",
                "second",
                2.0,
                "Maximum observed opposing-candidate arrival time to the switch receiver point.",
            ),
            _number_param(
                "coverage_maximum_player_speed_mps",
                "none",
                7.0,
                "Declared straight-line speed assumption for static-point reachability.",
            ),
            _number_param(
                "coverage_minimum_observed_candidates",
                "count",
                1,
                "Minimum observed candidate count before reachability can be PASS/FAIL.",
            ),
        ]
    )
    plan = payload["draft_plan"]
    plan.update(
        {
            "plan_id": "q4_compact_then_switch_reachability",
            "plan_version": "0.1.0",
            "recipe_id": recipe["recipe_id"],
            "recipe_version": recipe["recipe_version"],
            "classification_mode": "exhaustive",
        }
    )
    plan["nodes"].extend(
        [
            {
                "kind": "primitive",
                "node_id": "lane_reachability",
                "catalog_ref": "time_to_arrival",
                "version": "0.1.0",
                "inputs": {
                    "anchors": {"source_node_id": "switch_of_play", "output_name": "anchor_evaluations"}
                },
                "parameters": {
                    "frame_field": {"payload_type": "enum", "unit": "none", "value": "controlled_reception_frame_id"},
                    "target_mode": {"payload_type": "enum", "unit": "none", "value": "entity"},
                    "target_entity_field": {"payload_type": "enum", "unit": "none", "value": "receiver_id"},
                    "candidate_scope": {
                        "payload_type": "enum",
                        "unit": "none",
                        "value": "opposition_outfield_to_anchor_team",
                    },
                    "maximum_arrival_seconds": {"kind": "parameter", "name": "coverage_maximum_arrival_seconds"},
                    "maximum_player_speed_mps": {"kind": "parameter", "name": "coverage_maximum_player_speed_mps"},
                    "minimum_observed_candidates": {"kind": "parameter", "name": "coverage_minimum_observed_candidates"},
                },
            },
            _eq_predicate("lane_not_covered", "lane_reachability", "time_to_arrival_status", "FAIL"),
        ]
    )
    plan["classification_rules"] = [
        {
            "label": "Q4_COMPACT_THEN_SWITCH_LANE_REACHABILITY",
            "predicate_ids": ["switch_pass", "width_change_pass", "lane_not_covered"],
            "description": (
                "Compact before a switch, defending width increases afterward, and no observed opposing "
                "outfield candidate reaches the switch receiver point within the declared threshold."
            ),
        }
    ]
    plan["anchor_source"] = {"source_node_id": "lane_reachability", "output_name": "anchor_evaluations"}
    for field in [
        "time_to_arrival_status",
        "time_to_arrival_reason",
        "arrival_frame_id",
        "target_point",
        "candidate_scope",
        "candidate_player_ids",
        "observed_candidate_player_ids",
        "arrival_player_ids",
        "nearest_arrival_player_id",
        "minimum_arrival_seconds",
        "maximum_arrival_seconds",
        "maximum_player_speed_mps",
        "reachability_model",
        "momentum_policy",
        "reachable_verdict_bias",
        "coverage_status",
    ]:
        plan["requested_evidence"].append(_evidence("lane_reachability", field))
    return payload


def verify_time_to_arrival() -> dict[str, Any]:
    document_payload = time_to_arrival_document()
    PLAN_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_ARTIFACT_PATH.write_text(json.dumps(document_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    document = TacticalQueryDocument.model_validate(document_payload)
    bound_plan = bind_document(document)
    executor = TacticalQueryExecutor()
    execution = executor.execute(bound_plan)
    rows = execution_result_rows(execution)
    evidence_failure_count = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    probe = probe_first_period(executor, bound_plan)
    proof_carrying = validate_proof_carrying_records(proof_carrying_records(probe))
    honest_zero = (
        not rows
        and execution.status == ExecutionStatus.PASS
        and execution.provenance.get("compatibility_profile") == "generic"
        and evidence_failure_count == 0
    )
    findings: list[dict[str, str]] = []
    if execution.status != ExecutionStatus.PASS:
        findings.append({"code": "execution_not_pass", "message": f"Execution status was {execution.status}.", "path": "execution.status"})
    if evidence_failure_count:
        findings.append({"code": "requested_evidence_missing", "message": f"{evidence_failure_count} requested evidence failures.", "path": "execution.provenance.requested_evidence_failures"})
    if proof_carrying["status"] != "PASS":
        findings.append({"code": "proof_carrying_rows_failed", "message": "time_to_arrival proof-carrying records did not satisfy PASS/FAIL/UNKNOWN branch discipline.", "path": "proof_carrying"})
    if not rows and not honest_zero:
        findings.append({"code": "zero_not_honest", "message": "Zero-result execution did not satisfy honest-zero conditions.", "path": "execution"})
    report = {
        "schema_version": "afl.time_to_arrival.v1",
        "milestone": "AFL-08 time_to_arrival substrate / Q4 lane-coverage gap closure",
        "status": "PASS" if not findings else "FAIL",
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
        },
        "slice_unlocks": {
            "time_to_arrival": "Static-point reachability for observed candidate players under declared threshold.",
            "q4": "The previous Q4 lane-coverage typed gap now compiles as a reachability clause.",
        },
        "execution": {
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "compatibility_profile": execution.provenance.get("compatibility_profile"),
            "result_count": len(rows),
            "result_mode": "OBSERVED_RESULTS" if rows else "HONEST_ZERO",
            "honest_zero": honest_zero,
            "requested_evidence_failure_count": evidence_failure_count,
            "runtime_value_count": execution.provenance.get("runtime_value_count"),
            "runtime_trace_hash": execution.provenance.get("runtime_trace_hash"),
        },
        "probe": probe,
        "proof_carrying": {
            **proof_carrying,
            "real_row_status_counts": probe.get("time_to_arrival_status_counts", {}),
            "unknown_fixture": probe.get("unknown_fixture", {}),
            "branch_source_note": (
                "PASS/FAIL are exercised by real Q4 first-period rows. UNKNOWN is exercised by an "
                "adversarial runtime fixture using a real anchor with a missing target point, because "
                "the observed Q4 rows in this corpus do not naturally produce UNKNOWN."
            ),
        },
        "claim_boundary": {
            "dependency_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "required_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "enforced_in_report": True,
        },
        "checks": {
            "generic_execution": execution.provenance.get("compatibility_profile") == "generic",
            "time_to_arrival_clause_exercised": probe.get("time_to_arrival_count", 0) > 0,
            "q4_lane_coverage_gap_closed": execution.status == ExecutionStatus.PASS,
            "requested_evidence_complete": evidence_failure_count == 0,
            "result_or_honest_zero": bool(rows) or honest_zero,
            "unknown_fixture_exercised": probe.get("unknown_fixture", {}).get("time_to_arrival_status") == "UNKNOWN",
        },
        "findings": findings,
    }
    return attach_validation_factory(report, rows=rows, spec=VALIDATION_FACTORY_SPEC)


def probe_first_period(executor: TacticalQueryExecutor, bound_plan: Any) -> dict[str, Any]:
    params = runtime_parameters(bound_plan)
    state = executor._execute_period(
        bound_plan=bound_plan,
        match_id=bound_plan.match_ids[0],
        period=bound_plan.periods[0],
        params=params,
        compatibility_profile=executor.compatibility_profile,
    )

    def records(node_id: str, output_name: str = "anchor_evaluations") -> list[dict[str, Any]]:
        value = state.runtime_values[node_id][output_name]
        return [record for record in value.value if isinstance(record, dict)]

    reachability = records("lane_reachability")
    switch = records("switch_of_play")
    unknown_fixture = {}
    if switch:
        unknown_fixture = time_to_arrival_anchor_record(
            state=state,
            anchor=switch[0],
            frame_field="controlled_reception_frame_id",
            target_mode="fields",
            target_entity_field="receiver_id",
            target_x_field="zone_ball_x_m",
            target_y_field="zone_ball_y_m",
            candidate_scope="opposition_outfield_to_anchor_team",
            maximum_arrival_seconds=2.0,
            maximum_player_speed_mps=7.0,
            minimum_observed_candidates=1,
        ) or {}
    return {
        "match_id": bound_plan.match_ids[0],
        "period": bound_plan.periods[0],
        "time_to_arrival_count": len(reachability),
        "time_to_arrival_status_counts": _status_counts(reachability, "time_to_arrival_status"),
        "coverage_status_counts": _status_counts(reachability, "coverage_status"),
        "unknown_fixture": {
            "time_to_arrival_status": unknown_fixture.get("time_to_arrival_status"),
            "time_to_arrival_reason": unknown_fixture.get("time_to_arrival_reason"),
            "fixture_type": "real_anchor_missing_target_point",
        },
        "switch_count": len(switch),
        "width_change_count": len(records("width_change_after_switch")),
    }


def proof_carrying_records(probe: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    counts = probe.get("time_to_arrival_status_counts", {})
    if int(counts.get("PASS", 0)) > 0:
        rows.append({"judgement": "PASS", "witnesses": [{"source": "time_to_arrival", "count": int(counts["PASS"])}]})
    if int(counts.get("FAIL", 0)) > 0:
        rows.append({"judgement": "FAIL", "evaluation_domain_complete": True, "source": "time_to_arrival", "count": int(counts["FAIL"])})
    if int(counts.get("UNKNOWN", 0)) > 0:
        rows.append({"judgement": "UNKNOWN", "unmet_premises": ["time_to_arrival_unknown"], "count": int(counts["UNKNOWN"])})
    fixture = probe.get("unknown_fixture", {})
    if int(counts.get("UNKNOWN", 0)) == 0 and fixture.get("time_to_arrival_status") == "UNKNOWN":
        rows.append(
            {
                "judgement": "UNKNOWN",
                "unmet_premises": [str(fixture.get("time_to_arrival_reason") or "time_to_arrival_unknown_fixture")],
                "source": "adversarial_runtime_fixture",
                "count": 1,
            }
        )
    return rows


def main() -> int:
    report = verify_time_to_arrival()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
