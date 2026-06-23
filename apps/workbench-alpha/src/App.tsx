import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  bootstrap,
  confirm,
  execute,
  executionCacheStatus,
  fetchMatches,
  inspectResult,
  inspectTimestamp,
  interpret,
  submitValidate
} from "./api";
import { PitchCanvas } from "./PitchCanvas";
import { advancePlaybackFrame } from "./playback";
import {
  entryModePresentation,
  humanizePredicate,
  predicateWhy,
  principalMeasurement,
  provenanceLabel,
  provenanceTone,
  tacticalHeadline,
  timestampOutcomeSummary
} from "./presentation";
import { corridorOverlayState, overlayLegendLines, overlayProofText, type CorridorOverlay } from "./overlay";
import {
  initialState,
  reducer,
  selectBusy,
  selectCanRun,
  selectHasSelectedScope,
  selectIsNovelComposition,
  selectPlanReady
} from "./workbenchState";
import type {
  BootstrapResponse,
  InterpretResponse,
  JsonObject,
  MatchSummary,
  Preset,
  ReplayPayload,
  ResultRow,
  TimestampTarget
} from "./types";

function asRecord(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function pretty(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function requestedEvidence(planDocument: JsonObject | null) {
  const draft = asRecord(planDocument?.draft_plan);
  const evidence = Array.isArray(draft.requested_evidence) ? draft.requested_evidence : [];
  return evidence.map((item, index) => {
    const request = asRecord(item);
    const source = asRecord(request.source);
    const node = String(source.source_node_id ?? "");
    const field = String(request.field ?? "");
    const alias = String(request.alias ?? `${node}.${field}`);
    return { id: `${alias}-${index}`, alias, source: `${node}.${String(source.output_name ?? "")}`, field };
  });
}

function periodLabel(period: string | null | undefined) {
  return period === "secondHalf" ? "Second half" : period === "firstHalf" ? "First half" : "Period";
}

function matchTimeLabel(matchTimeMs: number | null | undefined) {
  if (typeof matchTimeMs !== "number" || !Number.isFinite(matchTimeMs) || matchTimeMs < 0) return "";
  const totalSeconds = Math.round(matchTimeMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function matchLabel(match: MatchSummary | undefined, fallbackId: string) {
  if (!match) return fallbackId;
  return match.match_title.replace(":", " vs ");
}

function modelStatusCopy(boot: BootstrapResponse | null) {
  if (!boot) return { tone: "neutral" as const, label: "Loading host status" };
  if (boot.model.available) return { tone: "good" as const, label: "Hermes ready" };
  return { tone: "warn" as const, label: "Hermes unavailable · recipes work" };
}

function runStepLabel(step: "validating" | "confirming" | "executing" | null) {
  if (step === "validating") return "Validating plan";
  if (step === "confirming") return "Host confirming";
  if (step === "executing") return "Executing over selected matches";
  return "Preparing";
}

function interpretationBullets(recipe: InterpretResponse["recipe"] | null | undefined, planDocument: JsonObject | null) {
  const invocation = asRecord(planDocument?.default_invocation);
  const params = asRecord(invocation.parameters);
  if (recipe?.recipe_id === "possession_corridor_availability_v1") {
    return [
      "Search possession anchors with a progressive geometric corridor ahead of the ball.",
      `Minimum progression: ${String(params.corridor_minimum_progression_m ?? "recipe default")} metres.`,
      `Minimum defender clearance: ${String(params.corridor_minimum_clearance_m ?? "recipe default")} metres.`,
      `Available window: ${String(params.corridor_max_window_seconds ?? "recipe default")} seconds after the anchor.`,
      "Does not establish that this was the optimal pass."
    ];
  }
  if (recipe?.recipe_id === "ball_side_block_shift_v1") {
    return [
      "Find wide-possession moments where the defending block shifts toward the ball side.",
      "Compare baseline defensive shape to the later maximum-shift shape.",
      "Return moments whose displacement clears the approved block-shift threshold.",
      "Does not infer player intent or coaching instruction."
    ];
  }
  return ["Ask a tactical question or choose a recipe to load an interpretation."];
}

function recipeDescription(recipe: InterpretResponse["recipe"] | null | undefined) {
  if (!recipe) return "Choose a reviewed or experimental recipe to load its deterministic definition.";
  return recipe.description;
}

function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function JsonBlock({ value, compact = false }: { value: unknown; compact?: boolean }) {
  return <pre className={compact ? "jsonBlock compact" : "jsonBlock"}>{pretty(value)}</pre>;
}

export function App() {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const {
    phase,
    boot,
    matchLibrary,
    matchLibraryLoaded,
    selectedMatchIds,
    mode,
    query,
    selectedPreset,
    planDocument,
    interpretation,
    validation,
    confirmation,
    executionProgress,
    execution,
    inspection,
    timestampInspection,
    inspectionLoadingResultId,
    runStep,
    runStartedAt,
    error
  } = state;

  const [target, setTarget] = useState<TimestampTarget>({
    schema_version: "1.0",
    target_id: "known_probe",
    match_id: "",
    period: "firstHalf",
    approximate_time_ms: 0,
    search_radius_ms: 500
  });
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<0.5 | 1 | 2>(1);
  const [nowTs, setNowTs] = useState(0);
  const inspectionGenerationRef = useRef(0);
  const playbackRef = useRef<{ previousTimestamp: number | null; carriedMs: number }>({
    previousTimestamp: null,
    carriedMs: 0
  });

  const busy = selectBusy(state);
  const planReady = selectPlanReady(state);
  const canRun = selectCanRun(state);
  const hasSelectedScope = selectHasSelectedScope(state);
  const isNovelComposition = selectIsNovelComposition(state);
  const booting = phase === "booting";
  const running = phase === "confirming" || phase === "executing";

  const inspectedResultId = inspection?.inspection.result.result_id ?? null;
  const effectiveSelectedResultId = state.selectedResultId ?? inspectedResultId;

  const selectedResult = useMemo<ResultRow | null>(() => {
    const rows = execution?.execution.results ?? [];
    return rows.find((item) => item.result_id === effectiveSelectedResultId) ?? rows[0] ?? null;
  }, [execution, effectiveSelectedResultId]);

  const correlatedInspection =
    inspection && effectiveSelectedResultId && inspection.inspection.result.result_id === effectiveSelectedResultId
      ? inspection
      : null;
  const replay: ReplayPayload | null = timestampInspection?.replay ?? correlatedInspection?.replay ?? null;
  const evidenceResult = correlatedInspection ? selectedResult : null;
  const evidenceAliases = useMemo(() => requestedEvidence(planDocument), [planDocument]);

  useEffect(() => {
    Promise.all([bootstrap(), fetchMatches()])
      .then(([bootPayload, matchPayload]) => dispatch({ type: "BOOT_READY", boot: bootPayload, matchLibrary: matchPayload }))
      .catch((err: unknown) => dispatch({ type: "BOOT_FAILED", error: err instanceof Error ? err.message : String(err) }));
  }, []);

  // Elapsed-time ticker for the cold-run waiting state.
  useEffect(() => {
    if (!running) return;
    setNowTs(Date.now());
    const handle = window.setInterval(() => setNowTs(Date.now()), 250);
    return () => window.clearInterval(handle);
  }, [running]);

  useEffect(() => {
    if (!playing || !replay || replay.frames.length === 0) return;
    let animationFrame = 0;
    const tick = (timestamp: number) => {
      const previous = playbackRef.current.previousTimestamp;
      playbackRef.current.previousTimestamp = timestamp;
      if (previous !== null) {
        const elapsedMs = timestamp - previous;
        setFrameIndex((current) => {
          const step = advancePlaybackFrame({
            currentFrameIndex: current,
            frameCount: replay.frames.length,
            frameRateHz: replay.frame_rate_hz,
            playbackSpeed,
            elapsedMs,
            carriedMs: playbackRef.current.carriedMs
          });
          playbackRef.current.carriedMs = step.carriedMs;
          return step.frameIndex;
        });
      }
      animationFrame = window.requestAnimationFrame(tick);
    };
    animationFrame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(animationFrame);
  }, [playing, replay, playbackSpeed]);

  useEffect(() => {
    setFrameIndex(0);
    setPlaying(false);
    playbackRef.current = { previousTimestamp: null, carriedMs: 0 };
  }, [replay?.replay_window_id]);

  function errorMessage(err: unknown) {
    return err instanceof Error ? err.message : String(err);
  }

  async function handleInterpret() {
    dispatch({ type: "INTERPRET_START" });
    try {
      const payload = await interpret({ query: mode === "model" ? query : "", mode, preset_id: selectedPreset });
      dispatch({ type: "INTERPRET_RESULT", interpretation: payload });
    } catch (err) {
      dispatch({ type: "ERROR", error: errorMessage(err) });
    }
  }

  // One product action ("Confirm and run") drives the full host-authority sequence (validate ->
  // host confirm -> execute). The host still issues the bound plan and execution authorization
  // server-side; this only collapses the steps into one deliberate confirmation.
  async function handleConfirmAndRun() {
    if (!planDocument || !canRun) return;
    const scopedPlan = planDocument;
    try {
      dispatch({ type: "RUN_STEP", step: "validating", startedAt: Date.now() });
      const validationPayload = await submitValidate(scopedPlan);
      dispatch({ type: "VALIDATED", validation: validationPayload });
      const boundPlanId = validationPayload.validation.bound_plan_id;
      if (!validationPayload.validation.ok || !boundPlanId) {
        dispatch({ type: "ERROR", error: "Plan failed host validation." });
        return;
      }

      dispatch({ type: "RUN_STEP", step: "confirming", startedAt: Date.now() });
      const confirmationPayload = await confirm(boundPlanId);
      dispatch({ type: "CONFIRMED", confirmation: confirmationPayload });
      const authorizationId = confirmationPayload.confirmation.execution_authorization_id;
      if (!authorizationId) {
        dispatch({ type: "ERROR", error: "Host did not return an execution authorization." });
        return;
      }

      dispatch({ type: "RUN_STEP", step: "executing", startedAt: Date.now() });
      dispatch({
        type: "EXEC_PROGRESS",
        progress: {
          ok: true,
          cache_key: "pending",
          cache_status: "MISS",
          message: "Checking host-owned execution cache.",
          stages: ["authorization_checked"]
        }
      });
      const cache = await executionCacheStatus({
        bound_plan_id: boundPlanId,
        execution_authorization_id: authorizationId,
        result_limit: 25
      });
      dispatch({
        type: "EXEC_PROGRESS",
        progress: {
          ...cache,
          message:
            cache.cache_status === "HIT"
              ? "Cache hit: loading cached deterministic execution."
              : "Cache miss: deterministic runtime is running."
        }
      });
      const payload = await execute({
        bound_plan_id: boundPlanId,
        execution_authorization_id: authorizationId,
        result_limit: 25
      });
      const first = payload.execution.results[0];
      dispatch({ type: "EXECUTED", execution: payload, selectedResultId: first?.result_id ?? null });
      if (first) {
        setTarget((current) => ({
          ...current,
          match_id: first.match_id,
          period: first.period === "secondHalf" ? "secondHalf" : "firstHalf"
        }));
        await inspectSpecificResult(payload.execution.execution_id, first.result_id);
      }
    } catch (err) {
      dispatch({ type: "ERROR", error: errorMessage(err) });
    }
  }

  async function inspectSpecificResult(executionId: string, resultId: string) {
    const generation = inspectionGenerationRef.current + 1;
    inspectionGenerationRef.current = generation;
    dispatch({ type: "INSPECT_START", resultId });
    try {
      const payload = await inspectResult({ execution_id: executionId, result_id: resultId, padding_seconds: 2 });
      if (inspectionGenerationRef.current !== generation) return;
      if (payload.inspection.result.result_id !== resultId) {
        dispatch({ type: "INSPECT_DONE" });
        return;
      }
      dispatch({ type: "INSPECTED", inspection: payload });
    } catch (err) {
      if (inspectionGenerationRef.current === generation) dispatch({ type: "ERROR", error: errorMessage(err) });
    }
  }

  async function handleResultSelect(resultId: string) {
    dispatch({ type: "SELECT_RESULT", resultId });
    const executionId = execution?.execution.execution_id;
    if (!executionId) return;
    await inspectSpecificResult(executionId, resultId);
  }

  async function handleInspectTimestamp() {
    const executionId = execution?.execution.execution_id;
    if (!executionId) return;
    dispatch({ type: "TIMESTAMP_START" });
    try {
      const payload = await inspectTimestamp({ execution_id: executionId, target, padding_seconds: 2 });
      inspectionGenerationRef.current += 1;
      dispatch({ type: "TIMESTAMP_INSPECTED", timestampInspection: payload });
    } catch (err) {
      dispatch({ type: "ERROR", error: errorMessage(err) });
    }
  }

  const modelStatus = modelStatusCopy(boot);
  const matchesById = new Map((matchLibrary?.matches ?? []).map((match) => [match.match_id, match]));
  const currentFrame = replay?.frames[Math.min(frameIndex, Math.max(0, replay.frames.length - 1))];
  const selectedResultIndex =
    execution?.execution.results.findIndex((result) => result.result_id === effectiveSelectedResultId) ?? -1;
  const selectedResultMatch = selectedResult ? matchesById.get(selectedResult.match_id) : undefined;
  const allMatchCount = matchLibrary?.default_match_ids.length ?? 0;
  const scopeLabel =
    selectedMatchIds.length === allMatchCount
      ? `All ${selectedMatchIds.length || 0} available matches`
      : `${selectedMatchIds.length} selected ${selectedMatchIds.length === 1 ? "match" : "matches"}`;

  const previewRecipe = mode === "manual" ? boot?.presets.find((preset) => preset.preset_id === selectedPreset)?.recipe ?? null : null;
  const displayRecipe = interpretation?.recipe ?? previewRecipe;
  const isPreview = !interpretation && Boolean(previewRecipe);
  const interpretationItems = interpretationBullets(displayRecipe, planDocument);
  const provenance = interpretation?.provenance_source ?? null;
  const sourceTone = provenanceTone(provenance);
  const manualRecipeDescription = recipeDescription(displayRecipe);
  const elapsedSeconds = runStartedAt ? Math.max(0, Math.round((nowTs - runStartedAt) / 1000)) : 0;

  const selectedEvidence = selectedResult?.requested_evidence ?? null;
  const selectedEntryMode = entryModePresentation(
    selectedEvidence?.["destination_entry_mode"] ?? selectedEvidence?.["entry_mode"] ?? asRecord(selectedResult).entry_mode,
    selectedEvidence?.["destination_time_to_entry_seconds"] ?? selectedEvidence?.["time_to_entry_seconds"]
  );
  const overlayState: CorridorOverlay = useMemo(
    () => corridorOverlayState(evidenceResult?.requested_evidence ?? null, replay),
    [evidenceResult, replay]
  );
  const overlayProof = overlayProofText(overlayState, currentFrame?.frame_id);
  const overlayLegend = overlayLegendLines(overlayState);
  const timestampOutcome = timestampOutcomeSummary(timestampInspection?.inspection ?? null);

  // Group results by match for scanability, preserving the deterministic result order within and
  // across groups (groups appear in first-seen order; rows keep their original rank order).
  const resultGroups = useMemo(() => {
    const rows = execution?.execution.results ?? [];
    const groups: Array<{ matchId: string; label: string; rows: ResultRow[] }> = [];
    const indexByMatch = new Map<string, number>();
    for (const row of rows) {
      let index = indexByMatch.get(row.match_id);
      if (index === undefined) {
        index = groups.length;
        indexByMatch.set(row.match_id, index);
        groups.push({ matchId: row.match_id, label: matchLabel(matchesById.get(row.match_id), row.match_id), rows: [] });
      }
      groups[index].rows.push(row);
    }
    return groups;
    // matchesById is rebuilt each render; depend on the data that actually changes it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [execution, matchLibrary]);

  function setAllMatches() {
    dispatch({ type: "SET_SCOPE", ids: matchLibrary?.default_match_ids ?? [] });
  }

  function toggleMatch(matchId: string) {
    const allIds = matchLibrary?.default_match_ids ?? [];
    const next = selectedMatchIds.includes(matchId)
      ? selectedMatchIds.filter((id) => id !== matchId)
      : [...selectedMatchIds, matchId].sort((a, b) => allIds.indexOf(a) - allIds.indexOf(b));
    dispatch({ type: "SET_SCOPE", ids: next });
  }

  return (
    <main className="appShell">
      <header className="topbar">
        <div>
          <div className="eyebrow">Workbench Alpha</div>
          <h1>Host tactical query workbench</h1>
        </div>
        <div
          className="topbarStatus"
          data-testid="host-status"
          data-phase={phase}
          data-model-status={boot?.model.status ?? "loading"}
          data-model-available={String(boot?.model.available ?? false)}
          data-mcp-adapter={String(boot?.service.mcp_adapter ?? "")}
          data-busy={busy ? "true" : "false"}
        >
          <StatusPill tone={modelStatus.tone}>{modelStatus.label}</StatusPill>
          {busy && !booting ? (
            <span className="pill pill-neutral" data-testid="busy-indicator">
              Working…
            </span>
          ) : null}
        </div>
      </header>

      {error ? (
        <div className="errorBanner" data-testid="error-banner">
          {error}
        </div>
      ) : null}

      {booting ? (
        <section className="bootingState" data-testid="booting-state">
          <div className="bootingCard">
            <div className="spinner" aria-hidden="true" />
            <strong>Loading workbench…</strong>
            <span className="muted">Fetching the match library and host capabilities.</span>
          </div>
        </section>
      ) : (
        <>
          <section className="scopeBar" data-testid="analysis-scope">
            <div className="scopeMetric">
              <span>Perspective team</span>
              <strong>{matchLibrary?.perspective_team ?? "Fortuna Düsseldorf"}</strong>
            </div>
            <div className="scopeMetric">
              <span>Matches</span>
              <strong>{scopeLabel}</strong>
            </div>
            <div className="scopeMetric">
              <span>Periods</span>
              <strong>All</strong>
            </div>
            <div className="scopeMetric">
              <span>Possession</span>
              <strong>Fortuna in possession</strong>
            </div>
            <div className="scopePicker" data-testid="match-scope-selector">
              <button className={selectedMatchIds.length === allMatchCount ? "active" : ""} onClick={setAllMatches}>
                All matches
              </button>
              {(matchLibrary?.matches ?? []).map((match) => (
                <button
                  key={match.match_id}
                  className={selectedMatchIds.includes(match.match_id) ? "active" : ""}
                  onClick={() => toggleMatch(match.match_id)}
                  title={match.match_title}
                >
                  {match.away_team.replace("F.C. ", "").replace("1. FC ", "")}
                </button>
              ))}
            </div>
            {matchLibraryLoaded && !hasSelectedScope ? (
              <div className="scopeWarning" data-testid="scope-warning">
                Select at least one match to validate or execute.
              </div>
            ) : null}
          </section>

          <section className="workspaceGrid">
            <aside className="leftRail">
              <section className="panel">
                <div className="panelTitle">Start here</div>
                <div className="pathChooser" data-testid="path-chooser" role="tablist" aria-label="Choose how to start">
                  <button
                    role="tab"
                    aria-selected={mode === "model"}
                    aria-label="Ask Hermes"
                    data-testid="path-ask-hermes"
                    className={mode === "model" ? "pathOption active" : "pathOption"}
                    onClick={() => dispatch({ type: "SET_MODE", mode: "model" })}
                  >
                    <strong>Ask Hermes</strong>
                    <small>Type a football question in your own words.</small>
                  </button>
                  <button
                    role="tab"
                    aria-selected={mode === "manual"}
                    aria-label="Browse recipes"
                    data-testid="path-browse-recipes"
                    className={mode === "manual" ? "pathOption active" : "pathOption"}
                    onClick={() => dispatch({ type: "SET_MODE", mode: "manual" })}
                  >
                    <strong>Browse recipes</strong>
                    <small>Pick a reviewed or experimental recipe.</small>
                  </button>
                </div>
                {mode === "model" ? (
                  <>
                    <label className="field">
                      <span>Natural language</span>
                      <textarea
                        data-testid="query-input"
                        value={query}
                        onChange={(event) => dispatch({ type: "SET_QUERY", query: event.target.value })}
                      />
                    </label>
                    <div className="helperText">
                      Ask Hermes translates football language into a bounded typed plan when the model path is available.
                    </div>
                  </>
                ) : (
                  <>
                    <div className="helperText">
                      Browse recipes loads a stored deterministic definition. The recipe text below is not interpreted as a new request.
                    </div>
                    <div className="presetStack">
                      {boot?.presets.map((preset) => (
                        <button
                          key={preset.preset_id}
                          data-testid={`preset-${preset.preset_id}`}
                          className={selectedPreset === preset.preset_id ? "preset active" : "preset"}
                          onClick={() => dispatch({ type: "SET_PRESET", preset: preset.preset_id })}
                        >
                          <span>{preset.label}</span>
                          <small>{preset.recipe.state}</small>
                        </button>
                      ))}
                    </div>
                    <div className="recipeBrief" data-testid="manual-recipe-description">
                      <strong>{displayRecipe?.display_name ?? "Choose a recipe"}</strong>
                      <span>{manualRecipeDescription}</span>
                    </div>
                  </>
                )}
                <button
                  className={planReady ? "fullButton" : "primaryAction"}
                  data-testid="interpret-button"
                  onClick={() => void handleInterpret()}
                  disabled={busy}
                >
                  {mode === "model"
                    ? planReady
                      ? "Ask Hermes again"
                      : "Ask Hermes"
                    : planReady
                      ? "Reload recipe"
                      : "Use selected recipe"}
                </button>
              </section>

              <details className="panel developerDrawer devPanel" data-testid="developer-tools">
                <summary data-testid="dev-tools-toggle">Developer tools · known-timestamp probe</summary>
                <p className="muted devNote">Engineering inspection tool. Not part of the primary flow.</p>
                <label className="field tight">
                  <span>Target ID</span>
                  <input value={target.target_id} onChange={(event) => setTarget({ ...target, target_id: event.target.value })} />
                </label>
                <label className="field tight">
                  <span>Match ID</span>
                  <input
                    data-testid="timestamp-match-id"
                    value={target.match_id}
                    onChange={(event) => setTarget({ ...target, match_id: event.target.value })}
                  />
                </label>
                <div className="twoCol">
                  <label className="field tight">
                    <span>Period</span>
                    <select
                      value={target.period}
                      onChange={(event) =>
                        setTarget({ ...target, period: event.target.value === "secondHalf" ? "secondHalf" : "firstHalf" })
                      }
                    >
                      <option value="firstHalf">firstHalf</option>
                      <option value="secondHalf">secondHalf</option>
                    </select>
                  </label>
                  <label className="field tight">
                    <span>Radius ms</span>
                    <input
                      type="number"
                      min={1}
                      value={target.search_radius_ms}
                      onChange={(event) => setTarget({ ...target, search_radius_ms: Number(event.target.value) })}
                    />
                  </label>
                </div>
                <label className="field tight">
                  <span>Approx time ms</span>
                  <input
                    type="number"
                    min={0}
                    data-testid="timestamp-time-ms"
                    value={target.approximate_time_ms}
                    onChange={(event) => setTarget({ ...target, approximate_time_ms: Number(event.target.value) })}
                  />
                </label>
                <button
                  className="fullButton"
                  data-testid="inspect-timestamp-button"
                  onClick={() => void handleInspectTimestamp()}
                  disabled={!execution?.execution.execution_id || !target.match_id || busy}
                >
                  Inspect timestamp
                </button>
                {timestampOutcome ? (
                  <p className="muted devNote" data-testid="timestamp-outcome">
                    {timestampOutcome}
                  </p>
                ) : null}
              </details>
            </aside>

            <section className="centerStage">
              <section className="panel interpreted" data-testid="interpreted-plan-panel">
                <div className="panelHeader">
                  <div>
                    <div className="panelTitle">Interpreted as</div>
                    <div className="interpretTitle">
                      {displayRecipe?.display_name ?? (mode === "model" ? "Ask Hermes to interpret your question" : "Choose a recipe")}
                    </div>
                  </div>
                  <StatusPill tone={interpretation?.status === "PLAN_INTERPRETED" ? "good" : interpretation ? "warn" : "neutral"}>
                    {interpretation?.status ?? (isPreview ? "preview" : "ready")}
                  </StatusPill>
                </div>
                {interpretation?.source ? (
                  <div
                    className="sourceLine"
                    data-testid="interpretation-source"
                    data-raw-source={interpretation.source}
                    data-provenance-source={interpretation.provenance_source}
                  >
                    Source: <StatusPill tone={sourceTone}>{provenanceLabel(interpretation.provenance_source)}</StatusPill>
                    {interpretation.fallback_reason ? <span className="sourceReason">{interpretation.fallback_reason}</span> : null}
                  </div>
                ) : isPreview ? (
                  <div className="sourceLine" data-testid="recipe-preview-badge">
                    <StatusPill tone="warn">Preview — not yet interpreted</StatusPill>
                    <span className="sourceReason">Use the selected recipe to interpret before running.</span>
                  </div>
                ) : (
                  <div className="sourceLine">
                    Source: <StatusPill tone="warn">Not interpreted</StatusPill>
                  </div>
                )}
                {interpretation?.status === "CLARIFICATION_REQUIRED" ? (
                  <StateList title="I need clarification" items={interpretation.clarification_questions ?? []} />
                ) : null}
                {interpretation?.status === "CAPABILITY_GAP" ? (
                  <div className="stateBox bad">
                    <strong>This cannot currently be measured</strong>
                    {(interpretation.capability_gaps ?? []).map((gap) => (
                      <p key={gap.concept}>
                        <strong>{gap.concept}</strong>: {gap.reason}
                      </p>
                    ))}
                  </div>
                ) : null}
                {interpretation?.status === "MODEL_UNAVAILABLE" ? (
                  <div className="stateBox warn" data-testid="model-unavailable-state">
                    <strong>Hermes interpretation is not available right now</strong>
                    <p>{interpretation.message}</p>
                    <p>
                      Browse recipes still works. It runs reviewed and experimental recipes deterministically — this is
                      recipe/manual analysis, not a fallback AI interpretation.
                    </p>
                    {interpretation.manual_available ? (
                      <button
                        className="fullButton"
                        data-testid="switch-to-recipes"
                        onClick={() => dispatch({ type: "SET_MODE", mode: "manual" })}
                      >
                        Switch to Browse recipes
                      </button>
                    ) : null}
                  </div>
                ) : null}
                {isNovelComposition ? (
                  <div className="stateBox warn" data-testid="novel-composition-pending">
                    <strong>Novel composition is not product-ready yet</strong>
                    <p>
                      Live model-authored composition is held back pending an N1C runtime proof refresh. This
                      interpretation is shown for transparency only and cannot be run as a product result here.
                    </p>
                  </div>
                ) : null}
                <div className="interpretSummary">
                  {interpretationItems.map((item) => (
                    <div key={item} className="interpretLine">
                      {item}
                    </div>
                  ))}
                </div>
                <div className="interpretMeta">
                  <div>
                    <span>Scope</span>
                    <strong>{scopeLabel}</strong>
                  </div>
                  <div>
                    <span>Validation</span>
                    <strong>{validation?.validation.ok ? "valid" : validation ? "invalid" : "not run"}</strong>
                  </div>
                  <div>
                    <span>Plan source</span>
                    <StatusPill tone={sourceTone}>{provenanceLabel(provenance)}</StatusPill>
                  </div>
                </div>
                <div className="actionStrip single">
                  <button
                    className="primaryAction"
                    data-testid="primary-action"
                    data-stage={execution ? "ran" : planReady ? "ready" : "interpret"}
                    onClick={() => void handleConfirmAndRun()}
                    disabled={!canRun}
                  >
                    {running ? "Confirming and running…" : execution ? "Run again" : "Confirm and run"}
                  </button>
                  <p className="actionNote" data-testid="confirm-and-run-note">
                    {planReady
                      ? "Host confirms the bound plan and runs the deterministic execution over the selected scope. Nothing runs until you confirm."
                      : "Interpret a question or recipe above, then confirm to run."}
                  </p>
                </div>
                <details className="developerDrawer">
                  <summary>Plan details</summary>
                  <div className="planMeta">
                    <span>{planDocument ? String(asRecord(planDocument.recipe).recipe_id ?? "") : "no recipe"}</span>
                    <span>{interpretation?.provenance_source ?? "no provenance"}</span>
                    <span>{interpretation?.plan_hash ?? ""}</span>
                  </div>
                  <JsonBlock value={interpretation ?? { status: "not_interpreted" }} compact />
                  <JsonBlock value={planDocument ?? {}} compact />
                </details>
              </section>

              <section className="panel canvasPanel">
                <div className="panelHeader">
                  <div>
                    <div className="panelTitle">Coordinate Replay</div>
                    {selectedResult ? (
                      <div
                        className="replayContext"
                        data-testid="replay-window-summary"
                        data-replay-window-id={replay?.replay_window_id ?? ""}
                        data-result-id={selectedResult.result_id}
                      >
                        <strong>{matchLabel(selectedResultMatch, selectedResult.match_id)}</strong>
                        <span>{tacticalHeadline(selectedResult.classification)}</span>
                        <span>
                          {periodLabel(selectedResult.period)} · {matchTimeLabel(selectedResult.match_time_ms)} · Fortuna in possession
                        </span>
                        <span>
                          Result {selectedResultIndex + 1} of {execution?.execution.returned_result_count ?? 0}
                        </span>
                        {selectedEntryMode ? (
                          <span data-testid="entry-mode" data-entry-mode={selectedEntryMode.value}>
                            Destination entry: {selectedEntryMode.label}
                          </span>
                        ) : null}
                      </div>
                    ) : (
                      <div className="muted" data-testid="replay-window-summary">
                        {inspectionLoadingResultId ? `Loading result ${inspectionLoadingResultId}` : "No replay window selected"}
                      </div>
                    )}
                  </div>
                  {currentFrame ? <StatusPill tone="neutral">frame {currentFrame.frame_id}</StatusPill> : null}
                </div>
                <PitchCanvas replay={replay} frameIndex={frameIndex} result={evidenceResult} overlay={overlayState} />
                <div className="overlayProof" data-testid="overlay-proof" data-overlay-kind={overlayState.kind}>
                  {overlayProof}
                </div>
                <div className="overlayLegend" data-testid="overlay-legend">
                  {overlayLegend.map((line) => (
                    <p key={line}>{line}</p>
                  ))}
                </div>
                <div className="replayControls">
                  <button onClick={() => setFrameIndex((value) => Math.max(0, value - 1))} disabled={!replay}>
                    Prev
                  </button>
                  <button data-testid="play-pause-button" onClick={() => setPlaying((value) => !value)} disabled={!replay}>
                    {playing ? "Pause" : "Play"}
                  </button>
                  <div className="speedControls" data-testid="playback-speed-controls">
                    {([0.5, 1, 2] as const).map((speed) => (
                      <button key={speed} className={playbackSpeed === speed ? "active" : ""} onClick={() => setPlaybackSpeed(speed)} disabled={!replay}>
                        {speed}x
                      </button>
                    ))}
                  </div>
                  <button onClick={() => setFrameIndex((value) => Math.min((replay?.frames.length ?? 1) - 1, value + 1))} disabled={!replay}>
                    Next
                  </button>
                  <input
                    type="range"
                    data-testid="replay-scrubber"
                    min={0}
                    max={Math.max(0, (replay?.frames.length ?? 1) - 1)}
                    value={frameIndex}
                    onChange={(event) => setFrameIndex(Number(event.target.value))}
                    disabled={!replay}
                  />
                </div>
              </section>

              <section className="detailGrid">
                <div className="panel">
                  <div className="panelTitle">Evidence Aliases</div>
                  <div className="evidenceGrid" data-testid="evidence-aliases">
                    {evidenceAliases.map((item) => (
                      <div
                        key={item.id}
                        className="evidenceRow"
                        data-testid="evidence-alias"
                        data-source={item.source}
                        data-field={item.field}
                      >
                        <span>{item.alias}</span>
                        <code>{String(evidenceResult?.requested_evidence[item.alias] ?? "")}</code>
                      </div>
                    ))}
                    {inspectionLoadingResultId ? (
                      <div className="emptyState" data-testid="inspection-loading">
                        Loading selected result evidence.
                      </div>
                    ) : null}
                  </div>
                </div>
                <div className="panel">
                  <div className="panelTitle">Predicate Trace</div>
                  <TraceList traces={correlatedInspection?.inspection.predicate_traces ?? []} />
                  {correlatedInspection?.inspection.predicate_traces?.length ? (
                    <details className="developerDrawer">
                      <summary>Trace details</summary>
                      <JsonBlock value={correlatedInspection.inspection.predicate_traces} compact />
                    </details>
                  ) : null}
                </div>
              </section>
            </section>

            <aside className="rightRail">
              <section className="panel">
                <div className="panelHeader">
                  <div className="panelTitle">Result Rail</div>
                  <StatusPill tone="neutral">
                    <span data-testid="result-count">{execution?.execution.returned_result_count ?? 0}</span> shown
                  </StatusPill>
                </div>
                <div className="resultList" data-testid="result-rail">
                  {resultGroups.map((group) => (
                    <div key={group.matchId} className="resultGroup" data-testid="result-group" data-match-id={group.matchId}>
                      <div className="resultGroupHeader" data-testid="result-group-header">
                        <span>{group.label}</span>
                        <small>
                          {group.rows.length} {group.rows.length === 1 ? "moment" : "moments"}
                        </small>
                      </div>
                      {group.rows.map((result) => {
                        const measurement = principalMeasurement(result.requested_evidence);
                        return (
                          <button
                            key={result.result_id}
                            data-testid="result-item"
                            data-result-id={result.result_id}
                            data-classification={result.classification}
                            className={effectiveSelectedResultId === result.result_id ? "resultItem active" : "resultItem"}
                            onClick={() => void handleResultSelect(result.result_id)}
                          >
                            <span>
                              #{result.rank} · {tacticalHeadline(result.classification)}
                            </span>
                            <small>
                              {periodLabel(result.period)} · {matchTimeLabel(result.match_time_ms)}
                            </small>
                            {measurement ? (
                              <small
                                className="resultMeasurement"
                                data-testid="result-measurement"
                                data-measurement-key={measurement.key}
                                data-measurement-raw={measurement.raw}
                              >
                                {measurement.label}
                              </small>
                            ) : null}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                  {!execution ? <div className="emptyState">Confirm and run an interpretation to populate results.</div> : null}
                </div>
              </section>

              <section className="panel">
                <div className="panelTitle">Run State</div>
                {running ? (
                  <div className="coldRunState" data-testid="cold-run-state" data-run-step={runStep ?? ""}>
                    <div className="coldRunHeader">
                      <span className="spinner" aria-hidden="true" />
                      <strong>{runStepLabel(runStep)}</strong>
                    </div>
                    <div className="coldRunMeta">
                      <span data-testid="cold-run-elapsed">Elapsed {elapsedSeconds}s</span>
                      <span>{scopeLabel}</span>
                    </div>
                    <small>First run may take longer; repeat runs are cached.</small>
                    <small className="muted">This runs on the host and cannot be canceled once started.</small>
                  </div>
                ) : executionProgress ? (
                  <div className="progressBox" data-testid="execution-progress">
                    <div>
                      <strong>{executionProgress.cache_status}</strong> {executionProgress.message}
                    </div>
                    <small>Searching {scopeLabel.toLowerCase()} across all periods. First runs are cached for repeated queries.</small>
                    <details className="developerDrawer inlineDrawer">
                      <summary>Run stages</summary>
                      <small>{executionProgress.stages.join(" -> ")}</small>
                    </details>
                  </div>
                ) : (
                  <div className="emptyState">Confirm and run an interpretation to populate moments.</div>
                )}
                <details className="developerDrawer">
                  <summary>Run details</summary>
                  <div data-testid="validation-result">
                    <JsonBlock value={validation?.validation ?? { status: "not_run" }} compact />
                  </div>
                  <div data-testid="host-confirmation">
                    <JsonBlock value={confirmation?.confirmation ?? { status: "not_confirmed" }} compact />
                  </div>
                  <div data-testid="execution-result">
                    <JsonBlock value={execution?.execution ?? { status: "not_executed" }} compact />
                  </div>
                  <div data-testid="timestamp-inspection">
                    <JsonBlock value={timestampInspection?.inspection ?? { status: "not_run" }} compact />
                  </div>
                </details>
              </section>
            </aside>
          </section>
        </>
      )}
    </main>
  );
}

function StateList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="stateBox warn">
      <strong>{title}</strong>
      {items.map((item) => (
        <p key={item}>{item}</p>
      ))}
    </div>
  );
}

function TraceList({
  traces
}: {
  traces: Array<{ predicate_id?: string; status?: string; value?: unknown; threshold?: unknown; unit?: string | null }>;
}) {
  if (traces.length === 0) {
    return <div className="emptyState">No predicate trace selected.</div>;
  }
  return (
    <div className="traceList">
      {traces.map((trace, index) => {
        const status = trace.status ?? "UNKNOWN";
        const tone = status === "PASS" ? "good" : status === "FAIL" ? "bad" : "warn";
        return (
          <div
            key={`${trace.predicate_id ?? "trace"}-${index}`}
            className="traceRow"
            data-testid="predicate-trace"
            data-predicate-id={trace.predicate_id ?? ""}
            data-raw={pretty({ value: trace.value, threshold: trace.threshold })}
          >
            <StatusPill tone={tone}>{status}</StatusPill>
            <span>{humanizePredicate(trace.predicate_id)}</span>
            <small data-testid="predicate-why">{predicateWhy(status, trace.value, trace.threshold, trace.unit)}</small>
          </div>
        );
      })}
    </div>
  );
}
