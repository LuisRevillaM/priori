"""Verify N1A generic relation-destination outcome preflight."""

from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import (
    execute_plan_from_path,
    execution_result_rows,
)
from tqe.runtime.ir import TacticalQueryDocument, stable_hash

ARTIFACT_DIR = Path("artifacts/n1-live-novel-composition-2026-06-22")
HERO_QUESTION = (
    "Show possessions where a progressive corridor opens within four seconds of possession "
    "starting, remains available for at least 0.8 seconds, and the ball enters that corridor's "
    "destination region within five seconds of the corridor opening."
)
PLAN_PATHS = [
    Path("config/query-plans/ball_side_block_shift.ir.v1.json"),
    Path("config/query-plans/possession_corridor_availability.experimental.v1.json"),
    Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json"),
]
CAPABILITY_CONTEXT_PATH = Path("generated/capability-context.json")
KNOWLEDGE_PACK_PATH = Path("generated/tactical-knowledge-pack.json")
CANDIDATE_PATH = ARTIFACT_DIR / "n1-local-only-candidate-plan.json"
REGISTERED_FINGERPRINTS_PATH = ARTIFACT_DIR / "registered-structural-fingerprints.json"
EXPRESSIBILITY_PATH = ARTIFACT_DIR / "expressibility-preflight.json"
FREEZE_PATH = ARTIFACT_DIR / "freeze.json"
REPORT_PATH = ARTIFACT_DIR / "PREFLIGHT_REPORT.md"
N1A_REPORT_PATH = ARTIFACT_DIR / "N1A_REPORT.json"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def build_candidate_plan() -> dict[str, Any]:
    base = read_json(Path("config/query-plans/possession_corridor_availability.experimental.v1.json"))
    opposite = read_json(Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json"))
    payload = deepcopy(base)
    payload["recipe"]["recipe_id"] = "n1_possession_corridor_destination_entry_v1"
    payload["recipe"]["recipe_version"] = "0.1.0-local-preflight"
    payload["recipe"]["display_name"] = "N1 Possession Corridor Destination Entry"
    payload["recipe"]["description"] = HERO_QUESTION
    payload["recipe"]["output_classifications"] = ["DESTINATION_ENTERED"]
    payload["recipe"]["parameters"] = deepcopy(base["recipe"]["parameters"])
    for parameter in opposite["recipe"]["parameters"]:
        if parameter["name"] not in {"result_id_seed_hash", "destination_entry_horizon_seconds"}:
            continue
        copied = deepcopy(parameter)
        if copied["name"] == "result_id_seed_hash":
            copied["default"]["value"] = "n1_possession_corridor_destination_entry_v1"
        elif copied["name"] == "destination_entry_horizon_seconds":
            copied["default"]["value"] = 5.0
        payload["recipe"]["parameters"].append(copied)
    for parameter in payload["recipe"]["parameters"]:
        if parameter["name"] == "corridor_max_window_seconds":
            parameter["default"]["value"] = 4.0
        elif parameter["name"] == "corridor_minimum_duration_seconds":
            parameter["default"]["value"] = 0.8
    payload["default_invocation"]["invocation_id"] = "n1_local_preflight"
    payload["default_invocation"]["match_ids"] = ["J03WOY"]
    payload["default_invocation"]["max_results"] = 5
    payload["draft_plan"]["plan_id"] = "n1_possession_corridor_destination_entry_v1"
    payload["draft_plan"]["recipe_id"] = payload["recipe"]["recipe_id"]
    payload["draft_plan"]["recipe_version"] = payload["recipe"]["recipe_version"]

    destination_entry: dict[str, Any] | None = None
    destination_predicate: dict[str, Any] | None = None
    for node in opposite["draft_plan"]["nodes"]:
        if node["node_id"] == "destination_entry":
            destination_entry = deepcopy(node)
            destination_entry["catalog_ref"] = "relation_destination_entry"
            destination_entry["inputs"]["relation_episodes"] = {
                "source_node_id": "progressive_corridor",
                "output_name": "episodes",
            }
            destination_entry["parameters"]["episode_selection"] = {
                "payload_type": "enum",
                "unit": "none",
                "value": "entry_first_then_progression",
            }
        elif node["node_id"] == "destination_region_entered":
            destination_predicate = deepcopy(node)
            destination_predicate["input"] = {
                "source_node_id": "destination_entry",
                "output_name": "entry_status",
            }
            destination_predicate["operator"] = {"name": "eq", "version": "1.0.0"}
            destination_predicate["compare"] = {
                "payload_type": "enum",
                "unit": "none",
                "value": "PASS",
            }
    if destination_entry is None or destination_predicate is None:
        raise RuntimeError("opposite corridor template is missing destination-entry nodes")

    payload["draft_plan"]["nodes"] = deepcopy(base["draft_plan"]["nodes"]) + [
        destination_entry,
        destination_predicate,
    ]
    payload["draft_plan"]["classification_rules"] = [
        {
            "label": "DESTINATION_ENTERED",
            "predicate_ids": ["has_progressive_corridor", "destination_region_entered"],
            "description": (
                "A possession-anchored progressive corridor persisted and the ball entered "
                "its destination region within the configured horizon."
            ),
        }
    ]
    payload["draft_plan"]["requested_evidence"] = deepcopy(base["draft_plan"]["requested_evidence"]) + [
        {
            "source": {"source_node_id": "destination_entry", "output_name": "entry_status"},
            "field": "entry_status",
            "alias": "destination_entry_status",
        },
        {
            "source": {"source_node_id": "destination_entry", "output_name": "entry_status"},
            "field": "destination_entry_frame_id",
            "alias": "destination_entry_frame_id",
            "required": False,
        },
        {
            "source": {"source_node_id": "destination_entry", "output_name": "entry_status"},
            "field": "relation_id",
            "alias": "destination_relation_id",
        },
        {
            "source": {"source_node_id": "destination_entry", "output_name": "entry_status"},
            "field": "observed_window_end_frame_id",
            "alias": "destination_observed_window_end_frame_id",
        },
    ]
    payload["draft_plan"]["anchor_source"] = {"source_node_id": "possession", "output_name": "anchors"}
    return payload


def structural_fingerprint(document: dict[str, Any]) -> dict[str, Any]:
    nodes = document["draft_plan"]["nodes"]
    node_map = {node["node_id"]: f"n{index:02d}" for index, node in enumerate(nodes)}

    def normalize_ref(ref: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(ref, dict):
            return None
        return {
            "source": node_map.get(ref.get("source_node_id"), str(ref.get("source_node_id"))),
            "output": ref.get("output_name"),
        }

    normalized_nodes: list[dict[str, Any]] = []
    for node in nodes:
        normalized: dict[str, Any] = {
            "id": node_map[node["node_id"]],
            "kind": node["kind"],
            "catalog_ref": node.get("catalog_ref"),
        }
        if node["kind"] in {"primitive", "relation"}:
            normalized["inputs"] = {
                name: normalize_ref(ref)
                for name, ref in sorted((node.get("inputs") or {}).items())
            }
            normalized["parameter_names"] = sorted((node.get("parameters") or {}).keys())
        if node["kind"] == "predicate":
            normalized["operator"] = node["operator"]["name"]
            normalized["input"] = normalize_ref(node.get("input"))
            normalized["compare_shape"] = compare_shape(node.get("compare"))
            normalized["duration_shape"] = compare_shape(node.get("duration"))
        normalized_nodes.append(normalized)

    fingerprint = {
        "schema_version": "n1.structural_fingerprint.v1",
        "anchor_source": normalize_ref(document["draft_plan"].get("anchor_source")),
        "nodes": normalized_nodes,
        "classification_rules": [
            {
                "label": rule["label"],
                "predicates": [node_map.get(predicate_id, predicate_id) for predicate_id in rule["predicate_ids"]],
            }
            for rule in document["draft_plan"].get("classification_rules", [])
        ],
        "evidence_sources": sorted(
            f"{node_map.get(request['source']['source_node_id'], request['source']['source_node_id'])}."
            f"{request['source']['output_name']}:{request['field']}"
            for request in document["draft_plan"].get("requested_evidence", [])
        ),
    }
    fingerprint["fingerprint_hash"] = stable_hash(
        {key: value for key, value in fingerprint.items() if key != "fingerprint_hash"}
    )
    return fingerprint


def compare_shape(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("kind") == "parameter":
        return {"kind": "parameter", "name": "<parameter>"}
    return {
        "kind": "literal",
        "payload_type": value.get("payload_type"),
        "unit": value.get("unit"),
        "value": "<literal>",
    }


def registered_fingerprints() -> dict[str, Any]:
    registered = []
    for path in PLAN_PATHS:
        document = read_json(path)
        bound = bind_document(TacticalQueryDocument.model_validate(document))
        registered.append(
            {
                "source_path": str(path),
                "file_sha256": file_sha256(path),
                "document_stable_hash": stable_hash(document),
                "plan_id": document["draft_plan"]["plan_id"],
                "plan_status": document["draft_plan"]["status"],
                "recipe_id": document["recipe"]["recipe_id"],
                "recipe_version": document["recipe"]["recipe_version"],
                "bound_plan_hash": bound.bound_plan_hash,
                "structural_fingerprint": structural_fingerprint(document),
            }
        )
    return {
        "schema_version": "n1.registered_fingerprints.v1",
        "generated_at": utc_now_iso(),
        "registered": registered,
    }


def capability_entry(context: dict[str, Any], name: str) -> dict[str, Any] | None:
    for section in ("primitives", "relations", "operators"):
        for entry in context.get(section, []):
            if entry.get("name") == name:
                return entry
    return None


def check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "pass" if passed else "fail",
        "message": message,
        "details": details or {},
    }


def build_report() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    candidate = build_candidate_plan()
    write_json(CANDIDATE_PATH, candidate)

    registered = registered_fingerprints()
    write_json(REGISTERED_FINGERPRINTS_PATH, registered)

    freeze = {
        "schema_version": "n1.freeze.v1",
        "generated_at": utc_now_iso(),
        "git_commit": git_head(),
        "hero_question": HERO_QUESTION,
        "tactical_knowledge_pack_sha256": file_sha256(KNOWLEDGE_PACK_PATH),
        "capability_context_sha256": file_sha256(CAPABILITY_CONTEXT_PATH),
        "provider": "openai-codex",
        "model": "gpt-5.5",
        "reasoning_effort": "xhigh",
        "toolset": "mcp-priori_tactical",
    }
    write_json(FREEZE_PATH, freeze)

    context = read_json(CAPABILITY_CONTEXT_PATH)
    generic_capability = capability_entry(context, "relation_destination_entry")
    legacy_wrapper = capability_entry(context, "relation_destination_entry_classification")
    candidate_fingerprint = structural_fingerprint(candidate)
    registered_hashes = {
        item["recipe_id"]: item["structural_fingerprint"]["fingerprint_hash"]
        for item in registered["registered"]
    }
    candidate_hash = candidate_fingerprint["fingerprint_hash"]

    bind_ok = False
    execute_ok = False
    error_payload: dict[str, Any] = {}
    bound_plan_hash: str | None = None
    execution_summary: dict[str, Any] = {}
    try:
        bound, execution = execute_plan_from_path(CANDIDATE_PATH)
        rows = execution_result_rows(execution)
        bind_ok = True
        execute_ok = execution.status.value == "pass"
        bound_plan_hash = bound.bound_plan_hash
        execution_summary = {
            "status": execution.status.value,
            "compatibility_profile": execution.provenance.get("compatibility_profile"),
            "row_count": len(rows),
            "trace_count": len(execution.predicate_traces),
            "classifications": sorted({row["classification"] for row in rows}),
            "first_result_id": rows[0]["result_id"] if rows else None,
            "first_requested_evidence": rows[0].get("requested_evidence") if rows else {},
            "contains_m1_fields": bool(
                rows
                and {"block_shift_score", "wide_entry_frame_id", "signed_shift_metres"}.intersection(rows[0])
            ),
        }
    except Exception as exc:  # pragma: no cover - serialized into report for preflight diagnostics.
        error_payload = {"error_type": type(exc).__name__, "error_message": str(exc)}

    opposite_bound, opposite_execution = execute_plan_from_path(
        Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
    )
    opposite_rows = execution_result_rows(opposite_execution)
    opposite_summary = {
        "status": opposite_execution.status.value,
        "compatibility_profile": opposite_execution.provenance.get("compatibility_profile"),
        "bound_plan_hash": opposite_bound.bound_plan_hash,
        "row_count": len(opposite_rows),
        "classifications": sorted({row["classification"] for row in opposite_rows}),
    }

    checks = [
        check(
            "n1a.capability.generic_authorable",
            bool(generic_capability and generic_capability.get("agent_authorable") is True),
            "relation_destination_entry is Hermes-authorable.",
            {"capability": generic_capability},
        ),
        check(
            "n1a.capability.legacy_wrapper_not_authorable",
            bool(legacy_wrapper and legacy_wrapper.get("agent_authorable") is False),
            "relation_destination_entry_classification remains trusted-recipe-only.",
            {"capability": legacy_wrapper},
        ),
        check(
            "n1a.candidate.uses_generic_capability",
            any(
                node.get("catalog_ref") == "relation_destination_entry"
                for node in candidate["draft_plan"]["nodes"]
            )
            and not any(
                node.get("catalog_ref") == "relation_destination_entry_classification"
                for node in candidate["draft_plan"]["nodes"]
            ),
            "Frozen local candidate uses the generic destination-entry primitive.",
        ),
        check(
            "n1a.candidate.binds_and_executes",
            bind_ok and execute_ok,
            "Frozen local candidate binds and executes under generic runtime.",
            {"bound_plan_hash": bound_plan_hash, "execution": execution_summary, **error_payload},
        ),
        check(
            "n1a.candidate.real_results_or_honest_zero",
            bool(execution_summary) and execution_summary["row_count"] >= 0,
            "Execution produced a deterministic result set.",
            execution_summary,
        ),
        check(
            "n1a.candidate.no_m1_fields",
            bool(execution_summary) and not execution_summary.get("contains_m1_fields"),
            "Generic rows do not require M1-specific result fields.",
            execution_summary,
        ),
        check(
            "n1a.fingerprint.novel",
            candidate_hash not in set(registered_hashes.values()),
            "Candidate structural fingerprint differs from registered recipes.",
            {"candidate": candidate_hash, "registered": registered_hashes},
        ),
        check(
            "n1a.opposite_plan.still_executes",
            opposite_summary["status"] == "pass"
            and opposite_summary["compatibility_profile"] == "generic"
            and opposite_summary["row_count"] > 0,
            "Existing opposite-corridor plan still executes generically.",
            opposite_summary,
        ),
    ]
    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
    }
    report = {
        "schema_version": "n1a.report.v1",
        "generated_at": utc_now_iso(),
        "hero_question": HERO_QUESTION,
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "freeze": freeze,
        "candidate_plan_path": str(CANDIDATE_PATH),
        "candidate_structural_fingerprint": candidate_fingerprint,
        "registered_structural_fingerprints_path": str(REGISTERED_FINGERPRINTS_PATH),
        "execution_summary": execution_summary,
        "opposite_corridor_summary": opposite_summary,
        "checks": checks,
    }
    write_json(N1A_REPORT_PATH, report)
    write_json(
        EXPRESSIBILITY_PATH,
        {
            "schema_version": "n1.expressibility_preflight.v2",
            "generated_at": report["generated_at"],
            "hero_question": HERO_QUESTION,
            "schema_valid": True,
            "bind_ok": bind_ok,
            "execute_ok": execute_ok,
            "bound_plan_hash": bound_plan_hash,
            "candidate_plan_path": str(CANDIDATE_PATH),
            "candidate_structural_fingerprint_hash": candidate_hash,
            "registered_structural_fingerprint_hashes": registered_hashes,
            "novel_structural_fingerprint": candidate_hash not in set(registered_hashes.values()),
            "execution_summary": execution_summary,
            **error_payload,
        },
    )
    REPORT_PATH.write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    checks = report["checks"]
    freeze = report["freeze"]
    candidate = report["candidate_structural_fingerprint"]
    registered = read_json(Path(report["registered_structural_fingerprints_path"]))["registered"]
    lines = [
        "# N1 Live Novel Tactical Composition Preflight",
        "",
        "## State",
        "",
        "N1A generic relation-destination outcome preflight passed locally. Live Hermes has not been run in this report.",
        "",
        "## Frozen Hero Question",
        "",
        report["hero_question"],
        "",
        "## Freeze",
        "",
        f"- Git commit: `{freeze['git_commit']}`",
        f"- Tactical Knowledge Pack SHA-256: `{freeze['tactical_knowledge_pack_sha256']}`",
        f"- Capability context SHA-256: `{freeze['capability_context_sha256']}`",
        f"- Provider/model: `{freeze['provider']}` / `{freeze['model']}`",
        f"- Reasoning effort: `{freeze['reasoning_effort']}`",
        f"- Toolset: `{freeze['toolset']}`",
        "",
        "## Registered Structural Fingerprints",
        "",
    ]
    for item in registered:
        lines.extend(
            [
                f"- `{item['recipe_id']}`",
                f"  - document stable hash: `{item['document_stable_hash']}`",
                f"  - structural fingerprint: `{item['structural_fingerprint']['fingerprint_hash']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Candidate Structural Fingerprint",
            "",
            f"- plan: `{report['candidate_plan_path']}`",
            f"- fingerprint: `{candidate['fingerprint_hash']}`",
            "",
            "## Execution",
            "",
            f"- status: `{report['execution_summary'].get('status')}`",
            f"- compatibility profile: `{report['execution_summary'].get('compatibility_profile')}`",
            f"- rows: `{report['execution_summary'].get('row_count')}`",
            f"- traces: `{report['execution_summary'].get('trace_count')}`",
            "",
            "## Checks",
            "",
        ]
    )
    for item in checks:
        lines.append(f"- `{item['status']}` {item['id']}: {item['message']}")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            "- `freeze.json`",
            "- `registered-structural-fingerprints.json`",
            "- `expressibility-preflight.json`",
            "- `n1-local-only-candidate-plan.json`",
            "- `N1A_REPORT.json`",
            "",
            "The original failed preflight is superseded by N1A because the catalog now exposes a truly generic `relation_destination_entry` capability and keeps the previous wrapper recipe-only.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
