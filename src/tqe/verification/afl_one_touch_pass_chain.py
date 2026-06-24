"""AFL-08 One-Touch / Pass-Chain package verifier.

This verifier is the first new consumer of the AFL-09A validation-factory
spine. It proves a narrow package:

one_touch_relay_episode -> receiver_line_transition_during_pass_leg
-> pass_chain_episode -> first_time_relay_after_receiver_line_transition_v1.

The capstone is literal: observed first-time relay after the receiver/relay
player transitioned beyond a supplied observed line. It does not claim a
third-man combination, tactical intent, causation, decision quality, or that the
ball/pass itself crossed the line.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.runtime.one_touch import evaluate_one_touch_relays
from tqe.semantic_registry.generate import OUTPUT_ROOT, generate_scp0_artifacts
from tqe.verification.afl_validation_factory import (
    ValidationFactorySpec,
    attach_validation_factory,
    validate_proof_carrying_records,
)


REPORT_PATH = Path("artifacts/autonomous/afl-one-touch-pass-chain-verification-report.json")
EXPECTATION_PATH = Path(
    "delivery/autonomous/afl09a/frozen-expectations/one_touch_pass_chain.json"
)
PLAN_ARTIFACT_PATH = Path("config/query-plans/first_time_relay_after_receiver_line_transition.experimental.v1.json")
PASSPORT_PROJECTION_PATH = OUTPUT_ROOT / "capability-passport-projection.json"

MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
SUBJECT_REF = "recipe:first_time_relay_after_receiver_line_transition_v1:0.1.0"
DEPENDENCY_SUBJECTS = [
    "runtime:primitive:one_touch_relay_episode:0.1.0",
    "runtime:primitive:defensive_line_model:0.1.0",
    "runtime:primitive:relative_position_to_line:0.1.0",
    "runtime:primitive:receiver_line_transition_during_pass_leg:0.1.0",
    "runtime:primitive:controlled_pass_episode:0.1.0",
    "runtime:primitive:pass_chain_episode:0.1.0",
]
REQUIRED_PROHIBITED_CLAIMS = {
    "pass_crossed_line_claimed",
    "defensive_line_was_broken",
    "tactical_line_role_identified",
    "line_break_caused_by_pass",
    "planned_combination_inferred",
    "third_man_combination_claimed",
    "player_intent_inferred",
    "pass_was_optimal",
    "pass_probability_inferred",
    "decision_quality_inferred",
}
VALIDATION_FACTORY_SPEC = ValidationFactorySpec(
    factory_id="afl09a.one_touch_pass_chain.0_1_0",
    subject_ref=SUBJECT_REF,
    expectation_path=EXPECTATION_PATH,
    source_verifier="tqe.verification.afl_one_touch_pass_chain",
    threshold_version="first_time_relay_after_receiver_line_transition.v0.1.0",
    required_prohibited_claims=frozenset(REQUIRED_PROHIBITED_CLAIMS),
    required_check_keys=(
        "generic_execution",
        "real_capstone_results_or_honest_zero",
        "requested_evidence_complete",
        "proof_carrying_real_rows",
        "claim_boundary_present",
    ),
)

RELAY_EVIDENCE_FIELDS = [
    "input_pass_episode_id",
    "relay_pass_episode_id",
    "input_passer_id",
    "relay_player_id",
    "declared_next_pass_recipient_id",
    "input_physical_release_frame_id",
    "relay_touch_frame_id",
    "relay_physical_release_frame_id",
    "relay_dwell_seconds",
    "one_touch_relay_status",
    "one_touch_relay_reason",
    "relay_touch_ball_point",
    "relay_touch_player_point",
]
TRANSITION_EVIDENCE_FIELDS = [
    "receiver_line_transition_status",
    "receiver_line_transition_reason",
    "line_x_m",
    "release_relative_position_status",
    "release_signed_distance_to_line_m",
    "relay_relative_position_status",
    "relay_signed_distance_to_line_m",
]
CHAIN_EVIDENCE_FIELDS = [
    "pass_chain_status",
    "pass_chain_reason",
    "terminal_pass_episode_id",
    "terminal_receiver_id",
    "terminal_controlled_reception_frame_id",
    "terminal_forward_progression_m",
    "terminal_controlled_pass_status",
]


def one_touch_pass_chain_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "first_time_relay_after_receiver_line_transition_v1",
            "recipe_version": "0.1.0",
            "display_name": "First-Time Relay After Receiver Line Transition",
            "description": (
                "Experimental composition that finds event-linked first-time relays "
                "where the receiver/relay player moves beyond a supplied observed "
                "line during the input pass leg and the onward pass has a terminal "
                "controlled reception."
            ),
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "The relay was event-linked and tracking-bounded under declared thresholds.",
                "The receiver/relay player transitioned from not beyond to beyond a supplied observed line.",
                "The onward pass reached a terminal controlled reception.",
                "Replay/evidence comes from canonical event and tracking records.",
            ],
            "disallowed_claims": [
                "The pass or ball itself crossed the line.",
                "The system identified a tactical defensive-line role or definitive line break.",
                "The sequence was a planned third-man combination.",
                "The players intended the measured outcome.",
                "The decision was optimal or has an inferred completion probability.",
            ],
            "limitations": [
                "Experimental plan; not an approved recipe.",
                "v0.1 requires provider event linkage for the relay.",
                "Tracking-only redirection candidates are deferred.",
                "The line-transition measurement is a receiver/relay-player position transition, not ball trajectory.",
            ],
            "output_classifications": ["FIRST_TIME_RELAY_AFTER_RECEIVER_LINE_TRANSITION"],
            "parameters": [
                _number_param("relay_max_event_gap_seconds", "second", 3.0, "Maximum gap between input pass event and relay pass event."),
                _number_param("relay_touch_distance_m", "metre", 2.75, "Maximum ball-player distance for relay-touch evidence."),
                _number_param("maximum_relay_dwell_seconds", "second", 0.56, "Maximum relay touch-to-release interval."),
                _number_param("goal_side_buffer_m", "metre", 1.0, "Minimum distance beyond the ball for defenders to count as goal-side."),
                _number_param("line_band_width_m", "metre", 2.0, "Maximum normalized x-span of defenders in one observed line band."),
                _number_param("minimum_line_defenders", "count", 4, "Minimum defenders required to form an observed line."),
                _number_param("line_buffer_m", "metre", 0.5, "Distance from the supplied line treated as level."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "first_time_relay_after_receiver_line_transition_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "first_time_relay_after_receiver_line_transition",
            "plan_version": "0.1.0",
            "recipe_id": "first_time_relay_after_receiver_line_transition_v1",
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "nodes": [
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
                {
                    "kind": "primitive",
                    "node_id": "defensive_line_at_input_release",
                    "catalog_ref": "defensive_line_model",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {
                            "source_node_id": "one_touch_relay",
                            "output_name": "anchor_evaluations",
                        },
                    },
                    "parameters": {
                        "goal_side_buffer_m": {"kind": "parameter", "name": "goal_side_buffer_m"},
                        "line_band_width_m": {"kind": "parameter", "name": "line_band_width_m"},
                        "minimum_line_defenders": {"kind": "parameter", "name": "minimum_line_defenders"},
                        "anchor_frame_field": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": "input_physical_release_frame_id",
                        },
                    },
                },
                _relative_position_node(
                    node_id="relay_position_at_input_release",
                    entity_frame_field="input_physical_release_frame_id",
                ),
                _relative_position_node(
                    node_id="relay_position_at_touch",
                    entity_frame_field="relay_touch_frame_id",
                ),
                {
                    "kind": "primitive",
                    "node_id": "receiver_line_transition",
                    "catalog_ref": "receiver_line_transition_during_pass_leg",
                    "version": "0.1.0",
                    "inputs": {
                        "relay_anchors": {
                            "source_node_id": "one_touch_relay",
                            "output_name": "anchor_evaluations",
                        },
                        "line_evaluations": {
                            "source_node_id": "defensive_line_at_input_release",
                            "output_name": "anchor_evaluations",
                        },
                        "release_relative_positions": {
                            "source_node_id": "relay_position_at_input_release",
                            "output_name": "anchor_evaluations",
                        },
                        "relay_relative_positions": {
                            "source_node_id": "relay_position_at_touch",
                            "output_name": "anchor_evaluations",
                        },
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "terminal_controlled_pass",
                    "catalog_ref": "controlled_pass_episode",
                    "version": "0.1.0",
                },
                {
                    "kind": "primitive",
                    "node_id": "pass_chain",
                    "catalog_ref": "pass_chain_episode",
                    "version": "0.1.0",
                    "inputs": {
                        "relay_anchors": {
                            "source_node_id": "one_touch_relay",
                            "output_name": "anchor_evaluations",
                        },
                        "terminal_controlled_pass_anchors": {
                            "source_node_id": "terminal_controlled_pass",
                            "output_name": "anchors",
                        },
                    },
                },
                _status_predicate("relay_pass", "one_touch_relay", "one_touch_relay_status"),
                _status_predicate(
                    "receiver_line_transition_pass",
                    "receiver_line_transition",
                    "receiver_line_transition_status",
                ),
                _status_predicate("pass_chain_pass", "pass_chain", "pass_chain_status"),
            ],
            "classification_rules": [
                {
                    "label": "FIRST_TIME_RELAY_AFTER_RECEIVER_LINE_TRANSITION",
                    "predicate_ids": [
                        "relay_pass",
                        "receiver_line_transition_pass",
                        "pass_chain_pass",
                    ],
                    "description": (
                        "Observed first-time relay after receiver/relay-player line transition "
                        "with terminal controlled reception."
                    ),
                },
            ],
            "anchor_source": {
                "source_node_id": "pass_chain",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": requested_evidence(),
        },
    }


def requested_evidence() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    result.extend(_evidence("one_touch_relay", field, output_name="anchor_evaluations") for field in RELAY_EVIDENCE_FIELDS)
    result.extend(_evidence("receiver_line_transition", field, output_name="anchor_evaluations") for field in TRANSITION_EVIDENCE_FIELDS)
    result.extend(_evidence("pass_chain", field, output_name="anchor_evaluations") for field in CHAIN_EVIDENCE_FIELDS)
    return result


def verify_one_touch_pass_chain() -> dict[str, Any]:
    _registry, _runtime_manifest, lock, parity_report = generate_scp0_artifacts(write=True)
    document_payload = one_touch_pass_chain_document()
    PLAN_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_ARTIFACT_PATH.write_text(
        json.dumps(document_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    document = TacticalQueryDocument.model_validate(document_payload)
    bound_plan = bind_document(document)
    execution = TacticalQueryExecutor().execute(bound_plan)
    rows = execution_result_rows(execution)
    passport_projection = _load_passport_projection()
    prohibited_claims = _dependency_prohibited_claims(passport_projection)
    evidence_failure_count = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    relay_probe = evaluate_one_touch_relays(
        canonical_root=Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1")),
        match_ids=MATCH_IDS,
    )
    proof_carrying = validate_proof_carrying_records(
        [_proof_carrying_record(record) for record in relay_probe.anchor_evaluations]
    )
    honest_zero_result = (
        not rows
        and execution.status == ExecutionStatus.PASS
        and execution.provenance.get("compatibility_profile") == "generic"
        and evidence_failure_count == 0
    )

    findings: list[dict[str, str]] = []
    if parity_report.status != "PASS":
        findings.append({"code": "scp0_parity_failed", "message": "SCP-0 artifact generation did not pass.", "path": "semantic-registry"})
    if execution.status != ExecutionStatus.PASS:
        findings.append({"code": "execution_not_pass", "message": f"Execution status was {execution.status}.", "path": "execution.status"})
    if execution.provenance.get("compatibility_profile") != "generic":
        findings.append({"code": "non_generic_execution", "message": "One-Touch package must run through the generic executor.", "path": "execution.provenance.compatibility_profile"})
    if evidence_failure_count:
        findings.append({"code": "requested_evidence_missing", "message": f"{evidence_failure_count} result(s) had missing requested evidence.", "path": "execution.provenance.requested_evidence_failures"})
    if not rows and not honest_zero_result:
        findings.append({"code": "zero_not_honest", "message": "Zero-result execution did not satisfy honest-zero conditions.", "path": "execution"})
    if proof_carrying["status"] != "PASS":
        findings.append({"code": "proof_carrying_real_rows_failed", "message": "Real relay rows did not satisfy proof-carrying branch requirements.", "path": "proof_carrying_real_rows"})
    missing_prohibitions = sorted(REQUIRED_PROHIBITED_CLAIMS - prohibited_claims)
    if missing_prohibitions:
        findings.append({"code": "claim_boundary_missing", "message": f"Dependency passports lack prohibited claims: {', '.join(missing_prohibitions)}.", "path": "capability_passport_projection.passports"})

    sample = rows[0] if rows else {}
    requested = sample.get("requested_evidence") if isinstance(sample, dict) else {}
    status = "PASS" if not findings else "FAIL"
    report = {
        "schema_version": "1.0",
        "milestone": "AFL-08 one_touch_pass_chain",
        "status": status,
        "registry_lock": lock.model_dump(mode="json"),
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
            "dependency_subjects": DEPENDENCY_SUBJECTS,
        },
        "execution": {
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "compatibility_profile": execution.provenance.get("compatibility_profile"),
            "result_count": len(rows),
            "requested_evidence_failure_count": evidence_failure_count,
            "runtime_value_count": execution.provenance.get("runtime_value_count"),
            "runtime_trace_hash": execution.provenance.get("runtime_trace_hash"),
            "result_mode": "OBSERVED_RESULTS" if rows else "HONEST_ZERO",
            "honest_zero_result": honest_zero_result,
            "corpus_observation": (
                "One or more observed results under frozen thresholds."
                if rows
                else "No observed results under frozen thresholds; thresholds were not relaxed."
            ),
        },
        "relay_probe": {
            "summary": relay_probe.summary,
            "proof_carrying_real_rows": proof_carrying,
        },
        "sample_result": {
            "result_id": sample.get("result_id"),
            "classification": sample.get("classification"),
            "requested_evidence": requested,
        },
        "claim_boundary": {
            "dependency_prohibited_claims": sorted(prohibited_claims),
            "required_prohibited_claims": sorted(REQUIRED_PROHIBITED_CLAIMS),
        },
        "checks": {
            "generic_execution": execution.provenance.get("compatibility_profile") == "generic",
            "real_capstone_results_or_honest_zero": bool(rows) or honest_zero_result,
            "requested_evidence_complete": evidence_failure_count == 0,
            "proof_carrying_real_rows": proof_carrying["status"] == "PASS",
            "claim_boundary_present": REQUIRED_PROHIBITED_CLAIMS.issubset(prohibited_claims),
        },
        "findings": findings,
    }
    return attach_validation_factory(report, rows=rows, spec=VALIDATION_FACTORY_SPEC)


def _proof_carrying_record(record: dict[str, Any]) -> dict[str, Any]:
    judgement = str(record.get("one_touch_relay_status"))
    if judgement == "PASS":
        return {
            "judgement": "PASS",
            "witnesses": [
                {
                    "input_pass_episode_id": record.get("input_pass_episode_id"),
                    "relay_pass_episode_id": record.get("relay_pass_episode_id"),
                    "relay_touch_frame_id": record.get("relay_touch_frame_id"),
                    "relay_physical_release_frame_id": record.get("relay_physical_release_frame_id"),
                }
            ],
        }
    if judgement == "FAIL":
        return {
            "judgement": "FAIL",
            "evaluation_domain_complete": True,
            "reason": record.get("one_touch_relay_reason"),
        }
    return {
        "judgement": "UNKNOWN",
        "unmet_premises": [str(record.get("one_touch_relay_reason") or "unknown_relay_premise")],
    }


def _relative_position_node(*, node_id: str, entity_frame_field: str) -> dict[str, Any]:
    return {
        "kind": "primitive",
        "node_id": node_id,
        "catalog_ref": "relative_position_to_line",
        "version": "0.1.0",
        "inputs": {
            "line_evaluations": {
                "source_node_id": "defensive_line_at_input_release",
                "output_name": "anchor_evaluations",
            },
            "entity_anchors": {
                "source_node_id": "one_touch_relay",
                "output_name": "anchor_evaluations",
            },
        },
        "parameters": {
            "entity_id_field": {
                "payload_type": "enum",
                "unit": "none",
                "value": "relay_player_id",
            },
            "entity_frame_field": {
                "payload_type": "enum",
                "unit": "none",
                "value": entity_frame_field,
            },
            "line_buffer_m": {"kind": "parameter", "name": "line_buffer_m"},
        },
    }


def _status_predicate(node_id: str, source_node_id: str, output_name: str) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": {"source_node_id": source_node_id, "output_name": output_name},
        "operator": {"name": "eq", "version": "1.0.0"},
        "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
    }


def _number_param(name: str, unit: str, value: float | int, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "payload_type": "number",
        "unit": unit,
        "required": False,
        "default": {"payload_type": "number", "unit": unit, "value": value},
        "description": description,
    }


def _evidence(
    source_node_id: str,
    field: str,
    *,
    output_name: str = "anchor_evaluations",
    alias: str | None = None,
) -> dict[str, Any]:
    return {
        "source": {"source_node_id": source_node_id, "output_name": output_name},
        "field": field,
        "alias": alias or field,
    }


def _load_passport_projection() -> dict[str, Any]:
    if not PASSPORT_PROJECTION_PATH.exists():
        return {}
    return json.loads(PASSPORT_PROJECTION_PATH.read_text(encoding="utf-8"))


def _dependency_prohibited_claims(projection: dict[str, Any]) -> set[str]:
    target_subjects = set(DEPENDENCY_SUBJECTS + [SUBJECT_REF])
    return {
        claim
        for passport in projection.get("passports", [])
        if isinstance(passport, dict) and passport.get("subject_ref") in target_subjects
        for contract in passport.get("claim_contracts", [])
        for claim in contract.get("prohibited", [])
    }


def main() -> None:
    report = verify_one_touch_pass_chain()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
