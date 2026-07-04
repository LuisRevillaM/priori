from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import TacticalQueryDocument, TypedValue
from tqe.runtime.ir import MissingDataSemantics
from tqe.runtime.operators.project_onto_axis import (
    AXIS_VALUES,
    PROJECT_ONTO_AXIS_SIGNATURE,
    execute_project_onto_axis,
)
from tqe.runtime.values import RuntimeValue, runtime_value_from_raw


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def fake_state() -> SimpleNamespace:
    return SimpleNamespace(
        canonical_root=Path("canonical"),
        match_id="TST",
        period="firstHalf",
        perspective_team_role="home",
        frame_ids=[10, 20, 30],
        signals={},
    )


def source_value(records: list[dict]) -> RuntimeValue:
    output = PROJECT_ONTO_AXIS_SIGNATURE.inputs[0]
    # Build a matching CatalogOutput through the operator's input contract.
    from tqe.runtime.ir import CatalogOutput

    return runtime_value_from_raw(
        node_id="source",
        output=CatalogOutput(
            name="episodes",
            temporal_type=output.temporal_type,
            payload_type=output.payload_type,
            cardinality=output.cardinality,
            unit=output.unit,
            entity_scope=output.entity_scope,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
        ),
        raw_value=records,
        frame_ids=[record["anchor_frame_id"] for record in records],
        records=records,
    )


def operator_node() -> SimpleNamespace:
    return SimpleNamespace(
        node_id="project",
        inputs={"source": SimpleNamespace(source_node_id="source", output_name="episodes")},
    )


