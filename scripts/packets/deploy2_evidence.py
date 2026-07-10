#!/usr/bin/env python3
"""R-AZ producer for DEPLOY-2 cache refresh, 2 GiB proof, and live closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "delivery/packets/deploy-2-evidence/runs"
BUNDLE_NAME = "entrelineas-cloud-workbench-alpha-seven-match-v1"
ORACLES = {
    "deploy_smoke": ROOT / "delivery/oracles/DEPLOY-1/deploy_smoke.py",
    "gallery_ready": ROOT / "delivery/oracles/DEPLOY-1C/gallery_ready.py",
    "chain_gallery": ROOT / "delivery/oracles/DEPLOY-2/chain_gallery.py",
}
EXPECTED_ORACLE_SHA256 = {
    "deploy_smoke": "708e90e81109c63462a4d3d97ba11ebd4e5c12f7d0bb084fcd710257b60a5dc2",
    "gallery_ready": "a3ef8770f86fea8762ace34a8675f3e9410809d77b68837b4e3d450a10f03d3c",
    "chain_gallery": "e3485b16fa6cb7b40be9a021befa535a402db1bff1c2d4436fc1c084124344b4",
}
MEMORY_LIMIT_BYTES = 2 * 1024 * 1024 * 1024


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(argv)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def isolated_git_env() -> dict[str, str]:
    handle, name = tempfile.mkstemp(prefix="priori-deploy2-index-", dir="/private/tmp")
    os.close(handle)
    Path(name).unlink()
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = name
    command(["git", "read-tree", "HEAD"], env=env)
    return env


def git_output(args: list[str], env: dict[str, str]) -> str:
    return command(["git", *args], env=env).stdout.strip()


def producer_metadata() -> tuple[dict[str, Any], dict[str, str]]:
    git_env = isolated_git_env()
    script = Path(__file__).resolve()
    relative = script.relative_to(ROOT).as_posix()
    head_bytes = command(["git", "show", f"HEAD:{relative}"], env=git_env).stdout.encode()
    if head_bytes != script.read_bytes():
        raise RuntimeError("R-AZ refusal: producer is not byte-identical to the committed HEAD copy")
    dirty = command(["git", "diff", "--quiet", "HEAD", "--", "."], env=git_env, check=False)
    if dirty.returncode:
        raise RuntimeError("R-AZ refusal: tracked worktree differs from HEAD")
    oracle_hashes = {name: sha256_path(path) for name, path in ORACLES.items()}
    if oracle_hashes != EXPECTED_ORACLE_SHA256:
        raise RuntimeError(f"leg-zero refusal: oracle hashes changed: {oracle_hashes}")
    started = datetime.now(UTC).isoformat().replace(":", "").replace("+00:00", "Z")
    metadata = {
        "schema_version": "deploy2.evidence.v1",
        "run_started_at": datetime.now(UTC).isoformat(),
        "producing_script": relative,
        "producing_script_sha256": sha256_path(script),
        "producing_commit": git_output(["rev-parse", "HEAD"], git_env),
        "producing_tree": git_output(["rev-parse", "HEAD^{tree}"], git_env),
        "branch": git_output(["branch", "--show-current"], git_env),
        "oracle_sha256": oracle_hashes,
        "run_id": f"{started}-{sha256_path(script)[:12]}",
    }
    return metadata, git_env


def allocate_run(metadata: dict[str, Any], phase: str) -> Path:
    run_dir = EVIDENCE_ROOT / f"{metadata['run_id']}-{phase}"
    if run_dir.exists():
        raise RuntimeError(f"R-AZ refusal: evidence path already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    return run_dir


def write_text(path: Path, value: str) -> None:
    if path.exists():
        raise RuntimeError(f"R-AZ refusal: will not overwrite {path}")
    path.write_text(value, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def get_json(url: str, timeout: int = 60) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected object from {url}")
    return payload


def docker_image_id(tag: str) -> str:
    return command(["docker", "image", "inspect", tag, "--format", "{{.Id}}"]).stdout.strip()


def build_image(tag: str, revision: str, log_path: Path) -> str:
    completed = command(
        [
            "docker",
            "build",
            "--label",
            f"org.opencontainers.image.revision={revision}",
            "--tag",
            tag,
            ".",
        ],
        timeout=3600,
        check=False,
    )
    write_text(log_path, completed.stdout + completed.stderr)
    if completed.returncode:
        raise RuntimeError(f"Docker build failed; see {log_path}")
    image_id = docker_image_id(tag)
    label = command(
        ["docker", "image", "inspect", tag, "--format", "{{index .Config.Labels \"org.opencontainers.image.revision\"}}"]
    ).stdout.strip()
    if label != revision:
        raise RuntimeError(f"image revision label mismatch: {label} != {revision}")
    return image_id


def container_port(name: str) -> int:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        completed = command(["docker", "port", name, "10000/tcp"], check=False)
        value = completed.stdout.strip().rsplit(":", 1)[-1]
        if value.isdigit():
            return int(value)
        time.sleep(1)
    raise RuntimeError("Docker did not publish port 10000")


def start_cache_builder(name: str, tag: str, stage: Path) -> tuple[str, int]:
    argv = [
        "docker",
        "run",
        "--detach",
        "--name",
        name,
        "--memory=4g",
        "--memory-swap=4g",
        "--publish",
        "127.0.0.1::10000",
        "--mount",
        f"type=bind,source={stage.resolve()},target=/var/data",
        "--env",
        "PORT=10000",
        "--env",
        "TQE_DATA_ROOT=/var/data/dataset/canonical/v1",
        "--env",
        "TQE_RAW_ROOT=/var/data/dataset/raw/idsse/figshare-28196177-v1",
        "--env",
        "TQE_RUNTIME_ROOT=/var/data/runtime",
        "--env",
        "TQE_CACHE_ROOT=/var/data/cache",
        "--env",
        "TQE_NODE_CACHE_ROOT=/var/data/cache/node-output",
        "--env",
        "TQE_EXECUTION_WORKERS=1",
        "--env",
        "WORKBENCH_HERMES_ENABLED=0",
        "--env",
        "WORKBENCH_PREWARM_FILM_ROOM=1",
        tag,
        "python",
        "-m",
        "tqe.workshop.app_service",
        "--host",
        "0.0.0.0",
        "--port",
        "10000",
        "--static-root",
        "/app/apps/workbench-alpha/dist",
        "--output-root",
        "/var/data/runtime",
    ]
    container_id = command(argv).stdout.strip()
    return container_id, container_port(name)


def start_proof_container(
    name: str,
    volume: str,
    tag: str,
    bundle: Path,
    manifest: Path,
    bundle_sha: str,
) -> tuple[str, int]:
    bundle_dir = bundle.parent.resolve()
    argv = [
        "docker",
        "run",
        "--detach",
        "--name",
        name,
        "--memory=2g",
        "--memory-swap=2g",
        "--publish",
        "127.0.0.1::10000",
        "--mount",
        f"type=volume,source={volume},target=/var/data",
        "--mount",
        f"type=bind,source={bundle_dir},target=/bundle,readonly",
        "--env",
        "PORT=10000",
        "--env",
        "TQE_PROVISION_DATA_BACKGROUND=0",
        "--env",
        "TQE_PREWARM_COACH_COMPILER=0",
        "--env",
        "WORKBENCH_HERMES_ENABLED=0",
        "--env",
        "WORKBENCH_PREWARM_FILM_ROOM=1",
        "--env",
        "TQE_EXECUTION_WORKERS=1",
        "--env",
        "TQE_PUBLIC_MODE=1",
        "--env",
        f"TQE_DATA_BUNDLE_URL=file:///bundle/{bundle.name}",
        "--env",
        f"TQE_DATA_BUNDLE_SHA256={bundle_sha}",
        "--env",
        f"TQE_DATA_BUNDLE_MANIFEST=/bundle/{manifest.name}",
        tag,
    ]
    container_id = command(argv).stdout.strip()
    return container_id, container_port(name)


def wait_for_execution_gallery(base_url: str, name: str, timeout: int) -> tuple[dict[str, Any], int]:
    deadline = time.monotonic() + timeout
    sampled_peak = 0
    last_error = "service did not answer"
    while time.monotonic() < deadline:
        peak = command(
            ["docker", "exec", name, "sh", "-c", "cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory.current"],
            check=False,
        ).stdout.strip()
        if peak.isdigit():
            sampled_peak = max(sampled_peak, int(peak))
        state = command(["docker", "inspect", name, "--format", "{{.State.Status}} {{.State.OOMKilled}}"], check=False)
        if "true" in state.stdout.lower() or state.stdout.startswith("exited"):
            raise RuntimeError(f"container stopped before gallery upgrade: {state.stdout.strip()}")
        try:
            boot = get_json(f"{base_url}/api/film-room/bootstrap")
            records = [record for record in boot.get("prewarm_records", []) if record.get("prewarm_kind") == "execution_upgrade"]
            answer = boot.get("answer") or {}
            chain_count = sum(1 for moment in answer.get("moments", []) if moment.get("source_kind") == "chain_record")
            if len(records) >= 2 and all(record.get("upgrade_applied") for record in records) and chain_count:
                return boot, sampled_peak
            last_error = f"execution_records={len(records)} chain_records={chain_count}"
        except Exception as exc:  # noqa: BLE001 - readiness loop records the final transport state.
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"execution gallery did not become ready in {timeout}s: {last_error}")


def stop_container(name: str, log_path: Path) -> dict[str, Any]:
    logs = command(["docker", "logs", name], check=False)
    write_text(log_path, logs.stdout + logs.stderr)
    inspect_before = command(
        ["docker", "inspect", name, "--format", "{{json .State}}|{{json .HostConfig}}"],
        check=False,
    ).stdout.strip()
    command(["docker", "stop", "--time", "20", name], check=False)
    command(["docker", "rm", name], check=False)
    return {"raw_state_and_host_config": inspect_before}


def run_oracle(name: str, base_url: str, run_dir: Path, timeout: int) -> dict[str, Any]:
    argv = [sys.executable, str(ORACLES[name]), "--base-url", base_url]
    if name == "chain_gallery":
        argv.extend(["--ready-timeout", str(timeout)])
    if name == "gallery_ready":
        argv.extend(["--ready-timeout", str(min(timeout, 300))])
    completed = command(argv, timeout=timeout + 60, check=False)
    output = completed.stdout + completed.stderr
    write_text(run_dir / f"{name}.txt", output)
    return {"exit_code": completed.returncode, "output_file": f"{name}.txt"}


def markdown_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# DEPLOY-2 R-AZ evidence",
        "",
        f"- Phase: `{payload['phase']}`",
        f"- Status: `{payload['status']}`",
        f"- Producing commit: `{payload['producing_commit']}`",
        f"- Producer SHA-256: `{payload['producing_script_sha256']}`",
    ]
    if payload["phase"] == "local":
        local = payload.get("local_proof", {})
        lines.extend(
            [
                f"- Bundle SHA-256: `{payload.get('bundle', {}).get('archive_sha256', '')}`",
                f"- Docker memory limit: `{local.get('memory_limit_bytes')}` bytes",
                f"- Measured cgroup peak: `{local.get('memory_peak_bytes')}` bytes",
                f"- OOM killed: `{local.get('oom_killed')}`",
                f"- Cache-hit execution upgrades: `{local.get('execution_cache_statuses')}`",
            ]
        )
    if payload["phase"] == "live":
        lines.extend(
            [
                f"- Live URL: `{payload.get('base_url')}`",
                f"- Stability duration: `{payload.get('stability_duration_seconds')}` seconds",
                f"- Deploy ID: `{payload.get('deploy_id')}`",
            ]
        )
    lines.extend(["", "| Oracle | Exit |", "| --- | ---: |"])
    for name, result in payload.get("oracles", {}).items():
        lines.append(f"| `{name}` | {result['exit_code']} |")
    return "\n".join(lines) + "\n"


def local_phase(args: argparse.Namespace) -> int:
    metadata, git_env = producer_metadata()
    run_dir = allocate_run(metadata, "local")
    result: dict[str, Any] = {**metadata, "phase": "local", "status": "FAIL"}
    work_root = ROOT / "artifacts/deploy-2" / metadata["run_id"]
    base_output = work_root / "base"
    stage = work_root / "stage"
    empty_cache = work_root / "empty-cache"
    empty_runtime = work_root / "empty-runtime"
    final_output = ROOT / "artifacts/cloud-alpha"
    for path in (base_output, stage, empty_cache, empty_runtime, final_output):
        path.mkdir(parents=True, exist_ok=True)
    image_tag = args.image_tag
    cache_name = f"priori-deploy2-cache-{metadata['producing_script_sha256'][:8]}"
    proof_name = f"priori-deploy2-proof-{metadata['producing_script_sha256'][:8]}"
    proof_volume = f"priori-deploy2-proof-{metadata['producing_script_sha256'][:8]}"
    cache_started = False
    proof_started = False
    try:
        image_id = build_image(image_tag, metadata["producing_commit"], run_dir / "docker-build.log")
        bundle_env = git_env | {"PYTHONPATH": "src:."}
        base = command(
            [
                sys.executable,
                "scripts/create-demo-data-bundle.py",
                "--dataset-root",
                "data",
                "--cache-root",
                str(empty_cache),
                "--runtime-root",
                str(empty_runtime),
                "--output-dir",
                str(base_output),
            ],
            env=bundle_env,
            timeout=1800,
        )
        write_text(run_dir / "base-bundle-build.txt", base.stdout + base.stderr)
        base_archive = base_output / f"{BUNDLE_NAME}.tar.gz"
        with tarfile.open(base_archive, "r:gz") as archive:
            archive.extractall(stage, filter="data")
        _, cache_port = start_cache_builder(cache_name, image_tag, stage)
        cache_started = True
        cache_boot, _ = wait_for_execution_gallery(f"http://127.0.0.1:{cache_port}", cache_name, args.timeout)
        cache_records = [record for record in cache_boot.get("prewarm_records", []) if record.get("prewarm_kind") == "execution_upgrade"]
        stop_container(cache_name, run_dir / "cache-build-service.log")
        cache_started = False

        final = command(
            [
                sys.executable,
                "scripts/create-demo-data-bundle.py",
                "--dataset-root",
                str(stage / "dataset"),
                "--cache-root",
                str(stage / "cache"),
                "--runtime-root",
                str(stage / "runtime"),
                "--output-dir",
                str(final_output),
            ],
            env=bundle_env,
            timeout=1800,
        )
        write_text(run_dir / "final-bundle-build.txt", final.stdout + final.stderr)
        bundle = final_output / f"{BUNDLE_NAME}.tar.gz"
        manifest = final_output / f"{BUNDLE_NAME}.manifest.json"
        bundle_manifest = json.loads(manifest.read_text(encoding="utf-8"))
        bundle_sha = sha256_path(bundle)
        if bundle_sha != bundle_manifest.get("archive_sha256"):
            raise RuntimeError("final bundle SHA does not match its manifest")
        if bundle_manifest.get("source_commit") != metadata["producing_commit"] or bundle_manifest.get("source_dirty"):
            raise RuntimeError("final bundle provenance is not the clean producing commit")
        shutil.copy2(manifest, run_dir / "bundle-manifest.json")

        command(["docker", "volume", "create", proof_volume])
        _, proof_port = start_proof_container(proof_name, proof_volume, image_tag, bundle, manifest, bundle_sha)
        proof_started = True
        base_url = f"http://127.0.0.1:{proof_port}"
        proof_boot, sampled_peak = wait_for_execution_gallery(base_url, proof_name, args.timeout)
        write_json(run_dir / "local-bootstrap.json", {**metadata, "bootstrap": proof_boot})
        oracle_results = {
            name: run_oracle(name, base_url, run_dir, args.timeout)
            for name in ("deploy_smoke", "gallery_ready", "chain_gallery")
        }
        peak_raw = command(
            ["docker", "exec", proof_name, "sh", "-c", "cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory.current"]
        ).stdout.strip()
        memory_peak = int(peak_raw) if peak_raw.isdigit() else sampled_peak
        memory_events = command(
            ["docker", "exec", proof_name, "sh", "-c", "cat /sys/fs/cgroup/memory.events 2>/dev/null || true"]
        ).stdout
        write_text(run_dir / "memory-events.txt", memory_events)
        state = command(["docker", "inspect", proof_name, "--format", "{{json .State}}"])
        state_payload = json.loads(state.stdout)
        host_memory = int(command(["docker", "inspect", proof_name, "--format", "{{.HostConfig.Memory}}"] ).stdout)
        proof_records = [record for record in proof_boot.get("prewarm_records", []) if record.get("prewarm_kind") == "execution_upgrade"]
        statuses = [status for record in proof_records for status in record.get("cache_after_execute", [])]
        stop_state = stop_container(proof_name, run_dir / "local-service.log")
        proof_started = False
        command(["docker", "volume", "rm", proof_volume], check=False)
        local_ok = (
            host_memory == MEMORY_LIMIT_BYTES
            and not bool(state_payload.get("OOMKilled"))
            and memory_peak <= MEMORY_LIMIT_BYTES
            and len(proof_records) >= 2
            and statuses
            and all(status == "HIT" for status in statuses)
            and all(item["exit_code"] == 0 for item in oracle_results.values())
        )
        result.update(
            {
                "status": "PASS" if local_ok else "FAIL",
                "image": {"tag": image_tag, "id": image_id},
                "bundle": {
                    "path": str(bundle.relative_to(ROOT)),
                    "manifest_path": str(manifest.relative_to(ROOT)),
                    "archive_sha256": bundle_sha,
                    "runtime_code_epoch": bundle_manifest.get("runtime_code_epoch"),
                    "file_count": bundle_manifest.get("file_count"),
                    "compressed_size_bytes": bundle_manifest.get("compressed_size_bytes"),
                },
                "cache_generation": {"execution_records": cache_records},
                "local_proof": {
                    "base_url": base_url,
                    "memory_limit_bytes": host_memory,
                    "memory_peak_bytes": memory_peak,
                    "memory_peak_mib": round(memory_peak / 1024 / 1024, 3),
                    "oom_killed": bool(state_payload.get("OOMKilled")),
                    "execution_cache_statuses": statuses,
                    "container_state": state_payload,
                    "container_inspect": stop_state,
                },
                "oracles": oracle_results,
            }
        )
    except Exception as exc:  # noqa: BLE001 - failure is sealed as evidence.
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if cache_started:
            stop_container(cache_name, run_dir / "cache-build-service-failure.log")
        if proof_started:
            stop_container(proof_name, run_dir / "local-service-failure.log")
        command(["docker", "volume", "rm", proof_volume], check=False)
        write_json(run_dir / "deploy2-evidence.json", result)
        write_text(run_dir / "deploy2-evidence.md", markdown_summary(result))
    print(run_dir.relative_to(ROOT))
    print(result["status"])
    return 0 if result["status"] == "PASS" else 1


def live_phase(args: argparse.Namespace) -> int:
    metadata, _ = producer_metadata()
    run_dir = allocate_run(metadata, "live")
    result: dict[str, Any] = {
        **metadata,
        "phase": "live",
        "status": "FAIL",
        "base_url": args.base_url.rstrip("/"),
        "deploy_id": args.deploy_id,
        "service_id": args.service_id,
        "stability_duration_seconds": args.stability_seconds,
    }
    try:
        samples: list[dict[str, Any]] = []
        deadline = time.monotonic() + args.stability_seconds
        while True:
            started = datetime.now(UTC).isoformat()
            health = get_json(f"{result['base_url']}/healthz", timeout=60)
            boot = get_json(f"{result['base_url']}/api/film-room/bootstrap", timeout=60)
            moments = (boot.get("answer") or {}).get("moments") or []
            samples.append(
                {
                    "sampled_at": started,
                    "health_status": health.get("status"),
                    "gallery_state": boot.get("state"),
                    "chain_record_count": sum(1 for moment in moments if moment.get("source_kind") == "chain_record"),
                }
            )
            if time.monotonic() >= deadline:
                break
            time.sleep(min(30, max(0, deadline - time.monotonic())))
        write_json(run_dir / "stability-samples.json", {**metadata, "samples": samples})
        oracle_results = {
            name: run_oracle(name, str(result["base_url"]), run_dir, 600)
            for name in ("deploy_smoke", "gallery_ready", "chain_gallery")
        }
        stable = len(samples) >= 2 and all(
            sample["health_status"] == "READY"
            and sample["gallery_state"] == "ready"
            and sample["chain_record_count"] > 0
            for sample in samples
        )
        result["samples"] = samples
        result["oracles"] = oracle_results
        result["status"] = "PASS" if stable and all(item["exit_code"] == 0 for item in oracle_results.values()) else "FAIL"
    except Exception as exc:  # noqa: BLE001 - failure is sealed as evidence.
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    write_json(run_dir / "deploy2-evidence.json", result)
    write_text(run_dir / "deploy2-evidence.md", markdown_summary(result))
    print(run_dir.relative_to(ROOT))
    print(result["status"])
    return 0 if result["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="phase", required=True)
    local = subparsers.add_parser("local")
    local.add_argument("--image-tag", default="priori-deploy2:local")
    local.add_argument("--timeout", type=int, default=1800)
    live = subparsers.add_parser("live")
    live.add_argument("--base-url", required=True)
    live.add_argument("--service-id", required=True)
    live.add_argument("--deploy-id", required=True)
    live.add_argument("--stability-seconds", type=int, default=300)
    args = parser.parse_args()
    if args.phase == "local":
        return local_phase(args)
    return live_phase(args)


if __name__ == "__main__":
    raise SystemExit(main())
