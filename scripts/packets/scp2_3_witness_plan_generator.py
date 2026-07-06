#!/usr/bin/env python3
"""Generate the SCP2-3 witness-enriched R2-4 plan copy."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = ROOT / "scripts/packets/r2_4_flagship_generator.py"
DEFAULT_OUT_DIR = ROOT / "delivery/packets/scp2-3-evidence/witness-plan"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def file_sha256(path: Path) -> str:
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
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else "unknown"


def load_generator() -> Any:
    spec = importlib.util.spec_from_file_location("r2_4_flagship_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def output_record(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": relative(path),
        "sha256": file_sha256(path),
    }
    if path.suffix == ".json":
        from tqe.runtime.ir import stable_hash

        record["stable_hash"] = stable_hash(read_json(path))
    return record


def generate_witness_plan(*, output_dir: Path, canonical_root: Path, raw_root: Path, long_threshold_seconds: float) -> dict[str, Any]:
    generator = load_generator()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "counterattack_initiation_v0.json"
    table_json = output_dir / "counterattack_initiation_table.json"
    table_md = output_dir / "counterattack_initiation_table.md"
    generator_provenance = output_dir / "r2_4_generator_provenance.json"
    provenance_path = output_dir / "provenance.json"
    local_sidecar = Path("/private/tmp") / f"scp2-3-witness-plan-sidecar-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    for path in (plan_path, table_json, table_md, generator_provenance, provenance_path):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite evidence file: {path}")

    generator.OUT_DIR = output_dir
    generator.PLAN_PATH = plan_path
    generator.PROVENANCE_PATH = generator_provenance
    generator.TABLE_JSON = table_json
    generator.TABLE_MD = table_md
    generator.LOCAL_SIDECAR = local_sidecar

    run_started_at = utc_now()
    summary = generator.write_artifacts(
        canonical_root=canonical_root,
        raw_root=raw_root,
        long_threshold_seconds=long_threshold_seconds,
    )
    outputs = {
        "plan": output_record(plan_path),
        "table_json": output_record(table_json),
        "table_markdown": output_record(table_md),
        "r2_4_generator_provenance": output_record(generator_provenance),
    }
    provenance = {
        "schema_version": "scp2_3_witness_plan_provenance.v1",
        "produced_by": relative(Path(__file__)),
        "producing_script_sha256": file_sha256(Path(__file__).resolve()),
        "generated_by": relative(GENERATOR_PATH),
        "generator_script_sha256": file_sha256(GENERATOR_PATH),
        "run_started_at": run_started_at,
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
        "output_dir": relative(output_dir),
        "canonical_root": str(canonical_root),
        "raw_root": str(raw_root),
        "local_sidecar_path": str(local_sidecar),
        "generator_summary": summary,
        "outputs": outputs,
    }
    write_json(provenance_path, provenance)
    return {"provenance": output_record(provenance_path), **provenance}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--canonical-root",
        default="data/canonical/v1",
        help="Canonical parquet root used for execution.",
    )
    parser.add_argument(
        "--raw-root",
        default="data/raw/idsse/figshare-28196177-v1",
        help="Raw IDSSE root used for execution.",
    )
    parser.add_argument("--long-threshold-seconds", type=float, default=300.0)
    args = parser.parse_args(argv)
    summary = generate_witness_plan(
        output_dir=args.output_dir,
        canonical_root=Path(args.canonical_root),
        raw_root=Path(args.raw_root),
        long_threshold_seconds=float(args.long_threshold_seconds),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
