"""Write-mode policy for verifiers and generators (F0-2).

One contract across the repo:

* Default mode of every verifier is a READ-ONLY CHECK. It may write untracked
  run reports under ``artifacts/check-runs/`` (gitignored), but it must never
  create or modify tracked files. It exits non-zero on failure.
* Regeneration of tracked evidence/projection files happens only under the
  explicit opt-in ``TQE_WRITE=1`` environment variable, exposed via the
  ``make <gate>-write`` targets. In write mode a FAIL must still write the
  FAIL report — a failing run may never preserve a stale PASS artifact.
* In check mode, verifiers that used to regenerate a tracked file regenerate
  it in memory (or into a temp/check-run path) and DIFF it against the
  checked-in version, failing with an explicit drift message.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

WRITE_ENV_VAR = "TQE_WRITE"
CHECK_RUN_ROOT = Path("artifacts/check-runs")


def write_mode() -> bool:
    """True only under the explicit ``TQE_WRITE=1`` opt-in."""
    return os.environ.get(WRITE_ENV_VAR, "").strip() == "1"


def output_path(canonical: Path) -> Path:
    """Where a verifier report/artifact may be written in the current mode.

    Write mode returns the canonical (potentially tracked) path. Check mode
    returns an untracked mirror under ``artifacts/check-runs/`` so a check run
    can never create or modify tracked files.
    """
    if write_mode():
        return canonical
    parts = canonical.parts
    if parts and parts[0] == "artifacts":
        parts = parts[1:]
    return CHECK_RUN_ROOT.joinpath(*parts)


def serialize_json_artifact(payload: Any) -> str:
    """Canonical JSON serialization used by generated tracked artifacts."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def emit_tracked_artifact(path: Path, content: str) -> dict[str, Any] | None:
    """Write a tracked artifact in write mode; diff it in check mode.

    Returns None when the artifact was written (write mode) or matches the
    checked-in version (check mode), otherwise a drift record the caller must
    surface as a failing finding.
    """
    if write_mode():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return None
    return diff_against_checked_in(path, content)


def diff_against_checked_in(path: Path, fresh_content: str) -> dict[str, Any] | None:
    """Return a drift record if ``path`` does not match ``fresh_content``.

    This is the check-mode replacement for regenerating a tracked file in
    place: regenerate in memory, then compare against the checked-in version.
    """
    if not path.exists():
        return {
            "path": str(path),
            "kind": "missing",
            "message": f"{path} is missing; run the corresponding -write target to regenerate it.",
        }
    if path.read_text(encoding="utf-8") != fresh_content:
        return {
            "path": str(path),
            "kind": "content_drift",
            "message": (
                f"{path} does not match a fresh regeneration. The checked-in artifact has "
                "drifted; inspect the change and run the corresponding -write target "
                "(TQE_WRITE=1) to regenerate it deliberately."
            ),
        }
    return None
