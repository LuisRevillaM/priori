from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from scripts.coverage_map import compiler_search_reachability as search
from tqe.runtime.binder import BindError, bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import CatalogOutput, MissingDataSemantics, TacticalQueryDocument, TypedValue
from tqe.runtime.operators.project_onto_axis import (
    AXIS_VALUES,
    ORIENTATION_BASIS_VALUES,
    PROJECT_ONTO_AXIS_SIGNATURE,
    execute_project_onto_axis,
)
from tqe.runtime.values import RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def state_with_orientation(root: Path) -> SimpleNamespace:
    pd.DataFrame(
        [
            {
                "match_id": "TST",
                "period": "firstHalf",
                "team_role": "home",
                "attack_x_sign": 1,
            },
            {
                "match_id": "TST",
                "period": "firstHalf",
                "team_role": "away",
                "attack_x_sign": -1,
            },
        ]
    ).to_parquet(root / "orientation.parquet")
    return SimpleNamespace(
        canonical_root=root,
        match_id="TST",
        period="firstHalf",
        perspective_team_role="home",
        frame_ids=[10, 20, 30, 40, 50],
        signals={},
    )


def source_value(records: list[dict]) -> RuntimeValue:
    output = PROJECT_ONTO_AXIS_SIGNATURE.inputs[0]
    return runtime_value_from_raw(
        node_id="source",
        output=CatalogOutput(
            name="anchor_evaluations",
            temporal_type=output.temporal_type,
            payload_type=output.payload_type,
            cardinality=output.cardinality,
            unit=output.unit,
            entity_scope=output.entity_scope,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=[
                "start_point",
                "end_point",
                "reference_point",
                "lane_start_point",
                "lane_end_point",
                "team_role",
                "source_status",
            ],
        ),
        raw_value=records,
        frame_ids=[record["anchor_frame_id"] for record in records],
        records=records,
    )


def operator_node() -> SimpleNamespace:
    return SimpleNamespace(
        node_id="project",
        inputs={"source": SimpleNamespace(source_node_id="source", output_name="anchor_evaluations")},
    )


def run_projection(
    *,
    root: Path,
    records: list[dict],
    parameters: dict[str, TypedValue],
) -> dict[str, object]:
    state = state_with_orientation(root)
    execute_project_onto_axis(
        state=state,
        node=operator_node(),
        inputs={"source": source_value(records)},
        parameters=parameters,
    )
    return state.signals["project"]


def base_parameters(axis: str = "goalward") -> dict[str, TypedValue]:
    return {
        "axis": typed_enum(axis),
        "start_point_field": typed_enum("start_point"),
        "end_point_field": typed_enum("end_point"),
        "acting_team_field": typed_enum("team_role"),
        "orientation_basis": typed_enum("acting_team"),
    }


def record(
    *,
    anchor_id: str = "a",
    frame_id: int = 10,
    team_role: str = "home",
    start: tuple[float, float] = (0.0, 0.0),
    end: tuple[float, float] = (5.0, 0.0),
    **extra: object,
) -> dict[str, object]:
    item: dict[str, object] = {
        "anchor_id": anchor_id,
        "match_id": "TST",
        "period": "firstHalf",
        "anchor_frame_id": frame_id,
        "start_frame_id": frame_id,
        "end_frame_id": frame_id,
        "team_role": team_role,
        "start_point": {"x_m": start[0], "y_m": start[1]},
        "end_point": {"x_m": end[0], "y_m": end[1]},
        **extra,
    }
    item["anchor_id"] = canonical_anchor_record_id(item)
    return item


