from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tqe.runtime.ir import stable_hash
from tqe.semantic_compiler.meaning_expression import (
    BridgeRefusalKind,
    load_meaning_expression_from_path,
    load_meaning_expression_result,
    load_pack_vocabulary,
    stable_expression_json,
)
from tqe.semantic_compiler.target_synthesis import (
    LedgerWriteForbiddenError,
    synthesize_and_bind,
    synthesize_search_target,
    update_coverage_rows,
    validate_correspondence_with_r1c_guard,
)


FIXTURE_DIR = Path("delivery/packets/scp2-1-roundtrip/meaning-expressions")


class SCP2MeaningToTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = load_pack_vocabulary()
        cls.coverage_rows = json.loads(Path("generated/coverage-map.json").read_text(encoding="utf-8"))

    def test_vocabulary_counts_are_derived_from_generated_pack(self) -> None:
        self.assertEqual(37, len(self.vocabulary.primitive_names))
        self.assertEqual(8, len(self.vocabulary.operator_names))
        self.assertEqual(14, len(self.vocabulary.gap_codes))
        self.assertIn("carry_episode", self.vocabulary.primitive_names)
        self.assertIn("gte", self.vocabulary.operator_names)
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

    def test_out_of_pack_operator_is_typed_gap_not_generic_error(self) -> None:
        payload = self.fixture_payload("carry_progression_known.v0.json")
        payload["operator_applications"][0]["operator"] = "made_up_operator"

        result = load_meaning_expression_result(payload, vocabulary=self.vocabulary)

        self.assertEqual("refused", result.outcome)
        self.assertIsNotNone(result.refusal)
        self.assertEqual("operator:made_up_operator", result.refusal.missing_capability)
        self.assertEqual("operator_applications.operator", result.refusal.vocabulary_section)

    def test_out_of_pack_parameter_is_typed_gap_not_generic_error(self) -> None:
        payload = self.fixture_payload("carry_progression_known.v0.json")
        payload["operator_applications"][0]["parameters"][0]["name"] = "made_up_parameter"

        result = load_meaning_expression_result(payload, vocabulary=self.vocabulary)

        self.assertEqual("refused", result.outcome)
        self.assertIsNotNone(result.refusal)
        self.assertEqual("parameter:made_up_parameter", result.refusal.missing_capability)
        self.assertEqual("operator_applications.parameters", result.refusal.vocabulary_section)

    def test_out_of_pack_field_is_typed_gap_not_generic_error(self) -> None:
        payload = self.fixture_payload("carry_progression_known.v0.json")
        payload["target_contract"]["required_evidence"].append("made_up_field")

        result = load_meaning_expression_result(payload, vocabulary=self.vocabulary)

        self.assertEqual("refused", result.outcome)
        self.assertIsNotNone(result.refusal)
        self.assertEqual("field:made_up_field", result.refusal.missing_capability)
        self.assertEqual("target_contract.required_evidence", result.refusal.vocabulary_section)

    def test_scratch_pack_mutation_removing_primitive_trips_vocabulary_gate(self) -> None:
        payload = json.loads(Path("generated/tactical-knowledge-pack.json").read_text(encoding="utf-8"))
        payload["primitives"] = [
            item for item in payload["primitives"] if item["name"] != "carry_episode"
        ]
        payload["primitives"].append({"name": "scratch_replacement", "outputs": [], "parameters": []})
        with tempfile.TemporaryDirectory() as tmp:
            pack_path = Path(tmp) / "pack.json"
            pack_path.write_text(json.dumps(payload), encoding="utf-8")
            mutated = load_pack_vocabulary(pack_path)
            result = load_meaning_expression_from_path(
                FIXTURE_DIR / "carry_progression_known.v0.json",
                vocabulary=mutated,
            )

        self.assertEqual("refused", result.outcome)
        self.assertIsNotNone(result.refusal)
        self.assertEqual("concept:carry_episode", result.refusal.missing_capability)

    def test_schema_round_trip_is_hash_stable(self) -> None:
        result = load_meaning_expression_from_path(
            FIXTURE_DIR / "carry_progression_known.v0.json",
            vocabulary=self.vocabulary,
        )
        self.assertIsNotNone(result.expression)

        dumped = stable_expression_json(result.expression)
        reparsed = load_meaning_expression_result(dumped, vocabulary=self.vocabulary)

        self.assertIsNotNone(reparsed.expression)
        self.assertEqual(result.expression.document_hash(), reparsed.expression.document_hash())
        self.assertEqual(stable_hash(json.loads(dumped)), result.expression.document_hash())

    def test_synthesized_target_passes_r1c_guard_and_preserves_row_identity(self) -> None:
        expression = self.accepted_expression("carry_progression_known.v0.json")

        target = synthesize_search_target(expression)
        declaration = validate_correspondence_with_r1c_guard(target)

        self.assertEqual(expression.concept_identity, target["concept"])
        self.assertEqual(expression.concept_identity, declaration["coverage_row"])
        self.assertEqual(expression.meaning, declaration["meaning"])
        self.assertNotIn("verdict", declaration)

    def test_synthesized_target_rejects_mutated_correspondence_row(self) -> None:
        expression = self.accepted_expression("carry_progression_known.v0.json")
        target = synthesize_search_target(expression)
        mutated = copy.deepcopy(target)
        mutated["semantic_correspondence"]["coverage_row"] = "other_row"

        with self.assertRaisesRegex(ValueError, "coverage_row does not match"):
            validate_correspondence_with_r1c_guard(mutated)

    def test_ledger_write_path_is_unreachable_from_bridge_code(self) -> None:
        with self.assertRaises(LedgerWriteForbiddenError):
            update_coverage_rows([], [])

    def test_binder_accepts_synthesized_known_target_and_matches_committed_hash(self) -> None:
        expression = self.accepted_expression("carry_progression_known.v0.json")

        synthesized = synthesize_and_bind(expression, coverage_rows=self.coverage_rows)

        row = next(row for row in self.coverage_rows if row.get("concept") == "carry_progression")
        expected_hash = row["compiler_reachability_evidence"]["document_hash"]
        self.assertEqual("PASS", synthesized["bind"]["status"])
        self.assertEqual(expected_hash, synthesized["document_hash"])

    def test_binder_accepts_novel_in_grammar_composition(self) -> None:
        expression = self.accepted_expression("progressive_pressure_relief_carry_novel.v0.json")

        synthesized = synthesize_and_bind(expression, coverage_rows=self.coverage_rows)

        self.assertEqual("PASS", synthesized["bind"]["status"])
        self.assertEqual("scp2_1_progressive_pressure_relief_carry", synthesized["target"]["concept"])
        self.assertEqual(
            "scp2_1_progressive_pressure_relief_carry",
            synthesized["target"]["semantic_correspondence"]["coverage_row"],
        )

    def accepted_expression(self, name: str):
        result = load_meaning_expression_from_path(FIXTURE_DIR / name, vocabulary=self.vocabulary)
        self.assertEqual("accepted", result.outcome)
        self.assertIsNotNone(result.expression)
        return result.expression

    @staticmethod
    def fixture_payload(name: str) -> dict:
        return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
