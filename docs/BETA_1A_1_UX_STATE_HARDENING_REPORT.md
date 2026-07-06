# Workbench Beta 1A.1 — UX State Hardening Report

Date: 2026-06-22
Baseline: Beta 1A `59b6749`; N1D `16fa57e`.
Scope: frontend state/UX only. No `HERMES_NOVEL_COMPOSITION` exposure; no backend runtime semantics,
primitives, MCP boundary, Hermes prompts, or N1D proof artifacts changed.

## Summary

Made the Workbench state model predictable and removed confusing loading/transition behavior before
Beta 1C. The workflow now runs on a pure, unit-tested reducer; the app shows an honest booting state,
a cold-run waiting state, a labeled recipe preview, and a principal measurement per result.

## What changed

1. **Explicit booting state.** New `phase: "booting"` renders a "Loading workbench…" card until
   bootstrap + match library resolve. The scope bar and the "Select at least one match" warning are
   not rendered until the library has loaded — the boot flash (false "0 matches" / scope warning) is
   gone. `data-testid="booting-state"`.

2. **Reducer-based state machine.** New `src/workbenchState.ts` (pure, framework-free): `Phase`
   (`booting → idle → interpreting → ready → confirming → executing → results | error`),
   `WorkbenchState`, `WorkbenchAction`, `initialState`, `reducer`, and selectors
   (`selectPlanReady`/`selectCanRun`/`selectBusy`/`selectHasSelectedScope`/`selectIsNovelComposition`).
   All invalidation is centralized in the reducer — `SET_MODE`, `SET_QUERY`, `SET_PRESET` clear the
   interpretation and everything downstream; `SET_SCOPE` clears validation/confirmation/execution/
   results/replay while keeping the interpretation; `INTERPRET_RESULT` settles to `ready` only for a
   `PLAN_INTERPRETED` plan; model-unavailable / clarification / capability-gap settle to `idle`.
   `App.tsx` now `useReducer`s this and derives all disabled/label logic from selectors.

3. **Cold-run waiting state.** While `confirming`/`executing`, the Run State panel shows the current
   step (Validating plan / Host confirming / Executing over selected matches), a live elapsed timer,
   the selected scope, and "First run may take longer; repeat runs are cached." There is no safe
   server-side cancellation, so it is labeled honestly: "This runs on the host and cannot be canceled
   once started." `data-testid="cold-run-state"` / `cold-run-elapsed`.

4. **Preview vs interpretation.** A browsed recipe shown before interpretation is now labeled
   **"Preview — not yet interpreted"** (`data-testid="recipe-preview-badge"`), and Ask Hermes no
   longer borrows a recipe preview — its panel reads "Ask Hermes to interpret your question."

5. **Result-rail scanability.** Each result card shows one principal measurement where available —
   shift metres, time-to-entry, entry_mode, clearance, or duration — via the pure
   `principalMeasurement()` (matches plain and node-prefixed aliases like
   `signed_shift.signed_shift_metres`; never infers a missing value). Raw value preserved in
   `data-measurement-raw`. `data-testid="result-measurement"`.

6. **Consolidated Developer labels.** The repeated "Developer details" headings are now contextual:
   "Plan details", "Run details", "Run stages", and "Developer tools · known-timestamp probe".

## Tests

- `npm run test:acceptance` (in `apps/workbench-alpha`): **PASS** — contracts, fixtures, 4 unit
  suites (geometry, playback, presentation, **workbenchState**), and **13 Playwright tests**.
- New unit suite `tests/workbenchState.test.ts`: every invalidation transition (query edit, recipe
  switch, mode switch, scope change incl. zero-scope, result selection), boot, run→results, and the
  novel-composition / model-unavailable runnability rules.
- `tests/presentation.test.ts`: extended with `principalMeasurement` (priority order, dotted-alias
  match, never-inferred).
- New e2e tests: `beta1a.1 booting state…` (no false empty/scope warning) and
  `beta1a.1 cold-run state…` (step + elapsed + non-cancelable honesty while executing).
- Existing journeys, stale-state, model-unavailable/clarification/capability-gap, host-authority,
  and novel-composition-pending tests still pass unchanged.
- `tsc --noEmit`: clean.

## Screenshots

`artifacts/workbench-alpha/beta1a-proof/screenshots/`:
- `b11-00-booting.png` — boot/loading state
- `01-initial-split.png` — loaded initial split
- `b11-03-recipe-preview.png` — recipe preview, "not yet interpreted"
- `b11-04-cold-run.png` — executing cold-run state
- `b11-05-result-measurement.png` — result rail with a principal measurement per card

## Acceptance

- ✅ No boot flash with a false empty/scope warning.
- ✅ State transitions are reducer-driven and centrally controlled.
- ✅ Existing stale-state tests still pass.
- ✅ New tests cover the booting state and the cold-run/executing state.
- ✅ Approved recipe and experimental preset journeys still pass.
- ✅ Model-unavailable, clarification, and capability-gap states still render honestly.

## Follow-ups (not in this slice)

- Beta 1C: remove the "pending proof refresh" block and wire `HERMES_NOVEL_COMPOSITION` to the
  N1D-pinned novel path, with end-to-end UI tests.
- Optional: corridor overlay temporal validity, result grouping/filters (Beta 1B comprehension).
- Hygiene: `artifacts/n1c/*.json` are tracked despite `.gitignore` and are rewritten by `n1c-verify`;
  convert N1C to a read-compare gate (like N1D) or `git rm --cached` them.
