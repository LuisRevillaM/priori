import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  bootstrap,
  confirm,
  execute,
  executionCacheStatus,
  fetchMatches,
  fetchPlan,
  inspectResult,
  inspectTimestamp,
  interpret,
  submitValidate
} from "./api";
import { PitchCanvas } from "./PitchCanvas";
import { advancePlaybackFrame } from "./playback";
import type {
  BootstrapResponse,
  ConfirmationResponse,
  ExecutionProgressResponse,
  ExecutionResponse,
  InspectResultResponse,
  InspectTimestampResponse,
  InterpretResponse,
  JsonObject,
  MatchLibraryResponse,
  MatchSummary,
  Preset,
  ReplayPayload,
  ResultRow,
  SubmitValidateResponse,
  TimestampTarget
} from "./types";

type BusyKey =
  | "bootstrap"
  | "interpret"
  | "validate"
  | "confirm"
  | "execute"
  | "inspect"
  | "timestamp";

const DEFAULT_QUERY = "Show possessions where the ball goes wide and the defending block moves toward that side.";

function asRecord(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
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
    return {
      id: `${alias}-${index}`,
      alias,
      source: `${node}.${String(source.output_name ?? "")}`,
      field
    };
  });
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function applyScopeToPlan(planDocument: JsonObject, matchIds: string[]): JsonObject {
  const next = structuredClone(planDocument) as JsonObject;
  const invocation = asRecord(next.default_invocation);
  invocation.match_ids = matchIds;
  invocation.periods = asArray(invocation.periods).length > 0 ? invocation.periods : ["firstHalf", "secondHalf"];
  invocation.perspective_team_role = invocation.perspective_team_role || "home";
  next.default_invocation = invocation;
  return next;
}

function periodLabel(period: string | null | undefined) {
  return period === "secondHalf" ? "Second half" : period === "firstHalf" ? "First half" : "Period";
}

