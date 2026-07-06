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
import urllib.parse
import urllib.request
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.ir import stable_hash  # noqa: E402
from tqe.workshop.app_service import stable_json_sha256  # noqa: E402
from tqe.workshop.m1_2 import replay_window_from_canonical  # noqa: E402

FLAGSHIP_ASK = "After a regain, how often does the team progress the ball by carry and keep it with a controlled pass?"
TABLE_PATH = ROOT / "delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_table.json"
EVIDENCE_DIR = ROOT / "delivery/packets/scp2-3-evidence"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def run_metadata() -> dict[str, Any]:
    script_path = Path(__file__).resolve()
    return {
        "schema_version": "scp2_3.evidence_metadata.v1",
        "produced_by": str(script_path.relative_to(ROOT)),
        "producing_script_sha256": file_sha256(script_path),
        "run_started_at": utc_now(),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def with_metadata(payload: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {"evidence_metadata": metadata, **payload}


def write_json(path: Path, payload: dict[str, Any], metadata: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(with_metadata(payload, metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def open_service_log(path: Path, metadata: dict[str, Any]):
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("x", encoding="utf-8")
    handle.write(json.dumps({"evidence_metadata": metadata}, sort_keys=True) + "\n")
    handle.flush()
    return handle


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


def replay_window_url(base_url: str, replay_window_id: str) -> str:
    return f"{base_url}/api/film-room/replay-window?replay_window_id={urllib.parse.quote(replay_window_id)}"


def replay_frame_url(base_url: str, replay_window_id: str, frame_id: int) -> str:
    return (
        f"{base_url}/api/film-room/replay-frame?"
        f"replay_window_id={urllib.parse.quote(replay_window_id)}&frame_id={frame_id}"
    )


def assert_canonical_frame_match(
    response: dict[str, Any],
    replay: dict[str, Any],
    *,
    base_url: str,
    timeout: int,
) -> list[dict[str, Any]]:
    answer = response["answer"]
    sampled = [
        replay["frames"][0],
        replay["frames"][len(replay["frames"]) // 2],
        replay["frames"][-1],
    ]
    canonical = replay_window_from_canonical(
        replay_window_id=replay["replay_window_id"],
        plan_path=Path(f"film_room_plan_{answer['provenance']['plan_hash']}"),
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
        endpoint = get_json(replay_frame_url(base_url, replay["replay_window_id"], frame_id), timeout=timeout)
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


def add_png_text_metadata(path: Path, metadata: dict[str, Any]) -> None:
    payload = path.read_bytes()
    if not payload.startswith(PNG_SIGNATURE):
        raise RuntimeError(f"not a PNG: {path}")
    offset = len(PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(payload):
        length = int.from_bytes(payload[offset : offset + 4], "big")
        kind = payload[offset + 4 : offset + 8]
        data = payload[offset + 8 : offset + 8 + length]
        chunks.append((kind, data))
        offset += 12 + length
    output = bytearray(PNG_SIGNATURE)
    inserted = False
    text_fields = {
        "scp2_3_producing_script_sha256": str(metadata["producing_script_sha256"]),
        "scp2_3_run_started_at": str(metadata["run_started_at"]),
        "scp2_3_git_tree": str(metadata["git_tree"]),
    }
    for kind, data in chunks:
        output.extend(png_chunk(kind, data))
        if kind == b"IHDR" and not inserted:
            for key, value in text_fields.items():
                output.extend(png_chunk(b"tEXt", key.encode("latin-1") + b"\x00" + value.encode("latin-1")))
            inserted = True
    path.write_bytes(bytes(output))


def png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(data, crc) & 0xFFFFFFFF
    return len(data).to_bytes(4, "big") + kind + data + crc.to_bytes(4, "big")


def capture_screenshot(
    base_url: str,
    path: Path,
    *,
    timeout_ms: int,
    metadata: dict[str, Any],
    select_unknown: bool = False,
    select_trail: bool = False,
) -> None:
    unknown_script = """
const unknownMoment = page.locator('.momentItem', { hasText: 'window_truncated' }).first();
await unknownMoment.click();
await page.waitForSelector('.unknownOverlay');
await page.waitForSelector('.unknownLabel');
""" if select_unknown else ""
    trail_script = """
const trailMoment = page.locator('.momentItem', { hasText: 'PASS' }).first();
await trailMoment.click();
await page.waitForSelector('.carryTrail');
await page.waitForSelector('.stageLabel');
""" if select_trail else ""
    script = f"""
import {{ chromium }} from 'playwright';
const browser = await chromium.launch({{ headless: true }});
const page = await browser.newPage({{ viewport: {{ width: 1440, height: 1000 }} }});
page.setDefaultTimeout({timeout_ms});
await page.goto('{base_url}/film-room', {{ waitUntil: 'networkidle' }});
await page.waitForSelector('.stagebox svg');
await page.waitForSelector('.metricValue');
{unknown_script}
{trail_script}
await page.screenshot({{ path: '{path.as_posix()}', fullPage: true }});
await browser.close();
"""
    runner = ROOT / "apps/workbench-alpha/.film-room-screenshot.mjs"
    runner.write_text(script, encoding="utf-8")
    try:
        subprocess.run(["node", str(runner)], cwd=ROOT / "apps/workbench-alpha", check=True, timeout=timeout_ms / 1000 + 30)
    finally:
        runner.unlink(missing_ok=True)
    add_png_text_metadata(path, metadata)


def assert_interval_metric(response: dict[str, Any]) -> None:
    metric = response.get("answer", {}).get("interval_metric")
    if not isinstance(metric, dict):
        raise AssertionError("Film Room response did not include interval_metric")
    for key in ("observed", "lower", "upper", "unknown_count"):
        if not isinstance(metric.get(key), (int, float)):
            raise AssertionError(f"interval_metric.{key} is not numeric")


def assert_chain_moments(response: dict[str, Any]) -> dict[str, Any]:
    answer = response["answer"]
    moments = answer.get("moments")
    if not isinstance(moments, list) or not moments:
        raise AssertionError("Film Room answer returned no chain moments")
    total = int(answer.get("moment_total_count") or 0)
    visible = int(answer.get("visible_moment_count") or 0)
    if total != len(moments) or visible != len(moments):
        raise AssertionError(f"moment totals must match rendered list: total={total} visible={visible} len={len(moments)}")
    chain_moments = [moment for moment in moments if moment.get("source_kind") == "chain_record"]
    if len(chain_moments) != len(moments):
        raise AssertionError("all Film Room moments must be derived chain records")
    replay_ids = [str(moment.get("replay_window_id") or "") for moment in moments]
    if len(set(replay_ids)) != len(replay_ids):
        raise AssertionError("per-moment replay windows must be unique")
    staged = [
        moment
        for moment in moments
        if len(((moment.get("evidence_overlay") or {}).get("stage_labels") or [])) >= 3
    ]
    trails = [
        moment
        for moment in moments
        if ((moment.get("evidence_overlay") or {}).get("carry_trails") or [])
    ]
    unknown = [
        moment
        for moment in moments
        if moment.get("chain_status") == "UNKNOWN"
        and ((moment.get("evidence_overlay") or {}).get("unknown") or {}).get("is_unknown") is True
    ]
    truthful_unknown = [
        moment
        for moment in unknown
        if str(((moment.get("evidence_overlay") or {}).get("unknown") or {}).get("reason") or "")
        == str(moment.get("chain_reason") or "")
    ]
    truncated_unknown = [
        moment
        for moment in truthful_unknown
        if "truncated" in str(moment.get("chain_reason") or "")
    ]
    if not staged:
        raise AssertionError("no chain moment exercised stage-label overlays")
    if not trails:
        raise AssertionError("no chain moment exercised carry-trail overlays")
    if not unknown:
        raise AssertionError("no chain moment exercised UNKNOWN slate overlay")
    if not truthful_unknown:
        raise AssertionError("UNKNOWN slate reason did not render the chain reason")
    if not truncated_unknown:
        raise AssertionError("no UNKNOWN slate rendered a truncation reason")
    return {
        "moment_total_count": total,
        "visible_moment_count": visible,
        "chain_record_count": len(chain_moments),
        "unique_replay_window_count": len(set(replay_ids)),
        "stage_overlay_count": len(staged),
        "carry_trail_count": len(trails),
        "unknown_slate_count": len(unknown),
        "first_unknown_replay_window_id": unknown[0]["replay_window_id"],
        "first_unknown_chain_reason": unknown[0].get("chain_reason"),
        "first_truncated_unknown_replay_window_id": truncated_unknown[0]["replay_window_id"],
        "first_truncated_unknown_chain_reason": truncated_unknown[0].get("chain_reason"),
        "first_stage_trail_replay_window_id": trails[0]["replay_window_id"],
        "first_stage_trail_chain_status": trails[0].get("chain_status"),
    }


def main() -> None:
    metadata = run_metadata()
    default_output_root = Path("/private/tmp") / "scp2-3-film-room-workshop-runs" / (
        metadata["run_started_at"].replace(":", "").replace("+", "Z") + "-" + metadata["producing_script_sha256"][:12]
    )
    default_run_dir = EVIDENCE_DIR / "runs" / (
        metadata["run_started_at"].replace(":", "").replace("+", "Z") + "-" + metadata["producing_script_sha256"][:12]
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--output-root", type=Path, default=default_output_root)
    parser.add_argument("--evidence-run-dir", type=Path, default=default_run_dir)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--skip-service-prewarm", action="store_true")
    parser.add_argument("--skip-screenshot", action="store_true")
    args = parser.parse_args()

    run_dir = args.evidence_run_dir
    if run_dir.exists():
        raise RuntimeError(f"evidence run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    output_root_preexisting = args.output_root.exists()

    table = read_json(TABLE_PATH)
    expected_plan_hash = str(table["plan_hash"])
    port = args.port or free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": "src:.",
            "HERMES_HOME": str(Path.home() / ".hermes-priori"),
            "HERMES_SCP2_2_PROVIDER": "openai-codex",
            "HERMES_SCP2_2_MODEL": "gpt-5.5",
            "WORKBENCH_HERMES_PROVIDER": "openai-codex",
            "WORKBENCH_HERMES_MODEL": "gpt-5.5",
            "WORKBENCH_PREWARM_FILM_ROOM": "0" if args.skip_service_prewarm else "1",
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
    service_log_path = run_dir / "film-room-service.log"
    service_log_handle = open_service_log(service_log_path, metadata)
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=service_log_handle, stderr=subprocess.STDOUT, text=True)
    try:
        wait_ready(base_url, timeout_seconds=args.timeout)
        ready_elapsed_ms = int((time.monotonic() - started_at) * 1000)

        bootstrap_started = time.monotonic()
        bootstrap = get_json(f"{base_url}/api/film-room/bootstrap", timeout=args.timeout)
        bootstrap_elapsed_ms = int((time.monotonic() - bootstrap_started) * 1000)
        write_json(run_dir / "film-room-bootstrap.json", bootstrap, metadata)
        if not isinstance(bootstrap.get("prewarmed_response"), dict):
            raise AssertionError("bootstrap did not include a prewarmed Film Room response")
        assert_interval_metric(bootstrap["prewarmed_response"])
        bootstrap_chain_checks = assert_chain_moments(bootstrap["prewarmed_response"])

        ask_started = time.monotonic()
        cold_response = post_json(
            f"{base_url}/api/film-room/ask",
            {"text": FLAGSHIP_ASK},
            timeout=args.timeout,
        )
        cold_ask_elapsed_ms = int((time.monotonic() - ask_started) * 1000)
        write_json(run_dir / "film-room-cold-response.json", cold_response, metadata)
        if cold_response.get("ok") is not True or cold_response.get("outcome") != "expression":
            raise AssertionError(f"unexpected Film Room outcome: {cold_response.get('outcome')}")
        assert_interval_metric(cold_response)
        cold_chain_checks = assert_chain_moments(cold_response)

        answer = cold_response["answer"]
        actual_document_hash = stable_hash(answer["document"])
        if answer["provenance"]["plan_hash"] != actual_document_hash:
            raise AssertionError(
                f"answer plan hash {answer['provenance']['plan_hash']} != executed document {actual_document_hash}"
            )
        if answer["provenance"].get("certified_table_path") and answer["provenance"]["plan_hash"] != expected_plan_hash:
            raise AssertionError(
                f"historical certified table hash mismatch: {answer['provenance']['plan_hash']} != {expected_plan_hash}"
            )
        first_moment = answer["moments"][0]
        replay_window_id = str(first_moment["replay_window_id"])
        replay_started = time.monotonic()
        replay_window = get_json(replay_window_url(base_url, replay_window_id), timeout=args.timeout)
        replay_fetch_elapsed_ms = int((time.monotonic() - replay_started) * 1000)
        write_json(run_dir / "film-room-replay-window.json", replay_window, metadata)
        unknown_replay_window_id = str(cold_chain_checks["first_truncated_unknown_replay_window_id"])
        unknown_replay_started = time.monotonic()
        unknown_replay_window = get_json(replay_window_url(base_url, unknown_replay_window_id), timeout=args.timeout)
        unknown_replay_fetch_elapsed_ms = int((time.monotonic() - unknown_replay_started) * 1000)
        write_json(run_dir / "film-room-unknown-replay-window.json", unknown_replay_window, metadata)
        stage_trail_replay_window_id = str(cold_chain_checks["first_stage_trail_replay_window_id"])
        stage_trail_replay_started = time.monotonic()
        stage_trail_replay_window = get_json(replay_window_url(base_url, stage_trail_replay_window_id), timeout=args.timeout)
        stage_trail_replay_fetch_elapsed_ms = int((time.monotonic() - stage_trail_replay_started) * 1000)
        write_json(run_dir / "film-room-stage-trail-replay-window.json", stage_trail_replay_window, metadata)
        frame_checks = assert_canonical_frame_match(
            cold_response,
            replay_window["replay"],
            base_url=base_url,
            timeout=args.timeout,
        )

        screenshot_path = run_dir / "film-room.png"
        unknown_screenshot_path = run_dir / "film-room-unknown.png"
        stage_trail_screenshot_path = run_dir / "film-room-stage-trail.png"
        if not args.skip_screenshot:
            capture_screenshot(base_url, screenshot_path, timeout_ms=args.timeout * 1000, metadata=metadata)
            capture_screenshot(
                base_url,
                unknown_screenshot_path,
                timeout_ms=args.timeout * 1000,
                metadata=metadata,
                select_unknown=True,
            )
            capture_screenshot(
                base_url,
                stage_trail_screenshot_path,
                timeout_ms=args.timeout * 1000,
                metadata=metadata,
                select_trail=True,
            )

        evidence = {
            "schema_version": "scp2_3.film_room_e2e.v2",
            "ask": FLAGSHIP_ASK,
            "provider": cold_response["provider"],
            "model": cold_response["model"],
            "billing_surface": "ChatGPT subscription via openai-codex Hermes CLI",
            "output_root": str(args.output_root),
            "skip_service_prewarm": args.skip_service_prewarm,
            "timeout_seconds": args.timeout,
            "cache_provenance": {
                "output_root": str(args.output_root),
                "output_root_preexisting_at_start": output_root_preexisting,
                "service_prewarm_enabled": not args.skip_service_prewarm,
            },
            "expected_r2_4_plan_hash": expected_plan_hash,
            "answer_plan_hash": answer["provenance"]["plan_hash"],
            "answer_document_hash": actual_document_hash,
            "matches_r2_4_certified_table": answer["provenance"]["plan_hash"] == expected_plan_hash,
            "certified_table_path": answer["provenance"].get("certified_table_path"),
            "synthesized_document_hash": answer["provenance"]["synthesized_document_hash"],
            "tree": answer["provenance"].get("tree"),
            "replay_window_id": replay_window_id,
            "moment_total_count": answer["moment_total_count"],
            "visible_moment_count": answer["visible_moment_count"],
            "interval_metric": answer["interval_metric"],
            "frame_checks": frame_checks,
            "chain_moment_checks": {
                "bootstrap": bootstrap_chain_checks,
                "cold": cold_chain_checks,
            },
            "latency_ms": {
                "service_ready_including_startup_prewarm": ready_elapsed_ms,
                "bootstrap_prewarmed_fetch": bootstrap_elapsed_ms,
                "cold_ask_total_observed": cold_ask_elapsed_ms,
                "cold_ask_attribution": cold_response["latency_breakdown_ms"],
                "replay_window_fetch": replay_fetch_elapsed_ms,
                "unknown_replay_window_fetch": unknown_replay_fetch_elapsed_ms,
                "stage_trail_replay_window_fetch": stage_trail_replay_fetch_elapsed_ms,
            },
            "prewarm_records": bootstrap.get("prewarm_records", []),
            "artifacts": {
                "bootstrap": str((run_dir / "film-room-bootstrap.json").relative_to(ROOT)),
                "cold_response": str((run_dir / "film-room-cold-response.json").relative_to(ROOT)),
                "replay_window": str((run_dir / "film-room-replay-window.json").relative_to(ROOT)),
                "unknown_replay_window": str((run_dir / "film-room-unknown-replay-window.json").relative_to(ROOT)),
                "stage_trail_replay_window": str((run_dir / "film-room-stage-trail-replay-window.json").relative_to(ROOT)),
                "screenshot": str(screenshot_path.relative_to(ROOT)) if screenshot_path.exists() else None,
                "unknown_screenshot": str(unknown_screenshot_path.relative_to(ROOT)) if unknown_screenshot_path.exists() else None,
                "stage_trail_screenshot": (
                    str(stage_trail_screenshot_path.relative_to(ROOT)) if stage_trail_screenshot_path.exists() else None
                ),
                "service_log": str(service_log_path.relative_to(ROOT)),
            },
        }
        write_json(run_dir / "film-room-e2e.json", evidence, metadata)
        print(json.dumps(with_metadata(evidence, metadata), indent=2, sort_keys=True))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        service_log_handle.close()


if __name__ == "__main__":
    main()
