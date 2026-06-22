#!/usr/bin/env python3
"""Smoke-test a deployed Manual Tactical Workbench Alpha service."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Cloud Workbench Alpha smoke checks.")
    parser.add_argument("--base-url", required=True, help="Base URL, for example https://service.onrender.com")
    parser.add_argument("--token", default="", help="DEMO_ACCESS_TOKEN for private alpha.")
    parser.add_argument("--result-limit", type=int, default=3)
    args = parser.parse_args()
    client = Client(args.base_url.rstrip("/"), args.token)

    health = client.get("/healthz")
    ready = client.get("/readyz")
    checks = [
        check("healthz.ok", health.get("ok") is True, health),
        check("readyz.ready", ready.get("status") == "READY", ready),
    ]
    for recipe_id in ("ball_side_block_shift_v1", "possession_corridor_availability_v1"):
        result = run_recipe(client, recipe_id, args.result_limit)
        checks.extend(result["checks"])
    passed = all(item["ok"] for item in checks)
    report = {"passed": passed, "checks": checks}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


def run_recipe(client: Client, recipe_id: str, result_limit: int) -> dict[str, Any]:
    plan = client.get(f"/api/plan?recipe_id={recipe_id}")
    submitted = client.post("/api/submit-validate", {"plan_document": plan["plan_document"]})
    bound_plan_id = submitted["validation"]["bound_plan_id"]
    confirmed = client.post("/api/confirm", {"bound_plan_id": bound_plan_id, "reviewer": "cloud_smoke"})
    authorization_id = confirmed["confirmation"]["execution_authorization_id"]
    request = {
        "bound_plan_id": bound_plan_id,
        "execution_authorization_id": authorization_id,
        "result_limit": result_limit,
    }
    first = client.post("/api/execute", request)
    second = client.post("/api/execute", request)
    first_result = (first["execution"]["results"] or [{}])[0]
    inspection = {}
    if first_result.get("result_id"):
        inspection = client.post(
            "/api/inspect-result",
            {
                "execution_id": first["execution"]["execution_id"],
                "result_id": first_result["result_id"],
            },
        )
    prefix = f"recipe.{recipe_id}"
    return {
        "checks": [
            check(f"{prefix}.plan_loaded", plan.get("ok") is True, {"plan_hash": plan.get("plan_hash")}),
            check(f"{prefix}.validated", bool(bound_plan_id), submitted.get("validation", {})),
            check(f"{prefix}.confirmed", bool(authorization_id), confirmed.get("confirmation", {})),
            check(
                f"{prefix}.executed_with_results",
                first["execution"]["total_result_count"] > 0,
                {
                    "total": first["execution"]["total_result_count"],
                    "returned": first["execution"]["returned_result_count"],
                    "traces": first["execution"]["trace_count"],
                },
            ),
            check(f"{prefix}.repeat_cache_hit", second["cache"]["cache_status"] == "HIT", second["cache"]),
            check(
                f"{prefix}.replay_loaded",
                bool((inspection.get("replay") or {}).get("frames")),
                {
                    "result_id": first_result.get("result_id"),
                    "replay_frames": len((inspection.get("replay") or {}).get("frames") or []),
                },
            ),
        ]
    }


def check(name: str, ok: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "details": details}


class Client:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, payload)

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        last_error: RuntimeError | None = None
        for attempt in range(1, 6):
            request = urllib.request.Request(self.base_url + path, data=body, method=method)
            request.add_header("Accept", "application/json")
            if body is not None:
                request.add_header("Content-Type", "application/json")
            if self.token:
                request.add_header("X-Demo-Access-Token", self.token)
            try:
                with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310 - user-supplied smoke URL.
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"{method} {path} failed with {exc.code}: {detail}")
                if exc.code not in {502, 503, 504} or attempt == 5:
                    raise last_error from exc
                time.sleep(attempt)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"{method} {path} failed without an HTTP response")


if __name__ == "__main__":
    raise SystemExit(main())
