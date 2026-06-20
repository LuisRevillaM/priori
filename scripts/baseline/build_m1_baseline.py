"""Generate tracked M1 baseline manifests from verified local artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASELINE_DIR = Path("delivery/m1/baseline")

M1_VERIFICATION = Path("artifacts/m1/verification-report.json")
QUERY_FREEZE = Path("artifacts/m1/gate-c/query-freeze.json")
ACCEPTED_RESULTS = Path("artifacts/m1/gate-c/accepted-results.json")
NEAR_MISSES = Path("artifacts/m1/gate-c/near-misses.json")
PROOF_PACK = Path("artifacts/m1/gate-c/proof-pack-manifest.json")
SEMANTIC_GOLD = Path("docs/queries/ball-side-block-shift/semantic-gold-set.v1.json")

LEGACY_DETECTOR_SOURCE_FILES = [
    Path("config/queries/ball_side_block_shift.v1.yaml"),
    Path("src/tqe/query/ball_side_block_shift.py"),
    Path("src/tqe/evidence/gate_c_build.py"),
    Path("src/tqe/verification/gate_c.py"),
    Path("apps/replay-proof/src/verifyBundles.ts"),
]

M1_SOURCE_FILES = [
    Path("Makefile"),
    Path("pyproject.toml"),
    Path("delivery/m1/SPEC.md"),
    Path("delivery/m1/status.yaml"),
    Path("docs/queries/ball-side-block-shift/definition.md"),
    Path("docs/queries/ball-side-block-shift/calibration-log.md"),
    SEMANTIC_GOLD,
    *LEGACY_DETECTOR_SOURCE_FILES,
]


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def combined_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def git_output(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return None


def file_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: str(item)):
        records.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return records


def selected_result_record(result: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "result_id",
        "match_id",
        "period",
        "classification",
        "quality_status",
        "query_hash",
        "query_id",
        "query_version",
        "perspective_team_role",
        "wide_entry_frame_id",
        "baseline_start_frame_id",
        "baseline_end_frame_id",
        "anchor_frame_id",
        "outcome_frame_id",
        "replay_start_frame_id",
        "replay_end_frame_id",
        "signed_shift_metres",
        "block_shift_score",
    ]
    return {field: result[field] for field in fields if field in result}


def build_legacy_result_manifest(
    *,
    generated_at: str,
    query_freeze: dict[str, Any],
    accepted_results: list[dict[str, Any]],
    near_misses: list[dict[str, Any]],
) -> dict[str, Any]:
    by_class = Counter(str(item["classification"]) for item in accepted_results)
    by_match = Counter(str(item["match_id"]) for item in accepted_results)
    near_by_reason = Counter(str(item.get("near_miss_reason")) for item in near_misses)
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "purpose": "Tracked M1 legacy result oracle manifest for M1.1 parity.",
        "query": {
            "query_id": query_freeze["canonical_config"]["query_id"],
            "query_version": query_freeze["canonical_config"]["query_version"],
            "query_hash": query_freeze["query_hash"],
            "config_path": query_freeze["config_path"],
        },
        "selected_result_count": len(accepted_results),
        "selected_results_by_classification": dict(sorted(by_class.items())),
        "selected_results_by_match": dict(sorted(by_match.items())),
        "near_miss_count": len(near_misses),
        "near_misses_by_reason": dict(sorted(near_by_reason.items())),
        "selected_results": [selected_result_record(item) for item in accepted_results],
        "near_miss_keys": [
            {
                "result_id": item.get("result_id"),
                "match_id": item["match_id"],
                "period": item["period"],
                "wide_entry_frame_id": item["wide_entry_frame_id"],
                "anchor_frame_id": item["anchor_frame_id"],
                "classification": item.get("classification"),
                "near_miss_reason": item.get("near_miss_reason"),
                "signed_shift_metres": item.get("signed_shift_metres"),
            }
            for item in near_misses
        ],
    }


def build_evidence_bundle_manifest(
    *,
    generated_at: str,
    proof_pack: dict[str, Any],
) -> dict[str, Any]:
    bundles: list[dict[str, Any]] = []
    for item in proof_pack["evidence_bundles"]:
        bundle_json = Path(item["bundle_json"])
        replay_json = Path(item["replay_json"])
        bundles.append(
            {
                "result_id": item["result_id"],
                "match_id": item["match_id"],
                "classification": item["classification"],
                "bundle_json": str(bundle_json),
                "bundle_json_sha256": sha256_file(bundle_json),
                "bundle_json_bytes": bundle_json.stat().st_size,
                "replay_json": str(replay_json),
                "replay_json_sha256": sha256_file(replay_json),
                "replay_json_bytes": replay_json.stat().st_size,
            }
        )
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "purpose": "Tracked M1 evidence bundle hash manifest for M1.1 baseline freeze.",
        "proof_pack_manifest": str(PROOF_PACK),
        "proof_pack_manifest_sha256": sha256_file(PROOF_PACK),
        "selected_result_count": proof_pack["selected_result_count"],
        "query_hash": proof_pack["query_hash"],
        "hard_floor": proof_pack["hard_floor"],
        "bundles": bundles,
    }


def build_baseline_manifest(
    *,
    generated_at: str,
    verification: dict[str, Any],
    query_freeze: dict[str, Any],
    accepted_results: list[dict[str, Any]],
    proof_pack: dict[str, Any],
) -> dict[str, Any]:
    branch = git_output(["branch", "--show-current"])
    head = git_output(["rev-parse", "HEAD"])
    git_status = git_output(["status", "--short"])
    legacy_source_files = file_records(LEGACY_DETECTOR_SOURCE_FILES)
    m1_source_files = file_records(M1_SOURCE_FILES)
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "purpose": "Tracked M1 baseline freeze manifest for M1.1 implementation precondition.",
        "baseline_state": {
            "git_branch": branch,
            "git_head_at_generation": head,
            "git_head_note": "null means this manifest was generated before the baseline commit existed",
            "git_status_short_at_generation": git_status.splitlines() if git_status else [],
            "baseline_commit": "the commit that contains this manifest",
        },
        "m1_verification": {
            "status": verification["status"],
            "gate_reports": verification["gate_reports"],
            "report_path": str(M1_VERIFICATION),
            "report_sha256": sha256_file(M1_VERIFICATION),
        },
        "m1_acceptance_state": {
            "state": "VERIFIED_CONTROLLER_ONLY",
            "owner_acceptance": "PENDING_FINAL_M1_ACCEPTANCE",
            "independent_review": "WAIVED_BY_OWNER_FOR_GATE_A_GATE_B_AND_GATE_C",
            "m1_1_owner_waiver_required_if_no_final_acceptance": True,
        },
        "query_freeze": {
            "query_hash": query_freeze["query_hash"],
            "query_id": query_freeze["canonical_config"]["query_id"],
            "query_version": query_freeze["canonical_config"]["query_version"],
            "config_path": query_freeze["config_path"],
            "config_sha256": sha256_file(Path(query_freeze["config_path"])),
            "query_freeze_path": str(QUERY_FREEZE),
            "query_freeze_sha256": sha256_file(QUERY_FREEZE),
        },
        "legacy_detector_source_hash": {
            "combined_sha256": combined_sha256(LEGACY_DETECTOR_SOURCE_FILES),
            "files": legacy_source_files,
        },
        "m1_source_hash": {
            "combined_sha256": combined_sha256(M1_SOURCE_FILES),
            "files": m1_source_files,
        },
        "legacy_result_manifest": {
            "path": "delivery/m1/baseline/legacy-result-manifest.json",
            "selected_result_count": len(accepted_results),
            "selected_result_ids": [item["result_id"] for item in accepted_results],
        },
        "evidence_bundle_manifest": {
            "path": "delivery/m1/baseline/evidence-bundle-manifest.json",
            "selected_result_count": proof_pack["selected_result_count"],
        },
        "semantic_gold_set": {
            "path": str(SEMANTIC_GOLD),
            "sha256": sha256_file(SEMANTIC_GOLD),
        },
    }


def main() -> int:
    for path in (M1_VERIFICATION, QUERY_FREEZE, ACCEPTED_RESULTS, NEAR_MISSES, PROOF_PACK, SEMANTIC_GOLD):
        if not path.exists():
            raise FileNotFoundError(path)

    generated_at = utc_now_iso()
    verification = read_json(M1_VERIFICATION)
    query_freeze = read_json(QUERY_FREEZE)
    accepted_results = read_json(ACCEPTED_RESULTS)
    near_misses = read_json(NEAR_MISSES)
    proof_pack = read_json(PROOF_PACK)

    if verification["status"] != "pass":
        raise RuntimeError("M1 verification report must pass before baseline freeze")
    if query_freeze["status"] != "pass" or proof_pack["status"] != "pass":
        raise RuntimeError("Gate C query freeze and proof pack must pass before baseline freeze")

    write_json(
        BASELINE_DIR / "legacy-result-manifest.json",
        build_legacy_result_manifest(
            generated_at=generated_at,
            query_freeze=query_freeze,
            accepted_results=accepted_results,
            near_misses=near_misses,
        ),
    )
    write_json(
        BASELINE_DIR / "evidence-bundle-manifest.json",
        build_evidence_bundle_manifest(generated_at=generated_at, proof_pack=proof_pack),
    )
    write_json(
        BASELINE_DIR / "m1-baseline-manifest.json",
        build_baseline_manifest(
            generated_at=generated_at,
            verification=verification,
            query_freeze=query_freeze,
            accepted_results=accepted_results,
            proof_pack=proof_pack,
        ),
    )
    print(f"Wrote {BASELINE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
