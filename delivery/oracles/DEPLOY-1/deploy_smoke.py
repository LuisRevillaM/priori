"""DEPLOY-1 oracle: binary smoke against a Film Room deployment.

Usage: deploy_smoke.py --base-url http://127.0.0.1:8765 [--demo-token T]
Exit 0 = deployment serves the product honestly; nonzero = failure,
one line per failed check on stderr. Runnable against local and Render.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request


def get(url: str, timeout: float = 30.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def post(url: str, payload: dict, timeout: float = 30.0):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--demo-token", default=None)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = ""):
        print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
        if not ok:
            failures.append(name)

    # 1. The surface serves.
    try:
        status, body = get(f"{base}/film-room")
        check("film_room_page", status == 200 and b"ENTREL" in body.upper())
    except Exception as e:
        check("film_room_page", False, str(e))

    # 2. Bootstrap: prewarmed content OR an honest warming state — never a hang.
    try:
        status, raw = get(f"{base}/api/film-room/bootstrap", timeout=60)
        boot = json.loads(raw)
        state = boot.get("state") or ("ready" if boot.get("answer") else "unknown")
        check("bootstrap_honest", status == 200 and state in ("ready", "warming"), f"state={state}")
        if state == "ready":
            interval = (boot.get("answer") or {}).get("interval_metric") or {}
            check(
                "interval_card_law",
                interval.get("observed") is not None
                and interval.get("lower") is not None
                and interval.get("unknown_count") is not None,
            )
            prov = (boot.get("answer") or {}).get("provenance") or boot.get("provenance") or {}
            check("provenance_present", bool(prov))
    except Exception as e:
        check("bootstrap_honest", False, str(e))

    # 3. Replay frames serve (only when ready).
    try:
        status, raw = get(f"{base}/api/film-room/bootstrap", timeout=60)
        boot = json.loads(raw)
        moments = (boot.get("answer") or {}).get("moments") or []
        if moments and moments[0].get("replay_window_id"):
            window_id = moments[0]["replay_window_id"]
            status, win = post(
                f"{base}/api/film-room/replay-window",
                {"replay_window_id": window_id},
                timeout=30,
            )
            replay = win.get("replay") or win.get("window") or win
            frames = replay.get("frames") or []
            first = frames[0].get("frame_id") if frames and isinstance(frames[0], dict) else replay.get("anchor_frame_id")
            if first is None:
                check("replay_frame_serves", False, f"no frame ids in window payload keys={list(win)[:6]}")
            else:
                status, resp = post(
                    f"{base}/api/film-room/replay-frame",
                    {"replay_window_id": window_id, "frame_id": int(first)},
                    timeout=30,
                )
                check("replay_frame_serves", status == 200 and resp.get("ok", True) is not False)
        else:
            print("SKIP replay_frame_serves — no ready moments")
    except Exception as e:
        check("replay_frame_serves", False, str(e))

    # 4. Live asks are gated: without token → typed, honest refusal of the
    #    gate (never a schema lie, never a model call); with token → accepted
    #    or an honestly-typed model-side outcome.
    ask = {"text": "Show controlled passes."}
    status, resp = post(f"{base}/api/film-room/ask", ask, timeout=20)
    err = str(resp.get("error_code", ""))
    gated = status in (401, 403) or err in ("DEMO_TOKEN_REQUIRED", "ASKS_DISABLED")
    check("ask_gated_without_token", gated, f"status={status} code={err}")
    if args.demo_token:
        status, resp = post(
            f"{base}/api/film-room/ask", {**ask, "demo_token": args.demo_token}, timeout=600
        )
        ok_shapes = ("expression", "clarification_required", "understood_but_not_expressible",
                     "unsupported_modality", "MODEL_OUTPUT_TRUNCATED", "INTERNAL_ERROR")
        outcome = resp.get("outcome") or resp.get("error_code")
        check("ask_with_token_typed", status in (200, 500) and str(outcome) in ok_shapes,
              f"outcome={outcome}")

    if failures:
        print(f"\nORACLE FAIL ({len(failures)}): {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nORACLE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
