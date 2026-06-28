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
            ("A corner variant is a set piece routine pattern used from the corner restart.", "scl1_set_piece_routine_status"),
        ]:
            contract, _ = generate_contract_from_meaning(text)
            self.assertIn(evidence, contract["required_evidence"])

    def test_cover_shadow_maps_to_observed_lane_geometry_not_intent(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "A cover shadow is a defended passing lane region hidden behind the pressing defender."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("cover_shadow_status", contract["required_evidence"])
        self.assertIn("passing_lane_denial_status", contract["required_evidence"])
        self.assertIn("screening_defender_id", contract["required_evidence"])
        self.assertIn("screening_defender_distance_to_lane_m", contract["required_evidence"])
        self.assertIn("cover_shadow_claim_boundary", contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in contract["status_semantics"]}["cover_shadow_status"],
            "PASS",
        )
        self.assertNotIn("scl1_cover_shadow_status", contract["required_evidence"])
        self.assertIn("meaning.cover_shadow.observed_lane_geometry", trace_rules)

    def test_passing_lane_denial_maps_to_cover_shadow_element(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Passing-lane denial means a defender blocks the passing lane between the ball and a potential receiver."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("cover_shadow_status", contract["required_evidence"])
        self.assertIn("passing_lane_denial_status", contract["required_evidence"])
        self.assertIn("screening_defender_projection_fraction", contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in contract["status_semantics"]}["passing_lane_denial_status"],
            "PASS",
        )
        self.assertIn("meaning.cover_shadow.observed_lane_geometry", trace_rules)

    def test_team_press_maps_to_observed_multi_defender_pressure(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Team press candidate means several defenders act as a collective press around the ball."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("team_press_status", contract["required_evidence"])
        self.assertIn("pressure_actor_ids", contract["required_evidence"])
        self.assertIn("pressure_actor_count", contract["required_evidence"])
        self.assertIn("pressure_angle_spread_degrees", contract["required_evidence"])
        self.assertIn("team_press_claim_boundary", contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in contract["status_semantics"]}["team_press_status"],
            "PASS",
        )
        self.assertNotIn("scl1_team_press_status", contract["required_evidence"])
        self.assertIn("meaning.team_press.observed_multi_defender_pressure", trace_rules)

    def test_pressing_trap_keeps_coordination_gap_on_top_of_team_press(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "A pressing trap is a team press structure intended to constrain the ball carrier."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("team_press_status", contract["required_evidence"])
        self.assertIn("scl1_pressing_trap_status", contract["required_evidence"])
        self.assertIn("meaning.team_press.observed_multi_defender_pressure", trace_rules)
        self.assertIn("meaning.missing_primitive.pressing_trap_or_coordination", trace_rules)

    def test_open_space_region_maps_to_observed_geometry_not_value(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Available space region means an observed free area of pitch available at the anchor under frozen distance thresholds."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("open_space_status", contract["required_evidence"])
        self.assertIn("representative_open_space_point", contract["required_evidence"])
        self.assertIn("space_region_model", contract["required_evidence"])
        self.assertIn("space_region_claim_boundary", contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in contract["status_semantics"] if "required_value" in item}["open_space_status"],
            "PASS",
        )
        self.assertNotIn("scl1_space_creation_status", contract["required_evidence"])
        self.assertIn("meaning.space.open_region", trace_rules)

    def test_space_creation_keeps_creation_gap_on_top_of_open_space(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Space creation candidate means an action creates a new open space region for a teammate."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("open_space_status", contract["required_evidence"])
        self.assertIn("scl1_space_creation_status", contract["required_evidence"])
        self.assertIn("meaning.space.open_region", trace_rules)
        self.assertIn("meaning.missing_primitive.space_creation", trace_rules)

    def test_marking_element_maps_to_observed_proximity_not_assignment(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "An unmarked player candidate asks whether a receiver is not closely marked by a defender."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("marking_status", contract["required_evidence"])
        self.assertIn("unmarked_status", contract["required_evidence"])
        self.assertIn("nearest_marker_distance_m", contract["required_evidence"])
        self.assertIn("marking_assignment_policy", contract["required_evidence"])
        self.assertIn("marking_claim_boundary", contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in contract["status_semantics"]}["unmarked_status"],
            "PASS",
        )
        self.assertNotIn("scl1_marking_assignment_status", contract["required_evidence"])
        self.assertIn("meaning.relation.marking_proximity", trace_rules)

    def test_marking_assignment_keeps_missing_assignment_gap_on_top_of_proximity(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Marking assignment means a defender is assigned as the marker of an attacking player."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("marking_status", contract["required_evidence"])
        self.assertIn("scl1_marking_assignment_status", contract["required_evidence"])
        self.assertIn("meaning.relation.marking_proximity", trace_rules)
        self.assertIn("meaning.missing_primitive.marking_assignment", trace_rules)

    def test_off_ball_run_element_maps_to_observed_movement_not_run_type(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "An off ball run episode identifies a player's observed run while they are away from the ball."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("off_ball_run_status", contract["required_evidence"])
        self.assertIn("run_player_id", contract["required_evidence"])
        self.assertIn("run_displacement_m", contract["required_evidence"])
        self.assertIn("run_start_ball_distance_m", contract["required_evidence"])
        self.assertIn("off_ball_run_claim_boundary", contract["required_evidence"])
        self.assertNotIn("scl1_off_ball_run_type_status", contract["required_evidence"])
        self.assertIn("meaning.movement.off_ball_run", trace_rules)

    def test_run_in_behind_maps_to_observed_path_type(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "A run in behind is an off-ball run into space behind the defensive line."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("off_ball_run_status", contract["required_evidence"])
        self.assertIn("run_in_behind_status", contract["required_evidence"])
        self.assertIn("off_ball_run_type_status", contract["required_evidence"])
        self.assertIn("off_ball_run_type_claim_boundary", contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in contract["status_semantics"] if "required_value" in item}["run_in_behind_status"],
            "PASS",
        )
        self.assertNotIn("scl1_off_ball_run_purpose_status", contract["required_evidence"])
        self.assertIn("meaning.movement.off_ball_run", trace_rules)
        self.assertIn("meaning.run_type.observed_path", trace_rules)

    def test_diagonal_run_maps_to_observed_path_type(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "A diagonal run is an off-ball run with both forward and lateral movement."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("off_ball_run_status", contract["required_evidence"])
        self.assertIn("diagonal_run_status", contract["required_evidence"])
        self.assertIn("run_forward_progression_m", contract["required_evidence"])
        self.assertIn("run_lateral_displacement_m", contract["required_evidence"])
        self.assertNotIn("carry_forward_progression_m", contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in contract["status_semantics"] if "required_value" in item}["diagonal_run_status"],
            "PASS",
        )
        self.assertIn("meaning.movement.off_ball_run", trace_rules)
        self.assertIn("meaning.run_type.observed_path", trace_rules)

    def test_decoy_run_keeps_purpose_gap_on_top_of_base_run(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "A decoy run is an off-ball run intended to drag a marker away."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("off_ball_run_status", contract["required_evidence"])
        self.assertIn("scl1_off_ball_run_purpose_status", contract["required_evidence"])
        self.assertNotIn("run_in_behind_status", contract["required_evidence"])
        self.assertNotIn("diagonal_run_status", contract["required_evidence"])
        self.assertIn("meaning.movement.off_ball_run", trace_rules)
        self.assertIn("meaning.missing_primitive.off_ball_run_purpose", trace_rules)

    def test_set_piece_structure_element_maps_to_observed_restart_shape_not_routine(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "Set-piece attacking shape means attackers have an observed set-piece arrangement at the restart frame."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("set_piece_structure_status", contract["required_evidence"])
        self.assertIn("set_piece_restart_type", contract["required_evidence"])
        self.assertIn("attacking_shape_width_m", contract["required_evidence"])
        self.assertIn("defending_shape_width_m", contract["required_evidence"])
        self.assertIn("structure_model", contract["required_evidence"])
        self.assertIn("coverage_status", contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in contract["status_semantics"]}["set_piece_structure_status"],
            "PASS",
        )
        self.assertIn("meaning.restart.set_piece_structure", trace_rules)
        self.assertNotIn("scl1_set_piece_routine_status", contract["required_evidence"])

    def test_set_piece_routine_language_keeps_missing_routine_gap(self) -> None:
        contract, traces = generate_contract_from_meaning(
            "A corner variant is a set piece routine pattern used from the corner restart."
        )
        trace_rules = {trace["rule_id"] for trace in traces}

        self.assertIn("set_piece_structure_status", contract["required_evidence"])
        self.assertIn("scl1_set_piece_routine_status", contract["required_evidence"])
        self.assertIn("meaning.restart.set_piece_structure", trace_rules)
        self.assertIn("meaning.missing_primitive.set_piece_routine", trace_rules)

    def test_acceleration_element_maps_speed_up_and_slow_down_to_directional_status(self) -> None:
        acceleration_contract, acceleration_traces = generate_contract_from_meaning(
            "A burst of acceleration is rapid speeding up across consecutive frames."
        )
        deceleration_contract, deceleration_traces = generate_contract_from_meaning(
            "Deceleration after receiving means the receiver slows down after the first touch."
        )

        self.assertIn("acceleration_status", acceleration_contract["required_evidence"])
        self.assertIn("deceleration_status", deceleration_contract["required_evidence"])
        self.assertIn("acceleration_model", acceleration_contract["required_evidence"])
        self.assertIn("noise_policy", acceleration_contract["required_evidence"])
        self.assertIn("tracking_quality_status", acceleration_contract["required_evidence"])
        self.assertEqual(
            {item["field"]: item["required_value"] for item in acceleration_contract["status_semantics"]}["acceleration_status"],
            "PASS",
        )
        self.assertEqual(
            {item["field"]: item["required_value"] for item in deceleration_contract["status_semantics"]}["deceleration_status"],
            "PASS",
        )
        self.assertEqual(
            {trace["rule_id"] for trace in acceleration_traces if trace["contract_path"] == "required_evidence.acceleration_status"},
            {"meaning.kinematics.acceleration"},
        )
        self.assertEqual(
            {trace["rule_id"] for trace in deceleration_traces if trace["contract_path"] == "required_evidence.deceleration_status"},
            {"meaning.kinematics.acceleration"},
        )


if __name__ == "__main__":
    unittest.main()
