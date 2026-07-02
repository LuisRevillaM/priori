"""N1D.1 — Hermes origin and structural-novelty attestation for the runtime-pinned N1D plan.

This verifier issues a host-verifiable attestation that the pinned N1D plan is (1) genuinely
Hermes-originated and (2) structurally novel versus registered recipes/templates. It fails closed:
it emits status VERIFIED only when every origin and novelty check passes, and otherwise emits
status BLOCKED with explicit reasons. It never fabricates origin — if the original Hermes session's
raw decision and ordered MCP tool-call trace are not present in existing artifacts, the corresponding
hashes are recorded as null with a reason, not invented.

The only N1D host augmentation permitted over the Hermes-submitted draft is adding the two requested
evidence aliases: destination_entry_mode and destination_time_to_entry_seconds.
"""

from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

from tqe.verification.n1a import registered_fingerprints, structural_fingerprint
from tqe.verification.n1c import (
    HERO_QUESTION,
    check,
    file_sha256,
    read_json,
    stable_json_sha256,
)
from tqe.write_mode import diff_against_checked_in, serialize_json_artifact, write_mode

# Committed source-of-truth (pinned N1D plan + manifest).
PINNED_ROOT = Path("delivery/n1d")
N1D_PLAN_PATH = PINNED_ROOT / "n1d-hero-plan.json"
N1D_MANIFEST_PATH = PINNED_ROOT / "n1d-canonical-freeze-manifest.json"
N1F_ORIGIN_BUNDLE_PATH = PINNED_ROOT / "n1f-origin-bundle.json"
N1E_ORIGIN_BUNDLE_PATH = PINNED_ROOT / "n1e-origin-bundle.json"
VERIFIED_ATTESTATION_PATH = PINNED_ROOT / "n1d1-attestation.json"
# The attestation is a generated artifact while BLOCKED (gitignored). It is promoted to
# delivery/n1d/n1d1-attestation.json (committed) only once it reaches status VERIFIED.
ATTESTATION_PATH = Path("artifacts/n1d/n1d1-attestation.json")
REPORT_PATH = Path("artifacts/n1d/n1d1-verification-report.json")

# Origin evidence (lives under gitignored artifacts/; this verifier fails closed if absent).
N1B_STRUCTURAL_PATH = Path("artifacts/n1b/n1-post-n1b-hero-structural-novelty-report.json")
HERMES_DRAFT_PATH = Path("artifacts/m1.2/workshop/handles/draft-plans/draft_26912b2c452106e8.json")
HERMES_TRACES_DIR = Path("artifacts/m1.2/workshop/hermes-traces")

ALLOWED_AUGMENTATION = {"destination_entry_mode", "destination_time_to_entry_seconds"}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strip_requested_evidence(document: dict[str, Any]) -> dict[str, Any]:
    stripped = deepcopy(document)
    stripped.get("draft_plan", {}).pop("requested_evidence", None)
    return stripped


def evidence_aliases(document: dict[str, Any]) -> set[str]:
    return {
        str(item.get("alias"))
        for item in document.get("draft_plan", {}).get("requested_evidence", [])
        if item.get("alias")
    }


