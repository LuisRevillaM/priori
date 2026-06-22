"""Verify M1.2 S2I-A Tactical Knowledge Pack artifacts."""

from __future__ import annotations

from pathlib import Path

from tqe.workshop.knowledge_pack import (
    PACK_JSON_PATH,
    PACK_MD_PATH,
    verify_tactical_knowledge_pack,
    write_json,
    write_tactical_knowledge_pack,
)
from tqe.runtime.binder import bind_document
from tqe.runtime.ir import TacticalQueryDocument
from tqe.workshop.m1_2 import (
    CallerProfile,
    CapabilityGap,
    describe_capability,
    read_json,
    utc_now_iso,
    validate_safe_agent_plan,
)


REPORT_PATH = Path("artifacts/m1.2/gate-s2i-verification-report.json")


def main() -> None:
    pack = write_tactical_knowledge_pack(PACK_JSON_PATH, PACK_MD_PATH)
    checks = verify_tactical_knowledge_pack(PACK_JSON_PATH, PACK_MD_PATH)
    checks.extend(executable_plan_contract_checks())
    report = {
        "schema_version": "1.0",
        "gate": "S2I_A_tactical_knowledge_pack",
        "generated_at": utc_now_iso(),
        "knowledge_pack_path": str(PACK_JSON_PATH),
        "knowledge_pack_markdown_path": str(PACK_MD_PATH),
        "knowledge_pack_sha256": pack["knowledge_pack_sha256"],
        "checks": checks,
        "passed": all(item["ok"] for item in checks),
    }
    write_json(REPORT_PATH, report)
    passed = sum(1 for item in checks if item["ok"])
    failed = len(checks) - passed
    print(f"S2I-A verification: {passed} passed, {failed} failed")
    print(f"Report: {REPORT_PATH}")
    if not report["passed"]:
        raise SystemExit(1)


def executable_plan_contract_checks() -> list[dict[str, object]]:
    capability = describe_capability("possession_corridor_availability_v1", CallerProfile.HERMES_S2I_MCP)
    contract = capability.get("authoring_contract", {})
    invocation_contract = contract.get("default_invocation_contract", {})
    constraints = contract.get("constraints", [])
    bind_only_rejected = False
    try:
        document = read_json(Path("config/query-plans/possession_corridor_availability.experimental.v1.json"))
        document["default_invocation"] = dict(document["default_invocation"], execution_mode="bind_only")
        bound = bind_document(TacticalQueryDocument.model_validate(document))
        validate_safe_agent_plan(bound, caller_profile=CallerProfile.HERMES_S2I_MCP)
    except CapabilityGap:
        bind_only_rejected = True
    return [
        {
            "name": "capability_contract.hermes_authors_execute_mode",
            "ok": invocation_contract.get("execution_mode") == "execute",
            "details": invocation_contract,
        },
        {
            "name": "capability_contract.validation_is_non_executing",
            "ok": "validate_query_plan binds and checks the plan but never executes it."
            == invocation_contract.get("validation_contract"),
            "details": invocation_contract,
        },
        {
            "name": "capability_contract.constraints_keep_host_executable",
            "ok": any("execution_mode=execute" in str(item) for item in constraints),
            "details": {"constraints": constraints},
        },
        {
            "name": "validator.rejects_hermes_bind_only_plan",
            "ok": bind_only_rejected,
            "details": {},
        },
    ]


if __name__ == "__main__":
    main()
