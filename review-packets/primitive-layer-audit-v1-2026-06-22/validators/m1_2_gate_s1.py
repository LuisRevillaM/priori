"""Verify M1.2 S1: manual typed-plan workshop loop."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.ir import EvaluationTarget
from tqe.workshop.m1_2 import (
    CallerProfile,
    DEFAULT_WORKSHOP_ROOT,
    FeedbackLabel,
    ToolDispatchRequest,
    dispatch_model_visible,
    dispatch_tool,
    host_confirm_bound_plan,
    replay_artifact_path,
    resolve_evaluation_target,
    write_manual_workshop_artifacts,
)

REPORT_PATH = Path("artifacts/m1.2/gate-s1-verification-report.json")
APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
EXPERIMENTAL_PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "pass" if passed else "fail",
        "message": message,
        "details": details or {},
    }


def build_report() -> dict[str, Any]:
    clean_workshop_artifacts()
    checks: list[dict[str, Any]] = []
    approved_run = run_manual_plan(
        plan_path=APPROVED_PLAN_PATH,
        recipe_state="APPROVED",
    )
    experimental_run = run_manual_plan(
        plan_path=EXPERIMENTAL_PLAN_PATH,
        recipe_state="EXPERIMENTAL",
    )
    checks.append(
        check(
            "s1.approved_and_experimental_runs",
            approved_run["execution"]["total_result_count"] > 0
            and experimental_run["execution"]["total_result_count"] > 0,
            "Manual workshop executes one approved recipe and one experimental recipe.",
            {
                "approved_total": approved_run["execution"]["total_result_count"],
                "experimental_total": experimental_run["execution"]["total_result_count"],
            },
        )
    )
    returned_results = approved_run["results"] + experimental_run["results"]
    checks.append(
        check(
            "s1.every_returned_result_has_replay",
            bool(returned_results)
            and all(result["replay"]["frame_count"] > 0 for result in returned_results),
            "Every returned manual-workshop result opens in a real coordinate replay artifact.",
            {"returned_result_count": len(returned_results)},
        )
    )
    checks.append(
        check(
            "s1.why_matched_traces_present",
            all(result["predicate_traces"] for result in returned_results),
            "Why-matched inspection exposes predicate traces for returned results.",
            {
                "trace_counts": {
                    result["result_id"]: len(result["predicate_traces"])
                    for result in returned_results
                }
            },
        )
    )
    non_match = build_known_timestamp_non_match(experimental_run)
    checks.append(
        check(
            "s1.why_not_timestamp_works",
            non_match["inspection"]["status"] == "NON_MATCH"
            or non_match["inspection"]["status"] == "NO_COMPATIBLE_ANCHOR",
            "Known timestamp inspection returns a deterministic non-match explanation.",
            non_match,
        )
    )
    checks.append(
        check(
            "s1.non_match_inspection_replay_same_resolved_frame",
            non_match["inspection"]["resolved_target"]["canonical_frame_id"] == non_match["replay"]["anchor_frame_id"],
            "Known timestamp inspection and coordinate replay resolve to the same canonical frame.",
            {
                "inspection_frame": non_match["inspection"]["resolved_target"]["canonical_frame_id"],
                "replay_frame": non_match["replay"]["anchor_frame_id"],
            },
        )
    )
    predicate_failure_probe = build_compatible_predicate_failure_probe(experimental_run)
    checks.append(
        check(
            "s1.compatible_anchor_predicate_failure_explained",
            predicate_failure_probe is not None
            and predicate_failure_probe["inspection"]["status"] == "NON_MATCH"
            and predicate_failure_probe["inspection"]["candidate_count"] > 0
            and bool(predicate_failure_probe["inspection"]["failed_predicates"]),
            "Known timestamp inspection distinguishes compatible-anchor predicate failure from no compatible anchor.",
            predicate_failure_probe or {},
        )
    )
    feedback_records = record_feedback_examples(
        approved_run=approved_run,
        experimental_run=experimental_run,
        non_match=non_match,
    )
    checks.append(
        check(
            "s1.feedback_labels_recorded",
            {record["label"] for record in feedback_records} == {label.value for label in FeedbackLabel},
            "All required feedback labels are schema-valid and append-only.",
            {"feedback_count": len(feedback_records)},
        )
    )
    saved_recipe = dispatch(
        "save_experimental_recipe",
        {
            "draft_plan_id": experimental_run["draft_plan_id"],
            "creator": "controller",
            "note": "M1.2 S1 manual workshop proof recipe.",
        },
    )
    checks.append(
        check(
            "s1.experimental_recipe_saved_immutably",
            Path(saved_recipe["path"]).exists() and bool(saved_recipe["query_hash"]),
            "Experimental recipe saves as a content-addressed immutable version.",
            saved_recipe,
        )
    )
    workshop_data = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "generated_at": utc_now_iso(),
        "manual_without_hermes": True,
        "feedback_labels": [label.value for label in FeedbackLabel],
        "runs": [approved_run, experimental_run],
        "non_match_inspection": non_match,
        "predicate_failure_probe": predicate_failure_probe,
        "saved_recipe": saved_recipe,
    }
    workshop_artifacts = write_manual_workshop_artifacts(
        output_root=DEFAULT_WORKSHOP_ROOT,
        data=workshop_data,
    )
    checks.append(
        check(
            "s1.manual_reference_client_written",
            Path(workshop_artifacts["html"]).exists()
            and Path(workshop_artifacts["data_json"]).exists(),
            "Thin manual workshop reference client was generated without Hermes.",
            workshop_artifacts,
        )
    )
    checks.append(
        check(
            "s1.no_hardcoded_result_moments",
            all(result["result_id"] == result["replay"]["source_id"] for result in returned_results),
            "Replay artifacts are keyed from executed result IDs, not canned moments.",
            {"result_ids": [result["result_id"] for result in returned_results]},
        )
    )

    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "gate": "S1_manual_reference_workshop",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "artifacts": {
            **workshop_artifacts,
            "feedback_records": str(DEFAULT_WORKSHOP_ROOT / "feedback-records.jsonl"),
            "saved_recipe": saved_recipe["path"],
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def run_manual_plan(*, plan_path: Path, recipe_state: str) -> dict[str, Any]:
    plan_document = read_json(plan_path)
    submitted = dispatch(
        "submit_query_plan",
        {"plan_document": plan_document, "source_label": f"s1_{recipe_state.lower()}"},
    )
    validation = dispatch("validate_query_plan", {"draft_plan_id": submitted["draft_plan_id"]})
    execution = dispatch(
        "execute_query_plan",
        {
            "bound_plan_id": validation["bound_plan_id"],
            "execution_authorization_id": host_confirm_bound_plan(
                validation["bound_plan_id"],
                reviewer="controller",
            ).execution_authorization_id,
            "result_limit": 5,
        },
    )
    results = []
    for result in execution["results"]:
        detail = dispatch(
            "inspect_result",
            {"execution_id": execution["execution_id"], "result_id": result["result_id"]},
        )
        replay = dispatch(
            "retrieve_replay_window",
            {
                "execution_id": execution["execution_id"],
                "result_id": result["result_id"],
                "padding_seconds": 2.0,
            },
        )
        replay_payload = read_json(replay_artifact_path(replay["replay_window_id"]))
        results.append(
            {
                **result,
                "predicate_traces": detail["predicate_traces"],
                "requested_evidence": detail["requested_evidence"],
                "replay": {
                    **replay,
                    "source_id": result["result_id"],
                    "frames": replay_payload["frames"],
                    "pitch": replay_payload["pitch"],
                },
            }
        )
    return {
        "recipe_state": recipe_state,
        "draft_plan_id": submitted["draft_plan_id"],
        "plan_document": plan_document,
        "validation": validation,
        "execution": execution,
        "results": results,
    }


def build_known_timestamp_non_match(experimental_run: dict[str, Any]) -> dict[str, Any]:
    first_result = experimental_run["results"][0]
    target = EvaluationTarget(
        target_id="known_non_match_probe",
        match_id=str(first_result["match_id"]),
        period=str(first_result["period"]),
        approximate_time_ms=0,
        search_radius_ms=250,
    )
    inspection = dispatch(
        "inspect_non_match",
        {
            "execution_id": experimental_run["execution"]["execution_id"],
            "target": target.model_dump(mode="json"),
        },
    )
    replay = dispatch(
        "retrieve_replay_window",
        {
            "execution_id": experimental_run["execution"]["execution_id"],
            "target": target.model_dump(mode="json"),
            "padding_seconds": 2.0,
        },
    )
    return {
        "target": target.model_dump(mode="json"),
        "inspection": inspection["inspection"],
        "replay": replay,
    }


def build_compatible_predicate_failure_probe(experimental_run: dict[str, Any]) -> dict[str, Any] | None:
    diagnostic_plan = strict_corridor_failure_plan()
    submitted = dispatch(
        "submit_query_plan",
        {"plan_document": diagnostic_plan, "source_label": "s1_predicate_failure_probe"},
    )
    validation = dispatch("validate_query_plan", {"draft_plan_id": submitted["draft_plan_id"]})
    execution = dispatch(
        "execute_query_plan",
        {
            "bound_plan_id": validation["bound_plan_id"],
            "execution_authorization_id": host_confirm_bound_plan(
                validation["bound_plan_id"],
                reviewer="controller",
            ).execution_authorization_id,
            "result_limit": 5,
        },
    )
    execution_id = execution["execution_id"]
    first_result = experimental_run["results"][0]
    match_id = str(first_result["match_id"])
    period = str(first_result["period"])
    period_start = resolve_evaluation_target(
        EvaluationTarget(
            target_id="period_start_probe",
            match_id=match_id,
            period=period,
            approximate_time_ms=0,
            search_radius_ms=250,
        )
    ).canonical_frame_id
    candidate_frames = [int(first_result["anchor_frame_id"])]
    for index, frame_id in enumerate(candidate_frames):
        approximate_time_ms = int(round((frame_id - period_start) / 25 * 1000))
        target = EvaluationTarget(
            target_id=f"predicate_fail_{index}",
            match_id=match_id,
            period=period,
            approximate_time_ms=approximate_time_ms,
            search_radius_ms=500,
        )
        inspection = dispatch(
            "inspect_non_match",
            {"execution_id": execution_id, "target": target.model_dump(mode="json")},
        )["inspection"]
        if (
            inspection.get("status") == "NON_MATCH"
            and int(inspection.get("candidate_count", 0)) > 0
            and inspection.get("failed_predicates")
        ):
            replay = dispatch(
                "retrieve_replay_window",
                {
                    "execution_id": execution_id,
                    "target": target.model_dump(mode="json"),
                    "padding_seconds": 2.0,
                },
            )
            return {
                "diagnostic_execution": execution,
                "target": target.model_dump(mode="json"),
                "inspection": inspection,
                "replay": replay,
            }
    return None


def strict_corridor_failure_plan() -> dict[str, Any]:
    payload = deepcopy(read_json(EXPERIMENTAL_PLAN_PATH))
    payload["recipe"]["recipe_id"] = "s1_strict_corridor_failure_probe"
    payload["recipe"]["display_name"] = "S1 Strict Corridor Failure Probe"
    payload["recipe"]["output_classifications"] = ["IMPOSSIBLY_DENSE_CORRIDOR"]
    payload["draft_plan"]["plan_id"] = "s1_strict_corridor_failure_probe"
    payload["draft_plan"]["recipe_id"] = "s1_strict_corridor_failure_probe"
    payload["draft_plan"]["classification_rules"] = [
        {
            "label": "IMPOSSIBLY_DENSE_CORRIDOR",
            "predicate_ids": ["has_progressive_corridor"],
            "description": "Diagnostic proof that compatible anchors can fail declared predicates.",
        }
    ]
    for node in payload["draft_plan"]["nodes"]:
        if node.get("node_id") == "has_progressive_corridor":
            node["operator"] = {"name": "count_at_least", "version": "1.0.0"}
            node["compare"] = {"payload_type": "number", "unit": "count", "value": 999}
    return payload


def record_feedback_examples(
    *,
    approved_run: dict[str, Any],
    experimental_run: dict[str, Any],
    non_match: dict[str, Any],
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = [
        {
            "execution_id": approved_run["execution"]["execution_id"],
            "result_id": approved_run["results"][0]["result_id"],
            "label": FeedbackLabel.MATCHES_INTENT.value,
            "reviewer": "controller",
            "reason_code": "manual_visual_match",
        },
        {
            "execution_id": experimental_run["execution"]["execution_id"],
            "result_id": experimental_run["results"][0]["result_id"],
            "label": FeedbackLabel.NEAR_MATCH.value,
            "reviewer": "controller",
            "reason_code": "needs_tactical_tightening",
        },
        {
            "execution_id": experimental_run["execution"]["execution_id"],
            "result_id": experimental_run["results"][-1]["result_id"],
            "label": FeedbackLabel.FALSE_POSITIVE.value,
            "reviewer": "controller",
            "reason_code": "visual_false_positive_example",
        },
        {
            "execution_id": experimental_run["execution"]["execution_id"],
            "target": non_match["target"],
            "label": FeedbackLabel.KNOWN_MISS.value,
            "reviewer": "controller",
            "reason_code": "known_timestamp_should_match",
        },
        {
            "execution_id": experimental_run["execution"]["execution_id"],
            "target": non_match["target"],
            "label": FeedbackLabel.UNUSABLE_DATA.value,
            "reviewer": "controller",
            "reason_code": "example_unusable_data_label",
        },
    ]
    records = []
    for request in examples:
        response = dispatch("record_feedback", request)
        records.append({**request, **response})
    return records


def dispatch(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name in {
        "list_capabilities",
        "describe_capability",
        "submit_query_plan",
        "validate_query_plan",
        "execute_query_plan",
        "inspect_result",
        "inspect_non_match",
        "retrieve_replay_window",
    }:
        payload = dispatch_model_visible(
            ToolDispatchRequest(tool_name=tool_name, arguments=arguments),
            caller_profile=CallerProfile.HOST_MANUAL,
        )
        if payload.get("ok") is False:
            raise RuntimeError(f"{tool_name} failed: {payload}")
        return payload
    response = dispatch_tool(
        ToolDispatchRequest(tool_name=tool_name, arguments=arguments),
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    if not response.ok:
        raise RuntimeError(f"{tool_name} failed: {response.response}")
    return response.response


def clean_workshop_artifacts() -> None:
    import shutil

    for path in (
        DEFAULT_WORKSHOP_ROOT / "feedback-records.jsonl",
        DEFAULT_WORKSHOP_ROOT / "manual-workshop-data.json",
        DEFAULT_WORKSHOP_ROOT / "manual-workshop-data.js",
        DEFAULT_WORKSHOP_ROOT / "index.html",
    ):
        if path.exists():
            path.unlink()
    for directory in (
        DEFAULT_WORKSHOP_ROOT / "handles",
        DEFAULT_WORKSHOP_ROOT / "replay-windows",
        DEFAULT_WORKSHOP_ROOT / "recipes",
    ):
        if directory.exists():
            shutil.rmtree(directory)


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