def audit_augmentation_diff(final_document: dict[str, Any], hermes_document: dict[str, Any]) -> dict[str, Any]:
    """Audit the only allowed difference between Hermes draft and the pinned N1D plan.

    Earlier N1D paths expected the host to add exactly two aliases after Hermes submitted the
    draft. After N1I, those aliases are part of the generated authoring contract, so Hermes may
    author them directly. That is a stronger origin claim, not a weaker one. The invariant is:
    no structural edits after Hermes submission, no removed Hermes evidence, any host-added aliases
    are limited to the two approved fields, and the final plan contains both required fields.
    """
    final_stripped = strip_requested_evidence(final_document)
    hermes_stripped = strip_requested_evidence(hermes_document)
    final_aliases = evidence_aliases(final_document)
    hermes_aliases = evidence_aliases(hermes_document)
    added = sorted(final_aliases - hermes_aliases)
    removed = sorted(hermes_aliases - final_aliases)
    required_present = ALLOWED_AUGMENTATION.issubset(final_aliases)
    added_within_allowed = set(added).issubset(ALLOWED_AUGMENTATION)
    diff_allowed = (
        final_stripped == hermes_stripped
        and not removed
        and added_within_allowed
        and required_present
    )
    return {
        "structure_identical_after_strip": final_stripped == hermes_stripped,
        "added_aliases": added,
        "removed_aliases": removed,
        "added_equals_allowed": set(added) == ALLOWED_AUGMENTATION and not removed,
        "added_within_allowed": added_within_allowed,
        "required_aliases_present": required_present,
        "required_aliases_authored_by_hermes": sorted(ALLOWED_AUGMENTATION.intersection(hermes_aliases)),
        "diff_allowed": diff_allowed,
    }


def locate_hermes_trace(session_id: str, draft_plan_id: str | None) -> dict[str, Any] | None:
    """Find the persisted Hermes trace for the live session. Returns None if not present."""
    if not HERMES_TRACES_DIR.exists():
        return None
    for path in sorted(HERMES_TRACES_DIR.glob("*.json")):
        trace = read_json(path)
        if not isinstance(trace, dict):
            continue
        if trace.get("session_id") != session_id:
            continue
        if draft_plan_id and trace.get("draft_plan_id") not in (None, draft_plan_id):
            continue
        return trace
    return None


def bundle_host_augmented_plan(bundle: dict[str, Any]) -> dict[str, Any] | None:
    host = bundle.get("host_augmentation")
    if not isinstance(host, dict):
        return None
    document = host.get("augmented_document")
    return document if isinstance(document, dict) else None


def bundle_bound_plan_hash(bundle: dict[str, Any]) -> str | None:
    pipeline = bundle.get("host_pipeline")
    validation = pipeline.get("validation") if isinstance(pipeline, dict) else None
    if isinstance(validation, dict) and validation.get("bound_plan_hash"):
        return str(validation["bound_plan_hash"])
    artifact_records = bundle.get("artifact_records")
    bound_record = artifact_records.get("bound_record") if isinstance(artifact_records, dict) else None
    if isinstance(bound_record, dict) and bound_record.get("bound_plan_hash"):
        return str(bound_record["bound_plan_hash"])
    return None


def bundle_required_evidence_audit(bundle: dict[str, Any]) -> dict[str, Any]:
    audit = bundle.get("required_evidence_audit")
    if isinstance(audit, dict):
        return audit
    pipeline = bundle.get("host_pipeline") if isinstance(bundle.get("host_pipeline"), dict) else {}
    execution = pipeline.get("execution") if isinstance(pipeline.get("execution"), dict) else {}
    artifact_records = bundle.get("artifact_records") if isinstance(bundle.get("artifact_records"), dict) else {}
    execution_record = artifact_records.get("execution_record") if isinstance(artifact_records.get("execution_record"), dict) else {}
    nested_execution = (
        execution_record.get("execution") if isinstance(execution_record.get("execution"), dict) else {}
    )
    provenance = nested_execution.get("provenance") if isinstance(nested_execution.get("provenance"), dict) else {}
    return {
        "execution_status": execution.get("execution_status") or nested_execution.get("status"),
        "requested_evidence_failure_count": execution.get("requested_evidence_failure_count")
        if execution.get("requested_evidence_failure_count") is not None
        else provenance.get("requested_evidence_failure_count"),
        "all_required_aliases_resolved": False,
        "acceptance_pass": False,
        "reason": "origin bundle predates explicit required_evidence_audit",
    }


def origin_bundle_path() -> Path | None:
    if N1F_ORIGIN_BUNDLE_PATH.exists():
        return N1F_ORIGIN_BUNDLE_PATH
    if N1E_ORIGIN_BUNDLE_PATH.exists():
        return N1E_ORIGIN_BUNDLE_PATH
    return None


