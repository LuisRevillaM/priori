"""AFL-08 substrate slice 8 and Q5 compile verifier.

Q5 asks for regains that become settled possession. In v0.1 this compiles a
literal, evidence-backed subset:

- an observed possession-role transition from defending to the perspective team;
- ball location in the perspective team's own half at that transition;
- possession retained for a declared settled-duration threshold inside a
  declared outcome window.

It does not infer transition phase quality, tactical intent, counterattack
quality, or whether the possession was settled in a coaching/tactical sense.
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


REPORT_PATH = Path("artifacts/autonomous/afl-substrate-q5-verification-report.json")
EXPECTATION_PATH = Path("delivery/autonomous/afl09a/frozen-expectations/substrate_q5.json")
PLAN_ARTIFACT_PATH = Path("config/query-plans/q5_own_half_regain_settled.experimental.v1.json")

MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
REQUIRED_PROHIBITED_CLAIMS = {
    "settled_quality_inferred",
    "transition_intent_inferred",
    "counterattack_quality_inferred",
    "tactical_causation_inferred",
    "player_intent_inferred",
    "decision_quality_inferred",
    "optimality_inferred",
    "role_taxonomy_inferred",
    "pressure_inferred",
}

VALIDATION_FACTORY_SPEC = ValidationFactorySpec(
    factory_id="afl09a.substrate_q5.0_1_0",
    subject_ref="recipe:q5_own_half_regain_settled_v1:0.1.0",
    expectation_path=EXPECTATION_PATH,
    source_verifier="tqe.verification.afl_substrate_q5",
    threshold_version="q5_own_half_regain_settled.v0.1.0",
    required_prohibited_claims=frozenset(REQUIRED_PROHIBITED_CLAIMS),
    required_check_keys=(
        "generic_execution",
        "q5_compiles_end_to_end",
        "requested_evidence_complete",
        "transition_anchor_clause_exercised",
        "structured_zone_clause_exercised",
        "outcome_window_clause_exercised",
        "alignment_metadata_declared",
        "result_or_honest_zero",
    ),
)


def q5_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "q5_own_half_regain_settled_v1",
            "recipe_version": "0.1.0",
            "display_name": "Own-Half Regain Into Settled Possession",
            "description": (
                "Experimental northstar Q5 composition: an observed regain transition occurs with the ball "
                "in the perspective team's own half, then possession is retained for a declared settled-duration "
                "threshold inside a declared outcome window. Alignment: structured-zone evaluation uses the "
                "transition_frame_id from the transition anchor; outcome-window evaluation starts at that same "
                "anchor_frame_id and preserves the same team perspective."
            ),
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "A possession-role transition from defending to the perspective team was observed.",
                "The ball was in the perspective team's own half at the transition frame under a declared buffer.",
                "The perspective team retained ball-alive possession for the declared duration inside the declared outcome window.",
            ],
            "disallowed_claims": [
                "The system inferred transition intent, counterattack quality, decision quality, or tactical causation.",
                "The system inferred coaching-quality settled possession beyond the frozen duration threshold.",
                "The system inferred pressure, role taxonomy, optimality, or player intent.",
            ],
            "limitations": [
                "Transition is derived from the canonical possession-role stream, not from tactical phase labeling.",
                "Own-half is a coarse attacking-direction-normalized zone, not a full pitch-control or territory model.",
                "Settled possession means retained ball-alive possession for the declared duration, not possession quality.",
                "UNKNOWN evidence is excluded rather than treated as not settled.",
            ],
            "output_classifications": ["Q5_OWN_HALF_REGAIN_SETTLED_WITHIN_WINDOW"],
            "parameters": [
                _number_param("minimum_prior_possession_seconds", "second", 0.4, "Minimum prior opponent-possession continuity before the regain."),
                _number_param("zone_boundary_buffer_m", "metre", 0.5, "Boundary buffer for own-half zone uncertainty."),
                _number_param("maximum_window_seconds", "second", 8.0, "Maximum window after the regain transition."),
                _number_param("minimum_settled_possession_seconds", "second", 4.0, "Required retained-possession duration inside the window."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "q5_own_half_regain_settled_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "q5_own_half_regain_settled",
            "plan_version": "0.1.0",
            "recipe_id": "q5_own_half_regain_settled_v1",
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "nodes": [
                {
                    "kind": "primitive",
                    "node_id": "regain_transition",
                    "catalog_ref": "transition_anchor",
                    "version": "0.1.0",
                    "parameters": {
                        "transition_type": {"payload_type": "enum", "unit": "none", "value": "regain"},
                        "minimum_prior_possession_seconds": {"kind": "parameter", "name": "minimum_prior_possession_seconds"},
                        "zone_filter": {"payload_type": "enum", "unit": "none", "value": "any"},
                        "zone_boundary_buffer_m": {"kind": "parameter", "name": "zone_boundary_buffer_m"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "own_half_zone",
                    "catalog_ref": "structured_zone",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "regain_transition", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "frame_field": {"payload_type": "enum", "unit": "none", "value": "transition_frame_id"},
                        "zone_name": {"payload_type": "enum", "unit": "none", "value": "own_half"},
                        "zone_boundary_buffer_m": {"kind": "parameter", "name": "zone_boundary_buffer_m"},
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "settled_outcome_window",
                    "catalog_ref": "outcome_window",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "own_half_zone", "output_name": "anchor_evaluations"},
                    },
                    "parameters": {
                        "maximum_window_seconds": {"kind": "parameter", "name": "maximum_window_seconds"},
                        "minimum_settled_possession_seconds": {"kind": "parameter", "name": "minimum_settled_possession_seconds"},
                        "required_anchor_status_field": {"payload_type": "enum", "unit": "none", "value": "zone_status"},
                        "required_anchor_status_value": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                    },
                },
                _eq_predicate("transition_pass", "regain_transition", "transition_status", "PASS"),
                _eq_predicate("zone_pass", "own_half_zone", "zone_status", "PASS"),
                _eq_predicate("settled_pass", "settled_outcome_window", "outcome_window_status", "PASS"),
            ],
            "classification_rules": [
                {
                    "label": "Q5_OWN_HALF_REGAIN_SETTLED_WITHIN_WINDOW",
                    "predicate_ids": ["transition_pass", "zone_pass", "settled_pass"],
                    "description": "Observed own-half regain followed by retained ball-alive possession inside the declared window.",
                }
            ],
            "anchor_source": {
                "source_node_id": "settled_outcome_window",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": requested_evidence(),
        },
    }


def q5_alignment_annotations() -> dict[str, str]:
    return {
        "same_anchor_identity": "own_half_zone preserves regain_transition.anchor_id; settled_outcome_window evaluates the same anchor.",
        "same_team_perspective": "transition, zone, and outcome evaluate the invocation perspective_team_role.",
        "zone_frame_alignment": "own_half_zone.frame_field is transition_frame_id from regain_transition.",
        "outcome_window_alignment": "settled_outcome_window starts at the shared anchor_frame_id and never claims prior/future causation.",
        "unknown_policy": "UNKNOWN zone/outcome evidence is excluded, never coerced to no-settle.",
    }


def requested_evidence() -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for field in [
        "transition_status",
        "transition_reason",
        "transition_type",
        "transition_frame_id",
        "previous_frame_id",
        "previous_team_role",
        "new_team_role",
        "prior_possession_frame_count",
        "minimum_prior_possession_seconds",
        "transition_match_time_ms",
    ]:
        evidence.append(_evidence("regain_transition", field, alias=f"transition_{field}"))
    for field in [
        "zone_status",
        "zone_reason",
        "zone_name",
        "zone_frame_id",
        "zone_ball_x_m",
        "zone_ball_y_m",
        "zone_normalized_ball_x_m",
        "zone_boundary_buffer_m",
        "attacking_direction",
    ]:
        evidence.append(_evidence("own_half_zone", field, alias=f"own_half_{field}"))
    for field in [
        "outcome_window_status",
        "outcome_window_reason",
        "possession_phase_status",
        "outcome_window_start_frame_id",
        "outcome_window_end_frame_id",
        "maximum_window_seconds",
        "minimum_settled_possession_seconds",
        "settled_start_frame_id",
        "settled_end_frame_id",
        "required_anchor_status_field",
        "required_anchor_status_value",
    ]:
        evidence.append(_evidence("settled_outcome_window", field, alias=f"settled_{field}"))
    for field in ["loss_frame_id", "stoppage_frame_id"]:
        evidence.append(_evidence("settled_outcome_window", field, alias=f"settled_{field}", required=False))
    return evidence


def verify_substrate_q5() -> dict[str, Any]:
    document_payload = q5_document()
    plan_artifact_drift = emit_tracked_artifact(
        PLAN_ARTIFACT_PATH,
        json.dumps(document_payload, indent=2, sort_keys=True) + "\n",
    )
    document = TacticalQueryDocument.model_validate(document_payload)
    bound_plan = bind_document(document)
    executor = TacticalQueryExecutor()
    execution = executor.execute(bound_plan)
    rows = execution_result_rows(execution)
    probe = probe_corpus(executor, bound_plan)
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
        findings.append({"code": "zero_not_honest", "message": "Zero-result Q5 execution did not satisfy honest-zero conditions.", "path": "execution"})
    if proof_carrying["status"] != "PASS":
        findings.append({"code": "proof_carrying_rows_failed", "message": "Real substrate rows did not satisfy PASS/FAIL/UNKNOWN proof-carrying discipline.", "path": "proof_carrying"})

    checks = {
        "generic_execution": execution.provenance.get("compatibility_profile") == "generic",
        "q5_compiles_end_to_end": execution.status == ExecutionStatus.PASS and evidence_failure_count == 0,
        "requested_evidence_complete": evidence_failure_count == 0,
        "transition_anchor_clause_exercised": probe.get("transition_count", 0) > 0,
        "structured_zone_clause_exercised": probe.get("zone_count", 0) > 0,
        "outcome_window_clause_exercised": probe.get("outcome_count", 0) > 0,
        "alignment_metadata_declared": bool(q5_alignment_annotations()),
        "result_or_honest_zero": bool(rows) or honest_zero,
    }
    report = {
        "schema_version": "afl.substrate_q5.v1",
        "milestone": "AFL-08 substrate slice 8 / Q5 transition-anchor stop gate",
        "status": "PASS" if not findings and all(checks.values()) else "FAIL",
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
        },
        "slice_unlocks": {
            "slice_8": "transition_anchor + structured_zone + outcome_window -> regain-then-settled query vocabulary",
            "q5": "Own-half regain followed by retained possession inside a frozen outcome window",
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
        "alignment_annotations": q5_alignment_annotations(),
        "probe": probe,
        "proof_carrying_real_rows": proof_carrying,
        "claim_boundary": {
            "dependency_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "required_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "enforced_in_report": True,
        },
        "checks": checks,
        "findings": findings,
    }
    for key, value in checks.items():
        if not value:
            report["findings"].append({"code": "required_check_failed", "message": f"Q5 required check failed: {key}.", "path": f"checks.{key}"})
    return attach_validation_factory(report, rows=rows, spec=VALIDATION_FACTORY_SPEC)


def probe_corpus(executor: TacticalQueryExecutor, bound_plan: Any) -> dict[str, Any]:
    params = runtime_parameters(bound_plan)
    transition_records: list[dict[str, Any]] = []
    zone_records: list[dict[str, Any]] = []
    outcome_records: list[dict[str, Any]] = []
    for match_id in bound_plan.match_ids:
        for period in bound_plan.periods:
            state = executor._execute_period(
                bound_plan=bound_plan,
                match_id=match_id,
                period=period,
                params=params,
                compatibility_profile=executor.compatibility_profile,
            )
            transition_records.extend(_records(state, "regain_transition"))
            zone_records.extend(_records(state, "own_half_zone"))
            outcome_records.extend(_records(state, "settled_outcome_window"))

    return {
        "match_count": len(bound_plan.match_ids),
        "period_count": len(bound_plan.periods),
        "transition_count": len(transition_records),
        "zone_count": len(zone_records),
        "outcome_count": len(outcome_records),
        "transition_status_counts": _status_counts(transition_records, "transition_status"),
        "zone_status_counts": _status_counts(zone_records, "zone_status"),
        "outcome_status_counts": _status_counts(outcome_records, "outcome_window_status"),
        "possession_phase_status_counts": _status_counts(outcome_records, "possession_phase_status"),
    }


def proof_carrying_records(probe: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    branch_sources = [
        ("transition", probe.get("transition_status_counts", {})),
        ("own_half_zone", probe.get("zone_status_counts", {})),
        ("outcome_window", probe.get("outcome_status_counts", {})),
    ]
    for source, counts in branch_sources:
        if int(counts.get("PASS", 0)) > 0:
            rows.append({"judgement": "PASS", "witnesses": [{"source": source, "count": int(counts["PASS"])}]})
        if int(counts.get("FAIL", 0)) > 0:
            rows.append({"judgement": "FAIL", "evaluation_domain_complete": True, "source": source, "count": int(counts["FAIL"])})
        if int(counts.get("UNKNOWN", 0)) > 0:
            rows.append({"judgement": "UNKNOWN", "unmet_premises": [f"{source}_unknown"], "source": source, "count": int(counts["UNKNOWN"])})
    return rows


def _records(state: Any, node_id: str, output_name: str = "anchor_evaluations") -> list[dict[str, Any]]:
    value = state.runtime_values[node_id][output_name]
    return [record for record in value.value if isinstance(record, dict)]


def _status_counts(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(field))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


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
    required: bool = True,
) -> dict[str, Any]:
    return {
        "alias": alias or field,
        "source": {"source_node_id": source_node_id, "output_name": output_name},
        "field": field,
        "required": required,
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
    report = verify_substrate_q5()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
