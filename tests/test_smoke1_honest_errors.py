from __future__ import annotations

import http.client
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from scripts.coverage_map.compiler_search_reachability import SynthesisError
from tqe.semantic_compiler.hermes_nl import ExpressionOutcome, TranscriptEvidence
from tqe.semantic_compiler.meaning_expression import load_meaning_expression_result, load_pack_vocabulary
from tqe.workshop.app_service import WorkbenchHandler, WorkbenchServer


class Smoke1HonestErrorTests(unittest.TestCase):
    def post_json(self, payload: dict[str, object]) -> tuple[int, dict[str, object], str]:
        with tempfile.TemporaryDirectory() as directory:
            server = WorkbenchServer(
                ("127.0.0.1", 0),
                WorkbenchHandler,
                static_root=Path("."),
                output_root=Path(directory),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                try:
                    thread.start()
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request(
                        "POST",
                        "/api/film-room/ask",
                        body=json.dumps(payload),
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    body = json.loads(response.read().decode("utf-8"))
                    connection.close()
                    return response.status, body, stderr.getvalue()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)

    def test_internal_key_error_beyond_dispatch_is_not_request_schema_invalid(self) -> None:
        def raise_internal_key_error(_payload: dict[str, object], *, output_root: Path) -> dict[str, object]:
            raise KeyError("chain_status")

        with patch("tqe.workshop.app_service.film_room_ask_request", side_effect=raise_internal_key_error):
            status, body, logs = self.post_json({"text": "valid ask"})

        self.assertEqual(500, status)
        self.assertEqual(False, body["ok"])
        self.assertEqual("INTERNAL_ERROR", body["error_code"])
        self.assertNotEqual("REQUEST_SCHEMA_INVALID", body["error_code"])
        details = body["details"]
        self.assertIsInstance(details, dict)
        self.assertRegex(str(details.get("correlation_id")), r"^err_[0-9a-f]{12}$")
        self.assertIn("workbench_internal_error", logs)
        self.assertIn("KeyError", logs)
        self.assertIn("chain_status", logs)

    def test_empty_film_room_ask_is_request_schema_invalid(self) -> None:
        status, body, _logs = self.post_json({"text": ""})

        self.assertEqual(400, status)
        self.assertEqual(False, body["ok"])
        self.assertEqual("REQUEST_SCHEMA_INVALID", body["error_code"])
        self.assertIn("expected", body["details"])

    def test_synthesis_error_after_successful_compile_is_typed_refusal(self) -> None:
        fixture = json.loads(
            Path("delivery/packets/scp2-1-roundtrip/meaning-expressions/fragile_possession_state_known.v0.json").read_text(
                encoding="utf-8"
            )
        )
        expression = load_meaning_expression_result(fixture, vocabulary=load_pack_vocabulary()).expression
        assert expression is not None
        outcome = ExpressionOutcome(
            outcome="expression",
            expression=expression,
            expression_json=fixture,
            document_hash=expression.document_hash(),
            transcript=TranscriptEvidence(
                prompt_hash="prompt",
                pack_sha256="pack",
                raw_completion=json.dumps({"outcome": "expression", "expression": fixture}),
                completion_hash="completion",
                model_provider="test-provider",
                model_name="test-model",
                invocation={"request_text": "owner ask"},
            ),
        )

        with (
            patch("tqe.semantic_compiler.hermes_nl.compile_nl_request", return_value=outcome),
            patch(
                "tqe.semantic_compiler.target_synthesis.synthesize_and_bind",
                side_effect=SynthesisError(
                    "no_registered_operator_composition",
                    "No registered operator composition satisfied the target contract.",
                    {},
                ),
            ),
        ):
            from tqe.workshop.app_service import film_room_ask_request

            with tempfile.TemporaryDirectory() as directory:
                response = film_room_ask_request({"text": "owner ask"}, output_root=Path(directory))

        self.assertEqual(True, response["ok"])
        self.assertEqual("understood_but_not_expressible", response["outcome"])
        self.assertEqual("TARGET_SYNTHESIS_UNSATISFIED", response["refusal"]["gap_code"])
        self.assertEqual("registered_operator_composition", response["refusal"]["missing_capability"])


if __name__ == "__main__":
    unittest.main()
