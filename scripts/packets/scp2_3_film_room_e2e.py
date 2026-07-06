#!/usr/bin/env python3
"""SCP2-3 Film Room end-to-end provenance check."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.ir import stable_hash  # noqa: E402
from tqe.workshop.app_service import film_room_execute_document, stable_json_sha256  # noqa: E402
from tqe.workshop.m1_2 import replay_window_from_canonical  # noqa: E402

FLAGSHIP_ASK = "After a regain, how often does the team progress the ball by carry and keep it with a controlled pass?"
TABLE_PATH = ROOT / "delivery/packets/r2-4-flagship/counterattack_initiation_table.json"
PREWARM_PLAN_PATHS = [
    ROOT / "delivery/packets/r2-2-flagship/fragile_retention_rate_v0.json",
    ROOT / "delivery/packets/r2-4-flagship/counterattack_initiation_v0.json",
]
EVIDENCE_DIR = ROOT / "delivery/packets/scp2-3-evidence"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def post_json(url: str, payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, *, timeout: int) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def wait_ready(base_url: str, *, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            payload = get_json(f"{base_url}/readyz", timeout=5)
            if payload.get("ok") is True:
                return
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"service did not become ready: {last_error}")


def assert_canonical_frame_match(response: dict[str, Any], *, base_url: str, timeout: int) -> list[dict[str, Any]]:
    answer = response["answer"]
    replay = answer["replay"]
    sampled = [
        replay["frames"][0],
        replay["frames"][len(replay["frames"]) // 2],
        replay["frames"][-1],
    ]
    canonical = replay_window_from_canonical(
        replay_window_id=replay["replay_window_id"],
        plan_path=Path(f"certified://{answer['provenance']['plan_hash']}"),
        source_id=replay["source_id"],
        source_kind=replay["source_kind"],
        match_id=replay["match_id"],
        period=replay["period"],
        anchor_frame_id=int(replay["anchor_frame_id"]),
        padding_seconds=2.0,
    )
    canonical_by_frame = {int(frame["frame_id"]): frame for frame in canonical["frames"]}
    checks = []
    for frame in sampled:
        frame_id = int(frame["frame_id"])
        endpoint = get_json(
            f"{base_url}/api/film-room/replay-frame?replay_window_id={replay['replay_window_id']}&frame_id={frame_id}",
            timeout=timeout,
        )
        canonical_frame = canonical_by_frame[frame_id]
        if stable_hash(endpoint["frame"]) != stable_hash(canonical_frame):
            raise AssertionError(f"frame {frame_id} does not match canonical replay frame")
        if endpoint["frame_sha256"] != stable_json_sha256(canonical_frame):
            raise AssertionError(f"frame {frame_id} byte hash does not match canonical JSON bytes")
        checks.append(
            {
                "frame_id": frame_id,
                "frame_sha256": endpoint["frame_sha256"],
                "entity_count": len(endpoint["frame"].get("entities", [])),
            }
        )
    return checks


def capture_screenshot(base_url: str, path: Path, *, response_path: Path, timeout_ms: int) -> None:
    script = f"""
