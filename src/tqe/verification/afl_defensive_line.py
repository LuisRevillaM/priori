"""AFL-08 defensive-line capability verifier.

This verifier proves the first line-library capability as a runtime capability,
not a product recipe. It compiles a minimal typed plan:

controlled_pass_episode -> defensive_line_model -> line_status == PASS

The proof intentionally claims only an observed geometric line. It must not
claim a tactical first/second line or line break.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash
from tqe.semantic_registry.generate import OUTPUT_ROOT, generate_scp0_artifacts


REPORT_PATH = Path("artifacts/autonomous/afl-defensive-line-verification-report.json")
PASSPORT_PROJECTION_PATH = OUTPUT_ROOT / "capability-passport-projection.json"
SUBJECT_REF = "runtime:primitive:defensive_line_model:0.1.0"


def defensive_line_probe_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "observed_defensive_line_probe",
            "recipe_version": "0.1.0",
            "display_name": "Observed Defensive Line Probe",
            "description": "Verification-only probe for observed geometric defensive line.",
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "An observed geometric defensive line was fit under declared thresholds.",
            ],
            "disallowed_claims": [
                "The capability does not identify a tactical line role.",
                "The capability does not prove a line break.",
                "The capability does not infer defender intent.",
            ],
            "limitations": [
                "Verification-only probe; not a registered user-facing recipe.",
            ],
            "output_classifications": ["OBSERVED_GEOMETRIC_DEFENSIVE_LINE"],
            "parameters": [
                {
                    "name": "goal_side_buffer_m",
                    "payload_type": "number",
                    "unit": "metre",
                    "required": False,
                    "default": {"payload_type": "number", "unit": "metre", "value": 1.0},
                    "description": "Minimum distance beyond the ball for a defender to count as goal-side.",
                },
                {
                    "name": "line_band_width_m",
                    "payload_type": "number",
                    "unit": "metre",
                    "required": False,
                    "default": {"payload_type": "number", "unit": "metre", "value": 2.0},
                    "description": "Maximum normalized x-span of defenders in one observed line band.",
                },
                {
                    "name": "minimum_line_defenders",
                    "payload_type": "number",
                    "unit": "count",
                    "required": False,
                    "default": {"payload_type": "number", "unit": "count", "value": 4},
                    "description": "Minimum defending outfield players required to form a line.",
                },
            ],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "observed_defensive_line_probe",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "observed_defensive_line_probe",
            "plan_version": "0.1.0",
            "recipe_id": "observed_defensive_line_probe",
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
                    "node_id": "defensive_line",
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
                    },
                },
                {
                    "kind": "predicate",
                    "node_id": "line_observed",
                    "input": {"source_node_id": "defensive_line", "output_name": "line_status"},
                    "operator": {"name": "eq", "version": "1.0.0"},
                    "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                },
            ],
            "classification_rules": [
                {
                    "label": "OBSERVED_GEOMETRIC_DEFENSIVE_LINE",
                    "predicate_ids": ["line_observed"],
                    "description": "Observed geometric defensive line exists at the anchor frame.",
                },
            ],
            "anchor_source": {
                "source_node_id": "defensive_line",
                "output_name": "anchor_evaluations",
            },
            "requested_evidence": [
                _evidence("line_status"),
                _evidence("line_reason"),
                _evidence("line_x_m"),
                _evidence("normalized_line_x_m"),
                _evidence("line_compactness_m"),
                _evidence("defensive_line_player_ids"),
                _evidence("defenders_goal_side_count"),
                _evidence("defender_positions_used"),
                _evidence("goal_side_buffer_m"),
                _evidence("line_band_width_m"),
                _evidence("minimum_line_defenders"),
            ],
        },
    }


def _evidence(field: str) -> dict[str, Any]:
    return {
        "source": {"source_node_id": "defensive_line", "output_name": "anchor_evaluations"},
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


def verify_defensive_line_capability() -> dict[str, Any]:
    # Refresh registry artifacts so the passport projection reflects the runtime catalog in this tree.
    _registry, _runtime_manifest, lock, parity_report = generate_scp0_artifacts(write=True)
    document_payload = defensive_line_probe_document()
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
                "message": "Defensive-line verifier must run through the generic executor.",
                "path": "execution.provenance.compatibility_profile",
            }
        )
    if not rows:
        findings.append(
            {
                "code": "no_real_results",
                "message": "The defensive-line verifier produced no real rows.",
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
        "tactical_line_role_identified",
        "defensive_line_was_broken",
        "defender_intent_inferred",
    }
    missing_prohibitions = sorted(required_prohibitions - prohibited_claims)
    if missing_prohibitions:
        findings.append(
            {
                "code": "passport_missing_prohibited_claims",
                "message": f"Passport lacks prohibited claims: {', '.join(missing_prohibitions)}.",
                "path": "capability_passport_projection.passports.defensive_line_model.claim_contracts",
            }
        )

    sample = rows[0] if rows else {}
    requested = sample.get("requested_evidence") if isinstance(sample, dict) else {}
    status = "PASS" if not findings else "FAIL"
    return {
        "schema_version": "1.0",
        "milestone": "AFL-08 defensive_line_model",
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
            "real_results": len(rows) > 0,
            "requested_evidence_complete": evidence_failure_count == 0,
            "line_break_overclaim_prohibited": "defensive_line_was_broken" in prohibited_claims,
        },
        "findings": findings,
    }


def main() -> None:
    report = verify_defensive_line_capability()
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
