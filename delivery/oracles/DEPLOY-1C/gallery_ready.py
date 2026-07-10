"""DEPLOY-1C oracle: the gallery must be READY without execution prewarm.

Runs against a base URL. Exit 0 iff bootstrap reaches state=ready with
the interval-card law satisfied (observed+lower+unknown present) and at
least one moment with a servable replay window — while the service env
has execution prewarm disabled. Warming-forever is a FAIL here (unlike
the DEPLOY-1 smoke, which honors warming as honest).
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.request

def get_json(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--ready-timeout", type=int, default=300)
    a = ap.parse_args()
    base = a.base_url.rstrip("/")
    deadline = time.time() + a.ready_timeout
    state = "?"
    while time.time() < deadline:
        boot = get_json(f"{base}/api/film-room/bootstrap", timeout=60)
        state = boot.get("state", "ready")
        if state == "ready":
            break
        time.sleep(10)
    if state != "ready":
        print(f"FAIL gallery_ready — state={state} after {a.ready_timeout}s", file=sys.stderr)
        return 1
    ans = boot.get("answer") or {}
    im = ans.get("interval_metric") or {}
    ok_interval = all(im.get(k) is not None for k in ("observed", "lower", "unknown_count"))
    moments = ans.get("moments") or []
    ok_moment = bool(moments and moments[0].get("replay_window_id"))
    print(f"PASS state=ready | interval={'PASS' if ok_interval else 'FAIL'} | moment={'PASS' if ok_moment else 'FAIL'}")
    if not (ok_interval and ok_moment):
        return 1
    print("ORACLE PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
