#!/usr/bin/env python3
"""Create the deterministic Cloud Workbench Alpha data bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("config/deploy/demo-data-manifest.json")
DEFAULT_ATTRIBUTION = Path("config/deploy/DATA_ATTRIBUTION.md")
DEFAULT_OUTPUT_DIR = Path("artifacts/cloud-alpha")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Priori cloud demo data bundle.")
    parser.add_argument("--dataset-root", type=Path, default=Path("data"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--attribution", type=Path, default=DEFAULT_ATTRIBUTION)
    parser.add_argument("--knowledge-pack", type=Path, default=Path("generated/tactical-knowledge-pack.json"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    manifest = read_json(args.manifest)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_id = str(manifest.get("bundle_id") or "priori-cloud-workbench-alpha")
    archive_path = output_dir / f"{bundle_id}.tar.gz"
    manifest_path = output_dir / f"{bundle_id}.manifest.json"

    with tempfile.TemporaryDirectory(prefix="priori-bundle-") as temp_dir:
        staging = Path(temp_dir) / "dataset"
        files = stage_dataset(
            dataset_root=args.dataset_root,
            staging_root=staging,
            manifest=manifest,
            attribution_path=args.attribution,
        )
        create_archive(staging.parent, archive_path)
    bundle_manifest = build_bundle_manifest(
        manifest=manifest,
        files=files,
        archive_path=archive_path,
        source_manifest_path=args.manifest,
        attribution_path=args.attribution,
        knowledge_pack_path=args.knowledge_pack,
    )
    write_json(manifest_path, bundle_manifest)
    print(json.dumps(bundle_manifest, indent=2, sort_keys=True))
    return 0


def stage_dataset(
    *,
    dataset_root: Path,
    staging_root: Path,
    manifest: dict[str, Any],
    attribution_path: Path,
) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for relative in manifest.get("required_paths") or []:
        source = dataset_root / "canonical" / "v1" / str(relative)
        destination = staging_root / "canonical" / "v1" / str(relative)
        files.append(copy_required_file(source, destination, f"canonical/v1/{relative}"))
    for relative in manifest.get("required_raw_paths") or []:
        source = dataset_root / "raw" / "idsse" / "figshare-28196177-v1" / str(relative)
        destination = staging_root / "raw" / "idsse" / "figshare-28196177-v1" / str(relative)
        files.append(copy_required_file(source, destination, f"raw/idsse/figshare-28196177-v1/{relative}"))
    if attribution_path.exists():
        destination = staging_root / "ATTRIBUTION.md"
        files.append(copy_required_file(attribution_path, destination, "ATTRIBUTION.md"))
    return files


def copy_required_file(source: Path, destination: Path, logical_path: str) -> dict[str, Any]:
    if not source.exists() or not source.is_file():
        raise SystemExit(f"Required bundle file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return file_record(destination, logical_path)


def create_archive(source_root: Path, archive_path: Path) -> None:
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(source_root.rglob("*")):
            info = tar.gettarinfo(str(path), arcname=path.relative_to(source_root).as_posix())
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            if path.is_file():
                with path.open("rb") as handle:
                    tar.addfile(info, handle)
            else:
                tar.addfile(info)


def build_bundle_manifest(
    *,
    manifest: dict[str, Any],
    files: list[dict[str, Any]],
    archive_path: Path,
    source_manifest_path: Path,
    attribution_path: Path,
    knowledge_pack_path: Path,
) -> dict[str, Any]:
    expanded_size = sum(int(file["size_bytes"]) for file in files)
    return {
        "schema_version": "1.0",
        "bundle_id": manifest.get("bundle_id"),
        "created_at": datetime.now(UTC).isoformat(),
        "source_commit": git_commit(),
        "source_dirty": git_dirty(),
        "source_manifest_path": str(source_manifest_path),
        "source_manifest_sha256": file_sha256(source_manifest_path) if source_manifest_path.exists() else "",
        "attribution_path": str(attribution_path),
        "attribution_sha256": file_sha256(attribution_path) if attribution_path.exists() else "",
        "knowledge_pack_path": str(knowledge_pack_path),
        "knowledge_pack_sha256": knowledge_pack_hash(knowledge_pack_path),
        "archive_path": str(archive_path),
        "archive_sha256": file_sha256(archive_path),
        "compressed_size_bytes": archive_path.stat().st_size,
        "expanded_size_bytes": expanded_size,
        "file_count": len(files),
        "files": sorted(files, key=lambda item: item["path"]),
    }


def file_record(path: Path, logical_path: str) -> dict[str, Any]:
    return {
        "path": logical_path,
        "size_bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def knowledge_pack_hash(path: Path) -> str:
    if not path.exists():
        return ""
    payload = read_json(path)
    return str(payload.get("knowledge_pack_sha256") or file_sha256(path))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_commit() -> str:
    return run_git(["rev-parse", "HEAD"])


def git_dirty() -> bool:
    return bool(run_git(["status", "--porcelain", "--untracked-files=no"]))


def run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
