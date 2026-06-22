"""Verify N1C novel-composition proof integrity before Workbench exposure."""

from __future__ import annotations

import json
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tqe.runtime.binder import bind_document
from tqe.runtime.catalog import default_catalog
from tqe.runtime.executor import (
    PeriodState,
    TacticalQueryExecutor,
    runtime_parameters,
)
from tqe.runtime.ir import (
    BoundCatalogNode,
    BoundPredicateNode,
    PayloadType,
    TacticalQueryDocument,
    TemporalContainer,
    canonical_json,
)
from tqe.runtime.values import FrameSignal, runtime_value_from_raw
from tqe.verification.n1b import (
    corrected_document,
    runtime_parameter_access_contract,
)
from tqe.workshop.m1_2 import write_json


HERO_QUESTION = (
    "Show possessions where a progressive corridor opens within four seconds of possession starting, "
    "remains available for at least 0.8 seconds, and the ball enters that corridor's destination region "
    "within five seconds of the corridor opening."
)
N1C_PROOF_RECORDED_AT = "2026-06-22T15:15:37-07:00"
N1C_ROOT = Path("artifacts/n1c")
MANIFEST_PATH = N1C_ROOT / "n1c-canonical-freeze-manifest.json"
REPORT_PATH = N1C_ROOT / "n1c-verification-report.json"
FREEZE_PATH = Path("delivery/m1.2/frontier-runtime-freeze.json")
KNOWLEDGE_PACK_PATH = Path("generated/tactical-knowledge-pack.json")
CAPABILITY_CONTEXT_PATH = Path("generated/capability-context.json")
DEMO_DATA_MANIFEST_PATH = Path("config/deploy/demo-data-manifest.json")
CANONICAL_DATA_ROOT = Path("data/canonical/v1")
N1_DRAFT_PATH = Path("artifacts/m1.2/workshop/handles/draft-plans/draft_26912b2c452106e8.json")
N1_BOUND_PATH = Path("artifacts/m1.2/workshop/handles/bound-plans/bound_f619f6c9677a4d2a.json")
N1_EXECUTION_PATH = Path("artifacts/m1.2/workshop/handles/executions/exec_5466f201a479ba0f.json")
N1_REPLAY_PATH = Path("artifacts/m1.2/workshop/handles/replay-windows/replay_63574966cd34b86d.json")
N1_STRUCTURAL_PATH = Path("artifacts/n1b/n1-post-n1b-hero-structural-novelty-report.json")
N1_EXECUTION_REPORT_PATH = Path("artifacts/n1b/n1-post-n1b-hero-execution-report.json")
N1_INSPECTION_REPORT_PATH = Path("artifacts/n1b/n1-post-n1b-hero-inspection-report.json")


