import unittest

from scripts.coverage_map.semantic_contract_scl0 import (
    generate_contract_from_meaning,
    has_constraint_kind,
    stable_hash,
)


class Scl0SemanticContractTests(unittest.TestCase):
    def test_same_meaning_rewording_generates_stable_contract(self) -> None:
        first, _ = generate_contract_from_meaning(
            "A give-and-go is a two-pass combination where the first passer plays to a teammate "
            "and then receives the return pass back as the terminal receiver."
        )
        second, _ = generate_contract_from_meaning(
            "A wall-pass sequence has the ball leave the original passer, get relayed by a teammate, "
            "and come back to that same original passer."
        )

        self.assertEqual(stable_hash(first), stable_hash(second))
        self.assertTrue(has_constraint_kind(first, "same_player_return"))

    def test_changed_meaning_removes_identity_return_constraint(self) -> None:
        base, _ = generate_contract_from_meaning(
            "A give-and-go is a two-pass combination where the first passer plays to a teammate "
            "and then receives the return pass back as the terminal receiver."
        )
        changed, _ = generate_contract_from_meaning(
            "A two-pass sequence where the first passer plays to a teammate and the teammate "
            "continues the ball onward to a different terminal receiver."
        )

        self.assertNotEqual(stable_hash(base), stable_hash(changed))
        self.assertTrue(has_constraint_kind(base, "same_player_return"))
        self.assertFalse(has_constraint_kind(changed, "same_player_return"))

    def test_substring_does_not_trigger_body_orientation_modality(self) -> None:
        contract, _ = generate_contract_from_meaning(
            "A player carries the ball from pressure into less pressure when the pressure distance "
            "improves between carry start and carry end."
        )

        self.assertNotIn("body_orientation", contract.get("required_modalities", []))


if __name__ == "__main__":
    unittest.main()
