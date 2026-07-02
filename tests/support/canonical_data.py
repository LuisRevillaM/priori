"""Canonical-corpus availability detection for the CI test split (F0-3).

The 2.6 GB canonical match corpus (``data/canonical/v1``, gitignored) is not
available in CI. Tests that execute against real match data must declare that
dependency with ``@requires_canonical_data`` so a data-free environment runs
the honest subset and *reports* the skips instead of failing.

The root honors ``TQE_DATA_ROOT`` (same contract as the runtime executor), so
a no-data run can also be simulated locally with
``TQE_DATA_ROOT=/nonexistent`` — though the highest-fidelity simulation is a
fresh ``git worktree`` (data/ is gitignored, so a worktree has no corpus,
exactly like CI). See docs/CI.md.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

CANONICAL_DATA_ROOT = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))

# matches.parquet is the corpus index; if it is missing the corpus is not
# provisioned (a partial download would still fail loudly inside the tests,
# which is the correct behavior — this guard only covers "no corpus at all").
_SENTINEL = CANONICAL_DATA_ROOT / "matches.parquet"


def canonical_data_available() -> bool:
    return _SENTINEL.is_file()


SKIP_REASON = (
    f"canonical match corpus not available at {CANONICAL_DATA_ROOT} "
    "(gitignored 2.6 GB corpus; provision with `make provision-corpus` "
    "or point TQE_DATA_ROOT at it)"
)

requires_canonical_data = unittest.skipUnless(canonical_data_available(), SKIP_REASON)
