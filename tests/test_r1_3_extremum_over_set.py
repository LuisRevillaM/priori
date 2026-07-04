from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.coverage_map import compiler_search_reachability as search
from tqe.runtime.binder import BindError, bind_document, bind_error_codes
from tqe.runtime.capabilities import teamshape_family
from tqe.runtime.ir import CatalogOutput, MissingDataSemantics, TacticalQueryDocument, TypedValue
from tqe.runtime.operators.extremum_over_set import (
    EXTREMUM_OVER_SET_SIGNATURE,
    execute_extremum_over_set,
)
from tqe.runtime.values import RuntimeValue, canonical_anchor_record_id, runtime_value_from_raw


PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
R1_3_TARGET_PATH = Path("config/compiler-reachability/r1-3-extremum-over-set-targets.v0.json")


def typed_enum(value: str) -> TypedValue:
    return TypedValue(payload_type="enum", value=value)


def typed_number(value: float) -> TypedValue:
    return TypedValue(payload_type="number", value=value)


def candidate(
    *,
    anchor_id: str = "a",
    record_id: str,
    entity_id: str,
    value: float | None,
    frame_id: int = 10,
    status: str = "PASS",
    coverage: str = "COMPLETE",
    subject_id: str = "carrier",
) -> dict[str, object]:
    item: dict[str, object] = {
        "match_id": "TST",
        "period": "firstHalf",
        "anchor_frame_id": frame_id,
        "start_frame_id": frame_id,
        "end_frame_id": frame_id,
        "entity_refs": [subject_id, entity_id],
        "source_anchor_id": anchor_id,
        "candidate_record_id": record_id,
        "candidate_entity_id": entity_id,
        "candidate_frame_id": frame_id,
        "candidate_distance_m": value,
        "candidate_status": status,
        "coverage_status": coverage,
        "subject_player_id": subject_id,
    }
    item["anchor_id"] = canonical_anchor_record_id(item)
    return item


def candidate_value(records: list[dict[str, object]]) -> RuntimeValue:
    input_def = EXTREMUM_OVER_SET_SIGNATURE.inputs[0]
    output = CatalogOutput(
        name="candidate_records",
        temporal_type=input_def.temporal_type,
        payload_type=input_def.payload_type,
        cardinality=input_def.cardinality,
        unit=input_def.unit,
        entity_scope=input_def.entity_scope,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
        evidence_fields=[
            "anchor_id",
            "source_anchor_id",
            "anchor_frame_id",
            "candidate_record_id",
            "candidate_entity_id",
            "candidate_frame_id",
            "candidate_distance_m",
            "candidate_status",
            "coverage_status",
            "subject_player_id",
        ],
    )
    return runtime_value_from_raw(
        node_id="candidates",
        output=output,
        raw_value=records,
        frame_ids=[int(record["anchor_frame_id"]) for record in records],
        records=records,
    )


def relation_candidate_value(records: list[dict[str, object]]) -> RuntimeValue:
    input_def = EXTREMUM_OVER_SET_SIGNATURE.inputs[0]
    output = CatalogOutput(
        name="anchor_evaluations",
        temporal_type=input_def.temporal_type,
        payload_type=input_def.payload_type,
        cardinality=input_def.cardinality,
        unit=input_def.unit,
        entity_scope=input_def.entity_scope,
        missing_data_semantics=MissingDataSemantics.UNKNOWN,
        evidence_fields=[
            "anchor_id",
            "source_anchor_id",
            "anchor_frame_id",
            "candidate_record_id",
            "candidate_defender_id",
            "candidate_frame_id",
            "candidate_distance_m",
            "defender_distance_candidate_status",
            "coverage_status",
            "target_player_id",
        ],
    )
    return runtime_value_from_raw(
        node_id="defender_distance_candidate_set",
        output=output,
        raw_value=records,
        frame_ids=[int(record["anchor_frame_id"]) for record in records],
        records=records,
    )


def operator_node() -> SimpleNamespace:
    return SimpleNamespace(
        node_id="extremum",
        inputs={"candidates": SimpleNamespace(source_node_id="source", output_name="candidate_records")},
    )


