"""Verify M1.1 Gate A: minimal IR, type system, and binder."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.artifacts import expected_generated_artifacts, read_json
from tqe.runtime.binder import BindError, bind_document, bind_document_from_path, bind_error_codes
from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import CapabilityCatalog, TacticalQueryDocument, stable_hash

PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
BINDER_REPORT = Path("artifacts/m1.1/binder-validation-report.json")
VERIFY_REPORT = Path("artifacts/m1.1/verification-report.json")
BASELINE_FILES = [
    Path("delivery/m1/baseline/m1-baseline-manifest.json"),
    Path("delivery/m1/baseline/legacy-result-manifest.json"),
    Path("delivery/m1/baseline/evidence-bundle-manifest.json"),
]


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def expect_bind_error(
    *,
    check_id: str,
    document_payload: dict[str, Any],
    expected_code: str,
) -> dict[str, Any]:
    try:
        document = TacticalQueryDocument.model_validate(document_payload)
        bind_document(document)
    except BindError as error:
        codes = sorted(bind_error_codes(error))
        if expected_code in codes:
            return pass_check(
                check_id,
                f"binder rejected invalid plan with {expected_code}",
                {"codes": codes},
            )
        return fail_check(
            check_id,
            f"binder rejected plan, but did not emit {expected_code}",
            {"codes": codes},
        )
    except Exception as error:  # pragma: no cover - defensive report path
        return fail_check(
            check_id,
            f"unexpected exception type {type(error).__name__}",
            {"error": str(error)},
        )
    return fail_check(check_id, f"binder accepted invalid plan; expected {expected_code}")


def load_plan_payload() -> dict[str, Any]:
    return read_json(PLAN_PATH)


def clone_plan_payload() -> dict[str, Any]:
    return deepcopy(load_plan_payload())


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    checks.extend(check_baseline_files())
    checks.extend(check_generated_artifacts())
    checks.extend(check_catalog_metadata())
    checks.extend(check_valid_plan_binding())
    checks.extend(check_invalid_plans())

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    return {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_A_type_system_and_binder",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }


def check_baseline_files() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for path in BASELINE_FILES:
        if path.exists():
            checks.append(pass_check(f"baseline.{path.name}", f"{path} exists"))
        else:
            checks.append(fail_check(f"baseline.{path.name}", f"{path} is missing"))
    return checks


def check_generated_artifacts() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    expected = expected_generated_artifacts()
    for path_text, content in expected.items():
        path = Path(path_text)
        if not path.exists():
            checks.append(fail_check(f"generated.{path.name}", f"{path} is missing"))
            continue
        actual = path.read_text(encoding="utf-8")
        if actual == content:
            checks.append(
                pass_check(
                    f"generated.{path.name}",
                    f"{path} is current",
                    {"sha256": stable_hash(actual)},
                )
            )
        else:
            checks.append(fail_check(f"generated.{path.name}", f"{path} is stale"))

    schema = read_json(Path("generated/tactical-query-plan.schema.json"))
    defs = schema.get("$defs", {})
    required_defs = {
        "RecipeDefinition",
        "QueryInvocation",
        "DraftQueryPlan",
        "BoundQueryPlan",
        "QueryExecution",
    }
    missing = sorted(required_defs - set(defs))
    if missing:
        checks.append(
            fail_check("schema.formal_objects", "schema is missing formal objects", {"missing": missing})
        )
    else:
        checks.append(pass_check("schema.formal_objects", "schema includes all formal objects"))
    return checks


def check_catalog_metadata() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    catalog = default_catalog()
    try:
        CapabilityCatalog.model_validate(catalog.model_dump(mode="json"))
        checks.append(pass_check("catalog.schema", "capability catalog validates"))
    except Exception as error:
        checks.append(fail_check("catalog.schema", "capability catalog failed validation", {"error": str(error)}))

    for entry in [*catalog.primitives, *catalog.relations]:
        if not entry.outputs:
            checks.append(fail_check(f"catalog.{entry.name}.outputs", "entry has no outputs"))
            continue
        if not entry.evidence_fields:
            checks.append(fail_check(f"catalog.{entry.name}.evidence", "entry has no evidence fields"))
        else:
            checks.append(pass_check(f"catalog.{entry.name}.evidence", "entry declares evidence fields"))
        for output in entry.outputs:
            if output.missing_data_semantics is None:
                checks.append(
                    fail_check(
                        f"catalog.{entry.name}.{output.name}.missing_data",
                        "output missing data semantics are undeclared",
                    )
                )
            else:
                checks.append(
                    pass_check(
                        f"catalog.{entry.name}.{output.name}.metadata",
                        "output declares type, unit, cardinality, scope, and missing-data semantics",
                    )
                )
        if not entry.executable:
            checks.append(fail_check(f"catalog.{entry.name}.executable", "entry is not executable"))
        else:
            checks.append(pass_check(f"catalog.{entry.name}.executable", "entry is executable"))
        for parameter in entry.parameters:
            if parameter.required and parameter.default is not None:
                checks.append(
                    fail_check(
                        f"catalog.{entry.name}.{parameter.name}.parameter",
                        "required catalog parameter should not declare a default",
                    )
                )
            else:
                checks.append(
                    pass_check(
                        f"catalog.{entry.name}.{parameter.name}.parameter",
                        "catalog parameter declares type, unit, bounds, and required/default policy",
                    )
                )

    for operator in catalog.operators:
        if operator.version:
            checks.append(pass_check(f"operator.{operator.name}.version", "operator is versioned"))
        else:
            checks.append(fail_check(f"operator.{operator.name}.version", "operator lacks version"))
    return checks


def check_valid_plan_binding() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        bound = bind_document_from_path(PLAN_PATH)
    except BindError as error:
        return [
            fail_check(
                "binder.valid_plan",
                "approved M1 plan failed binding",
                {"issues": [issue.model_dump(mode="json") for issue in error.issues]},
            )
        ]

    checks.append(
        pass_check(
            "binder.valid_plan",
            "approved M1 plan binds",
            {
                "plan_hash": bound.plan_hash,
                "bound_plan_hash": bound.bound_plan_hash,
                "node_count": len(bound.nodes),
            },
        )
    )
    rebound = bind_document_from_path(PLAN_PATH)
    if rebound.plan_hash == bound.plan_hash and rebound.bound_plan_hash == bound.bound_plan_hash:
        checks.append(pass_check("hash.same_process", "plan hashes are stable in-process"))
    else:
        checks.append(fail_check("hash.same_process", "plan hashes changed in-process"))

    script = (
        "from pathlib import Path;"
        "from tqe.runtime.binder import bind_document_from_path;"
        "b=bind_document_from_path(Path('config/query-plans/ball_side_block_shift.ir.v1.json'));"
        "print(b.plan_hash + ' ' + b.bound_plan_hash)"
    )
    output = subprocess.check_output([sys.executable, "-c", script], text=True).strip()
    plan_hash, bound_plan_hash = output.split()
    if plan_hash == bound.plan_hash and bound_plan_hash == bound.bound_plan_hash:
        checks.append(pass_check("hash.cross_process", "plan hashes are stable across processes"))
    else:
        checks.append(
            fail_check(
                "hash.cross_process",
                "plan hashes changed across processes",
                {
                    "expected": [bound.plan_hash, bound.bound_plan_hash],
                    "actual": [plan_hash, bound_plan_hash],
                },
            )
        )
    return checks


def check_invalid_plans() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    payload = clone_plan_payload()
    payload["draft_plan"]["nodes"][1]["catalog_ref"] = "imaginary_primitive"
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_unknown_primitive",
            document_payload=payload,
            expected_code="unknown_catalog_ref",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["nodes"][6]["compare"] = {
        "payload_type": "number",
        "unit": "second",
        "value": 5.0,
    }
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_distance_vs_seconds",
            document_payload=payload,
            expected_code="unit_mismatch",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["nodes"][2]["operator"] = {"name": "count_at_least", "version": "1.0.0"}
    payload["draft_plan"]["nodes"][2]["compare"] = {
        "payload_type": "number",
        "unit": "count",
        "value": 1,
    }
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_count_on_non_collection",
            document_payload=payload,
            expected_code="operator_cardinality_mismatch",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["nodes"] = [
        {
            "kind": "primitive",
            "node_id": "possession",
            "catalog_ref": "possession_segment",
            "version": "0.1.0",
        },
        {
            "kind": "predicate",
            "node_id": "possession_persists",
            "input": {"source_node_id": "possession", "output_name": "episodes"},
            "operator": {"name": "persists_for", "version": "1.0.0"},
            "duration": {"payload_type": "number", "unit": "second", "value": 1.0},
        },
    ]
    payload["draft_plan"]["classification_rules"] = [
        {
            "label": "BAD",
            "predicate_ids": ["possession_persists"],
            "description": "Invalid episode-set persistence fixture.",
        }
    ]
    payload["draft_plan"]["requested_evidence"] = []
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_persists_for_scalar_number",
            document_payload=payload,
            expected_code="operator_temporal_mismatch",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["nodes"][6]["required_entity_scope"] = "player"
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_team_signal_as_player_relation",
            document_payload=payload,
            expected_code="required_entity_scope_mismatch",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["requested_evidence"][1]["field"] = "destination_region"
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_destination_from_frame_signal",
            document_payload=payload,
            expected_code="unsupported_evidence_field",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["complexity_limits"]["max_plan_nodes"] = 1
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_complexity_excess",
            document_payload=payload,
            expected_code="complexity_nodes_exceeded",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["nodes"][2]["input"] = {
        "source_node_id": "missing",
        "output_name": "fraction",
    }
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_unresolved_temporal_reference",
            document_payload=payload,
            expected_code="unresolved_temporal_reference",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["nodes"][5]["parameters"] = {
        "totally_unknown_knob": {"payload_type": "number", "unit": "metre", "value": 99}
    }
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_unknown_node_parameter",
            document_payload=payload,
            expected_code="unknown_node_parameter",
        )
    )

    payload = clone_plan_payload()
    del payload["draft_plan"]["nodes"][5]["inputs"]["entry_episodes"]
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_missing_node_input",
            document_payload=payload,
            expected_code="missing_node_input",
        )
    )

    payload = clone_plan_payload()
    payload["draft_plan"]["classification_rules"] = [
        {
            "label": "NONSENSE",
            "predicate_ids": ["wide_entry_persists"],
            "description": "Invalid label outside recipe outputs.",
        }
    ]
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_classification_label_mismatch",
            document_payload=payload,
            expected_code="classification_label_mismatch",
        )
    )

    return checks


def main() -> int:
    report = build_report()
    write_json(BINDER_REPORT, report)
    write_json(VERIFY_REPORT, report)
    print(f"Wrote {BINDER_REPORT}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
