from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from tqe.runtime.artifacts import expected_generated_artifacts
from tqe.runtime.binder import BindError, bind_document, bind_document_from_path, bind_error_codes
from tqe.runtime.ir import TacticalQueryDocument

PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")


def load_payload() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


class M11BinderTests(unittest.TestCase):
    def test_ball_side_block_shift_plan_binds_with_stable_hashes(self) -> None:
        bound = bind_document_from_path(PLAN_PATH)
        rebound = bind_document_from_path(PLAN_PATH)

        self.assertEqual("ball_side_block_shift_v1", bound.recipe_id)
        self.assertEqual(10, len(bound.nodes))
        self.assertEqual(19, len(bound.resolved_parameters))
        self.assertEqual(16, bound.max_results)
        self.assertEqual("bind_only", bound.execution_mode.value)
        self.assertEqual(bound.plan_hash, rebound.plan_hash)
        self.assertEqual(bound.bound_plan_hash, rebound.bound_plan_hash)

        script = (
            "from pathlib import Path;"
            "from tqe.runtime.binder import bind_document_from_path;"
            "b=bind_document_from_path(Path('config/query-plans/ball_side_block_shift.ir.v1.json'));"
            "print(b.plan_hash + ' ' + b.bound_plan_hash)"
        )
        output = subprocess.check_output([sys.executable, "-c", script], text=True).strip()
        self.assertEqual(f"{bound.plan_hash} {bound.bound_plan_hash}", output)

    def test_generated_artifacts_are_current(self) -> None:
        for path_text, expected in expected_generated_artifacts().items():
            path = Path(path_text)
            self.assertTrue(path.exists(), path_text)
            self.assertEqual(expected, path.read_text(encoding="utf-8"))

    def test_unknown_primitive_fails_at_bind_time(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["nodes"][1]["catalog_ref"] = "imaginary_primitive"

        self.assertBindError(payload, "unknown_catalog_ref")

    def test_distance_compared_to_seconds_fails_at_bind_time(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["nodes"][6]["compare"] = {
            "payload_type": "number",
            "unit": "second",
            "value": 5.0,
        }

        self.assertBindError(payload, "unit_mismatch")

    def test_count_on_non_collection_fails_at_bind_time(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["nodes"][2]["operator"] = {
            "name": "count_at_least",
            "version": "1.0.0",
        }
        payload["draft_plan"]["nodes"][2]["compare"] = {
            "payload_type": "number",
            "unit": "count",
            "value": 1,
        }

        self.assertBindError(payload, "operator_cardinality_mismatch")

    def test_persists_for_non_frame_signal_fails_at_bind_time(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["nodes"] = [
            {
                "kind": "primitive",
                "node_id": "possession",
                "catalog_ref": "possession_segment",
                "version": "0.1.0",
            },
            {
                "kind": "predicate",
                "node_id": "possession_persists",
                "input": {"source_node_id": "possession", "output_name": "episodes"},
                "operator": {"name": "persists_for", "version": "1.0.0"},
                "duration": {"payload_type": "number", "unit": "second", "value": 1.0},
            },
        ]
        payload["draft_plan"]["classification_rules"] = [
            {
                "label": "BAD",
                "predicate_ids": ["possession_persists"],
                "description": "Invalid episode-set persistence fixture.",
            }
        ]
        payload["draft_plan"]["requested_evidence"] = []

        self.assertBindError(payload, "operator_temporal_mismatch")

    def test_unknown_node_parameter_fails_at_bind_time(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["nodes"][5]["parameters"] = {
            "totally_unknown_knob": {"payload_type": "number", "unit": "metre", "value": 99}
        }

        self.assertBindError(payload, "unknown_node_parameter")

    def test_missing_required_node_input_fails_at_bind_time(self) -> None:
        payload = load_payload()
        del payload["draft_plan"]["nodes"][5]["inputs"]["entry_episodes"]

        self.assertBindError(payload, "missing_node_input")

    def test_invalid_node_parameter_range_fails_at_bind_time(self) -> None:
        payload = json.loads(
            Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json").read_text(
                encoding="utf-8"
            )
        )
        payload["draft_plan"]["nodes"][10]["parameters"]["minimum_clearance_m"] = {
            "payload_type": "number",
            "unit": "metre",
            "value": -3.0,
        }

        self.assertBindError(payload, "parameter_below_minimum")

    def test_classification_labels_must_match_recipe(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["classification_rules"] = [
            {
                "label": "NONSENSE",
                "predicate_ids": ["wide_entry_persists"],
                "description": "Invalid label outside recipe outputs.",
            }
        ]

        self.assertBindError(payload, "classification_label_mismatch")

    def test_team_signal_as_player_relation_fails_at_bind_time(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["nodes"][6]["required_entity_scope"] = "player"

        self.assertBindError(payload, "required_entity_scope_mismatch")

    def test_destination_from_frame_signal_fails_at_bind_time(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["requested_evidence"][1]["field"] = "destination_region"

        self.assertBindError(payload, "unsupported_evidence_field")

    def test_complexity_limit_fails_before_execution(self) -> None:
        payload = load_payload()
        payload["draft_plan"]["complexity_limits"]["max_plan_nodes"] = 1

        self.assertBindError(payload, "complexity_nodes_exceeded")

    def test_missing_perspective_team_role_is_schema_error(self) -> None:
        payload = load_payload()
        del payload["default_invocation"]["perspective_team_role"]

        with self.assertRaises(ValueError):
            TacticalQueryDocument.model_validate(payload)

    def assertBindError(self, payload: dict, expected_code: str) -> None:
        document = TacticalQueryDocument.model_validate(deepcopy(payload))
        with self.assertRaises(BindError) as raised:
            bind_document(document)
        self.assertIn(expected_code, bind_error_codes(raised.exception))


if __name__ == "__main__":
    unittest.main()
