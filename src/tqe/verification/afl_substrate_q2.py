"""AFL-08 Q2 capstone verifier.

Q2 asks for carries that break pressure and lead to a third-player layoff. In
v0.1 this is interpreted literally and narrowly:

- a conservative carry_episode is observed;
- nearest-defender pressure distance increases across the carry under frozen
  thresholds;
- the carry's terminal pass is the input pass of an event-linked one-touch
  relay;
- the relay's onward pass has a terminal controlled reception;
- the carrier, relay player, and terminal receiver are three distinct players.

It does not claim dribbling skill, pressure-breaking quality, third-man intent,
causation, decision quality, optimality, or pass probability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows, runtime_parameters
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.verification.afl_substrate_q4 import _eq_predicate, _evidence, _number_param, _status_counts
from tqe.verification.afl_validation_factory import (
    ValidationFactorySpec,
    attach_validation_factory,
    validate_proof_carrying_records,
)


REPORT_PATH = Path("artifacts/autonomous/afl-substrate-q2-verification-report.json")
EXPECTATION_PATH = Path("delivery/autonomous/afl09a/frozen-expectations/substrate_q2.json")
PLAN_ARTIFACT_PATH = Path("config/query-plans/q2_carry_breaks_pressure_layoff.experimental.v1.json")

MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
REQUIRED_PROHIBITED_CLAIMS = {
    "dribbling_skill_inferred",
    "pressure_break_quality_inferred",
    "defender_bypassed_by_carry",
    "third_man_combination_claimed",
    "planned_combination_inferred",
    "player_intent_inferred",
    "tactical_causation_inferred",
    "decision_quality_inferred",
    "optimality_inferred",
    "pass_probability_inferred",
    "pass_was_optimal",
}

VALIDATION_FACTORY_SPEC = ValidationFactorySpec(
    factory_id="afl09a.substrate_q2.0_1_0",
    subject_ref="recipe:q2_carry_breaks_pressure_layoff_v1:0.1.0",
    expectation_path=EXPECTATION_PATH,
    source_verifier="tqe.verification.afl_substrate_q2",
    threshold_version=(
        "q2_carry_breaks_pressure_layoff.v0.1.0:"
        "carry_min_displacement=3.0:carry_max_seconds=10.0:"
        "pressure_start_max_distance=4.0:pressure_distance_increase=2.0:"
        "relay_max_event_gap=3.0:max_relay_dwell=0.56"
    ),
    required_prohibited_claims=frozenset(REQUIRED_PROHIBITED_CLAIMS),
    required_check_keys=(
        "generic_execution",
        "q2_compiles_end_to_end",
        "requested_evidence_complete",
        "carry_clause_exercised",
        "pressure_reduction_clause_exercised",
        "layoff_clause_exercised",
        "result_or_honest_zero",
        "proof_carrying_real_rows",
        "claim_boundary_present",
    ),
)

Q2_EVIDENCE_FIELDS = [
    "carry_relay_layoff_status",
    "carry_relay_layoff_reason",
    "carry_episode_id",
    "carrier_id",
    "carry_start_frame_id",
    "carry_end_frame_id",
    "terminal_pass_id",
    "displacement_m",
    "carry_forward_progression_m",
    "control_model",
    "control_bias",
    "pressure_change_status",
    "pressure_change_reason",
    "pressure_before_distance_m",
    "pressure_after_distance_m",
    "pressure_distance_delta_m",
    "pressure_minimum_distance_increase_m",
    "relay_input_pass_episode_id",
    "relay_pass_episode_id",
    "relay_player_id",
    "relay_touch_frame_id",
    "terminal_receiver_id",
    "terminal_controlled_reception_frame_id",
    "terminal_forward_progression_m",
    "pass_chain_status",
    "three_distinct_players",
]


def q2_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "q2_carry_breaks_pressure_layoff_v1",
            "recipe_version": "0.1.0",
            "display_name": "Carry Reduces Pressure Before Third-Player Layoff",
            "description": (
                "Experimental northstar Q2 composition: a conservative carry is observed, "
                "nearest-defender distance increases across the carry, the terminal pass "
                "feeds an event-linked one-touch relay, and the onward pass reaches a "
                "third player with controlled reception."
            ),
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "A conservative movement-under-control carry was observed.",
                "Nearest-defender distance increased across the carry under declared thresholds.",
                "The carry terminal pass was the input pass of an observed one-touch relay.",
                "The carrier, relay player, and terminal receiver were three distinct observed players.",
            ],
            "disallowed_claims": [
                "The system inferred dribbling skill or that the carry beat a defender.",
                "The system inferred pressure-breaking quality, player intent, tactical causation, or decision quality.",
                "The system claimed a planned third-man combination, pass optimality, or pass probability.",
            ],
            "limitations": [
                "Pressure break is operationalized as nearest-defender distance increasing across the carry.",
                "Layoff is an event-linked one-touch relay with terminal controlled reception, not a planned combination claim.",
                "UNKNOWN pressure, carry, or relay evidence is excluded rather than coerced to a match.",
            ],
            "output_classifications": ["Q2_CARRY_PRESSURE_REDUCTION_THIRD_PLAYER_LAYOFF"],
            "parameters": [
                _number_param("maximum_carry_seconds", "second", 10.0, "Maximum carry interval."),
                _number_param("minimum_displacement_m", "metre", 3.0, "Minimum carry displacement."),
                _number_param("control_distance_m", "metre", 2.5, "Maximum ball-carrier control distance."),
                _number_param("nearest_teammate_margin_m", "metre", 1.0, "Nearest-team control margin."),
                _number_param("maximum_ball_player_speed_delta_mps", "none", 10.0, "Maximum ball/player velocity delta."),
                _number_param("minimum_controlled_frame_ratio", "none", 1.0, "Minimum controlled-frame ratio."),
                _number_param("minimum_comoving_frame_ratio", "none", 0.75, "Minimum co-moving ratio."),
                _number_param("maximum_missing_frame_ratio", "none", 0.02, "Maximum missing-tracking ratio."),
                _number_param("pressure_maximum_distance_m", "metre", 4.0, "Pressure distance threshold at carry start."),
                _number_param("pressure_minimum_distance_increase_m", "metre", 2.0, "Required nearest-defender distance increase."),
                _number_param("pressure_minimum_closing_speed_mps", "none", -5.0, "Permissive closing-speed floor for pressure-distance evidence."),
                _number_param("pressure_maximum_approach_angle_degrees", "none", 180.0, "Permissive approach-angle ceiling for pressure-distance evidence."),
                _number_param("velocity_lookback_seconds", "second", 0.4, "Pressure kinematic lookback interval."),
                _number_param("relay_max_event_gap_seconds", "second", 3.0, "Maximum event gap into relay pass."),
                _number_param("relay_touch_distance_m", "metre", 2.75, "Maximum ball-player relay touch distance."),
                _number_param("maximum_relay_dwell_seconds", "second", 0.56, "Maximum relay dwell interval."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "q2_carry_breaks_pressure_layoff_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "q2_carry_breaks_pressure_layoff",
            "plan_version": "0.1.0",
            "recipe_id": "q2_carry_breaks_pressure_layoff_v1",
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "nodes": [
                {"kind": "primitive", "node_id": "controlled_pass", "catalog_ref": "controlled_pass_episode", "version": "0.1.0"},
                {
                    "kind": "primitive",
                    "node_id": "carry_episode",
                    "catalog_ref": "carry_episode",
                    "version": "0.1.0",
                    "inputs": {"controlled_pass_anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"}},
                    "parameters": {
                        "maximum_carry_seconds": {"kind": "parameter", "name": "maximum_carry_seconds"},
                        "minimum_displacement_m": {"kind": "parameter", "name": "minimum_displacement_m"},
                        "control_distance_m": {"kind": "parameter", "name": "control_distance_m"},
                        "nearest_teammate_margin_m": {"kind": "parameter", "name": "nearest_teammate_margin_m"},
                        "maximum_ball_player_speed_delta_mps": {"kind": "parameter", "name": "maximum_ball_player_speed_delta_mps"},
                        "minimum_controlled_frame_ratio": {"kind": "parameter", "name": "minimum_controlled_frame_ratio"},
                        "minimum_comoving_frame_ratio": {"kind": "parameter", "name": "minimum_comoving_frame_ratio"},
                        "maximum_missing_frame_ratio": {"kind": "parameter", "name": "maximum_missing_frame_ratio"},
                    },
                },
                _pressure_node("pressure_at_carry_start", "carry_start_frame_id"),
                _pressure_node("pressure_at_carry_end", "carry_end_frame_id"),
                {
                    "kind": "primitive",
                    "node_id": "pressure_distance_change",
                    "catalog_ref": "change_across_anchor",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "carry_episode", "output_name": "anchor_evaluations"},
                        "before_evaluations": {"source_node_id": "pressure_at_carry_start", "output_name": "anchor_evaluations"},
                        "after_evaluations": {"source_node_id": "pressure_at_carry_end", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "before_value_field": {"payload_type": "enum", "unit": "none", "value": "nearest_defender_distance_m"},
                        "after_value_field": {"payload_type": "enum", "unit": "none", "value": "nearest_defender_distance_m"},
                        "before_status_field": {"payload_type": "enum", "unit": "none", "value": "pressure_status"},
                        "after_status_field": {"payload_type": "enum", "unit": "none", "value": "none"},
                        "required_status_value": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                        "change_mode": {"payload_type": "enum", "unit": "none", "value": "increase_at_least"},
                        "minimum_change_m": {"kind": "parameter", "name": "pressure_minimum_distance_increase_m"},
                        "maximum_before_value_m": {"kind": "parameter", "name": "pressure_maximum_distance_m"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "one_touch_relay",
                    "catalog_ref": "one_touch_relay_episode",
                    "version": "0.1.0",
                    "parameters": {
                        "relay_max_event_gap_seconds": {"kind": "parameter", "name": "relay_max_event_gap_seconds"},
                        "relay_touch_distance_m": {"kind": "parameter", "name": "relay_touch_distance_m"},
                        "maximum_relay_dwell_seconds": {"kind": "parameter", "name": "maximum_relay_dwell_seconds"},
                    },
                },
                {"kind": "primitive", "node_id": "terminal_controlled_pass", "catalog_ref": "controlled_pass_episode", "version": "0.1.0"},
                {
                    "kind": "primitive",
                    "node_id": "pass_chain",
                    "catalog_ref": "pass_chain_episode",
                    "version": "0.1.0",
                    "inputs": {
                        "relay_anchors": {"source_node_id": "one_touch_relay", "output_name": "anchor_evaluations"},
                        "terminal_controlled_pass_anchors": {"source_node_id": "terminal_controlled_pass", "output_name": "anchors"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "q2_chain",
                    "catalog_ref": "carry_relay_layoff_chain",
                    "version": "0.1.0",
                    "inputs": {
                        "carry_anchors": {"source_node_id": "carry_episode", "output_name": "anchor_evaluations"},
                        "pressure_change_evaluations": {"source_node_id": "pressure_distance_change", "output_name": "anchor_evaluations"},
                        "relay_anchors": {"source_node_id": "one_touch_relay", "output_name": "anchor_evaluations"},
                        "pass_chain_evaluations": {"source_node_id": "pass_chain", "output_name": "anchor_evaluations"},
                    },
                },
                _eq_predicate("q2_chain_pass", "q2_chain", "carry_relay_layoff_status", "PASS"),
            ],
            "classification_rules": [
                {
                    "label": "Q2_CARRY_PRESSURE_REDUCTION_THIRD_PLAYER_LAYOFF",
                    "predicate_ids": ["q2_chain_pass"],
                    "description": "Observed carry with nearest-defender distance increase followed by third-player one-touch layoff.",
                }
            ],
            "anchor_source": {"source_node_id": "q2_chain", "output_name": "anchor_evaluations"},
            "requested_evidence": [_evidence("q2_chain", field) for field in Q2_EVIDENCE_FIELDS],
        },
    }


def _pressure_node(node_id: str, frame_field: str) -> dict[str, Any]:
    return {
        "kind": "relation",
        "node_id": node_id,
        "catalog_ref": "pressure_on_carrier",
        "version": "0.1.0",
        "inputs": {"anchors": {"source_node_id": "carry_episode", "output_name": "anchor_evaluations"}},
        "parameters": {
            "frame_field": {"payload_type": "enum", "unit": "none", "value": frame_field},
            "carrier_id_field": {"payload_type": "enum", "unit": "none", "value": "carrier_id"},
            "maximum_pressure_distance_m": {"kind": "parameter", "name": "pressure_maximum_distance_m"},
            "minimum_closing_speed_mps": {"kind": "parameter", "name": "pressure_minimum_closing_speed_mps"},
            "maximum_approach_angle_degrees": {"kind": "parameter", "name": "pressure_maximum_approach_angle_degrees"},
            "minimum_pressure_duration_seconds": {"payload_type": "number", "unit": "second", "value": 0.0},
            "lookback_seconds": {"kind": "parameter", "name": "velocity_lookback_seconds"},
            "candidate_scope": {"payload_type": "enum", "unit": "none", "value": "defending_outfield"},
        },
    }


def verify_substrate_q2() -> dict[str, Any]:
    document_payload = q2_document()
    PLAN_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_ARTIFACT_PATH.write_text(json.dumps(document_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    document = TacticalQueryDocument.model_validate(document_payload)
    bound_plan = bind_document(document)
    executor = TacticalQueryExecutor()
    execution = executor.execute(bound_plan)
    rows = execution_result_rows(execution)
    evidence_failure_count = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    probe = probe_first_period(executor, bound_plan)
    proof_carrying = validate_proof_carrying_records(proof_carrying_records(rows, probe))
    honest_zero = (
        not rows
        and execution.status == ExecutionStatus.PASS
        and execution.provenance.get("compatibility_profile") == "generic"
        and evidence_failure_count == 0
        and probe.get("q2_chain_count", 0) > 0
    )

    findings: list[dict[str, str]] = []
    if execution.status != ExecutionStatus.PASS:
        findings.append({"code": "execution_not_pass", "message": f"Execution status was {execution.status}.", "path": "execution.status"})
    if execution.provenance.get("compatibility_profile") != "generic":
        findings.append({"code": "non_generic_execution", "message": "Q2 must run through the generic executor.", "path": "execution.provenance.compatibility_profile"})
    if evidence_failure_count:
        findings.append({"code": "requested_evidence_missing", "message": f"{evidence_failure_count} requested evidence failure(s).", "path": "execution.provenance.requested_evidence_failures"})
    if not rows and not honest_zero:
        findings.append({"code": "zero_not_honest", "message": "Zero-result execution did not satisfy honest-zero conditions.", "path": "execution"})
    if proof_carrying["status"] != "PASS":
        findings.append({"code": "proof_carrying_real_rows_failed", "message": "Q2 real rows did not satisfy proof-carrying branch discipline.", "path": "proof_carrying_real_rows"})

    sample = rows[0] if rows else {}
    report = {
        "schema_version": "afl.substrate_q2.v1",
        "milestone": "AFL-08 Q2 carry-pressure-layoff capstone",
        "status": "PASS" if not findings else "FAIL",
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
        },
        "slice_unlocks": {
            "q2": "Carries that reduce nearest-defender pressure and lead to a third-player one-touch layoff now compile end-to-end.",
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
            "real_row_status_counts": probe.get("q2_chain_status_counts", {}),
            "branch_source_note": (
                "Q2 is an honest-zero capstone in this corpus. PASS/FAIL/UNKNOWN branch discipline "
                "is exercised by real component rows; q2_chain rows exercise FAIL/UNKNOWN only."
            ),
        },
        "claim_boundary": {
            "dependency_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "required_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "enforced_in_report": True,
        },
        "sample_result": {
            "result_id": sample.get("result_id"),
            "classification": sample.get("classification"),
            "requested_evidence": sample.get("requested_evidence") if isinstance(sample, dict) else {},
        },
        "checks": {
            "generic_execution": execution.provenance.get("compatibility_profile") == "generic",
            "q2_compiles_end_to_end": execution.status == ExecutionStatus.PASS and (bool(rows) or honest_zero),
            "requested_evidence_complete": evidence_failure_count == 0,
            "carry_clause_exercised": probe.get("carry_count", 0) > 0,
            "pressure_reduction_clause_exercised": probe.get("pressure_change_count", 0) > 0,
            "layoff_clause_exercised": probe.get("relay_count", 0) > 0 and probe.get("pass_chain_count", 0) > 0,
            "result_or_honest_zero": bool(rows) or honest_zero,
            "proof_carrying_real_rows": proof_carrying["status"] == "PASS",
            "claim_boundary_present": True,
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

    def records(node_id: str) -> list[dict[str, Any]]:
        value = state.runtime_values[node_id]["anchor_evaluations"]
        return [record for record in value.value if isinstance(record, dict)]

    carry_records = records("carry_episode")
    pressure_change_records = records("pressure_distance_change")
    relay_records = records("one_touch_relay")
    pass_chain_records = records("pass_chain")
    q2_records = records("q2_chain")
    return {
        "match_id": bound_plan.match_ids[0],
        "period": bound_plan.periods[0],
        "carry_count": len(carry_records),
        "pressure_change_count": len(pressure_change_records),
        "relay_count": len(relay_records),
        "pass_chain_count": len(pass_chain_records),
        "q2_chain_count": len(q2_records),
        "carry_status_counts": _status_counts(carry_records, "carry_status"),
        "carry_reason_counts": _status_counts(carry_records, "carry_reason"),
        "pressure_change_status_counts": _status_counts(pressure_change_records, "change_status"),
        "q2_chain_status_counts": _status_counts(q2_records, "carry_relay_layoff_status"),
        "q2_chain_reason_counts": _status_counts(q2_records, "carry_relay_layoff_reason"),
    }


def proof_carrying_records(rows: list[dict[str, Any]], probe: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    branch_sources = [
        ("carry", probe.get("carry_status_counts", {}), probe.get("carry_reason_counts", {})),
        ("pressure_change", probe.get("pressure_change_status_counts", {}), {}),
        ("q2_chain", probe.get("q2_chain_status_counts", {}), probe.get("q2_chain_reason_counts", {})),
    ]
    if rows:
        records.append(
            {
                "judgement": "PASS",
                "witnesses": [{"source": "q2_chain", "count": len(rows)}],
            }
        )
    for source, counts, reasons in branch_sources:
        if int(counts.get("PASS", 0)) > 0:
            records.append({"judgement": "PASS", "witnesses": [{"source": source, "count": int(counts["PASS"])}]})
        if int(counts.get("FAIL", 0)) > 0:
            records.append(
                {
                    "judgement": "FAIL",
                    "evaluation_domain_complete": True,
                    "source": source,
                    "count": int(counts["FAIL"]),
                    "domain_evidence": sorted(reasons) if reasons else [f"{source}_evaluated"],
                }
            )
        if int(counts.get("UNKNOWN", 0)) > 0:
            unknown_reasons = [reason for reason in sorted(reasons) if reason]
            records.append(
                {
                    "judgement": "UNKNOWN",
                    "unmet_premises": unknown_reasons or [f"{source}_unknown"],
                    "count": int(counts["UNKNOWN"]),
                }
            )
    return records


def main() -> int:
    report = verify_substrate_q2()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
