"""N1D.1 attestation contract: the verifier must fail closed and never fabricate Hermes origin."""

import json
import unittest
from pathlib import Path

from tqe.verification import n1d1


class N1D1AttestationTests(unittest.TestCase):
    def test_verifier_fails_closed_and_does_not_fabricate_origin(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            n1d1.main()
        self.assertEqual(ctx.exception.code, 1, "N1D.1 must fail closed until a VERIFIED attestation exists")

        attestation = json.loads(n1d1.ATTESTATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(attestation["status"], "BLOCKED")
        self.assertNotEqual(attestation["status"], "VERIFIED")

        origin = attestation["hermes_origin"]
        if n1d1.N1F_ORIGIN_BUNDLE_PATH.exists():
            self.assertTrue(origin["trace_persisted"])
            self.assertIsNotNone(origin["ordered_tool_call_trace_sha256"])
            self.assertIsNotNone(origin["raw_hermes_decision_sha256"])
            self.assertIn("n1d1.augmentation_diff_allowed", attestation["blocking_reasons"])
        elif n1d1.N1E_ORIGIN_BUNDLE_PATH.exists():
            self.assertTrue(origin["trace_persisted"])
            self.assertIsNotNone(origin["ordered_tool_call_trace_sha256"])
            self.assertIsNotNone(origin["raw_hermes_decision_sha256"])
            self.assertIn("n1d1.origin_compile_tools_present", attestation["blocking_reasons"])
            self.assertIn("n1d1.augmentation_diff_allowed", attestation["blocking_reasons"])
        else:
            self.assertIn("n1d1.origin_trace_persisted", attestation["blocking_reasons"])
            # The missing raw decision and ordered tool-call trace are recorded as null, never invented.
            self.assertIsNone(origin["ordered_tool_call_trace_sha256"])
            self.assertIsNone(origin["raw_hermes_decision_sha256"])
            self.assertFalse(origin["trace_persisted"])

        # The Beta 1C unlock contract is published for later enforcement.
        contract = attestation["beta_1c_unlock_contract"]
        self.assertEqual(contract["required_status"], "VERIFIED")
        self.assertEqual(contract["required_provenance_source"], "HERMES_NOVEL_COMPOSITION")

    def test_structural_novelty_is_computable_and_plan_is_novel(self) -> None:
        if not n1d1.N1D_PLAN_PATH.exists():
            self.skipTest("N1D pinned plan not present")
        plan = json.loads(n1d1.N1D_PLAN_PATH.read_text(encoding="utf-8"))
        novelty = n1d1.attest_structural_novelty(plan)
        self.assertTrue(novelty["structurally_novel"])
        self.assertFalse(novelty["existing_recipe_selected"])

    def test_augmentation_diff_rejects_more_than_two_allowed_aliases(self) -> None:
        # A plan that adds anything beyond the two allowed aliases must be rejected by the diff rule.
        base = {"draft_plan": {"nodes": [], "requested_evidence": [{"alias": "a"}]}}
        augmented = {
            "draft_plan": {
                "nodes": [],
                "requested_evidence": [
                    {"alias": "a"},
                    {"alias": "destination_entry_mode"},
                    {"alias": "destination_time_to_entry_seconds"},
                    {"alias": "unexpected_extra"},
                ],
            }
        }
        added = sorted(n1d1.evidence_aliases(augmented) - n1d1.evidence_aliases(base))
        self.assertNotEqual(set(added), n1d1.ALLOWED_AUGMENTATION)


if __name__ == "__main__":
    unittest.main()
