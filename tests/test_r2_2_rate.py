from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tqe.runtime.executor import RuntimeAnchor, evidence_value_for_anchor
from tqe.runtime.binder import BindError, bind_document, bind_error_codes
from tqe.runtime.ir import CatalogOutput, MissingDataSemantics, TacticalQueryDocument, TypedValue
from tqe.runtime.operators.rate import (
    RATE_SIGNATURE,
    RateIntervalResult,
    execute_rate,
)
from tqe.runtime.values import RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw


CAR_BUNDLE_PATH = Path("tests/fixtures/r1_5_fragile_possession_state_j03woh_bundle.json")


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def typed_bool(value: bool) -> TypedValue:
    return TypedValue(payload_type="boolean", value=value)


def typed_entity_set(values: list[str]) -> TypedValue:
    return TypedValue(payload_type="entity_set", value=values)


def rate_record(
    frame_id: int,
    *,
    team_role: str,
    numerator_status: str,
    denominator_status: str,
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
        "numerator_status": numerator_status,
        "denominator_status": denominator_status,
    }
    record["anchor_id"] = canonical_anchor_record_id(record)
    return record


def population_value(records: list[dict[str, object]]) -> RuntimeValue:
    input_def = {item.name: item for item in RATE_SIGNATURE.inputs}["denominator"]
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
                "numerator_status",
                "denominator_status",
            ],
        ),
        raw_value=records,
        records=records,
    )


def rate_output_value(records: list[dict[str, object]]) -> RuntimeValue:
    output = RATE_SIGNATURE.outputs[0]
    return runtime_value_from_raw(
        node_id="rate",
        output=CatalogOutput(
            name=output.name,
            temporal_type=output.temporal_type,
            payload_type=output.payload_type,
            cardinality=output.cardinality,
            unit=output.unit,
            entity_scope=output.entity_scope,
            missing_data_semantics=output.missing_data_semantics,
            evidence_fields=list(output.evidence_fields),
        ),
        raw_value=records,
        records=records,
    )


def runtime_anchor_for_record(record: dict[str, object]) -> RuntimeAnchor:
    return RuntimeAnchor(
        anchor_id=str(record["anchor_id"]),
        semantic_key=str(record["anchor_id"]),
        match_id=str(record["match_id"]),
        period=str(record["period"]),
        anchor_frame_id=int(record["anchor_frame_id"]),
        source_node_id="sequence_pattern",
        output_name="chain_records",
        start_frame_id=int(record["start_frame_id"]),
        end_frame_id=int(record["end_frame_id"]),
        attributes=dict(record),
    )


def rate_node() -> SimpleNamespace:
    return SimpleNamespace(
        node_id="rate",
        inputs={
            "numerator": SimpleNamespace(source_node_id="typed_join_2", output_name="typed_join_records"),
            "denominator": SimpleNamespace(source_node_id="typed_join_2", output_name="typed_join_records"),
        },
    )


def run_rate(
    records: list[dict[str, object]],
    *,
    group_by_fields: list[str] | None = None,
) -> list[dict[str, object]]:
    state = SimpleNamespace(match_id="TST", period="firstHalf", perspective_team_role="home", signals={})
    value = population_value(records)
    execute_rate(
        state=state,
        node=rate_node(),
        inputs={"numerator": value, "denominator": value},
        parameters={
            "rate_kind": typed_enum("rate"),
            "population_expression": typed_enum("retention rate in fragile situations"),
            "group_by_fields": typed_entity_set(group_by_fields or ["left_team_role", "match_id"]),
            "numerator_status_field": typed_enum("numerator_status"),
            "denominator_status_field": typed_enum("denominator_status"),
            "subset_declaration": typed_enum("same source relation; numerator adds retention predicate"),
            "subset_predicate_fields": typed_entity_set(["numerator_status"]),
            "removed_denominator_predicate_fields": typed_entity_set([]),
            "same_team_perspective_required": typed_bool(True),
            "entity_identity_preserved_required": typed_bool(True),
            "frame_alignment_required": typed_bool(True),
            "constraint_opt_out_reason": typed_enum("none"),
            "team_role_field": typed_enum("left_team_role"),
        },
    )
    return state.signals["rate"]["rate_records"]


