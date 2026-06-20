"""Build static M1.1 developer inspector artifacts."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.executor import (
    DEFAULT_PLAN_PATH,
    execute_default_plan,
    execute_plan_from_path,
    execution_result_rows,
    runtime_parameters,
    select_proof_results,
)
from tqe.runtime.ir import model_payload, stable_hash

APPROVED_PLAN_PATH = DEFAULT_PLAN_PATH
EXPERIMENTAL_PLAN_PATH = Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
APPROVED_PROOF_MANIFEST = Path("artifacts/m1/gate-c/proof-pack-manifest.json")
EXPERIMENTAL_PROOF_MANIFEST = Path("artifacts/m1.1/experimental-evidence-manifest.json")
PREDICATE_TRACE_REPORT = Path("artifacts/m1.1/predicate-trace-report.json")
NON_MATCH_REPORT = Path("artifacts/m1.1/non-match-inspection-report.json")
INSPECTOR_ROOT = Path("artifacts/m1.1/inspector")
INSPECTOR_DATA = INSPECTOR_ROOT / "inspector-data.json"
INSPECTOR_DATA_JS = INSPECTOR_ROOT / "inspector-data.js"
INSPECTOR_HTML = INSPECTOR_ROOT / "index.html"
INSPECTOR_MANIFEST = INSPECTOR_ROOT / "manifest.json"

DEFAULT_PITCH = {
    "length_m": 105.0,
    "width_m": 68.0,
    "coordinate_contract": "centered_metres",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_inspector_artifacts(output_root: Path = INSPECTOR_ROOT) -> dict[str, Any]:
    data = build_inspector_data()
    output_root.mkdir(parents=True, exist_ok=True)
    data_path = output_root / "inspector-data.json"
    data_js_path = output_root / "inspector-data.js"
    html_path = output_root / "index.html"
    manifest_path = output_root / "manifest.json"

    data_path.write_text(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    data_js_path.write_text(
        "window.M11_INSPECTOR_DATA = "
        + json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + ";\n",
        encoding="utf-8",
    )
    html_path.write_text(inspector_html(), encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "status": "pass",
        "generated_at": utc_now_iso(),
        "inspector_root": str(output_root),
        "html": str(html_path),
        "data_json": str(data_path),
        "data_js": str(data_js_path),
        "plan_count": len(data["plans"]),
        "result_count": sum(len(plan["results"]) for plan in data["plans"]),
        "non_match_evaluation_count": len(data["non_match_evaluations"]),
        "data_hash": stable_hash(data),
        "contract": data["inspector_contract"],
    }
    write_json(manifest_path, manifest)
    return manifest


def build_inspector_data() -> dict[str, Any]:
    approved_plan = build_approved_plan_inspector()
    experimental_plan = build_experimental_plan_inspector()
    non_match = read_json(NON_MATCH_REPORT)
    validation_reports = validation_report_summary()
    result_key_union = sorted(
        {
            key
            for plan in (approved_plan, experimental_plan)
            for result in plan["results"]
            for key in result["raw_evidence"].keys()
        }
    )
    return {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "generated_at": utc_now_iso(),
        "title": "M1.1 Developer Inspector",
        "inspector_contract": {
            "plan_selector": True,
            "validation_visible": True,
            "result_list": True,
            "coordinate_replay": True,
            "predicate_trace": True,
            "non_match_tester": True,
            "raw_evidence_values": True,
            "generic_result_shape": True,
            "reuses_existing_replay_bundles": True,
        },
        "validation_reports": validation_reports,
        "plans": [approved_plan, experimental_plan],
        "non_match_evaluations": [
            {
                "plan_id": approved_plan["plan_id"],
                "target_id": evaluation["target"]["target_id"],
                "status": evaluation["status"],
                "match_id": evaluation["target"]["match_id"],
                "period": evaluation["target"]["period"],
                "target_frame_id": evaluation["target_frame_id"],
                "candidate_count": evaluation["candidate_count"],
                "failed_predicates": evaluation.get("failed_predicates", []),
                "predicate_traces": evaluation.get("predicate_traces", []),
                "raw_evaluation": evaluation,
            }
            for evaluation in non_match["evaluations"]
        ],
        "result_key_union": result_key_union,
    }


def build_approved_plan_inspector() -> dict[str, Any]:
    bound, execution = execute_default_plan()
    rows = execution_result_rows(execution)
    selected_rows = select_proof_results(rows, runtime_parameters(bound))
    traces = traces_by_result(read_json(PREDICATE_TRACE_REPORT)["predicate_traces"])
    manifest = read_json(APPROVED_PROOF_MANIFEST)
    bundles = {
        str(item["result_id"]): item
        for item in manifest.get("evidence_bundles", [])
    }
    results = [
        inspector_result(
            row=row,
            traces=traces.get(str(row["result_id"]), []),
            bundle_record=bundles[str(row["result_id"])],
            replay_family="m1_proof_pack",
            plan_status=bound.plan_status.value,
        )
        for row in selected_rows
        if str(row["result_id"]) in bundles
    ]
    return {
        "plan_id": bound.plan_id,
        "recipe_id": bound.recipe_id,
        "display_name": "Ball-Side Block Shift",
        "plan_status": bound.plan_status.value,
        "plan_path": str(APPROVED_PLAN_PATH),
        "plan_hash": bound.plan_hash,
        "bound_plan_hash": bound.bound_plan_hash,
        "validation": plan_validation(APPROVED_PLAN_PATH, bound.plan_status.value),
        "execution": {
            "execution_id": execution.execution_id,
            "runtime_result_count": len(rows),
            "inspectable_result_count": len(results),
            "result_summary": summarize_rows(rows),
            "proof_manifest": str(APPROVED_PROOF_MANIFEST),
        },
        "nodes": bound_node_summary(bound),
        "result_schema_keys": sorted({key for result in results for key in result["raw_evidence"]}),
        "results": results,
    }


def build_experimental_plan_inspector() -> dict[str, Any]:
    bound, execution = execute_plan_from_path(EXPERIMENTAL_PLAN_PATH)
    rows = execution_result_rows(execution)
    traces = traces_by_result(
        [trace.model_dump(mode="json", exclude_none=True) for trace in execution.predicate_traces]
    )
    manifest = read_json(EXPERIMENTAL_PROOF_MANIFEST)
    bundles = {
        str(item["result_id"]): item
        for item in manifest.get("evidence_bundles", [])
    }
    results = [
        inspector_result(
            row=row,
            traces=traces.get(str(row["result_id"]), []),
            bundle_record=bundles[str(row["result_id"])],
            replay_family="m1_1_experimental_proof_pack",
            plan_status=bound.plan_status.value,
        )
        for row in rows
        if str(row["result_id"]) in bundles
    ]
    return {
        "plan_id": bound.plan_id,
        "recipe_id": bound.recipe_id,
        "display_name": "Opposite Corridor After Shift",
        "plan_status": bound.plan_status.value,
        "plan_path": str(EXPERIMENTAL_PLAN_PATH),
        "plan_hash": bound.plan_hash,
        "bound_plan_hash": bound.bound_plan_hash,
        "validation": plan_validation(EXPERIMENTAL_PLAN_PATH, bound.plan_status.value),
        "execution": {
            "execution_id": execution.execution_id,
            "runtime_result_count": len(rows),
            "inspectable_result_count": len(results),
            "result_summary": summarize_rows(rows),
            "proof_manifest": str(EXPERIMENTAL_PROOF_MANIFEST),
        },
        "nodes": bound_node_summary(bound),
        "result_schema_keys": sorted({key for result in results for key in result["raw_evidence"]}),
        "results": results,
    }


def inspector_result(
    *,
    row: dict[str, Any],
    traces: list[dict[str, Any]],
    bundle_record: dict[str, Any],
    replay_family: str,
    plan_status: str,
) -> dict[str, Any]:
    bundle_path = Path(str(bundle_record["bundle_json"]))
    replay_path = Path(str(bundle_record["replay_json"]))
    bundle = read_json(bundle_path)
    replay = read_json(replay_path)
    replay_pitch = replay.get("pitch") if isinstance(replay.get("pitch"), dict) else DEFAULT_PITCH
    raw_evidence = json_ready(row)
    return {
        "result_id": str(row["result_id"]),
        "classification": str(row["classification"]),
        "match_id": str(row.get("match_id") or replay["match_id"]),
        "period": str(row.get("period") or replay["period"]),
        "anchor_frame_id": int(row["anchor_frame_id"]),
        "plan_status": str(row.get("plan_status") or plan_status),
        "summary_fields": summary_fields(raw_evidence),
        "raw_evidence": raw_evidence,
        "bundle": {
            "path": str(bundle_path),
            "status": bundle.get("status"),
            "classification": bundle.get("classification"),
            "raw": bundle,
        },
        "replay": {
            "path": str(replay_path),
            "source_artifact_family": replay_family,
            "frame_rate_hz": replay.get("frame_rate_hz"),
            "analysis_rate_hz": replay.get("analysis_rate_hz"),
            "start_frame_id": replay["start_frame_id"],
            "end_frame_id": replay["end_frame_id"],
            "frame_count": len(replay.get("frames", [])),
            "pitch": replay_pitch,
            "canonical_sources": replay.get("canonical_sources", {}),
            "frames": replay.get("frames", []),
        },
        "predicate_traces": traces,
    }


def plan_validation(plan_path: Path, expected_status: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        bound = bind_document_from_path(plan_path)
    except Exception as exc:  # pragma: no cover - verifier records the concrete error.
        return [
            {
                "id": "bind.visible_failure",
                "status": "fail",
                "message": f"{plan_path} failed to bind: {exc}",
                "evidence": str(plan_path),
            }
        ]
    checks.append(
        {
            "id": "bind.plan",
            "status": "pass",
            "message": "Plan document binds against the capability catalog.",
            "evidence": str(plan_path),
        }
    )
    checks.append(
        {
            "id": "bind.plan_status",
            "status": "pass" if bound.plan_status.value == expected_status else "fail",
            "message": f"Bound plan status is {bound.plan_status.value}.",
            "evidence": str(plan_path),
        }
    )
    checks.append(
        {
            "id": "bind.bound_plan_hash",
            "status": "pass" if bool(bound.bound_plan_hash) else "fail",
            "message": "Bound plan hash is present.",
            "evidence": bound.bound_plan_hash,
        }
    )
    return checks


def validation_report_summary() -> list[dict[str, Any]]:
    report_paths = [
        Path("artifacts/m1.1/binder-validation-report.json"),
        Path("artifacts/m1.1/gate-b-verification-report.json"),
        Path("artifacts/m1.1/gate-c-verification-report.json"),
        Path("artifacts/m1.1/gate-d-verification-report.json"),
        Path("artifacts/m1.1/gate-e-verification-report.json"),
    ]
    reports: list[dict[str, Any]] = []
    for path in report_paths:
        if not path.exists():
            reports.append(
                {
                    "id": path.stem,
                    "status": "fail",
                    "summary": {"pass": 0, "fail": 1, "not_ready": 0},
                    "path": str(path),
                }
            )
            continue
        report = read_json(path)
        reports.append(
            {
                "id": report.get("gate", path.stem),
                "status": report.get("status"),
                "summary": report.get("summary", {}),
                "path": str(path),
            }
        )
    return reports


def traces_by_result(traces: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        source = trace.get("source_evidence") if isinstance(trace.get("source_evidence"), dict) else {}
        result_id = source.get("result_id")
        if result_id is not None:
            grouped[str(result_id)].append(trace)
    return dict(grouped)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_class = Counter(str(row.get("classification")) for row in rows)
    by_match = Counter(str(row.get("match_id")) for row in rows)
    return {
        "count": len(rows),
        "by_classification": dict(sorted(by_class.items())),
        "by_match": dict(sorted(by_match.items())),
    }


def summary_fields(row: dict[str, Any]) -> dict[str, Any]:
    preferred = [
        "match_id",
        "period",
        "anchor_frame_id",
        "wide_entry_frame_id",
        "ball_side",
        "signed_shift_metres",
        "relation_id",
        "destination_region",
        "destination_entry_frame_id",
    ]
    return {key: row[key] for key in preferred if key in row}


def bound_node_summary(bound: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for node in bound.nodes:
        payload = model_payload(node)
        nodes.append(
            {
                "node_id": payload["node_id"],
                "kind": payload["kind"],
                "catalog_ref": payload.get("catalog_ref"),
                "operator": payload.get("operator", {}).get("name"),
                "outputs": [item["name"] for item in payload.get("outputs", [])]
                if "outputs" in payload
                else [payload.get("output", {}).get("name")],
            }
        )
    return nodes


def json_ready(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def inspector_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>M1.1 Developer Inspector</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #15202b;
      --muted: #5b6777;
      --line: #d7dde8;
      --accent: #1f6feb;
      --field: #0b6b43;
      --warn: #b56a00;
      --fail: #b3261e;
      --pass: #167a42;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 14px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header, main { max-width: 1480px; margin: 0 auto; padding: 16px 20px; }
    header {
      display: grid;
      grid-template-columns: minmax(240px, 1fr) auto;
      gap: 16px;
      align-items: end;
      border-bottom: 1px solid var(--line);
    }
    h1, h2, h3 { margin: 0; letter-spacing: 0; }
    h1 { font-size: 22px; }
    h2 { font-size: 16px; margin-bottom: 10px; }
    h3 { font-size: 14px; margin-bottom: 8px; }
    label { display: block; font-weight: 650; color: var(--muted); margin-bottom: 4px; }
    select, button, input[type="range"] {
      width: 100%;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      padding: 8px;
    }
    button { cursor: pointer; text-align: left; }
    main {
      display: grid;
      grid-template-columns: 300px minmax(420px, 1fr) 420px;
      gap: 12px;
      align-items: start;
    }
    section, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-width: 0;
    }
    .stack { display: grid; gap: 12px; }
    .meta { color: var(--muted); font-size: 12px; }
    .badge {
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      background: #fff;
      margin: 2px 4px 2px 0;
    }
    .pass { color: var(--pass); }
    .fail { color: var(--fail); }
    .not_ready, .unknown { color: var(--warn); }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th, td {
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      padding: 6px;
      overflow-wrap: anywhere;
      font-size: 12px;
    }
    th { color: var(--muted); font-weight: 700; }
    tr.selected { background: #edf4ff; }
    .result-list { max-height: 340px; overflow: auto; }
    .trace-list { max-height: 280px; overflow: auto; }
    canvas {
      width: 100%;
      aspect-ratio: 105 / 68;
      display: block;
      background: var(--field);
      border-radius: 6px;
      border: 1px solid #0f5136;
    }
    pre {
      white-space: pre-wrap;
      overflow: auto;
      max-height: 420px;
      background: #0f1720;
      color: #e7eef7;
      border-radius: 6px;
      padding: 10px;
      font-size: 12px;
    }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    @media (max-width: 1100px) {
      header, main { padding: 12px; }
      main { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>M1.1 Developer Inspector</h1>
      <div class="meta" id="buildMeta"></div>
    </div>
    <div>
      <label for="planSelect">Plan</label>
      <select id="planSelect"></select>
    </div>
  </header>
  <main>
    <aside class="stack">
      <section>
        <h2>Validation</h2>
        <div id="validationList"></div>
      </section>
      <section>
        <h2>Plan Nodes</h2>
        <div id="nodeList"></div>
      </section>
      <section>
        <h2>Non-Match Tester</h2>
        <label for="nonMatchSelect">Target</label>
        <select id="nonMatchSelect"></select>
        <div id="nonMatchDetails"></div>
      </section>
    </aside>
    <section class="stack">
      <div>
        <h2>Results</h2>
        <div class="meta" id="planSummary"></div>
        <div class="result-list">
          <table>
            <thead><tr><th>Result</th><th>Class</th><th>Match</th><th>Frame</th></tr></thead>
            <tbody id="resultRows"></tbody>
          </table>
        </div>
      </div>
      <div>
        <h2>Coordinate Replay</h2>
        <canvas id="pitchCanvas" width="1050" height="680"></canvas>
        <div class="grid2">
          <input id="frameSlider" type="range" min="0" max="0" value="0">
          <div class="meta" id="frameMeta"></div>
        </div>
      </div>
      <div>
        <h2>Predicate Trace</h2>
        <div class="trace-list">
          <table>
            <thead><tr><th>Predicate</th><th>Status</th><th>Value</th><th>Threshold</th><th>Frame</th></tr></thead>
            <tbody id="traceRows"></tbody>
          </table>
        </div>
      </div>
    </section>
    <aside class="stack">
      <section>
        <h2>Raw Evidence</h2>
        <pre id="rawEvidence"></pre>
      </section>
      <section>
        <h2>Replay Sources</h2>
        <pre id="sourceEvidence"></pre>
      </section>
    </aside>
  </main>
  <script src="./inspector-data.js"></script>
  <script>
    const data = window.M11_INSPECTOR_DATA;
    const state = { plan: null, result: null, frameIndex: 0 };
    const planSelect = document.getElementById("planSelect");
    const resultRows = document.getElementById("resultRows");
    const frameSlider = document.getElementById("frameSlider");
    const canvas = document.getElementById("pitchCanvas");
    const ctx = canvas.getContext("2d");

    function text(value) {
      if (value === null || value === undefined) return "";
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
    }

    function statusClass(status) {
      return String(status || "unknown").toLowerCase();
    }

    function init() {
      document.getElementById("buildMeta").textContent =
        `${data.milestone} | generated ${data.generated_at} | ${data.plans.length} plans`;
      for (const plan of data.plans) {
        const option = document.createElement("option");
        option.value = plan.plan_id;
        option.textContent = `${plan.display_name} (${plan.plan_status})`;
        planSelect.appendChild(option);
      }
      planSelect.addEventListener("change", () => selectPlan(planSelect.value));
      frameSlider.addEventListener("input", () => {
        state.frameIndex = Number(frameSlider.value);
        drawReplay();
      });
      selectPlan(data.plans[0].plan_id);
    }

    function selectPlan(planId) {
      state.plan = data.plans.find((plan) => plan.plan_id === planId);
      state.result = state.plan.results[0];
      state.frameIndex = 0;
      renderPlan();
    }

    function renderPlan() {
      document.getElementById("planSummary").textContent =
        `${state.plan.execution.inspectable_result_count} inspectable results | ` +
        `${state.plan.execution.runtime_result_count} runtime results | ` +
        `bound ${state.plan.bound_plan_hash.slice(0, 12)}`;
      renderValidation();
      renderNodes();
      renderResults();
      renderNonMatches();
      renderResult();
    }

    function renderValidation() {
      const target = document.getElementById("validationList");
      const rows = [
        ...data.validation_reports.map((item) => ({
          id: item.id,
          status: item.status,
          message: JSON.stringify(item.summary),
          evidence: item.path
        })),
        ...state.plan.validation
      ];
      target.innerHTML = rows.map((item) =>
        `<div class="badge ${statusClass(item.status)}">${item.status}</div>` +
        `<div><strong>${item.id}</strong></div>` +
        `<div class="meta">${text(item.message)} ${text(item.evidence)}</div>`
      ).join("");
    }

    function renderNodes() {
      document.getElementById("nodeList").innerHTML = state.plan.nodes.map((node) =>
        `<div><span class="badge">${node.kind}</span><strong>${node.node_id}</strong></div>` +
        `<div class="meta">${text(node.catalog_ref || node.operator)} -> ${text(node.outputs)}</div>`
      ).join("");
    }

    function renderResults() {
      resultRows.innerHTML = "";
      for (const result of state.plan.results) {
        const tr = document.createElement("tr");
        tr.className = result.result_id === state.result.result_id ? "selected" : "";
        tr.innerHTML =
          `<td><button data-result="${result.result_id}">${result.result_id}</button></td>` +
          `<td>${result.classification}</td>` +
          `<td>${result.match_id}<br>${result.period}</td>` +
          `<td>${result.anchor_frame_id}</td>`;
        resultRows.appendChild(tr);
      }
      resultRows.querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => {
          state.result = state.plan.results.find((result) => result.result_id === button.dataset.result);
          state.frameIndex = 0;
          renderResults();
          renderResult();
        });
      });
    }

    function renderResult() {
      const frames = state.result.replay.frames;
      frameSlider.max = Math.max(0, frames.length - 1);
      frameSlider.value = state.frameIndex;
      document.getElementById("rawEvidence").textContent = JSON.stringify({
        summary_fields: state.result.summary_fields,
        raw_evidence: state.result.raw_evidence,
        bundle: state.result.bundle.raw
      }, null, 2);
      document.getElementById("sourceEvidence").textContent = JSON.stringify({
        replay_path: state.result.replay.path,
        replay_family: state.result.replay.source_artifact_family,
        canonical_sources: state.result.replay.canonical_sources
      }, null, 2);
      renderTraces();
      drawReplay();
    }

    function renderTraces() {
      document.getElementById("traceRows").innerHTML = state.result.predicate_traces.map((trace) =>
        `<tr><td>${trace.predicate_id}</td>` +
        `<td class="${statusClass(trace.status)}">${trace.status}</td>` +
        `<td>${text(trace.value && trace.value.value)}</td>` +
        `<td>${text(trace.threshold && trace.threshold.value)}</td>` +
        `<td>${text(trace.frame_id || (trace.window && JSON.stringify(trace.window)))}</td></tr>`
      ).join("");
    }

    function renderNonMatches() {
      const select = document.getElementById("nonMatchSelect");
      select.innerHTML = "";
      for (const item of data.non_match_evaluations) {
        const option = document.createElement("option");
        option.value = item.target_id;
        option.textContent = `${item.target_id} (${item.status})`;
        select.appendChild(option);
      }
      select.onchange = () => renderNonMatchDetails(select.value);
      renderNonMatchDetails(select.value || (data.non_match_evaluations[0] && data.non_match_evaluations[0].target_id));
    }

    function renderNonMatchDetails(targetId) {
      const item = data.non_match_evaluations.find((evaluation) => evaluation.target_id === targetId);
      document.getElementById("nonMatchDetails").innerHTML = item ? (
        `<div><span class="badge ${statusClass(item.status)}">${item.status}</span>` +
        `<strong>${item.match_id} ${item.period}</strong></div>` +
        `<div class="meta">candidate count ${item.candidate_count} | target frame ${item.target_frame_id}</div>` +
        `<pre>${JSON.stringify(item.raw_evaluation, null, 2)}</pre>`
      ) : "";
    }

    function drawReplay() {
      const replay = state.result.replay;
      const frames = replay.frames;
      const frame = frames[Math.min(state.frameIndex, Math.max(0, frames.length - 1))];
      const pitch = replay.pitch || { length_m: 105, width_m: 68 };
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#0b6b43";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = "rgba(255,255,255,.85)";
      ctx.lineWidth = 4;
      ctx.strokeRect(20, 20, canvas.width - 40, canvas.height - 40);
      ctx.beginPath();
      ctx.moveTo(canvas.width / 2, 20);
      ctx.lineTo(canvas.width / 2, canvas.height - 20);
      ctx.stroke();
      if (!frame) return;
      for (const entity of frame.entities) {
        const [x, y] = toCanvas(entity.x_m, entity.y_m, pitch);
        ctx.beginPath();
        ctx.fillStyle = entity.entity_type === "ball" ? "#f5d547" :
          entity.team_role === "home" ? "#ffffff" : "#e04f3f";
        ctx.arc(x, y, entity.entity_type === "ball" ? 5 : 7, 0, Math.PI * 2);
        ctx.fill();
      }
      document.getElementById("frameMeta").textContent =
        `frame ${frame.frame_id} | ${state.frameIndex + 1}/${frames.length} | ${state.result.replay.path}`;
    }

    function toCanvas(x, y, pitch) {
      const length = pitch.length_m || 105;
      const width = pitch.width_m || 68;
      const px = 20 + ((x + length / 2) / length) * (canvas.width - 40);
      const py = 20 + ((width / 2 - y) / width) * (canvas.height - 40);
      return [px, py];
    }

    init();
  </script>
</body>
</html>
"""


def main() -> int:
    manifest = build_inspector_artifacts()
    print(json.dumps({"status": manifest["status"], "manifest": str(INSPECTOR_MANIFEST)}, sort_keys=True))
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
