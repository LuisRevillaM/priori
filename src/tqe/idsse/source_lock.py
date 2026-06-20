"""Official Figshare source lock for IDSSE / Sportec Open DFL data.

This module intentionally uses only the Python standard library. Gate A source
locking should work before the analytical stack is installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIGSHARE_ARTICLE_ID = 28196177
FIGSHARE_API_URL = f"https://api.figshare.com/v2/articles/{FIGSHARE_ARTICLE_ID}"
FIGSHARE_ARTICLE_URL = (
    "https://springernature.figshare.com/articles/dataset/"
    "An_integrated_dataset_of_spatiotemporal_and_event_data_in_elite_soccer/28196177"
)
DATASET_DOI = "10.6084/m9.figshare.28196177"
PAPER_DOI = "10.1038/s41597-025-04505-y"
SOURCE_VERSION = "figshare-28196177-v1"

EXPECTED_MATCH_IDS = (
    "J03WOH",
    "J03WOY",
    "J03WPY",
    "J03WQQ",
    "J03WR9",
    "J03WMX",
    "J03WN1",
)
MATCH_ID_CHOICES = (*EXPECTED_MATCH_IDS, "ALL")

LOCAL_FILE_NAMES = {
    "metadata": "metadata.xml",
    "events": "events.xml",
    "tracking": "tracking.xml",
}

_MATCH_ID_RE = re.compile(r"DFL-MAT-([A-Z0-9]+)")


class SourceLockError(RuntimeError):
    """Raised when official source files cannot be locked safely."""


@dataclass(frozen=True)
class FigshareFile:
    figshare_file_id: int
    name: str
    size: int
    download_url: str
    computed_md5: str | None
    match_id: str
    kind: str


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def fetch_figshare_article(api_url: str = FIGSHARE_API_URL) -> dict[str, Any]:
    request = urllib.request.Request(api_url, headers={"User-Agent": "priori-tqe/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def load_article(path: Path | None) -> dict[str, Any]:
    if path is None:
        return fetch_figshare_article()
    return json.loads(path.read_text(encoding="utf-8"))


def parse_match_id(name: str) -> str:
    match = _MATCH_ID_RE.search(name)
    if not match:
        raise SourceLockError(f"Could not parse match ID from Figshare file name: {name}")
    return match.group(1)


def parse_file_kind(name: str) -> str:
    if "_matchinformation_" in name:
        return "metadata"
    if "_events_raw_" in name:
        return "events"
    if "_positions_raw_observed_" in name:
        return "tracking"
    raise SourceLockError(f"Could not classify Figshare file name: {name}")


def article_files(article: dict[str, Any]) -> list[FigshareFile]:
    files: list[FigshareFile] = []
    for raw_file in article.get("files", []):
        name = str(raw_file["name"])
        files.append(
            FigshareFile(
                figshare_file_id=int(raw_file["id"]),
                name=name,
                size=int(raw_file["size"]),
                download_url=str(raw_file["download_url"]),
                computed_md5=raw_file.get("computed_md5"),
                match_id=parse_match_id(name),
                kind=parse_file_kind(name),
            )
        )
    return files


def select_match_files(article: dict[str, Any], match_id: str) -> list[FigshareFile]:
    selected = [file for file in article_files(article) if file.match_id == match_id]
    by_kind = {file.kind: file for file in selected}
    expected = set(LOCAL_FILE_NAMES)
    missing = expected - set(by_kind)
    extra = set(by_kind) - expected
    if missing or extra or len(selected) != len(expected):
        raise SourceLockError(
            f"Expected one metadata/events/tracking file for {match_id}; "
            f"missing={sorted(missing)} extra={sorted(extra)} count={len(selected)}"
        )
    return [by_kind[kind] for kind in ("metadata", "events", "tracking")]


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_existing(path: Path, source_file: FigshareFile) -> tuple[str, str]:
    local_size = path.stat().st_size
    if local_size != source_file.size:
        raise SourceLockError(
            f"Existing file size mismatch for {path}: {local_size} != {source_file.size}"
        )
    local_md5 = hash_file(path, "md5")
    if source_file.computed_md5 and local_md5 != source_file.computed_md5:
        raise SourceLockError(
            f"Existing file MD5 mismatch for {path}: {local_md5} != {source_file.computed_md5}"
        )
    local_sha256 = hash_file(path, "sha256")
    return local_md5, local_sha256


def download_file(source_file: FigshareFile, destination: Path, attempts: int = 3) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            source_file.download_url,
            headers={"User-Agent": "priori-tqe/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response, temp_path.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            temp_path.replace(destination)
            return
        except TimeoutError as exc:
            last_error = exc
            print(
                f"Timed out downloading {source_file.name} on attempt {attempt}/{attempts}",
                file=sys.stderr,
            )
            if attempt < attempts:
                time.sleep(2 * attempt)
    if last_error is not None:
        raise last_error


def ensure_local_file(source_file: FigshareFile, destination: Path, download: bool) -> dict[str, Any]:
    if not destination.exists():
        if not download:
            return {
                "exists": False,
                "local_size": None,
                "local_md5": None,
                "local_sha256": None,
                "status": "missing",
            }
        print(f"Downloading {source_file.name} -> {destination}", file=sys.stderr)
        download_file(source_file, destination)

    local_md5, local_sha256 = validate_existing(destination, source_file)
    return {
        "exists": True,
        "local_size": destination.stat().st_size,
        "local_md5": local_md5,
        "local_sha256": local_sha256,
        "status": "locked",
    }


def build_manifest(
    *,
    article: dict[str, Any],
    match_id: str,
    match_files: list[FigshareFile],
    raw_root: Path,
    artifact_dir: Path,
    download: bool,
) -> dict[str, Any]:
    raw_match_root = raw_root / SOURCE_VERSION / match_id
    file_records: list[dict[str, Any]] = []

    for source_file in match_files:
        local_path = raw_match_root / LOCAL_FILE_NAMES[source_file.kind]
        local_record = ensure_local_file(source_file, local_path, download)
        file_records.append(
            {
                "kind": source_file.kind,
                "figshare_file_id": source_file.figshare_file_id,
                "source_file_name": source_file.name,
                "source_size": source_file.size,
                "source_md5": source_file.computed_md5,
                "download_url": source_file.download_url,
                "local_path": str(local_path),
                **local_record,
            }
        )

    complete = all(record["status"] == "locked" for record in file_records)
    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "match_id": match_id,
        "complete": complete,
        "source": {
            "dataset_name": "IDSSE / Sportec Open DFL Tracking and Event Data",
            "dataset_doi": DATASET_DOI,
            "paper_doi": PAPER_DOI,
            "article_id": int(article.get("id", FIGSHARE_ARTICLE_ID)),
            "article_version": int(article.get("version", 1)),
            "article_doi": article.get("doi"),
            "article_api_url": FIGSHARE_API_URL,
            "article_url": FIGSHARE_ARTICLE_URL,
            "published_date": article.get("published_date"),
            "license": article.get("license"),
            "source_kind": "official_figshare",
            "mirror_status": "none",
        },
        "raw_root": str(raw_match_root),
        "artifact_dir": str(artifact_dir),
        "files": file_records,
    }


def build_corpus_manifest(
    *,
    article: dict[str, Any],
    raw_root: Path,
    artifact_dir: Path,
    download: bool,
) -> dict[str, Any]:
    match_manifests: list[dict[str, Any]] = []
    for match_id in EXPECTED_MATCH_IDS:
        match_artifact_dir = artifact_dir / "source-manifests" / match_id
        manifest = build_manifest(
            article=article,
            match_id=match_id,
            match_files=select_match_files(article, match_id),
            raw_root=raw_root,
            artifact_dir=match_artifact_dir,
            download=download,
        )
        write_json(match_artifact_dir / "source-manifest.json", manifest)
        match_manifests.append(manifest)

    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "scope": "corpus",
        "source_version": SOURCE_VERSION,
        "expected_match_ids": list(EXPECTED_MATCH_IDS),
        "complete": all(manifest["complete"] for manifest in match_manifests),
        "source": match_manifests[0]["source"] if match_manifests else {},
        "raw_root": str(raw_root / SOURCE_VERSION),
        "artifact_dir": str(artifact_dir),
        "matches": [
            {
                "match_id": manifest["match_id"],
                "complete": manifest["complete"],
                "raw_root": manifest["raw_root"],
                "manifest_path": str(
                    artifact_dir / "source-manifests" / manifest["match_id"] / "source-manifest.json"
                ),
                "files": manifest["files"],
            }
            for manifest in match_manifests
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-id", default="J03WOH", choices=MATCH_ID_CHOICES)
    parser.add_argument("--raw-root", default="data/raw/idsse")
    parser.add_argument("--artifact-dir", default="artifacts/m1/gate-a")
    parser.add_argument("--article-json", type=Path, help="Use a saved Figshare article JSON file.")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download missing official raw files before writing the manifest.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    article = load_article(args.article_json)
    if int(article.get("id", FIGSHARE_ARTICLE_ID)) != FIGSHARE_ARTICLE_ID:
        raise SourceLockError(f"Unexpected Figshare article id: {article.get('id')}")

    artifact_dir = Path(args.artifact_dir)
    if args.match_id == "ALL":
        manifest = build_corpus_manifest(
            article=article,
            raw_root=Path(args.raw_root),
            artifact_dir=artifact_dir,
            download=args.download,
        )
    else:
        match_files = select_match_files(article, args.match_id)
        manifest = build_manifest(
            article=article,
            match_id=args.match_id,
            match_files=match_files,
            raw_root=Path(args.raw_root),
            artifact_dir=artifact_dir,
            download=args.download,
        )
    manifest_path = artifact_dir / "source-manifest.json"
    write_json(manifest_path, manifest)
    print(f"Wrote {manifest_path}")
    if not manifest["complete"]:
        print(
            "Manifest is incomplete because one or more raw files are missing. "
            "Re-run with --download to lock local source files.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
