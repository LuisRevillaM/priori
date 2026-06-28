import unittest

from scripts.coverage_map.semantic_contract_scl0 import generate_contract_from_meaning, has_constraint_kind, stable_hash
from scripts.coverage_map.semantic_nl_interpreter_scl0 import (
    CLARIFICATION_REQUIRED,
    MEANING_DEFINITION,
    interpret_request,
)


class SclNl0Tests(unittest.TestCase):
    def test_cross_phrasing_stable_for_return_combination(self) -> None:
        first = interpret_request("show me give-and-gos")
        second = interpret_request("find wall passes")

        self.assertEqual(MEANING_DEFINITION, first.status)
        self.assertEqual(first.as_dict()["meaning_hash"], second.as_dict()["meaning_hash"])
        first_contract, _ = generate_contract_from_meaning(first.meaning_definition or "")
        second_contract, _ = generate_contract_from_meaning(second.meaning_definition or "")
        self.assertEqual(stable_hash(first_contract), stable_hash(second_contract))
        self.assertTrue(has_constraint_kind(first_contract, "same_player_return"))

    def test_vocabulary_invariance_keeps_nl_meaning_stable(self) -> None:
        baseline = interpret_request("show me give-and-gos")
        disabled = interpret_request(
            "show me give-and-gos",
            disabled_downstream_elements=["meaning.constraint.same_player_return"],
        )

        self.assertEqual(baseline.as_dict()["meaning_hash"], disabled.as_dict()["meaning_hash"])

    def test_changed_meaning_changes_contract(self) -> None:
        base = interpret_request("show me give-and-gos")
        changed = interpret_request(
            "show two-pass combinations where the second player sends it onward to a different receiver"
        )
        base_contract, _ = generate_contract_from_meaning(base.meaning_definition or "")
        changed_contract, _ = generate_contract_from_meaning(changed.meaning_definition or "")

        self.assertNotEqual(base.as_dict()["meaning_hash"], changed.as_dict()["meaning_hash"])
        self.assertTrue(has_constraint_kind(base_contract, "same_player_return"))
        self.assertFalse(has_constraint_kind(changed_contract, "same_player_return"))

    def test_line_break_without_support_cross_phrasing_is_stable(self) -> None:
        first = interpret_request("show line breaks with no underneath outlet")
        second = interpret_request("find moments where the receiver breaks the second line without support")

        self.assertEqual(MEANING_DEFINITION, first.status)
        self.assertEqual(MEANING_DEFINITION, second.status)
        self.assertEqual(first.as_dict()["meaning_hash"], second.as_dict()["meaning_hash"])
        contract, _ = generate_contract_from_meaning(first.meaning_definition or "")
        self.assertTrue(has_constraint_kind(contract, "relation_on_anchor"))

    def test_ambiguous_request_requires_clarification(self) -> None:
        output = interpret_request("show me dangerous attacks")

        self.assertEqual(CLARIFICATION_REQUIRED, output.status)
        self.assertIn("TACTICAL_MEANING_UNDERSPECIFIED", output.clarification_codes)
        self.assertTrue(output.clarification_questions)

    def test_known_negative_meaning_becomes_modality_gap(self) -> None:
        output = interpret_request("show expected pass completion")
        contract, _ = generate_contract_from_meaning(output.meaning_definition or "")

        self.assertEqual(MEANING_DEFINITION, output.status)
        self.assertIn("learned_model", contract.get("required_modalities", []))

    def test_understood_but_not_expressible_gets_unresolved_contract(self) -> None:
        output = interpret_request("show blindside rotations")
        contract, _ = generate_contract_from_meaning(output.meaning_definition or "")

        self.assertEqual(MEANING_DEFINITION, output.status)
        self.assertIn("scl0_unresolved_meaning_status", contract.get("required_evidence", []))


if __name__ == "__main__":
    unittest.main()
