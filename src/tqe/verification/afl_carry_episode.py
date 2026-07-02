"""AFL-08 carry_episode substrate verifier.

This slice adds a conservative movement-under-control primitive. A carry is
only claimed when a player receives a controlled pass, remains in clear control
under declared tracking thresholds, and next releases a confirmed same-player
pass. It does not claim dribbling skill, pressure breaking, defender bypassing,
intent, or decision quality.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows, runtime_parameters
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import generate_scp0_artifacts
from tqe.write_mode import emit_tracked_artifact, write_mode
from tqe.verification.afl_substrate_q4 import _eq_predicate, _evidence, _number_param, _status_counts
from tqe.verification.afl_validation_factory import (
    ValidationFactorySpec,
    attach_validation_factory,
    validate_proof_carrying_records,
)


REPORT_PATH = Path("artifacts/autonomous/afl-carry-episode-verification-report.json")
EXPECTATION_PATH = Path("delivery/autonomous/afl09a/frozen-expectations/carry_episode.json")
PLAN_ARTIFACT_PATH = Path("config/query-plans/carry_episode.experimental.v1.json")

MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
REQUIRED_PROHIBITED_CLAIMS = {
    "dribbling_skill_inferred",
    "pressure_break_quality_inferred",
    "defender_bypassed_by_carry",
    "player_intent_inferred",
    "tactical_causation_inferred",
    "decision_quality_inferred",
    "optimality_inferred",
    "pass_probability_inferred",
    "pass_was_optimal",
}

VALIDATION_FACTORY_SPEC = ValidationFactorySpec(
    factory_id="afl09a.carry_episode.0_1_0",
    subject_ref="runtime:primitive:carry_episode:0.1.0",
    expectation_path=EXPECTATION_PATH,
    source_verifier="tqe.verification.afl_carry_episode",
    threshold_version=(
        "carry_episode.v0.1.0:min_displacement=3.0:max_seconds=10.0:"
        "control_distance=2.5:nearest_margin=1.0:max_speed_delta=10.0:"
        "min_controlled_ratio=1.0:min_comoving_ratio=0.75:max_missing_ratio=0.02"
    ),
    required_prohibited_claims=frozenset(REQUIRED_PROHIBITED_CLAIMS),
    required_check_keys=(
        "generic_execution",
        "carry_clause_exercised",
        "requested_evidence_complete",
        "result_or_honest_zero",
        "proof_carrying_real_rows",
        "control_assumption_carried",
    ),
)

CONTROL_EVIDENCE_FIELDS = [
    "carry_status",
    "carry_reason",
    "carry_episode_id",
    "carrier_id",
    "team_role",
    "source_reception_pass_id",
    "terminal_pass_id",
    "terminal_detection_status",
    "terminal_detection_reason",
    "carry_start_frame_id",
    "carry_end_frame_id",
    "carry_duration_seconds",
    "start_point",
    "end_point",
    "displacement_m",
    "carry_forward_progression_m",
    "possession_continuity_status",
    "possession_continuity_reason",
    "control_continuity_status",
    "control_continuity_reason",
    "controlled_frame_ratio",
    "comoving_frame_ratio",
    "missing_frame_ratio",
    "observed_frame_count",
    "controlled_frame_count",
    "comoving_frame_count",
    "velocity_observed_frame_count",
    "missing_frame_count",
    "control_model",
    "control_bias",
    "control_distance_m",
    "nearest_teammate_margin_m",
    "maximum_ball_player_speed_delta_mps",
    "minimum_controlled_frame_ratio",
    "minimum_comoving_frame_ratio",
    "maximum_missing_frame_ratio",
    "minimum_displacement_m",
    "maximum_carry_seconds",
]


def carry_episode_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "carry_episode_probe_v1",
            "recipe_version": "0.1.0",
            "display_name": "Controlled Carry Episode Probe",
            "description": (
                "Experimental substrate probe: identify observed same-player movement with the ball "
                "from controlled reception to the same player's next confirmed pass release under a "
                "conservative control-continuity model."
            ),
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "A same-player carry interval was identified between controlled reception and confirmed pass release.",
                "Carrier displacement and forward progression were measured from observed tracking endpoints.",
                "Control continuity was evaluated with declared distance, nearest-player, co-movement, and missing-tracking thresholds.",
            ],
            "disallowed_claims": [
                "The system inferred dribbling skill, pressure-breaking quality, intent, decision quality, or tactical causation.",
                "The system claimed the carry beat or bypassed a defender.",
                "The system inferred optimality or pass probability.",
            ],
            "limitations": [
                "v0.1 ends carries at the same player's next confirmed pass release; tracking-only endings are deferred.",
                "The base primitive is direction-neutral; progressive carry is a composition over forward_progression_m.",
                "Ambiguous or missing ball/carrier tracking produces UNKNOWN rather than a carry.",
            ],
            "output_classifications": ["CONTROLLED_CARRY_EPISODE"],
            "parameters": [
                _number_param("maximum_carry_seconds", "second", 10.0, "Maximum interval from controlled reception to same-player pass release."),
                _number_param("minimum_displacement_m", "metre", 3.0, "Minimum movement distance required for a carry PASS."),
                _number_param("control_distance_m", "metre", 2.5, "Maximum ball-carrier distance for control evidence."),
                _number_param("nearest_teammate_margin_m", "metre", 1.0, "Allowed nearest-teammate margin around the ball."),
                _number_param("maximum_ball_player_speed_delta_mps", "none", 10.0, "Touch-tolerant maximum ball/player velocity-vector difference."),
                _number_param("minimum_controlled_frame_ratio", "none", 1.0, "Minimum observed-frame control ratio."),
                _number_param("minimum_comoving_frame_ratio", "none", 0.75, "Minimum velocity-observed co-moving ratio."),
                _number_param("maximum_missing_frame_ratio", "none", 0.02, "Maximum missing ball/player tracking ratio."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "carry_episode_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "carry_episode_probe",
            "plan_version": "0.1.0",
            "recipe_id": "carry_episode_probe_v1",
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
                    "node_id": "carry_episode",
                    "catalog_ref": "carry_episode",
                    "version": "0.1.0",
                    "inputs": {
                        "controlled_pass_anchors": {
                            "source_node_id": "controlled_pass",
                            "output_name": "anchors",
                        },
                    },
                    "parameters": {
                        "maximum_carry_seconds": {"kind": "parameter", "name": "maximum_carry_seconds"},
                        "minimum_displacement_m": {"kind": "parameter", "name": "minimum_displacement_m"},
                        "control_distance_m": {"kind": "parameter", "name": "control_distance_m"},
                        "nearest_teammate_margin_m": {"kind": "parameter", "name": "nearest_teammate_margin_m"},
                        "maximum_ball_player_speed_delta_mps": {
                            "kind": "parameter",
                            "name": "maximum_ball_player_speed_delta_mps",
                        },
                        "minimum_controlled_frame_ratio": {
                            "kind": "parameter",
                            "name": "minimum_controlled_frame_ratio",
                        },
                        "minimum_comoving_frame_ratio": {
                            "kind": "parameter",
                            "name": "minimum_comoving_frame_ratio",
                        },
                        "maximum_missing_frame_ratio": {
                            "kind": "parameter",
                            "name": "maximum_missing_frame_ratio",
                        },
                    },
                },
                _eq_predicate("carry_pass", "carry_episode", "carry_status", "PASS"),
            ],
            "classification_rules": [
                {
                    "label": "CONTROLLED_CARRY_EPISODE",
                    "predicate_ids": ["carry_pass"],
                    "description": "Observed same-player movement-under-control carry under frozen thresholds.",
                }
            ],
            "anchor_source": {"source_node_id": "carry_episode", "output_name": "anchor_evaluations"},
            "requested_evidence": [_evidence("carry_episode", field) for field in CONTROL_EVIDENCE_FIELDS],
        },
    }


def verify_carry_episode() -> dict[str, Any]:
    _registry, _runtime_manifest, registry_lock, parity_report = generate_scp0_artifacts(write=write_mode())
    document_payload = carry_episode_document()
    plan_artifact_drift = emit_tracked_artifact(
        PLAN_ARTIFACT_PATH,
        json.dumps(document_payload, indent=2, sort_keys=True) + "\n",
    )
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
    if plan_artifact_drift is not None:
        findings.append(
            {
                "code": "plan_artifact_drift",
                "message": plan_artifact_drift["message"],
                "path": str(PLAN_ARTIFACT_PATH),
            }
        )
    if parity_report.status != "PASS":
        findings.append(
            {
                "code": "scp0_parity_failed",
                "parity_status": parity_report.status,
                "parity_finding_count": len(parity_report.findings),
            }
        )
    if execution.status != ExecutionStatus.PASS:
        findings.append({"code": "execution_not_pass", "message": f"Execution status was {execution.status}.", "path": "execution.status"})
    if execution.provenance.get("compatibility_profile") != "generic":
        findings.append({"code": "non_generic_execution", "message": "Carry probe must run through the generic executor.", "path": "execution.provenance.compatibility_profile"})
    if evidence_failure_count:
        findings.append({"code": "requested_evidence_missing", "message": f"{evidence_failure_count} requested evidence failure(s).", "path": "execution.provenance.requested_evidence_failures"})
    if not rows and not honest_zero:
        findings.append({"code": "zero_not_honest", "message": "Zero-result execution did not satisfy honest-zero conditions.", "path": "execution"})
    if proof_carrying["status"] != "PASS":
        findings.append({"code": "proof_carrying_real_rows_failed", "message": "Carry real rows did not satisfy PASS/FAIL/UNKNOWN branch discipline.", "path": "proof_carrying_real_rows"})

    sample = rows[0] if rows else {}
    requested = sample.get("requested_evidence") if isinstance(sample, dict) else {}
    control_assumption_carried = bool(requested) and all(
        requested.get(field) is not None
        for field in [
            "control_model",
            "control_bias",
            "control_distance_m",
            "nearest_teammate_margin_m",
            "maximum_ball_player_speed_delta_mps",
            "minimum_controlled_frame_ratio",
            "minimum_comoving_frame_ratio",
            "maximum_missing_frame_ratio",
        ]
    )
    if rows and not control_assumption_carried:
        findings.append({"code": "control_assumption_missing", "message": "PASS result did not carry the control model and threshold evidence.", "path": "sample_result.requested_evidence"})

    report = {
        "schema_version": "afl.carry_episode.v1",
        "registry_lock": registry_lock.model_dump(mode="json"),
        "milestone": "AFL-08 carry_episode substrate",
        "status": "PASS" if not findings else "FAIL",
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
        },
        "slice_unlocks": {
            "carry_episode": "Observed same-player movement-under-control intervals between controlled reception and terminal pass release.",
            "q2": "Carry clauses can now compile over a direction-neutral base primitive; progressive carry remains a composition over forward_progression_m.",
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
            "real_row_status_counts": probe.get("carry_status_counts", {}),
            "branch_source_note": "PASS/FAIL/UNKNOWN are exercised by real first-period carry rows.",
        },
        "claim_boundary": {
            "dependency_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "required_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
            "enforced_in_report": True,
        },
        "sample_result": {
            "result_id": sample.get("result_id"),
            "classification": sample.get("classification"),
            "requested_evidence": requested,
        },
        "checks": {
            "generic_execution": execution.provenance.get("compatibility_profile") == "generic",
            "carry_clause_exercised": probe.get("carry_count", 0) > 0,
            "requested_evidence_complete": evidence_failure_count == 0,
            "result_or_honest_zero": bool(rows) or honest_zero,
            "proof_carrying_real_rows": proof_carrying["status"] == "PASS",
            "control_assumption_carried": control_assumption_carried,
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

    value = state.runtime_values["carry_episode"]["anchor_evaluations"]
    records = [record for record in value.value if isinstance(record, dict)]
    return {
        "match_id": bound_plan.match_ids[0],
        "period": bound_plan.periods[0],
        "carry_count": len(records),
        "carry_status_counts": _status_counts(records, "carry_status"),
        "carry_reason_counts": _status_counts(records, "carry_reason"),
        "control_continuity_status_counts": _status_counts(records, "control_continuity_status"),
        "possession_continuity_status_counts": _status_counts(records, "possession_continuity_status"),
    }


def proof_carrying_records(probe: dict[str, Any]) -> list[dict[str, Any]]:
    counts = probe.get("carry_status_counts", {})
    reasons = probe.get("carry_reason_counts", {})
    rows: list[dict[str, Any]] = []
    if int(counts.get("PASS", 0)) > 0:
        rows.append(
            {
                "judgement": "PASS",
                "witnesses": [
                    {
                        "source": "carry_episode",
                        "count": int(counts["PASS"]),
                        "required_evidence": ["carry_episode_id", "carrier_id", "carry_start_frame_id", "carry_end_frame_id"],
                    }
                ],
            }
        )
    if int(counts.get("FAIL", 0)) > 0:
        rows.append(
            {
                "judgement": "FAIL",
                "evaluation_domain_complete": True,
                "source": "carry_episode",
                "count": int(counts["FAIL"]),
                "domain_evidence": sorted(reasons),
            }
        )
    if int(counts.get("UNKNOWN", 0)) > 0:
        unknown_reasons = [
            reason
            for reason in sorted(reasons)
            if reason
            in {
                "frame_window_missing",
                "possession_window_missing",
                "control_evidence_missing",
                "tracking_missing_during_carry",
                "attacking_direction_missing",
                "carry_endpoint_missing",
            }
        ]
        rows.append(
            {
                "judgement": "UNKNOWN",
                "unmet_premises": unknown_reasons or ["carry_unknown"],
                "count": int(counts["UNKNOWN"]),
            }
        )
    return rows


def main() -> int:
    report = verify_carry_episode()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
