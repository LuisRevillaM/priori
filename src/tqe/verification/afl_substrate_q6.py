"""AFL-08 substrate slices 4-5 and Q6 compile verifier.

This verifier continues the northstar-query-pulled substrate sequence:

4. velocity / closing_speed
5. pressure_on_carrier as a first-class capability

The stop gate is Q6: "throw-ins where the first action progresses past the
first observed line under pressure." In v0.1 this is interpreted literally and
narrowly:

- provider event type `ThrowIn_Play_Pass`;
- controlled reception is proven by `controlled_pass_episode`;
- receiver moves beyond observed geometric line rank 1;
- receiver is under observed nearest-defender pressure at controlled reception.

It does not claim a full restart routine, tactical line taxonomy, pressure
quality, intent, causation, or decision quality.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows, runtime_parameters
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.verification.afl_validation_factory import (
    ValidationFactorySpec,
    attach_validation_factory,
    validate_proof_carrying_records,
)
from tqe.write_mode import emit_tracked_artifact


REPORT_PATH = Path("artifacts/autonomous/afl-substrate-q6-verification-report.json")
EXPECTATION_PATH = Path("delivery/autonomous/afl09a/frozen-expectations/substrate_q6.json")
PLAN_ARTIFACT_PATH = Path("config/query-plans/q6_throw_in_first_action_under_pressure.experimental.v1.json")

MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
REQUIRED_PROHIBITED_CLAIMS = {
    "restart_routine_identified",
    "tactical_line_role_identified",
    "defensive_line_was_broken",
    "pressure_quality_inferred",
    "defender_intent_inferred",
    "player_intent_inferred",
    "decision_quality_inferred",
    "tactical_causation_inferred",
    "pass_probability_inferred",
    "pass_was_optimal",
}

VALIDATION_FACTORY_SPEC = ValidationFactorySpec(
    factory_id="afl09a.substrate_q6.0_1_0",
    subject_ref="recipe:q6_throw_in_first_action_under_pressure_v1:0.1.0",
    expectation_path=EXPECTATION_PATH,
    source_verifier="tqe.verification.afl_substrate_q6",
    threshold_version="q6_throw_in_first_action_under_pressure.v0.1.0",
    required_prohibited_claims=frozenset(REQUIRED_PROHIBITED_CLAIMS),
    required_check_keys=(
        "generic_execution",
        "q6_compiles_end_to_end",
        "requested_evidence_complete",
        "throw_in_action_clause_exercised",
        "slice_4_velocity_exercised",
        "slice_5_pressure_exercised",
        "result_or_honest_zero",
    ),
)


def q6_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "q6_throw_in_first_action_under_pressure_v1",
            "recipe_version": "0.1.0",
            "display_name": "Throw-In First Action Beyond Observed Line Under Pressure",
            "description": (
                "Experimental northstar Q6 composition: a provider throw-in pass is controlled, "
                "the receiver moves beyond observed geometric line rank 1, and observed "
                "nearest-defender pressure is present at controlled reception."
            ),
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "A provider ThrowIn_Play_Pass event was evaluated as the first action.",
                "The receiver moved beyond observed geometric line rank 1 under declared thresholds.",
                "Nearest-defender pressure was observed at the controlled reception frame.",
                "Velocity and closing speed are displacement-derived measurements, not intent or effort.",
            ],
            "disallowed_claims": [
                "The system identified a complete restart routine.",
                "The system identified tactical line roles or a definitive football line break.",
                "The defender intended to press or the receiver made a good/bad decision.",
                "Pressure quality, pass optimality, or completion probability was inferred.",
            ],
            "limitations": [
                "Throw-in is provider event type `ThrowIn_Play_Pass`, not a full restart model.",
                "Line rank 1 is a geometric ordering of observed defending bands, not a tactical line taxonomy.",
                "Pressure is nearest-defender distance plus closing-speed/approach-angle thresholds.",
                "UNKNOWN evidence is excluded rather than treated as no pressure.",
            ],
            "output_classifications": ["Q6_THROW_IN_FIRST_ACTION_PAST_OBSERVED_LINE_UNDER_PRESSURE"],
            "parameters": [
                _number_param("goal_side_buffer_m", "metre", 1.0, "Minimum defender distance beyond ball for line candidates."),
                _number_param("line_band_width_m", "metre", 2.5, "Maximum x-span for one observed line band."),
                _number_param("minimum_line_defenders", "count", 2, "Minimum defenders per observed line band."),
                _number_param("line_buffer_m", "metre", 0.5, "Distance from line treated as level."),
                _number_param("pressure_maximum_distance_m", "metre", 4.0, "Nearest-defender pressure distance threshold."),
                _number_param("pressure_minimum_closing_speed_mps", "none", 0.0, "Minimum defender-to-carrier closing speed."),
                _number_param("pressure_maximum_approach_angle_degrees", "none", 110.0, "Maximum defender approach angle."),
                _number_param("pressure_minimum_duration_seconds", "second", 0.0, "Minimum pressure duration ending at reception."),
                _number_param("velocity_lookback_seconds", "second", 0.4, "Velocity/closing-speed lookback interval."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "q6_throw_in_first_action_under_pressure_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "q6_throw_in_first_action_under_pressure",
            "plan_version": "0.1.0",
            "recipe_id": "q6_throw_in_first_action_under_pressure_v1",
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "nodes": [
                {
                    "kind": "primitive",
                    "node_id": "throw_in_events",
                    "catalog_ref": "action_event_anchor",
                    "version": "0.1.0",
                    "parameters": {
                        "action_type": {"payload_type": "enum", "unit": "none", "value": "throw_in_successful_pass"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "controlled_throw_in_pass",
                    "catalog_ref": "controlled_pass_episode",
                    "version": "0.1.0",
                    "parameters": {
                        "event_type_filter": {"payload_type": "enum", "unit": "none", "value": "ThrowIn_Play_Pass"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "tracking_quality",
                    "catalog_ref": "tracking_quality",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_throw_in_pass", "output_name": "anchors"},
                    },
                    "parameters": {
                        "frame_field": {"payload_type": "enum", "unit": "none", "value": "controlled_reception_frame_id"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "receiver_velocity",
                    "catalog_ref": "velocity",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_throw_in_pass", "output_name": "anchors"},
                    },
                    "parameters": {
                        "frame_field": {"payload_type": "enum", "unit": "none", "value": "controlled_reception_frame_id"},
                        "entity_id_field": {"payload_type": "enum", "unit": "none", "value": "receiver_id"},
                        "lookback_seconds": {"kind": "parameter", "name": "velocity_lookback_seconds"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "first_line_at_release",
                    "catalog_ref": "multi_line_model",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_throw_in_pass", "output_name": "anchors"},
                    },
                    "parameters": {
                        "goal_side_buffer_m": {"kind": "parameter", "name": "goal_side_buffer_m"},
                        "line_band_width_m": {"kind": "parameter", "name": "line_band_width_m"},
                        "minimum_line_defenders": {"kind": "parameter", "name": "minimum_line_defenders"},
                        "target_line_rank": {"payload_type": "number", "unit": "count", "value": 1},
                        "anchor_frame_field": {"payload_type": "enum", "unit": "none", "value": "physical_release_frame_id"},
                    },
                },
                _relative_position_node("receiver_release_position", "physical_release_frame_id"),
                _relative_position_node("receiver_reception_position", "controlled_reception_frame_id"),
                {
                    "kind": "primitive",
                    "node_id": "controlled_first_line_transition",
                    "catalog_ref": "controlled_line_break_episode",
                    "version": "0.1.0",
                    "inputs": {
                        "controlled_pass_anchors": {"source_node_id": "controlled_throw_in_pass", "output_name": "anchors"},
                        "line_evaluations": {"source_node_id": "first_line_at_release", "output_name": "anchor_evaluations"},
                        "release_relative_positions": {"source_node_id": "receiver_release_position", "output_name": "anchor_evaluations"},
                        "reception_relative_positions": {"source_node_id": "receiver_reception_position", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "line_buffer_m": {"kind": "parameter", "name": "line_buffer_m"},
                    },
                },
                {
                    "kind": "relation",
                    "node_id": "reception_pressure",
                    "catalog_ref": "pressure_on_carrier",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_first_line_transition", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "frame_field": {"payload_type": "enum", "unit": "none", "value": "controlled_reception_frame_id"},
                        "carrier_id_field": {"payload_type": "enum", "unit": "none", "value": "receiver_id"},
                        "maximum_pressure_distance_m": {"kind": "parameter", "name": "pressure_maximum_distance_m"},
                        "minimum_closing_speed_mps": {"kind": "parameter", "name": "pressure_minimum_closing_speed_mps"},
                        "maximum_approach_angle_degrees": {"kind": "parameter", "name": "pressure_maximum_approach_angle_degrees"},
                        "minimum_pressure_duration_seconds": {"kind": "parameter", "name": "pressure_minimum_duration_seconds"},
                        "lookback_seconds": {"kind": "parameter", "name": "velocity_lookback_seconds"},
                        "candidate_scope": {"payload_type": "enum", "unit": "none", "value": "defending_outfield"},
                    },
                },
                _eq_predicate("first_line_transition_pass", "controlled_first_line_transition", "line_break_status", "PASS"),
                _eq_predicate("pressure_pass", "reception_pressure", "pressure_status", "PASS"),
            ],
            "classification_rules": [
                {
                    "label": "Q6_THROW_IN_FIRST_ACTION_PAST_OBSERVED_LINE_UNDER_PRESSURE",
                    "predicate_ids": ["first_line_transition_pass", "pressure_pass"],
                    "description": "Throw-in controlled reception moved beyond observed line rank 1 while pressure was observed at reception.",
                },
            ],
            "anchor_source": {
                "source_node_id": "controlled_first_line_transition",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": requested_evidence(),
        },
    }


def requested_evidence() -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for field in [
        "pass_episode_id",
        "event_type",
        "passer_id",
        "receiver_id",
        "physical_release_frame_id",
        "controlled_reception_frame_id",
        "forward_progression_m",
    ]:
        evidence.append(_evidence("controlled_throw_in_pass", field, output_name="anchors"))
    for field in [
        "line_break_status",
        "line_break_reason",
        "line_x_m",
        "release_relative_position_status",
        "reception_relative_position_status",
    ]:
        evidence.append(_evidence("controlled_first_line_transition", field))
    for field in [
        "multi_line_status",
        "target_line_rank",
        "observed_line_count",
        "defensive_line_player_ids",
    ]:
        evidence.append(_evidence("first_line_at_release", field))
    for field in [
        "pressure_status",
        "pressure_reason",
        "nearest_defender_id",
        "nearest_defender_distance_m",
        "closing_speed_mps",
        "approach_angle_degrees",
        "coverage_status",
    ]:
        evidence.append(_evidence("reception_pressure", field))
    evidence.append(_evidence("receiver_velocity", "speed_mps"))
    evidence.append(_evidence("tracking_quality", "tracking_quality_status"))
    return evidence


def verify_substrate_q6() -> dict[str, Any]:
    document_payload = q6_document()
    plan_artifact_drift = emit_tracked_artifact(
        PLAN_ARTIFACT_PATH,
        json.dumps(document_payload, indent=2, sort_keys=True) + "\n",
    )
    document = TacticalQueryDocument.model_validate(document_payload)
    bound_plan = bind_document(document)
    executor = TacticalQueryExecutor()
    execution = executor.execute(bound_plan)
    rows = execution_result_rows(execution)
    probe = probe_first_period(executor, bound_plan)
    evidence_failure_count = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    honest_zero = (
        not rows
        and execution.status == ExecutionStatus.PASS
        and execution.provenance.get("compatibility_profile") == "generic"
        and evidence_failure_count == 0
    )
    proof_carrying = validate_proof_carrying_records(proof_carrying_records(probe))
    findings: list[dict[str, str]] = []
    if plan_artifact_drift is not None:
        findings.append(
            {
                "code": "plan_artifact_drift",
                "message": plan_artifact_drift["message"],
                "path": str(PLAN_ARTIFACT_PATH),
            }
        )
    if execution.status != ExecutionStatus.PASS:
        findings.append({"code": "execution_not_pass", "message": f"Execution status was {execution.status}.", "path": "execution.status"})
    if evidence_failure_count:
        findings.append({"code": "requested_evidence_missing", "message": f"{evidence_failure_count} requested evidence failures.", "path": "execution.provenance.requested_evidence_failures"})
    if not rows and not honest_zero:
        findings.append({"code": "zero_not_honest", "message": "Zero-result Q6 execution did not satisfy honest-zero conditions.", "path": "execution"})
    if proof_carrying["status"] != "PASS":
        findings.append({"code": "proof_carrying_rows_failed", "message": "Real substrate rows did not satisfy PASS/FAIL/UNKNOWN proof-carrying discipline.", "path": "proof_carrying"})

    report = {
        "schema_version": "afl.substrate_q6.v1",
        "milestone": "AFL-08 substrate slices 4-5 / Q6 stop gate",
        "status": "PASS" if not findings else "FAIL",
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
        },
        "slice_unlocks": {
            "slice_4": "velocity + closing-speed measurements -> kinematic pressure inputs",
            "slice_5": "pressure_on_carrier -> first-class observed pressure capability",
            "q6": "ThrowIn_Play_Pass controlled reception past observed line rank 1 under pressure",
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
        "proof_carrying_real_rows": proof_carrying,
        "claim_boundary": {
            "dependency_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "required_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "enforced_in_report": True,
        },
        "checks": {
            "generic_execution": execution.provenance.get("compatibility_profile") == "generic",
            "q6_compiles_end_to_end": execution.status == ExecutionStatus.PASS and evidence_failure_count == 0,
            "requested_evidence_complete": evidence_failure_count == 0,
            "throw_in_action_clause_exercised": probe.get("throw_in_action_count", 0) > 0 and probe.get("throw_in_pass_count", 0) > 0,
            "slice_4_velocity_exercised": probe.get("velocity_count", 0) > 0,
            "slice_5_pressure_exercised": probe.get("pressure_count", 0) > 0,
            "result_or_honest_zero": bool(rows) or honest_zero,
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

    throw_events = records("throw_in_events")
    controlled = records("controlled_throw_in_pass", "anchors")
    velocity = records("receiver_velocity")
    pressure = records("reception_pressure")
    line_transition = records("controlled_first_line_transition")
    return {
        "match_id": bound_plan.match_ids[0],
        "period": bound_plan.periods[0],
        "throw_in_action_count": len(throw_events),
        "throw_in_pass_count": len(controlled),
        "velocity_count": len(velocity),
        "pressure_count": len(pressure),
        "line_transition_count": len(line_transition),
        "velocity_status_counts": _status_counts(velocity, "velocity_status"),
        "pressure_status_counts": _status_counts(pressure, "pressure_status"),
        "line_break_status_counts": _status_counts(line_transition, "line_break_status"),
    }


def proof_carrying_records(probe: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    branch_sources = [
        ("velocity", probe.get("velocity_status_counts", {})),
        ("pressure", probe.get("pressure_status_counts", {})),
        ("line_transition", probe.get("line_break_status_counts", {})),
    ]
    for source, counts in branch_sources:
        if int(counts.get("PASS", 0)) > 0:
            rows.append({"judgement": "PASS", "witnesses": [{"source": source, "count": int(counts["PASS"])}]})
        if int(counts.get("FAIL", 0)) > 0:
            rows.append({"judgement": "FAIL", "evaluation_domain_complete": True, "source": source, "count": int(counts["FAIL"])})
        if int(counts.get("UNKNOWN", 0)) > 0:
            rows.append({"judgement": "UNKNOWN", "unmet_premises": [f"{source}_unknown"], "count": int(counts["UNKNOWN"])})
    return rows


def _status_counts(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(field))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _relative_position_node(node_id: str, entity_frame_field: str) -> dict[str, Any]:
    return {
        "kind": "primitive",
        "node_id": node_id,
        "catalog_ref": "relative_position_to_line",
        "version": "0.1.0",
        "inputs": {
            "line_evaluations": {"source_node_id": "first_line_at_release", "output_name": "anchor_evaluations"},
            "entity_anchors": {"source_node_id": "controlled_throw_in_pass", "output_name": "anchors"},
        },
        "parameters": {
            "entity_id_field": {"payload_type": "enum", "unit": "none", "value": "receiver_id"},
            "entity_frame_field": {"payload_type": "enum", "unit": "none", "value": entity_frame_field},
            "line_buffer_m": {"kind": "parameter", "name": "line_buffer_m"},
        },
    }


def _eq_predicate(node_id: str, source_node_id: str, output_name: str, value: str) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": {"source_node_id": source_node_id, "output_name": output_name},
        "operator": {"name": "eq", "version": "1.0.0"},
        "compare": {"payload_type": "enum", "unit": "none", "value": value},
    }


def _evidence(source_node_id: str, field: str, *, output_name: str = "anchor_evaluations") -> dict[str, Any]:
    return {
        "alias": field,
        "source": {"source_node_id": source_node_id, "output_name": output_name},
        "field": field,
        "required": True,
    }


def _number_param(name: str, unit: str, value: float, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "payload_type": "number",
        "unit": unit,
        "default": {"payload_type": "number", "unit": unit, "value": value},
        "description": description,
    }


def main() -> None:
    report = verify_substrate_q6()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
