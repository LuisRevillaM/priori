"""SCP-0 semantic registry verifier.

Default mode is a READ-ONLY CHECK (F0-2): it regenerates the SCP-0 artifacts
in memory, diffs them against the checked-in projections/lock/parity report,
and writes its run report to an untracked path under artifacts/check-runs/.
Explicit regeneration of the tracked artifacts requires TQE_WRITE=1
(``make scp-0-write``); in write mode a FAIL still rewrites the FAIL parity
report so stale PASS evidence can never survive a failing run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.semantic_registry.generate import check_scp0_artifacts, generate_scp0_artifacts
from tqe.write_mode import output_path, write_mode


REPORT_PATH = Path("artifacts/scp-0/verification-report.json")


def main() -> None:
    drift: list[dict[str, Any]] = []
    if write_mode():
        _, _, _, report = generate_scp0_artifacts(write=True)
    else:
        _, _, _, report, drift = check_scp0_artifacts()
    payload = report.model_dump(mode="json")
    report_path = output_path(REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if drift:
        print(json.dumps({"projection_drift": drift}, indent=2, sort_keys=True))
    if report.status != "PASS" or drift:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
