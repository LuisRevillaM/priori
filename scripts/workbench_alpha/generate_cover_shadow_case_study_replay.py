"""Generate a compact case-study replay for cover-shadow lane geometry."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.workbench_alpha.generate_moment_zero import FRAME_RATE_HZ, replay_window  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor  # noqa: E402
from tqe.runtime.ir import stable_hash  # noqa: E402
from tqe.verification.afl_cover_shadow import COVER_SHADOW_PLAN_PATH, primitive_probe  # noqa: E402

OUT_PATH = REPO_ROOT / "apps/workbench-alpha/public/case-study-cover-shadow-replays.json"


def main() -> None:
    canonical_root = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
    raw_root = Path(os.environ.get("TQE_RAW_ROOT", "data/raw/idsse/figshare-28196177-v1"))
    executor = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root)
    records, _fail_fixture, _unknown_fixture = primitive_probe(COVER_SHADOW_PLAN_PATH, executor)
    pass_records = [record for record in records if record.get("cover_shadow_status") == "PASS"]
    if not pass_records:
        raise RuntimeError("No PASS cover-shadow records available for case-study replay.")

    selected = select_representative_record(pass_records)
    payload = payload_from_record(selected, canonical_root=canonical_root)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "case_study_cover_shadow_replay_packet.v0",
                "source": {
                    "plan_path": str(COVER_SHADOW_PLAN_PATH),
                    "plan_hash": stable_hash(json.loads(COVER_SHADOW_PLAN_PATH.read_text(encoding="utf-8"))),
                    "selection": "short local ball-target lane with screening defender clearly inside threshold band",
                },
                "replays": [{"index": 0, "payload": payload}],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "path": str(OUT_PATH.relative_to(REPO_ROOT)),
                "match_id": payload["moment"]["match_id"],
                "period": payload["moment"]["period"],
                "anchor_frame_id": payload["moment"]["anchor_frame_id"],
                "lane_length_m": payload["moment"]["lane_length_m"],
                "screening_defender_distance_to_lane_m": payload["moment"]["screening_defender_distance_to_lane_m"],
                "frame_count": len(payload["replay"]["frames"]),
            },
            sort_keys=True,
        )
    )


def select_representative_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    readable = [
        record
        for record in records
        if 8.0 <= float(record.get("lane_length_m") or 0.0) <= 18.0
        and float(record.get("screening_defender_distance_to_lane_m") or 99.0) <= 1.2
        and 0.25 <= float(record.get("screening_defender_projection_fraction") or 0.0) <= 0.78
    ]
    candidates = readable or records
    ideal_lane_length_m = 12.0
    return max(
        candidates,
        key=lambda record: (
            -abs(float(record.get("lane_length_m") or 0.0) - ideal_lane_length_m),
            -float(record.get("screening_defender_distance_to_lane_m") or 99.0),
            int(record.get("observed_defender_count") or 0),
            -abs(float(record.get("screening_defender_projection_fraction") or 0.0) - 0.50),
            -int(record.get("anchor_frame_id") or 0),
        ),
    )


def payload_from_record(record: dict[str, Any], *, canonical_root: Path) -> dict[str, Any]:
    anchor_frame_id = int(record["anchor_frame_id"])
    start_frame_id = max(anchor_frame_id - FRAME_RATE_HZ, 0)
    end_frame_id = anchor_frame_id + FRAME_RATE_HZ
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(record["match_id"]),
        period=str(record["period"]),
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        raw_root=None,
    )
    replay["replay_window_id"] = (
        f"case_study_cover_shadow_{record['match_id']}_{record['period']}_{start_frame_id}_{end_frame_id}"
    )
    replay["source_id"] = "case_study_cover_shadow"
    replay["generated_at"] = "deterministic_from_cover_shadow_verification_plan"
    replay["anchor_frame_id"] = anchor_frame_id
    return {
        "schema_version": "coach_moment.cover_shadow.v0",
        "moment": {
            "anchor_id": record["anchor_id"],
            "match_id": record["match_id"],
            "period": record["period"],
            "team_role": record.get("team_role"),
            "anchor_frame_id": anchor_frame_id,
            "cover_shadow_status": record["cover_shadow_status"],
            "passing_lane_denial_status": record["passing_lane_denial_status"],
            "cover_shadow_reason": record["cover_shadow_reason"],
            "target_entity_id": record["target_entity_id"],
            "ball_point": record["ball_point"],
            "target_point": record["target_point"],
            "lane_length_m": float(record["lane_length_m"]),
            "observed_defender_count": int(record["observed_defender_count"]),
            "minimum_observed_defenders": int(record["minimum_observed_defenders"]),
            "maximum_lane_distance_m": float(record["maximum_lane_distance_m"]),
            "minimum_projection_fraction": float(record["minimum_projection_fraction"]),
            "screening_defender_id": record["screening_defender_id"],
            "screening_defender_distance_to_lane_m": float(record["screening_defender_distance_to_lane_m"]),
            "screening_defender_projection_fraction": float(record["screening_defender_projection_fraction"]),
            "screening_defender_point": record["screening_defender_point"],
            "screening_projection_point": record["screening_projection_point"],
            "screening_defender_evidence": record["screening_defender_evidence"],
            "coverage_status": record["coverage_status"],
            "claim_boundary": record["cover_shadow_claim_boundary"],
        },
        "replay": replay,
        "visual_contract": {
            "ball_target_lane": ["ball_point", "target_point", "lane_length_m"],
            "screening_defender": [
                "screening_defender_id",
                "screening_defender_point",
                "screening_projection_point",
                "screening_defender_distance_to_lane_m",
                "screening_defender_projection_fraction",
            ],
            "thresholds": [
                "maximum_lane_distance_m",
                "minimum_projection_fraction",
                "minimum_observed_defenders",
            ],
            "prohibited_visual_claims": [
                "defender intent",
                "passing probability",
                "pitch-control value",
                "tactical denial quality",
                "moving-ball interception",
            ],
        },
    }


if __name__ == "__main__":
    main()
