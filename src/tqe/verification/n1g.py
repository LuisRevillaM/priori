"""N1G — agent-authorable destination-entry capability gate.

N1F proved the live origin path was faithful but blocked because Hermes copied the
trusted ``relation_destination_entry_classification`` wrapper into a possession-start
corridor draft. N1G keeps that wrapper trusted-only and proves the generic path is
authorable:

possession anchors -> progressive corridor relation episodes
-> relation_destination_entry.entry_status -> eq PASS -> result evidence.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import TacticalQueryDocument, stable_hash
from tqe.verification.n1a import build_candidate_plan
from tqe.verification.n1c import check, relation_destination_entry_tri_state_fixture
from tqe.verification.n1d import ENTRY_MODE_EVIDENCE
from tqe.workshop.knowledge_pack import (
    PACK_JSON_PATH,
    PACK_MD_PATH,
    build_tactical_knowledge_pack,
    verify_tactical_knowledge_pack,
    write_tactical_knowledge_pack,
)
from tqe.workshop.knowledge_pack import render_markdown as render_knowledge_pack_markdown
from tqe.write_mode import diff_against_checked_in, serialize_json_artifact, write_mode
from tqe.workshop.m1_2 import (
    CallerProfile,
    CapabilityGap,
    SubmitQueryPlanRequest,
    ValidateQueryPlanRequest,
    describe_capability,
    list_capabilities,
    submit_query_plan,
    validate_query_plan,
    write_capability_context,
    write_json,
)

N1G_ROOT = Path("artifacts/n1g")
WORKSHOP_ROOT = N1G_ROOT / "workshop"
REPORT_PATH = N1G_ROOT / "n1g-verification-report.json"
MANUAL_PLAN_PATH = N1G_ROOT / "n1g-manual-possession-destination-entry-plan.json"
DELIVERY_REPORT_PATH = Path("delivery/n1d/N1G_REPORT.md")
N1F_BUNDLE_PATH = Path("delivery/n1d/n1f-origin-bundle.json")
TRUSTED_WRAPPER = "relation_destination_entry_classification"
GENERIC_ENTRY = "relation_destination_entry"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add_entry_mode_evidence(document: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(document)
    requested = updated["draft_plan"].setdefault("requested_evidence", [])
    aliases = {str(item.get("alias")) for item in requested if isinstance(item, dict)}
    for evidence in ENTRY_MODE_EVIDENCE:
        if str(evidence["alias"]) not in aliases:
            requested.append(deepcopy(evidence))
    return updated


def n1g_manual_document() -> dict[str, Any]:
    document = add_entry_mode_evidence(build_candidate_plan())
    document["recipe"]["recipe_id"] = "n1g_possession_corridor_destination_entry_v1"
    document["recipe"]["recipe_version"] = "0.1.0-local-proof"
    document["recipe"]["display_name"] = "N1G Possession Corridor Destination Entry"
    document["draft_plan"]["plan_id"] = "n1g_possession_corridor_destination_entry_v1"
    document["draft_plan"]["recipe_id"] = document["recipe"]["recipe_id"]
    document["draft_plan"]["recipe_version"] = document["recipe"]["recipe_version"]
    document["default_invocation"]["invocation_id"] = "n1g_local_proof"
    document["default_invocation"]["match_ids"] = ["J03WOY"]
    document["default_invocation"]["periods"] = ["firstHalf"]
    document["default_invocation"]["perspective_team_role"] = "home"
    document["default_invocation"]["max_results"] = 25
    return document


def trusted_wrapper_document_from(document: dict[str, Any]) -> dict[str, Any]:
    """Return a same-shape invalid draft using the trusted wrapper path."""

    updated = deepcopy(document)
    for node in updated["draft_plan"]["nodes"]:
        if node.get("node_id") == "destination_entry":
            node["catalog_ref"] = TRUSTED_WRAPPER
            node.setdefault("parameters", {})["episode_selection"] = {
                "payload_type": "enum",
                "unit": "none",
                "value": "first_by_duration_clearance",
            }
        elif node.get("node_id") == "destination_region_entered":
            node["input"] = {"source_node_id": "destination_entry", "output_name": "classification"}
            node["operator"] = {"name": "neq", "version": "1.0.0"}
            node["compare"] = {
                "payload_type": "enum",
                "unit": "none",
                "value": "CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY",
            }
    updated["draft_plan"]["requested_evidence"] = [
        request
        for request in updated["draft_plan"].get("requested_evidence", [])
        if not str(request.get("alias", "")).startswith("destination_")
    ]
    updated["draft_plan"]["requested_evidence"].extend(
        [
            {
                "source": {"source_node_id": "destination_entry", "output_name": "classification"},
                "field": "classification",
                "alias": "destination_classification",
            },
            {
                "source": {"source_node_id": "destination_entry", "output_name": "classification"},
                "field": "destination_entry_frame_id",
                "alias": "destination_entry_frame_id",
                "required": False,
            },
        ]
    )
    return updated


def model_validate_document(document: dict[str, Any]) -> dict[str, Any]:
    submitted = submit_query_plan(
        SubmitQueryPlanRequest(
            plan_document=TacticalQueryDocument.model_validate(document),
            source_label="n1g_local_model_boundary",
        ),
        output_root=WORKSHOP_ROOT,
        caller_profile=CallerProfile.HERMES_S2I_MCP,
    )
    validation = validate_query_plan(
        ValidateQueryPlanRequest(draft_plan_id=submitted.draft_plan_id),
        output_root=WORKSHOP_ROOT,
        caller_profile=CallerProfile.HERMES_S2I_MCP,
    )
    return {
        "submit": submitted.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
    }


def execute_manual_document(document: dict[str, Any]) -> dict[str, Any]:
    bound = bind_document(TacticalQueryDocument.model_validate(document))
    execution = TacticalQueryExecutor().execute(bound)
    rows = execution_result_rows(execution)
    first_evidence = rows[0].get("requested_evidence", {}) if rows else {}
    relation_witness_mismatches = [
        {
            "result_id": str(row.get("result_id")),
            "relation_id": row.get("requested_evidence", {}).get("relation_id"),
            "destination_relation_id": row.get("requested_evidence", {}).get("destination_relation_id"),
        }
        for row in rows
        if row.get("requested_evidence", {}).get("relation_id")
        != row.get("requested_evidence", {}).get("destination_relation_id")
    ]
    return {
        "bound_plan_hash": bound.bound_plan_hash,
        "execution_status": execution.status.value,
        "compatibility_profile": execution.provenance.get("compatibility_profile"),
        "row_count": len(rows),
        "classifications": sorted({str(row["classification"]) for row in rows}),
        "first_result_id": str(rows[0]["result_id"]) if rows else None,
        "first_requested_evidence": first_evidence,
        "entry_statuses": sorted(
            {str(row.get("requested_evidence", {}).get("destination_entry_status")) for row in rows}
        ),
        "entry_modes": sorted(
            {
                str(row.get("requested_evidence", {}).get("destination_entry_mode"))
                for row in rows
                if row.get("requested_evidence", {}).get("destination_entry_mode") is not None
            }
        ),
        "has_entry_mode_evidence": bool(rows)
        and all("destination_entry_mode" in (row.get("requested_evidence", {}) or {}) for row in rows),
        "has_time_to_entry_evidence": bool(rows)
        and all(
            "destination_time_to_entry_seconds" in (row.get("requested_evidence", {}) or {})
            for row in rows
        ),
        "relation_witness_mismatches": relation_witness_mismatches,
    }


def capability_contract() -> dict[str, Any]:
    context = list_capabilities(CallerProfile.HERMES_S2I_MCP).model_dump(mode="json")
    primitives = {item["name"]: item for item in context["primitives"]}
    recipe_contract = describe_capability(
        "opposite_corridor_after_shift_v1",
        CallerProfile.HERMES_S2I_MCP,
    )["authoring_contract"]
    authorable_refs = {
        str(node.get("catalog_ref"))
        for node in recipe_contract.get("authorable_nodes", [])
        if node.get("catalog_ref")
    }
    return {
        "generic_entry": primitives.get(GENERIC_ENTRY, {}),
        "trusted_wrapper": primitives.get(TRUSTED_WRAPPER, {}),
        "safe_composition_rule": context["safe_operator_source_rules"].get(
            "possession_corridor_destination_entry"
        ),
        "opposite_recipe_authorable_refs": sorted(authorable_refs),
        "opposite_recipe_omitted_refs": recipe_contract.get("trusted_recipe_only_catalog_refs_omitted", []),
        "opposite_recipe_safe_hints": recipe_contract.get("safe_generic_composition_hints", {}),
    }


def original_n1f_failure_summary() -> dict[str, Any]:
    if not N1F_BUNDLE_PATH.exists():
        return {"present": False}
    bundle = read_json(N1F_BUNDLE_PATH)
    hermes = bundle.get("hermes_origin") if isinstance(bundle.get("hermes_origin"), dict) else {}
    draft = hermes.get("draft_document") if isinstance(hermes.get("draft_document"), dict) else {}
    refs = [
        str(node.get("catalog_ref"))
        for node in draft.get("draft_plan", {}).get("nodes", [])
        if node.get("catalog_ref")
    ]
    return {
        "present": True,
        "status": bundle.get("status"),
        "blocking_reason": bundle.get("blocking_reason"),
        "draft_plan_id": hermes.get("draft_plan_id"),
        "draft_plan_hash": hermes.get("draft_plan_hash"),
        "draft_catalog_refs": refs,
        "used_trusted_wrapper": TRUSTED_WRAPPER in refs,
    }


def build_report() -> dict[str, Any]:
    N1G_ROOT.mkdir(parents=True, exist_ok=True)
    WORKSHOP_ROOT.mkdir(parents=True, exist_ok=True)
    write = write_mode()
    drift: list[dict[str, Any]] = []
    if write:
        # Explicit TQE_WRITE=1 opt-in: regenerate the tracked projections in place.
        write_capability_context()
        write_tactical_knowledge_pack(PACK_JSON_PATH, PACK_MD_PATH)
    else:
        # Read-only check: regenerate in memory and diff against the checked-in files.
        context = list_capabilities(CallerProfile.HERMES_S2).model_dump(mode="json")
        fresh_pack = build_tactical_knowledge_pack()
        drift.extend(
            item
            for item in (
                diff_against_checked_in(
                    Path("generated/capability-context.json"),
                    serialize_json_artifact(context),
                ),
                diff_against_checked_in(PACK_JSON_PATH, serialize_json_artifact(fresh_pack)),
                diff_against_checked_in(
                    PACK_MD_PATH, render_knowledge_pack_markdown(fresh_pack)
                ),
            )
            if item is not None
        )

    document = n1g_manual_document()
    write_json(MANUAL_PLAN_PATH, document)
    generic_validation = model_validate_document(document)
    wrapper_validation = model_validate_document(trusted_wrapper_document_from(document))
    execution = execute_manual_document(document)
    tri_state = relation_destination_entry_tri_state_fixture()
    contract = capability_contract()
    knowledge_checks = verify_tactical_knowledge_pack(PACK_JSON_PATH, PACK_MD_PATH)

    checks = [
        check(
            "n1g.generic_entry_agent_authorable",
            contract["generic_entry"].get("agent_authorable") is True
            and bool(contract["generic_entry"].get("agent_authoring", {}).get("safe_generic_path")),
            "relation_destination_entry is visible as the generic agent-authorable path.",
            contract["generic_entry"],
        ),
        check(
            "n1g.trusted_wrapper_not_agent_authorable",
            contract["trusted_wrapper"].get("agent_authorable") is False
            and TRUSTED_WRAPPER not in contract["opposite_recipe_authorable_refs"]
            and TRUSTED_WRAPPER in contract["opposite_recipe_omitted_refs"],
            "relation_destination_entry_classification remains trusted-recipe-only and is omitted from recipe authoring contracts.",
            contract,
        ),
        check(
            "n1g.safe_composition_path_advertised",
            bool(contract["safe_composition_rule"])
            and GENERIC_ENTRY in contract["safe_composition_rule"].get("required_catalog_refs", []),
            "Hermes-visible catalog describes the possession-corridor destination-entry path.",
            contract["safe_composition_rule"] or {},
        ),
        check(
            "n1g.manual_generic_plan_validates_for_model",
            generic_validation["validation"].get("ok") is True,
            "A manually authored model-profile plan validates through the generic path.",
            generic_validation["validation"],
        ),
        check(
            "n1g.manual_generic_plan_executes",
            execution["execution_status"] == "pass"
            and execution["compatibility_profile"] == "generic"
            and execution["row_count"] > 0,
            "The generic possession-start destination-entry plan executes over canonical data.",
            execution,
        ),
        check(
            "n1g.entry_evidence_projected",
            execution["has_entry_mode_evidence"] and execution["has_time_to_entry_evidence"],
            "Result evidence includes destination_entry_mode and destination_time_to_entry_seconds.",
            execution,
        ),
        check(
            "n1g.destination_evidence_scoped_to_same_relation",
            not execution["relation_witness_mismatches"],
            "Destination-entry evidence remains tied to the same witness relation selected by the corridor evidence.",
            {"mismatches": execution["relation_witness_mismatches"]},
        ),
        check(
            "n1g.eq_pass_preserves_unknown",
            tri_state["predicate_values_by_case"].get("unknown") is None
            and tri_state["predicate_unknown_mask_by_case"].get("unknown") is True,
            "entry_status eq PASS preserves UNKNOWN.",
            tri_state,
        ),
        check(
            "n1g.wrapper_plan_rejected_for_model",
            wrapper_validation["validation"].get("ok") is False
            and any(
                TRUSTED_WRAPPER in str(issue.get("message", ""))
                for issue in wrapper_validation["validation"].get("issues", [])
            ),
            "The same path using the trusted wrapper is still rejected for model callers.",
            wrapper_validation["validation"],
        ),
        check(
            "n1g.knowledge_pack_safe_surface",
            all(item["ok"] for item in knowledge_checks),
            "Generated tactical knowledge pack exposes the safe generic path and omits the trusted wrapper from authorable recipe summaries.",
            {"failed_checks": [item for item in knowledge_checks if not item["ok"]]},
        ),
        check(
            "n1g.tracked_projections_match_regeneration",
            not drift,
            "Checked-in knowledge pack / capability context match a fresh in-memory "
            "regeneration (check mode never rewrites tracked files; run `make n1g-write` "
            "to regenerate deliberately).",
            {"mode": "write" if write else "check", "drift": drift},
        ),
    ]
    summary = {"pass": sum(item["status"] == "pass" for item in checks), "fail": sum(item["status"] != "pass" for item in checks)}
    report = {
        "schema_version": "n1g.verification.v1",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "manual_plan_path": str(MANUAL_PLAN_PATH),
        "manual_plan_hash": stable_hash(document),
        "capability_contract": contract,
        "generic_validation": generic_validation,
        "wrapper_validation": wrapper_validation,
        "execution": execution,
        "tri_state": tri_state,
        "knowledge_pack_checks": knowledge_checks,
        "original_n1f_failure": original_n1f_failure_summary(),
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    if write:
        # Pinned delivery evidence is only rewritten under the explicit opt-in.
        DELIVERY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        DELIVERY_REPORT_PATH.write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# N1G — Agent-Authorable Destination Entry Capability",
        "",
        f"Status: `{report['status']}`",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Scope",
        "",
        "N1G makes the generic destination-entry measurement path visible and valid for agent-authored possession-start corridor plans. It does not expose the trusted recipe wrapper.",
        "",
        "## Local Proof",
        "",
        f"- Manual plan: `{report['manual_plan_path']}`",
        f"- Manual plan hash: `{report['manual_plan_hash']}`",
        f"- Model-profile validation: `{report['generic_validation']['validation'].get('ok')}`",
        f"- Execution status: `{report['execution']['execution_status']}`",
        f"- Rows: `{report['execution']['row_count']}`",
        f"- Bound plan hash: `{report['execution']['bound_plan_hash']}`",
        f"- Entry modes: `{', '.join(report['execution']['entry_modes'])}`",
        "",
        "## N1F Failure Preservation",
        "",
        f"- Existing N1F bundle present: `{report['original_n1f_failure'].get('present')}`",
        f"- Existing N1F status: `{report['original_n1f_failure'].get('status')}`",
        f"- Existing N1F used trusted wrapper: `{report['original_n1f_failure'].get('used_trusted_wrapper')}`",
        "",
        "## Checks",
        "",
    ]
    for item in report["checks"]:
        lines.append(f"- `{item['status']}` {item['id']}: {item['message']}")
    lines.extend(
        [
            "",
            "## Next Required Step",
            "",
            "Deploy this capability-contract fix, rerun the faithful scoped Hermes origin path, and preserve either a VERIFIED n1d1 attestation or the new blocker. Beta 1C remains blocked until n1d1-verify is VERIFIED.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    try:
        report = build_report()
    except CapabilityGap as exc:
        report = {
            "schema_version": "n1g.verification.v1",
            "generated_at": utc_now_iso(),
            "status": "fail",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        write_json(REPORT_PATH, report)
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        raise SystemExit(1) from exc
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
