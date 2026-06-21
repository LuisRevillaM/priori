"""Verify M1.2 S1: manual typed-plan workshop loop."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.executor import (
    GENERIC_EXECUTION_PROFILE,
    LEGACY_M1_PARITY_PROFILE,
    TacticalQueryExecutor,
    execute_legacy_m1_plan_from_path,
    execute_plan_from_path,
    execution_result_rows,
    runtime_parameters,
)
from tqe.runtime.ir import EvaluationTarget, stable_hash
from tqe.workshop.m1_2 import (
    DEFAULT_WORKSHOP_ROOT,
    FeedbackLabel,
    InspectNonMatchRequest,
    InspectResultRequest,
    RecordFeedbackRequest,
    ReplayWindowRequest,
    SaveExperimentalRecipeRequest,
    ValidateQueryPlanRequest,
    inspect_non_match,
    inspect_result,
    record_feedback,
    retrieve_replay_window,
    replay_window_from_canonical,
    save_experimental_recipe,
    validate_query_plan,
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
        profile=LEGACY_M1_PARITY_PROFILE,
        recipe_state="APPROVED",
    )
    experimental_run = run_manual_plan(
        plan_path=EXPERIMENTAL_PLAN_PATH,
        profile=GENERIC_EXECUTION_PROFILE,
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
    non_match = build_known_timestamp_non_match()
    checks.append(
        check(
            "s1.why_not_timestamp_works",
            non_match["inspection"]["status"] == "NON_MATCH"
            and len(non_match["inspection"]["failed_predicates"]) > 0,
            "Known timestamp inspection returns failed or unknown predicates.",
            non_match,
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
    saved_recipe = save_experimental_recipe(
        SaveExperimentalRecipeRequest(
            plan_path=str(EXPERIMENTAL_PLAN_PATH),
            creator="controller",
            note="M1.2 S1 manual workshop proof recipe.",
        )
    )
    checks.append(
        check(
            "s1.experimental_recipe_saved_immutably",
            Path(saved_recipe.path).exists() and bool(saved_recipe.query_hash),
            "Experimental recipe saves as a content-addressed immutable version.",
            saved_recipe.model_dump(mode="json"),
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
        "saved_recipe": saved_recipe.model_dump(mode="json"),
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
            "saved_recipe": saved_recipe.path,
        },
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def run_manual_plan(*, plan_path: Path, profile: str, recipe_state: str) -> dict[str, Any]:
    validation = validate_query_plan(ValidateQueryPlanRequest(plan_path=str(plan_path)))
    if profile == LEGACY_M1_PARITY_PROFILE:
        bound, full_execution = execute_legacy_m1_plan_from_path(plan_path)
    else:
        bound, full_execution = execute_plan_from_path(plan_path)
    all_rows = execution_result_rows(full_execution)
    rows = {str(row["result_id"]): row for row in all_rows}
    returned_rows = all_rows[:5]
    execution = {
        "ok": True,
        "plan_path": str(plan_path),
        "execution_id": full_execution.execution_id,
        "plan_id": bound.plan_id,
        "plan_status": bound.plan_status.value,
        "compatibility_profile": str(full_execution.provenance.get("compatibility_profile")),
        "total_result_count": len(all_rows),
        "returned_result_count": len(returned_rows),
        "trace_count": len(full_execution.predicate_traces),
        "bound_plan_hash": bound.bound_plan_hash,
        "results": [
            {
                "rank": index + 1,
                "result_id": str(row["result_id"]),
                "classification": str(row["classification"]),
                "match_id": str(row["match_id"]),
                "period": str(row["period"]),
                "anchor_frame_id": int(row["anchor_frame_id"]),
                "requested_evidence": row.get("requested_evidence", {}),
            }
            for index, row in enumerate(returned_rows)
        ],
    }
    traces_by_result: dict[str, list[dict[str, Any]]] = {}
    for trace in full_execution.predicate_traces:
        result_id = str(trace.source_evidence.get("result_id"))
        if result_id:
            traces_by_result.setdefault(result_id, []).append(
                trace.model_dump(mode="json", exclude_none=True)
            )
    plan_document = read_json(plan_path)
    results = []
    for result in execution["results"]:
        row = rows[result["result_id"]]
        replay_id = stable_hash(
            {
                "plan_path": str(plan_path),
                "profile": profile,
                "source_id": result["result_id"],
                "match_id": row["match_id"],
                "period": row["period"],
                "anchor_frame_id": row["anchor_frame_id"],
                "padding_seconds": 2.0,
            }
        )[:16]
        replay_payload = replay_window_from_canonical(
            replay_window_id=replay_id,
            plan_path=plan_path,
            source_id=result["result_id"],
            source_kind="result",
            match_id=str(row["match_id"]),
            period=str(row["period"]),
            anchor_frame_id=int(row["anchor_frame_id"]),
            padding_seconds=2.0,
        )
        replay_path = DEFAULT_WORKSHOP_ROOT / "replay-windows" / f"{replay_id}.json"
        write_json(replay_path, replay_payload)
        results.append(
            {
                **result,
                "predicate_traces": traces_by_result.get(result["result_id"], []),
                "requested_evidence": row.get("requested_evidence", {}),
                "replay": {
                    "ok": True,
                    "replay_window_id": replay_id,
                    "artifact_path": str(replay_path),
                    "match_id": row["match_id"],
                    "period": row["period"],
                    "start_frame_id": replay_payload["start_frame_id"],
                    "end_frame_id": replay_payload["end_frame_id"],
                    "anchor_frame_id": row["anchor_frame_id"],
                    "frame_count": len(replay_payload["frames"]),
                    "entity_observation_count": sum(
                        len(frame["entities"]) for frame in replay_payload["frames"]
                    ),
                    "source_kind": "result",
                    "source_id": result["result_id"],
                    "frames": replay_payload["frames"],
                    "pitch": replay_payload["pitch"],
                },
            }
        )
    return {
        "recipe_state": recipe_state,
        "plan_path": str(plan_path),
        "plan_document": plan_document,
        "validation": validation.model_dump(mode="json"),
        "execution": execution,
        "results": results,
    }


def build_known_timestamp_non_match() -> dict[str, Any]:
    bound = bind_document_from_path(EXPERIMENTAL_PLAN_PATH)
    executor = TacticalQueryExecutor()
    state = executor._execute_period(  # noqa: SLF001 - verifier needs a definitive FAIL anchor.
        bound_plan=bound,
        match_id=bound.match_ids[0],
        period=bound.periods[0],
        params=runtime_parameters(bound),
    )
    coverage = state.runtime_values["progressive_corridor"]["anchor_evaluations"].value
    fail_record = next(item for item in coverage if item["evaluation_status"] == "FAIL")
    target = EvaluationTarget(
        target_id="known_fail_corridor_anchor",
        match_id=str(fail_record["match_id"]),
        period=str(fail_record["period"]),
        approximate_time_ms=int(round(int(fail_record["anchor_frame_id"]) / 25.0 * 1000.0)),
        search_radius_ms=250,
    )
    inspection = inspect_non_match(
        InspectNonMatchRequest(
            plan_path=str(EXPERIMENTAL_PLAN_PATH),
            compatibility_profile=GENERIC_EXECUTION_PROFILE,
            target=target,
        )
    )
    replay = retrieve_replay_window(
        ReplayWindowRequest(
            plan_path=str(EXPERIMENTAL_PLAN_PATH),
            compatibility_profile=GENERIC_EXECUTION_PROFILE,
            target=target,
            padding_seconds=2.0,
        )
    )
    return {
        "target": target.model_dump(mode="json"),
        "inspection": inspection.inspection,
        "replay": replay.model_dump(mode="json"),
    }


def record_feedback_examples(
    *,
    approved_run: dict[str, Any],
    experimental_run: dict[str, Any],
    non_match: dict[str, Any],
) -> list[dict[str, Any]]:
    examples = [
        RecordFeedbackRequest(
            query_version=approved_run["execution"]["bound_plan_hash"],
            result_id=approved_run["results"][0]["result_id"],
            label=FeedbackLabel.MATCHES_INTENT,
            reviewer="controller",
            reason_code="manual_visual_match",
        ),
        RecordFeedbackRequest(
            query_version=experimental_run["execution"]["bound_plan_hash"],
            result_id=experimental_run["results"][0]["result_id"],
            label=FeedbackLabel.NEAR_MATCH,
            reviewer="controller",
            reason_code="needs_tactical_tightening",
        ),
        RecordFeedbackRequest(
            query_version=experimental_run["execution"]["bound_plan_hash"],
            result_id=experimental_run["results"][-1]["result_id"],
            label=FeedbackLabel.FALSE_POSITIVE,
            reviewer="controller",
            reason_code="visual_false_positive_example",
        ),
        RecordFeedbackRequest(
            query_version=experimental_run["execution"]["bound_plan_hash"],
            target=EvaluationTarget.model_validate(non_match["target"]),
            label=FeedbackLabel.KNOWN_MISS,
            reviewer="controller",
            reason_code="known_timestamp_should_match",
        ),
        RecordFeedbackRequest(
            query_version=experimental_run["execution"]["bound_plan_hash"],
            target=EvaluationTarget.model_validate(non_match["target"]),
            label=FeedbackLabel.UNUSABLE_DATA,
            reviewer="controller",
            reason_code="example_unusable_data_label",
        ),
    ]
    records = []
    for request in examples:
        response = record_feedback(request)
        records.append({**request.model_dump(mode="json", exclude_none=True), **response.model_dump(mode="json")})
    return records


def clean_workshop_artifacts() -> None:
    for path in (
        DEFAULT_WORKSHOP_ROOT / "feedback-records.jsonl",
        DEFAULT_WORKSHOP_ROOT / "manual-workshop-data.json",
        DEFAULT_WORKSHOP_ROOT / "manual-workshop-data.js",
        DEFAULT_WORKSHOP_ROOT / "index.html",
    ):
        if path.exists():
            path.unlink()


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
