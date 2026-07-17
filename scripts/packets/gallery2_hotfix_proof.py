#!/usr/bin/env python3
"""Prove GALLERY-2 isolation against old and refreshed bundle layouts."""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def cgroup_value(*paths: str) -> int | None:
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            continue
        value = path.read_text(encoding="utf-8").strip()
        if value and value != "max":
            return int(value)
    return None


def peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def configure_layout(layout_root: Path) -> None:
    os.environ["TQE_CACHE_ROOT"] = str(layout_root / "cache")
    os.environ["TQE_RUNTIME_ROOT"] = str(layout_root / "proof-runtime")
    os.environ["TQE_DATA_ROOT"] = str(layout_root / "dataset" / "canonical" / "v1")
    os.environ["TQE_RAW_ROOT"] = str(layout_root / "dataset" / "raw" / "idsse" / "v1")
    os.environ["WORKBENCH_PREWARM_FILM_ROOM"] = "0"


def reset_film_room_state(app_service: Any) -> None:
    with app_service.FILM_ROOM_PREWARM_LOCK:
        app_service.FILM_ROOM_PREWARMED_RESPONSES.clear()
        app_service.FILM_ROOM_PREWARM_RECORDS.clear()
        app_service.FILM_ROOM_REPLAY_INDEX.clear()
        app_service.FILM_ROOM_PREWARM_STATE.clear()
        app_service.FILM_ROOM_PREWARM_STATE.update(
            {
                "state": "warming",
                "started_at": None,
                "completed_at": None,
                "items": [],
                "last_error": None,
            }
        )