def main() -> None:
    N1C_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    write_json(MANIFEST_PATH, manifest)
    tri_state = relation_destination_entry_tri_state_fixture()
    enum_contract = declared_enum_output_contract()
    context_contract = runtime_parameter_access_contract()
    checks = [
        check(
            "n1c.manifest_written",
            MANIFEST_PATH.exists() and required_manifest_fields_present(manifest),
            "Canonical N1C freeze manifest exists and contains required identity fields.",
            {"manifest_path": str(MANIFEST_PATH), "manifest_sha256": file_sha256(MANIFEST_PATH)},
        ),
        check(
            "n1c.knowledge_pack_hashes_reconciled",
            manifest["knowledge_pack"]["file_sha256"] == file_sha256(KNOWLEDGE_PACK_PATH)
            and manifest["knowledge_pack"]["semantic_sha256"] == read_json(KNOWLEDGE_PACK_PATH).get("knowledge_pack_sha256"),
            "Knowledge-pack file and semantic hashes are both recorded and match current artifacts.",
            manifest["knowledge_pack"],
        ),
        check(
            "n1c.entry_status_pass_fail_unknown_exercised",
            tri_state["entry_statuses"] == {
                "after_open_pass": "PASS",
                "fail": "FAIL",
                "present_at_open_pass": "PASS",
                "unknown": "UNKNOWN",
            },
            "Generic relation_destination_entry emits PASS, FAIL, and UNKNOWN through actual node execution.",
            tri_state,
        ),
        check(
            "n1c.eq_pass_preserves_unknown",
            tri_state["predicate_values_by_case"].get("unknown") is None
            and tri_state["predicate_unknown_mask_by_case"].get("unknown") is True,
            "entry_status == PASS preserves UNKNOWN rather than converting it to false.",
            tri_state,
        ),
        check(
            "n1c.entry_mode_emitted",
            {
                "PRESENT_AT_OPEN",
                "ENTERED_AFTER_OPEN",
                "NOT_ENTERED",
                "UNKNOWN",
            }.issubset(set(tri_state["entry_modes"].values())),
            "Destination-entry records carry honest entry_mode evidence.",
            tri_state,
        ),
        check(
            "n1c.executor_runtime_parameters_declared",
            not context_contract["undeclared_accesses"],
            "Every executor RuntimeParameters access is supplied by host defaults or checked-in recipe parameters.",
            context_contract,
        ),
        check(
            "n1c.declared_enum_outputs_enforced",
            enum_contract["all_declared_domains_enforced"],
            "Every catalog output with declared enum allowed_values rejects out-of-domain runtime values.",
            enum_contract,
        ),
        check(
            "n1c.live_artifacts_referenced",
            all(item.get("sha256") for item in manifest["n1_live_artifacts"].values()),
            "Canonical manifest references the live draft, bound plan, execution, result, and replay artifacts.",
            manifest["n1_live_artifacts"],
        ),
    ]
    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
    }
    report = {
        "schema_version": "n1c.verification.v1",
        "generated_at": N1C_PROOF_RECORDED_AT,
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "manifest_path": str(MANIFEST_PATH),
        "manifest_sha256": file_sha256(MANIFEST_PATH),
        "tri_state_fixture": tri_state,
        "runtime_context_contract": context_contract,
        "declared_enum_output_contract": enum_contract,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    print(json.dumps({"status": report["status"], "summary": summary}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


def build_manifest() -> dict[str, Any]:
    freeze = read_json(FREEZE_PATH)
    structural = read_json(N1_STRUCTURAL_PATH)
    execution = read_json(N1_EXECUTION_REPORT_PATH)
    inspection = read_json(N1_INSPECTION_REPORT_PATH)
    knowledge_pack = read_json(KNOWLEDGE_PACK_PATH)
    tool_allowlist = freeze["mcp_boundary"]["tool_allowlist"]
    first_result = inspection["inspection"]["result"]
    replay = inspection["replay_window"]
    return {
        "schema_version": "n1c.canonical_freeze_manifest.v1",
        "generated_at": N1C_PROOF_RECORDED_AT,
        "source": {
            "commit_at_manifest_generation": git_output("rev-parse", "HEAD"),
            "source_files": {
                "runtime_executor": file_identity(Path("src/tqe/runtime/executor.py")),
                "runtime_catalog": file_identity(Path("src/tqe/runtime/catalog.py")),
                "runtime_binder": file_identity(Path("src/tqe/runtime/binder.py")),
                "runtime_values": file_identity(Path("src/tqe/runtime/values.py")),
                "workshop_service": file_identity(Path("src/tqe/workshop/m1_2.py")),
                "mcp_server": file_identity(Path("src/tqe/workshop/mcp_server.py")),
            },
        },
        "knowledge_pack": {
            "path": str(KNOWLEDGE_PACK_PATH),
            "file_sha256": file_sha256(KNOWLEDGE_PACK_PATH),
            "semantic_sha256": str(knowledge_pack.get("knowledge_pack_sha256")),
            "capability_context": file_identity(CAPABILITY_CONTEXT_PATH),
        },
        "hermes": {
            "provider": freeze["selected_product_route"].get("provider"),
            "configured_model": freeze["selected_product_route"].get("configured_model"),
            "reasoning_effort": freeze["selected_product_route"].get("reasoning_effort"),
            "version": freeze["selected_product_route"].get("hermes_version"),
            "config_sha256": freeze["selected_product_route"].get("hermes_config_sha256"),
            "system_instruction_sha256_values": freeze["s2id_unseeded_proof"].get("system_instruction_sha256_values"),
        },
        "mcp": {
            "server_name": "priori_tactical",
            "adapter": file_identity(Path("src/tqe/workshop/mcp_server.py")),
            "tool_allowlist": tool_allowlist,
            "tool_allowlist_sha256": stable_json_sha256(tool_allowlist),
        },
        "hero_question": {
            "text": HERO_QUESTION,
            "sha256": sha256(HERO_QUESTION.encode("utf-8")).hexdigest(),
        },
        "n1_live_artifacts": {
            "draft_plan": file_identity(N1_DRAFT_PATH),
            "bound_plan": file_identity(N1_BOUND_PATH),
            "execution_handle": file_identity(N1_EXECUTION_PATH),
            "replay_window": file_identity(N1_REPLAY_PATH),
            "structural_novelty_report": file_identity(N1_STRUCTURAL_PATH),
            "execution_report": file_identity(N1_EXECUTION_REPORT_PATH),
            "inspection_report": file_identity(N1_INSPECTION_REPORT_PATH),
        },
        "n1_live_identity": {
            "session_id": structural.get("session_id"),
            "draft_plan_id": structural.get("draft_plan_id"),
            "draft_plan_hash": execution["execution"].get("draft_plan_hash"),
            "bound_plan_id": structural.get("bound_plan_id"),
            "bound_plan_hash": execution.get("bound_plan_hash"),
            "structural_fingerprint": structural["live_structural_fingerprint"]["fingerprint_hash"],
            "execution_id": execution["execution"].get("execution_id"),
            "result_id": first_result.get("result_id"),
            "replay_window_id": replay.get("replay_window_id"),
            "cache_status_first_execution": "MISS",
            "cache_status_after_execution": "HIT",
        },
        "runtime": {
            "compatibility_profile": execution["execution"].get("compatibility_profile"),
            "executor_sha256": file_sha256(Path("src/tqe/runtime/executor.py")),
            "catalog_sha256": file_sha256(Path("src/tqe/runtime/catalog.py")),
            "binder_sha256": file_sha256(Path("src/tqe/runtime/binder.py")),
            "values_sha256": file_sha256(Path("src/tqe/runtime/values.py")),
        },
        "data": {
            "deploy_manifest": file_identity(DEMO_DATA_MANIFEST_PATH),
            "canonical_root": str(CANONICAL_DATA_ROOT),
            "canonical_inventory_sha256": canonical_data_inventory_sha256(CANONICAL_DATA_ROOT),
        },
    }


def relation_destination_entry_tri_state_fixture() -> dict[str, Any]:
    document = corrected_document()
    document["default_invocation"].setdefault("parameters", {})["destination_entry_horizon_seconds"] = {
        "payload_type": "number",
        "unit": "second",
        "value": 0.4,
    }
    bound = bind_document(TacticalQueryDocument.model_validate(document))
    destination_node = next(
        node
        for node in bound.nodes
        if (
            isinstance(node, BoundCatalogNode)
            and node.catalog_ref == "relation_destination_entry"
            and node.outputs
            and node.outputs[0].name == "entry_status"
        )
    )
    predicate_node = next(
        node
        for node in bound.nodes
        if isinstance(node, BoundPredicateNode)
        and node.input.source_node_id == destination_node.node_id
        and node.input.output_name == "entry_status"
    )
    relation_ref = destination_node.inputs["relation_episodes"]
    relation_node = next(
        node
        for node in bound.nodes
        if isinstance(node, BoundCatalogNode) and node.node_id == relation_ref.source_node_id
    )
    relation_output = next(output for output in relation_node.outputs if output.name == relation_ref.output_name)
    cases = [
        ("present_at_open_pass", 100, {frame_id: 40.0 for frame_id in range(100, 111)} | {100: 5.0}),
        ("after_open_pass", 150, {frame_id: 40.0 for frame_id in range(150, 161)} | {153: 5.0}),
        ("fail", 200, {frame_id: 40.0 for frame_id in range(200, 211)}),
        ("unknown", 300, {frame_id: 40.0 for frame_id in range(300, 311) if frame_id != 305}),
    ]
    ball_points: dict[int, float] = {}
    for _case_id, _open_frame_id, points in cases:
        ball_points.update(points)
    episodes = [relation_episode_for_case(case_id, open_frame_id) for case_id, open_frame_id, _points in cases]
    state = PeriodState(
        match_id="N1C_FIXTURE",
        period="firstHalf",
        params=runtime_parameters(bound),
        recipe_id=bound.recipe_id,
        recipe_version=bound.recipe_version,
        perspective_team_role="home",
        perspective_team_id="fixture_home",
        defending_team_role="away",
        defending_team_id="fixture_away",
        canonical_root=Path("."),
        raw_tracking=Path("."),
        positions=pd.DataFrame(
            [
                {
                    "frame_id": frame_id,
                    "entity_type": "ball",
                    "entity_id": "ball",
                    "team_id": "BALL",
                    "team_role": "ball",
                    "x_m": 0.0,
                    "y_m": y_m,
                }
                for frame_id, y_m in sorted(ball_points.items())
            ]
        ),
        frame_ids=np.array(list(range(100, 311)), dtype=np.int64),
        ball_y=np.array([ball_points.get(frame_id, np.nan) for frame_id in range(100, 311)]),
        possession_role=np.array(["home" for _frame_id in range(100, 311)], dtype=object),
        ball_alive=np.array([True for _frame_id in range(100, 311)], dtype=bool),
        defender_count=pd.Series(dtype="int64"),
        defender_centroid_y=pd.Series(dtype="float64"),
        runtime_values={
            relation_ref.source_node_id: {
                relation_ref.output_name: runtime_value_from_raw(
                    node_id=relation_ref.source_node_id,
                    output=relation_output,
                    raw_value=episodes,
                    records=episodes,
                )
            }
        },
    )
    executor = TacticalQueryExecutor()
    executor._execute_node(state=state, node=destination_node)
    executor._execute_node(state=state, node=predicate_node)
    entry_value = state.runtime_values[destination_node.node_id]["entry_status"]
    predicate_signal = state.runtime_values[predicate_node.node_id]["predicate"].value
    records_by_case = {
        str(record["base_result_id"]).removeprefix("source_"): record
        for record in entry_value.records
    }
    predicate_values_by_case: dict[str, bool | None] = {}
    predicate_unknown_mask_by_case: dict[str, bool] = {}
    for index, record in enumerate(entry_value.records):
        case_id = str(record["base_result_id"]).removeprefix("source_")
        predicate_values_by_case[case_id] = predicate_signal.values[index]
        predicate_unknown_mask_by_case[case_id] = predicate_signal.unknown_mask[index]
    return {
        "entry_statuses": {
            case_id: str(record.get("entry_status"))
            for case_id, record in sorted(records_by_case.items())
        },
        "entry_modes": {
            case_id: str(record.get("entry_mode"))
            for case_id, record in sorted(records_by_case.items())
        },
        "time_to_entry_seconds": {
            case_id: record.get("time_to_entry_seconds")
            for case_id, record in sorted(records_by_case.items())
        },
        "predicate_values_by_case": dict(sorted(predicate_values_by_case.items())),
        "predicate_unknown_mask_by_case": dict(sorted(predicate_unknown_mask_by_case.items())),
        "entry_signal_values": entry_value.value.values,
        "entry_signal_unknown_mask": entry_value.value.unknown_mask,
        "predicate_signal_values": predicate_signal.values,
        "predicate_signal_unknown_mask": predicate_signal.unknown_mask,
    }


def relation_episode_for_case(case_id: str, open_frame_id: int) -> dict[str, Any]:
    close_frame_id = open_frame_id + 10
    source_result = {
        "result_id": f"source_{case_id}",
        "match_id": "N1C_FIXTURE",
        "period": "firstHalf",
        "anchor_id": f"anchor_{case_id}",
        "anchor_frame_id": open_frame_id,
        "replay_start_frame_id": open_frame_id - 5,
        "replay_end_frame_id": close_frame_id + 5,
        "classification": "FIXTURE_SOURCE",
    }
    return {
        "relation_id": f"relation_{case_id}",
        "relation_version": "fixture",
        "relation_anchor_source": "n1c_fixture",
        "source_result": source_result,
        "open_frame_id": open_frame_id,
        "open_confirm_frame_id": open_frame_id + 1,
        "close_frame_id": close_frame_id,
        "duration_seconds": 0.4,
        "target_player_id": f"target_{case_id}",
        "minimum_clearance_m": 3.0,
        "limiting_defender_id": f"defender_{case_id}",
        "destination_side": "left",
        "destination_lane": "wide",
        "destination_region": "left_wide",
        "destination_region_type": "side_lane_band",
        "destination_region_bounds": {"min_y_m": 0.0, "max_y_m": 10.0},
        "source_open_point": {"x_m": 0.0, "y_m": 30.0},
        "target_open_point": {"x_m": 12.0, "y_m": 5.0},
        "source_close_point": {"x_m": 0.0, "y_m": 30.0},
        "target_close_point": {"x_m": 12.0, "y_m": 5.0},
    }


def declared_enum_output_contract() -> dict[str, Any]:
    checked: list[dict[str, Any]] = []
    for entry in [*default_catalog().primitives, *default_catalog().relations]:
        for output in entry.outputs:
            if output.payload_type != PayloadType.ENUM or output.allowed_values is None:
                continue
            accepted = False
            rejected = False
            try:
                runtime_value_from_raw(
                    node_id=f"{entry.name}_fixture",
                    output=output,
                    raw_value=FrameSignal(
                        frame_ids=[1],
                        values=[output.allowed_values[0]],
                        unknown_mask=[False],
                        unit=output.unit,
                        entity_scope=output.entity_scope,
                    )
                    if output.temporal_type == TemporalContainer.FRAME_SIGNAL
                    else output.allowed_values[0],
                )
                accepted = True
            except RuntimeError:
                accepted = False
            try:
                runtime_value_from_raw(
                    node_id=f"{entry.name}_fixture",
                    output=output,
                    raw_value=FrameSignal(
                        frame_ids=[1],
                        values=["__OUTSIDE_DECLARED_DOMAIN__"],
                        unknown_mask=[False],
                        unit=output.unit,
                        entity_scope=output.entity_scope,
                    )
                    if output.temporal_type == TemporalContainer.FRAME_SIGNAL
                    else "__OUTSIDE_DECLARED_DOMAIN__",
                )
            except RuntimeError:
                rejected = True
            checked.append(
                {
                    "capability": entry.name,
                    "output": output.name,
                    "allowed_values": list(output.allowed_values),
                    "valid_value_accepted": accepted,
                    "invalid_value_rejected": rejected,
                }
            )
    return {
        "checked_outputs": checked,
        "all_declared_domains_enforced": bool(checked)
        and all(item["valid_value_accepted"] and item["invalid_value_rejected"] for item in checked),
        "scope": "Only enum outputs with explicit allowed_values are domain-enforced.",
    }


def required_manifest_fields_present(manifest: dict[str, Any]) -> bool:
    required_paths = [
        ("source", "commit_at_manifest_generation"),
        ("knowledge_pack", "file_sha256"),
        ("knowledge_pack", "semantic_sha256"),
        ("hermes", "version"),
        ("hermes", "config_sha256"),
        ("hermes", "provider"),
        ("hermes", "configured_model"),
        ("hermes", "reasoning_effort"),
        ("mcp", "tool_allowlist_sha256"),
        ("hero_question", "sha256"),
        ("n1_live_identity", "draft_plan_hash"),
        ("n1_live_identity", "bound_plan_hash"),
        ("n1_live_identity", "structural_fingerprint"),
        ("runtime", "executor_sha256"),
        ("data", "deploy_manifest"),
        ("data", "canonical_inventory_sha256"),
    ]
    for first, second in required_paths:
        value = manifest.get(first, {}).get(second)
        if not value:
            return False
    return True


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() else "",
    }


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def stable_json_sha256(payload: Any) -> str:
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def canonical_data_inventory_sha256(root: Path) -> str:
    inventory: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        inventory.append(
            {
                "path": str(path.relative_to(root)),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return stable_json_sha256(inventory)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git_output(*args: str) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True, timeout=20)
    return result.stdout.strip()


def check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "pass" if passed else "fail",
        "message": message,
        "details": details or {},
    }


if __name__ == "__main__":
    main()
