#!/usr/bin/env python3
"""Provision the Cloud Workbench Alpha demo data bundle.

The script is intentionally conservative:
- if the expected manifest is already satisfied, it exits without mutation;
- if a bundle URL is configured, it downloads to a temporary file, verifies the
  SHA-256 when supplied, and unpacks atomically into the dataset root;
- if no bundle URL is configured, it validates the existing mounted data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Priori demo data for cloud Workbench.")
    parser.add_argument("--dataset-root", type=Path, default=Path("/var/data/dataset"))
    parser.add_argument("--manifest", type=Path, default=Path("config/deploy/demo-data-manifest.json"))
    parser.add_argument("--bundle-manifest", type=Path, default=Path(os.environ.get("TQE_DATA_BUNDLE_MANIFEST", "")) if os.environ.get("TQE_DATA_BUNDLE_MANIFEST") else None)
    parser.add_argument("--bundle-url", default=os.environ.get("TQE_DATA_BUNDLE_URL", ""))
    parser.add_argument("--bundle-sha256", default=os.environ.get("TQE_DATA_BUNDLE_SHA256", ""))
    args = parser.parse_args()

    manifest = read_json(args.manifest)
    args.dataset_root.mkdir(parents=True, exist_ok=True)
    bundle_manifest = read_json(args.bundle_manifest) if args.bundle_manifest else {}
    if dataset_satisfies_manifest(args.dataset_root, manifest, bundle_manifest):
        print("Demo data already satisfies manifest.")
        return 0
    if not args.bundle_url:
        print("Demo data is missing and TQE_DATA_BUNDLE_URL is not configured.")
        print(json.dumps(missing_report(args.dataset_root, manifest), indent=2, sort_keys=True))
        return 1

    with tempfile.TemporaryDirectory(prefix="priori-demo-data-") as temp_dir:
        temp_path = Path(temp_dir)
        archive = temp_path / "bundle.tar.gz"
        download(args.bundle_url, archive)
        expected_sha = args.bundle_sha256 or str(manifest.get("bundle_sha256") or "")
        if expected_sha:
            actual_sha = file_sha256(archive)
            if actual_sha != expected_sha:
                raise SystemExit(f"Data bundle SHA mismatch: expected {expected_sha}, got {actual_sha}")
        unpacked = temp_path / "unpacked"
        unpacked.mkdir()
        unpack_tar_gz(archive, unpacked)
        staged = temp_path / "dataset"
        source = unpacked / "dataset" if (unpacked / "dataset").exists() else unpacked
        shutil.move(str(source), staged)
        if not dataset_satisfies_manifest(staged, manifest, bundle_manifest):
            print(json.dumps(missing_report(staged, manifest, bundle_manifest), indent=2, sort_keys=True))
            raise SystemExit("Downloaded data bundle does not satisfy manifest.")
        replace_tree(staged, args.dataset_root)
    print("Demo data provisioned and verified.")
    return 0


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def dataset_satisfies_manifest(dataset_root: Path, manifest: dict[str, Any], bundle_manifest: dict[str, Any] | None = None) -> bool:
    required = [str(path) for path in manifest.get("required_paths") or []]
    raw_required = [str(path) for path in manifest.get("required_raw_paths") or []]
    present = all((dataset_root / "canonical" / "v1" / path).exists() for path in required) and all(
        (dataset_root / "raw" / "idsse" / "figshare-28196177-v1" / path).exists()
        for path in raw_required
    )
    if not present:
        return False
    if bundle_manifest:
        for record in bundle_manifest.get("files") or []:
            relative = str(record.get("path") or "")
            expected = str(record.get("sha256") or "")
            if not relative or not expected:
                continue
            path = dataset_root / relative
            if not path.exists() or file_sha256(path) != expected:
                return False
    return True


def missing_report(dataset_root: Path, manifest: dict[str, Any], bundle_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    required = [str(path) for path in manifest.get("required_paths") or []]
    raw_required = [str(path) for path in manifest.get("required_raw_paths") or []]
    hash_mismatches = []
    if bundle_manifest:
        for record in bundle_manifest.get("files") or []:
            relative = str(record.get("path") or "")
            expected = str(record.get("sha256") or "")
            path = dataset_root / relative
            if relative and expected and path.exists():
                actual = file_sha256(path)
                if actual != expected:
                    hash_mismatches.append({"path": relative, "expected": expected, "actual": actual})
    return {
        "dataset_root": str(dataset_root),
        "missing_canonical": [
            path for path in required if not (dataset_root / "canonical" / "v1" / path).exists()
        ],
        "missing_raw": [
            path
            for path in raw_required
            if not (dataset_root / "raw" / "idsse" / "figshare-28196177-v1" / path).exists()
        ],
        "hash_mismatches": hash_mismatches,
    }


def download(url: str, destination: Path) -> None:
    if url.startswith("file://"):
        shutil.copyfile(url.removeprefix("file://"), destination)
        return
    with urllib.request.urlopen(url, timeout=300) as response:  # noqa: S310 - deployment-controlled URL.
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unpack_tar_gz(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            if destination.resolve() not in target.parents and target != destination.resolve():
                raise SystemExit(f"Unsafe path in data bundle: {member.name}")
        tar.extractall(destination, filter="data")


def replace_tree(source: Path, destination: Path) -> None:
    backup = destination.with_name(f"{destination.name}.previous")
    if backup.exists():
        shutil.rmtree(backup)
    if destination.exists():
        destination.rename(backup)
    source.rename(destination)
    if backup.exists():
        shutil.rmtree(backup)


if __name__ == "__main__":
    raise SystemExit(main())
