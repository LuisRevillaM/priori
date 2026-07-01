"""SCP-0 semantic registry verifier."""

from __future__ import annotations

import json
from pathlib import Path

from tqe.semantic_registry.generate import generate_scp0_artifacts


REPORT_PATH = Path("artifacts/scp-0/verification-report.json")


def main() -> None:
    _, _, _, report = generate_scp0_artifacts(write=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    if report.status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
