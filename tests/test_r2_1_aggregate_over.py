from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from tqe.runtime.binder import BindError, bind_document, bind_error_codes
from tqe.runtime.ir import CatalogOutput, MissingDataSemantics, TacticalQueryDocument, TypedValue
from tqe.runtime.operators.aggregate_over import (
    AGGREGATE_OVER_SIGNATURE,
    AggregateIntervalResult,
    execute_aggregate_over,
)
from tqe.runtime.values import RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw


CAR_BUNDLE_PATH = Path("tests/fixtures/r1_5_fragile_possession_state_j03woh_bundle.json")


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def typed_bool(value: bool) -> TypedValue:
    return TypedValue(payload_type="boolean", value=value)


def typed_entity_set(values: list[str]) -> TypedValue:
    return TypedValue(payload_type="entity_set", value=values)


def aggregate_record(
    frame_id: int,
    *,
    team_role: str,
    status: str,
    match_id: str = "TST",
    period: str = "firstHalf",
) -> dict[str, object]:
    record: dict[str, object] = {
        "match_id": match_id,
        "period": period,
        "anchor_frame_id": frame_id,
        "start_frame_id": frame_id,
        "end_frame_id": frame_id,
        "entity_refs": [team_role],
        "left_team_role": team_role,
        "right_team_role": team_role,
        "anchor_team_role": team_role,
        "continuity_team_role": team_role,
        "typed_join_status": status,
    }
    record["anchor_id"] = canonical_anchor_record_id(record)
    return record


def population_value(records: list[dict[str, object]]) -> RuntimeValue:
    input_def = {item.name: item for item in AGGREGATE_OVER_SIGNATURE.inputs}["population"]
    return runtime_value_from_raw(
        node_id="population",
        output=CatalogOutput(
            name="population",
            temporal_type=input_def.temporal_type,
            payload_type=input_def.payload_type,
            cardinality=input_def.cardinality,
            unit=input_def.unit,
            entity_scope=input_def.entity_scope,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=[
                "match_id",
                "period",
                "left_team_role",
                "right_team_role",
                "anchor_team_role",
                "continuity_team_role",
                "typed_join_status",
            ],
        ),
        raw_value=records,
        frame_ids=[int(record["anchor_frame_id"]) for record in records],
        records=records,
    )


def aggregate_node() -> SimpleNamespace:
    return SimpleNamespace(
        node_id="aggregate",
        inputs={
            "population": SimpleNamespace(source_node_id="typed_join_2", output_name="typed_join_records"),
        },
    )


def run_count(records: list[dict[str, object]]) -> list[dict[str, object]]:
    state = SimpleNamespace(match_id="TST", period="firstHalf", perspective_team_role="home", signals={})
    execute_aggregate_over(
        state=state,
        node=aggregate_node(),
        inputs={"population": population_value(records)},
        parameters={
            "aggregation_kind": typed_enum("count"),
            "population_expression": typed_enum("fragile_possession_state rows"),
            "group_by_fields": typed_entity_set(["left_team_role", "match_id"]),
            "status_field": typed_enum("typed_join_status"),
            "numeric_field": typed_enum("none"),
            "same_team_perspective_required": typed_bool(True),
            "entity_identity_preserved_required": typed_bool(False),
            "frame_alignment_required": typed_bool(True),
            "team_role_field": typed_enum("left_team_role"),
        },
    )
    return state.signals["aggregate"]["aggregate_records"]


def run_count_by_perspective(records: list[dict[str, object]], *, perspective_team_role: str) -> list[dict[str, object]]:
    state = SimpleNamespace(
        match_id="TST",
        period="firstHalf",
        perspective_team_role=perspective_team_role,
        signals={},
    )
    execute_aggregate_over(
        state=state,
        node=aggregate_node(),
        inputs={"population": population_value(records)},
        parameters={
            "aggregation_kind": typed_enum("count"),
            "population_expression": typed_enum("fragile_possession_state rows"),
            "group_by_fields": typed_entity_set(["perspective_team_role", "match_id"]),
            "status_field": typed_enum("typed_join_status"),
            "numeric_field": typed_enum("none"),
            "same_team_perspective_required": typed_bool(True),
            "entity_identity_preserved_required": typed_bool(False),
            "frame_alignment_required": typed_bool(True),
            "team_role_field": typed_enum("perspective_team_role"),
        },
    )
    return state.signals["aggregate"]["aggregate_records"]


def aggregate_node_payload(
    *,
    same_team_required: bool = True,
    group_by_fields: list[str] | None = None,
    aggregation_kind: str = "count",
    numeric_field: str = "none",
) -> dict[str, object]:
    declared_group_by_fields = group_by_fields or ["perspective_team_role", "match_id"]
    return {
        "kind": "operator",
        "node_id": "aggregate",
        "operator": {"name": "aggregate_over", "version": "0.1.0"},
        "inputs": {
            "population": {"source_node_id": "typed_join_2", "output_name": "typed_join_records"},
        },
        "parameters": {
            "aggregation_kind": {"payload_type": "enum", "value": aggregation_kind},
            "population_expression": {"payload_type": "enum", "value": "fragile_possession_state rows"},
            "group_by_fields": {"payload_type": "entity_set", "value": declared_group_by_fields},
            "status_field": {"payload_type": "enum", "value": "typed_join_status"},
            "numeric_field": {"payload_type": "enum", "value": numeric_field},
            "same_team_perspective_required": {"payload_type": "boolean", "value": same_team_required},
            "frame_alignment_required": {"payload_type": "boolean", "value": True},
            "team_role_field": {"payload_type": "enum", "value": "perspective_team_role"},
        },
        "outputs": [output.model_dump(mode="json") for output in AGGREGATE_OVER_SIGNATURE.outputs],
    }


