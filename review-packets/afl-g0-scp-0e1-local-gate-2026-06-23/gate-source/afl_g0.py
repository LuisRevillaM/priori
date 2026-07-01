"""AFL-G0 local contract validation.

This is an interim self-verification gate. It validates the repo-local
operational autonomous-delivery contract, but it is not a protected promotion
boundary because the builder can edit this repository.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CONTRACT_PATH = Path("delivery/autonomous/afl_milestone_contract.yaml")
SCHEMA_PATHS = [
    Path("delivery/autonomous/schemas/afl_milestone_contract.schema.json"),
    Path("delivery/autonomous/schemas/gate_result.schema.json"),
    Path("delivery/autonomous/schemas/review_packet_manifest.schema.json"),
]
REPORT_PATH = Path("artifacts/autonomous/afl-g0-contract-verification-report.json")

RECOGNIZED_TARGET_CLASSES = {
    "HARD_GATE",
    "BOOTSTRAP_TARGET",
    "RELEASE_TARGET",
    "NORTH_STAR_TARGET",
}
REQUIRED_STAGED_TARGETS = {
    "generated_valid_semantic_programs",
    "canonical_football_intents",
    "intents_per_major_family",
}
REQUIRED_REVIEW_PACKET_ARTIFACTS = {
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
}
PROTECTED_AUTHORITY_FIELDS = {
    "protected_milestone_contracts",
    "protected_holdouts",
    "protected_mutations",
    "promotion_policy",
    "trusted_gate",
    "hidden_scoring_policy",
    "signing_key",
}


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    path: str
    severity: str = "critical"

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
        }


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    program = contract.get("program", {})
    if program.get("namespace") != "AFL":
        findings.append(
            Finding("invalid_namespace", "program.namespace must be AFL.", "program.namespace")
        )
    if program.get("protection_level") not in {
        "SELF_VERIFIED",
        "PROTECTED_CI",
        "SIGNED_PROMOTION",
    }:
        findings.append(
            Finding(
                "invalid_protection_level",
                "program.protection_level must be an accepted protection level.",
                "program.protection_level",
            )
        )

    target_classes = set(contract.get("target_classes", []))
    missing_target_classes = RECOGNIZED_TARGET_CLASSES - target_classes
    if missing_target_classes:
        findings.append(
            Finding(
                "missing_target_classes",
                f"Contract omits target classes {sorted(missing_target_classes)}.",
                "target_classes",
            )
        )

    authority = contract.get("authority", {})
    may_modify = set(authority.get("builder_may_modify", []))
    may_not_modify = set(authority.get("builder_may_not_modify", []))
    overlap = sorted(may_modify & may_not_modify)
    if overlap:
        findings.append(
            Finding(
                "authority_overlap",
                f"Builder-owned and protected fields overlap: {overlap}.",
                "authority",
            )
        )
    missing_protected = sorted(PROTECTED_AUTHORITY_FIELDS - may_not_modify)
    if missing_protected:
        findings.append(
            Finding(
                "missing_protected_authority_fields",
                f"Protected authority fields missing: {missing_protected}.",
                "authority.builder_may_not_modify",
            )
        )
    if authority.get("promotion_authority") != "protected_gate":
        findings.append(
            Finding(
                "invalid_promotion_authority",
                "promotion_authority must be protected_gate.",
                "authority.promotion_authority",
            )
        )

    findings.extend(validate_global_hard_gates(contract.get("global_hard_gates", [])))
    findings.extend(validate_staged_targets(contract.get("staged_targets", {})))
    findings.extend(validate_milestones(contract.get("milestones", [])))
    findings.extend(validate_promotion_policy(contract.get("promotion_policy", {})))
    findings.extend(validate_review_packet(contract.get("review_packet", {})))
    return findings


def validate_global_hard_gates(gates: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for index, gate in enumerate(gates):
        path = f"global_hard_gates[{index}]"
        metric = gate.get("metric")
        if not metric:
            findings.append(Finding("hard_gate_missing_metric", "Hard gate omits metric.", path))
        elif metric in seen:
            findings.append(
                Finding("duplicate_hard_gate", f"Duplicate hard gate {metric}.", path)
            )
        seen.add(str(metric))
        if gate.get("target_class") != "HARD_GATE":
            findings.append(
                Finding(
                    "hard_gate_wrong_target_class",
                    f"{metric} must use HARD_GATE target_class.",
                    f"{path}.target_class",
                )
            )
        if gate.get("threshold") != 0:
            findings.append(
                Finding(
                    "hard_gate_nonzero_threshold",
                    f"{metric} hard gate must have threshold 0.",
                    f"{path}.threshold",
                )
            )
        if gate.get("waivable") is not False:
            findings.append(
                Finding(
                    "hard_gate_waivable",
                    f"{metric} hard gate must not be waivable.",
                    f"{path}.waivable",
                )
            )
    return findings


def validate_staged_targets(targets: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    missing = sorted(REQUIRED_STAGED_TARGETS - set(targets))
    if missing:
        findings.append(
            Finding(
                "missing_staged_targets",
                f"Required staged targets missing: {missing}.",
                "staged_targets",
            )
        )
    for name, values in targets.items():
        for key in ("bootstrap", "release", "north_star"):
            if key not in values:
                findings.append(
                    Finding(
                        "staged_target_missing_stage",
                        f"{name} omits {key} target.",
                        f"staged_targets.{name}.{key}",
                    )
                )
        if all(key in values for key in ("bootstrap", "release", "north_star")):
            if not (values["bootstrap"] <= values["release"] <= values["north_star"]):
                findings.append(
                    Finding(
                        "staged_target_not_monotonic",
                        f"{name} targets must be bootstrap <= release <= north_star.",
                        f"staged_targets.{name}",
                    )
                )
    return findings


def validate_milestones(milestones: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    ids = [item.get("id") for item in milestones]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    for milestone_id in duplicates:
        findings.append(
            Finding("duplicate_milestone_id", f"Duplicate milestone id {milestone_id}.", "milestones")
        )
    id_set = {str(item) for item in ids if item}

    for index, milestone in enumerate(milestones):
        milestone_id = str(milestone.get("id", ""))
        path = f"milestones[{index}]"
        if not (milestone_id == "AFL-G0" or milestone_id.startswith("AFL-")):
            findings.append(
                Finding(
                    "legacy_or_invalid_milestone_id",
                    f"Milestone id must use AFL namespace, got {milestone_id}.",
                    f"{path}.id",
                )
            )
        if milestone_id.startswith("M") and milestone_id[1:].isdigit():
            findings.append(
                Finding(
                    "legacy_milestone_id",
                    f"Legacy milestone id {milestone_id} is forbidden.",
                    f"{path}.id",
                )
            )
        depends_on = milestone.get("depends_on", [])
        if milestone_id != "AFL-G0" and not depends_on:
            findings.append(
                Finding(
                    "milestone_missing_dependency",
                    f"{milestone_id} must depend on at least one prior milestone.",
                    f"{path}.depends_on",
                )
            )
        for dep in depends_on:
            if dep not in id_set:
                findings.append(
                    Finding(
                        "unknown_milestone_dependency",
                        f"{milestone_id} depends on unknown milestone {dep}.",
                        f"{path}.depends_on",
                    )
                )
        for target_index, target in enumerate(milestone.get("quantitative_targets", [])):
            findings.extend(
                validate_quantitative_target(
                    target,
                    f"{path}.quantitative_targets[{target_index}]",
                )
            )

    findings.extend(validate_acyclic_dependencies(milestones))
    return findings


def validate_quantitative_target(target: dict[str, Any], path: str) -> list[Finding]:
    findings: list[Finding] = []
    for key in ("metric", "threshold", "target_class", "numerator", "denominator", "evaluation_split"):
        if key not in target:
            findings.append(
                Finding(
                    "quantitative_target_missing_field",
                    f"Quantitative target omits {key}.",
                    f"{path}.{key}",
                )
            )
    target_class = target.get("target_class")
    if target_class not in RECOGNIZED_TARGET_CLASSES:
        findings.append(
            Finding(
                "unknown_target_class",
                f"Unknown target class {target_class}.",
                f"{path}.target_class",
            )
        )
    if target_class == "HARD_GATE" and target.get("threshold") not in {0, 1.0}:
        findings.append(
            Finding(
                "hard_gate_target_unusual_threshold",
                "HARD_GATE quantitative target should use threshold 0 or 1.0.",
                f"{path}.threshold",
                severity="high",
            )
        )
    return findings


def validate_acyclic_dependencies(milestones: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    graph = {item["id"]: list(item.get("depends_on", [])) for item in milestones if "id" in item}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, stack: list[str]) -> None:
        if node in visiting:
            findings.append(
                Finding(
                    "milestone_dependency_cycle",
                    f"Dependency cycle detected: {' -> '.join(stack + [node])}.",
                    "milestones",
                )
            )
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            if dep in graph:
                visit(dep, stack + [node])
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])
    return findings


def validate_promotion_policy(policy: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if policy.get("result_authority") != "protected_gate_only":
        findings.append(
            Finding(
                "invalid_result_authority",
                "promotion_policy.result_authority must be protected_gate_only.",
                "promotion_policy.result_authority",
            )
        )
    if policy.get("cumulative_gate_required") is not True:
        findings.append(
            Finding(
                "cumulative_gate_not_required",
                "promotion_policy.cumulative_gate_required must be true.",
                "promotion_policy.cumulative_gate_required",
            )
        )
    if policy.get("signed_certificate_required_for_protected_promotion") is not True:
        findings.append(
            Finding(
                "signed_certificate_not_required",
                "Protected promotion must require a signed certificate.",
                "promotion_policy.signed_certificate_required_for_protected_promotion",
            )
        )
    return findings


def validate_review_packet(packet: dict[str, Any]) -> list[Finding]:
    required = set(packet.get("required", []))
    missing = sorted(REQUIRED_REVIEW_PACKET_ARTIFACTS - required)
    if missing:
        return [
            Finding(
                "review_packet_missing_required_artifacts",
                f"Review packet omits required artifacts {missing}.",
                "review_packet.required",
            )
        ]
    return []


def build_report(contract: dict[str, Any], findings: list[Finding]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "gate_id": "AFL-G0.local_contract_validator",
        "protection_level": "SELF_VERIFIED",
        "status": "PASS" if not findings else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_hash": stable_hash(contract),
        "schema_paths": [str(path) for path in SCHEMA_PATHS],
        "schema_hashes": {
            str(path): stable_hash(load_schema(path)) for path in SCHEMA_PATHS
        },
        "milestone_count": len(contract.get("milestones", [])),
        "findings": [finding.as_dict() for finding in findings],
        "limitations": [
            "This is repo-local self-verification, not a protected CI boundary.",
            "No hidden holdout, protected mutation, signing key, or external promotion identity is active yet.",
        ],
    }


def run(write: bool = True) -> dict[str, Any]:
    contract = load_contract()
    # Copy to ensure validation never mutates the loaded contract.
    findings = validate_contract(copy.deepcopy(contract))
    report = build_report(contract, findings)
    if write:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run(write=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
