# M1.1 Gate F Controller Review

Reviewed at: 2026-06-19T22:51:23-05:00

## Decision

ACCEPTED_CONTROLLER_ONLY for M1.1 completion.

## Scope Reviewed

- Static developer inspector artifact builder.
- Plan selector data for the approved M1 plan and experimental opposite-corridor plan.
- Validation visibility for Gates A-E and per-plan binder checks.
- Result list, coordinate replay, predicate traces, non-match evaluations, replay sources, and raw evidence panels.
- Reuse of existing M1 proof replay bundles and M1.1 experimental replay bundles.
- Generic result-shape handling across approved and experimental plans.

## Evidence

- `make m1-1-gate-f-verify` passes with 13 passing checks, zero failures, and zero not-ready checks.
- `artifacts/m1.1/inspector/index.html` is the direct-open static inspector.
- `artifacts/m1.1/inspector/manifest.json` records 2 plans, 57 inspectable results, and 3 non-match evaluations.
- Plan spread: 16 approved M1 proof-pack results and 41 experimental opposite-corridor results.
- `make test` passes 20 tests.
- `make m1-1-verify` now passes full M1.1 with 118 passing checks, zero failures, and zero not-ready checks.
- `make m1-verify` still passes M1 Gate A, Gate B, and Gate C.

## Acceptance Rationale

Gate F proves the runtime is inspectable without a bespoke M1 UI. The inspector data is plan-oriented, not query-ID-oriented: each plan carries its bound-plan metadata, validation checks, node summaries, result rows, raw evidence, replay frames, predicate traces, and replay source paths. The HTML reads the generic data contract and provides the required developer controls: plan selector, validation list, result table, coordinate replay canvas, predicate trace table, non-match tester, and raw evidence panel.

## Non-Blocking Concerns

- The inspector is a developer artifact, not the M1.2 workshop UX.
- The generated inspector data is intentionally large because it embeds replay frames for all inspectable results; it remains under ignored `artifacts/`.
- M1.1 is controller-verified only. Final owner acceptance remains pending.
