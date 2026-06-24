from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tqe.verification import afl_gate


class AFLGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.candidate_dir = Path(cls._tmp.name) / "candidate"
        afl_gate.build_candidate_packet(cls.candidate_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_canaries_pass_in_local_mode(self) -> None:
        report = afl_gate.run_canaries(write=False)

        self.assertEqual("PASS", report["status"])
        self.assertEqual(
            {
                "known_good_contract_passes",
                "legacy_milestone_candidate_fails",
                "hard_gate_tampering_fails",
                "denominator_reduction_fails",
                "builder_cannot_claim_protected_authority",
                "deleted_hidden_suite_blocks_promotion",
            },
            {item["name"] for item in report["canaries"]},
        )

    def test_local_gate_result_blocks_protected_promotion(self) -> None:
        public = {"status": "PASS"}
        canary = {"status": "PASS"}

        with mock.patch.dict(os.environ, {}, clear=True):
            result = afl_gate.build_gate_result(self.candidate_dir, public, canary)

        self.assertEqual("BLOCKED", result["result"])
        categories = {item["category"] for item in result["findings"]}
        self.assertIn("not_running_under_protected_ci", categories)
        self.assertIn("protected_suite_hash_missing", categories)
        self.assertIn("signing_key_missing", categories)

    def test_protected_inputs_can_promote_when_all_required_inputs_exist(self) -> None:
        public = {"status": "PASS"}
        canary = {"status": "PASS"}
        env = {
            "AFL_GATE_PROTECTION_LEVEL": "PROTECTED_CI",
            "AFL_PROTECTED_SUITE_ID": "suite.example",
            "AFL_PROTECTED_SUITE_HASH": "abc123",
            "AFL_GATE_SIGNING_KEY": "secret",
        }

        with mock.patch.dict(os.environ, env, clear=True):
            result = afl_gate.build_gate_result(self.candidate_dir, public, canary)
            certificate = afl_gate.build_promotion_certificate(result)

        self.assertEqual("PROMOTED", result["result"])
        self.assertEqual([], result["findings"])
        self.assertEqual("SIGNED_HMAC_SHA256", certificate["signature_status"])
        self.assertRegex(certificate["promotion_signature"], r"^[0-9a-f]{64}$")

    def test_public_verification_failure_rejects_promotion_even_with_protected_inputs(self) -> None:
        public = {"status": "FAIL"}
        canary = {"status": "PASS"}
        env = {
            "AFL_GATE_PROTECTION_LEVEL": "PROTECTED_CI",
            "AFL_PROTECTED_SUITE_ID": "suite.example",
            "AFL_PROTECTED_SUITE_HASH": "abc123",
            "AFL_GATE_SIGNING_KEY": "secret",
        }

        with mock.patch.dict(os.environ, env, clear=True):
            result = afl_gate.build_gate_result(self.candidate_dir, public, canary)

        self.assertEqual("BLOCKED", result["result"])
        self.assertIn("public_tests_failed", {item["category"] for item in result["findings"]})

    def test_blocked_certificate_is_not_signed(self) -> None:
        result = {
            "milestone": "AFL-G0",
            "candidate_target": "SCP-0E.1",
            "candidate_commit": "abc",
            "contract_hash": "contract",
            "contract_schema_hash": "schema",
            "gate_runner_hash": "runner",
            "protected_suite_id": "UNAVAILABLE_SELF_VERIFIED",
            "protected_suite_hash": "UNAVAILABLE_SELF_VERIFIED",
            "denominators_hash": "denominators",
            "registry_lock": "registry",
            "source_tree_hash": "tree",
            "result": "BLOCKED",
        }

        with mock.patch.dict(os.environ, {"AFL_GATE_SIGNING_KEY": "secret"}, clear=True):
            certificate = afl_gate.build_promotion_certificate(result)

        self.assertIsNone(certificate["promotion_signature"])
        self.assertEqual("NOT_SIGNED_RESULT_NOT_PROMOTED", certificate["signature_status"])


if __name__ == "__main__":
    unittest.main()
