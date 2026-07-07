from __future__ import annotations

import http.client
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tqe.workshop import app_service
from tqe.workshop.app_service import WorkbenchHandler, WorkbenchServer


class Deploy1PublicModeTests(unittest.TestCase):
    def setUp(self) -> None:
        with app_service.FILM_ROOM_PREWARM_LOCK:
            app_service.FILM_ROOM_PREWARMED_RESPONSES.clear()
            app_service.FILM_ROOM_PREWARM_RECORDS.clear()
            app_service.FILM_ROOM_PREWARM_STATE.update(
                {
                    "state": "warming",
                    "started_at": None,
                    "completed_at": None,
                    "items": [],
                    "last_error": None,
                }
            )

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, object] | str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            static_root = root / "static"
            output_root = root / "output"
            static_root.mkdir()
            output_root.mkdir()
            (static_root / "index.html").write_text("<!doctype html><title>ENTRELÍNEAS</title>", encoding="utf-8")
            server = WorkbenchServer(
                ("127.0.0.1", 0),
                WorkbenchHandler,
                static_root=static_root,
                output_root=output_root,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            try:
                thread.start()
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                body = json.dumps(payload).encode("utf-8") if payload is not None else None
                headers = {"Content-Type": "application/json"} if payload is not None else {}
                connection.request(method, path, body=body, headers=headers)
                response = connection.getresponse()
                raw = response.read().decode("utf-8")
                connection.close()
                if response.getheader("Content-Type", "").startswith("application/json"):
                    return response.status, json.loads(raw)
                return response.status, raw
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_public_mode_serves_gallery_and_bootstrap_without_demo_token(self) -> None:
        with patch("tqe.workshop.app_service.TQE_PUBLIC_MODE", True), patch(
            "tqe.workshop.app_service.DEMO_ACCESS_TOKEN", "secret"
        ):
            page_status, page_body = self.request("GET", "/film-room")
            boot_status, boot_body = self.request("GET", "/api/film-room/bootstrap")

        self.assertEqual(200, page_status)
        self.assertIn("ENTREL", str(page_body).upper())
        self.assertEqual(200, boot_status)
        self.assertIsInstance(boot_body, dict)
        self.assertEqual(True, boot_body["ok"])
        self.assertEqual("warming", boot_body["state"])

    def test_public_mode_live_ask_without_token_is_demo_token_required(self) -> None:
        with (
            patch("tqe.workshop.app_service.TQE_PUBLIC_MODE", True),
            patch("tqe.workshop.app_service.DEMO_ACCESS_TOKEN", "secret"),
            patch("tqe.workshop.app_service.film_room_ask_disabled_reason") as disabled_reason,
            patch("tqe.workshop.app_service.film_room_ask_request") as ask_request,
        ):
            status, body = self.request("POST", "/api/film-room/ask", payload={"text": "Show controlled passes."})

        self.assertEqual(401, status)
        self.assertIsInstance(body, dict)
        self.assertEqual(False, body["ok"])
        self.assertEqual("DEMO_TOKEN_REQUIRED", body["error_code"])
        self.assertNotEqual("REQUEST_SCHEMA_INVALID", body["error_code"])
        disabled_reason.assert_not_called()
        ask_request.assert_not_called()

    def test_public_mode_live_ask_with_token_reaches_handler(self) -> None:
        response = {
            "ok": True,
            "outcome": "clarification_required",
            "request_text": "Show controlled passes.",
            "provider": "test",
            "model": "test",
            "latency_ms": 1,
            "latency_breakdown_ms": {"hermes": 1, "synthesis": 0, "execution": 0, "total": 1},
            "hermes": {},
            "answer": None,
            "clarification": {"question": "Which reading?"},
            "refusal": None,
        }
        with (
            patch("tqe.workshop.app_service.TQE_PUBLIC_MODE", True),
            patch("tqe.workshop.app_service.DEMO_ACCESS_TOKEN", "secret"),
            patch("tqe.workshop.app_service.film_room_ask_disabled_reason", return_value=None),
            patch("tqe.workshop.app_service.film_room_ask_request", return_value=response) as ask_request,
        ):
            status, body = self.request(
                "POST",
                "/api/film-room/ask",
                payload={"text": "Show controlled passes.", "demo_token": "secret"},
            )

        self.assertEqual(200, status)
        self.assertIsInstance(body, dict)
        self.assertEqual("clarification_required", body["outcome"])
        ask_request.assert_called_once()

    def test_public_mode_live_ask_with_token_degrades_when_hermes_absent(self) -> None:
        with (
            patch("tqe.workshop.app_service.TQE_PUBLIC_MODE", True),
            patch("tqe.workshop.app_service.DEMO_ACCESS_TOKEN", "secret"),
            patch(
                "tqe.workshop.app_service.film_room_ask_disabled_reason",
                return_value={"reason": "hermes_auth_missing", "message": "No Hermes auth."},
            ),
            patch("tqe.workshop.app_service.film_room_ask_request") as ask_request,
        ):
            status, body = self.request(
                "POST",
                "/api/film-room/ask",
                payload={"text": "Show controlled passes.", "demo_token": "secret"},
            )

        self.assertEqual(503, status)
        self.assertIsInstance(body, dict)
        self.assertEqual(False, body["ok"])
        self.assertEqual("ASKS_DISABLED", body["error_code"])
        self.assertEqual("hermes_auth_missing", body["details"]["reason"])
        ask_request.assert_not_called()

    def test_provisioning_rejects_cache_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset_root = root / "dataset"
            cache_root = root / "cache"
            runtime_root = root / "runtime"
            cache_file = cache_root / "node-output" / "entry.json"
            cache_file.parent.mkdir(parents=True)
            cache_file.write_text('{"ok":true}\n', encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"schema_version": "1.0", "required_paths": [], "required_raw_paths": []}) + "\n",
                encoding="utf-8",
            )
            bundle_manifest = root / "bundle-manifest.json"
            actual = hashlib.sha256(cache_file.read_bytes()).hexdigest()
            wrong = "0" * 64 if actual != "0" * 64 else "1" * 64
            bundle_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "files": [{"path": "cache/node-output/entry.json", "sha256": wrong}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/provision-demo-data.py",
                    "--dataset-root",
                    str(dataset_root),
                    "--cache-root",
                    str(cache_root),
                    "--runtime-root",
                    str(runtime_root),
                    "--manifest",
                    str(manifest),
                    "--bundle-manifest",
                    str(bundle_manifest),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("hash_mismatches", completed.stdout)
        self.assertIn("cache/node-output/entry.json", completed.stdout)


if __name__ == "__main__":
    unittest.main()
