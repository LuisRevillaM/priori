"""Minimal AFL-09A validation-factory spine.

The factory industrializes proof gates. It does not invent expected truth.
Normal verification is read-compare-only against frozen expectations. A
snapshot can be written only through the explicit AFL09A_FREEZE_EXPECTATIONS=1
environment variable, which keeps re-freeze deliberate and reviewable.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FREEZE_ENV = "AFL09A_FREEZE_EXPECTATIONS"


@dataclass(frozen=True)
class ValidationFactorySpec:
    factory_id: str
    subject_ref: str
    expectation_path: Path
    source_verifier: str
    threshold_version: str
    required_prohibited_claims: frozenset[str] = frozenset()
    required_check_keys: tuple[str, ...] = ()
    result_id_mode: str = "exact"
    require_tracked_expectation: bool = True


def attach_validation_factory(
    report: dict[str, Any],
    *,
    rows: list[dict[str, Any]],
    spec: ValidationFactorySpec,
) -> dict[str, Any]:
    """Attach AFL-09A proof gates to an existing verifier report."""

    actual = _actual_expectation(report, rows)
    findings: list[dict[str, str]] = []
    freeze_mode = os.environ.get(FREEZE_ENV) == "1"

    if freeze_mode:
        snapshot = _snapshot_payload(report, actual, spec)
        spec.expectation_path.parent.mkdir(parents=True, exist_ok=True)
        spec.expectation_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        comparison_status = "FROZEN"
        compared_fields: list[str] = []
    else:
        snapshot = _load_snapshot(spec.expectation_path)
        compared_fields = _compared_fields()
        findings.extend(_compare_snapshot(snapshot, actual, compared_fields))
        findings.extend(_validate_snapshot_provenance(snapshot, spec))
        findings.extend(_validate_expectation_file_state(spec))
        comparison_status = "PASS" if not findings else "FAIL"

    findings.extend(_validate_prohibited_claims(report, spec))
    findings.extend(_validate_required_checks(report, spec))

    gate_status = "PASS" if not findings else "FAIL"
    factory_block = {
        "schema_version": "afl09a.validation_factory.v1",
        "factory_id": spec.factory_id,
        "subject_ref": spec.subject_ref,
        "status": gate_status,
        "expectation_path": str(spec.expectation_path),
        "comparison_status": comparison_status,
        "freeze_mode": freeze_mode,
        "no_tautological_verification": not freeze_mode,
        "silent_refresh_blocked": not freeze_mode,
        "expectation_file_tracked": _path_tracked(spec.expectation_path),
        "expectation_file_unchanged": not _paths_dirty([str(spec.expectation_path)]),
        "compared_fields": compared_fields,
        "actual": actual,
        "expectation_hash": None
        if freeze_mode
        else _hash_json(_load_snapshot(spec.expectation_path)),
        "findings": findings,
    }
    report["validation_factory"] = factory_block
    if findings:
        report.setdefault("findings", []).extend(findings)
        report["status"] = "FAIL"
    return report


def validate_proof_carrying_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate PASS/FAIL/UNKNOWN branch requirements on proof-carrying records."""

    findings: list[dict[str, str]] = []
    seen_judgements: set[str] = set()
    for index, record in enumerate(records):
        judgement = str(record.get("judgement"))
        seen_judgements.add(judgement)
        path = f"records[{index}]"
        if judgement == "PASS":
            if not record.get("witnesses"):
                findings.append(
                    {
                        "code": "pass_missing_witness",
                        "message": "PASS records must carry at least one witness.",
                        "path": f"{path}.witnesses",
                    }
                )
        elif judgement == "FAIL":
            if record.get("evaluation_domain_complete") is not True:
                findings.append(
                    {
                        "code": "fail_domain_incomplete",
                        "message": "FAIL records require a complete evaluation domain.",
                        "path": f"{path}.evaluation_domain_complete",
                    }
                )
        elif judgement == "UNKNOWN":
            if not record.get("unmet_premises"):
                findings.append(
                    {
                        "code": "unknown_missing_unmet_premises",
                        "message": "UNKNOWN records must name unmet premises.",
                        "path": f"{path}.unmet_premises",
                    }
                )
        else:
            findings.append(
                {
                    "code": "unknown_judgement",
                    "message": f"Unsupported proof-carrying judgement: {judgement}.",
                    "path": f"{path}.judgement",
                }
            )

    required = {"PASS", "FAIL", "UNKNOWN"}
    missing = sorted(required - seen_judgements)
    if missing:
        findings.append(
            {
                "code": "branch_fixture_incomplete",
                "message": f"Fixture does not exercise branches: {', '.join(missing)}.",
                "path": "records",
            }
        )
    return {
        "schema_version": "afl09a.proof_carrying_branch_check.v1",
        "status": "PASS" if not findings else "FAIL",
        "observed_judgements": sorted(seen_judgements),
        "findings": findings,
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _actual_expectation(report: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    execution = report.get("execution", {})
    plan = report.get("plan", {})
    result_signatures = [_row_signature(row) for row in rows]
    return {
        "report_status": report.get("status"),
        "plan_id": plan.get("plan_id"),
        "bound_plan_hash": plan.get("bound_plan_hash"),
        "document_hash": plan.get("document_hash"),
        "execution_status": execution.get("status"),
        "compatibility_profile": execution.get("compatibility_profile"),
        "result_count": execution.get("result_count"),
        "result_ids": sorted(
            str(row.get("result_id")) for row in rows if row.get("result_id") is not None
        ),
        "requested_evidence_failure_count": execution.get("requested_evidence_failure_count"),
        "result_signature_hash": _hash_json(result_signatures),
    }


def _row_signature(row: dict[str, Any]) -> dict[str, Any]:
    requested = row.get("requested_evidence")
    if not isinstance(requested, dict):
        requested = {}
    return {
        "result_id": row.get("result_id"),
        "classification": row.get("classification"),
        "requested_evidence_hash": _hash_json(requested),
        "requested_evidence_aliases": sorted(str(key) for key in requested),
    }


def _snapshot_payload(
    report: dict[str, Any],
    actual: dict[str, Any],
    spec: ValidationFactorySpec,
) -> dict[str, Any]:
    return {
        "schema_version": "afl09a.frozen_expectation.v1",
        "expectation_id": spec.factory_id,
        "subject_ref": spec.subject_ref,
        "expected": actual,
        "freeze_provenance": {
            "source_commit": _git(["rev-parse", "HEAD"]),
            "worktree_dirty": _worktree_dirty(),
            "runtime_semantics_dirty": _paths_dirty(
                ["src/tqe/runtime", "semantic-registry", "config/query-plans"]
            ),
            "source_verifier": spec.source_verifier,
            "source_verifier_status": report.get("status"),
            "threshold_version": spec.threshold_version,
            "review": "controller_self_verified_original_real_data_verifier",
            "freeze_mechanism": f"explicit_{FREEZE_ENV}=1",
        },
    }


def _compared_fields() -> list[str]:
    return [
        "report_status",
        "plan_id",
        "bound_plan_hash",
        "document_hash",
        "execution_status",
        "compatibility_profile",
        "result_count",
        "result_ids",
        "requested_evidence_failure_count",
        "result_signature_hash",
    ]


def _compare_snapshot(
    snapshot: dict[str, Any],
    actual: dict[str, Any],
    fields: list[str],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected = snapshot.get("expected") if isinstance(snapshot, dict) else None
    if not isinstance(expected, dict):
        return [
            {
                "code": "expectation_snapshot_invalid",
                "message": "Frozen expectation snapshot has no expected object.",
                "path": "expected",
            }
        ]
    for field in fields:
        if expected.get(field) != actual.get(field):
            findings.append(
                {
                    "code": "frozen_expectation_mismatch",
                    "message": (
                        f"{field} drifted from frozen expectation "
                        f"{expected.get(field)!r} to {actual.get(field)!r}."
                    ),
                    "path": f"expected.{field}",
                }
            )
    return findings


def _validate_snapshot_provenance(
    snapshot: dict[str, Any], spec: ValidationFactorySpec
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    provenance = snapshot.get("freeze_provenance") if isinstance(snapshot, dict) else None
    if not isinstance(provenance, dict):
        return [
            {
                "code": "freeze_provenance_missing",
                "message": "Frozen expectation must carry freeze provenance.",
                "path": "freeze_provenance",
            }
        ]
    if provenance.get("source_verifier") != spec.source_verifier:
        findings.append(
            {
                "code": "source_verifier_mismatch",
                "message": "Frozen expectation provenance points to a different verifier.",
                "path": "freeze_provenance.source_verifier",
            }
        )
    if provenance.get("source_verifier_status") != "PASS":
        findings.append(
            {
                "code": "source_verifier_not_pass",
                "message": "Frozen expectation was not produced from a passing verifier.",
                "path": "freeze_provenance.source_verifier_status",
            }
        )
    if provenance.get("threshold_version") != spec.threshold_version:
        findings.append(
            {
                "code": "threshold_version_mismatch",
                "message": "Frozen expectation threshold version does not match the verifier spec.",
                "path": "freeze_provenance.threshold_version",
            }
        )
    if provenance.get("runtime_semantics_dirty") is True:
        findings.append(
            {
                "code": "runtime_semantics_dirty_at_freeze",
                "message": "Frozen expectation was created while runtime/query/registry semantics were dirty.",
                "path": "freeze_provenance.runtime_semantics_dirty",
            }
        )
    return findings


def _validate_expectation_file_state(spec: ValidationFactorySpec) -> list[dict[str, str]]:
    if not spec.require_tracked_expectation:
        return []
    findings: list[dict[str, str]] = []
    if not _path_tracked(spec.expectation_path):
        findings.append(
            {
                "code": "expectation_file_untracked",
                "message": "Frozen expectation must be a git-tracked artifact.",
                "path": str(spec.expectation_path),
            }
        )
    if _paths_dirty([str(spec.expectation_path)]):
        findings.append(
            {
                "code": "expectation_file_dirty",
                "message": "Frozen expectation must be unchanged during normal verification.",
                "path": str(spec.expectation_path),
            }
        )
    return findings


def _validate_prohibited_claims(
    report: dict[str, Any], spec: ValidationFactorySpec
) -> list[dict[str, str]]:
    if not spec.required_prohibited_claims:
        return []
    claims = set()
    passport = report.get("passport")
    if isinstance(passport, dict):
        claims.update(str(claim) for claim in passport.get("prohibited_claims", []))
    claim_boundary = report.get("claim_boundary")
    if isinstance(claim_boundary, dict):
        claims.update(str(claim) for claim in claim_boundary.get("dependency_prohibited_claims", []))
    missing = sorted(spec.required_prohibited_claims - claims)
    if not missing:
        return []
    return [
        {
            "code": "required_prohibited_claims_missing",
            "message": f"Missing prohibited claims: {', '.join(missing)}.",
            "path": "passport.prohibited_claims",
        }
    ]


def _validate_required_checks(
    report: dict[str, Any], spec: ValidationFactorySpec
) -> list[dict[str, str]]:
    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    findings: list[dict[str, str]] = []
    for key in spec.required_check_keys:
        if checks.get(key) is not True:
            findings.append(
                {
                    "code": "required_check_not_true",
                    "message": f"Required check {key} was not true.",
                    "path": f"checks.{key}",
                }
            )
    return findings


def _load_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "expected": None,
            "freeze_provenance": None,
            "_missing": str(path),
        }
    return load_json(path)


def _hash_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except Exception:
        return "UNKNOWN"


def _worktree_dirty() -> bool:
    try:
        subprocess.check_call(["git", "diff", "--quiet"])
        subprocess.check_call(["git", "diff", "--cached", "--quiet"])
        return False
    except Exception:
        return True


def _paths_dirty(paths: list[str]) -> bool:
    try:
        subprocess.check_call(
            ["git", "diff", "--quiet", "--", *paths],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["git", "diff", "--cached", "--quiet", "--", *paths],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return False
    except Exception:
        return True


def _path_tracked(path: Path) -> bool:
    try:
        subprocess.check_call(
            ["git", "ls-files", "--error-unmatch", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False
