"""Workbench Alpha host application service.

The browser talks to this HTTP service. This service calls the host-owned
workshop dispatcher directly; it is not an MCP server and does not expose the
Hermes adapter boundary to the browser.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import ValidationError

from tqe.runtime.ir import TacticalQueryDocument, stable_hash
from tqe.workshop.m1_2 import (
    CallerProfile,
    CapabilityGap,
    DEFAULT_WORKSHOP_ROOT,
    ExecuteQueryPlanRequest,
    HostConfirmationResponse,
    InspectNonMatchRequest,
    InspectResultRequest,
    ReplayWindowRequest,
    SubmitQueryPlanRequest,
    ValidateQueryPlanRequest,
    describe_capability,
    execute_query_plan,
    host_confirm_bound_plan,
    inspect_non_match,
    inspect_result,
    list_capabilities,
    read_json,
    replay_artifact_path,
    retrieve_replay_window,
    submit_query_plan,
    stable_tool_error_code,
    validate_query_plan,
)

APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
CORRIDOR_PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
DEFAULT_STATIC_ROOT = Path("apps/workbench-alpha/dist")

UNSUPPORTED_CONCEPTS = {
    "body orientation": "No body-orientation primitive is exposed.",
    "orientation": "No body-orientation primitive is exposed.",
    "intent": "Intent is not observable in the current deterministic vocabulary.",
    "optimal": "Optimal-action claims are outside the approved claims.",
    "should": "Normative decision-quality claims are outside the approved claims.",
    "communication": "Communication is not represented in the tracking data.",
    "pass probability": "Pass-probability modelling is not available.",
    "video": "Video is outside the current dataset/tool boundary.",
}

PLANNED_GAPS = {
    "pressure": ("pressure_change", "Pressure change is not in the current deterministic vocabulary."),
    "counterpress": ("pressure_change", "Counterpress queries need a future pressure-change capability."),
    "pressing": ("pressure_change", "Pressing queries need a future pressure-change capability."),
    "defensive line": (
        "defensive_line_model",
        "Defensive-line modelling is planned for the second tactical family.",
    ),
    "line break": (
        "controlled_line_break_episode",
        "Controlled line-break episodes are planned but not implemented.",
    ),
    "third man": ("support_arrival_relation", "Third-player support needs a support-arrival relation."),
    "third-man": ("support_arrival_relation", "Third-player support needs a support-arrival relation."),
    "lane occupancy": ("lane_occupancy", "General lane occupancy is planned but not implemented."),
    "overload": (
        "local_numerical_difference",
        "Local numerical difference is planned or may be folded into support arrival.",
    ),
}


def json_response(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")


def ok(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, **(payload or {})}


def error_response(code: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False, "error_code": code, "message": message, "details": details or {}}


def plan_for_recipe(recipe_id: str) -> dict[str, Any]:
    if recipe_id == "ball_side_block_shift_v1":
        return read_json(APPROVED_PLAN_PATH)
    if recipe_id == "possession_corridor_availability_v1":
        return read_json(CORRIDOR_PLAN_PATH)
    raise ValueError(f"Unsupported recipe_id: {recipe_id}")


def plan_path_for_preset(preset_id: str | None, selected_recipe_id: str | None) -> Path | None:
    key = (preset_id or selected_recipe_id or "").strip()
    if key in {"approved_block_shift", "ball_side_block_shift_v1"}:
        return APPROVED_PLAN_PATH
    if key in {"experimental_corridor", "possession_corridor_availability_v1"}:
        return CORRIDOR_PLAN_PATH
    return None


def load_plan_from_path(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    TacticalQueryDocument.model_validate(payload)
    return payload


def host_owned_plan_document(plan_document: dict[str, Any]) -> TacticalQueryDocument:
    candidate = TacticalQueryDocument.model_validate(plan_document)
    if (
        candidate.recipe.recipe_id == "ball_side_block_shift_v1"
        and candidate.draft_plan.status == "approved"
    ):
        return TacticalQueryDocument.model_validate(load_plan_from_path(APPROVED_PLAN_PATH))
    return candidate


def normalized(text: str) -> str:
    return " ".join(text.lower().strip().split())


def unsupported_gaps(text: str) -> list[dict[str, str]]:
    gaps = []
    for token, reason in UNSUPPORTED_CONCEPTS.items():
        if token in text:
            gaps.append({"concept": token, "reason": reason})
    seen_codes = set()
    for token, (code, reason) in PLANNED_GAPS.items():
        if token in text and code not in seen_codes:
            gaps.append({"concept": code, "reason": reason})
            seen_codes.add(code)
    return gaps


def needs_support_clarification(text: str, clarifications: list[str]) -> bool:
    if clarifications:
        return False
    if "support" not in text and "second runner" not in text and "teammate" not in text:
        return False
    return "corridor" not in text and "progressive lane" not in text and "passing lane" not in text


def infer_plan_path(query: str) -> Path | None:
    text = normalized(query)
    if "corridor" in text or "progressive lane" in text or "passing lane" in text:
        return CORRIDOR_PLAN_PATH
    if "block shift" in text:
        return APPROVED_PLAN_PATH
    if "ball side" in text and ("shift" in text or "defending block" in text or "block" in text):
        return APPROVED_PLAN_PATH
    if "wide" in text and "defending" in text and "shift" in text:
        return APPROVED_PLAN_PATH
    return None


def recipe_card(plan_document: dict[str, Any], state: str) -> dict[str, Any]:
    recipe = plan_document["recipe"]
    return {
        "recipe_id": recipe["recipe_id"],
        "recipe_version": recipe["recipe_version"],
        "state": state,
        "display_name": recipe["display_name"],
        "description": recipe["description"],
        "allowed_claims": recipe.get("allowed_claims", []),
        "disallowed_claims": recipe.get("disallowed_claims", []),
        "limitations": recipe.get("limitations", []),
        "output_classifications": recipe.get("output_classifications", []),
    }


def interpret_request(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    mode = str(payload.get("mode") or "manual")
    clarifications = [str(item) for item in payload.get("clarifications") or [] if str(item).strip()]
    selected_recipe_id = payload.get("selected_recipe_id")
    preset_id = payload.get("preset_id")
    if mode == "model":
        return ok(
            {
                "status": "MODEL_UNAVAILABLE",
                "query": query,
                "message": "Model-backed interpretation is not connected in Workbench Alpha. Manual mode remains available.",
                "manual_available": True,
            }
        )

    text = normalized(query)
    gaps = unsupported_gaps(text)
    if gaps:
        return ok(
            {
                "status": "CAPABILITY_GAP",
                "query": query,
                "capability_gaps": gaps,
                "message": "The request contains concepts outside the current deterministic capability set.",
            }
        )
    if needs_support_clarification(text, clarifications):
        return ok(
            {
                "status": "CLARIFICATION_REQUIRED",
                "query": query,
                "clarification_questions": [
                    "Should support mean a progressive corridor, a nearby teammate, or a distinct lane option?",
                    "What time window should count as support arriving after the anchor?",
                ],
                "clarification_codes": ["SUPPORT_DEFINITION", "TIME_WINDOW"],
            }
        )

    path = plan_path_for_preset(
        str(preset_id) if preset_id is not None else None,
        str(selected_recipe_id) if selected_recipe_id is not None else None,
    )
    if path is None:
        path = infer_plan_path(query)
    if path is None:
        return ok(
            {
                "status": "CLARIFICATION_REQUIRED",
                "query": query,
                "clarification_questions": [
                    "Select the approved block-shift recipe or the experimental corridor preset.",
                ],
                "clarification_codes": ["RECIPE_SELECTION"],
            }
        )

    plan_document = load_plan_from_path(path)
    state = "APPROVED" if path == APPROVED_PLAN_PATH else "EXPERIMENTAL"
    return ok(
        {
            "status": "PLAN_INTERPRETED",
            "query": query,
            "source": "manual_host_interpreter",
            "recipe": recipe_card(plan_document, state),
            "plan_document": plan_document,
            "plan_hash": stable_hash(plan_document),
        }
    )


def replay_payload(replay_window_id: str, *, output_root: Path) -> dict[str, Any]:
    return read_json(replay_artifact_path(replay_window_id, output_root=output_root))


def result_with_replay(payload: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    padding_seconds = float(payload.get("padding_seconds", 2.0))
    inspected = inspect_result(
        InspectResultRequest.model_validate(
            {
                "execution_id": payload.get("execution_id"),
                "result_id": payload.get("result_id"),
            }
        ),
        output_root=output_root,
    )
    replay_summary = retrieve_replay_window(
        ReplayWindowRequest(
            execution_id=inspected.execution_id,
            result_id=payload["result_id"],
            padding_seconds=padding_seconds,
        ),
        output_root=output_root,
    )
    return ok(
        {
            "inspection": inspected.model_dump(mode="json"),
            "replay_window": replay_summary.model_dump(mode="json"),
            "replay": replay_payload(replay_summary.replay_window_id, output_root=output_root),
        }
    )


def timestamp_inspection(payload: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    padding_seconds = float(payload.get("padding_seconds", 2.0))
    request = InspectNonMatchRequest.model_validate(
        {
            "execution_id": payload.get("execution_id"),
            "target": payload.get("target"),
        }
    )
    inspection = inspect_non_match(request, output_root=output_root)
    replay_summary = retrieve_replay_window(
        ReplayWindowRequest(
            execution_id=request.execution_id,
            target=request.target,
            padding_seconds=padding_seconds,
        ),
        output_root=output_root,
    )
    return ok(
        {
            "inspection": inspection.model_dump(mode="json"),
            "replay_window": replay_summary.model_dump(mode="json"),
            "replay": replay_payload(replay_summary.replay_window_id, output_root=output_root),
        }
    )


class WorkbenchServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler: type[BaseHTTPRequestHandler],
        *,
        static_root: Path,
        output_root: Path,
    ) -> None:
        super().__init__(server_address, request_handler)
        self.static_root = static_root.resolve()
        self.output_root = output_root


class WorkbenchHandler(BaseHTTPRequestHandler):
    server: WorkbenchServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json_response(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, path: str) -> None:
        route = path if path != "/" else "/index.html"
        relative = route.lstrip("/")
        target = (self.server.static_root / relative).resolve()
        if self.server.static_root not in target.parents and target != self.server.static_root:
            self.send_json(error_response("PATH_ESCAPE", "Static path escapes root."), HTTPStatus.BAD_REQUEST)
            return
        if not target.exists() or target.is_dir():
            if route != "/" and Path(relative).suffix:
                self.send_json(error_response("STATIC_NOT_FOUND", "Static asset was not found."), HTTPStatus.NOT_FOUND)
                return
            target = self.server.static_root / "index.html"
        if not target.exists():
            self.send_json(
                error_response(
                    "STATIC_BUILD_MISSING",
                    "Workbench static build is missing. Run npm --prefix apps/workbench-alpha run build.",
                ),
                HTTPStatus.NOT_FOUND,
            )
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(ok({"service": "workbench_alpha_host", "mcp_adapter": False}))
            return
        if parsed.path == "/api/bootstrap":
            self.send_json(self.bootstrap())
            return
        if parsed.path == "/api/plan":
            query = parse_qs(parsed.query)
            recipe_id = (query.get("recipe_id") or [""])[0]
            try:
                plan = plan_for_recipe(recipe_id)
                state = "APPROVED" if recipe_id == "ball_side_block_shift_v1" else "EXPERIMENTAL"
                self.send_json(ok({"recipe": recipe_card(plan, state), "plan_document": plan, "plan_hash": stable_hash(plan)}))
            except Exception as exc:
                self.send_json(error_response("PLAN_NOT_FOUND", str(exc)), HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/api/"):
            self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)
            return
        self.send_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_body()
            if parsed.path == "/api/interpret":
                self.send_json(interpret_request(payload))
            elif parsed.path == "/api/submit-validate":
                plan_document = host_owned_plan_document(payload["plan_document"])
                submitted = submit_query_plan(
                    SubmitQueryPlanRequest(plan_document=plan_document, source_label="workbench_alpha"),
                    output_root=self.server.output_root,
                    caller_profile=CallerProfile.HOST_MANUAL,
                )
                validation = validate_query_plan(
                    ValidateQueryPlanRequest(draft_plan_id=submitted.draft_plan_id),
                    output_root=self.server.output_root,
                    caller_profile=CallerProfile.HOST_MANUAL,
                )
                self.send_json(
                    ok(
                        {
                            "submit": submitted.model_dump(mode="json"),
                            "validation": validation.model_dump(mode="json"),
                        }
                    )
                )
            elif parsed.path == "/api/confirm":
                confirmation: HostConfirmationResponse = host_confirm_bound_plan(
                    str(payload["bound_plan_id"]),
                    reviewer=str(payload.get("reviewer") or "workbench_alpha_host"),
                    output_root=self.server.output_root,
                )
                self.send_json(ok({"confirmation": confirmation.model_dump(mode="json")}))
            elif parsed.path == "/api/execute":
                execution = execute_query_plan(
                    ExecuteQueryPlanRequest.model_validate(payload),
                    output_root=self.server.output_root,
                )
                self.send_json(ok({"execution": execution.model_dump(mode="json")}))
            elif parsed.path == "/api/inspect-result":
                self.send_json(result_with_replay(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/inspect-timestamp":
                self.send_json(timestamp_inspection(payload, output_root=self.server.output_root))
            else:
                self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)
        except (KeyError, ValueError, ValidationError) as exc:
            self.send_json(error_response("REQUEST_SCHEMA_INVALID", str(exc)), HTTPStatus.BAD_REQUEST)
        except CapabilityGap as exc:
            self.send_json(
                error_response(stable_tool_error_code(exc), str(exc)),
                HTTPStatus.FORBIDDEN,
            )
        except Exception as exc:
            self.send_json(
                error_response(type(exc).__name__.upper(), str(exc)),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def bootstrap(self) -> dict[str, Any]:
        approved_plan = load_plan_from_path(APPROVED_PLAN_PATH)
        corridor_plan = load_plan_from_path(CORRIDOR_PLAN_PATH)
        context = list_capabilities(CallerProfile.HOST_MANUAL)
        return ok(
            {
                "service": {
                    "name": "workbench_alpha_host",
                    "mcp_adapter": False,
                    "output_root": str(self.server.output_root),
                },
                "model": {
                    "available": False,
                    "status": "MODEL_UNAVAILABLE",
                    "message": "Manual mode is active; model-backed compilation is not connected in Workbench Alpha.",
                },
                "presets": [
                    {
                        "preset_id": "approved_block_shift",
                        "label": "Approved block shift",
                        "recipe": recipe_card(approved_plan, "APPROVED"),
                        "plan_hash": stable_hash(approved_plan),
                    },
                    {
                        "preset_id": "experimental_corridor",
                        "label": "Experimental corridor",
                        "recipe": recipe_card(corridor_plan, "EXPERIMENTAL"),
                        "plan_hash": stable_hash(corridor_plan),
                    },
                ],
                "capabilities": {
                    "primitive_count": len(context.primitives),
                    "relation_count": len(context.relations),
                    "operator_count": len(context.operators),
                    "tools": [tool.name for tool in context.tools],
                    "execute_tool_description": describe_capability(
                        "execute_query_plan",
                        CallerProfile.HOST_MANUAL,
                    ),
                },
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Workbench Alpha host app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--static-root", type=Path, default=DEFAULT_STATIC_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_WORKSHOP_ROOT)
    args = parser.parse_args()
    server = WorkbenchServer(
        (args.host, args.port),
        WorkbenchHandler,
        static_root=args.static_root,
        output_root=args.output_root,
    )
    print(f"Workbench Alpha host service: http://{args.host}:{args.port}")
    print(f"Static root: {args.static_root}")
    print(f"Output root: {args.output_root}")
    server.serve_forever()


if __name__ == "__main__":
    main()
