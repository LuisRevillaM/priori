"""AFL-08 lane-occupancy capability verifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import OUTPUT_ROOT, generate_scp0_artifacts


REPORT_PATH = Path("artifacts/autonomous/afl-lane-occupancy-verification-report.json")
PASSPORT_PROJECTION_PATH = OUTPUT_ROOT / "capability-passport-projection.json"
SUBJECT_REF = "runtime:primitive:lane_occupancy:0.1.0"


REQUIRED_EVIDENCE_FIELDS = [
    "anchor_id",
    "anchor_frame_id",
    "lane_occupancy_status",
    "lane_occupancy_reason",
    "lane_evaluation_frame_id",
    "lane_player_scope",
    "occupied_lanes",
    "occupied_lane_count",
    "lane_counts",
    "player_lane_assignments",
    "required_occupied_lane_count",
    "coverage_status",
    "lane_definitions",
]


def lane_occupancy_probe_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "lane_occupancy_probe",
            "recipe_version": "0.1.0",
            "display_name": "Lane Occupancy Probe",
            "description": "Verification-only probe for observed outfield lane occupancy.",
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "Observed outfield players occupied at least the declared number of lateral lanes.",
            ],
            "disallowed_claims": [
                "The capability does not prove complete active-player lane coverage.",
                "The capability does not infer player intent, support quality, or optimality.",
            ],
            "limitations": [
                "Verification-only probe; not a registered user-facing recipe.",
            ],
            "output_classifications": ["OBSERVED_LANE_OCCUPANCY"],
            "parameters": [
                {
                    "name": "required_occupied_lane_count",
                    "payload_type": "number",
                    "unit": "count",
                    "required": False,
                    "default": {"payload_type": "number", "unit": "count", "value": 3},
                    "description": "Minimum number of observed lanes with at least one selected player.",
                }
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "lane_occupancy_probe",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "lane_occupancy_probe",
            "plan_version": "0.1.0",
            "recipe_id": "lane_occupancy_probe",
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
                    "node_id": "lane_occupancy",
                    "catalog_ref": "lane_occupancy",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {
                            "source_node_id": "controlled_pass",
                            "output_name": "anchors",
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
                    "kind": "predicate",
                    "node_id": "lane_occupancy_pass",
                    "input": {
                        "source_node_id": "lane_occupancy",
                        "output_name": "lane_occupancy_status",
                    },
                    "operator": {"name": "eq", "version": "1.0.0"},
                    "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                },
            ],
            "classification_rules": [
                {
                    "label": "OBSERVED_LANE_OCCUPANCY",
                    "predicate_ids": ["lane_occupancy_pass"],
                    "description": "Observed outfield players occupied enough declared lanes.",
                },
            ],
            "anchor_source": {
                "source_node_id": "lane_occupancy",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": [_evidence(field) for field in REQUIRED_EVIDENCE_FIELDS],
        },
    }


def _evidence(field: str) -> dict[str, Any]:
    return {
        "source": {
            "source_node_id": "lane_occupancy",
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
            str(row.get("requested_evidence", {}).get("lane_occupancy_status"))
            for row in rows
            if isinstance(row.get("requested_evidence"), dict)
        }
    )


def verify_lane_occupancy_capability() -> dict[str, Any]:
    _registry, _runtime_manifest, lock, parity_report = generate_scp0_artifacts(write=True)
    document_payload = lane_occupancy_probe_document()
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
                "message": "Lane-occupancy verifier must run through the generic executor.",
                "path": "execution.provenance.compatibility_profile",
            }
        )
    if not rows:
        findings.append(
            {
                "code": "no_real_pass_results",
                "message": "The lane-occupancy verifier produced no real PASS rows.",
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
        "complete_active_player_lane_coverage_proven",
        "player_intent_inferred",
        "support_quality_inferred",
        "pass_was_optimal",
    }
    missing_prohibitions = sorted(required_prohibitions - prohibited_claims)
    if missing_prohibitions:
        findings.append(
            {
                "code": "passport_missing_prohibited_claims",
                "message": f"Passport lacks prohibited claims: {', '.join(missing_prohibitions)}.",
                "path": "capability_passport_projection.passports.lane_occupancy.claim_contracts",
            }
        )

    sample = rows[0] if rows else {}
    requested = sample.get("requested_evidence") if isinstance(sample, dict) else {}
    status = "PASS" if not findings else "FAIL"
    return {
        "schema_version": "1.0",
        "milestone": "AFL-08 lane_occupancy",
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
            "observed_lane_occupancy_statuses": _observed_statuses(rows),
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
    report = verify_lane_occupancy_capability()
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
