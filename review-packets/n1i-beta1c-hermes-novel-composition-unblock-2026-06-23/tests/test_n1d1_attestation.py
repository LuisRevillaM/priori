"""N1D.1 attestation contract: the verifier must fail closed and never fabricate Hermes origin."""

import json
import unittest
from pathlib import Path

from tqe.verification import n1d1


class N1D1AttestationTests(unittest.TestCase):
    def test_verifier_uses_persisted_origin_and_does_not_fabricate(self) -> None:
        exit_code = 0
        try:
            n1d1.main()
        except SystemExit as exc:
            exit_code = int(exc.code or 0)
        attestation = json.loads(n1d1.ATTESTATION_PATH.read_text(encoding="utf-8"))

        origin = attestation["hermes_origin"]
        if n1d1.N1F_ORIGIN_BUNDLE_PATH.exists():
            self.assertEqual(exit_code, 0, "A complete N1F origin bundle should verify.")
            self.assertEqual(attestation["status"], "VERIFIED")
            self.assertTrue(origin["trace_persisted"])
            self.assertIsNotNone(origin["ordered_tool_call_trace_sha256"])
            self.assertIsNotNone(origin["raw_hermes_decision_sha256"])
            self.assertNotIn("n1d1.augmentation_diff_allowed", attestation["blocking_reasons"])
        elif n1d1.N1E_ORIGIN_BUNDLE_PATH.exists():
            self.assertEqual(exit_code, 1)
            self.assertEqual(attestation["status"], "BLOCKED")
            self.assertTrue(origin["trace_persisted"])
            self.assertIsNotNone(origin["ordered_tool_call_trace_sha256"])
            self.assertIsNotNone(origin["raw_hermes_decision_sha256"])
            self.assertIn("n1d1.origin_compile_tools_present", attestation["blocking_reasons"])
            self.assertIn("n1d1.augmentation_diff_allowed", attestation["blocking_reasons"])
        else:
            self.assertEqual(exit_code, 1)
            self.assertEqual(attestation["status"], "BLOCKED")
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

    def test_augmentation_diff_accepts_model_authored_required_aliases(self) -> None:
        document = {
            "draft_plan": {
                "nodes": [{"kind": "primitive", "node_id": "x", "catalog_ref": "possession_segment"}],
                "requested_evidence": [
                    {"alias": "a"},
                    {"alias": "destination_entry_mode"},
                    {"alias": "destination_time_to_entry_seconds"},
                ],
            }
        }
        diff = n1d1.audit_augmentation_diff(document, document)
        self.assertTrue(diff["diff_allowed"])
        self.assertEqual(diff["added_aliases"], [])
        self.assertTrue(diff["required_aliases_present"])
        self.assertEqual(set(diff["required_aliases_authored_by_hermes"]), n1d1.ALLOWED_AUGMENTATION)

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
        diff = n1d1.audit_augmentation_diff(augmented, base)
        self.assertFalse(diff["diff_allowed"])
        self.assertEqual(diff["added_aliases"], ["destination_entry_mode", "destination_time_to_entry_seconds", "unexpected_extra"])

    def test_augmentation_diff_rejects_missing_required_aliases(self) -> None:
        document = {"draft_plan": {"nodes": [], "requested_evidence": [{"alias": "a"}]}}
        diff = n1d1.audit_augmentation_diff(document, document)
        self.assertFalse(diff["diff_allowed"])
        self.assertFalse(diff["required_aliases_present"])


if __name__ == "__main__":
    unittest.main()
