"""DEPLOY-2 oracle: the live gallery shows the STORY, not just dots.

Exit 0 iff bootstrap is ready AND the flagship answer's moments are
chain records (multiple moments, stage witnesses present) AND at least
one moment's replay window carries stage overlays (labels/trail data).
The certified-table fallback (single aggregate moment, no stages) FAILS
this oracle — that is the point.
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.request

def get_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())

def post_json(url, payload, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--ready-timeout", type=int, default=600)
    a = ap.parse_args()
    base = a.base_url.rstrip("/")
    deadline = time.time() + a.ready_timeout
    boot, state = {}, "?"
    while time.time() < deadline:
        boot = get_json(f"{base}/api/film-room/bootstrap")
        state = boot.get("state", "ready")
        if state == "ready":
            break
        time.sleep(15)
    fails = []
    if state != "ready":
        fails.append(f"state={state}")
    ans = boot.get("answer") or {}
    moments = ans.get("moments") or []
    if len(moments) < 2:
        fails.append(f"moments={len(moments)} (chain gallery needs the population, not one aggregate)")
    chainlike = [m for m in moments if m.get("source_kind") == "chain_record"]
    if not chainlike:
        fails.append("no chain_record moments")
    if chainlike:
        win_id = chainlike[0].get("replay_window_id")
        win = post_json(f"{base}/api/film-room/replay-window", {"replay_window_id": win_id})
        replay = win.get("replay") or {}
        overlays = replay.get("overlays") or (win.get("overlays") or {})
        stages = overlays.get("stages") if isinstance(overlays, dict) else None
        if not stages:
            fails.append("replay window carries no stage overlays")
        else:
            print(f"PASS overlays: {len(stages)} stages")
    if fails:
        print("ORACLE FAIL: " + "; ".join(fails), file=sys.stderr)
        return 1
    print(f"PASS ready | moments={len(moments)} | chain_records={len(chainlike)}")
    print("ORACLE PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
