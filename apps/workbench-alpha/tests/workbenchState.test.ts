import assert from "node:assert/strict";
import {
  initialState,
  reducer,
  selectCanRun,
  selectPlanReady,
  selectIsUnverifiedExperimental,
  type WorkbenchState
} from "../src/workbenchState";
import type {
  BootstrapResponse,
  ExecutionResponse,
  InterpretResponse,
  MatchLibraryResponse,
  SubmitValidateResponse
} from "../src/types";

const cast = <T>(value: unknown) => value as T;

const matchLibrary = cast<MatchLibraryResponse>({
  ok: true,
  perspective_team: "Fortuna",
  default_match_ids: ["J03WOY", "J03WPY"],
  matches: []
});
const boot = cast<BootstrapResponse>({ model: { available: false, status: "X" }, service: {}, presets: [] });

const planInterpreted = cast<InterpretResponse>({
  ok: true,
  status: "PLAN_INTERPRETED",
  provenance_source: "REVIEWED_RECIPE",
  plan_document: { draft_plan: {}, default_invocation: {} }
});
const novel = cast<InterpretResponse>({
  ok: true,
  status: "PLAN_INTERPRETED",
  provenance_source: "HERMES_NOVEL_COMPOSITION",
  plan_document: { draft_plan: {}, default_invocation: { match_ids: ["J03WOY"], periods: ["firstHalf"], perspective_team_role: "home" } }
});
const unverified = cast<InterpretResponse>({
  ok: true,
  status: "PLAN_INTERPRETED",
  provenance_source: "HERMES_EXPERIMENTAL_UNVERIFIED",
  plan_document: { draft_plan: {}, default_invocation: {} }
});
const modelUnavailable = cast<InterpretResponse>({
  ok: true,
  status: "MODEL_UNAVAILABLE",
  provenance_source: "MODEL_UNAVAILABLE",
  manual_available: true
});
const validation = cast<SubmitValidateResponse>({ ok: true, submit: {}, validation: { ok: true, bound_plan_id: "bound_x", draft_plan_id: "d", issues: [] } });
const execution = cast<ExecutionResponse>({ ok: true, cache: {}, execution: { results: [{ result_id: "r1" }], returned_result_count: 1 } });

// booted base state with full scope selected and a ready plan
function readyState(): WorkbenchState {
  let s = reducer(initialState(), { type: "BOOT_READY", boot, matchLibrary });
  s = reducer(s, { type: "INTERPRET_START" });
  s = reducer(s, { type: "INTERPRET_RESULT", interpretation: planInterpreted });
  return s;
}

// --- boot ---
const fresh = initialState();
assert.equal(fresh.phase, "booting");
assert.equal(fresh.inFlight, true);

const booted = reducer(fresh, { type: "BOOT_READY", boot, matchLibrary });
assert.equal(booted.phase, "idle");
assert.equal(booted.inFlight, false);
assert.equal(booted.matchLibraryLoaded, true);
assert.deepEqual(booted.selectedMatchIds, ["J03WOY", "J03WPY"]);

// --- ready plan ---
const ready = readyState();
assert.equal(ready.phase, "ready");
assert.equal(selectPlanReady(ready), true);
assert.equal(selectCanRun(ready), true);
assert.ok(ready.planDocument, "plan document scoped on interpret");

// --- run -> results ---
let ran = reducer(ready, { type: "RUN_STEP", step: "validating", startedAt: 1 });
assert.equal(ran.phase, "confirming");
assert.equal(ran.inFlight, true);
assert.equal(selectCanRun(ran), false, "cannot run while in flight");
ran = reducer(ran, { type: "VALIDATED", validation });
ran = reducer(ran, { type: "RUN_STEP", step: "executing", startedAt: 1 });
assert.equal(ran.phase, "executing");
ran = reducer(ran, { type: "EXECUTED", execution, selectedResultId: "r1" });
assert.equal(ran.phase, "results");
assert.equal(ran.inFlight, false);
assert.equal(ran.runStep, null);

// --- invalidation: query edit clears interpretation + downstream ---
const afterQuery = reducer(ran, { type: "SET_QUERY", query: "new" });
assert.equal(afterQuery.interpretation, null);
assert.equal(afterQuery.planDocument, null);
assert.equal(afterQuery.execution, null);
assert.equal(afterQuery.validation, null);
assert.equal(afterQuery.phase, "idle");

// --- invalidation: recipe switch clears ---
const afterPreset = reducer(ran, { type: "SET_PRESET", preset: "experimental_corridor" });
assert.equal(afterPreset.interpretation, null);
assert.equal(afterPreset.execution, null);
assert.equal(afterPreset.phase, "idle");

// --- invalidation: mode switch clears (and no-op when same mode) ---
const afterMode = reducer(ran, { type: "SET_MODE", mode: "model" });
assert.equal(afterMode.interpretation, null);
assert.equal(afterMode.execution, null);
assert.equal(afterMode.phase, "idle");
assert.equal(reducer(ran, { type: "SET_MODE", mode: ran.mode }), ran, "same mode is a no-op");

// --- invalidation: scope change keeps interpretation, clears execution; zero scope -> idle ---
const afterScope = reducer(ran, { type: "SET_SCOPE", ids: ["J03WOY"] });
assert.ok(afterScope.interpretation, "scope change keeps the interpretation");
assert.equal(afterScope.execution, null, "scope change clears prior execution");
assert.equal(afterScope.phase, "ready");
const zeroScope = reducer(ran, { type: "SET_SCOPE", ids: [] });
assert.equal(zeroScope.phase, "idle");
assert.equal(selectCanRun(zeroScope), false, "no scope -> cannot run");

// --- non-plan interpretation (model unavailable) is not runnable ---
let mu = reducer(readyState(), { type: "INTERPRET_START" });
mu = reducer(mu, { type: "INTERPRET_RESULT", interpretation: modelUnavailable });
assert.equal(mu.planDocument, null);
assert.equal(mu.phase, "idle");
assert.equal(selectPlanReady(mu), false);

// --- verified novel composition is plan-ready, runnable, and scope-locked to the attested invocation ---
let nv = reducer(readyState(), { type: "INTERPRET_START" });
nv = reducer(nv, { type: "INTERPRET_RESULT", interpretation: novel });
assert.equal(selectPlanReady(nv), true);
assert.equal(selectCanRun(nv), true, "verified novel composition is runnable");
assert.deepEqual(nv.selectedMatchIds, ["J03WOY"]);
const novelScopeAttempt = reducer(nv, { type: "SET_SCOPE", ids: ["J03WPY"] });
assert.equal(novelScopeAttempt, nv, "verified novel scope is locked");

// --- unverified experimental draft is plan-ready but not runnable ---
let uv = reducer(readyState(), { type: "INTERPRET_START" });
uv = reducer(uv, { type: "INTERPRET_RESULT", interpretation: unverified });
assert.equal(selectPlanReady(uv), true);
assert.equal(selectIsUnverifiedExperimental(uv), true);
assert.equal(selectCanRun(uv), false, "unverified experimental draft is blocked");

// --- result selection keeps execution ---
const selected = reducer(ran, { type: "SELECT_RESULT", resultId: "r1" });
assert.ok(selected.execution, "selecting a result keeps the execution");

console.log("workbenchState tests passed");
