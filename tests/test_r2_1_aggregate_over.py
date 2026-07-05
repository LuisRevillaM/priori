from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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
    perspective_team_role: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "match_id": match_id,
        "period": period,
        "perspective_team_role": perspective_team_role or team_role,
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
                "perspective_team_role",
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
            "same_team_perspective_required": typed_bool(True),
            "entity_identity_preserved_required": typed_bool(True),
            "frame_alignment_required": typed_bool(True),
            "constraint_opt_out_reason": typed_enum("none"),
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
            "same_team_perspective_required": typed_bool(True),
            "entity_identity_preserved_required": typed_bool(True),
            "frame_alignment_required": typed_bool(True),
            "constraint_opt_out_reason": typed_enum("none"),
            "team_role_field": typed_enum("perspective_team_role"),
        },
    )
    return state.signals["aggregate"]["aggregate_records"]


def aggregate_node_payload(
    *,
    same_team_required: bool = True,
    entity_required: bool = False,
    frame_required: bool = True,
    constraint_opt_out_reason: str = "entity identity is not part of the CAR-0 count denominator",
    group_by_fields: list[str] | None = None,
    aggregation_kind: str = "count",
    include_constraint_parameters: bool = True,
) -> dict[str, object]:
    declared_group_by_fields = group_by_fields or ["perspective_team_role", "match_id"]
    parameters = {
        "aggregation_kind": {"payload_type": "enum", "value": aggregation_kind},
        "population_expression": {"payload_type": "enum", "value": "fragile_possession_state rows"},
        "group_by_fields": {"payload_type": "entity_set", "value": declared_group_by_fields},
        "status_field": {"payload_type": "enum", "value": "typed_join_status"},
        "team_role_field": {"payload_type": "enum", "value": "perspective_team_role"},
    }
    if include_constraint_parameters:
        parameters.update(
            {
                "same_team_perspective_required": {"payload_type": "boolean", "value": same_team_required},
                "entity_identity_preserved_required": {"payload_type": "boolean", "value": entity_required},
                "frame_alignment_required": {"payload_type": "boolean", "value": frame_required},
                "constraint_opt_out_reason": {"payload_type": "enum", "value": constraint_opt_out_reason},
            }
        )
    return {
        "kind": "operator",
        "node_id": "aggregate",
        "operator": {"name": "aggregate_over", "version": "0.1.0"},
        "inputs": {
            "population": {"source_node_id": "typed_join_2", "output_name": "typed_join_records"},
        },
        "parameters": parameters,
        "outputs": [output.model_dump(mode="json") for output in AGGREGATE_OVER_SIGNATURE.outputs],
    }


def car_payload(role: str = "home") -> dict[str, object]:
    payload = json.loads(CAR_BUNDLE_PATH.read_text(encoding="utf-8"))["documents"][role]
    payload = copy.deepcopy(payload)
    declare_typed_join_identity_fields(payload)
    return payload