def run_extremum(
    records: list[dict[str, object]],
    *,
    selection_mode: str = "argmin",
    top_k: int = 1,
    value_bound_kind: str = "lower",
    value_bound: float = 0.0,
) -> dict[str, object]:
    state = SimpleNamespace(match_id="TST", period="firstHalf", signals={})
    execute_extremum_over_set(
        state=state,
        node=operator_node(),
        inputs={"candidates": candidate_value(records)},
        parameters={
            "selection_mode": typed_enum(selection_mode),
            "top_k": typed_number(float(top_k)),
            "value_field": typed_enum("candidate_distance_m"),
            "value_unit": typed_enum("metre"),
            "record_id_field": typed_enum("candidate_record_id"),
            "entity_id_field": typed_enum("candidate_entity_id"),
            "frame_field": typed_enum("candidate_frame_id"),
            "anchor_id_field": typed_enum("source_anchor_id"),
            "subject_id_field": typed_enum("subject_player_id"),
            "status_field": typed_enum("candidate_status"),
            "required_status_value": typed_enum("PASS"),
            "coverage_status_field": typed_enum("coverage_status"),
            "coverage_policy": typed_enum("unknown_if_incomplete_could_change_answer"),
            "value_bound_kind": typed_enum(value_bound_kind),
            "value_bound": typed_number(value_bound),
            "tie_breaker_field": typed_enum("candidate_entity_id"),
            "secondary_tie_breaker_field": typed_enum("candidate_record_id"),
            "missing_evidence_policy": typed_enum("unknown"),
        },
    )
    return state.signals["extremum"]


