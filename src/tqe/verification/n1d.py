"""N1D — runtime-pinned novel-composition refresh and read-compare freeze gate.

N1C pinned the N1B *live* hero artifacts, which were produced before the runtime emitted
``entry_mode``. N1D re-executes the SAME frozen hero plan under the CURRENT runtime so the fresh
artifacts carry honest ``entry_mode`` evidence, then pins a canonical manifest to the exact
runtime / data / artifact hashes that produced the results.

Two modes:

* ``--freeze`` : build the N1D hero plan (the frozen N1A candidate plus the two already
  runtime-emitted destination-entry evidence fields), run the full host-authority workshop
  pipeline into ``artifacts/n1d/workshop``, audit ``entry_mode``, and WRITE the pinned manifest.
* default (gate / verifier) : READ the pinned manifest, re-run the pipeline into a throwaway
  scratch directory, recompute the deterministic identity, and COMPARE. It fails on drift instead
  of silently regenerating proof. It also preserves the N1C UNKNOWN / enum-domain contracts.

The hero plan SHAPE, capabilities, operators, prompts, and hero question are unchanged. The only
addition is surfacing two catalog-declared evidence fields the runtime already emits
(``entry_mode`` and ``time_to_entry_seconds``) so the result evidence can carry the proof.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from tqe.runtime.ir import TacticalQueryDocument
from tqe.verification.n1b import runtime_parameter_access_contract
from tqe.verification.n1c import (
    CANONICAL_DATA_ROOT,
    CAPABILITY_CONTEXT_PATH,
    DEMO_DATA_MANIFEST_PATH,
    FREEZE_PATH,
    HERO_QUESTION,
    KNOWLEDGE_PACK_PATH,
    canonical_data_inventory_sha256,
    check,
    declared_enum_output_contract,
    file_identity,
    file_sha256,
    git_output,
    read_json,
    relation_destination_entry_tri_state_fixture,
    stable_json_sha256,
)
from tqe.workshop.m1_2 import (
    CallerProfile,
    ExecuteQueryPlanRequest,
    InspectResultRequest,
    ReplayWindowRequest,
    SubmitQueryPlanRequest,
    ValidateQueryPlanRequest,
    canonical_identity,
    execute_query_plan,
    host_confirm_bound_plan,
    inspect_result,
    read_handle,
    retrieve_replay_window,
    submit_query_plan,
    validate_query_plan,
)

# Pinned proof source-of-truth lives under committed delivery/; regenerated handles and the gate
# run report live under gitignored artifacts/.
PINNED_ROOT = Path("delivery/n1d")
N1D_ROOT = Path("artifacts/n1d")
N1D_WORKSHOP_ROOT = N1D_ROOT / "workshop"
N1D_PLAN_PATH = PINNED_ROOT / "n1d-hero-plan.json"
MANIFEST_PATH = PINNED_ROOT / "n1d-canonical-freeze-manifest.json"
AUDIT_PATH = PINNED_ROOT / "n1d-entry-mode-audit.json"
REPORT_PATH = N1D_ROOT / "n1d-verification-report.json"

CANDIDATE_PATH = Path("artifacts/n1-live-novel-composition-2026-06-22/n1-local-only-candidate-plan.json")

ENTRY_MODE_DOMAIN = ("PRESENT_AT_OPEN", "ENTERED_AFTER_OPEN", "NOT_ENTERED", "UNKNOWN")
RESULT_LIMIT = 25

# Two catalog-declared destination-entry evidence fields the runtime already emits. Surfacing them
# is required for proof consumption; it adds no tactical vocabulary, primitive, operator, or prompt.
ENTRY_MODE_EVIDENCE: list[dict[str, Any]] = [
    {
        "source": {"source_node_id": "destination_entry", "output_name": "entry_status"},
        "field": "entry_mode",
        "alias": "destination_entry_mode",
    },
    {
        "source": {"source_node_id": "destination_entry", "output_name": "entry_status"},
        "field": "time_to_entry_seconds",
        "alias": "destination_time_to_entry_seconds",
        "required": False,
    },
]

RUNTIME_SOURCE_FILES = {
    "runtime_executor": Path("src/tqe/runtime/executor.py"),
    "runtime_catalog": Path("src/tqe/runtime/catalog.py"),
    "runtime_binder": Path("src/tqe/runtime/binder.py"),
    "runtime_values": Path("src/tqe/runtime/values.py"),
    "workshop_service": Path("src/tqe/workshop/m1_2.py"),
    "mcp_server": Path("src/tqe/workshop/mcp_server.py"),
}

ENTRY_BEFORE_OPEN_ANALYSIS = (
    "Entry-before-open is structurally impossible: ball_entry_evaluation_into_destination_region "
    "scans ball frames from open_frame_id forward, so the first in-region frame satisfies "
    "frame_id >= open_frame_id. time_to_entry_seconds is therefore always >= 0.0, and entry_mode is "
    "PRESENT_AT_OPEN exactly when the entry frame equals the open frame (time_to_entry_seconds == 0.0)."
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_n1d_plan_document() -> dict[str, Any]:
    """Frozen N1A candidate plus the two runtime-emitted destination-entry evidence fields."""
    if CANDIDATE_PATH.exists():
        document = read_json(CANDIDATE_PATH)
    else:
        # Reproduce the frozen candidate deterministically from the N1A builder if absent.
        from tqe.verification.n1a import build_candidate_plan

        document = build_candidate_plan()
    requested = document["draft_plan"].setdefault("requested_evidence", [])
    present = {(item["source"]["source_node_id"], item["field"]) for item in requested}
    for evidence in ENTRY_MODE_EVIDENCE:
        key = (evidence["source"]["source_node_id"], evidence["field"])
        if key not in present:
            requested.append(deepcopy(evidence))
    return document


def run_pipeline(document: dict[str, Any], output_root: Path) -> dict[str, Any]:
    """Run the full host-authority workshop pipeline and return ids + canonical handle records."""
    plan_document = TacticalQueryDocument.model_validate(document)
    submit = submit_query_plan(
        SubmitQueryPlanRequest(plan_document=plan_document, source_label="n1d_refresh"),
        output_root=output_root,
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    validation = validate_query_plan(
        ValidateQueryPlanRequest(draft_plan_id=submit.draft_plan_id),
        output_root=output_root,
    )
    if not validation.ok or not validation.bound_plan_id:
        raise RuntimeError(f"N1D hero plan failed validation: {validation.issues}")
    confirmation = host_confirm_bound_plan(
        validation.bound_plan_id, reviewer="n1d_refresh", output_root=output_root
    )
    execution = execute_query_plan(
        ExecuteQueryPlanRequest(
            bound_plan_id=validation.bound_plan_id,
            execution_authorization_id=confirmation.execution_authorization_id,
            result_limit=RESULT_LIMIT,
        ),
        output_root=output_root,
    )
    if not execution.results:
        raise RuntimeError("N1D hero execution produced no results")
    first_result_id = str(execution.results[0]["result_id"])
    inspect_result(
        InspectResultRequest(execution_id=execution.execution_id, result_id=first_result_id),
        output_root=output_root,
    )
    replay = retrieve_replay_window(
        ReplayWindowRequest(execution_id=execution.execution_id, result_id=first_result_id),
        output_root=output_root,
    )
    return {
        "draft_plan_id": submit.draft_plan_id,
        "draft_plan_hash": submit.draft_plan_hash,
        "bound_plan_id": validation.bound_plan_id,
        "bound_plan_hash": validation.bound_plan_hash,
        "execution_profile": validation.execution_profile,
        "execution_id": execution.execution_id,
        "first_result_id": first_result_id,
        "replay_window_id": replay.replay_window_id,
        "draft_record": read_handle("draft-plans", submit.draft_plan_id, output_root=output_root),
        "bound_record": read_handle("bound-plans", validation.bound_plan_id, output_root=output_root),
        "execution_record": read_handle("executions", execution.execution_id, output_root=output_root),
        "replay_record": read_handle("replay-windows", replay.replay_window_id, output_root=output_root),
    }


def entry_mode_audit(execution_record: dict[str, Any]) -> dict[str, Any]:
    rows = execution_record.get("rows", [])
    distribution = {mode: 0 for mode in ENTRY_MODE_DOMAIN}
    per_result: list[dict[str, Any]] = []
    out_of_domain: list[dict[str, Any]] = []
    time_zero_mismatch: list[dict[str, Any]] = []
    entry_before_open: list[dict[str, Any]] = []
    for row in rows:
        evidence = row.get("requested_evidence", {}) or {}
        mode = evidence.get("destination_entry_mode")
        time_to_entry = evidence.get("destination_time_to_entry_seconds")
        record = {
            "result_id": row.get("result_id"),
            "classification": row.get("classification"),
            "entry_mode": mode,
            "time_to_entry_seconds": time_to_entry,
            "entry_status": evidence.get("destination_entry_status"),
            "entry_frame_id": evidence.get("destination_entry_frame_id"),
            "observed_window_end_frame_id": evidence.get("destination_observed_window_end_frame_id"),
        }
        per_result.append(record)
        if mode in distribution:
            distribution[mode] += 1
        else:
            out_of_domain.append(record)
        if isinstance(time_to_entry, (int, float)):
            if time_to_entry == 0.0 and mode != "PRESENT_AT_OPEN":
                time_zero_mismatch.append(record)
            if time_to_entry < 0:
                entry_before_open.append(record)
    return {
        "result_count": len(rows),
        "entry_mode_domain": list(ENTRY_MODE_DOMAIN),
        "distribution": distribution,
        "per_result": per_result,
        "all_in_domain": not out_of_domain,
        "out_of_domain": out_of_domain,
        "present_at_open_zero_time_consistent": not time_zero_mismatch,
        "time_zero_mismatch": time_zero_mismatch,
        "entry_before_open_count": len(entry_before_open),
        "entry_before_open_anomalies": entry_before_open,
        "entry_before_open_analysis": ENTRY_BEFORE_OPEN_ANALYSIS,
        "contains_entry_mode_evidence": bool(rows) and all(
            "destination_entry_mode" in (row.get("requested_evidence", {}) or {}) for row in rows
        ),
    }


def _strip_local_paths(value: Any) -> Any:
    """Drop output-root-dependent filesystem paths so content hashing is location-independent."""
    if isinstance(value, dict):
        return {key: _strip_local_paths(item) for key, item in value.items() if key != "artifact_path"}
    if isinstance(value, list):
        return [_strip_local_paths(item) for item in value]
    return value


def artifact_content_hash(record: dict[str, Any]) -> str:
    """Deterministic content hash ignoring wall-clock fields and output-root-dependent paths."""
    return stable_json_sha256(_strip_local_paths(canonical_identity(record)))


def runtime_hashes() -> dict[str, str]:
    return {name: file_sha256(path) for name, path in RUNTIME_SOURCE_FILES.items()}


def pinned_identity(document: dict[str, Any], records: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    """The deterministic subset the freeze gate recomputes and compares. Any drift fails the gate."""
    rows = records["execution_record"].get("rows", [])
    knowledge_pack = read_json(KNOWLEDGE_PACK_PATH)
    return {
        "runtime": runtime_hashes(),
        "knowledge_pack": {
            "file_sha256": file_sha256(KNOWLEDGE_PACK_PATH),
            "semantic_sha256": str(knowledge_pack.get("knowledge_pack_sha256")),
        },
        "data": {
            "canonical_inventory_sha256": canonical_data_inventory_sha256(CANONICAL_DATA_ROOT),
            "deploy_manifest_sha256": file_sha256(DEMO_DATA_MANIFEST_PATH)
            if DEMO_DATA_MANIFEST_PATH.exists()
            else "",
        },
        "hero_question_sha256": sha256(HERO_QUESTION.encode("utf-8")).hexdigest(),
        "plan": {
            "document_sha256": file_sha256(N1D_PLAN_PATH),
            "document_stable_sha256": stable_json_sha256(document),
            "draft_plan_hash": records["draft_plan_hash"],
            "bound_plan_hash": records["bound_plan_hash"],
        },
        "artifacts": {
            "draft_plan": artifact_content_hash(records["draft_record"]),
            "bound_plan": artifact_content_hash(records["bound_record"]),
            "execution": artifact_content_hash(records["execution_record"]),
            "replay_window": artifact_content_hash(records["replay_record"]),
        },
        "identity": {
            "draft_plan_id": records["draft_plan_id"],
            "bound_plan_id": records["bound_plan_id"],
            "execution_id": records["execution_id"],
            "first_result_id": records["first_result_id"],
            "replay_window_id": records["replay_window_id"],
            "result_ids": [str(row["result_id"]) for row in rows],
            "result_fingerprint": stable_json_sha256(canonical_identity(rows)),
        },
        "entry_mode": {
            "distribution": audit["distribution"],
            "all_in_domain": audit["all_in_domain"],
            "present_at_open_zero_time_consistent": audit["present_at_open_zero_time_consistent"],
            "entry_before_open_count": audit["entry_before_open_count"],
            "contains_entry_mode_evidence": audit["contains_entry_mode_evidence"],
        },
    }


def build_manifest(document: dict[str, Any], records: dict[str, Any], audit: dict[str, Any], pinned: dict[str, Any]) -> dict[str, Any]:
    freeze = read_json(FREEZE_PATH)
    tool_allowlist = freeze["mcp_boundary"]["tool_allowlist"]
    return {
        "schema_version": "n1d.canonical_freeze_manifest.v1",
        "generated_at": utc_now_iso(),
        "supersedes": "artifacts/n1c/n1c-canonical-freeze-manifest.json",
        "refresh_reason": (
            "N1B/N1C live hero artifacts predate the runtime entry_mode contract. N1D re-executes the "
            "frozen hero under current HEAD so result evidence carries honest entry_mode."
        ),
        "source": {
            "commit_at_manifest_generation": git_output("rev-parse", "HEAD"),
            "source_files": {name: file_identity(path) for name, path in RUNTIME_SOURCE_FILES.items()},
        },
        "knowledge_pack": {
            "path": str(KNOWLEDGE_PACK_PATH),
            "file_sha256": pinned["knowledge_pack"]["file_sha256"],
            "semantic_sha256": pinned["knowledge_pack"]["semantic_sha256"],
            "capability_context": file_identity(CAPABILITY_CONTEXT_PATH),
        },
        "hermes": {
            "provider": freeze["selected_product_route"].get("provider"),
            "configured_model": freeze["selected_product_route"].get("configured_model"),
            "reasoning_effort": freeze["selected_product_route"].get("reasoning_effort"),
            "version": freeze["selected_product_route"].get("hermes_version"),
            "config_sha256": freeze["selected_product_route"].get("hermes_config_sha256"),
        },
        "mcp": {
            "server_name": "priori_tactical",
            "tool_allowlist": tool_allowlist,
            "tool_allowlist_sha256": stable_json_sha256(tool_allowlist),
        },
        "hero_question": {"text": HERO_QUESTION, "sha256": pinned["hero_question_sha256"]},
        "hero_plan": {
            "path": str(N1D_PLAN_PATH),
            "derived_from": str(CANDIDATE_PATH),
            "added_evidence_fields": [item["field"] for item in ENTRY_MODE_EVIDENCE],
            "document_sha256": pinned["plan"]["document_sha256"],
            "document_stable_sha256": pinned["plan"]["document_stable_sha256"],
        },
        # Handles are regenerated under gitignored artifacts/n1d/workshop and carry wall-clock fields,
        # so we pin their deterministic canonical-content hash (not the raw timestamped file bytes).
        "n1d_live_artifacts": {
            "draft_plan": {
                "relative_path": f"{N1D_WORKSHOP_ROOT}/draft-plans/{records['draft_plan_id']}.json",
                "content_sha256": pinned["artifacts"]["draft_plan"],
            },
            "bound_plan": {
                "relative_path": f"{N1D_WORKSHOP_ROOT}/bound-plans/{records['bound_plan_id']}.json",
                "content_sha256": pinned["artifacts"]["bound_plan"],
            },
            "execution_handle": {
                "relative_path": f"{N1D_WORKSHOP_ROOT}/executions/{records['execution_id']}.json",
                "content_sha256": pinned["artifacts"]["execution"],
            },
            "replay_window": {
                "relative_path": f"{N1D_WORKSHOP_ROOT}/replay-windows/{records['replay_window_id']}.json",
                "content_sha256": pinned["artifacts"]["replay_window"],
            },
        },
        "runtime": {
            "compatibility_profile": records["bound_record"].get("execution_profile")
            or records["execution_record"].get("compatibility_profile"),
            "executor_sha256": pinned["runtime"]["runtime_executor"],
            "catalog_sha256": pinned["runtime"]["runtime_catalog"],
            "binder_sha256": pinned["runtime"]["runtime_binder"],
            "values_sha256": pinned["runtime"]["runtime_values"],
        },
        "data": {
            "deploy_manifest": file_identity(DEMO_DATA_MANIFEST_PATH),
            "canonical_root": str(CANONICAL_DATA_ROOT),
            "canonical_inventory_sha256": pinned["data"]["canonical_inventory_sha256"],
        },
        "entry_mode_audit": audit,
        "pinned_identity": pinned,
    }


def freeze() -> int:
    """Build fresh runtime-pinned artifacts and WRITE the canonical manifest. One-time pinning."""
    N1D_ROOT.mkdir(parents=True, exist_ok=True)
    PINNED_ROOT.mkdir(parents=True, exist_ok=True)
    if N1D_WORKSHOP_ROOT.exists():
        shutil.rmtree(N1D_WORKSHOP_ROOT)
    document = build_n1d_plan_document()
    write_json(N1D_PLAN_PATH, document)
    records = run_pipeline(document, N1D_WORKSHOP_ROOT)
    audit = entry_mode_audit(records["execution_record"])
    pinned = pinned_identity(document, records, audit)
    manifest = build_manifest(document, records, audit, pinned)
    write_json(MANIFEST_PATH, manifest)
    write_json(AUDIT_PATH, audit)
    report = {
        "schema_version": "n1d.freeze_report.v1",
        "mode": "freeze",
        "generated_at": utc_now_iso(),
        "status": "frozen",
        "manifest_path": str(MANIFEST_PATH),
        "manifest_sha256": file_sha256(MANIFEST_PATH),
        "entry_mode_distribution": audit["distribution"],
    }
    write_json(REPORT_PATH, report)
    print(json.dumps({"mode": "freeze", "status": "frozen", "entry_mode": audit["distribution"]}, sort_keys=True))
    return 0


def diff_pinned(expected: Any, actual: Any, path: str = "") -> list[dict[str, Any]]:
    drifts: list[dict[str, Any]] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            drifts.extend(diff_pinned(expected.get(key), actual.get(key), f"{path}.{key}" if path else key))
    elif expected != actual:
        drifts.append({"field": path, "pinned": expected, "current": actual})
    return drifts


def gate() -> int:
    """Read-compare freeze gate. Fails on drift instead of regenerating proof."""
    checks: list[dict[str, Any]] = []
    manifest_present = MANIFEST_PATH.exists() and N1D_PLAN_PATH.exists()
    checks.append(
        check(
            "n1d.manifest_present",
            manifest_present,
            "Pinned N1D canonical freeze manifest and hero plan exist (run --freeze first).",
            {"manifest_path": str(MANIFEST_PATH), "plan_path": str(N1D_PLAN_PATH)},
        )
    )
    drift: list[dict[str, Any]] = []
    audit: dict[str, Any] = {}
    if manifest_present:
        manifest = read_json(MANIFEST_PATH)
        document = read_json(N1D_PLAN_PATH)
        scratch = Path(tempfile.mkdtemp(prefix="n1d-gate-"))
        try:
            records = run_pipeline(document, scratch)
            audit = entry_mode_audit(records["execution_record"])
            current = pinned_identity(document, records, audit)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        drift = diff_pinned(manifest.get("pinned_identity", {}), current)
        checks.append(
            check(
                "n1d.no_artifact_or_runtime_drift",
                not drift,
                "Re-executed runtime/data/plan/artifact/result hashes match the pinned manifest.",
                {"drift": drift},
            )
        )
        checks.append(
            check(
                "n1d.runtime_matches_claim",
                manifest["pinned_identity"]["runtime"] == current["runtime"],
                "Pinned runtime source hashes match the runtime being claimed (current HEAD).",
                {"pinned": manifest["pinned_identity"]["runtime"], "current": current["runtime"]},
            )
        )
        checks.append(
            check(
                "n1d.result_evidence_contains_entry_mode",
                audit["contains_entry_mode_evidence"] and audit["result_count"] > 0,
                "Every re-executed result carries entry_mode evidence under the current runtime.",
                {"result_count": audit["result_count"], "distribution": audit["distribution"]},
            )
        )
        checks.append(
            check(
                "n1d.entry_mode_in_declared_domain",
                audit["all_in_domain"],
                "Every entry_mode value is within the declared PRESENT/ENTERED/NOT_ENTERED/UNKNOWN domain.",
                {"out_of_domain": audit["out_of_domain"], "domain": list(ENTRY_MODE_DOMAIN)},
            )
        )
        checks.append(
            check(
                "n1d.zero_time_is_present_at_open",
                audit["present_at_open_zero_time_consistent"],
                "Results with time_to_entry_seconds == 0.0 are labelled PRESENT_AT_OPEN, not entered-later.",
                {"time_zero_mismatch": audit["time_zero_mismatch"]},
            )
        )
        checks.append(
            check(
                "n1d.no_entry_before_open",
                audit["entry_before_open_count"] == 0,
                "No result reports entry before the corridor open frame (negative time_to_entry).",
                {"anomalies": audit["entry_before_open_anomalies"], "analysis": ENTRY_BEFORE_OPEN_ANALYSIS},
            )
        )

    # Preserve the N1C UNKNOWN + enum-domain + runtime-parameter contracts.
    tri_state = relation_destination_entry_tri_state_fixture()
    enum_contract = declared_enum_output_contract()
    context_contract = runtime_parameter_access_contract()
    checks.append(
        check(
            "n1c.entry_status_pass_fail_unknown_exercised",
            tri_state["entry_statuses"]
            == {"after_open_pass": "PASS", "fail": "FAIL", "present_at_open_pass": "PASS", "unknown": "UNKNOWN"},
            "Preserved: generic relation_destination_entry still emits PASS, FAIL, and UNKNOWN.",
            tri_state["entry_statuses"],
        )
    )
    checks.append(
        check(
            "n1c.eq_pass_preserves_unknown",
            tri_state["predicate_values_by_case"].get("unknown") is None
            and tri_state["predicate_unknown_mask_by_case"].get("unknown") is True,
            "Preserved: entry_status == PASS preserves UNKNOWN rather than converting it to false.",
            {
                "unknown_value": tri_state["predicate_values_by_case"].get("unknown"),
                "unknown_mask": tri_state["predicate_unknown_mask_by_case"].get("unknown"),
            },
        )
    )
    checks.append(
        check(
            "n1c.entry_mode_tri_state_emitted",
            set(ENTRY_MODE_DOMAIN).issubset(set(tri_state["entry_modes"].values())),
            "Preserved: destination-entry records carry the full entry_mode tri-state evidence.",
            tri_state["entry_modes"],
        )
    )
    checks.append(
        check(
            "n1c.declared_enum_outputs_enforced",
            enum_contract["all_declared_domains_enforced"],
            "Preserved: every catalog enum output rejects out-of-domain runtime values.",
            {"checked": len(enum_contract["checked_outputs"])},
        )
    )
    checks.append(
        check(
            "n1c.executor_runtime_parameters_declared",
            not context_contract["undeclared_accesses"],
            "Preserved: every executor RuntimeParameters access is host- or recipe-supplied.",
            {"undeclared_accesses": context_contract["undeclared_accesses"]},
        )
    )

    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
    }
    report = {
        "schema_version": "n1d.verification.v1",
        "mode": "gate",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "manifest_path": str(MANIFEST_PATH),
        "drift": drift,
        "entry_mode_audit": audit,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    print(json.dumps({"mode": "gate", "status": report["status"], "summary": summary}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="N1D runtime-pinned novel-composition refresh / freeze gate.")
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="Re-execute the frozen hero under current HEAD and write the pinned manifest.",
    )
    args = parser.parse_args()
    raise SystemExit(freeze() if args.freeze else gate())


if __name__ == "__main__":
    main()
