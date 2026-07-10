#!/usr/bin/env python3
"""R-AZ producer for DEPLOY-2 lazy hydration, 2 GiB proof, and live closure."""

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
MEMORY_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
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
FILM_ROOM_PLANS = (
    (
        "fragile_retention",
        ROOT / "delivery/packets/r2-2-flagship/fragile_retention_rate_v0.json",
    ),
    (
        "counterattack_sequence_rate",
        ROOT / "delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_v0.json",
    ),
)


class ContainerStopped(RuntimeError):
    def __init__(self, message: str, *, sampled_peak: int) -> None:
        super().__init__(message)
        self.sampled_peak = sampled_peak


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
    committed = command(["git", "show", f"HEAD:{relative}"], env=git_env).stdout.encode()
    if committed != script.read_bytes():
        raise RuntimeError("R-AZ refusal: producer is not byte-identical to committed HEAD")
    dirty = command(["git", "diff", "--quiet", "HEAD", "--", "."], env=git_env, check=False)
    if dirty.returncode:
        raise RuntimeError("R-AZ refusal: tracked worktree differs from HEAD")
    oracle_hashes = {name: sha256_path(path) for name, path in ORACLES.items()}
    if oracle_hashes != EXPECTED_ORACLE_SHA256:
        raise RuntimeError(f"leg-zero refusal: fenced oracle hashes changed: {oracle_hashes}")
    now = datetime.now(UTC)
    script_hash = sha256_path(script)
    metadata = {
        "schema_version": "deploy2.evidence.v2",
        "run_started_at": now.isoformat(),
        "producing_script": relative,
        "producing_script_sha256": script_hash,
        "producing_commit": git_output(["rev-parse", "HEAD"], git_env),
        "producing_tree": git_output(["rev-parse", "HEAD^{tree}"], git_env),
        "branch": git_output(["branch", "--show-current"], git_env),
        "oracle_sha256": oracle_hashes,
        "run_id": f"{now.strftime('%Y-%m-%dT%H%M%S.%fZ')}-{script_hash[:12]}",
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def get_json(url: str, *, timeout: int = 60) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected object from {url}")
    return payload


def post_json(url: str, payload: dict[str, Any], *, timeout: int = 120) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())
    if not isinstance(result, dict):
        raise RuntimeError(f"expected object from {url}")
    return result


def docker_image_id(tag: str) -> str:
    return command(["docker", "image", "inspect", tag, "--format", "{{.Id}}"]).stdout.strip()


def build_image(tag: str, revision: str, log_path: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="priori-deploy2-context-") as directory:
        context = Path(directory) / "context"
        context.mkdir()
        archive_path = Path(directory) / "source.tar"
        command(["git", "archive", "--format=tar", f"--output={archive_path}", revision])
        with tarfile.open(archive_path, "r:") as archive:
            archive.extractall(context, filter="data")
        completed = command(
            [
                "docker",
                "build",
                "--label",
                f"org.opencontainers.image.revision={revision}",
                "--tag",
                tag,
                str(context),
            ],
            timeout=5400,
            check=False,
        )
    write_text(log_path, completed.stdout + completed.stderr)
    if completed.returncode:
        raise RuntimeError(f"Docker build failed; see {log_path}")
    image_id = docker_image_id(tag)
    label = command(
        [
            "docker",
            "image",
            "inspect",
            tag,
            "--format",
            "{{index .Config.Labels \"org.opencontainers.image.revision\"}}",
        ]
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


def cgroup_peak(name: str) -> int:
    value = command(
        [
            "docker",
            "exec",
            name,
            "sh",
            "-c",
            "cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory.current",
        ],
        check=False,
    ).stdout.strip()
    return int(value) if value.isdigit() else 0


def build_role_caches(
    tag: str,
    stage: Path,
    run_id: str,
    timeout: int,
    log_path: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    logs: list[str] = []
    for key, plan in FILM_ROOM_PLANS:
        payload = json.loads(plan.read_text(encoding="utf-8"))
        documents = payload.get("documents") if isinstance(payload, dict) else None
        roles = sorted(documents) if isinstance(documents, dict) else [
            str(payload.get("default_invocation", {}).get("perspective_team_role") or "single")
        ]
        for role in roles:
            name = f"priori-d2-cache-{run_id[-8:]}-{len(records)}"
            completed = command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    name,
                    "--mount",
                    f"type=bind,source={stage.resolve()},target=/var/data",
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
                    "WORKBENCH_FILM_ROOM_RESULT_LIMIT=25",
                    tag,
                    "python",
                    "/app/scripts/packets/deploy2_cache_builder.py",
                    "--key",
                    key,
                    "--plan",
                    f"/app/{plan.relative_to(ROOT).as_posix()}",
                    "--role",
                    role,
                    "--output-root",
                    "/var/data/runtime",
                ],
                timeout=timeout,
                check=False,
            )
            logs.append(f"$ key={key} role={role}\n{completed.stdout}{completed.stderr}")
            if completed.returncode:
                write_text(log_path, "\n".join(logs))
                raise RuntimeError(f"isolated cache generation failed for {plan.name}/{role}")
            lines = [line for line in completed.stdout.splitlines() if line.startswith("{")]
            if not lines:
                write_text(log_path, "\n".join(logs))
                raise RuntimeError(f"cache builder emitted no record for {plan.name}/{role}")
            records.append(json.loads(lines[-1]))
    write_text(log_path, "\n".join(logs))
    return records


