#!/usr/bin/env python3
"""R-AZ proof for DEPLOY-2's prewarm-off descriptor-index fix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.executor import runtime_code_epoch

from scripts.packets.deploy2_evidence import (
    BUNDLE_NAME,
    EXPECTED_ORACLE_SHA256,
    MEMORY_LIMIT_BYTES,
    ORACLES,
    build_image,
    cgroup_peak,
    command,
    container_port,
    get_json,
    hydrate_two_windows,
    run_oracle,
    sha256_path,
    stop_container,
)


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "delivery/packets/deploy-2-fix-evidence/runs"
MINIMUM_HEADROOM_BYTES = 512 * 1024 * 1024
PRODUCER_FILES = (
    ROOT / "scripts/packets/deploy2_fix_evidence.py",
    ROOT / "scripts/packets/deploy2_evidence.py",
)


def isolated_git_env() -> dict[str, str]:
    handle, name = tempfile.mkstemp(prefix="priori-deploy2-fix-index-", dir="/private/tmp")
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
    for path in PRODUCER_FILES:
        relative = path.relative_to(ROOT).as_posix()
        committed = command(["git", "show", f"HEAD:{relative}"], env=git_env).stdout.encode()
        if committed != path.read_bytes():
            raise RuntimeError(f"R-AZ refusal: {relative} differs from committed HEAD")
    dirty = command(["git", "diff", "--quiet", "HEAD", "--", "."], env=git_env, check=False)
    if dirty.returncode:
        raise RuntimeError("R-AZ refusal: tracked worktree differs from HEAD")
    oracle_hashes = {name: sha256_path(path) for name, path in ORACLES.items()}
    if oracle_hashes != EXPECTED_ORACLE_SHA256:
        raise RuntimeError(f"leg-zero refusal: fenced oracle hashes changed: {oracle_hashes}")
    now = datetime.now(UTC)
    script = PRODUCER_FILES[0]
    script_hash = sha256_path(script)
    return (
        {
            "schema_version": "deploy2.fix.evidence.v1",
            "run_started_at": now.isoformat(),
            "producing_script": script.relative_to(ROOT).as_posix(),
            "producing_script_sha256": script_hash,
            "helper_script_sha256": sha256_path(PRODUCER_FILES[1]),
            "producing_commit": git_output(["rev-parse", "HEAD"], git_env),
            "producing_tree": git_output(["rev-parse", "HEAD^{tree}"], git_env),
            "branch": git_output(["branch", "--show-current"], git_env),
            "oracle_sha256": oracle_hashes,
            "run_id": f"{now.strftime('%Y-%m-%dT%H%M%S.%fZ')}-{script_hash[:12]}",
        },
        git_env,
    )


def allocate_run(metadata: dict[str, Any]) -> Path:
    run_dir = EVIDENCE_ROOT / metadata["run_id"]
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


def validate_bundle(
    bundle: Path,
    manifest: Path,
    producing_commit: str,
    git_env: dict[str, str],
) -> dict[str, Any]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    archive_sha = sha256_path(bundle)
    if payload.get("archive_sha256") != archive_sha:
        raise RuntimeError("bundle archive SHA does not match manifest")
    if payload.get("source_dirty"):
        raise RuntimeError("bundle manifest reports dirty source")
    if payload.get("runtime_code_epoch") != runtime_code_epoch():
        raise RuntimeError("bundle runtime code epoch is stale")
    source_commit = str(payload.get("source_commit") or "")
    ancestor = command(
        ["git", "merge-base", "--is-ancestor", source_commit, producing_commit],
        env=git_env,
        check=False,
    )
    if not source_commit or ancestor.returncode:
        raise RuntimeError("bundle source commit is not an ancestor of the proof commit")
    required = {
        "cache/film-room-descriptor-fragments/counterattack_sequence_rate-away.json",
        "cache/film-room-descriptor-fragments/counterattack_sequence_rate-home.json",
        "cache/film-room-descriptor-fragments/fragile_retention-away.json",
        "cache/film-room-descriptor-fragments/fragile_retention-home.json",
    }
    paths = {str(item.get("path") or "") for item in payload.get("files") or []}
    missing = sorted(required - paths)
    if missing:
        raise RuntimeError(f"bundle lacks descriptor fragments: {missing}")
    return {
        "path": str(bundle.relative_to(ROOT)),
        "manifest_path": str(manifest.relative_to(ROOT)),
        "archive_sha256": archive_sha,
        "compressed_size_bytes": bundle.stat().st_size,
        "source_commit": source_commit,
        "runtime_code_epoch": payload.get("runtime_code_epoch"),
        "descriptor_fragment_count": len(required),
    }


def provision_volume(
    *,
    name: str,
    volume: str,
    image_tag: str,
    bundle: Path,
    manifest: Path,
    bundle_sha: str,
    log_path: Path,
) -> None:
    completed = command(
        [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--mount",
            f"type=volume,source={volume},target=/var/data",
            "--mount",
            f"type=bind,source={bundle.parent.resolve()},target=/bundle,readonly",
            image_tag,
            "python",
            "/app/scripts/provision-demo-data.py",
            "--dataset-root",
            "/var/data/dataset",
            "--cache-root",
            "/var/data/cache",
            "--runtime-root",
            "/var/data/runtime",
            "--manifest",
            "/app/config/deploy/demo-data-manifest.json",
            "--bundle-manifest",
            f"/bundle/{manifest.name}",
            "--bundle-url",
            f"file:///bundle/{bundle.name}",
            "--bundle-sha256",
            bundle_sha,
        ],
        timeout=1800,
        check=False,
    )
    write_text(log_path, completed.stdout + completed.stderr)
    if completed.returncode:
        raise RuntimeError(f"unmeasured retained-disk provisioning failed; see {log_path}")
    if "Demo data provisioned and verified." not in completed.stdout:
        raise RuntimeError("retained-disk provisioning did not report verified installation")


def start_measured_service(
    *,
    name: str,
    volume: str,
    image_tag: str,
    bundle: Path,
    bundle_sha: str,
) -> tuple[str, int]:
    container_id = command(
        [
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
            "WORKBENCH_PREWARM_FILM_ROOM=0",
            "--env",
            "TQE_EXECUTION_WORKERS=1",
            "--env",
            "TQE_PUBLIC_MODE=1",
            "--env",
            f"TQE_DATA_BUNDLE_URL=file:///bundle/{bundle.name}",
            "--env",
            f"TQE_DATA_BUNDLE_SHA256={bundle_sha}",
            image_tag,
        ]
    ).stdout.strip()
    return container_id, container_port(name)


def wait_for_descriptor_gallery(
    base_url: str,
    container_name: str,
    timeout: int,
) -> tuple[dict[str, Any], int]:
    deadline = time.monotonic() + timeout
    sampled_peak = 0
    last_error = "service did not answer"
    while time.monotonic() < deadline:
        sampled_peak = max(sampled_peak, cgroup_peak(container_name))
        state = command(
            [
                "docker",
                "inspect",
                container_name,
                "--format",
                "{{.State.Status}} {{.State.OOMKilled}}",
            ],
            check=False,
        ).stdout.strip()
        if "true" in state.lower() or state.startswith("exited"):
            raise RuntimeError(f"measured container stopped before ready: {state}")
        try:
            bootstrap = get_json(f"{base_url}/api/film-room/bootstrap")
            answer = bootstrap.get("answer") if isinstance(bootstrap.get("answer"), dict) else {}
            moments = answer.get("moments") if isinstance(answer.get("moments"), list) else []
            records = [
                record
                for record in bootstrap.get("prewarm_records", [])
                if record.get("prewarm_kind") == "descriptor_index_load"
            ]
            chain_count = sum(
                1
                for moment in moments
                if isinstance(moment, dict) and moment.get("source_kind") == "chain_record"
            )
            metadata_only = bool(records) and all(
                record.get("execution_performed") is False
                and record.get("full_execution_cache_payloads_opened") == 0
                for record in records
            )
            if bootstrap.get("state") == "ready" and chain_count >= 2 and metadata_only:
                return bootstrap, sampled_peak
            last_error = (
                f"state={bootstrap.get('state')} chain_records={chain_count} "
                f"descriptor_records={len(records)} metadata_only={metadata_only}"
            )
        except Exception as exc:  # noqa: BLE001 - readiness records final transport state.
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"descriptor gallery did not become ready: {last_error}")


def markdown_summary(payload: dict[str, Any]) -> str:
    proof = payload.get("local_proof", {})
    lines = [
        "# DEPLOY-2 fix R-AZ evidence",
        "",
        f"- Status: `{payload['status']}`",
        f"- Producing commit: `{payload['producing_commit']}`",
        f"- Film Room execution prewarm: `{proof.get('execution_prewarm')}`",
        f"- Memory limit: `{proof.get('memory_limit_bytes')}` bytes",
        f"- Cgroup peak: `{proof.get('memory_peak_bytes')}` bytes",
        f"- Headroom: `{proof.get('memory_headroom_mib')}` MiB",
        f"- OOM event count: `{proof.get('oom_event_count')}`",
        "",
        "| Oracle | Exit |",
        "| --- | ---: |",
    ]
    for name, result in payload.get("oracles", {}).items():
        lines.append(f"| `{name}` | {result['exit_code']} |")
    return "\n".join(lines) + "\n"


def local_phase(args: argparse.Namespace) -> int:
    metadata, git_env = producer_metadata()
    run_dir = allocate_run(metadata)
    result: dict[str, Any] = {**metadata, "phase": "local", "status": "FAIL"}
    image_tag = args.image_tag
    suffix = metadata["run_id"].replace(".", "-")[-28:]
    volume = f"priori-d2-fix-{suffix}"
    provision_name = f"{volume}-provision"
    proof_name = f"{volume}-proof"
    proof_started = False
    try:
        bundle = args.bundle.resolve()
        manifest = args.manifest.resolve()
        result["bundle"] = validate_bundle(
            bundle,
            manifest,
            metadata["producing_commit"],
            git_env,
        )
        image_id = build_image(
            image_tag,
            metadata["producing_commit"],
            run_dir / "docker-build.log",
        )
        result["image"] = {
            "tag": image_tag,
            "id": image_id,
            "revision": metadata["producing_commit"],
            "build_context": "git archive of producing commit",
        }
        command(["docker", "volume", "create", volume])
        provision_volume(
            name=provision_name,
            volume=volume,
            image_tag=image_tag,
            bundle=bundle,
            manifest=manifest,
            bundle_sha=result["bundle"]["archive_sha256"],
            log_path=run_dir / "retained-disk-provision.log",
        )
        _, port = start_measured_service(
            name=proof_name,
            volume=volume,
            image_tag=image_tag,
            bundle=bundle,
            bundle_sha=result["bundle"]["archive_sha256"],
        )
        proof_started = True
        base_url = f"http://127.0.0.1:{port}"
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
            if record.get("prewarm_kind") == "descriptor_index_load"
        ]
        oom_events = 0
        for line in memory_events.splitlines():
            key, _, value = line.partition(" ")
            if key in {"oom", "oom_kill", "oom_group_kill"} and value.isdigit():
                oom_events += int(value)
        headroom = host_memory - memory_peak
        stop_state = stop_container(proof_name, run_dir / "local-service.log")
        proof_started = False
        local_ok = (
            host_memory == MEMORY_LIMIT_BYTES
            and headroom >= MINIMUM_HEADROOM_BYTES
            and not bool(state_payload.get("OOMKilled"))
            and oom_events == 0
            and len(descriptor_records) >= 2
            and all(record.get("execution_performed") is False for record in descriptor_records)
            and len(hydrations) == 2
            and all(record.get("stage_count", 0) > 0 for record in hydrations)
            and all(item["exit_code"] == 0 for item in oracle_results.values())
        )
        result.update(
            {
                "status": "PASS" if local_ok else "FAIL",
                "local_proof": {
                    "base_url": base_url,
                    "execution_prewarm": "OFF",
                    "measured_scope": "retained-disk service startup + bootstrap + two hydrations + oracles",
                    "memory_limit_bytes": host_memory,
                    "memory_peak_bytes": memory_peak,
                    "memory_peak_mib": round(memory_peak / 1024 / 1024, 3),
                    "memory_headroom_bytes": headroom,
                    "memory_headroom_mib": round(headroom / 1024 / 1024, 3),
                    "memory_headroom_percent": round(100 * headroom / host_memory, 3),
                    "minimum_required_headroom_bytes": MINIMUM_HEADROOM_BYTES,
                    "oom_event_count": oom_events,
                    "oom_killed": bool(state_payload.get("OOMKilled")),
                    "descriptor_record_count": len(descriptor_records),
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
    except Exception as exc:  # noqa: BLE001 - every failure is sealed as evidence.
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if proof_started:
            stop_container(proof_name, run_dir / "local-service-failure.log")
        command(["docker", "rm", "-f", provision_name], check=False)
        command(["docker", "volume", "rm", volume], check=False)
        write_json(run_dir / "deploy2-fix-evidence.json", result)
        write_text(run_dir / "deploy2-fix-evidence.md", markdown_summary(result))
    print(run_dir.relative_to(ROOT))
    print(result["status"])
    return 0 if result["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=ROOT / f"artifacts/cloud-alpha/{BUNDLE_NAME}.tar.gz",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / f"artifacts/cloud-alpha/{BUNDLE_NAME}.manifest.json",
    )
    parser.add_argument("--image-tag", default="priori-deploy2-fix:local")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    return local_phase(args)


if __name__ == "__main__":
    raise SystemExit(main())
