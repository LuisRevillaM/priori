#!/usr/bin/env python3
"""Produce immutable DEPLOY-1C certified-gallery evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_PATH = Path(__file__).resolve()
ORACLE_PATH = ROOT / "delivery/oracles/DEPLOY-1C/gallery_ready.py"
EVIDENCE_ROOT = ROOT / "delivery/packets/deploy-1c-evidence/runs"
PACKET_BASE = "9eef466"
FOCUSED_TESTS = [
    "tests.test_deploy1c_gallery_from_tables",
    "tests.test_film_room_app",
    "tests.test_deploy1_public_mode",
]
FENCED_PATHS = [
    "delivery/oracles",
    "delivery/LEDGER.md",
    "docs/design",
    "config/scp2-2-blind-eval.sha256",
    "config/scp2-2-blind-eval-v2.sha256",
    "delivery/packets/scp2-2-dev-cases.json",
    "delivery/packets/scp2-2-dev-results.json",
    "delivery/packets/r2-2-flagship",
    "delivery/packets/scp2-3-evidence",
    "src/tqe/semantic_compiler",
]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def require_committed_clean_script() -> None:
    script_relative = relative(SCRIPT_PATH)
    committed = subprocess.run(
        ["git", "show", f"HEAD:{script_relative}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=30,
    )
    if committed.returncode != 0:
        raise SystemExit(f"evidence producer is not committed at HEAD: {script_relative}")
    if hashlib.sha256(committed.stdout).hexdigest() != file_sha256(SCRIPT_PATH):
        raise SystemExit(f"evidence producer differs from committed HEAD: {script_relative}")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    if dirty:
        raise SystemExit("tracked tree is dirty; commit before producing DEPLOY-1C evidence")


def make_run_dir(script_sha: str) -> Path:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y-%m-%dT%H%M%SZ0000")
    for index in range(10_000):
        candidate = EVIDENCE_ROOT / f"{stamp}{index:04d}-{script_sha[:12]}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise RuntimeError("could not allocate unique DEPLOY-1C evidence directory")


def write_text_once(path: Path, payload: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    path.write_text(payload, encoding="utf-8")


def write_json_once(path: Path, payload: Any) -> None:
    write_text_once(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def metadata(script_sha: str, run_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": "deploy1c.evidence_metadata.v1",
        "produced_by": relative(SCRIPT_PATH),
        "producing_script_sha256": script_sha,
        "run_started_at": utc_now().replace(microsecond=0).isoformat(),
        "git_branch": git_value("branch", "--show-current"),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
        "run_dir": relative(run_dir),
        "oracle_path": relative(ORACLE_PATH),
        "oracle_sha256": file_sha256(ORACLE_PATH),
        "packet_base": PACKET_BASE,
    }


def stamped_text(meta: dict[str, Any], payload: str) -> str:
    stamp = json.dumps(meta, sort_keys=True, separators=(",", ":"))
    return f"evidence_metadata={stamp}\n{payload}"


def command_record(
    args: list[str],
    *,
    output_path: Path,
    meta: dict[str, Any],
    timeout: int,
    env: dict[str, str],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = completed.stdout + completed.stderr
        return_code = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        output = stdout + stderr + f"\nTIMEOUT after {timeout}s\n"
        return_code = 124
        timed_out = True
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    write_text_once(output_path, stamped_text(meta, output))
    match = re.search(r"Ran (\d+) tests? in ([0-9.]+)s", output)
    return {
        "command": args,
        "return_code": return_code,
        "status": "PASS" if return_code == 0 else "FAIL",
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "flagged_over_5_minutes": duration_ms > 300_000,
        "reported_test_count": int(match.group(1)) if match else None,
        "reported_test_seconds": float(match.group(2)) if match else None,
        "output_path": relative(output_path),
    }


def json_request(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def run_local_gallery(
    *,
    run_dir: Path,
    meta: dict[str, Any],
    env: dict[str, str],
) -> dict[str, Any]:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from tqe.workshop import app_service

    with tempfile.TemporaryDirectory(prefix="deploy1c-runtime-", dir="/private/tmp") as temp_dir:
        runtime_root = Path(temp_dir)
        server = app_service.WorkbenchServer(
            ("127.0.0.1", 0),
            app_service.WorkbenchHandler,
            static_root=ROOT / "apps/workbench-alpha/src",
            output_root=runtime_root,
        )
        app_service.initialize_film_room_prewarm(
            output_root=runtime_root,
            execution_enabled=False,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            oracle = command_record(
                [
                    sys.executable,
                    str(ORACLE_PATH),
                    "--base-url",
                    base_url,
                    "--ready-timeout",
                    "30",
                ],
                output_path=run_dir / "gallery-ready-oracle.txt",
                meta=meta,
                timeout=90,
                env=env,
            )
            bootstrap = json_request(f"{base_url}/api/film-room/bootstrap")
            moments = (bootstrap.get("answer") or {}).get("moments") or []
            first_moment = moments[0] if moments else {}
            replay_window_id = str(first_moment.get("replay_window_id") or "")
            artifact = runtime_root / "replay-windows" / f"{replay_window_id}.json"
            artifact_existed_before_request = artifact.exists()
            replay_response = json_request(
                f"{base_url}/api/film-room/replay-window",
                {"replay_window_id": replay_window_id},
            )
            artifact_exists_after_request = artifact.exists()
            replay = replay_response.get("replay") or {}
            frames = replay.get("frames") or []
            frame_ids = [int(frame["frame_id"]) for frame in frames]
            prewarm_records = bootstrap.get("prewarm_records") or []
            execution_artifact_counts = {
                name: len(list((runtime_root / name).glob("*.json")))
                for name in ("draft-plans", "bound-plans", "executions")
                if (runtime_root / name).exists()
            }
            execution_artifact_counts = {
                name: execution_artifact_counts.get(name, 0)
                for name in ("draft-plans", "bound-plans", "executions")
            }
            checks = {
                "bootstrap_ready": bootstrap.get("state") == "ready",
                "provider_is_certified_table": (
                    (bootstrap.get("prewarmed_response") or {}).get("provider")
                    == "prewarmed_certified_table"
                ),
                "evidence_rows_kind_certified": (
                    (bootstrap.get("answer") or {}).get("evidence_rows_kind") == "certified"
                ),
                "no_answer_executions": (bootstrap.get("answer") or {}).get("executions") == [],
                "prewarm_records_report_no_execution": bool(prewarm_records)
                and all(record.get("execution_performed") is False for record in prewarm_records),
                "partition_previews_honestly_typed": bool(moments)
                and all(
                    moment.get("source_kind") == "certified_table_partition"
                    and moment.get("classification") == "CERTIFIED_TABLE_RATE_PARTITION"
                    for moment in moments
                ),
                "replay_was_lazy": not artifact_existed_before_request,
                "replay_materialized_on_request": artifact_exists_after_request,
                "replay_has_frames": bool(frames),
                "replay_within_requested_window": bool(frame_ids)
                and min(frame_ids) >= int(first_moment.get("replay_start_frame_id") or 0)
                and max(frame_ids) <= int(first_moment.get("replay_end_frame_id") or 0),
                "no_execution_artifacts": all(
                    count == 0 for count in execution_artifact_counts.values()
                ),
            }
            bootstrap_evidence = {"evidence_metadata": meta, "payload": bootstrap}
            replay_evidence = {"evidence_metadata": meta, "payload": replay_response}
            write_json_once(run_dir / "film-room-bootstrap.json", bootstrap_evidence)
            write_json_once(run_dir / "film-room-replay-window.json", replay_evidence)
            return {
                "status": "PASS" if oracle["status"] == "PASS" and all(checks.values()) else "FAIL",
                "base_url": base_url,
                "oracle": oracle,
                "checks": checks,
                "first_moment": first_moment,
                "replay_frame_count": len(frames),
                "replay_frame_id_min": min(frame_ids) if frame_ids else None,
                "replay_frame_id_max": max(frame_ids) if frame_ids else None,
                "execution_artifact_counts": execution_artifact_counts,
                "bootstrap_path": relative(run_dir / "film-room-bootstrap.json"),
                "replay_path": relative(run_dir / "film-room-replay-window.json"),
            }
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)


def fence_record() -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", PACKET_BASE, "--", *FENCED_PATHS],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    changed = [line for line in completed.stdout.splitlines() if line]
    return {
        "status": "PASS" if completed.returncode == 0 and not changed else "FAIL",
        "packet_base": PACKET_BASE,
        "paths": FENCED_PATHS,
        "changed_paths": changed,
        "semantic_compiler_touched": any(
            path.startswith("src/tqe/semantic_compiler/") for path in changed
        ),
    }


@contextmanager
def mounted_test_corpus(data_root: Path, raw_root: Path):
    """Expose read-only corpus paths expected by legacy tests in this worktree."""

    mounts = [
        (ROOT / "data/canonical/v1", data_root.resolve()),
        (ROOT / "data/raw/idsse/figshare-28196177-v1", raw_root.resolve()),
    ]
    created: list[Path] = []
    for mount, target in mounts:
        if mount.is_symlink() or mount.exists():
            if mount.resolve() != target:
                raise RuntimeError(f"test corpus mount already points elsewhere: {mount}")
            continue
        mount.parent.mkdir(parents=True, exist_ok=True)
        mount.symlink_to(target, target_is_directory=True)
        created.append(mount)
    try:
        yield
    finally:
        for mount in reversed(created):
            mount.unlink(missing_ok=True)


def render_markdown(payload: dict[str, Any]) -> str:
    meta = payload["evidence_metadata"]
    focused = payload["focused_tests"]
    focused_ui = payload["focused_ui_test"]
    typecheck = payload["ui_typecheck"]
    full = payload["full_suite"]
    local = payload["local_gallery"]
    return "\n".join(
        [
            "<!-- evidence_metadata: "
            + json.dumps(meta, sort_keys=True, separators=(",", ":"))
            + " -->",
            "# DEPLOY-1C Evidence",
            "",
            "| Verification | Status | Duration ms | Tests | Evidence |",
            "| --- | --- | ---: | ---: | --- |",
            f"| Focused Python | {focused['status']} | {focused['duration_ms']} | "
            f"{focused.get('reported_test_count') or ''} | `{focused['output_path']}` |",
            f"| Focused Film Room UI | {focused_ui['status']} | {focused_ui['duration_ms']} | "
            f" | `{focused_ui['output_path']}` |",
            f"| UI typecheck | {typecheck['status']} | {typecheck['duration_ms']} | "
            f" | `{typecheck['output_path']}` |",
            f"| Fenced gallery oracle + replay | {local['status']} | "
            f"{local['oracle'].get('duration_ms', '')} |  | "
            f"`{local['oracle'].get('output_path', '')}` |",
            f"| Full Python suite | {full['status']} | {full['duration_ms']} | "
            f"{full.get('reported_test_count') or ''} | `{full['output_path']}` |",
            f"| Leg zero | {payload['fences']['status']} |  |  | packet base `{PACKET_BASE}` |",
            "",
            "## Gallery proof",
            "",
            f"- Bootstrap state: `{local['checks'].get('bootstrap_ready')}`.",
            f"- No plan execution: `{local['checks'].get('no_execution_artifacts')}`.",
            f"- Replay lazy before request: `{local['checks'].get('replay_was_lazy')}`.",
            f"- Replay frames served: `{local['replay_frame_count']}`.",
            f"- Bootstrap: `{local['bootstrap_path']}`.",
            f"- Replay: `{local['replay_path']}`.",
            "- Memory-read limitation: `FLAGGED_NON_BLOCKING`; returned Arrow tables are "
            "window-filtered, but full-half Parquet row groups may still be scanned/decoded.",
            "- Semantics deviation: `RATIFICATION_REQUESTED`; certified tables omit chain "
            "source records, so bootstrap items are honestly labelled partition previews, not "
            "R-BB chain moments.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1")),
    )
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--full-suite-timeout", type=int, default=1800)
    args = parser.parse_args(argv)
    require_committed_clean_script()
    if not args.data_root.exists():
        raise SystemExit(f"canonical data root does not exist: {args.data_root}")
    raw_root = args.raw_root or (
        args.data_root.resolve().parents[1] / "raw/idsse/figshare-28196177-v1"
    )
    if not raw_root.exists():
        raise SystemExit(f"raw data root does not exist: {raw_root}")
    os.environ.update(
        {
            "PYTHONPATH": str(SRC),
            "TMPDIR": "/private/tmp",
            "TQE_DATA_ROOT": str(args.data_root.resolve()),
            "TQE_RAW_ROOT": str(raw_root.resolve()),
            "TQE_PUBLIC_MODE": "1",
            "WORKBENCH_PREWARM_FILM_ROOM": "0",
        }
    )
    script_sha = file_sha256(SCRIPT_PATH)
    run_dir = make_run_dir(script_sha)
    meta = metadata(script_sha, run_dir)
    env = dict(os.environ)
    focused = command_record(
        [sys.executable, "-m", "unittest", "-v", *FOCUSED_TESTS],
        output_path=run_dir / "focused-python-tests.txt",
        meta=meta,
        timeout=300,
        env=env,
    )
    focused_ui = command_record(
        [
            "node",
            "--import",
            "./apps/workbench-alpha/node_modules/tsx/dist/loader.mjs",
            "apps/workbench-alpha/tests/filmRoom.test.ts",
        ],
        output_path=run_dir / "focused-film-room-ui-test.txt",
        meta=meta,
        timeout=120,
        env=env,
    )
    ui_typecheck = command_record(
        [
            "apps/workbench-alpha/node_modules/.bin/tsc",
            "--noEmit",
            "-p",
            "apps/workbench-alpha/tsconfig.json",
        ],
        output_path=run_dir / "ui-typecheck.txt",
        meta=meta,
        timeout=120,
        env=env,
    )
    try:
        local_gallery = run_local_gallery(run_dir=run_dir, meta=meta, env=env)
    except Exception as exc:  # noqa: BLE001 - evidence must preserve a typed FAIL.
        failure = f"{type(exc).__name__}: {exc}\n"
        failure_path = run_dir / "local-gallery-failure.txt"
        write_text_once(failure_path, stamped_text(meta, failure))
        local_gallery = {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "failure_path": relative(failure_path),
            "checks": {},
            "oracle": {},
            "replay_frame_count": 0,
            "bootstrap_path": "",
            "replay_path": "",
        }
    suite_env = dict(env)
    suite_env.update(
        {
            "TQE_PUBLIC_MODE": "0",
            "DEMO_ACCESS_TOKEN": "",
            "DEMO_ACCESS_QUERY_TOKEN_ENABLED": "0",
        }
    )
    with mounted_test_corpus(args.data_root, raw_root):
        full_suite = command_record(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            output_path=run_dir / "full-python-suite.txt",
            meta=meta,
            timeout=args.full_suite_timeout,
            env=suite_env,
        )
    fences = fence_record()
    payload = {
        "schema_version": "deploy1c.evidence.v1",
        "evidence_metadata": meta,
        "canonical_data_root": str(args.data_root.resolve()),
        "raw_data_root": str(raw_root.resolve()),
        "focused_tests": focused,
        "focused_ui_test": focused_ui,
        "ui_typecheck": ui_typecheck,
        "local_gallery": local_gallery,
        "full_suite": full_suite,
        "fences": fences,
        "lazy_replay_memory_read": {
            "status": "FLAGGED_NON_BLOCKING",
            "bounded": "materialized Arrow tables and public replay payload",
            "limitation": (
                "Canonical frame and position files currently use full-half row groups. "
                "Predicate filters keep returned rows inside the requested replay window, "
                "but overlapping row groups may still be scanned or decoded by PyArrow."
            ),
            "follow_up": (
                "Physically partition or row-group canonical Parquet by bounded frame ranges "
                "before claiming window-bounded storage I/O."
            ),
        },
        "deviations": [
            {
                "id": "DEPLOY-1C-D1",
                "status": "RATIFICATION_REQUESTED",
                "case_law": "SCP2-3 R-BB",
                "reason": (
                    "The committed certified table intentionally omits source-record populations. "
                    "Without plan execution or a fenced-table mutation, certified chain witnesses "
                    "cannot be reconstructed."
                ),
                "implementation": (
                    "Bootstrap exposes certified_table_partition previews anchored at the committed "
                    "period open frame. API and UI state that these are not chain witnesses."
                ),
                "requested_ruling": (
                    "Ratify partition previews as a DEPLOY-1C bootstrap-only exception to R-BB, "
                    "or require a later certified table format that commits replayable witnesses."
                ),
            }
        ],
        "oracle_scope_limitation": {
            "status": "FLAGGED",
            "detail": (
                "The fenced gallery_ready.py verifies a replay_window_id but does not request it. "
                "This R-AZ producer separately calls the replay-window endpoint; the director's "
                "live acceptance should repeat that supplemental request."
            ),
        },
    }
    payload["status"] = (
        "PASS"
        if all(
            record["status"] == "PASS"
            for record in (
                focused,
                focused_ui,
                ui_typecheck,
                local_gallery,
                full_suite,
                fences,
            )
        )
        else "FAIL"
    )
    write_json_once(run_dir / "deploy1c-evidence.json", payload)
    write_text_once(run_dir / "deploy1c-evidence.md", render_markdown(payload))
    print(
        json.dumps(
            {"run_dir": relative(run_dir), "status": payload["status"]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