def start_proof_container(
    name: str,
    volume: str,
    tag: str,
    bundle: Path,
    manifest: Path,
    bundle_sha: str,
) -> tuple[str, int]:
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
        f"type=bind,source={bundle.parent.resolve()},target=/bundle,readonly",
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


def wait_for_descriptor_gallery(
    base_url: str,
    name: str,
    timeout: int,
) -> tuple[dict[str, Any], int]:
    deadline = time.monotonic() + timeout
    sampled_peak = 0
    last_error = "service did not answer"
    while time.monotonic() < deadline:
        sampled_peak = max(sampled_peak, cgroup_peak(name))
        state = command(
            ["docker", "inspect", name, "--format", "{{.State.Status}} {{.State.OOMKilled}}"],
            check=False,
        ).stdout.strip()
        if "true" in state.lower() or state.startswith("exited"):
            raise ContainerStopped(
                f"container stopped before descriptor gallery became ready: {state}",
                sampled_peak=sampled_peak,
            )
        try:
            boot = get_json(f"{base_url}/api/film-room/bootstrap")
            answer = boot.get("answer") if isinstance(boot.get("answer"), dict) else {}
            moments = answer.get("moments") if isinstance(answer.get("moments"), list) else []
            records = [
                record
                for record in boot.get("prewarm_records", [])
                if record.get("prewarm_kind") == "descriptor_index_upgrade"
            ]
            chain_count = sum(
                1
                for moment in moments
                if isinstance(moment, dict) and moment.get("source_kind") == "chain_record"
            )
            no_full_payloads = bool(records) and all(
                record.get("execution_performed") is False
                and record.get("full_execution_cache_payloads_opened") == 0
                for record in records
            )
            descriptor_outcomes_valid = any(record.get("upgrade_applied") is True for record in records) and all(
                record.get("upgrade_applied") is True
                or record.get("reason") == "no_chain_descriptors"
                for record in records
            )
            if (
                boot.get("state") == "ready"
                and len(records) >= 2
                and chain_count >= 2
                and no_full_payloads
                and descriptor_outcomes_valid
            ):
                return boot, sampled_peak
            last_error = (
                f"state={boot.get('state')} descriptor_records={len(records)} "
                f"chain_records={chain_count} no_full_payloads={no_full_payloads} "
                f"descriptor_outcomes_valid={descriptor_outcomes_valid}"
            )
        except Exception as exc:  # noqa: BLE001 - readiness loop retains final transport state.
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"descriptor gallery did not become ready in {timeout}s: {last_error}")


