import { useEffect, useMemo, useState } from "react";
import { WorkbenchApiError, filmRoomAsk, filmRoomBootstrap, filmRoomReplayFrame, filmRoomReplayWindow } from "./api";
import type { FilmRoomAskResponse, FilmRoomBootstrapResponse, FilmRoomIntervalMetric, FilmRoomMoment, JsonObject, ReplayEntity, ReplayFrame, ReplayPayload } from "./types";

const FLAGSHIP_ASK = "After a regain, how often does the team progress the ball by carry and keep it with a controlled pass?";

function asRecord(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "UNKNOWN";
  return `${Math.round(value * 1000) / 10}%`;
}

function formatCount(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "0";
}

function matchClock(frame: ReplayFrame | undefined, replay: ReplayPayload | null | undefined) {
  if (!frame || !replay) return "00:00.00";
  const offsetFrames = Math.max(0, frame.frame_id - replay.start_frame_id);
  const seconds = offsetFrames / replay.frame_rate_hz;
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const centis = Math.floor((seconds % 1) * 100);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(centis).padStart(2, "0")}`;
}

export function assertIntervalMetric(metric: unknown): FilmRoomIntervalMetric {
  const record = asRecord(metric);
  for (const key of ["observed", "lower", "upper", "unknown_count"] as const) {
    const value = record[key];
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new Error(`Film Room interval metric missing finite ${key}.`);
    }
  }
  return {
    label: String(record.label ?? "Runtime evidence interval"),
    observed: record.observed as number,
    lower: record.lower as number,
    upper: record.upper as number,
    unknown_count: record.unknown_count as number,
    source: asRecord(record.source)
  };
}

export function intervalHeadline(metric: FilmRoomIntervalMetric | null | undefined) {
  const source = asRecord(metric?.source);
  return source.evidence_kind === "certified" ? "Certified interval" : "Runtime evidence interval";
}

export function chainStatusLabel(moment: FilmRoomMoment | null | undefined) {
  if (!moment) return "no chain selected";
  if (moment.source_kind === "certified_table_partition") {
    return "certified partition · no chain witness";
  }
  if (typeof moment.chain_status === "string" && moment.chain_status.length > 0) return moment.chain_status;
  return "chain_status not emitted";
}

export function momentCollectionLabel(moments: FilmRoomMoment[], total: number) {
  return moments.some((moment) => moment.source_kind === "certified_table_partition")
    ? `${total} certified table partition previews`
    : `${total} chain moments`;
}

export function filmRoomOutcomeClass(response: FilmRoomAskResponse | null) {
  if (!response) return "pending";
  if (response.answer) return "answer";
  if (response.outcome === "clarification_required") return "clarification";
  if (response.refusal) return "refusal";
  return "pending";
}

export function refusalViewModel(refusal: unknown) {
  const payload = asRecord(refusal);
  if (payload.gap_code === "MODEL_OUTPUT_TRUNCATED") {
    return {
      missing: "Model answer got cut off",
      gapCode: "MODEL_OUTPUT_TRUNCATED",
      message: "The model's answer got cut off. Retry the ask.",
      nearest: ""
    };
  }
  const missing = String(payload.missing_capability ?? payload.modality ?? "unnamed capability");
  const gapCode = String(payload.gap_code ?? payload.outcome ?? "CAPABILITY_GAP");
  const message = String(payload.message ?? "I understand the question, but I cannot measure it yet.");
  const nearest = payload.nearest_measurable_alternative;
  return {
    missing,
    gapCode,
    message,
    nearest:
      typeof nearest === "string"
        ? nearest
        : nearest && typeof nearest === "object"
          ? String(asRecord(nearest).label ?? asRecord(nearest).question ?? "")
          : ""
  };
}

export type FilmRoomErrorView = {
  title: string;
  code: string;
  message: string;
  detail: string;
  tone: "schema" | "truncation" | "internal" | "gate" | "disabled" | "generic";
};

export function filmRoomErrorViewModel(error: unknown): FilmRoomErrorView {
  const apiError = error instanceof WorkbenchApiError ? error : null;
  const payload = apiError ? { error_code: apiError.errorCode, details: apiError.details, message: apiError.message } : asRecord(error);
  const code = String(payload.error_code ?? payload.gap_code ?? "REQUEST_FAILED");
  const details = asRecord(payload.details);
  if (code === "REQUEST_SCHEMA_INVALID") {
    return {
      title: "Couldn't understand the request",
      code,
      message: "The request body did not match the Film Room API contract.",
      detail: String(details.expected ?? details.reason ?? "Expected a JSON object with the required fields."),
      tone: "schema"
    };
  }
  if (code === "MODEL_OUTPUT_TRUNCATED") {
    return {
      title: "The model's answer got cut off",
      code,
      message: "Retry the ask; the model stopped before it produced complete JSON.",
      detail: String(details.reason ?? "No request changes are needed."),
      tone: "truncation"
    };
  }
  if (code === "INTERNAL_ERROR") {
    const correlationId = String(details.correlation_id ?? "not recorded");
    return {
      title: "Something broke on our side",
      code,
      message: "The server logged a traceback for this failure.",
      detail: `correlation ${correlationId}`,
      tone: "internal"
    };
  }
  if (code === "DEMO_TOKEN_REQUIRED") {
    return {
      title: "Demo token required",
      code,
      message: "Live asks are gated in public mode.",
      detail: String(details.token_source ?? ""),
      tone: "gate"
    };
  }
  if (code === "ASKS_DISABLED") {
    return {
      title: "Live asks disabled",
      code,
      message: "The gallery is available, but model-backed asks are not connected in this runtime.",
      detail: String(details.reason ?? details.message ?? ""),
      tone: "disabled"
    };
  }
  const message = error instanceof Error ? error.message : String(payload.message ?? error ?? "Request failed.");
  return {
    title: "Request failed",
    code,
    message,
    detail: "",
    tone: "generic"
  };
}

export function filmRoomBootstrapWarmingMessage(payload: FilmRoomBootstrapResponse | null): string | null {
  if (!payload || payload.state !== "warming") return null;
  const warming = asRecord(payload.warming);
  const items = asArray(warming.items).map(asRecord);
  const running = items.filter((item) => String(item.status ?? "") === "running");
  const queued = items.filter((item) => String(item.status ?? "") === "queued");
  const labels = (running.length ? running : queued.length ? queued : items)
    .map((item) => String(item.key ?? "film-room-plan").replaceAll("_", " "))
    .slice(0, 3);
  const subject = labels.length ? labels.join(", ") : "committed Film Room plans";
  return `Warming ${subject}.`;
}

function demoTokenFromBrowser() {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("demo_token") || params.get("access_token") || window.localStorage.getItem("demo_token");
}

export function headerChipsFromResponse(response: FilmRoomAskResponse | null): string[] {
  const document = asRecord(response?.answer?.document);
  const bundleDocuments = asRecord(document.documents);
  const docs = Object.keys(bundleDocuments).length ? Object.values(bundleDocuments).map(asRecord) : [document];
  const matchIds = new Set<string>();
  const roles = new Set<string>();
  for (const doc of docs) {
    const invocation = asRecord(doc.default_invocation);
    for (const matchId of asArray(invocation.match_ids)) matchIds.add(String(matchId));
    if (invocation.perspective_team_role) roles.add(String(invocation.perspective_team_role));
  }
  const chips = [
    matchIds.size ? `${matchIds.size} matches` : "scope pending",
    roles.size ? `${Array.from(roles).join("+")} perspective` : "role pending",
    response ? `${response.provider} · ${response.model}` : "openai-codex · gpt-5.5"
  ];
  const tree = response?.answer?.provenance.tree;
  if (tree) chips.push(`tree ${tree.slice(0, 7)}`);
  return chips;
}

function IntervalCard({ metric }: { metric: FilmRoomIntervalMetric | null | undefined }) {
  const renderable = assertIntervalMetric(metric);
  const lower = Math.max(0, Math.min(100, renderable.lower * 100));
  const upper = Math.max(lower, Math.min(100, renderable.upper * 100));
  const observed = Math.max(0, Math.min(100, renderable.observed * 100));
  const source = renderable.source;
  const completed = finiteNumber(source.a_count) ?? 0;
  const brokeDown = (finiteNumber(source.b_count) ?? 0) + (finiteNumber(source.e_count) ?? 0);
  const unknown = renderable.unknown_count;
  const partitionTotal = Math.max(1, completed + brokeDown + unknown);
  return (
    <section className="filmPanel metricPanel">
      <div className="filmPanelHeader">
        <span>{intervalHeadline(renderable)}</span>
        <span>UNKNOWN {renderable.unknown_count}</span>
      </div>
      <div className="metricValue">{formatPercent(renderable.observed)}</div>
      <div className="metricLabel">{renderable.label}</div>
      <div className="metricBoundsLine">bounds {formatPercent(renderable.lower)} - {formatPercent(renderable.upper)}</div>
      <div className="intervalBar" aria-label="Bounded interval">
        <span className="intervalRange" style={{ left: `${lower}%`, width: `${upper - lower}%` }} />
        <span className="intervalObserved" style={{ left: `${observed}%` }} />
      </div>
      <div className="metricBounds">
        <span>{formatPercent(renderable.lower)}</span>
        <span>observed {formatPercent(renderable.observed)}</span>
        <span>{formatPercent(renderable.upper)}</span>
      </div>
      <div className="partitionStrip" aria-label="Observed, failed, and unknown partition">
        <i className="partitionPass" style={{ width: `${(completed / partitionTotal) * 100}%` }} />
        <i className="partitionFail" style={{ width: `${(brokeDown / partitionTotal) * 100}%` }} />
        <i className="partitionUnknown" style={{ width: `${(unknown / partitionTotal) * 100}%` }} />
      </div>
      <div className="partitionLegend">
        <span><i className="legendKey passKey" />{formatCount(completed)} completed</span>
        <span><i className="legendKey failKey" />{formatCount(brokeDown)} broke down</span>
        <span><i className="legendKey unknownKey" />{formatCount(unknown)} unknown</span>
      </div>
    </section>
  );
}

function nearestFrame(replay: ReplayPayload, frameId: number | null) {
  if (!replay.frames.length) return null;
  if (frameId == null) return replay.frames[0];
  return replay.frames.reduce((best, frame) => {
    return Math.abs(frame.frame_id - frameId) < Math.abs(best.frame_id - frameId) ? frame : best;
  }, replay.frames[0]);
}

function entityPoint(
  replay: ReplayPayload,
  frameId: number | null,
  entityId: string | null,
  toX: (x: number) => number,
  toY: (y: number) => number
) {
  const frame = nearestFrame(replay, frameId);
  if (!frame) return null;
  const entity =
    (entityId ? frame.entities.find((item) => item.entity_id === entityId) : null) ??
    frame.entities.find((item) => item.entity_type === "ball") ??
    frame.entities[0];
  if (!entity) return null;
  return { x: toX(entity.x_m), y: toY(entity.y_m), entity };
}

function trailPoints(
  replay: ReplayPayload,
  trail: JsonObject,
  toX: (x: number) => number,
  toY: (y: number) => number
) {
  const start = finiteNumber(trail.start_frame_id);
  const end = finiteNumber(trail.end_frame_id);
  if (start == null || end == null) return "";
  const entityId = typeof trail.player_id === "string" ? trail.player_id : null;
  const points = replay.frames
    .filter((frame) => frame.frame_id >= start && frame.frame_id <= end)
    .filter((_, index) => index % 3 === 0)
    .map((frame) => {
      const entity: ReplayEntity | undefined =
        (entityId ? frame.entities.find((item) => item.entity_id === entityId) : undefined) ??
        frame.entities.find((item) => item.entity_type === "ball");
      return entity ? `${toX(entity.x_m)},${toY(entity.y_m)}` : "";
    })
    .filter(Boolean);
  return points.join(" ");
}

function PitchReplay({
  replay,
  moment,
  frameIndex,
  setFrameIndex
}: {
  replay: ReplayPayload | null | undefined;
  moment: FilmRoomMoment | null | undefined;
  frameIndex: number;
  setFrameIndex: (value: number) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const frame = replay?.frames[frameIndex];
  useEffect(() => {
    if (!playing || !replay?.frames.length) return;
    const id = window.setInterval(() => {
      setFrameIndex((frameIndex + 1) % replay.frames.length);
    }, 120);
    return () => window.clearInterval(id);
  }, [frameIndex, playing, replay, setFrameIndex]);

  if (!replay || !frame) {
    return (
      <section className="stagebox emptyStage">
        <div className="emptyStageLabel">NO REPLAY WINDOW</div>
      </section>
    );
  }

  const width = 680;
  const height = 440;
  const pitchLength = replay.pitch.length_m || 105;
  const pitchWidth = replay.pitch.width_m || 68;
  const toX = (x: number) => ((x + pitchLength / 2) / pitchLength) * width;
  const toY = (y: number) => ((pitchWidth / 2 - y) / pitchWidth) * height;
  const players = frame.entities.filter((entity) => entity.entity_type !== "ball");
  const ball = frame.entities.find((entity) => entity.entity_type === "ball");
  const overlay = asRecord(moment?.evidence_overlay);
  const stageLabels = asArray(overlay.stage_labels).map(asRecord);
  const anchorMarkers = asArray(overlay.anchor_markers).map(asRecord);
  const carryTrails = asArray(overlay.carry_trails).map(asRecord);
  const unknown = asRecord(overlay.unknown);

  return (
    <section className="stagebox">
      <div className="stagehead">
        <span className="eyebrow">Replay</span>
        <span className="momentname">
          {moment ? `${moment.match_id} · ${moment.period} · frame ${moment.anchor_frame_id}` : replay.replay_window_id}
        </span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Canonical tracking replay with evidence overlay">
        <rect x="0" y="0" width={width} height={height} rx="4" className="pitchBase" />
        <rect x="34" y="28" width="612" height="384" className="pitchLine" />
        <line x1={width / 2} x2={width / 2} y1="28" y2="412" className="pitchLine" />
        <circle cx={width / 2} cy={height / 2} r="48" className="pitchLine" />
        <rect x="34" y="124" width="94" height="192" className="pitchLine" />
        <rect x="552" y="124" width="94" height="192" className="pitchLine" />
        {carryTrails.map((trail, index) => (
          <polyline key={`trail-${index}`} points={trailPoints(replay, trail, toX, toY)} className="carryTrail" />
        ))}
        {anchorMarkers.map((marker, index) => {
          const point = entityPoint(
            replay,
            finiteNumber(marker.frame_id),
            typeof marker.player_id === "string" ? marker.player_id : null,
            toX,
            toY
          );
          return point ? <circle key={`anchor-${index}`} cx={point.x} cy={point.y} r="13" className="anchorMarker" /> : null;
        })}
        {players.map((entity) => (
          <circle
            key={`${entity.team_role}-${entity.entity_id}`}
            cx={toX(entity.x_m)}
            cy={toY(entity.y_m)}
            r="7"
            className={entity.team_role === "home" ? "playerHome" : "playerAway"}
          />
        ))}
        {ball ? <circle cx={toX(ball.x_m)} cy={toY(ball.y_m)} r="4.5" className="ballDot" /> : null}
        {stageLabels.map((label, index) => {
          const point = entityPoint(
            replay,
            finiteNumber(label.frame_id),
            typeof label.player_id === "string" ? label.player_id : null,
            toX,
            toY
          );
          return point ? (
            <text key={`label-${index}`} x={point.x + 10} y={point.y - 12} className="stageLabel">
              {String(label.label)}
            </text>
          ) : null;
        })}
        {unknown.is_unknown === true ? (
          <g>
            <rect x="20" y="20" width="250" height="30" className="unknownOverlay" />
            <text x="32" y="40" className="unknownLabel">{String(unknown.reason ?? "UNKNOWN")}</text>
          </g>
        ) : null}
      </svg>
      <div className="filmControls">
        <button type="button" onClick={() => setPlaying(!playing)} aria-label="Play or pause replay">
          {playing ? "PAUSE" : "PLAY"}
        </button>
        <input
          type="range"
          min="0"
          max={Math.max(0, replay.frames.length - 1)}
          value={frameIndex}
          onChange={(event) => setFrameIndex(Number(event.currentTarget.value))}
          aria-label="Replay frame"
        />
        <span>{matchClock(frame, replay)}</span>
        <span>
          {frame.frame_id} · {frameIndex + 1}/{replay.frames.length}
        </span>
      </div>
    </section>
  );
}

function MomentList({
  moments,
  total,
  selected,
  setSelected
}: {
  moments: FilmRoomMoment[];
  total: number;
  selected: number;
  setSelected: (value: number) => void;
}) {
  return (
    <section className="filmPanel">
      <div className="filmPanelHeader">
        <span>{momentCollectionLabel(moments, total)}</span>
        <span>{moments.length} shown</span>
      </div>
      <div className="momentList">
        {moments.map((moment, index) => (
          <button
            type="button"
            key={`${moment.result_id}-${moment.replay_window_id ?? index}`}
            className={index === selected ? "momentItem selected" : "momentItem"}
            onClick={() => setSelected(index)}
          >
            <span>{moment.match_id}</span>
            <span>{moment.period}</span>
            <strong>{moment.anchor_frame_id}</strong>
            <small>{chainStatusLabel(moment)}</small>
            {moment.unknown_reason ? <em>{moment.unknown_reason}</em> : null}
          </button>
        ))}
      </div>
    </section>
  );
}

function ProvenanceStrip({ response, replay }: { response: FilmRoomAskResponse | null; replay: ReplayPayload | null }) {
  const provenance = response?.answer?.provenance;
  const latency = response?.latency_breakdown_ms;
  return (
    <section className="provenanceStrip">
      <span>PLAN {provenance?.plan_hash?.slice(0, 12) ?? "pending"}</span>
      <span>DOC {provenance?.synthesized_document_hash?.slice(0, 12) ?? "pending"}</span>
      <span>TREE {provenance?.tree?.slice(0, 12) ?? "pending"}</span>
      <span>REPLAY {replay?.replay_window_id ?? provenance?.replay_window_id ?? "none"}</span>
      <span>H {latency?.hermes ?? 0}ms · S {latency?.synthesis ?? 0}ms · E {latency?.execution ?? 0}ms</span>
    </section>
  );
}

function AskThread({
  response,
  error,
  loading,
  warming,
  onClarify
}: {
  response: FilmRoomAskResponse | null;
  error: FilmRoomErrorView | null;
  loading: boolean;
  warming: string | null;
  onClarify: (state: JsonObject, answer: string) => void;
}) {
  const clarification = asRecord(response?.clarification);
  const state = asRecord(clarification.state);
  const outcomeClass = filmRoomOutcomeClass(response);
  const refusal = refusalViewModel(response?.refusal);
  return (
    <section className="askThread">
      <div className="bubble userBubble">{response?.request_text ?? FLAGSHIP_ASK}</div>
      {loading ? <div className="bubble hermesBubble">{warming ?? "Loading prewarmed film..."}</div> : null}
      {outcomeClass === "answer" && response?.answer ? (
        <div className="bubble hermesBubble">
          <div>
            {momentCollectionLabel(response.answer.moments, response.answer.moment_total_count)} · plan{" "}
            {response.answer.provenance.plan_hash.slice(0, 12)}
          </div>
          <div className="compiled">
            {response.answer.compiled_chips.map((chip) => (
              <span className="stage" key={chip}>{chip}</span>
            ))}
          </div>
        </div>
      ) : null}
      {outcomeClass === "clarification" ? (
        <div className="bubble hermesBubble">
          <div>{String(clarification.question ?? "Clarify the reading.")}</div>
          <div className="readingRow">
            {asArray(clarification.readings).map((item) => {
              const reading = asRecord(item);
              const label = String(reading.label ?? reading.reading_id ?? "Reading");
              return (
                <button key={label} type="button" onClick={() => onClarify(state, label)}>
                  {label}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
      {outcomeClass === "refusal" ? (
        <div className="bubble refusalBubble">
          <strong>{refusal.missing}</strong>
          <span>{refusal.gapCode}</span>
          <p>{refusal.message}</p>
          {refusal.nearest ? <button type="button">{refusal.nearest}</button> : null}
        </div>
      ) : null}
      {error ? (
        <div className={`bubble refusalBubble filmErrorBubble ${error.tone}Error`}>
          <strong>{error.title}</strong>
          <span>{error.code}</span>
          <p>{error.message}</p>
          {error.detail ? <p>{error.detail}</p> : null}
        </div>
      ) : null}
    </section>
  );
}

function EvidencePanel({ moment, response }: { moment: FilmRoomMoment | null | undefined; response: FilmRoomAskResponse | null }) {
  const [showRaw, setShowRaw] = useState(false);
  const overlay = asRecord(moment?.evidence_overlay);
  const isPartitionPreview = moment?.source_kind === "certified_table_partition";
  return (
    <section className="filmPanel notesPanel">
      <div className="filmPanelHeader">
        <span>Evidence</span>
        <button type="button" onClick={() => setShowRaw(!showRaw)}>{showRaw ? "SUMMARY" : "JSON"}</button>
      </div>
      {showRaw ? (
        <pre>{JSON.stringify(moment?.evidence_row ?? response?.answer?.raw_evidence ?? {}, null, 2)}</pre>
      ) : (
        <dl className="evidenceSummary">
          <div><dt>{isPartitionPreview ? "record" : "chain"}</dt><dd>{chainStatusLabel(moment)}</dd></div>
          <div><dt>reason</dt><dd>{moment?.chain_reason ?? moment?.unknown_reason ?? "observed"}</dd></div>
          <div>
            <dt>replay</dt>
            <dd>{isPartitionPreview ? "period-open preview; not a certified chain witness" : "witness window"}</dd>
          </div>
          <div><dt>window</dt><dd>{moment?.replay_start_frame_id ?? "-"} - {moment?.replay_end_frame_id ?? "-"}</dd></div>
          <div><dt>overlays</dt><dd>{asArray(overlay.stage_labels).length} stages · {asArray(overlay.carry_trails).length} trails</dd></div>
        </dl>
      )}
    </section>
  );
}

export function FilmRoom() {
  const [query, setQuery] = useState(FLAGSHIP_ASK);
  const [response, setResponse] = useState<FilmRoomAskResponse | null>(null);
  const [replay, setReplay] = useState<ReplayPayload | null>(null);
  const [error, setError] = useState<FilmRoomErrorView | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingBootstrap, setLoadingBootstrap] = useState(true);
  const [bootstrapWarming, setBootstrapWarming] = useState<string | null>(null);
  const [selectedMoment, setSelectedMoment] = useState(0);
  const [frameIndex, setFrameIndex] = useState(0);
  const moments = response?.answer?.moments ?? [];
  const selected = moments[selectedMoment] ?? null;
  const selectedFrame = useMemo(() => {
    if (!replay?.frames.length) return null;
    return replay.frames[Math.min(frameIndex, replay.frames.length - 1)];
  }, [frameIndex, replay]);

  async function submit(context?: JsonObject) {
    setBusy(true);
    setError(null);
    try {
      const demo_token = demoTokenFromBrowser();
      const next = await filmRoomAsk({ text: query, context, demo_token });
      setResponse(next);
      setReplay(next.answer?.replay ?? null);
      setSelectedMoment(0);
      setFrameIndex(0);
      const replayWindowId = next.answer?.replay?.replay_window_id;
      const firstFrame = next.answer?.replay?.frames[0];
      if (replayWindowId && firstFrame) {
        await filmRoomReplayFrame({ replay_window_id: replayWindowId, frame_id: firstFrame.frame_id });
      }
    } catch (event) {
      setError(filmRoomErrorViewModel(event));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    const load = () => {
      filmRoomBootstrap()
      .then((payload) => {
        if (!alive) return;
        const warming = filmRoomBootstrapWarmingMessage(payload);
        setBootstrapWarming(warming);
        if (payload.state === "warming") {
          timer = window.setTimeout(load, 2000);
          return;
        }
        const prewarmed = payload.prewarmed_response ?? null;
        setResponse(prewarmed);
        setReplay(prewarmed?.answer?.replay ?? null);
        setLoadingBootstrap(false);
      })
      .catch((event) => {
        if (alive) setError(filmRoomErrorViewModel(event));
        if (alive) setLoadingBootstrap(false);
      })
      .finally(() => {
        if (alive && !timer) setLoadingBootstrap(false);
      });
    };
    load();
    return () => {
      alive = false;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    const replayWindowId = selected?.replay_window_id;
    if (!replayWindowId || replay?.replay_window_id === replayWindowId) return;
    let alive = true;
    filmRoomReplayWindow({ replay_window_id: replayWindowId })
      .then((payload) => {
        if (!alive) return;
        setReplay(payload.replay);
        setFrameIndex(0);
      })
      .catch((event) => {
        if (alive) setError(filmRoomErrorViewModel(event));
      });
    return () => {
      alive = false;
    };
  }, [selected?.replay_window_id, replay?.replay_window_id]);

  return (
    <main className="filmRoom">
      <header className="filmHeader">
        <div className="filmWordmark">ENTRELÍNEAS · FILM ROOM</div>
        <div className="filmChips">
          {headerChipsFromResponse(response).map((chip, index) => (
            <span key={`${chip}-${index}`}>{chip}</span>
          ))}
        </div>
      </header>

      <AskThread
        response={response}
        error={error}
        loading={loadingBootstrap}
        warming={bootstrapWarming}
        onClarify={(pending, answer) => void submit({ pending_clarification: pending, answer })}
      />

      <form
        className="filmAskbar"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <input value={query} onChange={(event) => setQuery(event.currentTarget.value)} aria-label="Ask the film anything" />
        <button type="submit" disabled={busy}>
          {busy ? "RUNNING" : "ASK"}
        </button>
      </form>

      <section className="filmGrid">
        <div>
          <PitchReplay replay={replay} moment={selected} frameIndex={frameIndex} setFrameIndex={setFrameIndex} />
          <ProvenanceStrip response={response} replay={replay} />
        </div>
        <aside className="filmRail">
          {response?.answer?.interval_metric ? <IntervalCard metric={response.answer.interval_metric} /> : null}
          <MomentList
            moments={moments}
            total={response?.answer?.moment_total_count ?? moments.length}
            selected={selectedMoment}
            setSelected={setSelectedMoment}
          />
          <EvidencePanel moment={selected} response={response} />
          <section className="filmPanel notesPanel">
            <div className="filmPanelHeader">
              <span>Frame</span>
              <span>{selectedFrame?.frame_id ?? "none"}</span>
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}
