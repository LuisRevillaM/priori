"""AFL-08 substrate slices 7-8 and Q4 partial compile verifier.

Q4 asks for defensive possessions where the block is compact, then loses lane
coverage after a switch. In v0.1 this deliberately compiles only the executable
prefix:

- a controlled pass is evaluated as an observed switch of play;
- defending outfield team compactness is measured at release and reception;
- width change is evaluated across the switch anchor.

The true lane-coverage / lane-denial clause is not fabricated. It returns a
typed semantic gap on `time_to_arrival`, because reachability is required before
coverage can be claimed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows, runtime_parameters
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_compiler.gaps import missing_operationalization_gap_expression
from tqe.semantic_compiler.lowering import compile_semantic_expression
from tqe.semantic_compiler.models import CompilerOutcome, SemanticExpression
from tqe.verification.afl_validation_factory import (
    ValidationFactorySpec,
    attach_validation_factory,
    validate_proof_carrying_records,
)
from tqe.write_mode import emit_tracked_artifact


REPORT_PATH = Path("artifacts/autonomous/afl-substrate-q4-verification-report.json")
EXPECTATION_PATH = Path("delivery/autonomous/afl09a/frozen-expectations/substrate_q4.json")
PLAN_ARTIFACT_PATH = Path("config/query-plans/q4_compact_then_switch_partial.experimental.v1.json")

MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
REQUIRED_PROHIBITED_CLAIMS = {
    "lane_coverage_proven",
    "time_to_arrival_inferred",
    "pitch_control_inferred",
    "tactical_line_role_identified",
    "restart_routine_identified",
    "player_intent_inferred",
    "defender_intent_inferred",
    "decision_quality_inferred",
    "tactical_causation_inferred",
    "pass_probability_inferred",
    "pass_was_optimal",
}

VALIDATION_FACTORY_SPEC = ValidationFactorySpec(
    factory_id="afl09a.substrate_q4.0_1_0",
    subject_ref="recipe:q4_compact_then_switch_partial_v1:0.1.0",
    expectation_path=EXPECTATION_PATH,
    source_verifier="tqe.verification.afl_substrate_q4",
    threshold_version="q4_compact_then_switch_partial.v0.1.0",
    required_prohibited_claims=frozenset(REQUIRED_PROHIBITED_CLAIMS),
    required_check_keys=(
        "generic_execution",
        "q4_partial_compiles_end_to_end",
        "requested_evidence_complete",
        "switch_clause_exercised",
        "compactness_change_clause_exercised",
        "typed_lane_coverage_gap_returned",
        "coverage_clause_not_fabricated",
        "result_or_honest_zero",
    ),
)


def q4_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "q4_compact_then_switch_partial_v1",
            "recipe_version": "0.1.0",
            "display_name": "Compact Block Then Switch Partial",
            "description": (
                "Experimental northstar Q4 partial composition: a controlled pass is observed as a switch of play, "
                "the defending outfield unit is compact at release, and defending-team width increases after reception. "
                "True lane coverage is intentionally returned as a typed time_to_arrival gap."
            ),
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "A controlled pass moved the ball from one lateral side to the opposite side under declared thresholds.",
                "Defending outfield width/depth was measured from observed tracking positions.",
                "Observed defending-team width increased across the switch anchor under declared thresholds.",
            ],
            "disallowed_claims": [
                "The system proved lane coverage or lane denial.",
                "The system inferred time-to-arrival, pitch control, player intent, or tactical causation.",
                "The switch was tactically optimal or caused the defensive change.",
            ],
            "limitations": [
                "Compactness is an observed outfield bounding-box measurement, not tactical quality.",
                "Switch of play is observed endpoint lateral movement, not a designed-switch claim.",
                "Lane coverage requires time_to_arrival and returns a typed gap in this slice.",
            ],
            "output_classifications": ["Q4_COMPACT_THEN_SWITCH_PARTIAL"],
            "parameters": [
                _number_param("switch_minimum_lateral_displacement_m", "metre", 25.0, "Minimum lateral ball displacement for switch status."),
                _number_param("switch_minimum_start_lateral_m", "metre", 10.0, "Minimum absolute release lateral position."),
                _number_param("switch_minimum_end_lateral_m", "metre", 10.0, "Minimum absolute reception lateral position."),
                _number_param("switch_maximum_duration_seconds", "second", 8.0, "Maximum release-to-reception duration."),
                _number_param("compact_maximum_team_width_m", "metre", 48.0, "Maximum defending-team width for compact before status."),
                _number_param("compact_maximum_team_depth_m", "metre", 42.0, "Maximum defending-team depth for compact before status."),
                _number_param("compact_minimum_observed_players", "count", 8, "Minimum observed defending outfield players."),
                _number_param("minimum_width_increase_m", "metre", 6.0, "Minimum defending-team width increase after switch."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "q4_compact_then_switch_partial_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "q4_compact_then_switch_partial",
            "plan_version": "0.1.0",
            "recipe_id": "q4_compact_then_switch_partial_v1",
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "nodes": [
                {
                    "kind": "primitive",
                    "node_id": "controlled_pass",
                    "catalog_ref": "controlled_pass_episode",
                    "version": "0.1.0",
                },
                {
                    "kind": "primitive",
                    "node_id": "switch_of_play",
                    "catalog_ref": "switch_of_play",
                    "version": "0.1.0",
                    "inputs": {"anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"}},
                    "parameters": {
                        "minimum_lateral_displacement_m": {"kind": "parameter", "name": "switch_minimum_lateral_displacement_m"},
                        "minimum_start_lateral_m": {"kind": "parameter", "name": "switch_minimum_start_lateral_m"},
                        "minimum_end_lateral_m": {"kind": "parameter", "name": "switch_minimum_end_lateral_m"},
                        "maximum_duration_seconds": {"kind": "parameter", "name": "switch_maximum_duration_seconds"},
                    },
                },
                _team_compactness_node("before_compactness", "physical_release_frame_id"),
                _team_compactness_node("after_compactness", "controlled_reception_frame_id"),
                {
                    "kind": "primitive",
                    "node_id": "width_change_after_switch",
                    "catalog_ref": "change_across_anchor",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "switch_of_play", "output_name": "anchor_evaluations"},
                        "before_evaluations": {"source_node_id": "before_compactness", "output_name": "anchor_evaluations"},
                        "after_evaluations": {"source_node_id": "after_compactness", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "before_value_field": {"payload_type": "enum", "unit": "none", "value": "team_width_m"},
                        "after_value_field": {"payload_type": "enum", "unit": "none", "value": "team_width_m"},
                        "before_status_field": {"payload_type": "enum", "unit": "none", "value": "team_compactness_status"},
                        "after_status_field": {"payload_type": "enum", "unit": "none", "value": "none"},
                        "required_status_value": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                        "change_mode": {"payload_type": "enum", "unit": "none", "value": "increase_at_least"},
                        "minimum_change_m": {"kind": "parameter", "name": "minimum_width_increase_m"},
                        "maximum_before_value_m": {"kind": "parameter", "name": "compact_maximum_team_width_m"},
                    },
                },
                _eq_predicate("switch_pass", "switch_of_play", "switch_status", "PASS"),
                _eq_predicate("width_change_pass", "width_change_after_switch", "change_status", "PASS"),
            ],
            "classification_rules": [
                {
                    "label": "Q4_COMPACT_THEN_SWITCH_PARTIAL",
                    "predicate_ids": ["switch_pass", "width_change_pass"],
                    "description": "Observed compact defending width before a switch, with observed defending width increase afterward. Lane coverage is a typed gap.",
                }
            ],
            "anchor_source": {
                "source_node_id": "width_change_after_switch",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": requested_evidence(),
        },
    }


def lane_coverage_gap_expression() -> SemanticExpression:
    return missing_operationalization_gap_expression(
        expression_id="q4_lane_coverage_time_to_arrival_gap",
        expression_version="0.1.0",
        display_name="Q4 Lane Coverage Gap",
        query_text="Defensive block compact, then loses lane coverage after a switch.",
        description="Executable compact-then-switch prefix exists, but true lane coverage requires time-to-arrival.",
        normal_form={
            "scope": {"summary": "Selected matches and periods.", "semantic_refs": [], "runtime_refs": []},
            "anchor": {"summary": "Observed switch of play from a controlled pass.", "semantic_refs": ["concept.observed_switch_of_play"], "runtime_refs": ["switch_of_play"]},
            "bind": {"summary": "Defending outfield unit at release and reception.", "semantic_refs": ["concept.observed_team_compactness"], "runtime_refs": ["team_compactness"]},
            "measure": {"summary": "Width/depth compactness and width change; lane coverage deferred.", "semantic_refs": ["concept.observed_change_across_anchor"], "runtime_refs": ["change_across_anchor"]},
            "match": {"summary": "Compact before switch and wider after switch.", "semantic_refs": [], "runtime_refs": []},
            "outcome": {"summary": "Lane-coverage loss requires reachability.", "semantic_refs": ["time_to_arrival"], "runtime_refs": []},
            "judge": {"summary": "Return typed gap rather than infer coverage.", "semantic_refs": [], "runtime_refs": []},
            "return": {"summary": "Partial executable prefix and blocking semantic gap.", "semantic_refs": [], "runtime_refs": []},
        },
        blocking_concept="time_to_arrival",
        blocked_slot="outcome",
        expected_input=[
            {
                "name": "defender_trajectories",
                "semantic_type": {"container": "episode_set", "value": "PlayerTrajectory", "unit": "none", "cardinality": "collection", "entity_scope": "defending"},
                "description": "Observed defender trajectories around the lane-coverage window.",
            },
            {
                "name": "lane_region",
                "semantic_type": {"container": "region", "value": "LaneRegion", "unit": "none", "cardinality": "single", "entity_scope": "region"},
                "description": "The lane or pass corridor whose defensive reachability is being tested.",
            },
        ],
        expected_output={"container": "frame_signal", "value": "ReachabilityMargin", "unit": "second", "cardinality": "single", "entity_scope": "anchor"},
        semantic_basis="lane_coverage_requires_reachability_not_occupancy",
        required_modalities=["tracking"],
        claim_boundary="Without time_to_arrival, Priori can report observed compactness/change but cannot claim lane coverage or lane denial.",
        evidence_obligations=["defender_position_time_series", "lane_region", "arrival_time_threshold", "tracking_quality_policy"],
        executable_prefix_exists=True,
        message="Q4 lane coverage is blocked on a time_to_arrival operationalization.",
        concept_refs=["concept.observed_switch_of_play", "concept.observed_team_compactness", "time_to_arrival"],
        operator_refs=["change_across_anchor"],
    )


def requested_evidence() -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for field in [
        "pass_episode_id",
        "passer_id",
        "receiver_id",
        "physical_release_frame_id",
        "controlled_reception_frame_id",
        "forward_progression_m",
    ]:
        evidence.append(_evidence("controlled_pass", field, output_name="anchors"))
    for field in [
        "switch_status",
        "switch_reason",
        "release_lateral_side",
        "reception_lateral_side",
        "lateral_displacement_m",
        "switch_duration_seconds",
    ]:
        evidence.append(_evidence("switch_of_play", field))
    for field in [
        "team_compactness_status",
        "team_width_m",
        "team_depth_m",
        "observed_player_count",
    ]:
        evidence.append(_evidence("before_compactness", field, alias=f"before_{field}"))
    for field in [
        "team_width_m",
        "team_depth_m",
        "observed_player_count",
    ]:
        evidence.append(_evidence("after_compactness", field, alias=f"after_{field}"))
    for field in [
        "change_status",
        "change_reason",
        "before_value",
        "after_value",
        "delta_value",
        "minimum_change_m",
        "maximum_before_value_m",
    ]:
        evidence.append(_evidence("width_change_after_switch", field))
    return evidence


def verify_substrate_q4() -> dict[str, Any]:
    document_payload = q4_document()
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
    gap_result = compile_semantic_expression(lane_coverage_gap_expression())
    evidence_failure_count = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    honest_zero = (
        not rows
        and execution.status == ExecutionStatus.PASS
        and execution.provenance.get("compatibility_profile") == "generic"
        and evidence_failure_count == 0
    )
    proof_carrying = validate_proof_carrying_records(proof_carrying_records(probe))
    typed_gap_ok = (
        gap_result.outcome == CompilerOutcome.CAPABILITY_GAP
        and gap_result.blocking_gap is not None
        and gap_result.blocking_gap.kind.value == "MISSING_OPERATIONALIZATION"
        and gap_result.blocking_gap.concept == "time_to_arrival"
        and gap_result.blocking_gap.executable_prefix_exists is True
    )
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
        findings.append({"code": "zero_not_honest", "message": "Zero-result Q4 partial execution did not satisfy honest-zero conditions.", "path": "execution"})
    if proof_carrying["status"] != "PASS":
        findings.append({"code": "proof_carrying_rows_failed", "message": "Real substrate rows did not satisfy PASS/FAIL/UNKNOWN proof-carrying discipline.", "path": "proof_carrying"})
    if not typed_gap_ok:
        findings.append({"code": "typed_gap_missing", "message": "Lane coverage did not return the expected time_to_arrival typed gap.", "path": "semantic_gap"})

    report = {
        "schema_version": "afl.substrate_q4.v1",
        "milestone": "AFL-08 substrate slices 7-8 / Q4 typed-gap stop gate",
        "status": "PASS" if not findings else "FAIL",
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
        },
        "slice_unlocks": {
            "slice_7": "change_across_anchor + switch_of_play -> compact-then-switch executable prefix",
            "slice_8_partial": "lane coverage returns typed time_to_arrival gap instead of fabricated coverage",
            "q4": "Defensive block compact, then lane coverage after switch is blocked on reachability substrate",
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
        "semantic_gap": gap_result.model_dump(mode="json", exclude={"runtime_document"}, exclude_none=True),
        "probe": probe,
        "proof_carrying_real_rows": proof_carrying,
        "claim_boundary": {
            "dependency_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "required_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "enforced_in_report": True,
        },
        "checks": {
            "generic_execution": execution.provenance.get("compatibility_profile") == "generic",
            "q4_partial_compiles_end_to_end": execution.status == ExecutionStatus.PASS and evidence_failure_count == 0,
            "requested_evidence_complete": evidence_failure_count == 0,
            "switch_clause_exercised": probe.get("switch_count", 0) > 0,
            "compactness_change_clause_exercised": probe.get("before_compactness_count", 0) > 0 and probe.get("change_count", 0) > 0,
            "typed_lane_coverage_gap_returned": typed_gap_ok,
            "coverage_clause_not_fabricated": gap_result.runtime_document is None and gap_result.runtime_recipe_id is None,
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

    switch = records("switch_of_play")
    before = records("before_compactness")
    after = records("after_compactness")
    change = records("width_change_after_switch")
    return {
        "match_id": bound_plan.match_ids[0],
        "period": bound_plan.periods[0],
        "switch_count": len(switch),
        "before_compactness_count": len(before),
        "after_compactness_count": len(after),
        "change_count": len(change),
        "switch_status_counts": _status_counts(switch, "switch_status"),
        "before_compactness_status_counts": _status_counts(before, "team_compactness_status"),
        "after_compactness_status_counts": _status_counts(after, "team_compactness_status"),
        "change_status_counts": _status_counts(change, "change_status"),
    }


def proof_carrying_records(probe: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    branch_sources = [
        ("switch", probe.get("switch_status_counts", {})),
        ("before_compactness", probe.get("before_compactness_status_counts", {})),
        ("after_compactness", probe.get("after_compactness_status_counts", {})),
        ("change", probe.get("change_status_counts", {})),
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


def _team_compactness_node(node_id: str, frame_field: str) -> dict[str, Any]:
    return {
        "kind": "primitive",
        "node_id": node_id,
        "catalog_ref": "team_compactness",
        "version": "0.1.0",
        "inputs": {"anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"}},
        "parameters": {
            "frame_field": {"payload_type": "enum", "unit": "none", "value": frame_field},
            "player_scope": {"payload_type": "enum", "unit": "none", "value": "defending_outfield"},
            "maximum_team_width_m": {"kind": "parameter", "name": "compact_maximum_team_width_m"},
            "maximum_team_depth_m": {"kind": "parameter", "name": "compact_maximum_team_depth_m"},
            "minimum_observed_players": {"kind": "parameter", "name": "compact_minimum_observed_players"},
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


def _evidence(
    source_node_id: str,
    field: str,
    *,
    output_name: str = "anchor_evaluations",
    alias: str | None = None,
) -> dict[str, Any]:
    return {
        "alias": alias or field,
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
    report = verify_substrate_q4()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
