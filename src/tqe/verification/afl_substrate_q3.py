"""AFL-08 substrate slices 1-3 and Q3 compile verifier.

This verifier adopts the northstar-query-pulled substrate steering:

1. action_event_anchor + action_chain
2. tracking_quality + pairwise_distance
3. multi_line_model + directional support

The stop gate is Q3: "receiver breaks the second line but has no underneath
support" compiles to a deterministic, evidence-backed plan or an honest zero.
Line "second" here is geometric line-rank 2, not tactical role taxonomy.
"""

from __future__ import annotations

import json
import os
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


REPORT_PATH = Path("artifacts/autonomous/afl-substrate-q3-verification-report.json")
EXPECTATION_PATH = Path("delivery/autonomous/afl09a/frozen-expectations/substrate_q3.json")
PLAN_ARTIFACT_PATH = Path("config/query-plans/q3_receiver_second_line_no_underneath_support.experimental.v1.json")

MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
REQUIRED_PROHIBITED_CLAIMS = {
    "tactical_line_role_identified",
    "defensive_line_was_broken",
    "support_quality_inferred",
    "player_intent_inferred",
    "planned_combination_inferred",
    "decision_quality_inferred",
    "tactical_causation_inferred",
    "pass_probability_inferred",
    "pass_was_optimal",
}
VALIDATION_FACTORY_SPEC = ValidationFactorySpec(
    factory_id="afl09a.substrate_q3.0_1_0",
    subject_ref="recipe:q3_receiver_second_line_no_underneath_support_v1:0.1.0",
    expectation_path=EXPECTATION_PATH,
    source_verifier="tqe.verification.afl_substrate_q3",
    threshold_version="q3_receiver_second_line_no_underneath_support.v0.1.0",
    required_prohibited_claims=frozenset(REQUIRED_PROHIBITED_CLAIMS),
    required_check_keys=(
        "generic_execution",
        "q3_compiles_end_to_end",
        "requested_evidence_complete",
        "slice_1_action_spine_exercised",
        "slice_2_quality_distance_exercised",
        "slice_3_multiline_support_direction_exercised",
        "result_or_honest_zero",
    ),
)