def audit_origin_bundle(n1d_plan: dict[str, Any], bundle: dict[str, Any], bundle_path: Path) -> dict[str, Any]:
    hermes = bundle.get("hermes_origin") if isinstance(bundle.get("hermes_origin"), dict) else {}
    session_trace = hermes.get("session_trace") if isinstance(hermes.get("session_trace"), dict) else {}
    hermes_doc = hermes.get("draft_document") if isinstance(hermes.get("draft_document"), dict) else {}
    tool_calls = session_trace.get("ordered_tool_calls")
    raw_model_output = session_trace.get("raw_model_output")
    if not isinstance(tool_calls, list):
        tool_calls = []

    compile_tool_names = [
        str(call.get("name") or "").removeprefix("functions.")
        for call in tool_calls
        if isinstance(call, dict)
    ]
    required_tools = {
        "mcp_priori_tactical_submit_query_plan",
        "mcp_priori_tactical_validate_query_plan",
    }
    return {
        "original_question_sha256": sha256(HERO_QUESTION.encode("utf-8")).hexdigest(),
        "n1d_host_augmented_plan_hash": stable_json_sha256(n1d_plan),
        "session_id": hermes.get("session_id"),
        "hermes_submitted_draft_plan_hash": hermes.get("draft_plan_hash"),
        "ordered_tool_call_trace_sha256": stable_json_sha256(tool_calls) if tool_calls else None,
        "raw_hermes_decision_sha256": stable_json_sha256(raw_model_output) if raw_model_output else None,
        "allowed_augmentation_diff": audit_augmentation_diff(n1d_plan, hermes_doc),
        "origin_artifacts_present": True,
        "trace_persisted": bool(session_trace.get("trace_persisted") and tool_calls and raw_model_output),
        "compile_tool_trace": {
            "tool_names": compile_tool_names,
            "contains_submit_and_validate": required_tools.issubset(set(compile_tool_names)),
        },
        "notes": [],
        "origin_bundle_path": str(bundle_path),
        "origin_bundle_sha256": sha256(
            json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


def audit_hermes_origin(n1d_plan: dict[str, Any]) -> dict[str, Any]:
    path = origin_bundle_path()
    if path is not None:
        return audit_origin_bundle(n1d_plan, read_json(path), path)

    origin: dict[str, Any] = {
        "original_question_sha256": sha256(HERO_QUESTION.encode("utf-8")).hexdigest(),
        "n1d_host_augmented_plan_hash": stable_json_sha256(n1d_plan),
        "session_id": None,
        "hermes_submitted_draft_plan_hash": None,
        "ordered_tool_call_trace_sha256": None,
        "raw_hermes_decision_sha256": None,
        "allowed_augmentation_diff": None,
        "origin_artifacts_present": False,
        "trace_persisted": False,
        "notes": [],
    }

    if not N1B_STRUCTURAL_PATH.exists() or not HERMES_DRAFT_PATH.exists():
        origin["notes"].append(
            "Origin artifacts absent (n1b structural report or Hermes draft handle missing under artifacts/)."
        )
        return origin
    origin["origin_artifacts_present"] = True

    structural = read_json(N1B_STRUCTURAL_PATH)
    session_id = structural.get("session_id")
    draft_plan_id = structural.get("draft_plan_id")
    origin["session_id"] = session_id

    hermes_handle = read_json(HERMES_DRAFT_PATH)
    hermes_doc = hermes_handle.get("document", {})
    origin["hermes_submitted_draft_plan_hash"] = hermes_handle.get("draft_plan_hash")

    # Allowed-augmentation diff vs the genuine Hermes draft.
    origin["allowed_augmentation_diff"] = audit_augmentation_diff(n1d_plan, hermes_doc)

    # Locate the raw decision + ordered tool-call trace. NEVER fabricate if missing.
    trace = locate_hermes_trace(session_id, draft_plan_id) if session_id else None
    if trace is None:
        origin["notes"].append(
            "No persisted Hermes trace (raw_model_output + ordered tool_calls) found for the live "
            "session; origin decision/tool-call hashes are unavailable and were NOT fabricated."
        )
        return origin
    origin["trace_persisted"] = True
    origin["ordered_tool_call_trace_sha256"] = stable_json_sha256(trace.get("tool_calls"))
    origin["raw_hermes_decision_sha256"] = sha256(
        json.dumps(trace.get("raw_model_output"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return origin


def attest_structural_novelty(n1d_plan: dict[str, Any]) -> dict[str, Any]:
    fingerprint = structural_fingerprint(n1d_plan)
    registered = registered_fingerprints()["registered"]
    registered_hashes = {item["recipe_id"]: item["structural_fingerprint"]["fingerprint_hash"] for item in registered}
    fingerprint_hash = fingerprint["fingerprint_hash"]
    per_template = [
        {"recipe_id": recipe_id, "fingerprint_hash": hash_value, "matches_n1d": hash_value == fingerprint_hash}
        for recipe_id, hash_value in sorted(registered_hashes.items())
    ]
    existing_recipe_selected = any(item["matches_n1d"] for item in per_template)
    return {
        "normalized_structural_fingerprint": fingerprint,
        "fingerprint_hash": fingerprint_hash,
        "registered_fingerprint_set_hash": stable_json_sha256(sorted(registered_hashes.values())),
        "per_template_comparison": per_template,
        "existing_recipe_selected": existing_recipe_selected,
        "structurally_novel": not existing_recipe_selected,
    }


def main() -> None:
    if not N1D_PLAN_PATH.exists() or not N1D_MANIFEST_PATH.exists():
        report = {
            "schema_version": "n1d1.verification.v1",
            "status": "fail",
            "blocking_reasons": ["N1D pinned plan or manifest missing — run n1d-freeze first."],
        }
        write_json(REPORT_PATH, report)
        print(json.dumps({"status": "fail", "reason": "n1d_pins_missing"}, sort_keys=True))
        raise SystemExit(1)

    bundle_path = origin_bundle_path()
    origin_bundle = read_json(bundle_path) if bundle_path is not None else None
    bundle_plan = bundle_host_augmented_plan(origin_bundle) if isinstance(origin_bundle, dict) else None
    n1d_plan = bundle_plan or read_json(N1D_PLAN_PATH)
    manifest = read_json(N1D_MANIFEST_PATH)
    pinned = manifest.get("pinned_identity", {})
    bound_plan_hash = bundle_bound_plan_hash(origin_bundle) if isinstance(origin_bundle, dict) else None
    if not bound_plan_hash:
        bound_plan_hash = pinned.get("plan", {}).get("bound_plan_hash")
    freeze_manifest_source = origin_bundle if isinstance(origin_bundle, dict) else pinned
    prefix = bundle_path.stem.split("-")[0] if bundle_path is not None else "n1d"
    freeze_manifest_id = f"{prefix}-" + stable_json_sha256(freeze_manifest_source)[:16]

    origin = audit_hermes_origin(n1d_plan)
    novelty = attest_structural_novelty(n1d_plan)
    aug = origin.get("allowed_augmentation_diff")
    manifest_required_evidence = pinned.get("required_evidence", {})
    bundle_required_evidence = (
        bundle_required_evidence_audit(origin_bundle) if isinstance(origin_bundle, dict) else {}
    )

    checks = [
        check(
            "n1d1.origin_session_recorded",
            bool(origin.get("session_id")),
            "The original Hermes session id is recorded in existing artifacts.",
            {"session_id": origin.get("session_id")},
        ),
        check(
            "n1d1.origin_trace_persisted",
            origin.get("trace_persisted") is True,
            "The original Hermes raw decision and ordered MCP tool-call trace are persisted and hashable.",
            {"notes": origin.get("notes")},
        ),
        check(
            "n1d1.origin_compile_tools_present",
            bool(origin.get("compile_tool_trace", {}).get("contains_submit_and_validate")),
            "The persisted Hermes tool trace contains submit_query_plan and validate_query_plan.",
            origin.get("compile_tool_trace", {"reason": "trace absent"}),
        ),
        check(
            "n1d1.augmentation_diff_allowed",
            bool(aug and aug["diff_allowed"]),
            "N1D plan equals the Hermes draft except for optional host addition of the two allowed evidence aliases, and the final plan contains both.",
            aug or {"reason": "origin artifacts absent"},
        ),
        check(
            "n1d1.structurally_novel",
            novelty["structurally_novel"],
            "N1D structural fingerprint differs from every registered recipe/template.",
            {"fingerprint_hash": novelty["fingerprint_hash"], "per_template": novelty["per_template_comparison"]},
        ),
        check(
            "n1d1.existing_recipe_not_selected",
            novelty["existing_recipe_selected"] is False,
            "existing_recipe_selected is false (the plan is not a registered recipe selection).",
            {"existing_recipe_selected": novelty["existing_recipe_selected"]},
        ),
        check(
            "n1d1.freeze_required_evidence_complete",
            manifest_required_evidence.get("acceptance_pass") is True,
            "The N1D freeze proves execution.status == pass, zero requested-evidence failures, and non-null required aliases.",
            manifest_required_evidence,
        ),
        check(
            "n1d1.origin_host_pipeline_required_evidence_complete",
            bundle_required_evidence.get("acceptance_pass") is True,
            "The committed Hermes-origin bundle host pipeline was refreshed with complete required evidence.",
            bundle_required_evidence,
        ),
    ]
    blocking_reasons = [item["id"] for item in checks if item["status"] != "pass"]
    status = "VERIFIED" if not blocking_reasons else "BLOCKED"

    attestation = {
        "schema_version": "n1d1.attestation.v1",
        "status": status,
        "plan_hash": bound_plan_hash,
        "freeze_manifest_id": freeze_manifest_id,
        "freeze_manifest_sha256": file_sha256(N1D_MANIFEST_PATH),
        "commit_at_manifest_generation": manifest.get("source", {}).get("commit_at_manifest_generation"),
        "hermes_origin": origin,
        "structural_novelty": novelty,
        "blocking_reasons": blocking_reasons,
        "beta_1c_unlock_contract": {
            "required_provenance_source": "HERMES_NOVEL_COMPOSITION",
            "required_status": "VERIFIED",
            "required_plan_hash": "must equal the current bound plan hash",
            "required_freeze_manifest_id": "must equal the current N1D manifest id",
            "fail_closed_on": ["browser payload", "model payload", "stale attestation", "mismatched plan hash"],
        },
    }
    write_json(ATTESTATION_PATH, attestation)
    drift: list[dict[str, Any]] = []
    if status == "VERIFIED":
        if write_mode():
            # Explicit TQE_WRITE=1 opt-in: promote the attestation into delivery/.
            write_json(VERIFIED_ATTESTATION_PATH, attestation)
        else:
            # Read-only check: the committed attestation must match a fresh
            # regeneration; drift fails the gate instead of being rewritten.
            drift_item = diff_against_checked_in(
                VERIFIED_ATTESTATION_PATH, serialize_json_artifact(attestation)
            )
            if drift_item is not None:
                drift.append(drift_item)
                blocking_reasons.append("n1d1.committed_attestation_drift")

    report = {
        "schema_version": "n1d1.verification.v1",
        "status": "pass" if status == "VERIFIED" and not drift else "fail",
        "attestation_status": status,
        "attestation_path": str(ATTESTATION_PATH),
        "committed_attestation_drift": drift,
        "blocking_reasons": blocking_reasons,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    print(json.dumps({"attestation_status": status, "blocking_reasons": blocking_reasons}, sort_keys=True))
    if status != "VERIFIED" or drift:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