class ExtremumOverSetTests(unittest.TestCase):
    def test_signature_fields_are_known_to_search(self) -> None:
        signature_fields = {
            field
            for output in EXTREMUM_OVER_SET_SIGNATURE.outputs
            for field in [output.name, *output.evidence_fields]
        }
        self.assertEqual(signature_fields, search.EXTREMUM_OVER_SET_FIELDS)

    def test_argmin_tie_uses_declared_breakers_and_is_shuffle_stable(self) -> None:
        records = [
            candidate(record_id="r-b", entity_id="def-b", value=3.0),
            candidate(record_id="r-a", entity_id="def-a", value=3.0),
            candidate(record_id="r-c", entity_id="def-c", value=5.0),
        ]

        first = run_extremum(records)["extremum_selection_records"][0]
        second = run_extremum(list(reversed(records)))["extremum_selection_records"][0]

        self.assertEqual("PASS", first["extremum_selection_status"])
        self.assertEqual("def-a", first["selected_entity_id"])
        self.assertEqual(first["selected_entity_id"], second["selected_entity_id"])
        self.assertEqual(first["selected_record_id"], second["selected_record_id"])

    def test_incomplete_set_is_pass_when_lower_bound_proves_argmin(self) -> None:
        records = [
            candidate(record_id="zero", entity_id="def-zero", value=0.0),
            candidate(record_id="missing", entity_id="def-x", value=None, status="UNKNOWN", coverage="INCOMPLETE"),
        ]

        selected = run_extremum(records)["extremum_selection_records"][0]

        self.assertEqual("PASS", selected["extremum_selection_status"])
        self.assertEqual("incomplete_set_cannot_improve_argmin", selected["extremum_selection_reason"])
        self.assertEqual("def-zero", selected["selected_entity_id"])

    def test_incomplete_set_is_unknown_when_missing_candidate_could_improve_argmin(self) -> None:
        records = [
            candidate(record_id="near", entity_id="def-near", value=2.0),
            candidate(record_id="missing", entity_id="def-x", value=None, status="UNKNOWN", coverage="INCOMPLETE"),
        ]

        selected = run_extremum(records)["extremum_selection_records"][0]

        self.assertEqual("UNKNOWN", selected["extremum_selection_status"])
        self.assertEqual("incomplete_set_could_change_argmin", selected["extremum_selection_reason"])
        self.assertIsNone(selected["selected_entity_id"])

    def test_top_k_coverage_decides_against_kth_ranked_value(self) -> None:
        records = [
            candidate(record_id="best", entity_id="def-best", value=0.0),
            candidate(record_id="second", entity_id="def-second", value=3.0),
            candidate(record_id="missing", entity_id="def-x", value=None, status="UNKNOWN", coverage="INCOMPLETE"),
        ]

        selected = run_extremum(records, top_k=2)["extremum_selection_records"][0]

        self.assertEqual("UNKNOWN", selected["extremum_selection_status"])
        self.assertEqual("incomplete_set_could_change_argmin", selected["extremum_selection_reason"])
        self.assertIsNone(selected["selected_entity_id"])

    def test_top_k_larger_than_valid_set_is_unknown(self) -> None:
        selected = run_extremum(
            [
                candidate(record_id="one", entity_id="def-one", value=1.0),
                candidate(record_id="two", entity_id="def-two", value=2.0),
            ],
            top_k=3,
        )["extremum_selection_records"][0]

        self.assertEqual("UNKNOWN", selected["extremum_selection_status"])
        self.assertEqual("top_k_exceeds_valid_candidate_count", selected["extremum_selection_reason"])

    def test_selected_witness_threads_record_entity_and_frame(self) -> None:
        selected = run_extremum(
            [
                candidate(record_id="far", entity_id="def-far", value=9.0, frame_id=20),
                candidate(record_id="near", entity_id="def-near", value=1.5, frame_id=21),
            ]
        )["extremum_selection_records"][0]

        self.assertEqual("near", selected["selected_record_id"])
        self.assertEqual("def-near", selected["selected_entity_id"])
        self.assertEqual(21, selected["selected_frame_id"])
        self.assertEqual(21, selected["anchor_frame_id"])
        self.assertIsNotNone(selected["selected_source_record_hash"])
        self.assertEqual("subject_player_id", selected["subject_id_field"])
        self.assertEqual("carrier", selected["subject_id"])

    def test_relation_composition_selects_defending_side_for_both_anchor_teams(self) -> None:
        originals = {
            "outfield_player_ids": teamshape_family.outfield_player_ids,
            "tracked_point_at_frame": teamshape_family.tracked_point_at_frame,
            "player_records_at_frame_for_team": teamshape_family.player_records_at_frame_for_team,
        }

        def fake_outfield_player_ids(_root: object, _match_id: str, team_role: str) -> set[str]:
            return {"home-near", "home-far"} if team_role == "home" else {"away-near", "away-far"}

        def fake_tracked_point_at_frame(_state: object, _frame_id: int, player_id: str) -> tuple[float, float] | None:
            return {
                "home-target": (0.0, 0.0),
                "away-target": (10.0, 0.0),
            }.get(player_id)

        def fake_player_records_at_frame_for_team(_state: object, _frame_id: int, team_role: str) -> list[dict[str, object]]:
            if team_role == "home":
                return [
                    {"player_id": "home-near", "x_m": 9.0, "y_m": 0.0},
                    {"player_id": "home-far", "x_m": 20.0, "y_m": 0.0},
                ]
            return [
                {"player_id": "away-near", "x_m": 1.0, "y_m": 0.0},
                {"player_id": "away-far", "x_m": -20.0, "y_m": 0.0},
            ]

        try:
            teamshape_family.outfield_player_ids = fake_outfield_player_ids
            teamshape_family.tracked_point_at_frame = fake_tracked_point_at_frame
            teamshape_family.player_records_at_frame_for_team = fake_player_records_at_frame_for_team
            state = SimpleNamespace(canonical_root=Path("."), match_id="TST", period="firstHalf")
            relation_records: list[dict[str, object]] = []
            for anchor in (
                {
                    "anchor_id": "home-anchor",
                    "anchor_frame_id": 100,
                    "controlled_reception_frame_id": 100,
                    "receiver_id": "home-target",
                    "team_role": "home",
                    "controlled_pass_status": "PASS",
                },
                {
                    "anchor_id": "away-anchor",
                    "anchor_frame_id": 200,
                    "controlled_reception_frame_id": 200,
                    "receiver_id": "away-target",
                    "team_role": "away",
                    "controlled_pass_status": "PASS",
                },
            ):
                relation_records.extend(
                    teamshape_family.defender_distance_candidate_records(
                        state=state,
                        anchor=anchor,
                        anchor_frame_field="controlled_reception_frame_id",
                        target_player_id_field="receiver_id",
                        candidate_scope="observed_defending_outfield",
                        required_anchor_status_field="controlled_pass_status",
                        required_anchor_status_value="PASS",
                        minimum_observed_candidates=1,
                        default_defending_team_role="away",
                    )
                )
        finally:
            for name, value in originals.items():
                setattr(teamshape_family, name, value)

        operator_state = SimpleNamespace(match_id="TST", period="firstHalf", signals={})
        execute_extremum_over_set(
            state=operator_state,
            node=operator_node(),
            inputs={"candidates": relation_candidate_value(relation_records)},
            parameters={
                "selection_mode": typed_enum("argmin"),
                "top_k": typed_number(1.0),
                "value_field": typed_enum("candidate_distance_m"),
                "value_unit": typed_enum("metre"),
                "record_id_field": typed_enum("candidate_record_id"),
                "entity_id_field": typed_enum("candidate_defender_id"),
                "frame_field": typed_enum("candidate_frame_id"),
                "anchor_id_field": typed_enum("source_anchor_id"),
                "subject_id_field": typed_enum("target_player_id"),
                "status_field": typed_enum("defender_distance_candidate_status"),
                "required_status_value": typed_enum("PASS"),
                "coverage_status_field": typed_enum("coverage_status"),
                "coverage_policy": typed_enum("unknown_if_incomplete_could_change_answer"),
                "value_bound_kind": typed_enum("lower"),
                "value_bound": typed_number(0.0),
                "tie_breaker_field": typed_enum("candidate_defender_id"),
                "secondary_tie_breaker_field": typed_enum("candidate_record_id"),
                "missing_evidence_policy": typed_enum("unknown"),
            },
        )
        selected = {
            record["source_anchor_id"]: record["selected_entity_id"]
            for record in operator_state.signals["extremum"]["extremum_selection_records"]
        }

        self.assertEqual("away-near", selected["home-anchor"])
        self.assertEqual("home-near", selected["away-anchor"])

    def test_binder_rejects_unbound_operator_field_parameter(self) -> None:
        payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        source_node_id = payload["draft_plan"]["nodes"][0]["node_id"]
        source_output = "anchors"
        payload["draft_plan"]["nodes"].append(
            {
                "kind": "operator",
                "node_id": "extremum",
                "operator": {"name": "extremum_over_set", "version": "0.1.0"},
                "inputs": {"candidates": {"source_node_id": source_node_id, "output_name": source_output}},
                "parameters": {
                    "selection_mode": {"payload_type": "enum", "value": "argmin"},
                    "value_field": {"payload_type": "enum", "value": "not_declared"},
                    "record_id_field": {"payload_type": "enum", "value": "anchor_id"},
                    "entity_id_field": {"payload_type": "enum", "value": "anchor_id"},
                    "frame_field": {"payload_type": "enum", "value": "anchor_frame_id"},
                    "tie_breaker_field": {"payload_type": "enum", "value": "anchor_id"},
                },
                "outputs": [
                    output.model_dump(mode="json")
                    for output in EXTREMUM_OVER_SET_SIGNATURE.outputs
                ],
            }
        )

        with self.assertRaises(BindError) as raised:
            bind_document(TacticalQueryDocument.model_validate(payload))

        self.assertIn("operator_field_parameter_not_in_input", bind_error_codes(raised.exception))

    def test_search_target_declares_semantic_correspondence(self) -> None:
        target_payload = json.loads(R1_3_TARGET_PATH.read_text(encoding="utf-8"))
        [target] = target_payload["targets"]
        self.assertEqual("nearest_defender_relation", target["concept"])
        self.assertEqual(
            "defender_distance_candidate_set.anchor_evaluations + extremum_over_set argmin(candidate_distance_m)",
            target["semantic_correspondence"]["source_relation"],
        )

    def test_search_synthesis_fails_on_provider_pinning_constraint_keys(self) -> None:
        target = copy.deepcopy(json.loads(R1_3_TARGET_PATH.read_text(encoding="utf-8"))["targets"][0])
        target["target_contract"]["composition_constraints"][1]["source_provider"] = "defender_distance_candidate_set"
        target["target_contract"]["composition_constraints"][1]["source_output"] = "anchor_evaluations"
        context = search.SearchContext(
            catalog=search.CatalogIndex(),
            target_contract=target["target_contract"],
        )
        required_fields = search.required_target_fields(target["target_contract"])

        with self.assertRaises(search.SynthesisError) as raised:
            search.build_operator_composition(context, required_fields, depth=0)

        self.assertEqual("missing_constraint", raised.exception.taxonomy)
        payload = json.dumps(raised.exception.details, sort_keys=True)
        self.assertIn("unapplied_extremum_constraint_keys", payload)
        self.assertIn("source_provider", payload)
        self.assertIn("source_output", payload)

    def test_provider_name_hint_guard_catches_constraint_value_channel(self) -> None:
        payload = json.loads(R1_3_TARGET_PATH.read_text(encoding="utf-8"))
        [target] = payload["targets"]
        self.assertFalse(search.provider_name_used_as_hint(target))

        hinted = copy.deepcopy(target)
        hinted["target_contract"]["composition_constraints"][1]["source_provider"] = "defender_distance_candidate_set"

        self.assertTrue(search.provider_name_used_as_hint(hinted))


if __name__ == "__main__":
    unittest.main()
