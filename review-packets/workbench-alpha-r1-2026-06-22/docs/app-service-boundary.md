# App Service Boundary Confirmation

`src/tqe/workshop/app_service.py` remains an orchestration and HTTP boundary for Workbench Alpha.

## What It Does

- Serves the built Workbench static app.
- Exposes `/api/health`, `/api/bootstrap`, `/api/plan`, `/api/interpret`, `/api/submit-validate`, `/api/confirm`, `/api/execute`, `/api/inspect-result`, and `/api/inspect-timestamp`.
- Loads reviewed plan documents for the approved block-shift recipe and experimental corridor preset.
- Performs manual recipe selection, clarification state routing, capability-gap state routing, response-envelope construction, and public error shaping.
- Calls host-owned workshop functions for submit, validate, confirm, execute, inspect, and replay retrieval.
- Defines Pydantic response-envelope contracts used to generate browser-side schema/types.

## What It Does Not Do

- It does not read canonical tracking parquet files directly.
- It does not iterate match frames or player positions for tactical analysis.
- It does not calculate distances, lateral shifts, corridor geometry, predicates, primitive truth values, or outcome classifications.
- It does not reconstruct tactical logic from result artifacts.
- It does not expose local artifact paths through `/api/bootstrap` or public error messages.
- It does not call MCP; MCP remains the Hermes adapter boundary.

## Source Evidence

- `source-excerpts/app_service.py`
- `tests/workbench-alpha.spec.ts`
- `diffs/commit-87b2441.patch`
