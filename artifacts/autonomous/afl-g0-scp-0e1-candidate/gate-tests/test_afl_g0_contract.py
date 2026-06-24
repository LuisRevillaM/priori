from __future__ import annotations

import copy
import unittest

from tqe.verification.afl_g0 import load_contract, run, validate_contract


def finding_codes(report_or_findings) -> set[str]:
    if isinstance(report_or_findings, dict):
        return {item["code"] for item in report_or_findings["findings"]}
    return {item.code for item in report_or_findings}


class AFLG0ContractTests(unittest.TestCase):
    def test_operational_contract_passes(self) -> None:
        report = run(write=False)

        self.assertEqual("PASS", report["status"])
        self.assertEqual("SELF_VERIFIED", report["protection_level"])
        self.assertEqual(13, report["milestone_count"])

    def test_legacy_milestone_ids_fail(self) -> None:
        contract = load_contract()
        contract["milestones"][0]["id"] = "M0"

        codes = finding_codes(validate_contract(contract))

        self.assertIn("legacy_or_invalid_milestone_id", codes)
        self.assertIn("legacy_milestone_id", codes)

    def test_unknown_or_cyclic_dependencies_fail(self) -> None:
        contract = load_contract()
        contract["milestones"][2]["depends_on"] = ["AFL-99"]
        contract["milestones"][0]["depends_on"] = ["AFL-01"]

        codes = finding_codes(validate_contract(contract))

        self.assertIn("unknown_milestone_dependency", codes)
        self.assertIn("milestone_dependency_cycle", codes)

    def test_quantitative_targets_require_denominator_and_split(self) -> None:
        contract = load_contract()
        target = contract["milestones"][1]["quantitative_targets"][0]
        del target["denominator"]
        del target["evaluation_split"]

        codes = finding_codes(validate_contract(contract))

        self.assertIn("quantitative_target_missing_field", codes)

    def test_hard_gates_cannot_be_waived_or_reclassified(self) -> None:
        contract = load_contract()
        gate = contract["global_hard_gates"][0]
        gate["waivable"] = True
        gate["target_class"] = "BOOTSTRAP_TARGET"

        codes = finding_codes(validate_contract(contract))

        self.assertIn("hard_gate_waivable", codes)
        self.assertIn("hard_gate_wrong_target_class", codes)

    def test_builder_cannot_own_protected_fields(self) -> None:
        contract = load_contract()
        contract["authority"]["builder_may_modify"].append("trusted_gate")

        codes = finding_codes(validate_contract(contract))

        self.assertIn("authority_overlap", codes)

    def test_north_star_staged_targets_cannot_disappear(self) -> None:
        contract = load_contract()
        del contract["staged_targets"]["generated_valid_semantic_programs"]

        codes = finding_codes(validate_contract(contract))

        self.assertIn("missing_staged_targets", codes)

    def test_review_packet_requirements_cannot_disappear(self) -> None:
        contract = load_contract()
        contract["review_packet"]["required"].remove("gate-result.json")

        codes = finding_codes(validate_contract(contract))

        self.assertIn("review_packet_missing_required_artifacts", codes)

    def test_validation_does_not_mutate_contract(self) -> None:
        contract = load_contract()
        baseline = copy.deepcopy(contract)

        validate_contract(contract)

        self.assertEqual(baseline, contract)


if __name__ == "__main__":
    unittest.main()
