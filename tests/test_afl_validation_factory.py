from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tqe.verification.afl_validation_factory import (
    FREEZE_ENV,
    ValidationFactorySpec,
    attach_validation_factory,
    validate_proof_carrying_records,
)


class ValidationFactoryTests(unittest.TestCase):
    def test_freeze_then_read_compare_and_fail_on_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expectation_path = Path(tmp) / "expectation.json"
            spec = ValidationFactorySpec(
                factory_id="test.factory",
                subject_ref="runtime:primitive:test:0.1.0",
                expectation_path=expectation_path,
                source_verifier="tests.test_afl_validation_factory",
                threshold_version="test.v1",
                required_check_keys=("generic_execution",),
            )
            report = _report()
            rows = [_row("result-a")]

            old_env = os.environ.get(FREEZE_ENV)
            os.environ[FREEZE_ENV] = "1"
            try:
                frozen = attach_validation_factory(report.copy(), rows=rows, spec=spec)
            finally:
                if old_env is None:
                    os.environ.pop(FREEZE_ENV, None)
                else:
                    os.environ[FREEZE_ENV] = old_env

            self.assertEqual(frozen["validation_factory"]["status"], "PASS")
            self.assertTrue(expectation_path.exists())
            frozen_payload = expectation_path.read_text(encoding="utf-8")

            compared = attach_validation_factory(_report(), rows=rows, spec=spec)
            self.assertEqual(compared["validation_factory"]["status"], "PASS")
            self.assertEqual(expectation_path.read_text(encoding="utf-8"), frozen_payload)

            drifted = attach_validation_factory(_report(), rows=[_row("result-b")], spec=spec)
            self.assertEqual(drifted["validation_factory"]["status"], "FAIL")
            self.assertIn("frozen_expectation_mismatch", _finding_codes(drifted))
            self.assertEqual(expectation_path.read_text(encoding="utf-8"), frozen_payload)

    def test_proof_carrying_branch_rules(self) -> None:
        result = validate_proof_carrying_records(
            [
                {"judgement": "PASS", "witnesses": [{"id": "w1"}]},
                {"judgement": "FAIL", "evaluation_domain_complete": True},
                {"judgement": "UNKNOWN", "unmet_premises": ["missing_frame"]},
            ]
        )
        self.assertEqual(result["status"], "PASS")

        bad = validate_proof_carrying_records(
            [
                {"judgement": "PASS", "witnesses": []},
                {"judgement": "FAIL", "evaluation_domain_complete": False},
                {"judgement": "UNKNOWN", "unmet_premises": []},
            ]
        )
        self.assertEqual(bad["status"], "FAIL")
        self.assertEqual(
            {
                "pass_missing_witness",
                "fail_domain_incomplete",
                "unknown_missing_unmet_premises",
            },
            set(_finding_codes(bad)),
        )


def _report() -> dict:
    return {
        "status": "PASS",
        "plan": {
            "plan_id": "test_plan",
            "bound_plan_hash": "bound_hash",
            "document_hash": "document_hash",
        },
        "execution": {
            "status": "pass",
            "compatibility_profile": "generic",
            "result_count": 1,
            "requested_evidence_failure_count": 0,
        },
        "checks": {"generic_execution": True},
        "findings": [],
    }


def _row(result_id: str) -> dict:
    return {
        "result_id": result_id,
        "classification": "TEST",
        "requested_evidence": {"status": "PASS", "witness": "frame_1"},
    }


def _finding_codes(report: dict) -> list[str]:
    findings = report.get("findings", [])
    if isinstance(findings, list):
        return [str(finding.get("code")) for finding in findings if isinstance(finding, dict)]
    return []


if __name__ == "__main__":
    unittest.main()
