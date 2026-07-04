from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tqe.runtime.binder import BindError, bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import CatalogOutput, MissingDataSemantics, TacticalQueryDocument, TypedValue
from tqe.runtime.operators.delta_across_anchor import (
    DELTA_ACROSS_ANCHOR_SIGNATURE,
    execute_delta_across_anchor,
)
from tqe.runtime.values import RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def typed_number(value: float) -> TypedValue:
    return TypedValue(payload_type="number", value=value)


def anchor_record(anchor_id: str, frame_id: int) -> dict[str, object]:
    item: dict[str, object] = {
        "anchor_id": anchor_id,
        "match_id": "TST",
        "period": "firstHalf",
        "anchor_frame_id": frame_id,
        "start_frame_id": frame_id,
        "end_frame_id": frame_id,
    }
    item["anchor_id"] = canonical_anchor_record_id(item)
    return item


def evaluation_record(anchor: dict[str, object], value: float, status: str = "PASS") -> dict[str, object]:
    return {
        **anchor,
        "pressure_status": status,
        "nearest_defender_distance_m": value,
    }


def runtime_records_value(name: str, records: list[dict[str, object]]) -> RuntimeValue:
    output = DELTA_ACROSS_ANCHOR_SIGNATURE.inputs[0]
    return runtime_value_from_raw(
        node_id=name,
        output=CatalogOutput(
            name="anchor_evaluations",
            temporal_type=output.temporal_type,
            payload_type=output.payload_type,
            cardinality=output.cardinality,
            unit=output.unit,
            entity_scope=output.entity_scope,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=["anchor_id", "anchor_frame_id", "pressure_status", "nearest_defender_distance_m"],
        ),
        raw_value=records,
        frame_ids=[int(record["anchor_frame_id"]) for record in records],
        records=records,
    )


def operator_node() -> SimpleNamespace:
    return SimpleNamespace(
        node_id="delta",
        inputs={
            "anchors": SimpleNamespace(source_node_id="anchors", output_name="anchor_evaluations"),
            "before_evaluations": SimpleNamespace(source_node_id="before", output_name="anchor_evaluations"),
            "after_evaluations": SimpleNamespace(source_node_id="after", output_name="anchor_evaluations"),
        },
    )


def run_delta(
    *,
    anchors: list[dict[str, object]],
    before: list[dict[str, object]],
    after: list[dict[str, object]],
    edge_threshold: float = 1.0,
    hysteresis_margin: float = 0.0,
    before_status_field: str = "pressure_status",
    after_status_field: str = "pressure_status",
) -> dict[str, object]:
    state = SimpleNamespace(match_id="TST", period="firstHalf", signals={})
    execute_delta_across_anchor(
        state=state,
        node=operator_node(),
        inputs={
            "anchors": runtime_records_value("anchors", anchors),
            "before_evaluations": runtime_records_value("before", before),
            "after_evaluations": runtime_records_value("after", after),
        },
        parameters={
            "before_value_field": typed_enum("nearest_defender_distance_m"),
            "after_value_field": typed_enum("nearest_defender_distance_m"),
            "before_status_field": typed_enum(before_status_field),
            "after_status_field": typed_enum(after_status_field),
            "required_status_value": typed_enum("PASS"),
            "edge_threshold": typed_number(edge_threshold),
            "hysteresis_margin": typed_number(hysteresis_margin),
            "value_unit": typed_enum("metre"),
            "missing_evidence_policy": typed_enum("unknown"),
        },
    )
    return state.signals["delta"]


