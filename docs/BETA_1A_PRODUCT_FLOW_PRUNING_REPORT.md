# Workbench Beta 1A — Product Flow Pruning Report

Date: 2026-06-22
Branch: `codex/integrated-alpha`
Scope baseline: N1C proof integrity complete at `393b4db` (not reopened).

## Summary

Beta 1A makes the Workbench legible and trustworthy by collapsing the engineering
workbench into one coherent product flow — **Ask → Understand → Confirm and run → Explore** —
without changing any backend runtime semantics, primitives, MCP boundary, Hermes config,
tactical semantics, or proof artifacts.

A key finding up front: the backend on the current branch (`393b4db`) already emits the typed
`provenance_source` enum and typed `MODEL_UNAVAILABLE` / `CLARIFICATION_REQUIRED` /
`CAPABILITY_GAP` states. The audit's HTTP-500 and string-derived-label findings were against the
older *deployed* commit `25f29a14`. Beta 1A was therefore a **frontend** effort: the contract was
already honest; the product surface was not yet.

## What was pruned / changed

All changes are in `apps/workbench-alpha/`.

1. **Two distinct entry paths.** The cramped segmented toggle became an explicit "Start here"
   chooser: **Ask Hermes** (natural-language box) vs **Browse recipes** (reviewed/experimental
   recipe picker, no editable query box). `path-ask-hermes` / `path-browse-recipes`.

2. **One primary action per state.** The three competing buttons (Validate / Host confirm /
   Execute) were replaced by a single stage-aware **Confirm and run** action (`primary-action`).
   One click drives the full host-authority sequence (`/api/submit-validate` → `/api/confirm` →
   `/api/execute`) — the host still issues the bound plan and execution authorization server-side;
   nothing runs until the user deliberately confirms after reading the interpretation. The
   interpret button visually demotes once a plan is ready, so only one green primary shows per step.

3. **Developer internals hidden by default.** Moved behind collapsed `<details>` drawers (or into
   `data-*` attributes preserved for tooling/tests):
   - the Known-Timestamp probe form (`developer-tools` drawer);
   - the host/API badge and raw model status (`browser to host API`, `HERMES_FRONTIER_READY`) →
     friendly `host-status` pill + `data-model-status` / `data-model-available` attributes;
   - raw `replay_window_id` / `result_id` in the replay summary → `data-replay-window-id` /
     `data-result-id`;
   - raw `result_id` and formal classification in result cards → tactical headline +
     `data-classification` / `data-result-id`;
   - raw predicate `{value, threshold}` JSON → human-readable measurement line
     (`describeMeasurement`) + `data-raw`;
   - evidence-alias source node / field strings → `data-source` / `data-field`;
   - raw typed-plan / validation / confirmation / execution JSON stay in their Developer drawers.

4. **Honest provenance.** The UI labels strictly from the backend `provenance_source` enum (never
   inferred from strings). A preset/manual recipe reads as **Reviewed recipe** / **Manual preset**,
   never AI-authored. Pure mappers extracted to `src/presentation.ts` and unit-tested.

5. **Stale-state cleanup.** Verified and tested that changing mode, query text, selected recipe,
   match scope, or selected result clears downstream validation / confirmation / execution /
   results / replay. No stale "confirmed/ready" state survives an interpretation change.

6. **Honest empty / error / model-unavailable states.** Typed `MODEL_UNAVAILABLE` renders as a
   normal product state with an explicit, honest "Browse recipes still works — recipe/manual
   analysis, not fallback AI" recovery (`switch-to-recipes`), not raw 500 text.

## Scope-update compliance (N1 novel composition NOT product-ready)

Per the mid-task directive (live N1 hero artifacts predate the N1C `entry_mode` contract):

- `HERMES_NOVEL_COMPOSITION` is kept as a supported provenance enum.
- It is **never** presented as a runnable product success: it renders as
  **"Novel composition · pending proof refresh"** (caution tone), shows a `novel-composition-pending`
  notice, and is **excluded from `canRun`** so the primary action is disabled. No prominent live
  novel-composition CTA exists.
- `entry_mode` is rendered honestly when present (`PRESENT_AT_OPEN`, `ENTERED_AFTER_OPEN`,
  `NOT_ENTERED`, `UNKNOWN`); when absent it is **not** inferred from `time_to_entry_seconds`
  (covered by unit tests). It is dormant for the two Beta-1A presets and only surfaces for the
  N1 destination-entry family, so the rendering is defensive.
