# Workbench Beta 1B — Comprehension Polish Report

Date: 2026-06-22
Baseline: Beta 1A `59b6749`, Beta 1A.1 `a9d056e`.
Scope: frontend comprehension only. No `HERMES_NOVEL_COMPOSITION` exposure; the pending-proof gate
stays; no backend runtime semantics, primitives, operators, MCP auth, Hermes prompts, or N1D proof
artifacts changed.

## Summary

Made reviewed/manual query results easier to understand and inspect: the corridor overlay now shows
only inside its valid evidence interval (with an explaining legend), the result rail groups by match
and surfaces a principal measurement per card, predicate traces read as plain "why matched"
summaries, and the known-timestamp outcome is human-readable. All of it uses exact evidence only —
nothing is inferred — and raw internals remain in Developer details.

## What changed (all in `apps/workbench-alpha/`)

1. **Corridor overlay temporal validity + legend** (`src/overlay.ts`, pure + unit-tested).
   - `corridorOverlayState(evidence, replay)` returns `interval` (open/close frames exist and the
     replay covers them), `witness` (only witness-frame geometry exists), or `none`.
   - `PitchCanvas` draws the ball→target corridor only when `overlayVisibleAtFrame` is true — across
     `[open, close]` for an interval, or at the witness frame only otherwise. Missing geometry hides
     the overlay; nothing is reconstructed.
   - `overlay-legend` explains the visible interval, the target receiver, and clearance / limiting
     defender when present, plus the non-optimality disclaimer. `overlay-proof` keeps its stable
     strings and adds an interval variant; `data-overlay-kind` exposes the state.

2. **Result-rail grouping + scanability.**
   - Results are grouped by match (header with a per-group moment count), preserving the deterministic
     result order within and across groups (`data-testid="result-group"` / `result-group-header`).
   - Each card shows one principal measurement already in evidence (shift / time-to-entry / entry_mode
     / clearance / duration; matches dotted aliases; never inferred; raw in `data-measurement-raw`).

3. **Product-language predicate / evidence summaries.**
   - The predicate trace shows a readable subject (`humanizePredicate`) and a "why matched / why not"
     line (`predicateWhy`) backed by the trace measurement. PASS/FAIL/UNKNOWN stays visible as a pill.
   - Raw predicate JSON moved into a per-panel **"Trace details"** Developer drawer (also in the
     `data-raw` attribute); it is no longer in the default view.

4. **Known-timestamp / non-match clarity.**
   - The probe stays in Developer tools (not the primary flow). After inspecting, it shows a readable
     outcome (`timestampOutcomeSummary`), e.g. `NO_COMPATIBLE_ANCHOR` → "No matching moment at this
     timestamp for the current plan." Raw record remains in Developer details.

5. **Beta 1A.1 state behavior preserved.** No changes to the reducer, booting state, invalidation, or
   cold-run state; no boot-flash regression.

## Tests

- `npm run test:acceptance`: **PASS** — contracts, fixtures, **5 unit suites** (geometry, playback,
  presentation, workbenchState, **overlay**), **16 Playwright tests**.
- New unit suite `tests/overlay.test.ts`: interval / witness / none classification, visibility timing,
  proof strings, legend lines, and the "no covered frames → downgrade to witness, not guess" rule.
- `tests/presentation.test.ts`: extended with `humanizePredicate`, `predicateWhy`,
  `timestampOutcomeSummary`.
- New e2e: `beta1b corridor overlay shows only within its valid interval, with a legend` (overlay
  visible at witness frame, hidden when scrubbed away, legend present) and `beta1b result rail groups
  by match and shows readable why-matched summaries`.
- Existing approved + experimental journeys, stale-state, model-unavailable/clarification/gap,
  host-authority, novel-composition-pending, booting, and cold-run tests all still pass.
- `tsc --noEmit`: clean. Backend untouched (no backend contract tests run — none touched).

## Screenshots

`artifacts/workbench-alpha/beta1a-proof/screenshots/`:
- `b1b-01-overlay-valid.png` — corridor visible during its valid (witness) interval
- `b1b-02-overlay-hidden.png` — overlay hidden outside the interval
- `b1b-03-result-grouping.png` — result rail grouped by match with principal measurements
- `b1b-04-why-matched.png` — readable why-matched predicate summary + Trace details drawer
- `b1b-05-developer-details.png` — Developer details still expose raw internals

## Acceptance

- ✅ Approved recipe journey and experimental corridor preset journey still work.
- ✅ Replay overlay does not appear outside its valid evidence interval; missing geometry hides/
  downgrades — no guessed corridors.
- ✅ Result cards are easier to scan (grouped + measurements) and still deterministic.
- ✅ Why-matched summaries are readable and backed by trace/evidence; PASS/FAIL/UNKNOWN visible.
- ✅ Developer details still expose raw internals (plan/run/trace/timestamp JSON).
- ✅ Existing Beta 1A/1A.1 tests pass; new tests cover overlay timing/legend and evidence summaries.

## Out of scope / next

- No `HERMES_NOVEL_COMPOSITION` exposure; pending-proof gate intact (Beta 1C, after N1D's external yes).
- For the current presets the corridor is witness-frame-only (no open/close frames in product
  evidence); the interval path is implemented and unit-tested for evidence that does carry them.
