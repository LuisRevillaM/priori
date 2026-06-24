"""AFL-09A minimal validation-factory verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.verification.afl_line_break_support_response import (
    verify_line_break_support_response,
)
from tqe.verification.afl_relative_position import verify_relative_position_capability
from tqe.verification.afl_validation_factory import (
    load_json,
    validate_proof_carrying_records,
)


REPORT_PATH = Path("artifacts/autonomous/afl-09a-validation-factory-report.json")
BRANCH_FIXTURE_PATH = Path("delivery/autonomous/afl09a/proof-carrying-branch-fixture.json")


def verify_afl_09a_validation_factory() -> dict[str, Any]:
    bootstrap_reports = [
        verify_line_break_support_response(),
        verify_relative_position_capability(),
    ]
    branch_fixture = load_json(BRANCH_FIXTURE_PATH)
    branch_check = validate_proof_carrying_records(branch_fixture.get("records", []))

    findings: list[dict[str, str]] = []
    for report in bootstrap_reports:
        factory = report.get("validation_factory") if isinstance(report, dict) else None
        milestone = str(report.get("milestone")) if isinstance(report, dict) else "unknown"
        if not isinstance(factory, dict):
            findings.append(
                {
                    "code": "missing_validation_factory_block",
                    "message": f"{milestone} did not emit a validation_factory block.",
                    "path": f"bootstrap_reports.{milestone}.validation_factory",
                }
            )
            continue
        if factory.get("status") != "PASS":
            findings.append(
                {
                    "code": "bootstrap_factory_gate_failed",
                    "message": f"{milestone} factory gate status was {factory.get('status')}.",
                    "path": f"bootstrap_reports.{milestone}.validation_factory.status",
                }
            )
        if factory.get("freeze_mode") is True:
            findings.append(
                {
                    "code": "verify_ran_in_freeze_mode",
                    "message": "AFL-09A verification must read-compare frozen expectations, not refresh them.",
                    "path": f"bootstrap_reports.{milestone}.validation_factory.freeze_mode",
                }
            )
        if factory.get("no_tautological_verification") is not True:
            findings.append(
                {
                    "code": "tautology_guard_not_asserted",
                    "message": "Factory did not assert no-tautological-verification in normal mode.",
                    "path": f"bootstrap_reports.{milestone}.validation_factory.no_tautological_verification",
                }
            )
        if factory.get("silent_refresh_blocked") is not True:
            findings.append(
                {
                    "code": "silent_refresh_guard_not_asserted",
                    "message": "Factory did not assert silent-refresh blocking in normal mode.",
                    "path": f"bootstrap_reports.{milestone}.validation_factory.silent_refresh_blocked",
                }
            )

    if branch_check.get("status") != "PASS":
        findings.extend(branch_check.get("findings", []))

    status = "PASS" if not findings else "FAIL"
    return {
        "schema_version": "afl09a.validation_factory_report.v1",
        "milestone": "AFL-09A minimal validation factory spine",
        "status": status,
        "scope": {
            "does": [
                "read-compare frozen expectations",
                "attach reusable proof gates to existing verifiers",
                "validate proof-carrying PASS/FAIL/UNKNOWN branch requirements on a frozen synthetic fixture",
                "regression-pin real-data result IDs, counts, plan hashes, evidence failures, and result signatures",
                "block silent refresh in normal verification mode",
            ],
            "does_not": [
                "generate semantic truth from fresh runtime outputs",
                "change runtime semantics",
                "add UI behavior",
                "implement One-Touch / Pass-Chain",
            ],
        },
        "bootstrap_targets": [
            _bootstrap_summary(report) for report in bootstrap_reports
        ],
        "branch_fixture": {
            "path": str(BRANCH_FIXTURE_PATH),
            "type": "frozen_synthetic_fixture",
            "status": branch_check.get("status"),
            "observed_judgements": branch_check.get("observed_judgements"),
            "claim": "Exercises branch discipline; does not claim real-row FAIL/UNKNOWN coverage.",
        },
        "checks": {
            "two_existing_verifiers_on_spine": len(bootstrap_reports) >= 2
            and all(
                isinstance(report.get("validation_factory"), dict)
                for report in bootstrap_reports
                if isinstance(report, dict)
            ),
            "no_tautological_verification": all(
                report.get("validation_factory", {}).get("no_tautological_verification") is True
                for report in bootstrap_reports
            ),
            "no_silent_refresh": all(
                report.get("validation_factory", {}).get("silent_refresh_blocked") is True
                for report in bootstrap_reports
            ),
            "synthetic_proof_carrying_branches_exercised": branch_check.get("status") == "PASS"
            and set(branch_check.get("observed_judgements", [])) == {"FAIL", "PASS", "UNKNOWN"},
            "real_rows_regression_pinned_not_branch_claimed": True,
        },
        "findings": findings,
    }


def _bootstrap_summary(report: dict[str, Any]) -> dict[str, Any]:
    factory = report.get("validation_factory", {})
    execution = report.get("execution", {})
    return {
        "milestone": report.get("milestone"),
        "report_status": report.get("status"),
        "execution_id": execution.get("execution_id"),
        "result_count": execution.get("result_count"),
        "factory_status": factory.get("status"),
        "expectation_path": factory.get("expectation_path"),
        "expectation_hash": factory.get("expectation_hash"),
        "compared_fields": factory.get("compared_fields"),
    }


def main() -> None:
    report = verify_afl_09a_validation_factory()
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
