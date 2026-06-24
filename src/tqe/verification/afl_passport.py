"""AFL-08/AFL-09 generated capability passport verifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.ir import stable_hash
from tqe.semantic_registry.generate import (
    OUTPUT_ROOT,
    build_capability_passport_projection,
    build_projections,
    generate_scp0_artifacts,
    validate_capability_passport_projection,
)


REPORT_PATH = Path("artifacts/autonomous/afl-capability-passport-verification-report.json")
PASSPORT_PROJECTION_PATH = OUTPUT_ROOT / "capability-passport-projection.json"
TARGET_SUBJECTS = {
    "runtime:primitive:controlled_pass_episode:0.1.0",
    "runtime:primitive:defensive_line_model:0.1.0",
    "runtime:primitive:relative_position_to_line:0.1.0",
    "runtime:primitive:controlled_line_break_episode:0.1.0",
    "runtime:primitive:lane_occupancy:0.1.0",
    "runtime:relation:opponents_bypassed_by_action:0.1.0",
    "runtime:relation:support_arrival_relation:0.1.0",
}


def _load_passport_projection() -> dict[str, Any]:
    if not PASSPORT_PROJECTION_PATH.exists():
        return {}
    return json.loads(PASSPORT_PROJECTION_PATH.read_text(encoding="utf-8"))


def _passport_index(passport_projection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["subject_ref"]: item
        for item in passport_projection.get("passports", [])
        if isinstance(item, dict) and "subject_ref" in item
    }


def verify_capability_passports() -> dict[str, Any]:
    registry, runtime_manifest, lock, parity_report = generate_scp0_artifacts(write=True)
    projections = build_projections(registry, runtime_manifest, lock)
    generated_projection = build_capability_passport_projection(
        registry, runtime_manifest, lock, projections
    )
    stored_projection = _load_passport_projection()
    findings = [
        item.model_dump(mode="json")
        for item in validate_capability_passport_projection(
            stored_projection, registry, runtime_manifest, lock, projections
        )
    ]

    passport_index = _passport_index(stored_projection)
    missing_targets = sorted(TARGET_SUBJECTS - set(passport_index))
    for subject in missing_targets:
        findings.append(
            {
                "code": "afl_passport_target_missing",
                "message": f"Required first-package passport {subject} is missing.",
                "path": "capability_passport_projection.passports",
            }
        )

    target_checks: dict[str, Any] = {}
    for subject in sorted(TARGET_SUBJECTS):
        passport = passport_index.get(subject)
        if passport is None:
            continue
        claim_contracts = passport.get("claim_contracts", [])
        evidence_contracts = passport.get("evidence_contracts", [])
        prohibited_claims = {
            claim
            for contract in claim_contracts
            for claim in contract.get("prohibited", [])
        }
        replay_evidence = {
            item
            for contract in evidence_contracts
            for item in contract.get("replay_projection", [])
        }
        required_evidence = {
            item
            for contract in evidence_contracts
            for item in contract.get("required", [])
        }
        target_checks[subject] = {
            "passport_hash": passport.get("passport_hash"),
            "conformance": passport.get("binding", {}).get("conformance"),
            "projection_membership": passport.get("projection_membership", {}),
            "prohibited_claim_count": len(prohibited_claims),
            "required_evidence_count": len(required_evidence),
            "replay_projection_count": len(replay_evidence),
        }
        if not prohibited_claims:
            findings.append(
                {
                    "code": "afl_passport_missing_prohibited_claims",
                    "message": f"{subject} passport has no prohibited claims.",
                    "path": f"capability_passport_projection.passports.{subject}.claim_contracts",
                }
            )
        if not required_evidence:
            findings.append(
                {
                    "code": "afl_passport_missing_required_evidence",
                    "message": f"{subject} passport has no required evidence.",
                    "path": f"capability_passport_projection.passports.{subject}.evidence_contracts",
                }
            )
        if not replay_evidence:
            findings.append(
                {
                    "code": "afl_passport_missing_replay_projection",
                    "message": f"{subject} passport has no replay projection evidence.",
                    "path": f"capability_passport_projection.passports.{subject}.evidence_contracts",
                }
            )

    atlas_leakage = sum(
        1
        for subject in passport_index
        if subject.startswith("atlas.") or ":atlas." in subject
    )
    if atlas_leakage:
        findings.append(
            {
                "code": "afl_passport_atlas_leakage",
                "message": f"{atlas_leakage} atlas-only entries leaked into capability passports.",
                "path": "capability_passport_projection.passports",
            }
        )

    stored_hash = stable_hash(stored_projection) if stored_projection else None
    generated_hash = stable_hash(generated_projection)
    if stored_hash != generated_hash:
        findings.append(
            {
                "code": "afl_passport_stored_projection_drift",
                "message": "Stored capability passport projection differs from freshly generated projection.",
                "path": str(PASSPORT_PROJECTION_PATH),
            }
        )

    status = "PASS" if parity_report.status == "PASS" and not findings else "FAIL"
    return {
        "schema_version": "1.0",
        "milestone": "AFL-08/AFL-09",
        "status": status,
        "registry_lock": lock.model_dump(mode="json"),
        "passport_projection": {
            "path": str(PASSPORT_PROJECTION_PATH),
            "sha256": stored_hash,
            "passport_revision": stored_projection.get("passport_revision"),
            "passport_count": stored_projection.get("passport_count"),
            "target_subjects": sorted(TARGET_SUBJECTS),
            "target_checks": target_checks,
        },
        "checks": {
            "scp0_parity_status": parity_report.status,
            "generated_hash": generated_hash,
            "stored_hash": stored_hash,
            "atlas_passport_leakage": atlas_leakage,
        },
        "findings": findings,
        "advisory": [
            "This is a local self-verification gate, not protected AFL promotion.",
            "It proves generated passport projection integrity for current runtime capabilities; it does not close all 741 atlas dispositions.",
        ],
    }


def main() -> None:
    report = verify_capability_passports()
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
