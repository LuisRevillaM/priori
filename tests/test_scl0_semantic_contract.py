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

    def test_novel_element_combination_builds_from_parts(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "A carry under defender pressure that also progresses forward."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("carry_status", contract["required_evidence"])
        self.assertIn("pressure_status", contract["required_evidence"])
        self.assertIn("carry_forward_progression_m", contract["required_evidence"])
        self.assertIn("join_status", contract["required_evidence"])
        self.assertIn("meaning.element.carry", trace_rules)
        self.assertIn("meaning.pressure.observed_components", trace_rules)
        self.assertIn("meaning.element.forward_progression", trace_rules)
        self.assertIn("meaning.composition.same_anchor_episode_join", trace_rules)

    def test_reachability_element_is_traceable(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Defender arrival time means an observed defender can arrive at the target point "
            "within the declared arrival window."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("time_to_arrival_status", contract["required_evidence"])
        self.assertIn("reachable_verdict_bias", contract["required_evidence"])
        self.assertIn("meaning.reachability.time_to_arrival", trace_rules)

    def test_lane_element_stays_at_classification_claim(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Lane classification means observed outfield players are classified into lateral lanes at the anchor."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("lane_occupancy_status", contract["required_evidence"])
        self.assertIn("occupied_lane_count", contract["required_evidence"])
        self.assertNotIn("gte", {str(item.get("operator")) for item in contract["status_semantics"]})
        self.assertIn("meaning.element.lane_occupancy", trace_rules)

    def test_lane_reachability_combination_uses_generic_join(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Covered lane reachability means observed outfield players occupy at least one lateral lane "
            "and observed defenders can arrive within the arrival window at the same anchor."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("lane_occupancy_status", contract["required_evidence"])
        self.assertIn("time_to_arrival_status", contract["required_evidence"])
        self.assertIn("join_status", contract["required_evidence"])
        self.assertTrue(has_constraint_kind(contract, "same_anchor_identity"))
        self.assertIn("meaning.composition.lane_reachability_same_anchor", trace_rules)

    def test_missing_substrate_elements_gap_without_substitutes(self) -> None:
        for text, evidence in [
            ("A cover shadow is a defended passing lane region hidden behind the pressing defender.", "scl1_cover_shadow_status"),
            ("A marker relation identifies which defender is marking a particular attacker.", "scl1_marking_status"),
            ("Off ball run typing identifies a player's run while they are away from the ball.", "scl1_off_ball_run_status"),
            ("A burst of acceleration is rapid speeding up across consecutive frames.", "scl1_acceleration_status"),
            ("A corner variant is a set piece routine pattern used from the corner restart.", "scl1_set_piece_structure_status"),
            ("A team press is a collective defensive pressing structure rather than one nearest defender.", "scl1_team_press_status"),
            ("A free space region is an open space area produced by the current player positions.", "scl1_space_region_generation_status"),
        ]:
            contract, _ = generate_contract_from_meaning(text)
            self.assertEqual(contract["required_evidence"], [evidence])


if __name__ == "__main__":
    unittest.main()
