import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  bootstrap,
  confirm,
  execute,
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
  ExecutionResponse,
  InspectResultResponse,
  InspectTimestampResponse,
  InterpretResponse,
  JsonObject,
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

function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function JsonBlock({ value, compact = false }: { value: unknown; compact?: boolean }) {
  return <pre className={compact ? "jsonBlock compact" : "jsonBlock"}>{pretty(value)}</pre>;
}

export function App() {
  const [boot, setBoot] = useState<BootstrapResponse | null>(null);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [mode, setMode] = useState<"manual" | "model">("manual");
  const [selectedPreset, setSelectedPreset] = useState<Preset["preset_id"]>("approved_block_shift");
  const [planDocument, setPlanDocument] = useState<JsonObject | null>(null);
  const [interpretation, setInterpretation] = useState<InterpretResponse | null>(null);
  const [validation, setValidation] = useState<SubmitValidateResponse | null>(null);
  const [confirmation, setConfirmation] = useState<ConfirmationResponse | null>(null);
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
    bootstrap()
      .then((payload) => {
        setBoot(payload);
        return fetchPlan("ball_side_block_shift_v1");
      })
      .then((payload) => {
        setPlanDocument(payload.plan_document);
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
    setPlanDocument(payload.plan_document);
    setInterpretation({
      ok: true,
      status: "PLAN_INTERPRETED",
      recipe: payload.recipe,
      plan_document: payload.plan_document,
      plan_hash: payload.plan_hash
    });
    setValidation(null);
    setConfirmation(null);
    setExecution(null);
    setInspection(null);
    setTimestampInspection(null);
    setInspectionLoadingResultId(null);
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
      setPlanDocument(payload.plan_document);
      setValidation(null);
      setConfirmation(null);
      setExecution(null);
      setInspection(null);
      setTimestampInspection(null);
      setInspectionLoadingResultId(null);
    }
  }

  async function handleValidate() {
    if (!planDocument) return;
    const payload = await runAction("validate", () => submitValidate(planDocument));
    if (!payload) return;
    setValidation(payload);
    setConfirmation(null);
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
  }

  async function handleExecute() {
    const boundPlanId = confirmation?.confirmation.bound_plan_id;
    const authorizationId = confirmation?.confirmation.execution_authorization_id;
    if (!boundPlanId || !authorizationId) return;
    const payload = await runAction("execute", () =>
      execute({
        bound_plan_id: boundPlanId,
        execution_authorization_id: authorizationId,
        result_limit: 25
      })
    );
    if (!payload) return;
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

      <section className="workspaceGrid">
        <aside className="leftRail">
          <section className="panel">
            <div className="panelTitle">Query</div>
            <label className="field">
              <span>Natural language</span>
              <textarea data-testid="query-input" value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <div className="segmented">
              <button className={mode === "manual" ? "active" : ""} onClick={() => setMode("manual")}>
                Manual
              </button>
              <button className={mode === "model" ? "active" : ""} onClick={() => setMode("model")}>
                Model
              </button>
            </div>
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
                <div className="panelTitle">Interpreted Plan</div>
                <div className="muted">{interpretation?.recipe?.display_name ?? "No interpreted plan loaded"}</div>
              </div>
              {interpretation ? <StatusPill tone={interpretation.status === "PLAN_INTERPRETED" ? "good" : "warn"}>{interpretation.status}</StatusPill> : null}
            </div>
            {interpretation?.status === "CLARIFICATION_REQUIRED" ? (
              <StateList title="Clarification" items={interpretation.clarification_questions ?? []} />
            ) : null}
            {interpretation?.status === "CAPABILITY_GAP" ? (
              <div className="stateBox bad">
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
            <div className="planMeta">
              <span>{planDocument ? String(asRecord(planDocument.recipe).recipe_id ?? "") : "no recipe"}</span>
              <span>{planDocument ? String(asRecord(planDocument.draft_plan).status ?? "") : "no status"}</span>
              <span>{interpretation?.plan_hash ?? ""}</span>
            </div>
            <JsonBlock value={planDocument ?? {}} compact />
          </section>

          <section className="panel canvasPanel">
            <div className="panelHeader">
              <div>
                <div className="panelTitle">Coordinate Replay</div>
                <div className="muted" data-testid="replay-window-summary">
                  {inspectionLoadingResultId
                    ? `Loading result ${inspectionLoadingResultId}`
                    : replay
                    ? `${replay.replay_window_id} ${replay.source_id} ${replay.match_id} ${replay.period} ${replay.start_frame_id}-${replay.end_frame_id}`
                    : "No replay window selected"}
                </div>
              </div>
              {currentFrame ? <StatusPill tone="neutral">frame {currentFrame.frame_id}</StatusPill> : null}
            </div>
            <PitchCanvas replay={replay} frameIndex={frameIndex} />
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
                  <span>#{result.rank} {result.classification}</span>
                  <small>{result.result_id}</small>
                  <small>{result.match_id} / {result.period} / frame {result.anchor_frame_id}</small>
                </button>
              ))}
              {!execution ? <div className="emptyState">Execute a confirmed bound plan to populate results.</div> : null}
            </div>
          </section>

          <section className="panel">
            <div className="panelTitle">Validation Result</div>
            <div data-testid="validation-result">
              <JsonBlock value={validation?.validation ?? { status: "not_run" }} compact />
            </div>
          </section>

          <section className="panel">
            <div className="panelTitle">Host Confirmation</div>
            <div data-testid="host-confirmation">
              <JsonBlock value={confirmation?.confirmation ?? { status: "not_confirmed" }} compact />
            </div>
          </section>

          <section className="panel">
            <div className="panelTitle">Execution</div>
            <div data-testid="execution-result">
              <JsonBlock value={execution?.execution ?? { status: "not_executed" }} compact />
            </div>
          </section>

          <section className="panel">
            <div className="panelTitle">Timestamp Inspection</div>
            <div data-testid="timestamp-inspection">
              <JsonBlock value={timestampInspection?.inspection ?? { status: "not_run" }} compact />
            </div>
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