class ProjectOntoAxisTests(unittest.TestCase):
    def test_axis_enum_is_complete(self) -> None:
        axis = next(parameter for parameter in PROJECT_ONTO_AXIS_SIGNATURE.parameters if parameter.name == "axis")

        self.assertEqual(
            ("goalward", "lateral", "toward_point", "along_lane_normal"),
            tuple(axis.allowed_values),
        )
        self.assertEqual(tuple(axis.allowed_values), AXIS_VALUES)

    def test_goalward_projection_is_mirror_symmetric_by_attack_direction(self) -> None:
        state = fake_state()
        records = [
            {
                "anchor_id": "a",
                "match_id": "TST",
                "period": "firstHalf",
                "anchor_frame_id": 10,
                "start_frame_id": 10,
                "end_frame_id": 10,
                "release_ball_point": {"x_m": 0.0, "y_m": 0.0},
                "reception_ball_point": {"x_m": 5.0, "y_m": 0.0},
                "attacking_direction": 1,
            },
            {
                "anchor_id": "b",
                "match_id": "TST",
                "period": "firstHalf",
                "anchor_frame_id": 20,
                "start_frame_id": 20,
                "end_frame_id": 20,
                "release_ball_point": {"x_m": 0.0, "y_m": 0.0},
                "reception_ball_point": {"x_m": -5.0, "y_m": 0.0},
                "attacking_direction": -1,
            },
        ]

        execute_project_onto_axis(
            state=state,
            node=operator_node(),
            inputs={"source": source_value(records)},
            parameters={"axis": typed_enum("goalward")},
        )

        signal = state.signals["project"]["signed_projection_m"]
        self.assertEqual([5.0, 5.0], signal.values)

    def test_missing_vector_points_emit_unknown_not_drop(self) -> None:
        state = fake_state()
        records = [
            {
                "anchor_id": "a",
                "match_id": "TST",
                "period": "firstHalf",
                "anchor_frame_id": 10,
                "start_frame_id": 10,
                "end_frame_id": 10,
                "release_ball_point": {"x_m": 0.0, "y_m": 0.0},
                "attacking_direction": 1,
            }
        ]

        execute_project_onto_axis(
            state=state,
            node=operator_node(),
            inputs={"source": source_value(records)},
            parameters={"axis": typed_enum("goalward")},
        )

        record = state.signals["project"]["axis_projection_records"][0]
        self.assertEqual("UNKNOWN", record["axis_projection_status"])
        self.assertEqual("missing_vector_point", record["axis_projection_reason"])
        self.assertIsNone(state.signals["project"]["signed_projection_m"].values[0])

    def test_angle_boundaries_are_declared_0_90_180(self) -> None:
        state = fake_state()
        records = [
            {
                "anchor_id": "a",
                "match_id": "TST",
                "period": "firstHalf",
                "anchor_frame_id": 10,
                "start_frame_id": 10,
                "end_frame_id": 10,
                "release_ball_point": {"x_m": 0.0, "y_m": 0.0},
                "reception_ball_point": {"x_m": 4.0, "y_m": 0.0},
                "attacking_direction": 1,
            },
            {
                "anchor_id": "b",
                "match_id": "TST",
                "period": "firstHalf",
                "anchor_frame_id": 20,
                "start_frame_id": 20,
                "end_frame_id": 20,
                "release_ball_point": {"x_m": 0.0, "y_m": 0.0},
                "reception_ball_point": {"x_m": 0.0, "y_m": 4.0},
                "attacking_direction": 1,
            },
            {
                "anchor_id": "c",
                "match_id": "TST",
                "period": "firstHalf",
                "anchor_frame_id": 30,
                "start_frame_id": 30,
                "end_frame_id": 30,
                "release_ball_point": {"x_m": 0.0, "y_m": 0.0},
                "reception_ball_point": {"x_m": -4.0, "y_m": 0.0},
                "attacking_direction": 1,
            },
        ]

        execute_project_onto_axis(
            state=state,
            node=operator_node(),
            inputs={"source": source_value(records)},
            parameters={"axis": typed_enum("goalward")},
        )

        self.assertEqual([0.0, 90.0, 180.0], state.signals["project"]["angle_between_degrees"].values)

    def test_bind_and_execute_real_composition(self) -> None:
        document = TacticalQueryDocument.model_validate(
            {
                "schema_version": "1.0",
                "recipe": {
                    "schema_version": "1.0",
                    "recipe_id": "r1_1_project_onto_axis_probe",
                    "recipe_version": "0.1.0",
                    "display_name": "R1-1 project onto axis probe",
                    "description": "Controlled pass point-pair projected onto goalward axis.",
                    "parameters": [],
                    "default_unknown_evidence_policy": "exclude_candidate",
                    "allowed_claims": [
                        "Observed pass point-pair projection onto the goalward axis only."
                    ],
                    "disallowed_claims": [
                        "The system inferred support quality, decision value, intent, causation, or pass probability."
                    ],
                    "limitations": ["Operator acceptance probe."],
                    "output_classifications": ["R1_1_AXIS_PROJECTION"],
                },
                "default_invocation": {
                    "schema_version": "1.0",
                    "invocation_id": "r1_1_project_onto_axis_probe",
                    "match_ids": ["J03WOY"],
                    "periods": ["firstHalf"],
                    "perspective_team_role": "home",
                    "parameters": {},
                    "max_results": 5,
                    "execution_mode": "execute",
                },
                "draft_plan": {
                    "schema_version": "1.0",
                    "plan_id": "r1_1_project_onto_axis_probe",
                    "plan_version": "0.1.0",
                    "recipe_id": "r1_1_project_onto_axis_probe",
                    "recipe_version": "0.1.0",
                    "status": "experimental",
                    "unknown_evidence_policy": "exclude_candidate",
                    "classification_mode": "partial_declared",
                    "nodes": [
                        {
                            "kind": "primitive",
                            "node_id": "controlled_pass",
                            "catalog_ref": "controlled_pass_episode",
                            "version": "0.1.0",
                        },
                        {
                            "kind": "operator",
                            "node_id": "goalward_projection",
                            "operator": {"name": "project_onto_axis", "version": "0.1.0"},
                            "inputs": {
                                "source": {
                                    "source_node_id": "controlled_pass",
                                    "output_name": "episodes",
                                }
                            },
                            "parameters": {
                                "axis": {"payload_type": "enum", "value": "goalward"},
                                "start_point_field": {
                                    "payload_type": "enum",
                                    "value": "release_ball_point",
                                },
                                "end_point_field": {
                                    "payload_type": "enum",
                                    "value": "reception_ball_point",
                                },
                                "required_source_status_field": {
                                    "payload_type": "enum",
                                    "value": "controlled_pass_status",
                                },
                                "required_source_status_value": {
                                    "payload_type": "enum",
                                    "value": "PASS",
                                },
                            },
                            "outputs": [
                                output.model_dump(mode="json")
                                for output in PROJECT_ONTO_AXIS_SIGNATURE.outputs
                            ],
                        },
                        {
                            "kind": "predicate",
                            "node_id": "projection_observed",
                            "input": {
                                "source_node_id": "goalward_projection",
                                "output_name": "axis_projection_status",
                            },
                            "operator": {"name": "eq", "version": "1.0.0"},
                            "compare": {"payload_type": "enum", "value": "PASS"},
                        },
                    ],
                    "classification_rules": [
                        {
                            "label": "R1_1_AXIS_PROJECTION",
                            "predicate_ids": ["projection_observed"],
                            "description": "Goalward projection exists for the controlled pass point pair.",
                        }
                    ],
                    "anchor_source": {
                        "source_node_id": "goalward_projection",
                        "output_name": "axis_projection_records",
                    },
                    "requested_evidence": [
                        {
                            "source": {
                                "source_node_id": "goalward_projection",
                                "output_name": "axis_projection_records",
                            },
                            "field": "signed_projection_m",
                            "alias": "signed_projection_m",
                            "required": True,
                        },
                        {
                            "source": {
                                "source_node_id": "goalward_projection",
                                "output_name": "axis_projection_records",
                            },
                            "field": "angle_between_degrees",
                            "alias": "angle_between_degrees",
                            "required": True,
                        },
                    ],
                },
            }
        )

        bound = bind_document(document)
        execution = TacticalQueryExecutor().execute(bound)
        rows = execution_result_rows(execution)

        self.assertGreater(len(rows), 0)
        self.assertEqual(0, execution.provenance["requested_evidence_failure_count"])
        self.assertIn("signed_projection_m", rows[0]["requested_evidence"])


if __name__ == "__main__":
    unittest.main()
