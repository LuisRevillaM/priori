#!/usr/bin/env python3
"""GALLERY-2 oracle: both flagship asks are servable from one bootstrap."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from typing import Any


def get_json(url: str, *, timeout: int = 60) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read())
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--ready-timeout", type=int, default=600)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    deadline = time.time() + args.ready_timeout
    bootstrap: dict[str, Any] = {}
    while time.time() < deadline:
        bootstrap = get_json(f"{base}/api/film-room/bootstrap")
        if bootstrap.get("state") == "ready":
            break
        time.sleep(2)

    failures: list[str] = []
    if bootstrap.get("state") != "ready":
        failures.append(f"state={bootstrap.get('state')}")
    responses = bootstrap.get("flagship_responses")
    responses = responses if isinstance(responses, dict) else {}
    pressing = responses.get("pressing_map") if isinstance(responses.get("pressing_map"), dict) else {}
    retention = (
        responses.get("counterattack_sequence_rate")
        if isinstance(responses.get("counterattack_sequence_rate"), dict)
        else {}
    )
    if pressing.get("request_text") != "Where does each team win the ball back?":
        failures.append("pressing-map ask is not servable")
    if not retention.get("answer"):
        failures.append("retention-chain ask is not servable")

    answer = pressing.get("answer") if isinstance(pressing.get("answer"), dict) else {}
    moments = answer.get("moments") if isinstance(answer.get("moments"), list) else []
    raw = answer.get("raw_evidence") if isinstance(answer.get("raw_evidence"), dict) else {}
    table = raw.get("certified_table") if isinstance(raw.get("certified_table"), dict) else {}
    totals = table.get("totals") if isinstance(table.get("totals"), dict) else {}
    thirds = totals.get("third_counts") if isinstance(totals.get("third_counts"), dict) else {}
    population = int(totals.get("population_count") or 0)
    unknown = int(totals.get("location_unknown_count") or 0)
    located = sum(int(thirds.get(name) or 0) for name in ("defensive_third", "middle_third", "final_third"))
    if population != 2811:
        failures.append(f"pressing population={population}, expected 2811")
    if located + unknown != population:
        failures.append(f"third reconciliation={located}+{unknown}!={population}")
    if len(moments) != population:
        failures.append(f"watchable moments={len(moments)}, expected {population}")
    if any(moment.get("source_kind") != "result" for moment in moments if isinstance(moment, dict)):
        failures.append("pressing moments are not regain result descriptors")
    if located < 30 or (unknown / population if population else 1.0) > 0.5:
        failures.append("real pressing data does not qualify for ratio-first presentation")

    if moments:
        replay_window_id = str(moments[0].get("replay_window_id") or "")
        replay_url = f"{base}/api/film-room/replay-window?{urllib.parse.urlencode({'replay_window_id': replay_window_id})}"
        replay = get_json(replay_url).get("replay") or {}
        if not replay.get("frames"):
            failures.append("pressing replay hydration has no frames")
        if not (replay.get("overlays") or {}).get("stage_labels"):
            failures.append("pressing replay hydration has no regain label")

    if failures:
        print("ORACLE FAIL: " + "; ".join(failures), file=sys.stderr)
        return 1
    print(
        "PASS both asks | "
        f"pressing_moments={len(moments)} | defensive={thirds['defensive_third']} | "
        f"middle={thirds['middle_third']} | attacking={thirds['final_third']} | unknown={unknown}"
    )
    print("ORACLE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
