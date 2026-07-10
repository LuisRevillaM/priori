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
import errno
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Entrelíneas demo data for cloud Workbench.")
    parser.add_argument("--dataset-root", type=Path, default=Path("/var/data/dataset"))
    parser.add_argument("--cache-root", type=Path, default=Path(os.environ.get("TQE_CACHE_ROOT", "/var/data/cache")))
    parser.add_argument("--runtime-root", type=Path, default=Path(os.environ.get("TQE_RUNTIME_ROOT", "/var/data/runtime")))
    parser.add_argument("--manifest", type=Path, default=Path("config/deploy/demo-data-manifest.json"))
    parser.add_argument("--bundle-manifest", type=Path, default=Path(os.environ.get("TQE_DATA_BUNDLE_MANIFEST", "")) if os.environ.get("TQE_DATA_BUNDLE_MANIFEST") else None)
    parser.add_argument("--bundle-url", default=os.environ.get("TQE_DATA_BUNDLE_URL", ""))
    parser.add_argument("--bundle-sha256", default=os.environ.get("TQE_DATA_BUNDLE_SHA256", ""))
    args = parser.parse_args()

    manifest = read_json(args.manifest)
    args.dataset_root.mkdir(parents=True, exist_ok=True)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    args.runtime_root.mkdir(parents=True, exist_ok=True)
    bundle_manifest = read_json(args.bundle_manifest) if args.bundle_manifest else {}
    expected_sha = args.bundle_sha256 or str(manifest.get("bundle_sha256") or "")
    stamp_path = args.dataset_root.parent / ".tqe-data-bundle.json"
    stamp = read_json(stamp_path)
    installed_bundle_matches = not expected_sha or stamp.get("archive_sha256") == expected_sha
    if installed_bundle_matches and dataset_satisfies_manifest(
        args.dataset_root,
        manifest,
        bundle_manifest,
        cache_root=args.cache_root,
        runtime_root=args.runtime_root,
    ):
        print("Demo data already satisfies manifest.")
        return 0
    if not args.bundle_url:
        print("Demo data is missing and TQE_DATA_BUNDLE_URL is not configured.")
        print(
            json.dumps(
                missing_report(
                    args.dataset_root,
                    manifest,
                    bundle_manifest,
                    cache_root=args.cache_root,
                    runtime_root=args.runtime_root,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    staging_parent = provisioning_staging_parent(args.dataset_root)
    try:
        with tempfile.TemporaryDirectory(
            prefix="entrelineas-demo-data-",
            dir=staging_parent,
        ) as temp_dir:
            temp_path = Path(temp_dir)
            print(f"Demo data staging directory: {temp_path}")
            archive = temp_path / "bundle.tar.gz"
            download(args.bundle_url, archive)
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
            staged_cache = unpacked / "cache"
            staged_runtime = unpacked / "runtime"
            if not dataset_satisfies_manifest(
                staged,
                manifest,
                bundle_manifest,
                cache_root=staged_cache,
                runtime_root=staged_runtime,
            ):
                print(
                    json.dumps(
                        missing_report(
                            staged,
                            manifest,
                            bundle_manifest,
                            cache_root=staged_cache,
                            runtime_root=staged_runtime,
                        ),
                        indent=2,
                        sort_keys=True,
                    )
                )
                raise SystemExit("Downloaded data bundle does not satisfy manifest.")
            replace_tree(staged, args.dataset_root)
            if staged_cache.exists():
                replace_tree(staged_cache, args.cache_root)
            if staged_runtime.exists():
                replace_tree(staged_runtime, args.runtime_root)
            write_bundle_stamp(
                stamp_path,
                {
                    "schema_version": "tqe.data_bundle_install.v1",
                    "archive_sha256": file_sha256(archive),
                    "installed_at": datetime.now(UTC).isoformat(),
                },
            )
    finally:
        remove_empty_staging_parent(staging_parent)
    print("Demo data provisioned and verified.")
    return 0


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def provisioning_staging_parent(dataset_root: Path) -> Path:
    """Return a staging parent on the same persistent volume as the dataset."""

    persistent_root = dataset_root.resolve().parent
    staging_parent = persistent_root / ".tqe-provisioning"
    staging_parent.mkdir(parents=True, exist_ok=True)
    return staging_parent


def remove_empty_staging_parent(staging_parent: Path) -> None:
    """Remove the shared parent when no concurrent provisioner is using it."""

    try:
        staging_parent.rmdir()
    except OSError:
        pass


def dataset_satisfies_manifest(
    dataset_root: Path,
    manifest: dict[str, Any],
    bundle_manifest: dict[str, Any] | None = None,
    *,
    cache_root: Path | None = None,
    runtime_root: Path | None = None,
) -> bool:
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
            path = bundle_record_path(
                relative,
                dataset_root=dataset_root,
                cache_root=cache_root,
                runtime_root=runtime_root,
            )
            if not path.exists() or file_sha256(path) != expected:
                return False
    return True


def missing_report(
    dataset_root: Path,
    manifest: dict[str, Any],
    bundle_manifest: dict[str, Any] | None = None,
    *,
    cache_root: Path | None = None,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    required = [str(path) for path in manifest.get("required_paths") or []]
    raw_required = [str(path) for path in manifest.get("required_raw_paths") or []]
    hash_mismatches = []
    missing_bundle_files = []
    if bundle_manifest:
        for record in bundle_manifest.get("files") or []:
            relative = str(record.get("path") or "")
            expected = str(record.get("sha256") or "")
            path = bundle_record_path(
                relative,
                dataset_root=dataset_root,
                cache_root=cache_root,
                runtime_root=runtime_root,
            )
            if relative and expected and not path.exists():
                missing_bundle_files.append(relative)
            elif relative and expected and path.exists():
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
        "missing_bundle_files": missing_bundle_files,
        "hash_mismatches": hash_mismatches,
    }


def bundle_record_path(
    relative: str,
    *,
    dataset_root: Path,
    cache_root: Path | None,
    runtime_root: Path | None,
) -> Path:
    if relative.startswith("cache/"):
        return (cache_root or dataset_root.parent / "cache") / relative.removeprefix("cache/")
    if relative.startswith("runtime/"):
        return (runtime_root or dataset_root.parent / "runtime") / relative.removeprefix("runtime/")
    return dataset_root / relative


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


def write_bundle_stamp(path: Path, payload: dict[str, Any]) -> None:
    """Publish bundle identity only after every verified tree is installed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


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
        move_tree(destination, backup)
    move_tree(source, destination)
    if backup.exists():
        shutil.rmtree(backup)


def move_tree(source: Path, destination: Path) -> None:
    try:
        source.rename(destination)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        shutil.move(str(source), str(destination))


if __name__ == "__main__":
    raise SystemExit(main())