class DeltaAcrossAnchorTests(unittest.TestCase):
    def test_signed_delta_and_edges_at_threshold(self) -> None:
        rising = anchor_record("rise", 10)
        falling = anchor_record("fall", 20)

        signals = run_delta(
            anchors=[rising, falling],
            before=[evaluation_record(rising, 0.8), evaluation_record(falling, 2.0)],
            after=[evaluation_record(rising, 1.0), evaluation_record(falling, 1.0)],
        )

        records = signals["delta_records"]
        self.assertEqual([0.2, -1.0], [record["signed_delta"] for record in records])
        self.assertEqual(["PASS", "FAIL"], [record["rising_edge_status"] for record in records])
        self.assertEqual(["FAIL", "PASS"], [record["falling_edge_status"] for record in records])

    def test_hysteresis_suppresses_threshold_flicker(self) -> None:
        anchor = anchor_record("flicker", 10)

        signals = run_delta(
            anchors=[anchor],
            before=[evaluation_record(anchor, 0.95)],
            after=[evaluation_record(anchor, 1.0)],
            edge_threshold=1.0,
            hysteresis_margin=0.1,
        )

        record = signals["delta_records"][0]
        self.assertEqual("PASS", record["delta_status"])
        self.assertEqual("FAIL", record["rising_edge_status"])
        self.assertEqual("rising_edge_not_observed", record["rising_edge_reason"])

    def test_missing_after_record_is_unknown(self) -> None:
        anchor = anchor_record("missing", 10)

        signals = run_delta(
            anchors=[anchor],
            before=[evaluation_record(anchor, 0.8)],
            after=[],
        )

        record = signals["delta_records"][0]
        self.assertEqual("UNKNOWN", record["delta_status"])
        self.assertEqual("before_or_after_record_missing", record["delta_reason"])
        self.assertEqual("UNKNOWN", record["rising_edge_status"])

    def test_source_status_failure_stays_fail_not_unknown(self) -> None:
        anchor = anchor_record("fail", 10)

        signals = run_delta(
            anchors=[anchor],
            before=[evaluation_record(anchor, 0.8, status="FAIL")],
            after=[evaluation_record(anchor, 1.2)],
        )

        record = signals["delta_records"][0]
        self.assertEqual("FAIL", record["delta_status"])
        self.assertEqual("before_required_status_not_met", record["delta_reason"])
        self.assertEqual("FAIL", record["rising_edge_status"])

    def test_bind_rejects_field_parameter_not_declared_by_inputs(self) -> None:
        payload = delta_pressure_document()
        payload["draft_plan"]["nodes"][3]["parameters"]["before_value_field"]["value"] = "missing_field"

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_field_parameter_not_in_input", str(raised.exception))

    def test_bind_and_execute_pressure_distance_delta(self) -> None:
        document = TacticalQueryDocument.model_validate(delta_pressure_document())

        bound = bind_document(document)
        execution = TacticalQueryExecutor(enable_node_cache=False).execute(bound)
        rows = execution_result_rows(execution)

        self.assertGreater(len(rows), 0)
        self.assertEqual(0, execution.provenance["requested_evidence_failure_count"])
        evidence = rows[0]["requested_evidence"]
        self.assertEqual("PASS", evidence["delta_status"])
        self.assertEqual("nearest_defender_distance_m", evidence["before_value_field"])
        self.assertEqual("nearest_defender_distance_m", evidence["after_value_field"])
        self.assertEqual("none", evidence["before_status_field"])
        self.assertEqual("metre", evidence["value_unit"])
        self.assertIsInstance(evidence["signed_delta"], float)


