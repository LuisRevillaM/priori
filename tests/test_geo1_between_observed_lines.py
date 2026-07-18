from __future__ import annotations

import unittest

from tqe.runtime.between_observed_lines import (
    ENTITY_RELATIVE_BRACKETING,
    BetweenObservedLinesConfig,
    evaluate_between_observed_lines,
)
from tqe.runtime.capabilities import (
    PRIMITIVE_IMPLEMENTATION_NAMES,
    RELOCATED_IMPLEMENTATION_MODULES,
)
from tqe.runtime.capabilities.pass_family import (
    controlled_pass_evaluations_for_team_scope,
)
from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import FieldReferenceKind, PayloadType


def observed_line(rank: int, normalized_x_m: float, direction: int = 1) -> dict[str, object]:
    return {
        "line_rank": rank,
        "line_id": f"observed-line-{rank}",
        "line_x_m": normalized_x_m / direction,
        "normalized_line_x_m": normalized_x_m,
        "defender_ids": [f"d{rank}a", f"d{rank}b", f"d{rank}c"],
        "defender_count": 3,
    }


def line_evidence(
    *,
    direction: int = 1,
    status: str = "PASS",
    defender_observation_status: str = "ADEQUATE",
    coverage_status: str = "CERTIFIED",
    lines: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "anchor_id": "a-10",
        "line_evaluation_frame_id": 10,
        "multi_line_status": status,
        "multi_line_reason": (
            "target_line_rank_observed"
            if status == "PASS"
            else "target_line_rank_not_observed"
        ),
        "defender_observation_status": defender_observation_status,
        "defender_observation_reason": (
            "defender_observation_adequate"
            if defender_observation_status == "ADEQUATE"
            else "insufficient_observed_outfield_defenders"
        ),
        "player_track_coverage_status": coverage_status,
        "player_track_coverage_reason": "coverage-certified",
        "player_track_coverage_row_ids": ["TST:firstHalf:player_track"],
        "attacking_direction": direction,
        "observed_lines": lines
        if lines is not None
        else [observed_line(1, 5.0, direction), observed_line(2, 10.0, direction)],
    }


def evaluate(
    x_m: float,
    *,
    evidence: dict[str, object] | None = None,
    frame_id: int = 10,
    config: BetweenObservedLinesConfig = BetweenObservedLinesConfig(),
):
    return evaluate_between_observed_lines(
        entity_position=(x_m, 2.0),
        entity_id="receiver-9",
        entity_frame_id=frame_id,
        line_evaluation=evidence or line_evidence(),
        config=config,
    )


