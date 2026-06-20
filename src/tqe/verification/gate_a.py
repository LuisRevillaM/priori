"""Gate A verification for the M1 one-match viability proof."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.idsse.source_lock import DATASET_DOI, FIGSHARE_ARTICLE_ID, hash_file

DEFAULT_ARTIFACT_DIR = Path("artifacts/m1/gate-a")
REQUIRED_GATE_A_ARTIFACTS = (
    "source-manifest.json",
    "canonical-summary.json",
    "raw-parity-report.json",
    "data-quality-report.json",
    "resource-report.json",
    "replay-bundle",
    "replay-screenshot.png",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def check(status: str, check_id: str, message: str, evidence: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"id": check_id, "status": status, "message": message}
    if evidence is not None:
        result["evidence"] = evidence
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_source_manifest(artifact_dir: Path) -> list[dict[str, Any]]:
    manifest_path = artifact_dir / "source-manifest.json"
    if not manifest_path.exists():
        return [
            check(
                "fail",
                "source_manifest.exists",
                "Source manifest is missing.",
                str(manifest_path),
            )
        ]

    checks: list[dict[str, Any]] = [
        check("pass", "source_manifest.exists", "Source manifest exists.", str(manifest_path))
    ]
    try:
        manifest = load_json(manifest_path)
    except json.JSONDecodeError as exc:
        return checks + [
            check("fail", "source_manifest.valid_json", f"Source manifest is invalid JSON: {exc}")
        ]

    checks.append(
        check(
            "pass" if manifest.get("schema_version") == "1.0" else "fail",
            "source_manifest.schema_version",
            "Source manifest schema version is 1.0.",
        )
    )
    checks.append(
        check(
            "pass" if manifest.get("match_id") == "J03WOH" else "fail",
            "source_manifest.match_id",
            "Source manifest targets Gate A match J03WOH.",
        )
    )
    source = manifest.get("source", {})
    checks.append(
        check(
            "pass" if source.get("dataset_doi") == DATASET_DOI else "fail",
            "source_manifest.dataset_doi",
            f"Dataset DOI is {DATASET_DOI}.",
        )
    )
    checks.append(
        check(
            "pass" if source.get("article_id") == FIGSHARE_ARTICLE_ID else "fail",
            "source_manifest.article_id",
            f"Figshare article ID is {FIGSHARE_ARTICLE_ID}.",
        )
    )
    checks.append(
        check(
            "pass" if source.get("source_kind") == "official_figshare" else "fail",
            "source_manifest.official_source",
            "Source kind is official_figshare.",
        )
    )
    checks.append(
        check(
            "pass" if source.get("mirror_status") == "none" else "fail",
            "source_manifest.no_mirror",
            "No mirror fallback was used.",
        )
    )

    file_records = manifest.get("files", [])
    expected_kinds = {"metadata", "events", "tracking"}
    actual_kinds = {record.get("kind") for record in file_records}
    checks.append(
        check(
            "pass" if actual_kinds == expected_kinds and len(file_records) == 3 else "fail",
            "source_manifest.file_set",
            "Manifest includes exactly metadata, events, and tracking source files.",
        )
    )

    for record in file_records:
        kind = str(record.get("kind"))
        local_path = Path(str(record.get("local_path", "")))
        if not local_path.exists():
            checks.append(
                check("fail", f"raw_file.{kind}.exists", f"Raw {kind} file is missing.", str(local_path))
            )
            continue
        checks.append(
            check("pass", f"raw_file.{kind}.exists", f"Raw {kind} file exists.", str(local_path))
        )

        source_size = int(record.get("source_size") or -1)
        local_size = local_path.stat().st_size
        checks.append(
            check(
                "pass" if local_size == source_size else "fail",
                f"raw_file.{kind}.size",
                f"Raw {kind} size matches official Figshare size.",
            )
        )

        source_md5 = record.get("source_md5")
        if source_md5:
            local_md5 = hash_file(local_path, "md5")
            checks.append(
                check(
                    "pass" if local_md5 == source_md5 else "fail",
                    f"raw_file.{kind}.md5",
                    f"Raw {kind} MD5 matches official Figshare checksum.",
                )
            )

        manifest_sha256 = record.get("local_sha256")
        local_sha256 = hash_file(local_path, "sha256")
        checks.append(
            check(
                "pass" if local_sha256 == manifest_sha256 else "fail",
                f"raw_file.{kind}.sha256",
                f"Raw {kind} SHA-256 matches the source manifest.",
            )
        )

    complete = manifest.get("complete") is True
    checks.append(
        check(
            "pass" if complete else "fail",
            "source_manifest.complete",
            "Source manifest is complete and all raw files are locally locked.",
        )
    )
    return checks


def validate_required_artifacts(artifact_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for artifact_name in REQUIRED_GATE_A_ARTIFACTS:
        if artifact_name == "source-manifest.json":
            continue
        artifact_path = artifact_dir / artifact_name
        if artifact_path.exists():
            checks.append(
                check(
                    "pass",
                    f"gate_a_artifact.{artifact_name}.exists",
                    f"Gate A artifact {artifact_name} exists.",
                    str(artifact_path),
                )
            )
            if artifact_name == "replay-bundle":
                replay_json = artifact_path / "replay.json"
                manifest_json = artifact_path / "manifest.json"
                for bundle_file in (replay_json, manifest_json):
                    checks.append(
                        check(
                            "pass" if bundle_file.exists() else "fail",
                            f"gate_a_artifact.replay-bundle.{bundle_file.name}.exists",
                            f"Replay bundle contains {bundle_file.name}.",
                            str(bundle_file),
                        )
                    )
                if manifest_json.exists():
                    try:
                        manifest = load_json(manifest_json)
                    except json.JSONDecodeError as exc:
                        checks.append(
                            check(
                                "fail",
                                "gate_a_artifact.replay-bundle.manifest.valid_json",
                                f"Replay manifest is invalid JSON: {exc}",
                                str(manifest_json),
                            )
                        )
                    else:
                        checks.append(
                            check(
                                "pass" if manifest.get("status") == "pass" else "fail",
                                "gate_a_artifact.replay-bundle.manifest.status",
                                "Replay manifest reports status=pass.",
                                str(manifest_json),
                            )
                        )
                        checks.append(
                            check(
                                "pass" if manifest.get("duration_seconds") == 30 else "fail",
                                "gate_a_artifact.replay-bundle.duration",
                                "Replay bundle covers 30 seconds.",
                                str(manifest_json),
                            )
                        )
                        checks.append(
                            check(
                                "pass" if manifest.get("frame_count") == 750 else "fail",
                                "gate_a_artifact.replay-bundle.frame_count",
                                "Replay bundle contains 750 frames at 25 Hz.",
                                str(manifest_json),
                            )
                        )
            if artifact_path.suffix == ".json":
                try:
                    payload = load_json(artifact_path)
                except json.JSONDecodeError as exc:
                    checks.append(
                        check(
                            "fail",
                            f"gate_a_artifact.{artifact_name}.valid_json",
                            f"Gate A artifact {artifact_name} is invalid JSON: {exc}",
                            str(artifact_path),
                        )
                    )
                    continue
                if "status" in payload:
                    checks.append(
                        check(
                            "pass" if payload.get("status") == "pass" else "fail",
                            f"gate_a_artifact.{artifact_name}.status",
                            f"Gate A artifact {artifact_name} reports status=pass.",
                            str(artifact_path),
                        )
                    )
        else:
            checks.append(
                check(
                    "not_ready",
                    f"gate_a_artifact.{artifact_name}.exists",
                    f"Gate A artifact {artifact_name} has not been generated yet.",
                    str(artifact_path),
                )
            )
        if artifact_name == "replay-screenshot.png" and artifact_path.exists():
            checks.append(
                check(
                    "pass" if artifact_path.stat().st_size > 0 else "fail",
                    "gate_a_artifact.replay-screenshot.png.non_empty",
                    "Replay screenshot is non-empty.",
                    str(artifact_path),
                )
            )
    return checks


def build_report(artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> dict[str, Any]:
    checks = validate_source_manifest(artifact_dir) + validate_required_artifacts(artifact_dir)
    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
        "not_ready": sum(1 for item in checks if item["status"] == "not_ready"),
    }
    status = "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail"
    return {
        "schema_version": "1.0",
        "gate": "Gate A - One-Match Viability Proof",
        "generated_at": utc_now_iso(),
        "status": status,
        "artifact_dir": str(artifact_dir),
        "summary": summary,
        "checks": checks,
        "next_required": [
            "Parse J03WOH into canonical Parquet.",
            "Emit raw XML parity and data-quality reports.",
            "Generate a canonical-data replay bundle and screenshot.",
        ]
        if status != "pass"
        else [],
    }


def write_report(report: dict[str, Any], artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / "verification-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir)
    report = build_report(artifact_dir)
    report_path = write_report(report, artifact_dir)
    print(f"Wrote {report_path}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