def delta_pressure_document() -> dict[str, object]:
    outputs = [output.model_dump(mode="json") for output in DELTA_ACROSS_ANCHOR_SIGNATURE.outputs]
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": "r1_2_delta_across_anchor_probe",
            "recipe_version": "0.1.0",
            "display_name": "R1-2 delta across anchor probe",
            "description": "Nearest-defender distance delta from pass release to reception.",
            "parameters": [],
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [
                "Observed before/after nearest-defender-distance delta across a controlled-pass anchor only."
            ],
            "disallowed_claims": [
                "The system inferred pressure quality, tactical causation, defender intent, or pass value."
            ],
            "limitations": ["Operator acceptance probe."],
            "output_classifications": ["R1_2_DELTA_ACROSS_ANCHOR"],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": "r1_2_delta_across_anchor_probe",
            "match_ids": ["J03WOY"],
            "periods": ["firstHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 5,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": "r1_2_delta_across_anchor_probe",
            "plan_version": "0.1.0",
            "recipe_id": "r1_2_delta_across_anchor_probe",
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
                    "node_id": "release_pressure",
                    "catalog_ref": "pressure_on_carrier",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"}
                    },
                    "parameters": {
                        "frame_field": {"payload_type": "enum", "value": "physical_release_frame_id"},
                        "carrier_id_field": {"payload_type": "enum", "value": "receiver_id"},
                        "maximum_pressure_distance_m": {"payload_type": "number", "unit": "metre", "value": 15.0},
                        "minimum_closing_speed_mps": {"payload_type": "number", "unit": "none", "value": -5.0},
                        "maximum_approach_angle_degrees": {"payload_type": "number", "unit": "none", "value": 180.0},
                        "minimum_pressure_duration_seconds": {"payload_type": "number", "unit": "second", "value": 0.0},
                        "lookback_seconds": {"payload_type": "number", "unit": "second", "value": 0.4},
                        "candidate_scope": {"payload_type": "enum", "value": "defending_outfield"},
                    },
                },
                {
                    "kind": "relation",
                    "node_id": "reception_pressure",
                    "catalog_ref": "pressure_on_carrier",
                    "version": "0.1.0",
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"}
                    },
                    "parameters": {
                        "frame_field": {"payload_type": "enum", "value": "controlled_reception_frame_id"},
                        "carrier_id_field": {"payload_type": "enum", "value": "receiver_id"},
                        "maximum_pressure_distance_m": {"payload_type": "number", "unit": "metre", "value": 15.0},
                        "minimum_closing_speed_mps": {"payload_type": "number", "unit": "none", "value": -5.0},
                        "maximum_approach_angle_degrees": {"payload_type": "number", "unit": "none", "value": 180.0},
                        "minimum_pressure_duration_seconds": {"payload_type": "number", "unit": "second", "value": 0.0},
                        "lookback_seconds": {"payload_type": "number", "unit": "second", "value": 0.4},
                        "candidate_scope": {"payload_type": "enum", "value": "defending_outfield"},
                    },
                },
                {
                    "kind": "operator",
                    "node_id": "pressure_distance_delta",
                    "operator": {"name": "delta_across_anchor", "version": "0.1.0"},
                    "inputs": {
                        "anchors": {"source_node_id": "controlled_pass", "output_name": "anchors"},
                        "before_evaluations": {
                            "source_node_id": "release_pressure",
                            "output_name": "anchor_evaluations",
                        },
                        "after_evaluations": {
                            "source_node_id": "reception_pressure",
                            "output_name": "anchor_evaluations",
                        },
                    },
                    "parameters": {
                        "before_value_field": {"payload_type": "enum", "value": "nearest_defender_distance_m"},
                        "after_value_field": {"payload_type": "enum", "value": "nearest_defender_distance_m"},
                        "before_status_field": {"payload_type": "enum", "value": "none"},
                        "after_status_field": {"payload_type": "enum", "value": "none"},
                        "required_status_value": {"payload_type": "enum", "value": "PASS"},
                        "edge_threshold": {"payload_type": "number", "unit": "none", "value": 4.0},
                        "hysteresis_margin": {"payload_type": "number", "unit": "none", "value": 0.0},
                        "value_unit": {"payload_type": "enum", "value": "metre"},
                        "missing_evidence_policy": {"payload_type": "enum", "value": "unknown"},
                    },
                    "outputs": outputs,
                },
                {
                    "kind": "predicate",
                    "node_id": "delta_observed",
                    "input": {"source_node_id": "pressure_distance_delta", "output_name": "delta_status"},
                    "operator": {"name": "eq", "version": "1.0.0"},
                    "compare": {"payload_type": "enum", "value": "PASS"},
                },
            ],
            "classification_rules": [
                {
                    "label": "R1_2_DELTA_ACROSS_ANCHOR",
                    "predicate_ids": ["delta_observed"],
                    "description": "Observed nearest-defender distance delta exists across the anchor.",
                }
            ],
            "anchor_source": {"source_node_id": "pressure_distance_delta", "output_name": "delta_records"},
            "requested_evidence": [
                {
                    "source": {"source_node_id": "pressure_distance_delta", "output_name": "delta_records"},
                    "field": field,
                    "alias": field,
                    "required": True,
                }
                for field in (
                    "delta_status",
                    "delta_reason",
                    "before_value_field",
                    "after_value_field",
                    "before_status_field",
                    "after_status_field",
                    "before_value",
                    "after_value",
                    "signed_delta",
                    "value_unit",
                    "witness_before_node_id",
                    "witness_after_node_id",
                )
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
