"""Generate a compact case-study replay for observed team-press geometry."""

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
from tqe.verification.afl_team_press import TEAM_PRESS_PLAN_PATH, primitive_probe  # noqa: E402

OUT_PATH = REPO_ROOT / "apps/workbench-alpha/public/case-study-team-press-replays.json"


def main() -> None:
    canonical_root = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
    raw_root = Path(os.environ.get("TQE_RAW_ROOT", "data/raw/idsse/figshare-28196177-v1"))
    executor = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root)
    records, _fail_fixture, _unknown_fixture = primitive_probe(TEAM_PRESS_PLAN_PATH, executor)
    pass_records = [record for record in records if record.get("team_press_status") == "PASS"]
    if not pass_records:
        raise RuntimeError("No PASS team-press records available for case-study replay.")

    selected = sorted(
        pass_records,
        key=lambda record: (
            -int(record.get("pressure_actor_count") or 0),
            -float(record.get("pressure_angle_spread_degrees") or 0.0),
            int(record.get("anchor_frame_id") or 0),
        ),
    )[0]
    payload = payload_from_record(selected, canonical_root=canonical_root)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "case_study_team_press_replay_packet.v0",
                "source": {
                    "plan_path": str(TEAM_PRESS_PLAN_PATH),
                    "plan_hash": stable_hash(json.loads(TEAM_PRESS_PLAN_PATH.read_text(encoding="utf-8"))),
                    "selection": "highest pressure_actor_count, then highest pressure_angle_spread_degrees",
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
                "pressure_actor_count": payload["moment"]["pressure_actor_count"],
                "pressure_angle_spread_degrees": payload["moment"]["pressure_angle_spread_degrees"],
                "frame_count": len(payload["replay"]["frames"]),
            },
            sort_keys=True,
        )
    )


def payload_from_record(record: dict[str, Any], *, canonical_root: Path) -> dict[str, Any]:
    anchor_frame_id = int(record["anchor_frame_id"])
    start_frame_id = max(anchor_frame_id - FRAME_RATE_HZ, 0)
    end_frame_id = anchor_frame_id + FRAME_RATE_HZ * 2
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(record["match_id"]),
        period=str(record["period"]),
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        raw_root=None,
    )
    replay["replay_window_id"] = (
        f"case_study_team_press_{record['match_id']}_{record['period']}_{start_frame_id}_{end_frame_id}"
    )
    replay["source_id"] = "case_study_team_press"
    replay["generated_at"] = "deterministic_from_team_press_verification_plan"
    replay["anchor_frame_id"] = anchor_frame_id
    carrier_id = str(record["carrier_id"])
    return {
        "schema_version": "coach_moment.team_press.v0",
        "moment": {
            "anchor_id": record["anchor_id"],
            "match_id": record["match_id"],
            "period": record["period"],
            "team_role": record.get("team_role"),
            "anchor_frame_id": anchor_frame_id,
            "carrier_id": carrier_id,
            "team_press_status": record["team_press_status"],
            "team_press_reason": record["team_press_reason"],
            "pressure_actor_ids": record["pressure_actor_ids"],
            "pressure_actor_count": int(record["pressure_actor_count"]),
            "nearby_defender_ids": record["nearby_defender_ids"],
            "nearby_defender_count": int(record["nearby_defender_count"]),
            "observed_defender_count": int(record["observed_defender_count"]),
            "pressure_angle_spread_degrees": round(float(record["pressure_angle_spread_degrees"]), 1),
            "maximum_press_distance_m": float(record["maximum_press_distance_m"]),
            "minimum_pressing_defenders": int(record["minimum_pressing_defenders"]),
            "minimum_angle_spread_degrees": float(record["minimum_angle_spread_degrees"]),
            "minimum_observed_defenders": int(record["minimum_observed_defenders"]),
            "lookback_seconds": float(record["lookback_seconds"]),
            "carrier_point": record["carrier_point"],
            "pressure_actor_evidence": record["pressure_actor_evidence"],
            "nearby_defender_evidence": record["nearby_defender_evidence"],
            "coverage_status": record["coverage_status"],
            "claim_boundary": record["team_press_claim_boundary"],
        },
        "replay": replay,
        "visual_contract": {
            "carrier": ["carrier_id", "carrier_point", "anchor_frame_id"],
            "pressure_actors": ["pressure_actor_ids", "pressure_actor_evidence"],
            "thresholds": [
                "maximum_press_distance_m",
                "minimum_pressing_defenders",
                "minimum_angle_spread_degrees",
                "minimum_observed_defenders",
            ],
            "prohibited_visual_claims": [
                "coordinated press",
                "press trap",
                "pressing trigger",
                "defensive intent",
                "pressure quality",
                "tactical causation",
            ],
        },
    }


if __name__ == "__main__":
    main()