class BetweenObservedLinesGeometryTests(unittest.TestCase):
    def test_entity_relative_selector_chooses_unique_adjacent_bracketing_pair(self) -> None:
        result = evaluate(
            5.0,
            evidence=line_evidence(lines=[observed_line(1, -8.0), observed_line(2, 0.0), observed_line(3, 12.0)]),
            config=BetweenObservedLinesConfig(line_selector=ENTITY_RELATIVE_BRACKETING),
        )
        self.assertEqual("PASS", result.status)
        self.assertEqual(2, result.selected_nearer_line_rank)
        self.assertEqual(3, result.selected_farther_line_rank)
        self.assertEqual("between_observed_lines.v2", result.definition_version)

    def test_entity_relative_selector_preserves_boundary_unknown(self) -> None:
        result = evaluate(
            0.25,
            evidence=line_evidence(lines=[observed_line(1, 0.0), observed_line(2, 10.0)]),
            config=BetweenObservedLinesConfig(
                line_selector=ENTITY_RELATIVE_BRACKETING,
                line_boundary_buffer_m=0.5,
            ),
        )
        self.assertEqual("UNKNOWN", result.status)
        self.assertEqual("entity_within_line_boundary_buffer", result.reason)

    def test_strict_signed_geometry_passes_in_both_attacking_directions(self) -> None:
        forward = evaluate(7.0)
        mirrored = evaluate(-7.0, evidence=line_evidence(direction=-1))

        for result in (forward, mirrored):
            self.assertEqual("PASS", result.status)
            self.assertEqual("entity_between_observed_lines", result.reason)
            self.assertEqual(2.0, result.signed_distance_to_nearer_line_m)
            self.assertEqual(-3.0, result.signed_distance_to_farther_line_m)
            self.assertEqual(5.0, result.interline_gap_m)
            self.assertEqual(["d1a", "d1b", "d1c"], result.selected_nearer_line["defender_ids"])

    def test_adequately_observed_outside_is_fail(self) -> None:
        result = evaluate(3.0)

        self.assertEqual("FAIL", result.status)
        self.assertEqual("entity_outside_observed_lines", result.reason)
        self.assertLess(result.signed_distance_to_nearer_line_m, 0.0)

    def test_closed_boundary_buffer_is_unknown_at_both_lines(self) -> None:
        near_boundary = evaluate(5.5)
        far_boundary = evaluate(9.5)

        self.assertEqual("UNKNOWN", near_boundary.status)
        self.assertEqual("entity_within_line_boundary_buffer", near_boundary.reason)
        self.assertEqual("UNKNOWN", far_boundary.status)
        self.assertEqual("entity_within_line_boundary_buffer", far_boundary.reason)

    def test_deepest_selector_uses_unique_maximum_normalized_line(self) -> None:
        evidence = line_evidence(
            lines=[
                observed_line(1, 5.0),
                observed_line(2, 10.0),
                observed_line(3, 15.0),
            ]
        )
        result = evaluate(
            12.0,
            evidence=evidence,
            config=BetweenObservedLinesConfig(line_selector="deepest_observed_line"),
        )

        self.assertEqual("PASS", result.status)
        self.assertEqual(1, result.selected_nearer_line_rank)
        self.assertEqual(3, result.selected_farther_line_rank)
        self.assertEqual("observed-line-3", result.selected_farther_line["line_id"])
        self.assertEqual(-3.0, result.signed_distance_to_farther_line_m)

    def test_minimum_interline_gap_is_declared_negative_evidence(self) -> None:
        result = evaluate(
            7.0,
            config=BetweenObservedLinesConfig(minimum_interline_gap_m=6.0),
        )

        self.assertEqual("FAIL", result.status)
        self.assertEqual("minimum_interline_gap_not_met", result.reason)


class BetweenObservedLinesHonestyTests(unittest.TestCase):
    def test_adequately_observed_missing_pair_can_fail(self) -> None:
        evidence = line_evidence(
            status="FAIL",
            lines=[observed_line(1, 5.0)],
        )

        result = evaluate(7.0, evidence=evidence)

        self.assertEqual("FAIL", result.status)
        self.assertEqual("selected_line_not_observed", result.reason)
        self.assertEqual("ADEQUATE", result.defender_observation_status)
        self.assertEqual("CERTIFIED", result.player_track_coverage_status)

    def test_insufficient_observation_forces_unknown_instead_of_missing_pair_fail(self) -> None:
        evidence = line_evidence(
            status="UNKNOWN",
            defender_observation_status="INSUFFICIENT",
            lines=[observed_line(1, 5.0)],
        )

        result = evaluate(7.0, evidence=evidence)

        self.assertEqual("UNKNOWN", result.status)
        self.assertEqual("insufficient_observed_outfield_defenders", result.reason)
        self.assertEqual(
            ("TST:firstHalf:player_track",),
            result.player_track_coverage_row_ids,
        )

    def test_fail_status_without_adequate_coverage_is_forced_unknown(self) -> None:
        evidence = line_evidence(
            status="FAIL",
            defender_observation_status="INSUFFICIENT",
            lines=[observed_line(1, 5.0)],
        )

        result = evaluate(7.0, evidence=evidence)

        self.assertEqual("UNKNOWN", result.status)
        self.assertEqual("insufficient_observed_outfield_defenders", result.reason)

    def test_frame_misalignment_is_unknown_before_geometry(self) -> None:
        result = evaluate(7.0, frame_id=11)

        self.assertEqual("UNKNOWN", result.status)
        self.assertEqual("line_entity_frame_misaligned", result.reason)

    def test_missing_entity_orientation_or_line_geometry_is_unknown(self) -> None:
        missing_entity = evaluate_between_observed_lines(
            entity_position=None,
            entity_id="receiver-9",
            entity_frame_id=10,
            line_evaluation=line_evidence(),
        )
        invalid_orientation = evaluate(
            7.0,
            evidence={**line_evidence(), "attacking_direction": 0},
        )
        invalid_line = evaluate(
            7.0,
            evidence=line_evidence(
                lines=[observed_line(1, 5.0), {**observed_line(2, 10.0), "line_id": None}]
            ),
        )

        self.assertEqual(("UNKNOWN", "entity_position_missing_or_invalid"), (missing_entity.status, missing_entity.reason))
        self.assertEqual(("UNKNOWN", "attacking_direction_invalid"), (invalid_orientation.status, invalid_orientation.reason))
        self.assertEqual(("UNKNOWN", "observed_line_geometry_invalid"), (invalid_line.status, invalid_line.reason))


