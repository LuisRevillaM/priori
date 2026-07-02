import unittest

from tqe.runtime.relative_position_to_line import (
    AHEAD_OF_LINE,
    BEHIND_LINE,
    LEVEL_WITH_LINE,
    UNKNOWN,
    EntityPosition,
    RelativePositionToLineConfig,
    evaluate_relative_position_to_line,
    evaluate_relative_positions_to_line,
)


class RelativePositionToLineTest(unittest.TestCase):
    def test_classifies_entity_ahead_of_line_with_geometry_metadata(self) -> None:
        evaluation = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=EntityPosition(12.0, -4.0),
            attacking_direction=1,
            entity_id="p9",
            anchor_frame_id=42,
            config=RelativePositionToLineConfig(buffer_m=0.5),
        )

        self.assertEqual(AHEAD_OF_LINE, evaluation.status)
        self.assertEqual("entity_goalward_of_line", evaluation.reason)
        self.assertEqual("p9", evaluation.entity_id)
        self.assertEqual(42, evaluation.anchor_frame_id)
        self.assertAlmostEqual(10.0, evaluation.normalized_line_x_m)
        self.assertAlmostEqual(12.0, evaluation.normalized_entity_x_m)
        self.assertAlmostEqual(2.0, evaluation.signed_distance_to_line_m)
        self.assertAlmostEqual(2.0, evaluation.distance_to_line_m)
        self.assertAlmostEqual(0.5, evaluation.buffer_m)

    def test_classifies_entity_behind_line(self) -> None:
        evaluation = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=(8.0, 3.0),
            attacking_direction=1,
            config=RelativePositionToLineConfig(buffer_m=0.5),
        )

        self.assertEqual(BEHIND_LINE, evaluation.status)
        self.assertEqual("entity_behind_line", evaluation.reason)
        self.assertAlmostEqual(-2.0, evaluation.signed_distance_to_line_m)
        self.assertAlmostEqual(2.0, evaluation.distance_to_line_m)

    def test_buffer_boundary_is_level_and_beyond_buffer_classifies(self) -> None:
        config = RelativePositionToLineConfig(buffer_m=0.5)

        ahead_boundary = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=(10.5, 0.0),
            attacking_direction=1,
            config=config,
        )
        behind_boundary = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=(9.5, 0.0),
            attacking_direction=1,
            config=config,
        )
        ahead_beyond = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=(10.500001, 0.0),
            attacking_direction=1,
            config=config,
        )

        self.assertEqual(LEVEL_WITH_LINE, ahead_boundary.status)
        self.assertEqual(LEVEL_WITH_LINE, behind_boundary.status)
        self.assertEqual(AHEAD_OF_LINE, ahead_beyond.status)

    def test_mirrored_attacking_direction_preserves_normalized_result(self) -> None:
        forward = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=(12.0, 0.0),
            attacking_direction=1,
            config=RelativePositionToLineConfig(buffer_m=0.25),
        )
        mirrored = evaluate_relative_position_to_line(
            line_x_m=-10.0,
            entity_position=(-12.0, 0.0),
            attacking_direction=-1,
            config=RelativePositionToLineConfig(buffer_m=0.25),
        )

        self.assertEqual(forward.status, mirrored.status)
        self.assertEqual(forward.reason, mirrored.reason)
        self.assertAlmostEqual(forward.normalized_line_x_m, mirrored.normalized_line_x_m)
        self.assertAlmostEqual(forward.normalized_entity_x_m, mirrored.normalized_entity_x_m)
        self.assertAlmostEqual(forward.signed_distance_to_line_m, mirrored.signed_distance_to_line_m)
        self.assertAlmostEqual(forward.distance_to_line_m, mirrored.distance_to_line_m)

    def test_unknown_when_line_position_missing(self) -> None:
        evaluation = evaluate_relative_position_to_line(
            line_x_m=None,
            entity_position=(12.0, 0.0),
            attacking_direction=1,
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual("line_x_missing", evaluation.reason)
        self.assertIsNone(evaluation.normalized_line_x_m)
        self.assertAlmostEqual(12.0, evaluation.normalized_entity_x_m)
        self.assertIsNone(evaluation.distance_to_line_m)

    def test_unknown_when_entity_position_missing(self) -> None:
        evaluation = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=None,
            attacking_direction=1,
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual("entity_position_missing", evaluation.reason)
        self.assertAlmostEqual(10.0, evaluation.normalized_line_x_m)
        self.assertIsNone(evaluation.normalized_entity_x_m)

    def test_unknown_when_line_or_entity_coordinate_is_boolean(self) -> None:
        bool_line = evaluate_relative_position_to_line(
            line_x_m=True,
            entity_position=(12.0, 0.0),
            attacking_direction=1,
        )
        bool_entity = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=(True, 0.0),
            attacking_direction=1,
        )

        self.assertEqual(UNKNOWN, bool_line.status)
        self.assertEqual("line_x_invalid", bool_line.reason)
        self.assertEqual(UNKNOWN, bool_entity.status)
        self.assertEqual("entity_position_invalid", bool_entity.reason)

    def test_non_numeric_entity_coordinates_yield_unknown_not_exception(self) -> None:
        # Bad coordinate evidence must degrade to UNKNOWN with a typed reason;
        # it must never escape as an exception from the kernel.
        bad_positions = [
            EntityPosition(x_m="not-a-number"),
            EntityPosition(x_m=None),
            EntityPosition(x_m=object()),
            EntityPosition(x_m=5.0, y_m="not-a-number"),
            EntityPosition(x_m=float("nan")),
            EntityPosition(x_m=float("inf")),
            {"x_m": "not-a-number"},
            ("not-a-number", 0.0),
        ]
        for position in bad_positions:
            with self.subTest(position=position):
                evaluation = evaluate_relative_position_to_line(
                    line_x_m=10.0,
                    entity_position=position,
                    attacking_direction=1,
                )
                self.assertEqual(UNKNOWN, evaluation.status)
                self.assertEqual("entity_position_invalid", evaluation.reason)
                self.assertIsNone(evaluation.normalized_entity_x_m)

    def test_numeric_string_coordinates_mirror_mapping_coercion(self) -> None:
        # A numeric-string EntityPosition must classify identically to the
        # equivalent mapping input instead of raising.
        typed = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=EntityPosition(x_m="12.0", y_m="0.0"),
            attacking_direction=1,
        )
        mapped = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position={"x_m": "12.0", "y_m": "0.0"},
            attacking_direction=1,
        )

        self.assertEqual(AHEAD_OF_LINE, typed.status)
        self.assertEqual(typed.to_dict(), mapped.to_dict())

    def test_unknown_when_attacking_direction_invalid(self) -> None:
        evaluation = evaluate_relative_position_to_line(
            line_x_m=10.0,
            entity_position=(12.0, 0.0),
            attacking_direction=0,
        )

        self.assertEqual(UNKNOWN, evaluation.status)
        self.assertEqual("attacking_direction_invalid", evaluation.reason)
        self.assertIsNone(evaluation.normalized_line_x_m)
        self.assertIsNone(evaluation.normalized_entity_x_m)

    def test_line_evaluation_can_supply_line_direction_and_anchor(self) -> None:
        evaluation = evaluate_relative_position_to_line(
            line_evaluation={
                "line_x_m": 10.0,
                "attacking_direction": 1,
                "anchor_frame_id": "frame-7",
            },
            entity_position={"x_m": 9.0, "y_m": 1.0},
            config=RelativePositionToLineConfig(buffer_m=0.25),
        )

        self.assertEqual(BEHIND_LINE, evaluation.status)
        self.assertEqual("frame-7", evaluation.anchor_frame_id)
        self.assertEqual(1, evaluation.attacking_direction)
        self.assertAlmostEqual(-1.0, evaluation.signed_distance_to_line_m)

    def test_batch_output_is_deterministic_under_mapping_order(self) -> None:
        first = evaluate_relative_positions_to_line(
            line_x_m=10.0,
            attacking_direction=1,
            entity_positions={
                "b": (12.0, 0.0),
                "a": (8.0, 0.0),
                "c": (10.0, 0.0),
            },
        )
        second = evaluate_relative_positions_to_line(
            line_x_m=10.0,
            attacking_direction=1,
            entity_positions={
                "c": (10.0, 0.0),
                "b": (12.0, 0.0),
                "a": (8.0, 0.0),
            },
        )

        self.assertEqual(("a", "b", "c"), tuple(item.entity_id for item in first))
        self.assertEqual(tuple(item.to_dict() for item in first), tuple(item.to_dict() for item in second))


if __name__ == "__main__":
    unittest.main()
