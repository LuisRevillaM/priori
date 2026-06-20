"""Verify M1.1R Gate R1: explicit plan graph and binder contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.artifacts import read_json
from tqe.runtime.binder import BindError, bind_document, bind_document_from_path, bind_error_codes
from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import BoundCatalogNode, TacticalQueryDocument

APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
EXPERIMENTAL_PLAN_PATH = Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
REPORT_PATH = Path("artifacts/m1.1/gate-r1-verification-report.json")
REMOVED_NOOP_CAPABILITIES = {
    "analysis_rate",
    "robust_team_width",
    "shift_persistence",
    "wide_channel_dwell",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def clone_payload(path: Path) -> dict[str, Any]:
    return deepcopy(read_json(path))


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
            return pass_check(check_id, f"binder rejected invalid plan with {expected_code}", {"codes": codes})
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


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.extend(validate_catalog_contract())
    checks.extend(validate_valid_plans())
    checks.extend(validate_invalid_plan_probes())
    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    return {
        "schema_version": "1.0",
        "milestone": "M1.1R",
        "gate": "Gate_R1_explicit_plan_graph_binder_contracts",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }


def validate_catalog_contract() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    catalog = default_catalog()
    catalog_names = {entry.name for entry in [*catalog.primitives, *catalog.relations]}
    removed_still_exposed = sorted(catalog_names & REMOVED_NOOP_CAPABILITIES)
    checks.append(
        pass_check(
            "catalog.no_noop_capabilities",
            "non-executable no-op capabilities are not exposed",
            {"removed_capabilities": sorted(REMOVED_NOOP_CAPABILITIES)},
        )
        if not removed_still_exposed
        else fail_check(
            "catalog.no_noop_capabilities",
            "non-executable no-op capabilities are still exposed",
            {"exposed": removed_still_exposed},
        )
    )

    for entry in [*catalog.primitives, *catalog.relations]:
        checks.append(
            pass_check(f"catalog.{entry.name}.executable", "catalog entry is executable")
            if entry.executable
            else fail_check(f"catalog.{entry.name}.executable", "catalog entry is not executable")
        )
        if entry.name in {"signed_lateral_shift", "outcome_classification", "geometric_progressive_corridor"}:
            checks.append(
                pass_check(f"catalog.{entry.name}.inputs", "catalog entry declares explicit inputs")
                if entry.inputs
                else fail_check(f"catalog.{entry.name}.inputs", "catalog entry has no explicit inputs")
            )
    return checks


def validate_valid_plans() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for path in [APPROVED_PLAN_PATH, EXPERIMENTAL_PLAN_PATH]:
        try:
            bound = bind_document_from_path(path)
        except BindError as error:
            checks.append(
                fail_check(
                    f"binder.{path.stem}.valid",
                    "plan failed binding",
                    {"issues": [issue.model_dump(mode="json") for issue in error.issues]},
                )
            )
            continue
        catalog_nodes = [node for node in bound.nodes if isinstance(node, BoundCatalogNode)]
        missing_required_bound_inputs = [
            node.node_id
            for node in catalog_nodes
            if node.catalog_ref in {"signed_lateral_shift", "outcome_classification", "geometric_progressive_corridor"}
            and not node.inputs
        ]
        checks.append(
            pass_check(
                f"binder.{path.stem}.valid",
                "plan binds with explicit graph inputs and invocation semantics",
                {
                    "bound_plan_hash": bound.bound_plan_hash,
                    "max_results": bound.max_results,
                    "execution_mode": bound.execution_mode.value,
                    "bound_input_nodes": {
                        node.node_id: sorted(node.inputs)
                        for node in catalog_nodes
                        if node.inputs
                    },
                },
            )
            if not missing_required_bound_inputs
            else fail_check(
                f"binder.{path.stem}.valid",
                "one or more nodes did not retain bound inputs",
                {"missing": missing_required_bound_inputs},
            )
        )
    return checks


def validate_invalid_plan_probes() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    payload = clone_payload(APPROVED_PLAN_PATH)
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

    payload = clone_payload(APPROVED_PLAN_PATH)
    del payload["draft_plan"]["nodes"][5]["inputs"]["entry_episodes"]
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_missing_required_input",
            document_payload=payload,
            expected_code="missing_node_input",
        )
    )

    payload = clone_payload(APPROVED_PLAN_PATH)
    payload["draft_plan"]["nodes"][5]["inputs"]["defensive_centroid"] = {
        "source_node_id": "possession",
        "output_name": "episodes",
    }
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_input_type_mismatch",
            document_payload=payload,
            expected_code="input_payload_mismatch",
        )
    )

    payload = clone_payload(EXPERIMENTAL_PLAN_PATH)
    payload["draft_plan"]["nodes"][10]["parameters"]["minimum_clearance_m"] = {
        "payload_type": "number",
        "unit": "metre",
        "value": -3.0,
    }
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_invalid_parameter_range",
            document_payload=payload,
            expected_code="parameter_below_minimum",
        )
    )

    payload = clone_payload(EXPERIMENTAL_PLAN_PATH)
    payload["draft_plan"]["nodes"][10]["parameters"]["side_filter"] = {
        "payload_type": "enum",
        "unit": "none",
        "value": "diagonal_magic",
    }
    checks.append(
        expect_bind_error(
            check_id="binder.rejects_invalid_parameter_enum",
            document_payload=payload,
            expected_code="parameter_value_not_allowed",
        )
    )

    payload = clone_payload(APPROVED_PLAN_PATH)
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
    write_json(REPORT_PATH, report)
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
