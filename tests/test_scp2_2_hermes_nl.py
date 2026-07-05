from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from scripts.scp2_2.eval_harness import evaluate_case_set_payload
from tqe.semantic_compiler.hermes_nl import (
    HERMES_OUTCOME_ADAPTER,
    HermesNLContext,
    HermesNLModelOutputError,
    UnderstoodButNotExpressibleOutcome,
    build_prompt_projection,
    compile_nl_request,
    expression_outcome,
    parse_hermes_completion,
    transcript_for,
)
from tqe.semantic_compiler.meaning_expression import load_meaning_expression_result, load_pack_vocabulary


FIXTURE_DIR = Path("delivery/packets/scp2-1-roundtrip/meaning-expressions")
R2_4_FIXTURE_DIR = Path("delivery/packets/r2-4-flagship/meaning-expressions")


class FakeInvoker:
    provider = "test-provider"
    model = "test-model"

    def __init__(self, *outputs: str) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.outputs:
            raise AssertionError("FakeInvoker was called more times than expected")
        return self.outputs.pop(0)


class SCP2HermesNLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = load_pack_vocabulary()
        cls.projection = build_prompt_projection()
        cls.coverage_rows = json.loads(Path("generated/coverage-map.json").read_text(encoding="utf-8"))

    def test_outcome_type_exhaustiveness_rejects_fifth_outcome_shape(self) -> None:
        with self.assertRaises(ValidationError):
            HERMES_OUTCOME_ADAPTER.validate_python(
                {
                    "outcome": "compiler_error",
                    "message": "not an allowed SCP2-2 outcome",
                }
            )

    def test_model_output_parser_rejects_fifth_raw_shape(self) -> None:
        with self.assertRaises(HermesNLModelOutputError):
            parse_hermes_completion(
                json.dumps({"outcome": "best_effort", "notes": "nope"}),
                transcript=self.transcript("{}"),
                vocabulary=self.vocabulary,
            )

    def test_mutation_bypassing_expression_gate_would_accept_body_orientation_oov(self) -> None:
        raw = json.dumps(
            {
                "outcome": "expression",
                "expression": self.fixture_payload("body_orientation_oov.v0.json"),
            }
        )

        outcome = compile_nl_request("show body orientation", invoker=FakeInvoker(raw))

        self.assertIsInstance(outcome, UnderstoodButNotExpressibleOutcome)
        self.assertEqual("understood_but_not_expressible", outcome.outcome)
        self.assertEqual("BODY_ORIENTATION", outcome.gap_code)
        self.assertEqual("concept:body_orientation", outcome.missing_capability)

    def test_expression_gate_routes_unsupported_modality_to_typed_refusal(self) -> None:
        payload = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        payload["target_contract"]["required_modalities"].append("video")
        raw = json.dumps({"outcome": "expression", "expression": payload})

        outcome = compile_nl_request("show the video", invoker=FakeInvoker(raw))

        self.assertEqual("unsupported_modality", outcome.outcome)
        self.assertEqual("VIDEO", outcome.gap_code)
        self.assertEqual("video", outcome.modality)

    def test_prompt_projection_changes_when_pack_copy_changes_and_no_hand_sentinel_exists(self) -> None:
        baseline = build_prompt_projection()
        sentinel = "scp2_2_projection_sentinel"
        self.assertNotIn(sentinel, baseline.prompt)
        payload = json.loads(Path("generated/tactical-knowledge-pack.json").read_text(encoding="utf-8"))
        payload["primitives"][0].setdefault("evidence_fields", []).append(sentinel)
        with tempfile.TemporaryDirectory() as tmp:
            pack_path = Path(tmp) / "pack.json"
            pack_path.write_text(json.dumps(payload), encoding="utf-8")

            mutated = build_prompt_projection(pack_path)

        self.assertIn(sentinel, mutated.prompt)
        self.assertNotEqual(baseline.prompt_hash, mutated.prompt_hash)

    def test_prompt_projection_contains_generated_certified_few_shots(self) -> None:
        examples = self.projection.sections["certified_few_shot_examples"]

        self.assertEqual(3, len(examples))
        fixture_paths = {item["fixture_path"] for item in examples}
        self.assertIn(
            "delivery/packets/scp2-1-roundtrip/meaning-expressions/fragile_possession_state_known.v0.json",
            fixture_paths,
        )
        self.assertIn(
            "delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_sequence_rate.v0.json",
            fixture_paths,
        )
        self.assertNotIn(
            "delivery/packets/scp2-1-roundtrip/meaning-expressions/body_orientation_oov.v0.json",
            fixture_paths,
        )
        for example in examples:
            result = load_meaning_expression_result(example["expression"], vocabulary=self.vocabulary)
            self.assertEqual("accepted", result.outcome)
            self.assertTrue(example["minimal_contract_guidance"]["required_evidence"])

    def test_prompt_projection_contains_generated_recipe_authoring_guides(self) -> None:
        guides = self.projection.sections["recipe_authoring_guides"]
        guide_by_id = {item["recipe_id"]: item for item in guides}

        self.assertIn("high_bypass_completed_pass_v1", guide_by_id)
        self.assertIn("first_time_relay_after_receiver_line_transition_v1", guide_by_id)
        high_bypass = guide_by_id["high_bypass_completed_pass_v1"]
        self.assertIn("opponents_bypassed_count", high_bypass["requested_evidence_fields"])
        self.assertIn(
            {"field": "opponents_bypassed_count", "operator": "gte", "required_value": {"parameter": "minimum_bypassed_opponents"}},
            high_bypass["required_status_semantics"],
        )

    def test_prompt_projection_contains_generated_classifier_rules(self) -> None:
        rules = self.projection.sections["compiler_classification_rules"]

        self.assertIn(
            "cover underneath",
            rules["clarify_not_gap_when_request_contains_without_corridor_alias"],
        )
        self.assertIn("body orientation", rules["capability_gap_when_request_contains"])

    def test_invalid_raw_completion_gets_repaired_before_acceptance(self) -> None:
        payload = self.fixture_payload("fragile_possession_state_known.v0.json")
        invoker = FakeInvoker(
            "The request is expressible as controlled_pass_status PASS.",
            json.dumps({"outcome": "expression", "expression": payload}),
        )

        outcome = compile_nl_request("show controlled passes", invoker=invoker)

        self.assertEqual("expression", outcome.outcome)
        self.assertEqual(payload["expression_id"], outcome.expression.expression_id)
        self.assertEqual(2, len(invoker.prompts))
        self.assertIn("previous final answer was rejected", invoker.prompts[1])
        self.assertEqual(1, outcome.transcript.invocation["repair_attempt_count"])
        self.assertEqual(1, len(outcome.transcript.invocation["rejected_attempts"]))

    def test_multi_turn_clarification_state_resumes_without_reasking_model(self) -> None:
        controlled = self.fixture_payload("fragile_possession_state_known.v0.json")
        sequence = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        raw = json.dumps(
            {
                "outcome": "clarification_required",
                "dimension": "SUPPORT_DEFINITION",
                "question": "Which support reading should be used?",
                "readings": [
                    {
                        "reading_id": "possession_window",
                        "label": "same possession support window",
                        "answer_aliases": ["window"],
                        "expression": controlled,
                    },
                    {
                        "reading_id": "count_window",
                        "label": "count support windows",
                        "answer_aliases": ["count"],
                        "expression": sequence,
                    },
                ],
            }
        )
        invoker = FakeInvoker(raw)

        first = compile_nl_request("show support", invoker=invoker)
        second = compile_nl_request(
            "count",
            context=HermesNLContext(pending_clarification=first.state, answer="count"),
            invoker=invoker,
        )

        self.assertEqual("clarification_required", first.outcome)
        self.assertEqual("expression", second.outcome)
        self.assertEqual(sequence["expression_id"], second.expression.expression_id)
        self.assertEqual(1, len(invoker.prompts))

    def test_clarification_with_reading_already_in_request_resolves_without_reasking(self) -> None:
        controlled = self.fixture_payload("fragile_possession_state_known.v0.json")
        sequence = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        raw = json.dumps(
            {
                "outcome": "clarification_required",
                "dimension": "SUPPORT_DEFINITION",
                "question": "Which support reading should be used?",
                "readings": [
                    {
                        "reading_id": "within_distance",
                        "label": "within distance support",
                        "answer_aliases": ["nearby"],
                        "expression": controlled,
                    },
                    {
                        "reading_id": "underneath_option",
                        "label": "underneath support option",
                        "answer_aliases": ["underneath"],
                        "expression": sequence,
                    },
                ],
            }
        )
        invoker = FakeInvoker(raw)

        outcome = compile_nl_request("find underneath support", invoker=invoker)

        self.assertEqual("expression", outcome.outcome)
        self.assertEqual(sequence["expression_id"], outcome.expression.expression_id)
        self.assertEqual("preanswered_clarification_state", outcome.transcript.invocation["source"])
        self.assertEqual(1, len(invoker.prompts))

    def test_distance_clarification_alias_does_not_preanswer_without_numeric_threshold(self) -> None:
        controlled = self.fixture_payload("fragile_possession_state_known.v0.json")
        sequence = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        raw = json.dumps(
            {
                "outcome": "clarification_required",
                "dimension": "DISTANCE_THRESHOLD",
                "question": "How close must support be?",
                "readings": [
                    {
                        "reading_id": "default_distance",
                        "label": "within the default 8 metre distance",
                        "answer_aliases": ["close enough"],
                        "expression": controlled,
                    },
                    {
                        "reading_id": "tight_distance",
                        "label": "within a tighter 4 metre distance",
                        "answer_aliases": ["very close"],
                        "expression": sequence,
                    },
                ],
            }
        )
        outcome = compile_nl_request("show close enough support", invoker=FakeInvoker(raw))

        self.assertEqual("clarification_required", outcome.outcome)
        self.assertEqual("DISTANCE_THRESHOLD", outcome.dimension)

    def test_clarification_dimension_label_canonicalizes_to_generated_code(self) -> None:
        controlled = self.fixture_payload("fragile_possession_state_known.v0.json")
        sequence = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        raw = json.dumps(
            {
                "outcome": "clarification_required",
                "dimension": "support",
                "question": "What support reading should be used?",
                "readings": [
                    {
                        "reading_id": "within_distance",
                        "label": "within distance support",
                        "answer_aliases": ["nearby"],
                        "expression": controlled,
                    },
                    {
                        "reading_id": "behind_ball",
                        "label": "behind ball outlet support",
                        "answer_aliases": ["outlet"],
                        "expression": sequence,
                    },
                ],
            }
        )

        outcome = compile_nl_request("show support", invoker=FakeInvoker(raw))

        self.assertEqual("clarification_required", outcome.outcome)
        self.assertEqual("SUPPORT_DEFINITION", outcome.dimension)

    def test_alias_only_support_uses_generated_typed_clarification_without_model_call(self) -> None:
        first = compile_nl_request("Show support.")

        self.assertEqual("clarification_required", first.outcome)
        self.assertEqual("SUPPORT_DEFINITION", first.dimension)
        self.assertIsNone(first.transcript.model_provider)
        self.assertEqual(
            "generated_classifier_clarification",
            first.transcript.invocation["source"],
        )

        second = compile_nl_request(
            "use support arrival within distance",
            context=HermesNLContext(
                pending_clarification=first.state,
                answer="use support arrival within distance",
            ),
        )

        self.assertEqual("expression", second.outcome)
        self.assertEqual(
            "scp2_2_support_arrival_within_distance_reading",
            second.expression.expression_id,
        )
        self.assertEqual(
            "typed_clarification_state",
            second.transcript.invocation["source"],
        )

    def test_clarification_resume_selects_fuzzy_typed_reading(self) -> None:
        controlled = self.fixture_payload("fragile_possession_state_known.v0.json")
        sequence = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        raw = json.dumps(
            {
                "outcome": "clarification_required",
                "dimension": "DISTANCE_THRESHOLD",
                "question": "How close must support be?",
                "readings": [
                    {
                        "reading_id": "five_metre_distance",
                        "label": "within 5 metres of the reference point",
                        "answer_aliases": [],
                        "expression": controlled,
                    },
                    {
                        "reading_id": "eight_metre_distance",
                        "label": "within 8 metres of the reference point",
                        "answer_aliases": [],
                        "expression": sequence,
                    },
                ],
            }
        )
        invoker = FakeInvoker(raw)
        first = compile_nl_request("show close support", invoker=invoker)

        second = compile_nl_request(
            "within five metres",
            context=HermesNLContext(pending_clarification=first.state, answer="within five metres"),
            invoker=invoker,
        )

        self.assertEqual("expression", second.outcome)
        self.assertEqual(controlled["expression_id"], second.expression.expression_id)
        self.assertEqual(1, len(invoker.prompts))

    def test_clarification_resume_can_select_by_reading_expression_identity(self) -> None:
        controlled = self.fixture_payload("fragile_possession_state_known.v0.json")
        controlled["expression_id"] = "support_arrival_relation_reading"
        sequence = self.fixture_payload("fragile_window_join_count_novel.v0.json")
        raw = json.dumps(
            {
                "outcome": "clarification_required",
                "dimension": "SUPPORT_DEFINITION",
                "question": "Which support definition should be shown?",
                "readings": [
                    {
                        "reading_id": "support_within_distance",
                        "label": "within distance support",
                        "answer_aliases": [],
                        "expression": controlled,
                    },
                    {
                        "reading_id": "support_lane",
                        "label": "passing lane support",
                        "answer_aliases": [],
                        "expression": sequence,
                    },
                ],
            }
        )
        invoker = FakeInvoker(raw)
        first = compile_nl_request("show support", invoker=invoker)

        second = compile_nl_request(
            "support arrival",
            context=HermesNLContext(pending_clarification=first.state, answer="support arrival"),
            invoker=invoker,
        )

        self.assertEqual("expression", second.outcome)
        self.assertEqual("support_arrival_relation_reading", second.expression.expression_id)
        self.assertEqual(1, len(invoker.prompts))

    def test_harness_verdict_correctness_on_tiny_fixture_set(self) -> None:
        fragile = self.expression_for("fragile_possession_state_known.v0.json")
        sequence = self.expression_for_r2_4("counterattack_initiation_sequence_rate.v0.json")

        def fake_compiler(text: str, _context: HermesNLContext | None = None):
            if text in {"same one", "same two", "changed one"}:
                return fragile
            if text == "changed two":
                return sequence
            return UnderstoodButNotExpressibleOutcome(
                outcome="understood_but_not_expressible",
                gap_code="BODY_ORIENTATION",
                missing_capability="concept:body_orientation",
                message="Body orientation is out of pack.",
                transcript=self.transcript("body"),
            )

        payload = {
            "schema_version": "scp2_2.dev_cases.v0",
            "cases": [
                {
                    "case_id": "same",
                    "kind": "same_meaning_pair",
                    "request_texts": ["same one", "same two"],
                    "expected": {"outcome": "expression"},
                },
                {
                    "case_id": "changed",
                    "kind": "changed_meaning_pair",
                    "request_texts": ["changed one", "changed two"],
                    "expected": {"outcome": "expression"},
                },
                {
                    "case_id": "refusal",
                    "kind": "single",
                    "request_text": "body",
                    "expected": {
                        "outcome": "understood_but_not_expressible",
                        "gap_code": "BODY_ORIENTATION",
                    },
                },
            ],
        }

        result = evaluate_case_set_payload(
            payload,
            compiler=fake_compiler,
            case_set_ref="<unit>",
            coverage_rows=self.coverage_rows,
        )

        self.assertEqual(3, result["summary"]["pass"])
        self.assertEqual(0, result["summary"]["fail"])

    def expression_for(self, name: str):
        payload = self.fixture_payload(name)
        return expression_outcome(
            payload,
            transcript=self.transcript(name),
            vocabulary=self.vocabulary,
        )

    def expression_for_r2_4(self, name: str):
        payload = json.loads((R2_4_FIXTURE_DIR / name).read_text(encoding="utf-8"))
        return expression_outcome(
            payload,
            transcript=self.transcript(name),
            vocabulary=self.vocabulary,
        )

    def transcript(self, raw: str):
        return transcript_for(
            projection=self.projection,
            raw_completion=raw,
            provider="test-provider",
            model="test-model",
        )

    @staticmethod
    def fixture_payload(name: str) -> dict:
        return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
