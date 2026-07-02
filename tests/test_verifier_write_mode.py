"""F0-2 write-mode contract tests.

Verifiers default to READ-ONLY CHECK mode: they never create or modify tracked
files, and tracked generated artifacts are regenerated in memory and diffed.
Explicit regeneration requires TQE_WRITE=1, and in write mode a FAIL must still
write the FAIL report (never preserving a stale PASS artifact).
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tqe.semantic_registry.generate import (
    LOCK_PATH,
    OUTPUT_ROOT,
    SCHEMA_PATH,
    generate_scp0_artifacts,
    load_registry,
)
from tqe.verification import scp0
from tqe.write_mode import WRITE_ENV_VAR, output_path, write_mode

TRACKED_SCP0_ARTIFACTS = [
    SCHEMA_PATH,
    LOCK_PATH,
    OUTPUT_ROOT / "runtime-manifest.json",
    OUTPUT_ROOT / "plan-artifact-index.json",
    OUTPUT_ROOT / "product-projection.json",
    OUTPUT_ROOT / "ai-projection.json",
    OUTPUT_ROOT / "recipe-library-projection.json",
    OUTPUT_ROOT / "unsupported-capability-projection.json",
    OUTPUT_ROOT / "research-atlas-projection.json",
    OUTPUT_ROOT / "capability-passport-projection.json",
    OUTPUT_ROOT / "semantic-parity-report.json",
    Path("generated/tactical-knowledge-pack.json"),
    Path("generated/tactical-knowledge-pack.md"),
    Path("generated/capability-context.json"),
]


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WriteModePolicyTests(unittest.TestCase):
    def test_write_mode_requires_explicit_opt_in(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(WRITE_ENV_VAR, None)
            self.assertFalse(write_mode())
        with mock.patch.dict(os.environ, {WRITE_ENV_VAR: "1"}):
            self.assertTrue(write_mode())
        # Anything but exactly "1" stays read-only (fail-closed opt-in).
        with mock.patch.dict(os.environ, {WRITE_ENV_VAR: "true"}):
            self.assertFalse(write_mode())

    def test_output_path_mirrors_check_runs_in_check_mode(self) -> None:
        canonical = Path("artifacts/scp-0/verification-report.json")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(WRITE_ENV_VAR, None)
            self.assertEqual(
                Path("artifacts/check-runs/scp-0/verification-report.json"),
                output_path(canonical),
            )
            self.assertEqual(
                Path("artifacts/check-runs/delivery/report.md"),
                output_path(Path("delivery/report.md")),
            )
        with mock.patch.dict(os.environ, {WRITE_ENV_VAR: "1"}):
            self.assertEqual(canonical, output_path(canonical))


class CheckModeIsReadOnlyTests(unittest.TestCase):
    def test_scp0_verifier_check_mode_leaves_tracked_files_untouched(self) -> None:
        """Representative verifier in check mode: no tracked file content changes."""
        before = {path: file_digest(path) for path in TRACKED_SCP0_ARTIFACTS}

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(WRITE_ENV_VAR, None)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    scp0.main()
            except SystemExit as exc:  # pragma: no cover - drift would surface here
                self.fail(f"scp0 check mode failed (drift or FAIL): {exc}")

        after = {path: file_digest(path) for path in TRACKED_SCP0_ARTIFACTS}
        self.assertEqual(before, after)
        # The run report lands only under the untracked check-runs mirror.
        check_report = Path("artifacts/check-runs/scp-0/verification-report.json")
        self.assertTrue(check_report.exists())
        self.assertEqual(
            "PASS", json.loads(check_report.read_text(encoding="utf-8"))["status"]
        )


class WriteModeFailReportTests(unittest.TestCase):
    def test_write_mode_on_fail_still_writes_fail_report(self) -> None:
        """A failing write-mode run must record the FAIL, never keep a stale PASS."""
        registry = load_registry()
        registry.runtime_bindings = registry.runtime_bindings[:-1]
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.yaml"
            output_root = Path(tmp) / "generated"
            output_root.mkdir()
            report_path = output_root / "semantic-parity-report.json"
            report_path.write_text('{"status": "PASS", "stale": true}\n', encoding="utf-8")
            product_projection = output_root / "product-projection.json"
            product_projection.write_text('{"sentinel": true}\n', encoding="utf-8")
            payload = registry.model_dump(mode="json", exclude_none=True)
            payload["atlas_entries"] = []
            registry_path.write_text(json.dumps(payload), encoding="utf-8")

            _, _, _, report = generate_scp0_artifacts(
                registry_path=registry_path, output_root=output_root, write=True
            )

            self.assertEqual("FAIL", report.status)
            written = json.loads(report_path.read_text(encoding="utf-8"))
            # The stale PASS report was replaced by the fresh FAIL report...
            self.assertEqual("FAIL", written["status"])
            self.assertNotIn("stale", written)
            # ...while the last valid projections are preserved, not clobbered.
            self.assertEqual(
                '{"sentinel": true}\n', product_projection.read_text(encoding="utf-8")
            )

    def test_check_mode_never_writes_even_on_fail(self) -> None:
        registry = load_registry()
        registry.runtime_bindings = registry.runtime_bindings[:-1]
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.yaml"
            output_root = Path(tmp) / "generated"
            output_root.mkdir()
            payload = registry.model_dump(mode="json", exclude_none=True)
            payload["atlas_entries"] = []
            registry_path.write_text(json.dumps(payload), encoding="utf-8")

            _, _, _, report = generate_scp0_artifacts(
                registry_path=registry_path, output_root=output_root
            )

            self.assertEqual("FAIL", report.status)
            self.assertEqual([], sorted(output_root.iterdir()))


if __name__ == "__main__":
    unittest.main()