class BetweenObservedLinesCatalogTests(unittest.TestCase):
    def test_catalog_uses_typed_entity_and_frame_references(self) -> None:
        entry = next(
            item
            for item in default_catalog().primitives
            if item.name == "between_observed_lines" and item.version == "0.2.0"
        )
        parameters = {parameter.name: parameter for parameter in entry.parameters}

        self.assertEqual(PayloadType.FIELD_REF, parameters["entity_id_field"].payload_type)
        self.assertEqual(FieldReferenceKind.ENTITY, parameters["entity_id_field"].field_reference_kind)
        self.assertEqual(PayloadType.FIELD_REF, parameters["entity_frame_field"].payload_type)
        self.assertEqual(FieldReferenceKind.FRAME, parameters["entity_frame_field"].field_reference_kind)
        self.assertIn("deepest_observed_line", parameters["line_selector"].allowed_values)

    def test_dispatch_is_explicit_and_relocated_to_line_family(self) -> None:
        self.assertIn(
            ("between_observed_lines", "primitive_between_observed_lines"),
            PRIMITIVE_IMPLEMENTATION_NAMES,
        )
        self.assertEqual(
            "tqe.runtime.capabilities.lines_family",
            RELOCATED_IMPLEMENTATION_MODULES["primitive_between_observed_lines"],
        )

    def test_recipe_team_scope_filters_without_changing_legacy_all_default(self) -> None:
        evaluations = [
            {"anchor_id": "home-pass", "team_role": "home"},
            {"anchor_id": "away-pass", "team_role": "away"},
        ]

        self.assertEqual(
            evaluations,
            controlled_pass_evaluations_for_team_scope(
                evaluations,
                team_scope="all",
                perspective_team_role="home",
            ),
        )
        self.assertEqual(
            [evaluations[0]],
            controlled_pass_evaluations_for_team_scope(
                evaluations,
                team_scope="perspective_team",
                perspective_team_role="home",
            ),
        )
        controlled_pass = next(
            entry
            for entry in default_catalog().primitives
            if entry.name == "controlled_pass_episode"
        )
        team_scope = next(
            parameter
            for parameter in controlled_pass.parameters
            if parameter.name == "team_scope"
        )
        self.assertEqual("all", str(team_scope.default.value))

    def test_certified_recipe_synthesizes_one_shared_perspective_chain(self) -> None:
        from scripts.packets.geo1_reception_between_lines_generator import (
            AGGREGATE_NODE_ID,
            RATE_NODE_ID,
            synthesized_plan_bundle,
        )

        bundle, _ = synthesized_plan_bundle()

        for role in ("home", "away"):
            document = bundle["documents"][role]
            nodes = {node["node_id"]: node for node in document["draft_plan"]["nodes"]}
            controlled = nodes["controlled_pass_episode"]
            lines = nodes["multi_line_model"]
            between = nodes["between_observed_lines"]
            self.assertEqual("perspective_team", controlled["parameters"]["team_scope"]["value"])
            self.assertEqual(controlled["node_id"], lines["inputs"]["anchors"]["source_node_id"])
            self.assertEqual(controlled["node_id"], between["inputs"]["entity_anchors"]["source_node_id"])
            self.assertEqual(lines["node_id"], between["inputs"]["line_evaluations"]["source_node_id"])
            self.assertIn(AGGREGATE_NODE_ID, nodes)
            self.assertIn(RATE_NODE_ID, nodes)


if __name__ == "__main__":
    unittest.main()