import {{ chromium }} from 'playwright';
import fs from 'node:fs';
const filmRoomResponse = JSON.parse(fs.readFileSync('{response_path.as_posix()}', 'utf8'));
const browser = await chromium.launch({{ headless: true }});
const page = await browser.newPage({{ viewport: {{ width: 1440, height: 1000 }} }});
page.setDefaultTimeout({timeout_ms});
await page.route('**/api/film-room/ask', async route => {{
  await route.fulfill({{
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(filmRoomResponse)
  }});
}});
await page.route('**/api/film-room/replay-frame**', async route => {{
  const url = new URL(route.request().url());
  const frameId = Number(url.searchParams.get('frame_id'));
  const replay = filmRoomResponse.answer && filmRoomResponse.answer.replay;
  const frame = replay && replay.frames.find(item => Number(item.frame_id) === frameId);
  await route.fulfill({{
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({{
      ok: true,
      replay_window_id: replay ? replay.replay_window_id : '',
      frame_id: frameId,
      frame_sha256: 'screenshot-intercept',
      canonical_sources: replay ? replay.canonical_sources : {{}},
      frame
    }})
  }});
}});
await page.goto('{base_url}/film-room', {{ waitUntil: 'domcontentloaded' }});
await page.waitForSelector('.stagebox svg');
await page.screenshot({{ path: '{path.as_posix()}', fullPage: true }});
await browser.close();
"""
    runner = ROOT / "apps/workbench-alpha/.film-room-screenshot.mjs"
    runner.write_text(script, encoding="utf-8")
    try:
        subprocess.run(["node", str(runner)], cwd=ROOT / "apps/workbench-alpha", check=True, timeout=timeout_ms / 1000 + 30)
    finally:
        runner.unlink(missing_ok=True)


def prewarm_flagships(output_root: Path) -> list[dict[str, Any]]:
    records = []
    for plan_path in PREWARM_PLAN_PATHS:
        started = time.monotonic()
        executions = film_room_execute_document(read_json(plan_path), output_root=output_root)
        records.append(
            {
                "plan": str(plan_path.relative_to(ROOT)),
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "cache_before": [item["cache_before"]["cache_status"] for item in executions],
                "cache_after": [item["cache_after_execute"]["cache_status"] for item in executions],
                "returned_result_counts": [item["execution"]["returned_result_count"] for item in executions],
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--output-root", type=Path, default=Path("/private/tmp/scp2-3-film-room-workshop"))
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--skip-prewarm", action="store_true")
    parser.add_argument("--skip-screenshot", action="store_true")
    args = parser.parse_args()

    table = read_json(TABLE_PATH)
    expected_plan_hash = str(table["plan_hash"])
    prewarm_records = [] if args.skip_prewarm else prewarm_flagships(args.output_root)
    port = args.port or free_port()
    base_url = f"http://127.0.0.1:{port}"
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": "src:.",
            "HERMES_HOME": str(Path.home() / ".hermes-priori"),
            "HERMES_SCP2_2_PROVIDER": "openai-codex",
            "HERMES_SCP2_2_MODEL": "gpt-5.5",
            "WORKBENCH_PREWARM_FILM_ROOM": "0",
            "WORKBENCH_FILM_ROOM_RESULT_LIMIT": "25",
        }
    )
    cmd = [
        sys.executable,
        "-m",
        "tqe.workshop.app_service",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--static-root",
        "apps/workbench-alpha/dist",
        "--output-root",
        str(args.output_root),
    ]
    started_at = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        wait_ready(base_url, timeout_seconds=args.timeout)
        ready_elapsed_ms = int((time.monotonic() - started_at) * 1000)
        ask_started = time.monotonic()
        response = post_json(
            f"{base_url}/api/film-room/ask",
            {"text": FLAGSHIP_ASK},
            timeout=args.timeout,
        )
        ask_elapsed_ms = int((time.monotonic() - ask_started) * 1000)
        if response.get("ok") is not True or response.get("outcome") != "expression":
            raise AssertionError(f"unexpected Film Room outcome: {response.get('outcome')}")
        answer = response["answer"]
        actual_document_hash = stable_hash(answer["document"])
        if answer["provenance"]["plan_hash"] != actual_document_hash:
            raise AssertionError(
                f"answer plan hash {answer['provenance']['plan_hash']} != executed document {actual_document_hash}"
            )
        if answer["provenance"].get("certified_table_path") and answer["provenance"]["plan_hash"] != expected_plan_hash:
            raise AssertionError(
                f"historical certified table hash mismatch: {answer['provenance']['plan_hash']} != {expected_plan_hash}"
            )
        replay_started = time.monotonic()
        frame_checks = assert_canonical_frame_match(response, base_url=base_url, timeout=args.timeout)
        replay_fetch_elapsed_ms = int((time.monotonic() - replay_started) * 1000)
        response_path = EVIDENCE_DIR / "film-room-response.json"
        write_json(response_path, response)
        screenshot_path = EVIDENCE_DIR / "film-room.png"
        if not args.skip_screenshot:
            capture_screenshot(base_url, screenshot_path, response_path=response_path, timeout_ms=args.timeout * 1000)
        evidence = {
            "schema_version": "scp2_3.film_room_e2e.v1",
            "ask": FLAGSHIP_ASK,
            "provider": response["provider"],
            "model": response["model"],
            "billing_surface": "ChatGPT subscription via openai-codex Hermes CLI",
            "expected_plan_hash": expected_plan_hash,
            "answer_plan_hash": answer["provenance"]["plan_hash"],
            "answer_document_hash": actual_document_hash,
            "matches_r2_4_certified_table": answer["provenance"]["plan_hash"] == expected_plan_hash,
            "certified_table_path": answer["provenance"].get("certified_table_path"),
            "synthesized_document_hash": answer["provenance"]["synthesized_document_hash"],
            "replay_window_id": answer["provenance"]["replay_window_id"],
            "moment_count": len(answer["moments"]),
            "frame_checks": frame_checks,
            "latency_ms": {
                "prewarm": prewarm_records,
                "service_ready_including_prewarm": ready_elapsed_ms,
                "ask": ask_elapsed_ms,
                "replay_sample_fetch": replay_fetch_elapsed_ms,
            },
            "screenshot": str(screenshot_path.relative_to(ROOT)) if screenshot_path.exists() else None,
            "response_artifact": str(response_path.relative_to(ROOT)),
        }
        write_json(EVIDENCE_DIR / "film-room-e2e.json", evidence)
        print(json.dumps(evidence, indent=2, sort_keys=True))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        if proc.stdout:
            log_path = EVIDENCE_DIR / "film-room-service.log"
            remaining = proc.stdout.read()
            if remaining:
                log_path.write_text(remaining, encoding="utf-8")


if __name__ == "__main__":
    main()