class AggregateOverOperatorTests(unittest.TestCase):
    def test_count_bounds_include_unknown_rows(self) -> None:
        records = [
            aggregate_record(100, team_role="home", status="PASS"),
            aggregate_record(110, team_role="home", status="PASS"),
            aggregate_record(120, team_role="home", status="FAIL"),
            aggregate_record(130, team_role="home", status="UNKNOWN"),
        ]

        [result] = run_count(records)

        self.assertEqual(2, result["observed"])
        self.assertEqual(2, result["lower_bound"])
        self.assertEqual(3, result["upper_bound"])
        self.assertEqual(1, result["unknown_count"])
        self.assertEqual(4, result["population_count"])

    def test_constructor_refuses_external_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "computed internally"):
            AggregateIntervalResult(
                aggregation_kind="count",
                population_expression="fixture",
                group_key={"team": "home"},
                pass_values=[1.0],
                fail_count=0,
                unknown_values=[],
                lower_bound=0,
            )

    def test_group_by_keys_preserve_both_team_perspectives(self) -> None:
        records = [
            aggregate_record(100, team_role="home", status="PASS"),
            aggregate_record(110, team_role="home", status="UNKNOWN"),
            aggregate_record(120, team_role="away", status="PASS"),
            aggregate_record(130, team_role="away", status="FAIL"),
        ]

        results = run_count(records)
        by_team = {record["group_key"]["left_team_role"]: record for record in results}

        self.assertEqual({"home", "away"}, set(by_team))
        self.assertEqual(1, by_team["home"]["unknown_count"])
        self.assertEqual(0, by_team["away"]["unknown_count"])
        for source in records:
            self.assertEqual(source["anchor_team_role"], source["continuity_team_role"])

    def test_perspective_team_role_can_be_declared_group_key(self) -> None:
        records = [
            aggregate_record(100, team_role="home", status="PASS"),
            aggregate_record(110, team_role="away", status="UNKNOWN"),
        ]

        [result] = run_count_by_perspective(records, perspective_team_role="away")

        self.assertEqual({"perspective_team_role": "away", "match_id": "TST"}, result["group_key"])
        self.assertEqual(1, result["observed"])
        self.assertEqual(2, result["upper_bound"])
        self.assertEqual(2, result["population_count"])

    def test_non_tri_state_status_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "PASS/FAIL/UNKNOWN"):
            run_count([aggregate_record(100, team_role="home", status="MAYBE")])

    def test_bind_accepts_declared_flagship_grouping(self) -> None:
        payload = json.loads(CAR_BUNDLE_PATH.read_text(encoding="utf-8"))["documents"]["home"]
        payload = copy.deepcopy(payload)
        payload["draft_plan"]["nodes"].append(aggregate_node_payload())

        bound = bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertEqual("aggregate", bound.nodes[-1].node_id)

    def test_bind_rejects_undeclared_group_by_field(self) -> None:
        payload = json.loads(CAR_BUNDLE_PATH.read_text(encoding="utf-8"))["documents"]["home"]
        payload = copy.deepcopy(payload)
        payload["draft_plan"]["nodes"].append(
            aggregate_node_payload(group_by_fields=["left_team_role", "not_a_declared_field"])
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_field_parameter_not_in_input", bind_error_codes(raised.exception))

    def test_bind_rejects_count_with_numeric_field(self) -> None:
        payload = json.loads(CAR_BUNDLE_PATH.read_text(encoding="utf-8"))["documents"]["home"]
        payload = copy.deepcopy(payload)
        payload["draft_plan"]["nodes"].append(aggregate_node_payload(numeric_field="duration_seconds"))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn(
            "operator_aggregate_count_numeric_field_forbidden",
            bind_error_codes(raised.exception),
        )

    def test_bind_rejects_sum_without_numeric_field(self) -> None:
        payload = json.loads(CAR_BUNDLE_PATH.read_text(encoding="utf-8"))["documents"]["home"]
        payload = copy.deepcopy(payload)
        payload["draft_plan"]["nodes"].append(aggregate_node_payload(aggregation_kind="sum"))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_aggregate_numeric_field_missing", bind_error_codes(raised.exception))

    def test_bind_rejects_uninherited_same_team_constraint(self) -> None:
        payload = json.loads(CAR_BUNDLE_PATH.read_text(encoding="utf-8"))["documents"]["home"]
        payload = copy.deepcopy(payload)
        for node in payload["draft_plan"]["nodes"]:
            if node.get("node_id") == "typed_join_2":
                node["parameters"]["same_team_perspective_required"]["value"] = False
        payload["draft_plan"]["nodes"].append(aggregate_node_payload(same_team_required=True))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_aggregate_constraint_not_inherited", bind_error_codes(raised.exception))


if __name__ == "__main__":
    unittest.main()
