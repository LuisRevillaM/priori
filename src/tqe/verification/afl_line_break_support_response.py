"""AFL-08 capstone verifier for Line-Break Support Response.

This verifier proves composition, not a new measurement primitive. The typed
plan reuses the existing line-package capabilities:

controlled_pass_episode -> defensive_line_model -> relative_position_to_line
-> controlled_line_break_episode -> support_arrival_relation
-> lane_occupancy -> local_number_relation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import OUTPUT_ROOT, generate_scp0_artifacts


REPORT_PATH = Path("artifacts/autonomous/afl-line-break-support-response-verification-report.json")
PLAN_ARTIFACT_PATH = Path("config/query-plans/line_break_support_response.experimental.v1.json")
PASSPORT_PROJECTION_PATH = OUTPUT_ROOT / "capability-passport-projection.json"

CAPSTONE_DEPENDENCY_SUBJECTS = [
    "runtime:primitive:controlled_pass_episode:0.1.0",
    "runtime:primitive:defensive_line_model:0.1.0",
    "runtime:primitive:relative_position_to_line:0.1.0",
    "runtime:primitive:controlled_line_break_episode:0.1.0",
    "runtime:relation:support_arrival_relation:0.1.0",
    "runtime:primitive:lane_occupancy:0.1.0",
    "runtime:relation:local_number_relation:0.1.0",
]

REQUIRED_PROHIBITED_CLAIMS = {
    "defensive_line_was_broken",
    "tactical_line_role_identified",
    "line_break_caused_by_pass",
    "line_break_caused_support",
    "player_intent_inferred",
    "passer_intended_measured_outcome",
    "support_quality_inferred",
    "pressure_inferred",
    "communication_inferred",
    "scanning_inferred",
    "pass_was_optimal",
    "pass_probability_inferred",
    "proves_pass_probability",
    "proves_pass_optimality",
}


LINE_BREAK_EVIDENCE_FIELDS = [
    "anchor_id",
    "anchor_frame_id",
    "line_break_status",
    "line_break_reason",
    "pass_episode_id",
    "physical_release_frame_id",
    "controlled_reception_frame_id",
    "line_anchor_frame_id",
    "line_x_m",
    "release_relative_position_status",
    "release_signed_distance_to_line_m",
    "reception_relative_position_status",
    "reception_signed_distance_to_line_m",
    "line_buffer_m",
]

CONTROLLED_PASS_EVIDENCE_FIELDS = [
    "passer_id",
    "receiver_id",
    "forward_progression_m",
]

SUPPORT_ARRIVAL_EVIDENCE_FIELDS = [
    "support_arrival_status",
    "support_arrival_reason",
    "support_anchor_frame_id",
    "support_window_start_frame_id",
    "support_window_end_frame_id",
    "support_region_mode",
    "maximum_arrival_seconds",
    "minimum_duration_seconds",
    "maximum_support_distance_m",
    "minimum_supporting_players",
    "supporting_player_ids",
    "first_arrival_frame_id",
    "first_arrival_seconds_after_anchor",
    "support_duration_seconds",
    "coverage_status",
    "reference_point",
]

LANE_OCCUPANCY_EVIDENCE_FIELDS = [
    "lane_occupancy_status",
    "lane_occupancy_reason",
    "lane_evaluation_frame_id",
    "lane_player_scope",
    "occupied_lanes",
    "occupied_lane_count",
    "required_occupied_lane_count",
]

LOCAL_NUMBER_EVIDENCE_FIELDS = [
    "local_number_status",
    "local_number_reason",
    "local_number_frame_id",
    "radius_m",
    "minimum_difference",
    "minimum_perspective_players",
    "maximum_defending_players",
    "perspective_count",
    "defending_count",
    "local_number_difference",
    "perspective_in_region_player_ids",
    "defending_in_region_player_ids",
]


def line_break_support_response_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "line_break_support_response_v1",
            "recipe_version": "0.1.0",
            "display_name": "Line-Break Support Response",
            "description": (
                "Experimental capstone composition that finds observed controlled-pass "
                "crossings of a supplied geometric defensive line and evaluates the "
                "declared support-arrival, lane-occupancy, and local-number context "
                "around the controlled reception."
            ),
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "A controlled pass crossed a supplied observed geometric defensive line under declared thresholds.",
                "Observed teammates satisfied the declared support-arrival relation around the controlled reception.",
                "Observed attacking players occupied at least the declared number of lateral lanes.",
                "Observed local player counts satisfied the declared numeric relation.",
                "The replay coordinates come from canonical tracking frames.",
            ],
            "disallowed_claims": [
                "The system identified a first, second, midfield, or back defensive line.",
                "The pass caused the line break or support response.",
                "The pass, support run, or resulting decision was optimal.",
                "The measured support was the right tactical option.",
                "The system inferred player intent, communication, scanning, or pressure.",
                "The result is a pass probability or video-backed claim.",
            ],
            "limitations": [
                "Experimental plan; not an approved recipe.",
                "Line crossing uses a supplied observed geometric line, not a named tactical line taxonomy.",
                "Support, lane, and local-number outputs are observed geometric relations only.",
                "No offside, pressure, body orientation, pass probability, decision-quality, or intention model is evaluated.",
            ],
            "output_classifications": ["LINE_BREAK_SUPPORT_RESPONSE"],
            "parameters": [
                _number_param(
                    "goal_side_buffer_m",
                    "metre",
                    1.0,
                    "Minimum distance beyond the ball for defenders to count as goal-side.",
                ),
                _number_param(
                    "line_band_width_m",
                    "metre",
                    2.0,
                    "Maximum normalized x-span of defenders in one observed line band.",
                ),
                _number_param(
                    "minimum_line_defenders",
                    "count",
                    4,
                    "Minimum defenders required to form an observed line.",
                ),
                _number_param(
                    "line_buffer_m",
                    "metre",
                    0.5,
                    "Distance from the supplied line treated as level.",
                ),
                _number_param(
                    "maximum_arrival_seconds",
                    "second",
                    2.0,
                    "Latest support arrival after the controlled reception.",
                ),
                _number_param(
                    "minimum_duration_seconds",
                    "second",
                    0.4,
                    "Minimum continuous observed support duration.",
                ),
                _number_param(
                    "maximum_support_distance_m",
                    "metre",
                    8.0,
                    "Maximum distance from the controlled receiver reference point.",
                ),
                _number_param(
                    "minimum_supporting_players",
                    "count",
                    1,
                    "Minimum observed support players required.",
                ),
                _number_param(
                    "required_occupied_lane_count",
                    "count",
                    3,
                    "Minimum number of observed lateral lanes occupied by attacking players.",
                ),
                _number_param(
                    "local_radius_m",
                    "metre",
                    12.0,
                    "Radius around the controlled receiver reference point for local-number counting.",
                ),
                _number_param(
                    "local_minimum_difference",
                    "count",
                    0,
                    "Minimum perspective minus defending local player count.",
                ),
                _number_param(
                    "local_minimum_perspective_players",
                    "count",
                    1,
                    "Minimum observed attacking players inside the local region.",
                ),
                _number_param(
                    "local_maximum_defending_players",
                    "count",
                    99,
                    "Maximum observed defending players inside the local region.",
                ),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "line_break_support_response_probe",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "line_break_support_response",
            "plan_version": "0.1.0",
            "recipe_id": "line_break_support_response_v1",
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
                    "node_id": "defensive_line_release",
                    "catalog_ref": "defensive_line_model",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {
                            "source_node_id": "controlled_pass",
                            "output_name": "anchors",
                        },
                    },
                    "parameters": {
                        "goal_side_buffer_m": {
                            "kind": "parameter",
                            "name": "goal_side_buffer_m",
                        },
                        "line_band_width_m": {
                            "kind": "parameter",
                            "name": "line_band_width_m",
                        },
                        "minimum_line_defenders": {
                            "kind": "parameter",
                            "name": "minimum_line_defenders",
                        },
                        "anchor_frame_field": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": "physical_release_frame_id",
                        },
                    },
                },
                _relative_position_node(
                    node_id="release_relative_position",
                    entity_frame_field="physical_release_frame_id",
                ),
                _relative_position_node(
                    node_id="reception_relative_position",
                    entity_frame_field="controlled_reception_frame_id",
                ),
                {
                    "kind": "primitive",
                    "node_id": "line_break",
                    "catalog_ref": "controlled_line_break_episode",
                    "version": "0.1.0",
                    "inputs": {
                        "controlled_pass_anchors": {
                            "source_node_id": "controlled_pass",
                            "output_name": "anchors",
                        },
                        "line_evaluations": {
                            "source_node_id": "defensive_line_release",
                            "output_name": "anchor_evaluations",
                        },
                        "release_relative_positions": {
                            "source_node_id": "release_relative_position",
                            "output_name": "anchor_evaluations",
                        },
                        "reception_relative_positions": {
                            "source_node_id": "reception_relative_position",
                            "output_name": "anchor_evaluations",
                        },
                    },
                    "parameters": {
                        "line_buffer_m": {
                            "kind": "parameter",
                            "name": "line_buffer_m",
                        },
                    },
                },
                {
                    "kind": "relation",
                    "node_id": "support_arrival",
                    "catalog_ref": "support_arrival_relation",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {
                            "source_node_id": "line_break",
                            "output_name": "anchor_evaluations",
                        },
                    },
                    "parameters": {
                        "anchor_frame_field": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": "controlled_reception_frame_id",
                        },
                        "candidate_scope": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": "perspective_outfield",
                        },
                        "support_region_mode": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": "WITHIN_DISTANCE_OF_REFERENCE_POINT",
                        },
                        "maximum_arrival_seconds": {
                            "kind": "parameter",
                            "name": "maximum_arrival_seconds",
                        },
                        "minimum_duration_seconds": {
                            "kind": "parameter",
                            "name": "minimum_duration_seconds",
                        },
                        "maximum_support_distance_m": {
                            "kind": "parameter",
                            "name": "maximum_support_distance_m",
                        },
                        "minimum_supporting_players": {
                            "kind": "parameter",
                            "name": "minimum_supporting_players",
                        },
                    },
                },
                {
                    "kind": "primitive",
                    "node_id": "lane_occupancy",
                    "catalog_ref": "lane_occupancy",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {
                            "source_node_id": "line_break",
                            "output_name": "anchor_evaluations",
                        },
                    },
                    "parameters": {
                        "frame_field": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": "controlled_reception_frame_id",
                        },
                        "player_scope": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": "perspective_outfield",
                        },
                        "required_occupied_lane_count": {
                            "kind": "parameter",
                            "name": "required_occupied_lane_count",
                        },
                    },
                },
                {
                    "kind": "relation",
                    "node_id": "local_number",
                    "catalog_ref": "local_number_relation",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {
                            "source_node_id": "line_break",
                            "output_name": "anchor_evaluations",
                        },
                    },
                    "parameters": {
                        "frame_field": {
                            "payload_type": "enum",
                            "unit": "none",
                            "value": "controlled_reception_frame_id",
                        },
                        "radius_m": {
                            "kind": "parameter",
                            "name": "local_radius_m",
                        },
                        "minimum_difference": {
                            "kind": "parameter",
                            "name": "local_minimum_difference",
                        },
                        "minimum_perspective_players": {
                            "kind": "parameter",
                            "name": "local_minimum_perspective_players",
                        },
                        "maximum_defending_players": {
                            "kind": "parameter",
                            "name": "local_maximum_defending_players",
                        },
                    },
                },
                _status_predicate(
                    node_id="line_break_pass",
                    source_node_id="line_break",
                    output_name="line_break_status",
                ),
                _status_predicate(
                    node_id="support_arrival_pass",
                    source_node_id="support_arrival",
                    output_name="support_arrival_status",
                ),
                _status_predicate(
                    node_id="lane_occupancy_pass",
                    source_node_id="lane_occupancy",
                    output_name="lane_occupancy_status",
                ),
                _status_predicate(
                    node_id="local_number_pass",
                    source_node_id="local_number",
                    output_name="local_number_status",
                ),
            ],
            "classification_rules": [
                {
                    "label": "LINE_BREAK_SUPPORT_RESPONSE",
                    "predicate_ids": [
                        "line_break_pass",
                        "support_arrival_pass",
                        "lane_occupancy_pass",
                        "local_number_pass",
                    ],
                    "description": (
                        "Observed controlled line crossing with declared support arrival, "
                        "lane occupancy, and local-number context."
                    ),
                },
            ],
            "anchor_source": {
                "source_node_id": "line_break",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": requested_evidence(),
        },
    }


def requested_evidence() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    result.extend(_evidence("line_break", field) for field in LINE_BREAK_EVIDENCE_FIELDS)
    result.extend(
        _evidence("controlled_pass", field, alias=f"controlled_pass_{field}", output_name="anchors")
        for field in CONTROLLED_PASS_EVIDENCE_FIELDS
    )
    result.extend(
        _evidence("support_arrival", field, alias=f"support_{field}")
        for field in SUPPORT_ARRIVAL_EVIDENCE_FIELDS
    )
    result.extend(
        _evidence("lane_occupancy", field, alias=f"lane_{field}")
        for field in LANE_OCCUPANCY_EVIDENCE_FIELDS
    )
    result.extend(
        _evidence("local_number", field, alias=f"local_{field}")
        for field in LOCAL_NUMBER_EVIDENCE_FIELDS
    )
    return result


def _number_param(name: str, unit: str, value: float | int, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "payload_type": "number",
        "unit": unit,
        "required": False,
        "default": {"payload_type": "number", "unit": unit, "value": value},
        "description": description,
    }


def _relative_position_node(*, node_id: str, entity_frame_field: str) -> dict[str, Any]:
    return {
        "kind": "primitive",
        "node_id": node_id,
        "catalog_ref": "relative_position_to_line",
        "version": "0.1.0",
        "inputs": {
            "line_evaluations": {
                "source_node_id": "defensive_line_release",
                "output_name": "anchor_evaluations",
            },
            "entity_anchors": {
                "source_node_id": "controlled_pass",
                "output_name": "anchors",
            },
        },
        "parameters": {
            "entity_id_field": {
                "payload_type": "enum",
                "unit": "none",
                "value": "receiver_id",
            },
            "entity_frame_field": {
                "payload_type": "enum",
                "unit": "none",
                "value": entity_frame_field,
            },
            "line_buffer_m": {"kind": "parameter", "name": "line_buffer_m"},
        },
    }


def _status_predicate(*, node_id: str, source_node_id: str, output_name: str) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": {
            "source_node_id": source_node_id,
            "output_name": output_name,
        },
        "operator": {"name": "eq", "version": "1.0.0"},
        "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
    }


def _evidence(
    source_node_id: str,
    field: str,
    alias: str | None = None,
    *,
    output_name: str = "anchor_evaluations",
) -> dict[str, Any]:
    return {
        "source": {
            "source_node_id": source_node_id,
            "output_name": output_name,
        },
        "field": field,
        "alias": alias or field,
    }


def _load_passport_projection() -> dict[str, Any]:
    if not PASSPORT_PROJECTION_PATH.exists():
        return {}
    return json.loads(PASSPORT_PROJECTION_PATH.read_text(encoding="utf-8"))


def _dependency_prohibited_claims(projection: dict[str, Any]) -> set[str]:
    target_subjects = set(CAPSTONE_DEPENDENCY_SUBJECTS)
    return {
        claim
        for passport in projection.get("passports", [])
        if isinstance(passport, dict) and passport.get("subject_ref") in target_subjects
        for contract in passport.get("claim_contracts", [])
        for claim in contract.get("prohibited", [])
    }


def _result_status_summary(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    status_aliases = {
        "line_break": "line_break_status",
        "support": "support_support_arrival_status",
        "lane": "lane_lane_occupancy_status",
        "local_number": "local_local_number_status",
    }
    summary: dict[str, list[str]] = {}
    for label, alias in status_aliases.items():
        summary[label] = sorted(
            {
                str(row.get("requested_evidence", {}).get(alias))
                for row in rows
                if isinstance(row.get("requested_evidence"), dict)
            }
        )
    return summary


def verify_line_break_support_response() -> dict[str, Any]:
    _registry, _runtime_manifest, lock, parity_report = generate_scp0_artifacts(write=True)
    document_payload = line_break_support_response_document()
    document = TacticalQueryDocument.model_validate(document_payload)
    bound_plan = bind_document(document)
    execution = TacticalQueryExecutor().execute(bound_plan)
    rows = execution_result_rows(execution)
    passport_projection = _load_passport_projection()
    prohibited_claims = _dependency_prohibited_claims(passport_projection)

    findings: list[dict[str, str]] = []
    if parity_report.status != "PASS":
        findings.append(
            {
                "code": "scp0_parity_failed",
                "message": "SCP-0 artifact generation did not pass.",
                "path": "semantic-registry",
            }
        )
    if execution.status != ExecutionStatus.PASS:
        findings.append(
            {
                "code": "execution_not_pass",
                "message": f"Execution status was {execution.status}.",
                "path": "execution.status",
            }
        )
    if execution.provenance.get("compatibility_profile") != "generic":
        findings.append(
            {
                "code": "non_generic_execution",
                "message": "Line-break support response must run through the generic executor.",
                "path": "execution.provenance.compatibility_profile",
            }
        )
    if not rows:
        findings.append(
            {
                "code": "no_real_capstone_results",
                "message": "The capstone composition produced no real PASS rows.",
                "path": "execution.results",
            }
        )
    evidence_failure_count = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    if evidence_failure_count:
        findings.append(
            {
                "code": "requested_evidence_missing",
                "message": f"{evidence_failure_count} result(s) had missing requested evidence.",
                "path": "execution.provenance.requested_evidence_failures",
            }
        )
    missing_prohibitions = sorted(REQUIRED_PROHIBITED_CLAIMS - prohibited_claims)
    if missing_prohibitions:
        findings.append(
            {
                "code": "composition_missing_dependency_prohibited_claims",
                "message": f"Dependency passports lack prohibited claims: {', '.join(missing_prohibitions)}.",
                "path": "capability_passport_projection.passports",
            }
        )

    sample = rows[0] if rows else {}
    requested = sample.get("requested_evidence") if isinstance(sample, dict) else {}
    status = "PASS" if not findings else "FAIL"
    return {
        "schema_version": "1.0",
        "milestone": "AFL-08 line_break_support_response",
        "status": status,
        "registry_lock": lock.model_dump(mode="json"),
        "plan": {
            "path": str(PLAN_ARTIFACT_PATH),
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
            "dependency_subjects": CAPSTONE_DEPENDENCY_SUBJECTS,
        },
        "execution": {
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "compatibility_profile": execution.provenance.get("compatibility_profile"),
            "result_count": len(rows),
            "requested_evidence_failure_count": evidence_failure_count,
            "runtime_value_count": execution.provenance.get("runtime_value_count"),
            "runtime_trace_hash": execution.provenance.get("runtime_trace_hash"),
            "observed_statuses": _result_status_summary(rows),
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
            "real_capstone_results": len(rows) > 0,
            "requested_evidence_complete": evidence_failure_count == 0,
            "dependency_overclaim_boundary_present": REQUIRED_PROHIBITED_CLAIMS.issubset(
                prohibited_claims
            ),
        },
        "findings": findings,
    }


def main() -> None:
    report = verify_line_break_support_response()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