function frameTimeLabel(frameId: number | null | undefined, frameRateHz = 25) {
  if (typeof frameId !== "number" || !Number.isFinite(frameId) || frameId < 0) return "";
  const totalSeconds = Math.round(frameId / frameRateHz);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function matchLabel(match: MatchSummary | undefined, fallbackId: string) {
  if (!match) return fallbackId;
  return match.match_title.replace(":", " vs ");
}

function sourceLabel(source: string | null | undefined) {
  if (!source) return "Not interpreted";
  if (source.includes("hermes")) return "Hermes frontier agent";
  if (source === "manual_preset") return "Manual recipe";
  if (source.includes("manual")) return "Manual fallback";
  return source;
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

function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function JsonBlock({ value, compact = false }: { value: unknown; compact?: boolean }) {
  return <pre className={compact ? "jsonBlock compact" : "jsonBlock"}>{pretty(value)}</pre>;
}

export function App() {
  const [boot, setBoot] = useState<BootstrapResponse | null>(null);
  const [matchLibrary, setMatchLibrary] = useState<MatchLibraryResponse | null>(null);
  const [selectedMatchIds, setSelectedMatchIds] = useState<string[]>([]);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [mode, setMode] = useState<"manual" | "model">("manual");
  const [selectedPreset, setSelectedPreset] = useState<Preset["preset_id"]>("approved_block_shift");
  const [planDocument, setPlanDocument] = useState<JsonObject | null>(null);
  const [interpretation, setInterpretation] = useState<InterpretResponse | null>(null);
  const [validation, setValidation] = useState<SubmitValidateResponse | null>(null);
  const [confirmation, setConfirmation] = useState<ConfirmationResponse | null>(null);
  const [executionProgress, setExecutionProgress] = useState<ExecutionProgressResponse | null>(null);
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
  const [inspection, setInspection] = useState<InspectResultResponse | null>(null);
  const [timestampInspection, setTimestampInspection] = useState<InspectTimestampResponse | null>(null);
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
  const [inspectionLoadingResultId, setInspectionLoadingResultId] = useState<string | null>(null);
  const [busy, setBusy] = useState<BusyKey | null>("bootstrap");
  const [error, setError] = useState<string | null>(null);
  const inspectionGenerationRef = useRef(0);
  const playbackRef = useRef<{ previousTimestamp: number | null; carriedMs: number }>({
    previousTimestamp: null,
    carriedMs: 0
  });

  const inspectedResultId = inspection?.inspection.result.result_id ?? null;
  const effectiveSelectedResultId = selectedResultId ?? inspectedResultId;

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
      .then(([bootPayload, matchPayload]) => {
        setBoot(bootPayload);
        setMatchLibrary(matchPayload);
        setSelectedMatchIds(matchPayload.default_match_ids);
        return fetchPlan("ball_side_block_shift_v1").then((planPayload) => ({
          planPayload,
          matchIds: matchPayload.default_match_ids
        }));
      })
      .then(({ planPayload, matchIds }) => {
        setPlanDocument(applyScopeToPlan(planPayload.plan_document, matchIds));
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setBusy(null));
  }, []);

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

  async function runAction<T>(key: BusyKey, action: () => Promise<T>): Promise<T | null> {
    setBusy(key);
    setError(null);
    try {
      return await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function choosePreset(presetId: Preset["preset_id"]) {
    setSelectedPreset(presetId);
    const recipeId = presetId === "approved_block_shift" ? "ball_side_block_shift_v1" : "possession_corridor_availability_v1";
    const payload = await runAction("interpret", () => fetchPlan(recipeId));
    if (!payload) return;
    const scopedPlan = applyScopeToPlan(payload.plan_document, selectedMatchIds);
    setPlanDocument(scopedPlan);
    setInterpretation({
      ok: true,
      status: "PLAN_INTERPRETED",
      query: null,
      message: null,
      source: "manual_preset",
      agent_session_id: null,
      draft_plan_id: null,
      bound_plan_id: null,
      bound_plan_hash: null,
      recipe: payload.recipe,
      plan_document: scopedPlan,
      plan_hash: payload.plan_hash,
      clarification_questions: null,
      clarification_codes: null,
      capability_gaps: null,
      manual_available: null
    });
    setValidation(null);
    setConfirmation(null);
    setExecutionProgress(null);
    setExecution(null);
    setInspection(null);
    setTimestampInspection(null);
    setInspectionLoadingResultId(null);
  }

  function setAllMatches() {
    const allIds = matchLibrary?.default_match_ids ?? [];
    setSelectedMatchIds(allIds);
    if (planDocument) setPlanDocument(applyScopeToPlan(planDocument, allIds));
    setValidation(null);
    setConfirmation(null);
    setExecutionProgress(null);
    setExecution(null);
    setInspection(null);
    setTimestampInspection(null);
  }

  function toggleMatch(matchId: string) {
    const allIds = matchLibrary?.default_match_ids ?? [];
    const next = selectedMatchIds.includes(matchId)
      ? selectedMatchIds.filter((id) => id !== matchId)
      : [...selectedMatchIds, matchId].sort((a, b) => allIds.indexOf(a) - allIds.indexOf(b));
    const safeNext = next.length > 0 ? next : [matchId];
    setSelectedMatchIds(safeNext);
    if (planDocument) setPlanDocument(applyScopeToPlan(planDocument, safeNext));
    setValidation(null);
    setConfirmation(null);
    setExecutionProgress(null);
    setExecution(null);
    setInspection(null);
    setTimestampInspection(null);
  }

  async function handleInterpret() {
    const payload = await runAction("interpret", () =>
      interpret({
        query,
        mode,
        preset_id: selectedPreset
      })
    );
    if (!payload) return;
    setInterpretation(payload);
    if (payload.status === "PLAN_INTERPRETED" && payload.plan_document) {
      setPlanDocument(applyScopeToPlan(payload.plan_document, selectedMatchIds));
      setValidation(null);
      setConfirmation(null);
      setExecutionProgress(null);
      setExecution(null);
      setInspection(null);
      setTimestampInspection(null);
      setInspectionLoadingResultId(null);
    }
  }

  async function handleValidate() {
    if (!planDocument) return;
    const scopedPlan = applyScopeToPlan(planDocument, selectedMatchIds);
    setPlanDocument(scopedPlan);
    const payload = await runAction("validate", () => submitValidate(scopedPlan));
    if (!payload) return;
    setValidation(payload);
    setConfirmation(null);
    setExecutionProgress(null);
    setExecution(null);
    setInspection(null);
    setTimestampInspection(null);
    setInspectionLoadingResultId(null);
  }

  async function handleConfirm() {
    const boundPlanId = validation?.validation.bound_plan_id;
    if (!boundPlanId) return;
    const payload = await runAction("confirm", () => confirm(boundPlanId));
    if (!payload) return;
    setConfirmation(payload);
    setExecutionProgress(null);
  }

  async function handleExecute() {
    const boundPlanId = confirmation?.confirmation.bound_plan_id;
    const authorizationId = confirmation?.confirmation.execution_authorization_id;
    if (!boundPlanId || !authorizationId) return;
    setExecutionProgress({
      ok: true,
      cache_key: "pending",
      cache_status: "MISS",
      message: "Checking host-owned execution cache.",
      stages: ["authorization_checked"]
    });
    const cache = await runAction("execute", () =>
      executionCacheStatus({
        bound_plan_id: boundPlanId,
        execution_authorization_id: authorizationId,
        result_limit: 25
      })
    );
    if (!cache) return;
    setExecutionProgress({
      ...cache,
      message:
        cache.cache_status === "HIT"
          ? "Cache hit: loading cached deterministic execution."
          : "Cache miss: deterministic runtime is running."
    });
    const payload = await runAction("execute", () =>
      execute({
        bound_plan_id: boundPlanId,
        execution_authorization_id: authorizationId,
        result_limit: 25
      })
    );
    if (!payload) return;
    setExecutionProgress(payload.cache);
    setExecution(payload);
    const first = payload.execution.results[0];
    setSelectedResultId(first?.result_id ?? null);
    if (first) {
      setTarget((current) => ({
        ...current,
        match_id: first.match_id,
        period: first.period === "secondHalf" ? "secondHalf" : "firstHalf"
      }));
      await inspectSpecificResult(payload.execution.execution_id, first.result_id);
    }
  }

  async function inspectSpecificResult(executionId: string, resultId: string) {
    const generation = inspectionGenerationRef.current + 1;
    inspectionGenerationRef.current = generation;
    setInspection(null);
    setTimestampInspection(null);
    setInspectionLoadingResultId(resultId);
    const payload = await runAction("inspect", () =>
      inspectResult({
        execution_id: executionId,
        result_id: resultId,
        padding_seconds: 2
      })
    );
    if (!payload) {
      if (inspectionGenerationRef.current === generation) {
        setInspectionLoadingResultId(null);
      }
      return;
    }
    if (inspectionGenerationRef.current !== generation) return;
    if (payload.inspection.result.result_id !== resultId) return;
    setInspection(payload);
    setInspectionLoadingResultId(null);
  }

  async function handleResultSelect(resultId: string) {
    setSelectedResultId(resultId);
    const executionId = execution?.execution.execution_id;
    if (!executionId) return;
    await inspectSpecificResult(executionId, resultId);
  }

  async function handleInspectTimestamp() {
    const executionId = execution?.execution.execution_id;
    if (!executionId) return;
    const payload = await runAction("timestamp", () =>
      inspectTimestamp({
        execution_id: executionId,
        target,
        padding_seconds: 2
      })
    );
    if (!payload) return;
    inspectionGenerationRef.current += 1;
    setTimestampInspection(payload);
    setInspection(null);
    setInspectionLoadingResultId(null);
  }

  const validationTone = validation?.validation.ok ? "good" : validation ? "bad" : "neutral";
  const currentFrame = replay?.frames[Math.min(frameIndex, Math.max(0, replay.frames.length - 1))];
  const matchesById = new Map((matchLibrary?.matches ?? []).map((match) => [match.match_id, match]));
  const selectedResultIndex = execution?.execution.results.findIndex((result) => result.result_id === effectiveSelectedResultId) ?? -1;
  const selectedResultMatch = selectedResult ? matchesById.get(selectedResult.match_id) : undefined;
  const scopeLabel =
    selectedMatchIds.length === (matchLibrary?.default_match_ids.length ?? 0)
      ? `All ${selectedMatchIds.length || 0} available matches`
      : `${selectedMatchIds.length} selected ${selectedMatchIds.length === 1 ? "match" : "matches"}`;
  const planRecipe = interpretation?.recipe ?? boot?.presets.find((preset) => preset.preset_id === selectedPreset)?.recipe ?? null;
  const interpretationItems = interpretationBullets(planRecipe, planDocument);
  const sourceTone = interpretation?.source?.includes("hermes") ? "good" : interpretation?.source ? "neutral" : "warn";

  return (
    <main className="appShell">
      <header className="topbar">
        <div>
          <div className="eyebrow">Workbench Alpha</div>
          <h1>Host tactical query workbench</h1>
        </div>
        <div className="topbarStatus">
          <StatusPill tone={boot?.service.mcp_adapter === false ? "good" : "warn"}>browser to host API</StatusPill>
          <StatusPill tone={boot?.model.available ? "good" : "warn"}>{boot?.model.status ?? "loading"}</StatusPill>
          <StatusPill tone="neutral">{busy ? `busy: ${busy}` : "idle"}</StatusPill>
        </div>
      </header>

      {error ? <div className="errorBanner" data-testid="error-banner">{error}</div> : null}

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
          <button className={selectedMatchIds.length === (matchLibrary?.default_match_ids.length ?? 0) ? "active" : ""} onClick={setAllMatches}>
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
      </section>

      <section className="workspaceGrid">
        <aside className="leftRail">
          <section className="panel">
            <div className="panelTitle">Query</div>
            <label className="field">
              <span>Natural language</span>
              <textarea data-testid="query-input" value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <div className="segmented">
              <button aria-label="Model" className={mode === "model" ? "active" : ""} onClick={() => setMode("model")}>
                Ask Hermes
              </button>
              <button aria-label="Manual" className={mode === "manual" ? "active" : ""} onClick={() => setMode("manual")}>
                Browse recipes
              </button>
            </div>
            <div className="helperText">Browse recipes is deterministic/offline. Ask Hermes uses the frontier interpreter when available.</div>
            <div className="presetStack">
              {boot?.presets.map((preset) => (
                <button
                  key={preset.preset_id}
                  data-testid={`preset-${preset.preset_id}`}
                  className={selectedPreset === preset.preset_id ? "preset active" : "preset"}
                  onClick={() => void choosePreset(preset.preset_id)}
                >
                  <span>{preset.label}</span>
                  <small>{preset.recipe.state}</small>
                </button>
              ))}
            </div>
            <button className="primaryAction" data-testid="interpret-button" onClick={() => void handleInterpret()} disabled={busy !== null}>
              Interpret
            </button>
          </section>

          <section className="panel">
            <div className="panelHeader">
              <div className="panelTitle">Validation</div>
              <StatusPill tone={validationTone}>{validation?.validation.ok ? "valid" : validation ? "invalid" : "not run"}</StatusPill>
            </div>
            <button className="fullButton" data-testid="validate-button" onClick={() => void handleValidate()} disabled={!planDocument || busy !== null}>
              Submit and validate
            </button>
            <button
              className="fullButton"
              data-testid="confirm-button"
              onClick={() => void handleConfirm()}
              disabled={!validation?.validation.bound_plan_id || busy !== null}
            >
              Host confirm
            </button>
            <button
              className="primaryAction"
              data-testid="execute-button"
              onClick={() => void handleExecute()}
              disabled={!confirmation?.confirmation.execution_authorization_id || busy !== null}
            >
              Execute
            </button>
          </section>

          <section className="panel">
            <div className="panelTitle">Known Timestamp</div>
            <label className="field tight">
              <span>Target ID</span>
              <input value={target.target_id} onChange={(event) => setTarget({ ...target, target_id: event.target.value })} />
            </label>
            <label className="field tight">
              <span>Match ID</span>
              <input data-testid="timestamp-match-id" value={target.match_id} onChange={(event) => setTarget({ ...target, match_id: event.target.value })} />
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
              disabled={!execution?.execution.execution_id || !target.match_id || busy !== null}
            >
              Inspect timestamp
            </button>
          </section>
        </aside>

        <section className="centerStage">
          <section className="panel interpreted" data-testid="interpreted-plan-panel">
            <div className="panelHeader">
              <div>
                <div className="panelTitle">Interpreted as</div>
                <div className="interpretTitle">{planRecipe?.display_name ?? "Choose a recipe or ask Hermes"}</div>
              </div>
              <StatusPill tone={interpretation?.status === "PLAN_INTERPRETED" ? "good" : interpretation ? "warn" : "neutral"}>
                {interpretation?.status ?? "ready"}
              </StatusPill>
            </div>
            {interpretation?.source ? (
              <div className="sourceLine" data-testid="interpretation-source">
                Interpretation source: <strong>{sourceLabel(interpretation.source)}</strong> <code>{interpretation.source}</code>
              </div>
            ) : (
              <div className="sourceLine">
                Interpretation source: <strong>{mode === "model" ? "Hermes frontier agent" : "Manual recipe"}</strong>
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
              <div className="stateBox warn">{interpretation.message}</div>
            ) : null}
            <div className="interpretSummary">
              {interpretationItems.map((item) => (
                <div key={item} className="interpretLine">{item}</div>
              ))}
            </div>
            <div className="interpretMeta">
              <div>
                <span>Scope</span>
                <strong>{scopeLabel}</strong>
              </div>
              <div>
                <span>Status</span>
                <strong>{planRecipe?.state ?? "not selected"}</strong>
              </div>
              <div>
                <span>Source</span>
                <StatusPill tone={sourceTone}>{sourceLabel(interpretation?.source)}</StatusPill>
              </div>
            </div>
            <div className="actionStrip">
              <button className="fullButton" onClick={() => void handleValidate()} disabled={!planDocument || busy !== null}>
                Confirm interpretation
              </button>
              <button className="fullButton" onClick={() => void handleConfirm()} disabled={!validation?.validation.bound_plan_id || busy !== null}>
                Host confirm
              </button>
              <button className="primaryAction" onClick={() => void handleExecute()} disabled={!confirmation?.confirmation.execution_authorization_id || busy !== null}>
                Run query
              </button>
            </div>
            <details className="developerDrawer">
              <summary>Developer details</summary>
              <div className="planMeta">
                <span>{planDocument ? String(asRecord(planDocument.recipe).recipe_id ?? "") : "no recipe"}</span>
                <span>{planDocument ? String(asRecord(planDocument.draft_plan).status ?? "") : "no status"}</span>
                <span>{interpretation?.plan_hash ?? ""}</span>
              </div>
              <JsonBlock value={planDocument ?? {}} compact />
            </details>
          </section>

          <section className="panel canvasPanel">
            <div className="panelHeader">
              <div>
                <div className="panelTitle">Coordinate Replay</div>
                {selectedResult ? (
                  <div className="replayContext" data-testid="replay-window-summary">
                    <strong>{matchLabel(selectedResultMatch, selectedResult.match_id)}</strong>
                    <span>
                      {periodLabel(selectedResult.period)} · {frameTimeLabel(selectedResult.anchor_frame_id, replay?.frame_rate_hz ?? 25)} · Fortuna in possession
                    </span>
                    <span>
                      Result {selectedResultIndex + 1} of {execution?.execution.returned_result_count ?? 0}
                    </span>
                    <small>{replay?.replay_window_id} · {selectedResult.result_id}</small>
                  </div>
                ) : (
                  <div className="muted" data-testid="replay-window-summary">
                    {inspectionLoadingResultId ? `Loading result ${inspectionLoadingResultId}` : "No replay window selected"}
                  </div>
                )}
              </div>
              {currentFrame ? <StatusPill tone="neutral">frame {currentFrame.frame_id}</StatusPill> : null}
            </div>
            <PitchCanvas replay={replay} frameIndex={frameIndex} result={evidenceResult} />
            <div className="replayControls">
              <button onClick={() => setFrameIndex((value) => Math.max(0, value - 1))} disabled={!replay}>
                Prev
              </button>
              <button data-testid="play-pause-button" onClick={() => setPlaying((value) => !value)} disabled={!replay}>
                {playing ? "Pause" : "Play"}
              </button>
              <div className="speedControls" data-testid="playback-speed-controls">
                {([0.5, 1, 2] as const).map((speed) => (
                  <button
                    key={speed}
                    className={playbackSpeed === speed ? "active" : ""}
                    onClick={() => setPlaybackSpeed(speed)}
                    disabled={!replay}
                  >
                    {speed}x
                  </button>
                ))}
              </div>
              <button
                onClick={() => setFrameIndex((value) => Math.min((replay?.frames.length ?? 1) - 1, value + 1))}
                disabled={!replay}
              >
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
                  <div key={item.id} className="evidenceRow" data-testid="evidence-alias">
                    <span>{item.alias}</span>
                    <small>{item.source} / {item.field}</small>
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
              {(execution?.execution.results ?? []).map((result) => (
                <button
                  key={result.result_id}
                  data-testid="result-item"
                  data-result-id={result.result_id}
                  className={effectiveSelectedResultId === result.result_id ? "resultItem active" : "resultItem"}
                  onClick={() => void handleResultSelect(result.result_id)}
                >
                  <span>#{result.rank} {result.classification.replaceAll("_", " ")}</span>
                  <small>{matchLabel(matchesById.get(result.match_id), result.match_id)}</small>
                  <small>{periodLabel(result.period)} · {frameTimeLabel(result.anchor_frame_id)} · {result.result_id}</small>
                </button>
              ))}
              {!execution ? <div className="emptyState">Execute a confirmed bound plan to populate results.</div> : null}
            </div>
          </section>

          <section className="panel">
            <div className="panelTitle">Run State</div>
            {executionProgress ? (
              <div className="progressBox" data-testid="execution-progress">
                <div>
                  <strong>{executionProgress.cache_status}</strong> {executionProgress.message}
                </div>
                <small>{executionProgress.stages.join(" -> ")}</small>
              </div>
            ) : (
              <div className="emptyState">Confirm and run an interpretation to populate moments.</div>
            )}
            <details className="developerDrawer">
              <summary>Developer details</summary>
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

function TraceList({ traces }: { traces: Array<{ predicate_id?: string; status?: string; value?: unknown; threshold?: unknown }> }) {
  if (traces.length === 0) {
    return <div className="emptyState">No predicate trace selected.</div>;
  }
  return (
    <div className="traceList">
      {traces.map((trace, index) => {
        const status = trace.status ?? "UNKNOWN";
        const tone = status === "PASS" ? "good" : status === "FAIL" ? "bad" : "warn";
        return (
          <div key={`${trace.predicate_id ?? "trace"}-${index}`} className="traceRow" data-testid="predicate-trace">
            <StatusPill tone={tone}>{status}</StatusPill>
            <span>{trace.predicate_id ?? "predicate"}</span>
            <small>{pretty({ value: trace.value, threshold: trace.threshold })}</small>
          </div>
        );
      })}
    </div>
  );
}
