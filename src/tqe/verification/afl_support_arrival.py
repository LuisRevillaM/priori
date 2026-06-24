"""AFL-08 support-arrival capability verifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import OUTPUT_ROOT, generate_scp0_artifacts


REPORT_PATH = Path("artifacts/autonomous/afl-support-arrival-verification-report.json")
PASSPORT_PROJECTION_PATH = OUTPUT_ROOT / "capability-passport-projection.json"
SUBJECT_REF = "runtime:relation:support_arrival_relation:0.1.0"


REQUIRED_EVIDENCE_FIELDS = [
    "anchor_id",
    "anchor_frame_id",
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
    "candidate_player_ids",
    "evaluated_candidate_player_ids",
    "supporting_player_ids",
    "coverage_status",
    "reference_point",
]


def support_arrival_probe_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "support_arrival_probe",
            "recipe_version": "0.1.0",
            "display_name": "Support Arrival Probe",
            "description": "Verification-only probe for observed geometric support arrival.",
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "Observed candidate teammates entered a declared support region around the reference point.",
            ],
            "disallowed_claims": [
                "The capability does not infer player intent, support quality, or communication.",
                "The capability does not prove the pass was optimal or caused the support arrival.",
            ],
            "limitations": [
                "Verification-only probe; not a registered user-facing recipe.",
            ],
            "output_classifications": ["OBSERVED_SUPPORT_ARRIVAL"],
            "parameters": [
                _number_param(
                    "maximum_arrival_seconds",
                    "second",
                    2.0,
                    "Latest arrival after the controlled-reception anchor.",
                ),
                _number_param(
                    "minimum_duration_seconds",
                    "second",
                    0.4,
                    "Minimum continuous observed duration inside the support region.",
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
                    "Minimum number of observed support players required.",
                ),
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "support_arrival_probe",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "support_arrival_probe",
            "plan_version": "0.1.0",
            "recipe_id": "support_arrival_probe",
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
                    "kind": "relation",
                    "node_id": "support_arrival",
                    "catalog_ref": "support_arrival_relation",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {
                            "source_node_id": "controlled_pass",
                            "output_name": "anchors",
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
                    "kind": "predicate",
                    "node_id": "support_arrival_pass",
                    "input": {
                        "source_node_id": "support_arrival",
                        "output_name": "support_arrival_status",
                    },
                    "operator": {"name": "eq", "version": "1.0.0"},
                    "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                },
            ],
            "classification_rules": [
                {
                    "label": "OBSERVED_SUPPORT_ARRIVAL",
                    "predicate_ids": ["support_arrival_pass"],
                    "description": "Observed teammate support arrived inside the declared region and time window.",
                },
            ],
            "anchor_source": {
                "source_node_id": "support_arrival",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": [_evidence(field) for field in REQUIRED_EVIDENCE_FIELDS],
        },
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


def _evidence(field: str) -> dict[str, Any]:
    return {
        "source": {
            "source_node_id": "support_arrival",
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
            str(row.get("requested_evidence", {}).get("support_arrival_status"))
            for row in rows
            if isinstance(row.get("requested_evidence"), dict)
        }
    )


def verify_support_arrival_capability() -> dict[str, Any]:
    _registry, _runtime_manifest, lock, parity_report = generate_scp0_artifacts(write=True)
    document_payload = support_arrival_probe_document()
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
                "message": "Support-arrival verifier must run through the generic executor.",
                "path": "execution.provenance.compatibility_profile",
            }
        )
    if not rows:
        findings.append(
            {
                "code": "no_real_pass_results",
                "message": "The support-arrival verifier produced no real PASS rows.",
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
        "player_intent_inferred",
        "support_quality_inferred",
        "communication_inferred",
        "pass_was_optimal",
        "pass_probability_inferred",
    }
    missing_prohibitions = sorted(required_prohibitions - prohibited_claims)
    if missing_prohibitions:
        findings.append(
            {
                "code": "passport_missing_prohibited_claims",
                "message": f"Passport lacks prohibited claims: {', '.join(missing_prohibitions)}.",
                "path": "capability_passport_projection.passports.support_arrival_relation.claim_contracts",
            }
        )

    sample = rows[0] if rows else {}
    requested = sample.get("requested_evidence") if isinstance(sample, dict) else {}
    status = "PASS" if not findings else "FAIL"
    return {
        "schema_version": "1.0",
        "milestone": "AFL-08 support_arrival_relation",
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
            "observed_support_arrival_statuses": _observed_statuses(rows),
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
    report = verify_support_arrival_capability()
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