def hydrate_two_windows(base_url: str, bootstrap: dict[str, Any], name: str) -> tuple[list[dict[str, Any]], int]:
    answer = bootstrap.get("answer") if isinstance(bootstrap.get("answer"), dict) else {}
    moments = answer.get("moments") if isinstance(answer.get("moments"), list) else []
    replay_ids: list[str] = []
    for moment in moments:
        if not isinstance(moment, dict) or moment.get("source_kind") != "chain_record":
            continue
        replay_id = str(moment.get("replay_window_id") or "")
        if replay_id and replay_id not in replay_ids:
            replay_ids.append(replay_id)
        if len(replay_ids) == 2:
            break
    if len(replay_ids) != 2:
        raise RuntimeError(f"bootstrap exposed only {len(replay_ids)} distinct chain windows")
    records: list[dict[str, Any]] = []
    sampled_peak = cgroup_peak(name)
    for replay_id in replay_ids:
        response = post_json(
            f"{base_url}/api/film-room/replay-window",
            {"replay_window_id": replay_id},
        )
        replay = response.get("replay") if isinstance(response.get("replay"), dict) else {}
        overlays = replay.get("overlays") if isinstance(replay.get("overlays"), dict) else {}
        stages = overlays.get("stages") if isinstance(overlays.get("stages"), list) else []
        if replay.get("replay_window_id") != replay_id or not stages:
            raise RuntimeError(f"hydrated replay lacks stage overlays: {replay_id}")
        sampled_peak = max(sampled_peak, cgroup_peak(name))
        records.append(
            {
                "replay_window_id": replay_id,
                "source_kind": replay.get("source_kind"),
                "frame_count": len(replay.get("frames") or []),
                "stage_count": len(stages),
                "carry_trail_count": len(overlays.get("carry_trails") or []),
                "memory_peak_bytes_after_hydration": sampled_peak,
            }
        )
    return records, sampled_peak


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
    elif name == "gallery_ready":
        argv.extend(["--ready-timeout", str(min(timeout, 300))])
    completed = command(argv, timeout=timeout + 60, check=False)
    output_file = f"{name}.txt"
    write_text(run_dir / output_file, completed.stdout + completed.stderr)
    return {"exit_code": completed.returncode, "output_file": output_file}


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
                f"- Descriptor upgrades: `{local.get('descriptor_upgrade_count')}`",
                f"- Hydrated windows: `{len(local.get('hydrations', []))}`",
            ]
        )
    else:
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
    proof_suffix = metadata["run_id"][-20:].replace(".", "-")
    proof_name = f"priori-d2-proof-{proof_suffix}"
    proof_volume = proof_name
    proof_started = False
    try:
        image_id = build_image(image_tag, metadata["producing_commit"], run_dir / "docker-build.log")
        result["image"] = {
            "tag": image_tag,
            "id": image_id,
            "revision": metadata["producing_commit"],
            "build_context": "git archive of producing commit",
        }
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
        cache_records = build_role_caches(
            image_tag,
            stage,
            metadata["run_id"],
            args.timeout,
            run_dir / "cache-build-service.log",
        )
        if len(cache_records) != 4:
            raise RuntimeError(f"expected four role descriptor fragments, got {cache_records}")
        descriptors_by_key = {
            key: sum(
                int(record.get("descriptor_count") or 0)
                for record in cache_records
                if record.get("flagship_key") == key
            )
            for key, _ in FILM_ROOM_PLANS
        }
        if descriptors_by_key["counterattack_sequence_rate"] < 2:
            raise RuntimeError(f"counterattack chain descriptors are insufficient: {descriptors_by_key}")
        result["cache_generation"] = {
            "role_records": cache_records,
            "descriptor_count_by_flagship": descriptors_by_key,
        }

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
        if bundle_manifest.get("source_commit") != metadata["producing_commit"]:
            raise RuntimeError("final bundle source commit does not match producing commit")
        if bundle_manifest.get("source_dirty"):
            raise RuntimeError("final bundle provenance reports a dirty source")
        shutil.copy2(manifest, run_dir / "bundle-manifest.json")
        result["bundle"] = {
            "path": str(bundle.relative_to(ROOT)),
            "manifest_path": str(manifest.relative_to(ROOT)),
            "archive_sha256": bundle_sha,
            "runtime_code_epoch": bundle_manifest.get("runtime_code_epoch"),
            "file_count": bundle_manifest.get("file_count"),
            "compressed_size_bytes": bundle_manifest.get("compressed_size_bytes"),
        }

        command(["docker", "volume", "create", proof_volume])
        _, proof_port = start_proof_container(
            proof_name,
            proof_volume,
            image_tag,
            bundle,
            manifest,
            bundle_sha,
        )
        proof_started = True
        base_url = f"http://127.0.0.1:{proof_port}"
        bootstrap, sampled_peak = wait_for_descriptor_gallery(
            base_url,
            proof_name,
            args.timeout,
        )
        hydrations, hydration_peak = hydrate_two_windows(base_url, bootstrap, proof_name)
        sampled_peak = max(sampled_peak, hydration_peak)
        write_json(run_dir / "local-bootstrap.json", {**metadata, "bootstrap": bootstrap})
        write_json(run_dir / "local-hydrations.json", {**metadata, "hydrations": hydrations})
        oracle_results = {
            name: run_oracle(name, base_url, run_dir, args.timeout)
            for name in ("deploy_smoke", "gallery_ready", "chain_gallery")
        }
        memory_peak = max(sampled_peak, cgroup_peak(proof_name))
        memory_events = command(
            [
                "docker",
                "exec",
                proof_name,
                "sh",
                "-c",
                "cat /sys/fs/cgroup/memory.events 2>/dev/null || true",
            ],
            check=False,
        ).stdout
        write_text(run_dir / "memory-events.txt", memory_events)
        state_payload = json.loads(
            command(["docker", "inspect", proof_name, "--format", "{{json .State}}" ]).stdout
        )
        host_memory = int(
            command(["docker", "inspect", proof_name, "--format", "{{.HostConfig.Memory}}" ]).stdout
        )
        descriptor_records = [
            record
            for record in bootstrap.get("prewarm_records", [])
            if record.get("prewarm_kind") == "descriptor_index_upgrade"
        ]
        stop_state = stop_container(proof_name, run_dir / "local-service.log")
        proof_started = False
        command(["docker", "volume", "rm", proof_volume], check=False)
        oom_events = 0
        for line in memory_events.splitlines():
            key, _, value = line.partition(" ")
            if key in {"oom", "oom_kill", "oom_group_kill"} and value.isdigit():
                oom_events += int(value)
        local_ok = (
            host_memory == MEMORY_LIMIT_BYTES
            and not bool(state_payload.get("OOMKilled"))
            and oom_events == 0
            and 0 < memory_peak <= MEMORY_LIMIT_BYTES
            and len(descriptor_records) >= 2
            and all(record.get("full_execution_cache_payloads_opened") == 0 for record in descriptor_records)
            and len(hydrations) == 2
            and len({record["replay_window_id"] for record in hydrations}) == 2
            and all(record["stage_count"] > 0 for record in hydrations)
            and all(item["exit_code"] == 0 for item in oracle_results.values())
        )
        result.update(
            {
                "status": "PASS" if local_ok else "FAIL",
                "local_proof": {
                    "base_url": base_url,
                    "memory_limit_bytes": host_memory,
                    "memory_peak_bytes": memory_peak,
                    "memory_peak_mib": round(memory_peak / 1024 / 1024, 3),
                    "oom_killed": bool(state_payload.get("OOMKilled")),
                    "oom_event_count": oom_events,
                    "descriptor_upgrade_count": len(descriptor_records),
                    "full_execution_cache_payloads_opened": sum(
                        int(record.get("full_execution_cache_payloads_opened") or 0)
                        for record in descriptor_records
                    ),
                    "hydrations": hydrations,
                    "container_state": state_payload,
                    "container_inspect": stop_state,
                },
                "oracles": oracle_results,
            }
        )
    except ContainerStopped as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        result["local_proof"] = {
            "memory_limit_bytes": MEMORY_LIMIT_BYTES,
            "sampled_memory_peak_bytes": exc.sampled_peak,
            "sampled_memory_peak_mib": round(exc.sampled_peak / 1024 / 1024, 3),
        }
    except Exception as exc:  # noqa: BLE001 - every failure is sealed as evidence.
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
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
            health = get_json(f"{result['base_url']}/healthz")
            boot = get_json(f"{result['base_url']}/api/film-room/bootstrap")
            answer = boot.get("answer") if isinstance(boot.get("answer"), dict) else {}
            moments = answer.get("moments") if isinstance(answer.get("moments"), list) else []
            descriptor_records = [
                record
                for record in boot.get("prewarm_records", [])
                if record.get("prewarm_kind") == "descriptor_index_upgrade"
            ]
            samples.append(
                {
                    "sampled_at": datetime.now(UTC).isoformat(),
                    "health_status": health.get("status"),
                    "gallery_state": boot.get("state"),
                    "chain_record_count": sum(
                        1
                        for moment in moments
                        if isinstance(moment, dict) and moment.get("source_kind") == "chain_record"
                    ),
                    "descriptor_upgrade_count": len(descriptor_records),
                    "full_execution_cache_payloads_opened": sum(
                        int(record.get("full_execution_cache_payloads_opened") or 0)
                        for record in descriptor_records
                    ),
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
            and sample["chain_record_count"] >= 2
            and sample["descriptor_upgrade_count"] >= 2
            and sample["full_execution_cache_payloads_opened"] == 0
            for sample in samples
        )
        result["samples"] = samples
        result["oracles"] = oracle_results
        result["status"] = (
            "PASS"
            if stable and all(item["exit_code"] == 0 for item in oracle_results.values())
            else "FAIL"
        )
    except Exception as exc:  # noqa: BLE001 - every failure is sealed as evidence.
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
    local.add_argument("--timeout", type=int, default=3600)
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