class ProjectOntoAxisTests(unittest.TestCase):
    def test_declares_axis_orientation_and_zero_length_contracts(self) -> None:
        axis = next(parameter for parameter in PROJECT_ONTO_AXIS_SIGNATURE.parameters if parameter.name == "axis")
        orientation = next(
            parameter for parameter in PROJECT_ONTO_AXIS_SIGNATURE.parameters if parameter.name == "orientation_basis"
        )
        zero_length = next(
            parameter for parameter in PROJECT_ONTO_AXIS_SIGNATURE.parameters if parameter.name == "zero_length_policy"
        )

        self.assertEqual(
            ("goalward", "lateral", "toward_point", "along_lane_normal"),
            tuple(axis.allowed_values),
        )
        self.assertEqual(tuple(axis.allowed_values), AXIS_VALUES)
        self.assertEqual(("acting_team", "perspective_team"), tuple(orientation.allowed_values))
        self.assertEqual(tuple(orientation.allowed_values), ORIENTATION_BASIS_VALUES)
        self.assertEqual(["unknown"], zero_length.allowed_values)
        signature_fields = {
            field
            for output in PROJECT_ONTO_AXIS_SIGNATURE.outputs
            for field in [output.name, *output.evidence_fields]
        }
        self.assertEqual(signature_fields, search.PROJECT_ONTO_AXIS_FIELDS)

    def test_goalward_projection_uses_per_record_acting_team(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            signals = run_projection(
                root=Path(tmp),
                records=[
                    record(anchor_id="home", team_role="home", start=(0.0, 0.0), end=(5.0, 0.0)),
                    record(anchor_id="away", frame_id=20, team_role="away", start=(0.0, 0.0), end=(-5.0, 0.0)),
                ],
                parameters=base_parameters("goalward"),
            )

        rows = signals["axis_projection_records"]
        self.assertEqual([5.0, 5.0], signals["signed_projection_m"].values)
        self.assertEqual(["home", "away"], [row["orientation_team_role"] for row in rows])
        self.assertEqual([1, -1], [row["attack_x_sign"] for row in rows])
        self.assertEqual(["acting_team", "acting_team"], [row["orientation_basis"] for row in rows])

    def test_lateral_axis_projects_across_pitch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            signals = run_projection(
                root=Path(tmp),
                records=[record(start=(0.0, 0.0), end=(0.0, 4.0))],
                parameters=base_parameters("lateral"),
            )

        self.assertEqual([4.0], signals["signed_projection_m"].values)
        self.assertEqual([0.0], signals["angle_between_degrees"].values)

    def test_toward_point_requires_record_backed_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            signals = run_projection(
                root=Path(tmp),
                records=[
                    record(
                        start=(0.0, 0.0),
                        end=(2.0, 0.0),
                        reference_point={"x_m": 4.0, "y_m": 0.0},
                    ),
                    record(anchor_id="missing", frame_id=20, start=(0.0, 0.0), end=(2.0, 0.0)),
                ],
                parameters={
                    **base_parameters("toward_point"),
                    "reference_point_field": typed_enum("reference_point"),
                },
            )

        self.assertEqual([2.0, None], signals["signed_projection_m"].values)
        self.assertEqual("reference_point_missing", signals["axis_projection_records"][1]["axis_projection_reason"])

    def test_lane_normal_axis_projects_against_lane_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            signals = run_projection(
                root=Path(tmp),
                records=[
                    record(
                        start=(0.0, 0.0),
                        end=(0.0, 3.0),
                        lane_start_point={"x_m": 0.0, "y_m": 0.0},
                        lane_end_point={"x_m": 4.0, "y_m": 0.0},
                    ),
                    record(
                        anchor_id="zero_lane",
                        frame_id=20,
                        start=(0.0, 0.0),
                        end=(0.0, 3.0),
                        lane_start_point={"x_m": 0.0, "y_m": 0.0},
                        lane_end_point={"x_m": 0.0, "y_m": 0.0},
                    ),
                ],
                parameters={
                    **base_parameters("along_lane_normal"),
                    "lane_start_point_field": typed_enum("lane_start_point"),
                    "lane_end_point_field": typed_enum("lane_end_point"),
                },
            )

        self.assertEqual([3.0, None], signals["signed_projection_m"].values)
        self.assertEqual("zero_length_axis_vector", signals["axis_projection_records"][1]["axis_projection_reason"])

    def test_zero_length_source_vector_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            signals = run_projection(
                root=Path(tmp),
                records=[record(start=(1.0, 1.0), end=(1.0, 1.0))],
                parameters={**base_parameters("goalward"), "zero_length_policy": typed_enum("unknown")},
            )

        row = signals["axis_projection_records"][0]
        self.assertEqual("UNKNOWN", row["axis_projection_status"])
        self.assertEqual("zero_length_source_vector", row["axis_projection_reason"])
        self.assertEqual("unknown", row["zero_length_policy"])

    def test_bind_rejects_field_parameter_not_declared_by_source(self) -> None:
        document_payload = support_depth_document()
        document_payload["draft_plan"]["nodes"][2]["parameters"]["start_point_field"]["value"] = "not_declared"
        document = TacticalQueryDocument.model_validate(document_payload)

        with self.assertRaises(BindError) as error:
            bind_document(document)

        self.assertIn("operator_field_parameter_not_in_input", str(error.exception))

    def test_bind_and_execute_support_depth_composition(self) -> None:
        document = TacticalQueryDocument.model_validate(support_depth_document())

        bound = bind_document(document)
        execution = TacticalQueryExecutor(enable_node_cache=False).execute(bound)
        rows = execution_result_rows(execution)

        self.assertGreater(len(rows), 0)
        self.assertEqual(0, execution.provenance["requested_evidence_failure_count"])
        evidence = rows[0]["requested_evidence"]
        self.assertEqual("PASS", evidence["axis_projection_status"])
        self.assertEqual("first_support_reference_point", evidence["source_start_point_field"])
        self.assertEqual("first_supporter_point", evidence["source_end_point_field"])
        self.assertEqual("acting_team", evidence["orientation_basis"])
        self.assertIn(evidence["orientation_team_role"], {"home", "away"})
        self.assertIsInstance(evidence["signed_projection_m"], float)

    def test_search_synthesis_applies_declared_relation_constraints(self) -> None:
        target = r1_1_target()
        context = search.SearchContext(
            catalog=search.CatalogIndex(),
            target_contract=target["target_contract"],
        )
        required_fields = search.required_target_fields(target["target_contract"])

        build = search.build_project_onto_axis(context, required_fields, depth=0)

        support_nodes = [
            node for node in build.nodes if node.get("catalog_ref") == "support_arrival_point_pair"
        ]
        self.assertEqual(1, len(support_nodes))
        parameters = support_nodes[0]["parameters"]
        self.assertEqual("controlled_reception_frame_id", parameters["anchor_frame_field"]["value"])
        self.assertEqual("perspective_outfield", parameters["candidate_scope"]["value"])
        self.assertEqual("WITHIN_DISTANCE_OF_REFERENCE_POINT", parameters["support_region_mode"]["value"])
        self.assertEqual(3.0, parameters["maximum_arrival_seconds"]["value"])
        self.assertEqual(0.0, parameters["minimum_duration_seconds"]["value"])
        self.assertEqual(30.0, parameters["maximum_support_distance_m"]["value"])
        self.assertEqual(1.0, parameters["minimum_supporting_players"]["value"])
        self.assertEqual("controlled_pass_status", parameters["required_anchor_status_field"]["value"])
        self.assertEqual("PASS", parameters["required_anchor_status_value"]["value"])
        source_metadata = build.metadata["source_build_metadata"]
        self.assertEqual(
            30.0,
            source_metadata["relation_on_anchor_applied_parameters"]["maximum_support_distance_m"]["value"],
        )

    def test_search_synthesis_fails_on_unapplied_relation_constraint_key(self) -> None:
        target = r1_1_target()
        target = copy.deepcopy(target)
        target["target_contract"]["composition_constraints"][0]["unsupported_relation_key"] = "must_not_drop"
        context = search.SearchContext(
            catalog=search.CatalogIndex(),
            target_contract=target["target_contract"],
        )
        required_fields = search.required_target_fields(target["target_contract"])

        with self.assertRaises(search.SynthesisError) as error:
            search.build_project_onto_axis(context, required_fields, depth=0)

        self.assertEqual("missing_constraint", error.exception.taxonomy)
        payload = json.dumps(error.exception.details, sort_keys=True)
        self.assertIn("unapplied_relation_constraint_keys", payload)
        self.assertIn("unsupported_relation_key", payload)


def support_depth_document() -> dict[str, object]:
    outputs = [output.model_dump(mode="json") for output in PROJECT_ONTO_AXIS_SIGNATURE.outputs]
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "r1_1_project_onto_axis_probe",
            "recipe_version": "0.1.0",
            "display_name": "R1-1 project onto axis probe",
            "description": "Support-arrival point-pair projected onto acting-team goalward axis.",
            "parameters": [],
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "Observed supporter-relative depth from carrier/reference point at support arrival only."
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
                    "kind": "relation",
                    "node_id": "support_arrival",
                    "catalog_ref": "support_arrival_point_pair",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {
                            "source_node_id": "controlled_pass",
                            "output_name": "anchors",
                        }
                    },
                    "parameters": {
                        "anchor_frame_field": {"payload_type": "enum", "value": "controlled_reception_frame_id"},
                        "candidate_scope": {"payload_type": "enum", "value": "perspective_outfield"},
                        "support_region_mode": {
                            "payload_type": "enum",
                            "value": "WITHIN_DISTANCE_OF_REFERENCE_POINT",
                        },
                        "maximum_arrival_seconds": {
                            "payload_type": "number",
                            "unit": "second",
                            "value": 3.0,
                        },
                        "minimum_duration_seconds": {
                            "payload_type": "number",
                            "unit": "second",
                            "value": 0.0,
                        },
                        "maximum_support_distance_m": {
                            "payload_type": "number",
                            "unit": "metre",
                            "value": 30.0,
                        },
                        "minimum_supporting_players": {
                            "payload_type": "number",
                            "unit": "count",
                            "value": 1.0,
                        },
                        "required_anchor_status_field": {"payload_type": "enum", "value": "controlled_pass_status"},
                        "required_anchor_status_value": {"payload_type": "enum", "value": "PASS"},
                    },
                },
                {
                    "kind": "operator",
                    "node_id": "goalward_projection",
                    "operator": {"name": "project_onto_axis", "version": "0.1.0"},
                    "inputs": {
                        "source": {
                            "source_node_id": "support_arrival",
                            "output_name": "anchor_evaluations",
                        }
                    },
                    "parameters": {
                        "axis": {"payload_type": "enum", "value": "goalward"},
                        "start_point_field": {
                            "payload_type": "enum",
                            "value": "first_support_reference_point",
                        },
                        "end_point_field": {
                            "payload_type": "enum",
                            "value": "first_supporter_point",
                        },
                        "acting_team_field": {
                            "payload_type": "enum",
                            "value": "candidate_team_role",
                        },
                        "orientation_basis": {"payload_type": "enum", "value": "acting_team"},
                        "required_source_status_field": {
                            "payload_type": "enum",
                            "value": "support_point_pair_status",
                        },
                        "required_source_status_value": {
                            "payload_type": "enum",
                            "value": "PASS",
                        },
                        "zero_length_policy": {"payload_type": "enum", "value": "unknown"},
                    },
                    "outputs": outputs,
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
                    "description": "Supporter-relative goalward projection exists at support arrival.",
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
                    "field": field,
                    "alias": field,
                    "required": True,
                }
                for field in (
                    "axis_projection_status",
                    "source_start_point_field",
                    "source_end_point_field",
                    "orientation_basis",
                    "orientation_team_role",
                    "signed_projection_m",
                    "angle_between_degrees",
                )
            ],
        },
    }


def r1_1_target() -> dict[str, object]:
    target_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "compiler-reachability"
        / "r1-1-project-onto-axis-targets.v0.json"
    )
    return json.loads(target_path.read_text(encoding="utf-8"))["targets"][0]


if __name__ == "__main__":
    unittest.main()