def rate_node_payload(
    *,
    node_id: str = "rate",
    numerator_source: str = "typed_join_2",
    denominator_source: str = "typed_join_2",
    numerator_output: str = "typed_join_records",
    denominator_output: str = "typed_join_records",
    removed_predicates: list[str] | None = None,
    group_by_fields: list[str] | None = None,
    same_team_required: bool = True,
    entity_required: bool = False,
    frame_required: bool = True,
    constraint_opt_out_reason: str = "entity identity is not part of the fragile-condition retention denominator",
    include_constraint_parameters: bool = True,
) -> dict[str, object]:
    parameters = {
        "rate_kind": {"payload_type": "enum", "value": "rate"},
        "population_expression": {
            "payload_type": "enum",
            "value": "retention rate in fragile situations",
        },
        "group_by_fields": {
            "payload_type": "entity_set",
            "value": group_by_fields or ["perspective_team_role", "match_id"],
        },
        "numerator_status_field": {"payload_type": "enum", "value": "typed_join_status"},
        "denominator_status_field": {"payload_type": "enum", "value": "right_status"},
        "subset_declaration": {
            "payload_type": "enum",
            "value": "typed_join_status is the final retained fragile subset over the right-side fragile condition",
        },
        "subset_predicate_fields": {"payload_type": "entity_set", "value": ["window_status"]},
        "removed_denominator_predicate_fields": {
            "payload_type": "entity_set",
            "value": removed_predicates or [],
        },
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
        "node_id": node_id,
        "operator": {"name": "rate", "version": "0.1.0"},
        "inputs": {
            "numerator": {"source_node_id": numerator_source, "output_name": numerator_output},
            "denominator": {"source_node_id": denominator_source, "output_name": denominator_output},
        },
        "parameters": parameters,
        "outputs": [output.model_dump(mode="json") for output in RATE_SIGNATURE.outputs],
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


class RateOperatorTests(unittest.TestCase):
    def test_joint_partition_bounds_use_spec_formula(self) -> None:
        records = [
            rate_record(100, team_role="home", numerator_status="PASS", denominator_status="PASS"),
            rate_record(110, team_role="home", numerator_status="FAIL", denominator_status="PASS"),
            rate_record(120, team_role="home", numerator_status="UNKNOWN", denominator_status="PASS"),
            rate_record(130, team_role="home", numerator_status="FAIL", denominator_status="UNKNOWN"),
            rate_record(140, team_role="home", numerator_status="UNKNOWN", denominator_status="UNKNOWN"),
            rate_record(150, team_role="home", numerator_status="FAIL", denominator_status="FAIL"),
        ]

        [result] = run_rate(records)

        self.assertEqual(1, result["a_count"])
        self.assertEqual(1, result["b_count"])
        self.assertEqual(1, result["c_count"])
        self.assertEqual(1, result["d1_count"])
        self.assertEqual(1, result["d2_count"])
        self.assertEqual(1, result["e_count"])
        self.assertEqual(0.5, result["observed"])
        self.assertEqual(0.2, result["lower_bound"])
        self.assertEqual(0.75, result["upper_bound"])
        self.assertEqual(2, result["observed_denominator_count"])
        self.assertEqual(3, result["numerator_count_interval"]["upper_bound"])
        self.assertEqual(5, result["denominator_count_interval"]["upper_bound"])

    def test_c_partition_is_not_in_observed_denominator(self) -> None:
        [result] = run_rate(
            [
                rate_record(100, team_role="home", numerator_status="PASS", denominator_status="PASS"),
                rate_record(110, team_role="home", numerator_status="FAIL", denominator_status="PASS"),
                rate_record(120, team_role="home", numerator_status="UNKNOWN", denominator_status="PASS"),
            ]
        )

        self.assertEqual(0.5, result["observed"])
        self.assertEqual(2, result["observed_denominator_count"])

    def test_d1_partition_remains_in_lower_bound_denominator(self) -> None:
        [result] = run_rate(
            [
                rate_record(100, team_role="home", numerator_status="PASS", denominator_status="PASS"),
                rate_record(110, team_role="home", numerator_status="FAIL", denominator_status="PASS"),
                rate_record(120, team_role="home", numerator_status="FAIL", denominator_status="UNKNOWN"),
            ]
        )

        self.assertEqual(1 / 3, result["lower_bound"])

    def test_num_pass_with_den_fail_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "numerator PASS with denominator FAIL"):
            run_rate([rate_record(100, team_role="home", numerator_status="PASS", denominator_status="FAIL")])

    def test_num_pass_with_den_unknown_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "numerator PASS with denominator UNKNOWN"):
            run_rate([rate_record(100, team_role="home", numerator_status="PASS", denominator_status="UNKNOWN")])

    def test_signature_declares_rate_as_only_rate_kind(self) -> None:
        [rate_kind] = [parameter for parameter in RATE_SIGNATURE.parameters if parameter.name == "rate_kind"]

        self.assertEqual(["rate"], rate_kind.allowed_values)

    def test_signature_does_not_advertise_share_key_field(self) -> None:
        parameter_names = {parameter.name for parameter in RATE_SIGNATURE.parameters}

        self.assertNotIn("share_key_field", parameter_names)

    def test_constructor_refuses_external_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "computed internally"):
            RateIntervalResult(
                rate_kind="rate",
                population_expression="fixture",
                group_key={"team": "home"},
                a_count=1,
                b_count=0,
                c_count=0,
                d1_count=0,
                d2_count=0,
                e_count=0,
                lower_bound=0,
            )

    def test_constructor_enforces_interval_ordering_invariant(self) -> None:
        with mock.patch(
            "tqe.runtime.operators.rate._rate_interval_from_partition",
            return_value=("PASS", 0.9, 0.1, 0.8),
        ):
            with self.assertRaisesRegex(ValueError, "lower_bound <= observed <= upper_bound"):
                RateIntervalResult(
                    rate_kind="rate",
                    population_expression="fixture",
                    group_key={"team": "home"},
                    a_count=1,
                    b_count=0,
                    c_count=0,
                    d1_count=0,
                    d2_count=0,
                    e_count=0,
                )

    def test_degenerate_denominator_yields_typed_unknown(self) -> None:
        [result] = run_rate(
            [
                rate_record(100, team_role="home", numerator_status="FAIL", denominator_status="FAIL"),
                rate_record(110, team_role="home", numerator_status="UNKNOWN", denominator_status="FAIL"),
            ]
        )

        self.assertEqual("UNKNOWN", result["rate_status"])
        self.assertIsNone(result["observed"])
        self.assertIsNone(result["lower_bound"])
        self.assertIsNone(result["upper_bound"])

    def test_d1_only_population_is_unknown_with_zero_bounds(self) -> None:
        [result] = run_rate(
            [
                rate_record(100, team_role="home", numerator_status="FAIL", denominator_status="UNKNOWN"),
                rate_record(110, team_role="home", numerator_status="FAIL", denominator_status="UNKNOWN"),
            ]
        )

        self.assertEqual("UNKNOWN", result["rate_status"])
        self.assertIsNone(result["observed"])
        self.assertEqual(0, result["lower_bound"])
        self.assertEqual(0, result["upper_bound"])
        self.assertEqual(2, result["d1_count"])

    def test_empty_population_emits_typed_unknown_row(self) -> None:
        [result] = run_rate([])

        self.assertEqual("UNKNOWN", result["rate_status"])
        self.assertIsNone(result["observed"])
        self.assertIsNone(result["lower_bound"])
        self.assertIsNone(result["upper_bound"])
        self.assertEqual({"left_team_role": "UNKNOWN", "match_id": "TST"}, result["group_key"])
        self.assertEqual(0, result["denominator_count_interval"]["population_count"])

    def test_group_by_keys_preserve_both_team_perspectives(self) -> None:
        records = [
            rate_record(100, team_role="home", numerator_status="PASS", denominator_status="PASS"),
            rate_record(110, team_role="home", numerator_status="FAIL", denominator_status="PASS"),
            rate_record(120, team_role="away", numerator_status="PASS", denominator_status="PASS"),
            rate_record(130, team_role="away", numerator_status="UNKNOWN", denominator_status="UNKNOWN"),
        ]

        results = run_rate(records, group_by_fields=["left_team_role", "match_id"])
        by_team = {record["group_key"]["left_team_role"]: record for record in results}

        self.assertEqual({"home", "away"}, set(by_team))
        self.assertEqual(2, by_team["home"]["denominator_count_interval"]["population_count"])
        self.assertEqual(2, by_team["away"]["denominator_count_interval"]["population_count"])
        self.assertEqual(1, by_team["away"]["d2_count"])

    def test_rate_record_projects_interval_to_source_chain_anchor(self) -> None:
        records = [
            rate_record(100, team_role="home", numerator_status="PASS", denominator_status="PASS"),
            rate_record(110, team_role="home", numerator_status="FAIL", denominator_status="PASS"),
        ]
        [result] = run_rate(records)
        anchor = runtime_anchor_for_record(records[0])

        self.assertEqual(records, result["source_records"])
        self.assertEqual(0.5, evidence_value_for_anchor(runtime_value=rate_output_value([result]), anchor=anchor, field="observed"))
        self.assertEqual(0.5, evidence_value_for_anchor(runtime_value=rate_output_value([result]), anchor=anchor, field="lower_bound"))
        self.assertEqual(0.5, evidence_value_for_anchor(runtime_value=rate_output_value([result]), anchor=anchor, field="upper_bound"))

    def test_bind_accepts_declared_flagship_rate(self) -> None:
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(rate_node_payload())

        bound = bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertEqual("rate", bound.nodes[-1].node_id)

    def test_bind_rejects_different_source_relations(self) -> None:
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(rate_node_payload(numerator_source="window"))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_rate_subset_source_mismatch", bind_error_codes(raised.exception))

    def test_bind_rejects_removed_denominator_predicates(self) -> None:
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(rate_node_payload(removed_predicates=["pressure_status"]))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_rate_subset_removed_predicate", bind_error_codes(raised.exception))

    def test_bind_rejects_perspective_grouping_without_same_team_lineage(self) -> None:
        payload = car_payload()
        for node in payload["draft_plan"]["nodes"]:
            if node.get("node_id") == "typed_join_2":
                node["parameters"]["same_team_perspective_required"]["value"] = False
        payload["draft_plan"]["nodes"].append(
            rate_node_payload(
                same_team_required=False,
                constraint_opt_out_reason="diagnostic perspective grouping opt-out test",
            )
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_rate_perspective_group_requires_same_team", bind_error_codes(raised.exception))

    def test_bind_defaults_constraints_to_true(self) -> None:
        payload = car_payload()
        payload["draft_plan"]["nodes"].append(rate_node_payload(include_constraint_parameters=False))

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_rate_constraint_not_inherited", bind_error_codes(raised.exception))

    def test_malformed_population_raises(self) -> None:
        empty_population = population_value([])
        malformed = RuntimeValue(output=empty_population.output, value=[1], records=[])

        with self.assertRaisesRegex(ValueError, "list of objects"):
            execute_rate(
                state=SimpleNamespace(match_id="TST", period="firstHalf", signals={}),
                node=rate_node(),
                inputs={"numerator": malformed, "denominator": malformed},
                parameters={
                    "rate_kind": typed_enum("rate"),
                    "population_expression": typed_enum("fixture"),
                    "group_by_fields": typed_entity_set(["left_team_role", "match_id"]),
                    "numerator_status_field": typed_enum("numerator_status"),
                    "denominator_status_field": typed_enum("denominator_status"),
                    "subset_declaration": typed_enum("same source relation"),
                    "subset_predicate_fields": typed_entity_set([]),
                    "removed_denominator_predicate_fields": typed_entity_set([]),
                            "same_team_perspective_required": typed_bool(True),
                    "entity_identity_preserved_required": typed_bool(True),
                    "frame_alignment_required": typed_bool(True),
                    "constraint_opt_out_reason": typed_enum("none"),
                    "team_role_field": typed_enum("left_team_role"),
                },
            )


if __name__ == "__main__":
    unittest.main()
