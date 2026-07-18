#!/usr/bin/env python3
"""Exercise the GALLERY-2 metadata bootstrap and two lazy hydrations."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument  # noqa: E402
from tqe.workshop import app_service  # noqa: E402
from tqe.workshop.m1_2 import read_json  # noqa: E402


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


def reset_film_room_state() -> None:
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


def seed_fragments(*, output_root: Path, cache_root: Path) -> list[dict[str, Any]]:
    app_service.CACHE_ROOT = cache_root
    summaries: list[dict[str, Any]] = []
    for spec in app_service.film_room_flagship_specs():
        key = str(spec["key"])
        plan_path = Path(spec["plan_path"])
        payload = read_json(plan_path)
        for role, document in sorted(app_service.film_room_role_documents(payload).items()):
            executions: list[dict[str, Any]] = []
            if key != "pressing_map":
                bound = bind_document(TacticalQueryDocument.model_validate(document))
                executions = [
                    {
                        "role": role,
                        "execution": {
                            "bound_plan_hash": bound.bound_plan_hash,
                            "execution_id": "gallery2_local_proof_empty_legacy_fragment",
                            "results": [],
                        },
                        "cache_after_execute": {"cache_status": "PROOF_FRAGMENT"},
                        "bound_record": {"bound_plan_hash": bound.bound_plan_hash},
                    }
                ]
            summaries.append(
                app_service.write_film_room_descriptor_fragment(
                    key=key,
                    role=role,
                    plan_path=plan_path,
                    executions=executions,
                    output_root=output_root,
                )
            )
    return summaries


def proof(*, proof_root: Path, required_limit_bytes: int | None) -> dict[str, Any]:
    output_root = proof_root / "runtime"
    cache_root = proof_root / "cache"
    output_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    configured_limit = cgroup_value(
        "/sys/fs/cgroup/memory.max",
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    )
    if required_limit_bytes is not None and configured_limit != required_limit_bytes:
        raise RuntimeError(
            f"sealed memory proof requires cgroup limit {required_limit_bytes}; "
            f"observed {configured_limit or 'none'}"
        )

    reset_film_room_state()
    fragments = seed_fragments(output_root=output_root, cache_root=cache_root)
    app_service.initialize_film_room_prewarm(output_root=output_root, execution_enabled=False)
    bootstrap = app_service.film_room_bootstrap_response(output_root=output_root)
    responses = bootstrap.get("flagship_responses")
    if bootstrap.get("state") != "ready" or not isinstance(responses, dict):
        raise RuntimeError(f"gallery bootstrap did not become ready: {bootstrap.get('warming')}")
    for key in ("pressing_map", "counterattack_sequence_rate"):
        response = responses.get(key)
        if not isinstance(response, dict) or not isinstance(response.get("answer"), dict):
            raise RuntimeError(f"gallery ask is not servable: {key}")

    pressing = responses["pressing_map"]["answer"]
    moments = pressing.get("moments")
    if not isinstance(moments, list) or len(moments) != 2_811:
        raise RuntimeError(f"pressing descriptor population mismatch: {len(moments or [])}")
    replay_ids = [
        str(moment.get("replay_window_id") or "")
        for moment in moments
        if isinstance(moment, dict) and moment.get("replay_window_id")
    ][:2]
    if len(replay_ids) != 2:
        raise RuntimeError("pressing map did not expose two hydration targets")

    hydration_records: list[dict[str, Any]] = []
    for replay_window_id in replay_ids:
        hydrated = app_service.film_room_replay_window_response(
            {"replay_window_id": replay_window_id},
            output_root=output_root,
        )
        replay = hydrated.get("replay") if isinstance(hydrated.get("replay"), dict) else {}
        frames = replay.get("frames") if isinstance(replay.get("frames"), list) else []
        overlays = replay.get("overlays") if isinstance(replay.get("overlays"), dict) else {}
        if not frames or not overlays.get("stage_labels"):
            raise RuntimeError(f"hydration did not yield frames plus location overlay: {replay_window_id}")
        hydration_records.append(
            {
                "frame_count": len(frames),
                "replay_window_id": replay_window_id,
                "stage_label_count": len(overlays["stage_labels"]),
            }
        )

    cgroup_peak = cgroup_value(
        "/sys/fs/cgroup/memory.peak",
        "/sys/fs/cgroup/memory/memory.max_usage_in_bytes",
    )
    measured_peak = cgroup_peak or peak_rss_bytes()
    headroom = configured_limit - measured_peak if configured_limit is not None else None
    return {
        "bootstrap_state": bootstrap["state"],
        "counterattack_servable": True,
        "cgroup_limit_bytes": configured_limit,
        "descriptor_count": len(moments),
        "execution_prewarm": False,
        "fragment_summaries": fragments,
        "headroom_bytes": headroom,
        "hydrations": hydration_records,
        "memory_peak_bytes": measured_peak,
        "memory_peak_source": "cgroup" if cgroup_peak is not None else "process_ru_maxrss",
        "pressing_map_servable": True,
        "schema_version": "gallery_2_local_proof.v1",
        "sealed_2gib_proof": (
            configured_limit == 2 * 1024**3
            and cgroup_peak is not None
            and measured_peak < configured_limit
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-root", type=Path)
    parser.add_argument("--evidence-path", type=Path)
    parser.add_argument("--require-memory-limit-bytes", type=int)
    args = parser.parse_args()
    if args.proof_root:
        result = proof(
            proof_root=args.proof_root,
            required_limit_bytes=args.require_memory_limit_bytes,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="gallery2-local-proof-") as directory:
            result = proof(
                proof_root=Path(directory),
                required_limit_bytes=args.require_memory_limit_bytes,
            )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.evidence_path:
        args.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
