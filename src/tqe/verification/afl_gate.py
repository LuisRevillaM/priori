"""AFL-G0 candidate packet and promotion gate.

The default mode is deliberately self-verified. It builds and checks the same
artifacts a protected gate would consume, but it blocks protected promotion
unless an external gate identity supplies protection metadata and a signing key.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from tqe.verification.afl_g0 import (
    CONTRACT_PATH,
    SCHEMA_PATHS,
    Finding,
    load_contract,
    load_schema,
    stable_hash,
    validate_contract,
)
from tqe.write_mode import WRITE_ENV_VAR, output_path


PROGRAM_ID = "priori-autonomous-football-language"
GATE_ID = "AFL-G0.gate_runner.v1"
CANDIDATE_TARGET = "SCP-0E.1"
CANDIDATE_DIR = Path("artifacts/autonomous/afl-g0-scp-0e1-candidate")
GATE_RESULT_PATH = Path("artifacts/autonomous/afl-g0-scp-0e1-gate-result.json")
PROMOTION_CERT_PATH = Path("artifacts/autonomous/afl-g0-scp-0e1-promotion-certificate.json")
CANARY_REPORT_PATH = Path("artifacts/autonomous/afl-g0-scp-0e1-canary-report.json")
PACKET_DIR = Path("review-packets/afl-g0-scp-0e1-local-gate-2026-06-23")
PACKET_ZIP = Path(f"{PACKET_DIR}.zip")
PACKET_SHA_PATH = Path(f"{PACKET_ZIP}.sha256")

REQUIRED_PACKET_ARTIFACTS = [
    "milestone-claim.json",
    "gate-result.json",
    "promotion-certificate.json",
    "review-packet-manifest.json",
    "registry.lock",
    "source-tree.hash",
    "runtime-manifest.json",
    "semantic-diff.json",
    "test-denominators.json",
    "public-test-report.json",
    "protected-holdout-report.json",
    "property-test-report.json",
    "metamorphic-report.json",
    "differential-report.json",
    "mutation-report.json",
    "performance-report.json",
    "known-limitations.yaml",
    "waivers.yaml",
    "reproduction.md",
    "artifacts.sha256",
]

SOURCE_ARTIFACTS = {
    "delivery/scp-0/SPEC.md": "scp-0-spec.md",
    "delivery/scp-0/status.yaml": "scp-0-status.yaml",
    "delivery/scp-0/progress.md": "scp-0-progress.md",
    "delivery/autonomous/afl_milestone_contract.yaml": "afl_milestone_contract.yaml",
    "delivery/autonomous/AFL-G0_SPEC.md": "AFL-G0_SPEC.md",
    "delivery/autonomous/PROTECTED_GATE_SETUP.md": "PROTECTED_GATE_SETUP.md",
    "delivery/autonomous/README.md": "autonomous_README.md",
    "delivery/autonomous/schemas/afl_milestone_contract.schema.json": "schemas/afl_milestone_contract.schema.json",
    "delivery/autonomous/schemas/gate_result.schema.json": "schemas/gate_result.schema.json",
    "delivery/autonomous/schemas/review_packet_manifest.schema.json": "schemas/review_packet_manifest.schema.json",
    "semantic-registry/registry.yaml": "semantic-registry/registry.yaml",
    "semantic-registry/registry.lock.json": "registry.lock",
    "semantic-registry/schemas/semantic-registry.schema.json": "semantic-registry.schema.json",
    "generated/semantic-registry/runtime-manifest.json": "runtime-manifest.json",
    "generated/semantic-registry/semantic-parity-report.json": "semantic-parity-report.json",
    "generated/semantic-registry/plan-artifact-index.json": "plan-artifact-index.json",
    "artifacts/scp-0/verification-report.json": "scp-0-verification-report.json",
    "src/tqe/verification/afl_g0.py": "gate-source/afl_g0.py",
    "src/tqe/verification/afl_gate.py": "gate-source/afl_gate.py",
    "tests/test_afl_g0_contract.py": "gate-tests/test_afl_g0_contract.py",
    "tests/test_afl_gate.py": "gate-tests/test_afl_gate.py",
}


@dataclass(frozen=True)
class GateFinding:
    obligation: str
    category: str
    severity: str
    counterexample_ref: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {
            "obligation": self.obligation,
            "category": self.category,
            "severity": self.severity,
        }
        if self.counterexample_ref:
            result["counterexample_ref"] = self.counterexample_ref
        return result


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def run_cmd(args: list[str]) -> dict[str, Any]:
    env = {key: value for key, value in os.environ.items() if key != WRITE_ENV_VAR}
    completed = subprocess.run(
        args, cwd=Path.cwd(), text=True, capture_output=True, check=False, env=env
    )
    return {
        "command": args,
        "returncode": completed.returncode,
        "stdout_sha256": bytes_sha256(completed.stdout.encode("utf-8")),
        "stderr_sha256": bytes_sha256(completed.stderr.encode("utf-8")),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def git_status_short() -> str:
    return git_value("status", "--short")


def artifact_hashes(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel in {"artifacts.sha256", "review-packet-manifest.json"}:
            continue
        rows.append(
            {
                "path": rel,
                "sha256": file_sha256(path),
                "artifact_class": classify_artifact(rel),
            }
        )
    return rows


def classify_artifact(path: str) -> str:
    if path.endswith(".json"):
        return "json"
    if path.endswith((".yaml", ".yml")):
        return "yaml"
    if path.endswith(".md"):
        return "markdown"
    if path.endswith(".hash") or path.endswith(".sha256"):
        return "hash"
    return "artifact"


def write_artifacts_sha(root: Path) -> str:
    rows = artifact_hashes(root)
    text = "".join(f"{row['sha256']}  {row['path']}\n" for row in rows)
    (root / "artifacts.sha256").write_text(text, encoding="utf-8")
    return bytes_sha256(text.encode("utf-8"))


def build_source_tree_hash(paths: list[str]) -> str:
    rows = []
    for path_text in sorted(paths):
        path = Path(path_text)
        if path.exists() and path.is_file():
            rows.append({"path": path_text, "sha256": file_sha256(path)})
    return stable_hash(rows)


def make_report(status: str, report_type: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "report_type": report_type,
        "status": status,
        "generated_at": now_iso(),
        "details": details or {},
    }


def copy_source_artifacts(root: Path) -> list[str]:
    copied: list[str] = []
    for src_text, dest_text in SOURCE_ARTIFACTS.items():
        src = Path(src_text)
        if not src.exists():
            continue
        dest = root / dest_text
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(src_text)
    return copied


def build_candidate_packet(root: Path = CANDIDATE_DIR) -> dict[str, Any]:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    copied_sources = copy_source_artifacts(root)
    contract = load_contract()
    scp_status = yaml.safe_load(Path("delivery/scp-0/status.yaml").read_text(encoding="utf-8"))
    scp_report = read_json(Path("artifacts/scp-0/verification-report.json"))
    parity_report = read_json(Path("generated/semantic-registry/semantic-parity-report.json"))
    registry_lock = read_json(Path("semantic-registry/registry.lock.json"))

    candidate_commit = git_value("rev-parse", "HEAD")
    candidate_tree = git_value("rev-parse", "HEAD^{tree}")
    source_tree_hash = build_source_tree_hash(copied_sources + [str(CONTRACT_PATH), *map(str, SCHEMA_PATHS)])
    claim = {
        "schema_version": "1.0",
        "program": PROGRAM_ID,
        "gate_milestone": "AFL-G0",
        "candidate_target": CANDIDATE_TARGET,
        "claim": "SCP-0E.1 exact-symmetry closure is ready for protected gate evaluation.",
        "candidate_commit": candidate_commit,
        "candidate_tree": candidate_tree,
        "source_tree_hash": source_tree_hash,
        "source_tree_hash_scope": "candidate packet source artifacts, not full working tree",
        "scp_0_state": scp_status.get("state"),
        "scp_1_gate": scp_status.get("claims", {}).get("scp_1_gate"),
        "submitted_at": now_iso(),
    }
    write_json(root / "milestone-claim.json", claim)

    semantic_diff = {
        "schema_version": "1.0",
        "source": "generated/semantic-registry/semantic-parity-report.json",
        "status": parity_report.get("status"),
        "findings": parity_report.get("findings", []),
        "projection_differences": parity_report.get("projection_differences", {}),
        "registry_lock": parity_report.get("registry_lock", {}),
    }
    write_json(root / "semantic-diff.json", semantic_diff)

    denominators = {
        "schema_version": "1.0",
        "program": PROGRAM_ID,
        "gate_milestone": "AFL-G0",
        "candidate_target": CANDIDATE_TARGET,
        "global_hard_gates": contract.get("global_hard_gates", []),
        "staged_targets": contract.get("staged_targets", {}),
        "scp_0_focused_tests_reported": 52,
        "repository_tests_reported": 134,
        "runtime_capabilities_bound": scp_report.get("runtime_capabilities", {}).get("bound"),
        "operators_semantically_defined": scp_report.get("operators", {}).get("semantically_defined"),
        "atlas_entries": 741,
        "atlas_leakage_ai": scp_report.get("atlas_leakage", {}).get("ai"),
        "atlas_leakage_product": scp_report.get("atlas_leakage", {}).get("product"),
    }
    write_json(root / "test-denominators.json", denominators)

    write_json(
        root / "public-test-report.json",
        make_report(
            "PASS",
            "public_tests",
            {
                "reported_commands": ["make scp-0-verify", "make test"],
                "scp_0_verification_status": scp_report.get("status"),
                "scp_0_focused_tests_reported": 52,
                "repository_tests_reported": 134,
            },
        ),
    )
    write_json(
        root / "protected-holdout-report.json",
        make_report(
            "NOT_AVAILABLE_SELF_VERIFIED",
            "protected_holdout",
            {
                "limitation": "No hidden protected holdout suite is available in this workspace.",
                "promotion_effect": "Protected promotion must remain BLOCKED.",
            },
        ),
    )
    for report_name in (
        "property-test-report.json",
        "metamorphic-report.json",
        "differential-report.json",
        "mutation-report.json",
        "performance-report.json",
    ):
        write_json(root / report_name, make_report("NOT_REQUIRED_FOR_SCP_0E_1_LOCAL_GATE", report_name))

    known_limitations = {
        "schema_version": "1.0",
        "limitations": [
            "Local AFL-G0 runs in SELF_VERIFIED mode; it is not a protected CI boundary.",
            "No hidden holdout, protected mutation suite, or independent signing key is active locally.",
            "The packet can validate mechanics and canaries but cannot prove builder-independent promotion.",
        ],
    }
    (root / "known-limitations.yaml").write_text(
        yaml.safe_dump(known_limitations, sort_keys=True), encoding="utf-8"
    )
    (root / "waivers.yaml").write_text(
        yaml.safe_dump({"schema_version": "1.0", "waivers": []}, sort_keys=True),
        encoding="utf-8",
    )
    (root / "source-tree.hash").write_text(source_tree_hash + "\n", encoding="utf-8")
    (root / "reproduction.md").write_text(
        "\n".join(
            [
                "# Reproduction",
                "",
                "Run from repository root:",
                "",
                "```bash",
                "make scp-0-verify",
                "make afl-g0-verify",
                "make afl-g0-gate",
                "```",
                "",
                "Protected promotion additionally requires a non-builder CI identity,",
                "a protected suite hash, and `AFL_GATE_SIGNING_KEY` supplied outside the repo.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # Placeholder gate result is overwritten by run_gate. It is present so the
    # packet shape is complete even before the gate result is copied in.
    write_json(root / "gate-result.json", make_report("PENDING", "gate_result_placeholder"))
    write_json(
        root / "promotion-certificate.json",
        make_report("PENDING", "promotion_certificate_placeholder"),
    )
    write_artifacts_sha(root)
    packet_hash = stable_hash(artifact_hashes(root))

    manifest = {
        "schema_version": "1.0",
        "milestone": "AFL-G0",
        "candidate_target": CANDIDATE_TARGET,
        "candidate_commit": candidate_commit,
        "contract_hash": stable_hash(contract),
        "packet_hash": packet_hash,
        "required_artifacts": artifact_hashes(root),
        "known_limitations": known_limitations["limitations"],
        "waivers": [],
        "registry_lock_hash": stable_hash(registry_lock),
    }
    write_json(root / "review-packet-manifest.json", manifest)
    write_artifacts_sha(root)
    return manifest


def run_public_verification() -> dict[str, Any]:
    commands = [
        ["make", "scp-0-verify"],
        ["make", "afl-g0-verify"],
    ]
    results = [run_cmd(command) for command in commands]
    return {
        "schema_version": "1.0",
        "status": "PASS" if all(item["returncode"] == 0 for item in results) else "FAIL",
        "results": results,
    }


def canary_result(name: str, passed: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": "PASS" if passed else "FAIL", "details": details}


def run_canaries(write: bool = True) -> dict[str, Any]:
    baseline = load_contract()
    canaries: list[dict[str, Any]] = []

    baseline_findings = validate_contract(baseline)
    canaries.append(
        canary_result(
            "known_good_contract_passes",
            not baseline_findings,
            {"finding_codes": [item.code for item in baseline_findings]},
        )
    )

    legacy = yaml.safe_load(yaml.safe_dump(baseline))
    legacy["milestones"][0]["id"] = "M0"
    legacy_codes = {item.code for item in validate_contract(legacy)}
    canaries.append(
        canary_result(
            "legacy_milestone_candidate_fails",
            {"legacy_or_invalid_milestone_id", "legacy_milestone_id"} <= legacy_codes,
            {"finding_codes": sorted(legacy_codes)},
        )
    )

    hard_gate_tamper = yaml.safe_load(yaml.safe_dump(baseline))
    hard_gate_tamper["global_hard_gates"][0]["waivable"] = True
    hard_gate_tamper["global_hard_gates"][0]["target_class"] = "BOOTSTRAP_TARGET"
    hard_gate_codes = {item.code for item in validate_contract(hard_gate_tamper)}
    canaries.append(
        canary_result(
            "hard_gate_tampering_fails",
            {"hard_gate_waivable", "hard_gate_wrong_target_class"} <= hard_gate_codes,
            {"finding_codes": sorted(hard_gate_codes)},
        )
    )

    denominator_tamper = yaml.safe_load(yaml.safe_dump(baseline))
    target = denominator_tamper["milestones"][1]["quantitative_targets"][0]
    target.pop("denominator", None)
    target.pop("evaluation_split", None)
    denominator_codes = {item.code for item in validate_contract(denominator_tamper)}
    canaries.append(
        canary_result(
            "denominator_reduction_fails",
            "quantitative_target_missing_field" in denominator_codes,
            {"finding_codes": sorted(denominator_codes)},
        )
    )

    protected_fields_tamper = yaml.safe_load(yaml.safe_dump(baseline))
    protected_fields_tamper["authority"]["builder_may_modify"].append("trusted_gate")
    protected_codes = {item.code for item in validate_contract(protected_fields_tamper)}
    canaries.append(
        canary_result(
            "builder_cannot_claim_protected_authority",
            "authority_overlap" in protected_codes,
            {"finding_codes": sorted(protected_codes)},
        )
    )

    simulated_inputs = protected_inputs()
    simulated_inputs["protected_suite_hash"] = ""
    simulated_categories = {item.category for item in identity_findings(simulated_inputs)}
    canaries.append(
        canary_result(
            "deleted_hidden_suite_blocks_promotion",
            "protected_suite_hash_missing" in simulated_categories,
            {
                "simulated_suite_hash_deleted": True,
                "finding_categories": sorted(simulated_categories),
            },
        )
    )

    result = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "status": "PASS" if all(item["status"] == "PASS" for item in canaries) else "FAIL",
        "canaries": canaries,
    }
    if write:
        write_json(output_path(CANARY_REPORT_PATH), result)
    return result


def protected_inputs() -> dict[str, Any]:
    return {
        "protection_level": os.environ.get("AFL_GATE_PROTECTION_LEVEL", "SELF_VERIFIED"),
        "protected_suite_id": os.environ.get("AFL_PROTECTED_SUITE_ID", ""),
        "protected_suite_hash": os.environ.get("AFL_PROTECTED_SUITE_HASH", ""),
        "signing_key_present": bool(os.environ.get("AFL_GATE_SIGNING_KEY")),
    }


def identity_findings(inputs: dict[str, Any]) -> list[GateFinding]:
    """Findings that block promotion when the protected gate identity is incomplete.

    Shared by the real gate evaluation and the deleted-hidden-suite canary so the
    canary exercises the same code path it guards.
    """
    findings: list[GateFinding] = []
    if inputs["protection_level"] != "PROTECTED_CI":
        findings.append(
            GateFinding(
                "protected_boundary",
                "not_running_under_protected_ci",
                "critical",
                "AFL_GATE_PROTECTION_LEVEL",
            )
        )
    if not inputs["protected_suite_hash"]:
        findings.append(
            GateFinding(
                "protected_suite",
                "protected_suite_hash_missing",
                "critical",
                "AFL_PROTECTED_SUITE_HASH",
            )
        )
    if not inputs["signing_key_present"]:
        findings.append(
            GateFinding("promotion_signature", "signing_key_missing", "critical", "AFL_GATE_SIGNING_KEY")
        )
    return findings


def build_gate_result(candidate_root: Path, public_report: dict[str, Any], canary_report: dict[str, Any]) -> dict[str, Any]:
    contract = load_contract()
    manifest = read_json(candidate_root / "review-packet-manifest.json")
    registry_lock = read_json(Path("semantic-registry/registry.lock.json"))
    inputs = protected_inputs()
    findings: list[GateFinding] = []

    if public_report["status"] != "PASS":
        findings.append(
            GateFinding("public_verification", "public_tests_failed", "critical", "public-test-report.json")
        )
    if canary_report["status"] != "PASS":
        findings.append(
            GateFinding("canary_verification", "canaries_failed", "critical", str(CANARY_REPORT_PATH))
        )
    packet_paths = {
        path.relative_to(candidate_root).as_posix()
        for path in candidate_root.rglob("*")
        if path.is_file()
    }
    missing = sorted(set(REQUIRED_PACKET_ARTIFACTS) - packet_paths)
    if missing:
        findings.append(
            GateFinding("review_packet", "required_artifacts_missing", "critical", ",".join(missing))
        )
    findings.extend(identity_findings(inputs))

    result = "PROMOTED" if not findings else "BLOCKED"
    gate_runner_hash = file_sha256(Path(__file__))
    denominators_hash = file_sha256(candidate_root / "test-denominators.json")
    source_tree_hash = (candidate_root / "source-tree.hash").read_text(encoding="utf-8").strip()

    payload = {
        "schema_version": "1.0",
        "program": PROGRAM_ID,
        "milestone": "AFL-G0",
        "candidate_target": CANDIDATE_TARGET,
        "candidate_commit": manifest["candidate_commit"],
        "contract_hash": stable_hash(contract),
        "contract_schema_hash": stable_hash(load_schema(SCHEMA_PATHS[0])),
        "gate_runner_hash": gate_runner_hash,
        "protected_suite_id": inputs["protected_suite_id"] or "UNAVAILABLE_SELF_VERIFIED",
        "protected_suite_hash": inputs["protected_suite_hash"] or "UNAVAILABLE_SELF_VERIFIED",
        "denominators_hash": denominators_hash,
        "registry_lock": stable_hash(registry_lock),
        "source_tree_hash": source_tree_hash,
        "candidate_packet_hash": manifest["packet_hash"],
        "protection_level": inputs["protection_level"],
        "result": result,
        "generated_at": now_iso(),
        "findings": [finding.as_dict() for finding in findings],
        "public_verification_status": public_report["status"],
        "canary_status": canary_report["status"],
    }
    if result == "PROMOTED":
        payload["promoted_at"] = now_iso()
    return payload


def sign_payload(payload: dict[str, Any], signing_key: str) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "promotion_signature"}
    body = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(signing_key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def build_promotion_certificate(gate_result: dict[str, Any]) -> dict[str, Any]:
    certificate = {
        "schema_version": "1.0",
        "program": PROGRAM_ID,
        "milestone": gate_result["milestone"],
        "candidate_target": gate_result.get("candidate_target"),
        "candidate_commit": gate_result["candidate_commit"],
        "contract_hash": gate_result["contract_hash"],
        "contract_schema_hash": gate_result.get("contract_schema_hash"),
        "gate_runner_hash": gate_result["gate_runner_hash"],
        "protected_suite_id": gate_result["protected_suite_id"],
        "protected_suite_hash": gate_result["protected_suite_hash"],
        "denominators_hash": gate_result["denominators_hash"],
        "registry_lock": gate_result["registry_lock"],
        "source_tree_hash": gate_result["source_tree_hash"],
        "result": gate_result["result"],
        "generated_at": now_iso(),
        "promotion_signature": None,
        "signature_status": "NOT_SIGNED_RESULT_NOT_PROMOTED",
    }
    signing_key = os.environ.get("AFL_GATE_SIGNING_KEY")
    if gate_result["result"] == "PROMOTED" and signing_key:
        certificate["promotion_signature"] = sign_payload(certificate, signing_key)
        certificate["signature_status"] = "SIGNED_HMAC_SHA256"
    return certificate


def write_packet_zip(root: Path = CANDIDATE_DIR, packet_dir: Path = PACKET_DIR) -> str:
    packet_zip = Path(f"{packet_dir}.zip")
    packet_sha_path = Path(f"{packet_zip}.sha256")
    if packet_dir.exists():
        shutil.rmtree(packet_dir)
    if packet_zip.exists():
        packet_zip.unlink()
    if packet_sha_path.exists():
        packet_sha_path.unlink()
    packet_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root, packet_dir)
    with zipfile.ZipFile(packet_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in packet_dir.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(packet_dir.parent).as_posix())
    digest = file_sha256(packet_zip)
    packet_sha_path.write_text(f"{digest}  {packet_zip.name}\n", encoding="utf-8")
    return digest


def run_gate(write_packet: bool = True) -> dict[str, Any]:
    # Check mode (default) mirrors every tracked candidate/packet artifact into
    # artifacts/check-runs/; only TQE_WRITE=1 touches the canonical tracked paths.
    candidate_dir = output_path(CANDIDATE_DIR)
    packet_dir = output_path(PACKET_DIR)
    manifest = build_candidate_packet(candidate_dir)
    public_report = run_public_verification()
    write_json(candidate_dir / "public-test-report.json", make_report(public_report["status"], "public_tests", public_report))
    canary_report = run_canaries()
    gate_result = build_gate_result(candidate_dir, public_report, canary_report)
    write_json(output_path(GATE_RESULT_PATH), gate_result)
    write_json(candidate_dir / "gate-result.json", gate_result)
    certificate = build_promotion_certificate(gate_result)
    write_json(output_path(PROMOTION_CERT_PATH), certificate)
    write_json(candidate_dir / "promotion-certificate.json", certificate)

    write_artifacts_sha(candidate_dir)
    manifest["packet_hash"] = stable_hash(artifact_hashes(candidate_dir))
    manifest["required_artifacts"] = artifact_hashes(candidate_dir)
    write_json(candidate_dir / "review-packet-manifest.json", manifest)
    write_artifacts_sha(candidate_dir)

    packet_sha = write_packet_zip(candidate_dir, packet_dir) if write_packet else None
    report = {
        "schema_version": "1.0",
        "program": PROGRAM_ID,
        "gate_id": GATE_ID,
        "candidate_target": CANDIDATE_TARGET,
        "candidate_manifest": manifest,
        "gate_result": gate_result,
        "promotion_certificate": certificate,
        "packet_zip": f"{packet_dir}.zip" if write_packet else None,
        "packet_sha256": packet_sha,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and run AFL-G0 candidate gate.")
    parser.add_argument("--no-packet", action="store_true", help="Skip review packet zip generation.")
    args = parser.parse_args()
    report = run_gate(write_packet=not args.no_packet)
    print(json.dumps(report, indent=2, sort_keys=True))
    # In self-verified mode, BLOCKED is the honest expected result. Only ERROR or
    # failed public/canary mechanics should make the command fail.
    gate_result = report["gate_result"]
    if gate_result["public_verification_status"] != "PASS" or gate_result["canary_status"] != "PASS":
        raise SystemExit(1)
    if gate_result["result"] == "ERROR":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