def declare_typed_join_identity_fields(payload: dict[str, object]) -> None:
    fields = ["match_id", "period", "perspective_team_role"]
    for node in payload["draft_plan"]["nodes"]:
        if not isinstance(node, dict) or node.get("node_id") != "typed_join_2":
            continue
        for output in node.get("outputs", []):
            evidence_fields = output.setdefault("evidence_fields", [])
            for field in fields:
                if field not in evidence_fields:
                    evidence_fields.insert(0, field)


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
                pass_count=1,
                fail_count=0,
                unknown_count=0,
                lower_bound=0,
            )

    def test_constructor_enforces_interval_ordering_invariant(self) -> None:
        with mock.patch(
            "tqe.runtime.operators.aggregate_over._count_interval",
            return_value=(2.0, 3.0, 4.0),
        ):
            with self.assertRaisesRegex(ValueError, "lower_bound <= observed <= upper_bound"):
                AggregateIntervalResult(
                    aggregation_kind="count",
                    population_expression="fixture",
                    group_key={"team": "home"},
                    pass_count=2,
                    fail_count=0,
                    unknown_count=1,
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
        expected_population_by_team = {
            role: sum(1 for record in records if record["left_team_role"] == role)
            for role in {"home", "away"}
        }
        expected_unknown_by_team = {
            role: sum(
                1
                for record in records
                if record["left_team_role"] == role and record["typed_join_status"] == "UNKNOWN"
            )
            for role in {"home", "away"}
        }

        self.assertEqual(set(expected_population_by_team), set(by_team))
        for team_role, expected_population in expected_population_by_team.items():
            self.assertEqual(expected_population, by_team[team_role]["population_count"])
            self.assertEqual(expected_unknown_by_team[team_role], by_team[team_role]["unknown_count"])

    def test_perspective_team_role_can_be_declared_group_key(self) -> None:
        records = [
            aggregate_record(100, team_role="home", status="PASS", perspective_team_role="away"),
            aggregate_record(110, team_role="away", status="UNKNOWN", perspective_team_role="away"),
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
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(aggregate_node_payload())

        bound = bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertEqual("aggregate", bound.nodes[-1].node_id)

    def test_bind_rejects_grouping_fields_missing_from_source_declaration(self) -> None:
        payload = json.loads(CAR_BUNDLE_PATH.read_text(encoding="utf-8"))["documents"]["home"]
        payload = copy.deepcopy(payload)
        payload["draft_plan"]["nodes"].append(aggregate_node_payload())

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_field_parameter_not_in_input", bind_error_codes(raised.exception))

    def test_bind_rejects_undeclared_group_by_field(self) -> None:
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(
            aggregate_node_payload(group_by_fields=["left_team_role", "not_a_declared_field"])
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_field_parameter_not_in_input", bind_error_codes(raised.exception))

    def test_signature_declares_count_as_only_aggregation_kind(self) -> None:
        [aggregation_kind] = [
            parameter
            for parameter in AGGREGATE_OVER_SIGNATURE.parameters
            if parameter.name == "aggregation_kind"
        ]

        self.assertEqual(["count"], aggregation_kind.allowed_values)

    def test_bind_rejects_sum_aggregation_kind(self) -> None:
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(aggregate_node_payload(aggregation_kind="sum"))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("parameter_value_not_allowed", bind_error_codes(raised.exception))

    def test_bind_defaults_constraints_to_true(self) -> None:
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(aggregate_node_payload(include_constraint_parameters=False))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_aggregate_constraint_not_inherited", bind_error_codes(raised.exception))

    def test_bind_rejects_constraint_opt_out_without_reason(self) -> None:
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(aggregate_node_payload(constraint_opt_out_reason="none"))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn(
            "operator_aggregate_constraint_opt_out_reason_missing",
            bind_error_codes(raised.exception),
        )

    def test_bind_rejects_perspective_grouping_without_same_team_lineage(self) -> None:
        payload = car_payload()
        for node in payload["draft_plan"]["nodes"]:
            if node.get("node_id") == "typed_join_2":
                node["parameters"]["same_team_perspective_required"]["value"] = False
        payload["draft_plan"]["nodes"].append(
            aggregate_node_payload(
                same_team_required=False,
                entity_required=False,
                frame_required=True,
                constraint_opt_out_reason="diagnostic perspective grouping opt-out test",
            )
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn(
            "operator_aggregate_perspective_group_requires_same_team",
            bind_error_codes(raised.exception),
        )

    def test_bind_rejects_missing_population_upstream(self) -> None:
        payload = car_payload()
        node = aggregate_node_payload()
        node["inputs"]["population"]["source_node_id"] = "missing_node"
        payload["draft_plan"]["nodes"].append(node)

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_aggregate_population_upstream_missing", bind_error_codes(raised.exception))

    def test_bind_rejects_uninherited_same_team_constraint(self) -> None:
        payload = car_payload()
        for node in payload["draft_plan"]["nodes"]:
            if node.get("node_id") == "typed_join_2":
                node["parameters"]["same_team_perspective_required"]["value"] = False
        payload["draft_plan"]["nodes"].append(
            aggregate_node_payload(group_by_fields=["left_team_role", "match_id"], same_team_required=True)
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_aggregate_constraint_not_inherited", bind_error_codes(raised.exception))

    def test_malformed_population_raises(self) -> None:
        empty_population = population_value([])
        malformed = RuntimeValue(output=empty_population.output, value=[1], records=[])

        with self.assertRaisesRegex(ValueError, "list of objects"):
            execute_aggregate_over(
                state=SimpleNamespace(match_id="TST", period="firstHalf", signals={}),
                node=aggregate_node(),
                inputs={"population": malformed},
                parameters={
                    "aggregation_kind": typed_enum("count"),
                    "population_expression": typed_enum("fixture"),
                    "group_by_fields": typed_entity_set(["left_team_role", "match_id"]),
                    "status_field": typed_enum("typed_join_status"),
                    "same_team_perspective_required": typed_bool(True),
                    "entity_identity_preserved_required": typed_bool(True),
                    "frame_alignment_required": typed_bool(True),
                    "constraint_opt_out_reason": typed_enum("none"),
                    "team_role_field": typed_enum("left_team_role"),
                },
            )


if __name__ == "__main__":
    unittest.main()
