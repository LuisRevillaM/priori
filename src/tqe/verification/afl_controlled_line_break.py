"""AFL-08 controlled-line-break capability verifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import OUTPUT_ROOT, generate_scp0_artifacts
from tqe.write_mode import write_mode


REPORT_PATH = Path("artifacts/autonomous/afl-controlled-line-break-verification-report.json")
PASSPORT_PROJECTION_PATH = OUTPUT_ROOT / "capability-passport-projection.json"
SUBJECT_REF = "runtime:primitive:controlled_line_break_episode:0.1.0"


def controlled_line_break_probe_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "controlled_line_break_episode_probe",
            "recipe_version": "0.1.0",
            "display_name": "Controlled Line Break Episode Probe",
            "description": "Verification-only probe for controlled pass crossing of a supplied observed line.",
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "A controlled pass crossed a supplied observed line under declared geometry.",
            ],
            "disallowed_claims": [
                "The capability does not identify a first, second, midfield, or back line.",
                "The capability does not prove that the pass caused the line to be broken.",
                "The capability does not infer player intent or pass optimality.",
            ],
            "limitations": [
                "Verification-only probe; not a registered user-facing recipe.",
            ],
            "output_classifications": ["OBSERVED_CONTROLLED_LINE_BREAK"],
            "parameters": [
                _number_param("goal_side_buffer_m", "metre", 1.0, "Minimum distance beyond the ball for defenders to count as goal-side."),
                _number_param("line_band_width_m", "metre", 2.0, "Maximum normalized x-span of defenders in one observed line band."),
                _number_param("minimum_line_defenders", "count", 4, "Minimum defenders required to form an observed line."),
                _number_param("line_buffer_m", "metre", 0.5, "Distance from the line treated as level rather than ahead or behind."),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "controlled_line_break_episode_probe",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "controlled_line_break_episode_probe",
            "plan_version": "0.1.0",
            "recipe_id": "controlled_line_break_episode_probe",
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
                        "goal_side_buffer_m": {"kind": "parameter", "name": "goal_side_buffer_m"},
                        "line_band_width_m": {"kind": "parameter", "name": "line_band_width_m"},
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
                        "line_buffer_m": {"kind": "parameter", "name": "line_buffer_m"},
                    },
                },
                {
                    "kind": "predicate",
                    "node_id": "line_break_pass",
                    "input": {
                        "source_node_id": "line_break",
                        "output_name": "line_break_status",
                    },
                    "operator": {"name": "eq", "version": "1.0.0"},
                    "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                },
            ],
            "classification_rules": [
                {
                    "label": "OBSERVED_CONTROLLED_LINE_BREAK",
                    "predicate_ids": ["line_break_pass"],
                    "description": "Controlled pass receiver crossed the supplied observed line.",
                },
            ],
            "anchor_source": {
                "source_node_id": "line_break",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": [_evidence(field) for field in REQUIRED_EVIDENCE_FIELDS],
        },
    }


REQUIRED_EVIDENCE_FIELDS = [
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


def _evidence(field: str) -> dict[str, Any]:
    return {
        "source": {
            "source_node_id": "line_break",
            "output_name": "anchor_evaluations",
        },
        "field": field,
        "alias": field,
    }


def _load_passport() -> dict[str, Any] | None:
    if not PASSPORT_PROJECTION_PATH.exists():
        return None
    projection = json.loads(PASSPORT_PROJECTION_PATH.read_text(encoding="utf-8"))
    for passport in projection.get("passports", []):
        if isinstance(passport, dict) and passport.get("subject_ref") == SUBJECT_REF:
            return passport
    return None


def _passport_prohibited_claims(passport: dict[str, Any] | None) -> set[str]:
    if not passport:
        return set()
    return {
        claim
        for contract in passport.get("claim_contracts", [])
        for claim in contract.get("prohibited", [])
    }


def _observed_statuses(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("requested_evidence", {}).get("line_break_status"))
            for row in rows
            if isinstance(row.get("requested_evidence"), dict)
        }
    )


def verify_controlled_line_break_capability() -> dict[str, Any]:
    _registry, _runtime_manifest, lock, parity_report = generate_scp0_artifacts(write=write_mode())
    document_payload = controlled_line_break_probe_document()
    document = TacticalQueryDocument.model_validate(document_payload)
    bound_plan = bind_document(document)
    execution = TacticalQueryExecutor().execute(bound_plan)
    rows = execution_result_rows(execution)
    passport = _load_passport()
    prohibited_claims = _passport_prohibited_claims(passport)

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
                "message": "Controlled-line-break verifier must run through the generic executor.",
                "path": "execution.provenance.compatibility_profile",
            }
        )
    if not rows:
        findings.append(
            {
                "code": "no_real_pass_results",
                "message": "The controlled-line-break verifier produced no real PASS rows.",
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
    required_prohibitions = {
        "defensive_line_was_broken",
        "tactical_line_role_identified",
        "line_break_caused_by_pass",
        "player_intent_inferred",
    }
    missing_prohibitions = sorted(required_prohibitions - prohibited_claims)
    if missing_prohibitions:
        findings.append(
            {
                "code": "passport_missing_prohibited_claims",
                "message": f"Passport lacks prohibited claims: {', '.join(missing_prohibitions)}.",
                "path": "capability_passport_projection.passports.controlled_line_break_episode.claim_contracts",
            }
        )

    sample = rows[0] if rows else {}
    requested = sample.get("requested_evidence") if isinstance(sample, dict) else {}
    status = "PASS" if not findings else "FAIL"
    return {
        "schema_version": "1.0",
        "milestone": "AFL-08 controlled_line_break_episode",
        "status": status,
        "registry_lock": lock.model_dump(mode="json"),
        "plan": {
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "document_hash": stable_hash(document_payload),
        },
        "execution": {
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "compatibility_profile": execution.provenance.get("compatibility_profile"),
            "result_count": len(rows),
            "requested_evidence_failure_count": evidence_failure_count,
            "runtime_value_count": execution.provenance.get("runtime_value_count"),
            "runtime_trace_hash": execution.provenance.get("runtime_trace_hash"),
            "observed_line_break_statuses": _observed_statuses(rows),
        },
        "sample_result": {
            "result_id": sample.get("result_id"),
            "classification": sample.get("classification"),
            "requested_evidence": requested,
        },
        "passport": {
            "subject_ref": SUBJECT_REF,
            "passport_hash": None if not passport else passport.get("passport_hash"),
            "conformance": None if not passport else passport.get("binding", {}).get("conformance"),
            "prohibited_claims": sorted(prohibited_claims),
        },
        "checks": {
            "generic_execution": execution.provenance.get("compatibility_profile") == "generic",
            "real_pass_results": len(rows) > 0,
            "requested_evidence_complete": evidence_failure_count == 0,
            "overclaim_prohibited": required_prohibitions.issubset(prohibited_claims),
        },
        "findings": findings,
    }


def main() -> None:
    report = verify_controlled_line_break_capability()
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