def hydrate(
    app_service: Any,
    *,
    response: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    answer = response.get("answer") if isinstance(response.get("answer"), dict) else {}
    moments = answer.get("moments") if isinstance(answer.get("moments"), list) else []
    first = moments[0] if moments and isinstance(moments[0], dict) else {}
    replay_window_id = str(first.get("replay_window_id") or "")
    if not replay_window_id:
        raise RuntimeError("servable flagship has no hydration target")
    hydrated = app_service.film_room_replay_window_response(
        {"replay_window_id": replay_window_id},
        output_root=output_root,
    )
    replay = hydrated.get("replay") if isinstance(hydrated.get("replay"), dict) else {}
    frames = replay.get("frames") if isinstance(replay.get("frames"), list) else []
    overlays = replay.get("overlays") if isinstance(replay.get("overlays"), dict) else {}
    stages = overlays.get("stage_labels") if isinstance(overlays.get("stage_labels"), list) else []
    if not frames or not stages:
        raise RuntimeError(f"hydration incomplete: {replay_window_id}")
    return {
        "replay_window_id": replay_window_id,
        "frame_count": len(frames),
        "stage_label_count": len(stages),
    }


def prove(
    *,
    layout_root: Path,
    mode: str,
    required_limit_bytes: int | None,
) -> dict[str, Any]:
    configure_layout(layout_root)
    from tqe.workshop import app_service

    cache_root = layout_root / "cache"
    output_root = layout_root / "proof-runtime"
    if not cache_root.is_dir():
        raise RuntimeError(f"bundle cache root is absent: {cache_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    app_service.CACHE_ROOT = cache_root

    configured_limit = cgroup_value(
        "/sys/fs/cgroup/memory.max",
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    )
    if required_limit_bytes is not None and configured_limit != required_limit_bytes:
        raise RuntimeError(
            f"sealed memory proof requires cgroup limit {required_limit_bytes}; "
            f"observed {configured_limit or 'none'}"
        )

    reset_film_room_state(app_service)
    app_service.initialize_film_room_prewarm(
        output_root=output_root,
        execution_enabled=False,
    )
    bootstrap = app_service.film_room_bootstrap_response(output_root=output_root)
    responses = (
        bootstrap.get("flagship_responses")
        if isinstance(bootstrap.get("flagship_responses"), dict)
        else {}
    )
    pressing = responses.get("pressing_map") if isinstance(responses.get("pressing_map"), dict) else {}
    retention = (
        responses.get("counterattack_sequence_rate")
        if isinstance(responses.get("counterattack_sequence_rate"), dict)
        else {}
    )
    retention_answer = (
        retention.get("answer") if isinstance(retention.get("answer"), dict) else {}
    )
    retention_moments = (
        retention_answer.get("moments")
        if isinstance(retention_answer.get("moments"), list)
        else []
    )
    if bootstrap.get("state") != "ready" or len(retention_moments) != 115:
        raise RuntimeError(
            f"retention isolation failed: state={bootstrap.get('state')} "
            f"moments={len(retention_moments)}"
        )

    pressing_answer = pressing.get("answer") if isinstance(pressing.get("answer"), dict) else None
    pressing_moments = (
        pressing_answer.get("moments")
        if isinstance(pressing_answer, dict)
        and isinstance(pressing_answer.get("moments"), list)
        else []
    )
    if mode == "old":
        refusal = pressing.get("refusal") if isinstance(pressing.get("refusal"), dict) else {}
        if pressing_answer is not None or refusal.get("gap_code") != app_service.FILM_ROOM_BUNDLED_DESCRIPTOR_ABSENT:
            raise RuntimeError("old layout did not expose the typed pressing absence")
        hydration_responses = [retention, retention]
        hydration_indices = [0, 1]
    else:
        if len(pressing_moments) != 2_811:
            raise RuntimeError(
                f"refreshed pressing population mismatch: {len(pressing_moments)}"
            )
        hydration_responses = [pressing, retention]
        hydration_indices = [0, 0]

    hydrations: list[dict[str, Any]] = []
    for response, moment_index in zip(hydration_responses, hydration_indices, strict=True):
        selected = dict(response)
        answer = dict(selected["answer"])
        answer["moments"] = [answer["moments"][moment_index]]
        selected["answer"] = answer
        hydrations.append(hydrate(app_service, response=selected, output_root=output_root))

    records = bootstrap.get("prewarm_records") if isinstance(bootstrap.get("prewarm_records"), list) else []
    if any(record.get("execution_performed") is not False for record in records if isinstance(record, dict)):
        raise RuntimeError("proof observed an execution-bearing prewarm record")

    cgroup_peak = cgroup_value(
        "/sys/fs/cgroup/memory.peak",
        "/sys/fs/cgroup/memory/memory.max_usage_in_bytes",
    )
    measured_peak = cgroup_peak or peak_rss_bytes()
    headroom = configured_limit - measured_peak if configured_limit is not None else None
    return {
        "schema_version": "gallery_2_hotfix_bundle_proof.v1",
        "mode": mode,
        "layout_root": str(layout_root),
        "execution_prewarm": False,
        "bootstrap_state": bootstrap["state"],
        "retention_moment_count": len(retention_moments),
        "pressing_moment_count": len(pressing_moments),
        "pressing_absence_code": (
            pressing.get("refusal", {}).get("gap_code")
            if isinstance(pressing.get("refusal"), dict)
            else None
        ),
        "descriptor_absences": app_service.FILM_ROOM_PREWARM_STATE.get(
            "descriptor_absences", {}
        ),
        "fragment_migration_count": sum(
            1
            for record in records
            if isinstance(record, dict)
            and record.get("prewarm_kind") == "descriptor_fragment_migration"
        ),
        "execution_cache_payloads_opened_by_migration": sum(
            int(record.get("execution_cache_bytes_opened") or 0)
            for record in records
            if isinstance(record, dict)
            and record.get("prewarm_kind") == "descriptor_fragment_migration"
        ),
        "hydrations": hydrations,
        "cgroup_limit_bytes": configured_limit,
        "memory_peak_bytes": measured_peak,
        "memory_peak_source": "cgroup" if cgroup_peak is not None else "process_ru_maxrss",
        "headroom_bytes": headroom,
        "sealed_2gib_proof": (
            configured_limit == 2 * 1024**3
            and cgroup_peak is not None
            and measured_peak < configured_limit
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("old", "refreshed"), required=True)
    parser.add_argument("--require-memory-limit-bytes", type=int)
    args = parser.parse_args()
    result = prove(
        layout_root=args.layout_root.resolve(),
        mode=args.mode,
        required_limit_bytes=args.require_memory_limit_bytes,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
