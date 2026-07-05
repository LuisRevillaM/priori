#!/usr/bin/env python3
"""Build the local data integrity manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_ROOTS = (
    Path("data/canonical/v1"),
    Path("data/raw/idsse/figshare-28196177-v1"),
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_records(roots: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for root in roots:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            records.append(
                {
                    "path": path.as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256_path(path),
                }
            )
    return records


def build_manifest(roots: list[Path]) -> dict[str, Any]:
    records = file_records(roots)
    return {
        "schema_version": "priori_data_manifest.v1",
        "integrity_policy": {
            "default_gate_verify": "manifest_hash_plus_file_sizes",
            "deep_verify_env": "TQE_DEEP_VERIFY=1",
            "deep_verify": "manifest_hash_plus_file_sizes_plus_file_sha256",
        },
        "roots": [root.as_posix() for root in roots],
        "file_count": len(records),
        "files": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/manifest.json"))
    parser.add_argument("--root", type=Path, action="append", default=None)
    args = parser.parse_args()
    roots = args.root or list(DEFAULT_ROOTS)
    manifest = build_manifest(roots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "file_count": manifest["file_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