- No backend runtime semantics or proof artifacts were touched.

## User flow now

```
Ask Hermes (natural language)  ─┐
                                ├─►  Understand (interpretation + honest provenance)
Browse recipes (pick recipe)  ─┘            │
                                            ▼
                                   Confirm and run (one action; host-authority chain)
                                            │
                                            ▼
                                   Explore (result rail · replay · evidence · trace)
```

## Tests run

- `npm run test:acceptance` (in `apps/workbench-alpha`) — **PASS**
  - `test:contracts` (generated API schemas unchanged — backend untouched)
  - `test:fixtures` (no hardcoded tactical fixtures)
  - `test:unit` — geometry, playback, **presentation** (new) suites pass
  - `test:e2e` — **10 Playwright tests pass**, including:
    - approved + experimental real query→replay journeys (single Confirm-and-run flow);
    - model-unavailable / clarification / capability-gap contracts;
    - host-authority enforcement via public API;
    - scope-transition invalidation;
    - **new** Beta 1A: interpretation invalidation (query edit / recipe switch / path switch),
      developer-internals-hidden-by-default, novel-composition-pending-not-runnable.
- Backend contract: `PYTHONPATH=src .venv/bin/python -m unittest tests.test_workbench_beta0_contract`
  — **6/6 OK** (REVIEWED_RECIPE vs MANUAL_PRESET provenance, scope/cache/execution provenance, etc.).
- `tsc --noEmit` — clean.

State-invalidation coverage (acceptance #4): Ask Hermes → edit query after validation; Browse →
select different recipe; change match scope after validation; change match scope after execution;
switch Ask Hermes ↔ Browse recipes; select zero matches; select a different result/replay — all
asserted across the scope and `beta1a interpretation invalidation` tests plus the journey tests.

## Artifacts

Screenshots: `artifacts/workbench-alpha/beta1a-proof/screenshots/`
- `01-initial-split.png` — initial split Ask Hermes / Browse recipes
- `02-ask-hermes-state.png` — Ask Hermes interpretation state (honest typed MODEL_UNAVAILABLE today)
- `03-browse-recipes-selection.png` — Browse recipes selection + interpretation (Reviewed recipe)
- `04-confirmed-result.png` — confirmed execution / result state
- `05a-developer-collapsed.png` / `05b-developer-expanded.png` — Developer details collapsed & expanded
- `06-model-unavailable.png` — typed model-unavailable product state

Existing review-proof journey screenshots remain under
`artifacts/workbench-alpha/review-proof/screenshots/` and are regenerated by the e2e suite.

Generated by the screenshot spec `apps/workbench-alpha/tests/beta1a-proof.spec.ts`.

## Files changed

- `apps/workbench-alpha/src/App.tsx` — flow, primary action, drawers, honest states, provenance.
- `apps/workbench-alpha/src/presentation.ts` *(new)* — pure mappers (provenance, headline,
  entry_mode, measurement); unit-tested.
- `apps/workbench-alpha/src/styles.css` — path chooser, single action strip, dev panel.
- `apps/workbench-alpha/tests/workbench-alpha.spec.ts` — rewired to the new UI + new Beta 1A tests.
- `apps/workbench-alpha/tests/presentation.test.ts` *(new)* — provenance/entry_mode/measurement.
- `apps/workbench-alpha/tests/beta1a-proof.spec.ts` *(new)* — required screenshots.
- `apps/workbench-alpha/package.json` — `test:unit` includes the presentation suite.

## Remaining Beta 1B / Beta 1C work (explicitly NOT in 1A)

- **Beta 1B (comprehension polish):** corridor overlay temporal validity + legend projection
  (open/close frame, limiting defender); cold-execution waiting state (elapsed time, selected
  matches, cancel); result-rail grouping/filters; richer evidence "2–3 human measurements" default;
  product-language "why matched / why not" predicate summaries.
- **Beta 1C (model + composition):** restore a stable live Hermes interpretation journey;
  refresh N1 novel-composition proof against the current N1C `entry_mode` runtime, then expose
  `HERMES_NOVEL_COMPOSITION` as a first-class, end-to-end tested product path (currently held back).
- **Later (out of Beta 1):** S3 feedback/revision loop (record_feedback), recipe history/versions.

## Stop condition

Beta 1A is implemented and verified. Per instructions, work stops here — N1 live
novel-composition exposure is not pursued.