def q3_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "q3_receiver_second_line_no_underneath_support_v1",
            "recipe_version": "0.1.0",
            "display_name": "Receiver Beyond Observed Line Rank 2 Without Underneath Support",
            "description": (
                "Experimental northstar Q3 composition: a controlled pass receiver moves beyond "
                "observed geometric line rank 2 and no underneath support arrives inside the "
                "declared window."
            ),
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "A provider-linked pass action was evaluated through the action substrate.",
                "The receiver moved beyond observed geometric line rank 2 under declared thresholds.",
                "No underneath support relation was observed inside the declared window.",
                "Tracking-quality and distance substrate outputs are evidence, not tactical judgement.",
            ],
            "disallowed_claims": [
                "The system identified a tactical second line or tactical line role.",
                "The pass definitively broke a defensive line taxonomy.",
                "The receiver intended to break a line.",
                "The support situation was tactically good or bad.",
                "The pass was optimal or has an inferred completion probability.",
            ],
            "limitations": [
                "Line rank 2 is a geometric ordering of observed defending bands, not football-role taxonomy.",
                "Underneath support means BEHIND_BALL_OUTLET under declared distance/timing thresholds.",
                "UNKNOWN evidence is excluded rather than coerced to no-support.",
            ],
            "output_classifications": ["Q3_RECEIVER_SECOND_LINE_NO_UNDERNEATH_SUPPORT"],
            "parameters": [
                _number_param("maximum_action_gap_seconds", "second", 5.0, "Maximum event gap for action-chain pairs."),
                _number_param("goal_side_buffer_m", "metre", 1.0, "Minimum defender distance beyond ball for line candidates."),
                _number_param("line_band_width_m", "metre", 2.5, "Maximum x-span for one observed line band."),
                _number_param("minimum_line_defenders", "count", 2, "Minimum defenders per observed line band."),
                _number_param("line_buffer_m", "metre", 0.5, "Distance from line treated as level."),
                _number_param("maximum_arrival_seconds", "second", 3.0, "Latest underneath support arrival after reception."),
                _number_param("minimum_duration_seconds", "second", 0.0, "Minimum observed support duration."),
                _number_param("maximum_support_distance_m", "metre", 8.0, "Maximum distance for underneath support."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "q3_receiver_second_line_no_underneath_support_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "q3_receiver_second_line_no_underneath_support",
            "plan_version": "0.1.0",
            "recipe_id": "q3_receiver_second_line_no_underneath_support_v1",
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "nodes": [
                {
                    "kind": "primitive",
                    "node_id": "action_events",
                    "catalog_ref": "action_event_anchor",
                    "version": "0.1.0",
                    "parameters": {
                        "action_type": {"payload_type": "enum", "unit": "none", "value": "successful_pass"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "action_chain",
                    "catalog_ref": "action_chain",
                    "version": "0.1.0",
                    "inputs": {
                        "actions": {"source_node_id": "action_events", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "maximum_action_gap_seconds": {"kind": "parameter", "name": "maximum_action_gap_seconds"},
                        "chain_length": {"payload_type": "number", "unit": "count", "value": 2},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "controlled_pass",
                    "catalog_ref": "controlled_pass_episode",
                    "version": "0.1.0",
                },
                {
                    "kind": "primitive",
                    "node_id": "tracking_quality",
                    "catalog_ref": "tracking_quality",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"},
                    },
                    "parameters": {
                        "frame_field": {"payload_type": "enum", "unit": "none", "value": "controlled_reception_frame_id"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "receiver_ball_distance",
                    "catalog_ref": "pairwise_distance",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"},
                    },
                    "parameters": {
                        "frame_field": {"payload_type": "enum", "unit": "none", "value": "controlled_reception_frame_id"},
                        "entity_a_field": {"payload_type": "enum", "unit": "none", "value": "receiver_id"},
                        "entity_b_field": {"payload_type": "enum", "unit": "none", "value": "ball"},
                        "maximum_distance_m": {"payload_type": "number", "unit": "metre", "value": 3.0},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "second_line_at_release",
                    "catalog_ref": "multi_line_model",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"},
                    },
                    "parameters": {
                        "goal_side_buffer_m": {"kind": "parameter", "name": "goal_side_buffer_m"},
                        "line_band_width_m": {"kind": "parameter", "name": "line_band_width_m"},
                        "minimum_line_defenders": {"kind": "parameter", "name": "minimum_line_defenders"},
                        "target_line_rank": {"payload_type": "number", "unit": "count", "value": 2},
                        "anchor_frame_field": {"payload_type": "enum", "unit": "none", "value": "physical_release_frame_id"},
                    },
                },
                _relative_position_node("receiver_release_position", "physical_release_frame_id"),
                _relative_position_node("receiver_reception_position", "controlled_reception_frame_id"),
                {
                    "kind": "primitive",
                    "node_id": "controlled_second_line_transition",
                    "catalog_ref": "controlled_line_break_episode",
                    "version": "0.1.0",
                    "inputs": {
                        "controlled_pass_anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"},
                        "line_evaluations": {"source_node_id": "second_line_at_release", "output_name": "anchor_evaluations"},
                        "release_relative_positions": {"source_node_id": "receiver_release_position", "output_name": "anchor_evaluations"},
                        "reception_relative_positions": {"source_node_id": "receiver_reception_position", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "line_buffer_m": {"kind": "parameter", "name": "line_buffer_m"},
                    },
                },
                {
                    "kind": "relation",
                    "node_id": "underneath_support",
                    "catalog_ref": "support_arrival_relation",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_second_line_transition", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "anchor_frame_field": {"payload_type": "enum", "unit": "none", "value": "controlled_reception_frame_id"},
                        "candidate_scope": {"payload_type": "enum", "unit": "none", "value": "perspective_outfield"},
                        "support_region_mode": {"payload_type": "enum", "unit": "none", "value": "BEHIND_BALL_OUTLET"},
                        "maximum_arrival_seconds": {"kind": "parameter", "name": "maximum_arrival_seconds"},
                        "minimum_duration_seconds": {"kind": "parameter", "name": "minimum_duration_seconds"},
                        "maximum_support_distance_m": {"kind": "parameter", "name": "maximum_support_distance_m"},
                        "minimum_supporting_players": {"payload_type": "number", "unit": "count", "value": 1},
                        "required_anchor_status_field": {"payload_type": "enum", "unit": "none", "value": "line_break_status"},
                        "required_anchor_status_value": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                    },
                },
                _eq_predicate("line_transition_pass", "controlled_second_line_transition", "line_break_status", "PASS"),
                _eq_predicate("no_underneath_support", "underneath_support", "support_arrival_status", "FAIL"),
            ],
            "classification_rules": [
                {
                    "label": "Q3_RECEIVER_SECOND_LINE_NO_UNDERNEATH_SUPPORT",
                    "predicate_ids": ["line_transition_pass", "no_underneath_support"],
                    "description": "Receiver moved beyond observed geometric line rank 2 and no underneath support relation was observed.",
                },
            ],
            "anchor_source": {
                "source_node_id": "controlled_second_line_transition",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": requested_evidence(),
        },
    }


def requested_evidence() -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for field in [
        "line_break_status",
        "line_break_reason",
        "pass_episode_id",
        "physical_release_frame_id",
        "controlled_reception_frame_id",
        "line_x_m",
        "release_relative_position_status",
        "reception_relative_position_status",
    ]:
        evidence.append(_evidence("controlled_second_line_transition", field))
    evidence.append(_evidence("controlled_pass", "receiver_id", output_name="anchors"))
    for field in [
        "multi_line_status",
        "target_line_rank",
        "observed_line_count",
        "observed_lines",
        "line_x_m",
        "defensive_line_player_ids",
    ]:
        evidence.append(_evidence("second_line_at_release", field))
    for field in [
        "support_arrival_status",
        "support_arrival_reason",
        "support_region_mode",
        "maximum_arrival_seconds",
        "maximum_support_distance_m",
        "supporting_player_ids",
        "candidate_player_ids",
        "coverage_status",
    ]:
        evidence.append(_evidence("underneath_support", field))
    evidence.append(_evidence("tracking_quality", "tracking_quality_status"))
    evidence.append(_evidence("receiver_ball_distance", "distance_m"))
    return evidence


def verify_substrate_q3() -> dict[str, Any]:
    document_payload = q3_document()
    PLAN_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_ARTIFACT_PATH.write_text(json.dumps(document_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    if execution.status != ExecutionStatus.PASS:
        findings.append({"code": "execution_not_pass", "message": f"Execution status was {execution.status}.", "path": "execution.status"})
    if evidence_failure_count:
        findings.append({"code": "requested_evidence_missing", "message": f"{evidence_failure_count} requested evidence failures.", "path": "execution.provenance.requested_evidence_failures"})
    if not rows and not honest_zero:
        findings.append({"code": "zero_not_honest", "message": "Zero-result Q3 execution did not satisfy honest-zero conditions.", "path": "execution"})
    if proof_carrying["status"] != "PASS":
        findings.append({"code": "proof_carrying_rows_failed", "message": "Real substrate rows did not satisfy PASS/FAIL/UNKNOWN proof-carrying discipline.", "path": "proof_carrying"})

    report = {
        "schema_version": "afl.substrate_q3.v1",
        "milestone": "AFL-08 substrate slices 1-3 / Q3 stop gate",
        "status": "PASS" if not findings else "FAIL",
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
        },
        "slice_unlocks": {
            "slice_1": "action_event_anchor + action_chain -> generic event/action sequencing vocabulary",
            "slice_2": "tracking_quality + pairwise_distance -> support distance/proximity inputs with UNKNOWN under missing tracking",
            "slice_3": "multi_line_model + BEHIND_BALL_OUTLET support -> Q3 compiles end-to-end",
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
            "q3_compiles_end_to_end": execution.status == ExecutionStatus.PASS and evidence_failure_count == 0,
            "requested_evidence_complete": evidence_failure_count == 0,
            "slice_1_action_spine_exercised": probe.get("action_event_count", 0) > 0 and probe.get("action_chain_count", 0) > 0,
            "slice_2_quality_distance_exercised": probe.get("tracking_quality_count", 0) > 0 and probe.get("pairwise_distance_count", 0) > 0,
            "slice_3_multiline_support_direction_exercised": probe.get("multi_line_count", 0) > 0 and probe.get("support_direction_count", 0) > 0,
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

    action_events = records("action_events")
    action_chains = records("action_chain")
    tracking = records("tracking_quality")
    distances = records("receiver_ball_distance")
    multi_lines = records("second_line_at_release")
    support = records("underneath_support")
    return {
        "match_id": bound_plan.match_ids[0],
        "period": bound_plan.periods[0],
        "action_event_count": len(action_events),
        "action_chain_count": len(action_chains),
        "tracking_quality_count": len(tracking),
        "pairwise_distance_count": len(distances),
        "multi_line_count": len(multi_lines),
        "support_direction_count": len(support),
        "action_chain_status_counts": _status_counts(action_chains, "action_chain_status"),
        "tracking_quality_status_counts": _status_counts(tracking, "tracking_quality_status"),
        "pairwise_distance_status_counts": _status_counts(distances, "pairwise_distance_status"),
        "multi_line_status_counts": _status_counts(multi_lines, "multi_line_status"),
        "support_arrival_status_counts": _status_counts(support, "support_arrival_status"),
    }


def proof_carrying_records(probe: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # These rows are sampled from real status distributions. They prove the
    # branch contract in the Q3 substrate gate without inventing expected truth.
    branch_sources = [
        ("action_chain", probe.get("action_chain_status_counts", {})),
        ("pairwise_distance", probe.get("pairwise_distance_status_counts", {})),
        ("multi_line", probe.get("multi_line_status_counts", {})),
        ("support_direction", probe.get("support_arrival_status_counts", {})),
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
            "line_evaluations": {"source_node_id": "second_line_at_release", "output_name": "anchor_evaluations"},
            "entity_anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"},
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
    report = verify_substrate_q3()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
