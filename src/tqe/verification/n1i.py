"""N1I — Agent AST authoring contract repair gate.

N1H proved the live Hermes path could reach ``submit_query_plan`` but the
submitted draft used plausible, non-registered AST names. N1I repairs the
generated Hermes-safe authoring contract so the model can discover the exact
registered catalog refs, output names, operator names, and node schema.

This gate is local only. The faithful Render rerun remains the origin proof.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.ir import TacticalQueryDocument, stable_hash
from tqe.verification.n1g import n1g_manual_document
from tqe.workshop.knowledge_pack import (
    PACK_JSON_PATH,
    PACK_MD_PATH,
    file_sha256,
    verify_tactical_knowledge_pack,
    write_tactical_knowledge_pack,
)
from tqe.workshop.m1_2 import (
    CAPABILITY_CONTEXT_PATH,
    CallerProfile,
    SubmitQueryPlanRequest,
    ValidateQueryPlanRequest,
    describe_capability,
    list_capabilities,
    submit_query_plan,
    validate_query_plan,
    write_capability_context,
)

N1I_ROOT = Path("artifacts/n1i")
REPORT_PATH = N1I_ROOT / "n1i-verification-report.json"
FAILURE_ANALYSIS_PATH = N1I_ROOT / "n1h-failure-analysis.json"
DELIVERY_FAILURE_ANALYSIS_PATH = Path("delivery/n1d/n1i-n1h-failure-analysis.json")
DELIVERY_REPORT_PATH = Path("delivery/n1d/N1I_REPORT.md")
N1H_ORIGIN_BUNDLE_PATH = Path("delivery/n1d/n1h-origin-bundle.json")

INVALID_N1H_NAMES = {
    "active_ball_possession_anchor",
    "progressive_corridor_availability",
    "ball_enters_corridor_destination_region",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def check(check_id: str, ok: bool, message: str, details: Any | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "pass" if ok else "fail",
        "message": message,
        "details": details if details is not None else {},
    }


def extract_tool_structured_content(content: str) -> dict[str, Any]:
    match = re.search(r"\n\n(\{.*\})\n</untrusted_tool_result>", content, flags=re.DOTALL)
    if not match:
        return {}
    payload = json.loads(match.group(1))
    structured = payload.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    result = payload.get("result")
    if isinstance(result, str) and result.strip().startswith("{"):
        return json.loads(result)
    return {}


def n1h_validation_response() -> dict[str, Any]:
    if not N1H_ORIGIN_BUNDLE_PATH.exists():
        return {}
    bundle = read_json(N1H_ORIGIN_BUNDLE_PATH)
    trace = bundle.get("hermes_origin", {}).get("session_trace", {})
    responses = trace.get("tool_responses") if isinstance(trace, dict) else []
    for response in reversed(responses if isinstance(responses, list) else []):
        if not isinstance(response, dict):
            continue
        if str(response.get("tool_name") or "").removeprefix("functions.") != "mcp_priori_tactical_validate_query_plan":
            continue
        content = response.get("content")
        if isinstance(content, str):
            structured = extract_tool_structured_content(content)
            if structured:
                return structured
        if isinstance(content, dict):
            return content
    return {}


def n1h_failure_analysis() -> dict[str, Any]:
    response = n1h_validation_response()
    issues = response.get("issues") if isinstance(response, dict) else []
    issues = issues if isinstance(issues, list) else []
    mappings = [
        {
            "invalid": "active_ball_possession_anchor",
            "issue_codes": ["unknown_catalog_ref"],
            "mapped_to": "possession_segment",
            "kind": "registered_catalog_ref",
            "reason": "The registered possession anchor primitive is possession_segment; its anchor output is possession_segment.anchors.",
        },
        {
            "invalid": "progressive_corridor_availability",
            "issue_codes": ["unknown_catalog_ref"],
            "mapped_to": "geometric_progressive_corridor_from_anchor_set",
            "kind": "registered_catalog_ref",
            "reason": "The agent-authorable relation over possession anchors is geometric_progressive_corridor_from_anchor_set.",
        },
        {
            "invalid": "ball_enters_corridor_destination_region",
            "issue_codes": ["unknown_operator"],
            "mapped_to": "relation_destination_entry.entry_status + eq PASS",
            "kind": "registered_measurement_plus_operator",
            "reason": "Destination-region entry is a generic measurement node, not a predicate operator.",
        },
        {
            "invalid": "progressive_corridor.candidates",
            "issue_codes": ["unresolved_temporal_reference"],
            "mapped_to": "progressive_corridor.episodes for relation_destination_entry and progressive_corridor.anchor_evaluations for exists",
            "kind": "registered_output_names",
            "reason": "geometric_progressive_corridor_from_anchor_set exposes episodes and anchor_evaluations, not candidates.",
        },
        {
            "invalid": "undeclared invocation threshold parameters",
            "issue_codes": ["unknown_parameter"],
            "mapped_to": "declare recipe.parameters and use ParameterRef, or use inline TypedValue in node.parameters",
            "kind": "schema_contract",
            "reason": "default_invocation.parameters may not contain undeclared recipe parameter names.",
        },
        {
            "invalid": "missing draft_plan.anchor_source",
            "issue_codes": ["missing_anchor_source"],
            "mapped_to": {"source_node_id": "possession", "output_name": "anchors"},
            "kind": "schema_contract",
            "reason": "Generic result emission requires an explicit anchor source.",
        },
    ]
    return {
        "source_bundle": str(N1H_ORIGIN_BUNDLE_PATH),
        "draft_plan_id": response.get("draft_plan_id"),
        "issues": issues,
        "unknown_catalog_refs": [issue for issue in issues if issue.get("code") == "unknown_catalog_ref"],
        "unknown_operators": [issue for issue in issues if issue.get("code") == "unknown_operator"],
        "mappings": mappings,
    }


def model_profile_validation(document: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="n1i-workshop-") as directory:
        output_root = Path(directory)
        submitted = submit_query_plan(
            SubmitQueryPlanRequest(
                plan_document=TacticalQueryDocument.model_validate(document),
                source_label="n1i_visible_contract_manual_ast",
            ),
            output_root=output_root,
            caller_profile=CallerProfile.HERMES_S2I_MCP,
        )
        validation = validate_query_plan(
            ValidateQueryPlanRequest(draft_plan_id=submitted.draft_plan_id),
            output_root=output_root,
            caller_profile=CallerProfile.HERMES_S2I_MCP,
        )
        return {
            "submit": submitted.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
        }


def document_refs_and_operators(document: dict[str, Any]) -> dict[str, list[str]]:
    refs: list[str] = []
    operators: list[str] = []
    outputs: list[str] = []
    for node in document.get("draft_plan", {}).get("nodes", []):
        if isinstance(node, dict) and node.get("catalog_ref"):
            refs.append(str(node["catalog_ref"]))
        if isinstance(node, dict) and isinstance(node.get("operator"), dict):
            operators.append(str(node["operator"].get("name")))
        for ref in [node.get("input") if isinstance(node, dict) else None, *((node.get("inputs") or {}).values() if isinstance(node, dict) else [])]:
            if isinstance(ref, dict):
                outputs.append(str(ref.get("output_name")))
    return {
        "catalog_refs": sorted(set(refs)),
        "operators": sorted(set(operators)),
        "referenced_outputs": sorted(set(outputs)),
    }


def build_report() -> dict[str, Any]:
    N1I_ROOT.mkdir(parents=True, exist_ok=True)
    write_capability_context()
    pack = write_tactical_knowledge_pack(PACK_JSON_PATH, PACK_MD_PATH)
    pack_checks = verify_tactical_knowledge_pack(PACK_JSON_PATH, PACK_MD_PATH)
    failure = n1h_failure_analysis()
    write_json(FAILURE_ANALYSIS_PATH, failure)
    write_json(DELIVERY_FAILURE_ANALYSIS_PATH, failure)

    context = list_capabilities(CallerProfile.HERMES_S2I_MCP).model_dump(mode="json")
    typed_contract = describe_capability("typed_query_plan", CallerProfile.HERMES_S2I_MCP)
    nodes_contract = describe_capability("plan_nodes", CallerProfile.HERMES_S2I_MCP)
    destination_contract = describe_capability(
        "possession_corridor_destination_entry",
        CallerProfile.HERMES_S2I_MCP,
    )
    relation_entry = describe_capability("relation_destination_entry", CallerProfile.HERMES_S2I_MCP)

    document = n1g_manual_document()
    validation = model_profile_validation(document)
    refs = document_refs_and_operators(document)
    authorable_refs = set(nodes_contract["authorable_catalog_refs"])
    contract_operators = set(nodes_contract["operators"])
    destination_text = json.dumps(destination_contract, sort_keys=True)
    authoring_text = json.dumps(context.get("authoring_contracts", {}), sort_keys=True)

    checks = [
        check(
            "n1i.n1h_failure_extracted",
            bool(failure.get("unknown_catalog_refs")) and bool(failure.get("unknown_operators")),
            "N1H unknown catalog refs/operators were extracted from the origin bundle.",
            failure,
        ),
        check(
            "n1i.describe_typed_query_plan_contract",
            typed_contract.get("kind") == "authoring_contract"
            and "draft_catalog_node_schema" in typed_contract
            and "draft_predicate_node_schema" in typed_contract,
            "describe_capability exposes the exact typed query plan node schemas.",
            typed_contract,
        ),
        check(
            "n1i.describe_destination_path_contract",
            destination_contract.get("kind") == "authoring_contract"
            and destination_contract.get("required_catalog_refs")
            == [
                "possession_segment",
                "geometric_progressive_corridor_from_anchor_set",
                "relation_destination_entry",
            ]
            and destination_contract.get("required_operators") == ["exists", "eq"],
            "describe_capability exposes exact valid refs/operators for destination entry composition.",
            destination_contract,
        ),
        check(
            "n1i.relation_destination_entry_contract_complete",
            relation_entry.get("name") == "relation_destination_entry"
            and relation_entry.get("agent_authorable") is True
            and any(output.get("name") == "entry_status" for output in relation_entry.get("outputs", [])),
            "relation_destination_entry describes its input/output contract and entry_status output.",
            relation_entry,
        ),
        check(
            "n1i.trusted_wrapper_absent_from_authorable_nodes",
            "relation_destination_entry_classification" not in authorable_refs
            and "relation_destination_entry_classification" not in nodes_contract.get("catalog_nodes", {}),
            "The trusted wrapper is not present in the generated authorable node set.",
            {
                "authorable_refs": sorted(authorable_refs),
                "trusted_recipe_only_catalog_refs_omitted": nodes_contract.get("trusted_recipe_only_catalog_refs_omitted"),
            },
        ),
        check(
            "n1i.failed_names_not_suggested",
            not any(name in authoring_text for name in INVALID_N1H_NAMES),
            "The generated authoring contracts do not suggest the failed N1H invented names.",
            {"invalid_names": sorted(INVALID_N1H_NAMES)},
        ),
        check(
            "n1i.manual_ast_uses_visible_contract_only",
            set(refs["catalog_refs"]).issubset(authorable_refs)
            and set(refs["operators"]).issubset(contract_operators)
            and "candidates" not in refs["referenced_outputs"],
            "The manually authored model-profile AST uses only visible refs/operators/output names.",
            refs,
        ),
        check(
            "n1i.manual_ast_validates",
            validation["validation"].get("ok") is True,
            "A model-profile manually authored AST using the visible contract validates.",
            validation["validation"],
        ),
        check(
            "n1i.knowledge_pack_checks_pass",
            all(item["ok"] for item in pack_checks),
            "The regenerated tactical knowledge pack passes its safety and consistency checks.",
            {"failed_checks": [item for item in pack_checks if not item["ok"]]},
        ),
    ]
    summary = {"pass": sum(item["status"] == "pass" for item in checks), "fail": sum(item["status"] != "pass" for item in checks)}
    report = {
        "schema_version": "n1i.verification.v1",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "git_head": git_head(),
        "knowledge_pack": {
            "path": str(PACK_JSON_PATH),
            "file_sha256": file_sha256(PACK_JSON_PATH),
            "semantic_sha256": pack["knowledge_pack_sha256"],
        },
        "capability_context": {
            "path": str(CAPABILITY_CONTEXT_PATH),
            "file_sha256": file_sha256(CAPABILITY_CONTEXT_PATH),
        },
        "n1h_failure_analysis_path": str(FAILURE_ANALYSIS_PATH),
        "delivery_failure_analysis_path": str(DELIVERY_FAILURE_ANALYSIS_PATH),
        "n1h_failure_analysis": failure,
        "manual_ast_hash": stable_hash(document),
        "manual_ast_refs_and_operators": refs,
        "model_profile_validation": validation,
        "pack_checks": pack_checks,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    DELIVERY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DELIVERY_REPORT_PATH.write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# N1I — Agent AST Authoring Contract Repair",
        "",
        f"Status: `{report['status']}`",
        f"Generated: `{report['generated_at']}`",
        f"Git head: `{report['git_head']}`",
        "",
        "## N1H Failure Mapping",
        "",
    ]
    for mapping in report["n1h_failure_analysis"]["mappings"]:
        lines.append(f"- `{mapping['invalid']}` -> `{mapping['mapped_to']}` ({mapping['kind']})")
    lines.extend(
        [
            "",
            "## Regenerated Knowledge Pack",
            "",
            f"- Path: `{report['knowledge_pack']['path']}`",
            f"- File SHA-256: `{report['knowledge_pack']['file_sha256']}`",
            f"- Semantic SHA-256: `{report['knowledge_pack']['semantic_sha256']}`",
            "",
            "## Checks",
            "",
        ]
    )
    for item in report["checks"]:
        lines.append(f"- `{item['status']}` {item['id']}: {item['message']}")
    lines.extend(
        [
            "",
            "## Faithful Rerun Status",
            "",
            "Not run by this local gate. The next step is a single faithful deploy-side Hermes rerun using the unchanged scoped hero question. Beta 1C remains blocked unless `n1d1-verify` reaches VERIFIED.",
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
