from __future__ import annotations

import unittest

from tqe.runtime.one_touch import (
    AHEAD_OF_LINE,
    BEHIND_LINE,
    FAIL,
    LEVEL_WITH_LINE,
    PASS,
    UNKNOWN,
    evaluate_pass_chain,
    evaluate_receiver_line_transition,
)


class OneTouchPassChainTests(unittest.TestCase):
    def test_receiver_transition_passes_from_not_beyond_to_beyond(self) -> None:
        result = evaluate_receiver_line_transition(
            relay_evidence={"one_touch_relay_status": PASS},
            observed_line_evidence={"line_status": PASS, "line_x_m": 10.0, "attacking_direction": 1},
            release_relative_position_evidence={
                "relative_position_status": LEVEL_WITH_LINE,
                "signed_distance_to_line_m": 0.2,
            },
            relay_relative_position_evidence={
                "relative_position_status": AHEAD_OF_LINE,
                "signed_distance_to_line_m": 1.1,
            },
        )
        self.assertEqual(result["receiver_line_transition_status"], PASS)

    def test_receiver_transition_does_not_claim_when_already_beyond(self) -> None:
        result = evaluate_receiver_line_transition(
            relay_evidence={"one_touch_relay_status": PASS},
            observed_line_evidence={"line_status": PASS, "line_x_m": 10.0, "attacking_direction": 1},
            release_relative_position_evidence={
                "relative_position_status": AHEAD_OF_LINE,
                "signed_distance_to_line_m": 2.0,
            },
            relay_relative_position_evidence={
                "relative_position_status": AHEAD_OF_LINE,
                "signed_distance_to_line_m": 3.0,
            },
        )
        self.assertEqual(result["receiver_line_transition_status"], FAIL)
        self.assertEqual(
            result["receiver_line_transition_reason"],
            "receiver_already_beyond_line_at_input_release",
        )

    def test_receiver_transition_preserves_unknown_premises(self) -> None:
        result = evaluate_receiver_line_transition(
            relay_evidence={"one_touch_relay_status": PASS},
            observed_line_evidence={"line_status": PASS, "line_x_m": 10.0, "attacking_direction": 1},
            release_relative_position_evidence={"relative_position_status": UNKNOWN},
            relay_relative_position_evidence={"relative_position_status": AHEAD_OF_LINE},
        )
        self.assertEqual(result["receiver_line_transition_status"], UNKNOWN)
        self.assertEqual(result["receiver_line_transition_reason"], "relative_position_unknown")

    def test_pass_chain_requires_terminal_controlled_reception(self) -> None:
        result = evaluate_pass_chain(
            relay_evidence={"one_touch_relay_status": PASS},
            terminal_controlled_pass_evidence={"controlled_pass_status": PASS},
        )
        self.assertEqual(result["pass_chain_status"], PASS)

        missing = evaluate_pass_chain(
            relay_evidence={"one_touch_relay_status": PASS},
            terminal_controlled_pass_evidence=None,
        )
        self.assertEqual(missing["pass_chain_status"], UNKNOWN)


if __name__ == "__main__":
    unittest.main()
