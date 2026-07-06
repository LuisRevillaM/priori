from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from scripts.coverage_map import compiler_search_reachability as search
from scripts.packets import scp2_1_roundtrip_generator as roundtrip_generator
from tqe.runtime.binder import bind_document
from tqe.runtime.ir import stable_hash
from tqe.runtime.ir import TacticalQueryDocument
from tqe.semantic_compiler.meaning_expression import (
    BridgeRefusalKind,
    CompositionConstraint,
    MissingGapCodeError,
    load_meaning_expression_from_path,
    load_meaning_expression_result,
    load_pack_vocabulary,
    render_meaning_sentence,
    stable_expression_json,
)
from tqe.semantic_compiler.target_synthesis import (
    document_payload_for_expression,
    synthesize_and_bind,
    synthesize_search_target,
    validate_correspondence_with_r1c_guard,
)


FIXTURE_DIR = Path("delivery/packets/scp2-1-roundtrip/meaning-expressions")
R2_4_FIXTURE_DIR = Path("delivery/packets/r2-4-flagship/meaning-expressions")


class SCP2MeaningToTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = load_pack_vocabulary()
        cls.coverage_rows = json.loads(Path("generated/coverage-map.json").read_text(encoding="utf-8"))

    def test_vocabulary_and_composition_grammar_are_derived_from_generated_pack(self) -> None:
        self.assertEqual(37, len(self.vocabulary.primitive_names))
        self.assertEqual(8, len(self.vocabulary.predicate_operator_names))
        self.assertEqual(8, len(self.vocabulary.composition_operator_names))
        self.assertEqual(15, len(self.vocabulary.constraint_kinds))
        self.assertEqual(14, len(self.vocabulary.gap_codes))
        self.assertIn("carry_episode", self.vocabulary.primitive_names)
        self.assertIn("gte", self.vocabulary.predicate_operator_names)
        self.assertIn("aggregate_over", self.vocabulary.composition_operator_names)
        self.assertIn("sequence_pattern", self.vocabulary.composition_operator_names)
        self.assertIn("typed_join", self.vocabulary.constraint_kinds)
        self.assertIn("window", self.vocabulary.constraint_kinds)
        self.assertIn("sequence_pattern", self.vocabulary.constraint_kinds)
        self.assertIn("possession_continuity_source", self.vocabulary.constraint_kind_parameters["sequence_pattern"])
        self.assertIn("BODY_ORIENTATION", self.vocabulary.gap_codes)

    def test_out_of_pack_reference_returns_exact_typed_gap_payload(self) -> None:
        result = load_meaning_expression_from_path(
            FIXTURE_DIR / "body_orientation_oov.v0.json",
            vocabulary=self.vocabulary,
        )

        self.assertEqual("refused", result.outcome)
        self.assertIsNotNone(result.refusal)
        self.assertEqual(BridgeRefusalKind.UNDERSTOOD_BUT_NOT_EXPRESSIBLE, result.refusal.outcome)
        self.assertEqual("BODY_ORIENTATION", result.refusal.gap_code)
        self.assertEqual("concept:body_orientation", result.refusal.missing_capability)
        self.assertEqual("body_orientation", result.refusal.reference)
        self.assertEqual("concept_refs", result.refusal.vocabulary_section)

    def test_out_of_pack_operator_without_truthful_gap_code_raises(self) -> None:
        payload = self.fixture_payload("fragile_possession_state_known.v0.json")
        payload["operator_applications"][0]["operator"] = "made_up_operator"

        with self.assertRaises(MissingGapCodeError):
            load_meaning_expression_result(payload, vocabulary=self.vocabulary)

    def test_out_of_pack_parameter_without_truthful_gap_code_raises(self) -> None:
        payload = self.fixture_payload("fragile_possession_state_known.v0.json")
        payload["operator_applications"][0]["parameters"][0]["name"] = "made_up_parameter"

        with self.assertRaises(MissingGapCodeError):
            load_meaning_expression_result(payload, vocabulary=self.vocabulary)

    def test_out_of_pack_field_without_truthful_gap_code_raises(self) -> None:
        payload = self.fixture_payload("fragile_possession_state_known.v0.json")
        payload["target_contract"]["required_evidence"].append("made_up_field")

        with self.assertRaises(MissingGapCodeError):
            load_meaning_expression_result(payload, vocabulary=self.vocabulary)

    def test_out_of_pack_constraint_kind_without_truthful_gap_code_raises(self) -> None:
        payload = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        payload["target_contract"]["composition_constraints"][0]["kind"] = "made_up_constraint"

        with self.assertRaises(MissingGapCodeError):
            load_meaning_expression_result(payload, vocabulary=self.vocabulary)

    def test_out_of_pack_constraint_field_without_truthful_gap_code_raises(self) -> None:
        payload = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        for parameter in payload["target_contract"]["composition_constraints"][0]["parameters"]:
            if parameter["name"] == "status_field":
                parameter["value"] = "made_up_field"
                break

        with self.assertRaises(MissingGapCodeError):
            load_meaning_expression_result(payload, vocabulary=self.vocabulary)

    def test_free_form_constraint_dict_is_rejected_by_schema(self) -> None:
        payload = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        payload["target_contract"]["composition_constraints"][0]["freeform"] = {"kind": "decoy"}

        with self.assertRaises(ValidationError):
            load_meaning_expression_result(payload, vocabulary=self.vocabulary)

    def test_constraints_are_typed_models_not_free_form_dicts(self) -> None:
        expression = self.accepted_expression("fragile_window_join_count_novel.v0.json")

        constraint = expression.target_contract.composition_constraints[0]

        self.assertIsInstance(constraint, CompositionConstraint)
        self.assertEqual("aggregate_over", constraint.kind)

    def test_scratch_pack_mutation_removing_primitive_trips_vocabulary_gate(self) -> None:
        payload = json.loads(Path("generated/tactical-knowledge-pack.json").read_text(encoding="utf-8"))
        payload["primitives"] = [
            item for item in payload["primitives"] if item["name"] != "controlled_pass_episode"
        ]
        payload["primitives"].append({"name": "scratch_replacement", "outputs": [], "parameters": []})
        with tempfile.TemporaryDirectory() as tmp:
            pack_path = Path(tmp) / "pack.json"
            pack_path.write_text(json.dumps(payload), encoding="utf-8")
            mutated = load_pack_vocabulary(pack_path)

            with self.assertRaises(MissingGapCodeError):
                load_meaning_expression_from_path(
                    FIXTURE_DIR / "fragile_possession_state_known.v0.json",
                    vocabulary=mutated,
                )

    def test_schema_round_trip_is_hash_stable(self) -> None:
        result = load_meaning_expression_from_path(
            FIXTURE_DIR / "fragile_possession_state_known.v0.json",
            vocabulary=self.vocabulary,
        )
        self.assertIsNotNone(result.expression)

        dumped = stable_expression_json(result.expression)
        reparsed = load_meaning_expression_result(dumped, vocabulary=self.vocabulary)

        self.assertIsNotNone(reparsed.expression)
        self.assertEqual(result.expression.document_hash(), reparsed.expression.document_hash())
        self.assertEqual(stable_hash(json.loads(dumped)), result.expression.document_hash())

    def test_synthesized_target_passes_r1c_guard_and_preserves_row_identity(self) -> None:
        expression = self.accepted_expression("fragile_possession_state_known.v0.json")

        target = synthesize_search_target(expression)
        declaration = validate_correspondence_with_r1c_guard(target)

        self.assertEqual(expression.concept_identity, target["concept"])
        self.assertEqual(expression.concept_identity, declaration["coverage_row"])
        self.assertEqual(render_meaning_sentence(expression), declaration["meaning"])
        self.assertNotIn("verdict", declaration)

    def test_synthesized_target_rejects_mutated_correspondence_row(self) -> None:
        expression = self.accepted_expression("fragile_possession_state_known.v0.json")
        target = synthesize_search_target(expression)
        mutated = copy.deepcopy(target)
        mutated["semantic_correspondence"]["coverage_row"] = "other_row"

        with self.assertRaisesRegex(ValueError, "coverage_row does not match"):
            validate_correspondence_with_r1c_guard(mutated)

    def test_renderer_makes_target_contract_name_free_even_when_text_echoes_concept(self) -> None:
        payload = self.fixture_payload("fragile_possession_state_known.v0.json")
        concept = payload["concept_identity"]
        payload["meaning_clauses"][0]["value"] = concept
        payload["target_contract"]["claim_boundary"] = (
            f"{concept} appears in free text but must not reach the contract body."
        )
        result = load_meaning_expression_result(payload, vocabulary=self.vocabulary)
        self.assertEqual("accepted", result.outcome)
        self.assertIsNotNone(result.expression)

        target = synthesize_search_target(result.expression)

        contract_json = json.dumps(target["target_contract"], sort_keys=True).lower()
        self.assertNotIn(concept, contract_json)
        self.assertFalse(search.concept_name_used_as_hint(target))
        self.assertEqual(concept, target["semantic_correspondence"]["coverage_row"])
        self.assertIn(concept, target["semantic_correspondence"]["meaning"])

    def test_ledger_write_path_is_unreachable_from_bridge_code(self) -> None:
        with patch.dict(os.environ, {"TQE_WRITE": "0", "TQE_SEARCH_UPDATE_LEDGER": "0"}):
            with self.assertRaises(PermissionError):
                search.update_coverage_rows([], [])

    def test_roundtrip_generator_rejects_requested_evidence_failures(self) -> None:
        execution = SimpleNamespace(
            status=SimpleNamespace(value="incomplete"),
            provenance={"requested_evidence_failure_count": 1},
        )
        executor = SimpleNamespace(execute=lambda _bound: execution)
        with patch.object(roundtrip_generator, "TacticalQueryExecutor", return_value=executor):
            with patch.object(roundtrip_generator.TacticalQueryDocument, "model_validate", return_value=object()):
                with patch.object(roundtrip_generator, "bind_document", return_value=object()):
                    with patch.object(roundtrip_generator, "execution_result_rows", return_value=[]):
                        with self.assertRaisesRegex(RuntimeError, "requested evidence failures"):
                            roundtrip_generator.execute_document({"schema_version": "1.0"})

    def test_binder_accepts_synthesized_known_target_and_matches_committed_hash(self) -> None:
        expression = self.accepted_expression("fragile_possession_state_known.v0.json")

        synthesized = synthesize_and_bind(expression, coverage_rows=self.coverage_rows)

        row = next(row for row in self.coverage_rows if row.get("concept") == "fragile_possession_state")
        expected_hash = row["compiler_reachability_evidence"]["document_hash"]
        self.assertEqual("PASS", synthesized["bind"]["status"])
        self.assertEqual(expected_hash, synthesized["document_hash"])

    def test_typed_join_synthesis_does_not_emit_inactive_missing_field_defaults(self) -> None:
        contract = {
            "desired_output": "classification",
            "required_evidence": [
                "typed_join_status",
                "left_anchor_id",
                "right_anchor_id",
                "left_frame_id",
                "right_frame_id",
            ],
            "required_modalities": [],
            "status_semantics": [{"field": "typed_join_status", "required_value": "PASS"}],
            "claim_boundary": "Bind regression only.",
            "composition_constraints": [
                {
                    "kind": "typed_join",
                    "join_key": "same_anchor",
                    "no_match_policy": "UNKNOWN",
                    "same_team_perspective_required": False,
                    "entity_identity_preserved_required": False,
                    "frame_alignment_required": True,
                    "left_required_fields": ["anchor_id", "anchor_frame_id"],
                    "right_required_fields": ["anchor_id", "anchor_frame_id"],
                }
            ],
        }
        target = {
            "target_id": "be_011_fragile_possession_state_bind_regression",
            "concept": "fragile_possession_state",
            "held_out": True,
            "multi_step": True,
            "semantic_correspondence": {
                "coverage_row": "fragile_possession_state",
                "meaning": "regression",
                "composition": "typed_join",
                "claim_boundary": "Bind regression only.",
            },
            "target_contract": contract,
        }

        build = search.synthesize_by_search(
            target=target,
            row={"concept": "fragile_possession_state"},
            context=search.SearchContext(
                catalog=search.CatalogIndex(),
                target_contract=contract,
            ),
        )
        join_node = next(
            node
            for node in build["document"]["draft_plan"]["nodes"]
            if node.get("operator", {}).get("name") == "typed_join"
        )

        for parameter in (
            "left_start_frame_field",
            "left_end_frame_field",
            "right_start_frame_field",
            "right_end_frame_field",
        ):
            self.assertEqual("none", join_node["parameters"][parameter]["value"])
        self.assertEqual("anchor_id", join_node["parameters"]["left_anchor_id_field"]["value"])
        self.assertEqual("anchor_frame_id", join_node["parameters"]["left_frame_field"]["value"])

        bind_document(TacticalQueryDocument.model_validate(build["document"]))

    def test_binder_accepts_novel_in_grammar_composition(self) -> None:
        expression = self.accepted_expression("fragile_window_join_count_novel.v0.json")

        synthesized = synthesize_and_bind(expression, coverage_rows=self.coverage_rows)

        self.assertEqual("PASS", synthesized["bind"]["status"])
        self.assertEqual("operator:aggregate_over", synthesized["build"]["terminal_provider"])
        self.assertEqual("scp2_1_fragile_window_join_count", synthesized["target"]["concept"])
        self.assertEqual(
            "scp2_1_fragile_window_join_count",
            synthesized["target"]["semantic_correspondence"]["coverage_row"],
        )

    def test_r2_4_sequence_expression_uses_search_not_committed_certified_plan_ref(self) -> None:
        result = load_meaning_expression_from_path(
            R2_4_FIXTURE_DIR / "counterattack_initiation_sequence_rate.v0.json",
            vocabulary=self.vocabulary,
        )
        self.assertEqual("accepted", result.outcome)
        self.assertIsNotNone(result.expression)

        synthesized = synthesize_and_bind(result.expression, coverage_rows=self.coverage_rows)

        self.assertEqual("PASS", synthesized["bind"]["status"])
        self.assertEqual("operator:rate", synthesized["build"]["terminal_provider"])
        self.assertIn("provider_field_backward_search", synthesized["build"]["rules_used"])
        self.assertIn("rate_operator_composition", synthesized["build"]["rules_used"])
        self.assertIn("sequence_pattern_operator_composition", synthesized["build"]["rules_used"])
        self.assertIsNone(synthesized["document"].get("plan_id"))
        self.assertIsNone(synthesized["document"].get("recipe_id"))
        for document in synthesized["document"]["documents"].values():
            rate_requests = [
                item
                for item in document["draft_plan"]["requested_evidence"]
                if item["source"]["source_node_id"] == "rate"
                and item["source"]["output_name"] == "rate_records"
            ]
            self.assertIn("source_records", {item["field"] for item in rate_requests})

    def test_recipe_id_does_not_bypass_search_with_exact_plan_ref(self) -> None:
        pack = json.loads(Path("generated/tactical-knowledge-pack.json").read_text(encoding="utf-8"))
        recipe = next(
            item for item in pack["recipes"] if item["recipe_id"] == "line_break_support_response_v1"
        )
        payload = self.recipe_expression_payload(recipe)
        result = load_meaning_expression_result(payload, vocabulary=self.vocabulary)
        self.assertEqual("accepted", result.outcome)
        self.assertIsNotNone(result.expression)

        with self.assertRaises(search.SynthesisError):
            synthesize_and_bind(result.expression, coverage_rows=self.coverage_rows)

    def test_single_provider_overcomposition_is_not_silently_elided(self) -> None:
        payload = self.controlled_pass_variant_payload("settled_completed_pass_retained_control")
        payload["operator_applications"] = [{"operator": "typed_join", "parameters": []}]
        payload["target_contract"]["composition_constraints"] = [{"kind": "typed_join", "parameters": []}]
        result = load_meaning_expression_result(payload, vocabulary=self.vocabulary)
        self.assertEqual("accepted", result.outcome)
        self.assertIsNotNone(result.expression)

        with self.assertRaisesRegex(search.SynthesisError, "No registered operator composition"):
            synthesize_and_bind(result.expression, coverage_rows=self.coverage_rows)

    def test_empty_expression_periods_fall_back_to_canonical_periods(self) -> None:
        payload = self.controlled_pass_variant_payload("settled_completed_pass_retained_control")
        payload["population"]["periods"] = []
        result = load_meaning_expression_result(payload, vocabulary=self.vocabulary)
        self.assertEqual("accepted", result.outcome)
        self.assertIsNotNone(result.expression)

        document = document_payload_for_expression(
            expression=result.expression,
            document={
                "default_invocation": {
                    "schema_version": "1.0",
                    "invocation_id": "fixture_probe",
                    "match_ids": [],
                    "periods": [],
                    "perspective_team_role": "home",
                    "parameters": {},
                    "max_results": 20,
                    "execution_mode": "execute",
                }
            },
        )

        self.assertEqual("compiler_search_perspective_bundle.v1", document["schema_version"])
        for role_document in document["documents"].values():
            self.assertEqual(["firstHalf", "secondHalf"], role_document["default_invocation"]["periods"])

    @staticmethod
    def controlled_pass_variant_payload(identity: str) -> dict:
        return {
            "schema_version": "meaning_expression.v0",
            "expression_id": identity,
            "expression_version": "0.1.0",
            "concept_identity": identity,
            "display_name": "Settled Completed Pass Retained Control",
            "meaning_clauses": [
                {
                    "subject": "controlled_pass_episode",
                    "action": "requires",
                    "field": "controlled_pass_status",
                    "operator": "eq",
                    "value": "PASS",
                }
            ],
            "concept_refs": ["controlled_pass_episode"],
            "operator_applications": [],
            "population": {
                "match_ids": [],
                "periods": ["firstHalf", "secondHalf"],
                "perspective_team_roles": ["home", "away"],
            },
            "group_by": [],
            "target": {
                "target_id": f"{identity}_v0",
                "held_out": True,
                "multi_step": False,
            },
            "target_contract": {
                "desired_output": "classification",
                "required_evidence": ["pass_episode_id", "controlled_pass_status"],
                "required_modalities": ["events", "tracking"],
                "status_semantics": [
                    {"field": "controlled_pass_status", "operator": "eq", "required_value": "PASS"}
                ],
                "composition_constraints": [],
                "claim_boundary": "Observed controlled pass status only.",
            },
            "correspondence_clauses": [
                {"name": "claim_boundary", "value": "single provider should satisfy this request"}
            ],
        }

    def accepted_expression(self, name: str):
        result = load_meaning_expression_from_path(FIXTURE_DIR / name, vocabulary=self.vocabulary)
        self.assertEqual("accepted", result.outcome)
        self.assertIsNotNone(result.expression)
        return result.expression

    @staticmethod
    def recipe_expression_payload(recipe: dict) -> dict:
        fields = []
        for evidence in recipe["authoring_contract"]["requested_evidence"]:
            field = evidence["field"]
            if field not in fields:
                fields.append(field)
        status_semantics = [
            {
                "field": predicate["input"]["output_name"],
                "operator": predicate["operator"]["name"],
                "required_value": (predicate.get("compare") or {}).get("value"),
            }
            for predicate in recipe["authoring_contract"]["required_predicates"]
        ]
        refs = []
        for node in recipe["authoring_contract"]["authorable_nodes"]:
            ref = node["catalog_ref"]
            if ref not in refs:
                refs.append(ref)
        base_id = recipe["recipe_id"].removesuffix("_v1")
        return {
            "schema_version": "meaning_expression.v0",
            "expression_id": base_id,
            "expression_version": "0.1.0",
            "concept_identity": base_id,
            "display_name": recipe["display_name"],
            "meaning_clauses": [
                {
                    "subject": "recipe",
                    "action": "requires",
                    "field": status_semantics[0]["field"],
                    "operator": status_semantics[0]["operator"],
                    "value": status_semantics[0]["required_value"],
                }
            ],
            "concept_refs": refs,
            "operator_applications": [],
            "population": {
                "match_ids": ["J03WOY"],
                "periods": ["firstHalf", "secondHalf"],
                "perspective_team_roles": ["home"],
            },
            "group_by": [],
            "target": {
                "target_id": f"{base_id}_v0",
                "held_out": True,
                "multi_step": True,
            },
            "target_contract": {
                "desired_output": "classification",
                "required_evidence": fields,
                "required_modalities": ["events", "tracking"],
                "status_semantics": status_semantics,
                "composition_constraints": [],
                "claim_boundary": "Observed recipe-backed evidence only.",
            },
            "correspondence_clauses": [
                {"name": "recipe_id", "value": recipe["recipe_id"]},
                {"name": "claim_boundary", "value": "generated exact typed plan reference"},
            ],
        }

    @staticmethod
    def fixture_payload(name: str) -> dict:
        return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
