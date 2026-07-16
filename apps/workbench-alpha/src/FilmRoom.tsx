import { useEffect, useMemo, useRef, useState } from "react";
import { WorkbenchApiError, filmRoomAsk, filmRoomBootstrap, filmRoomReplayFrame, filmRoomReplayWindow } from "./api";
import {
  deriveQuestionClauseKeys,
  intervalAnswerText,
  intervalPresentation,
  momentCardText,
  unknownMomentText,
  type QuestionClauseKey
} from "./filmRoomLegibility";
import type { FilmRoomAskResponse, FilmRoomBootstrapResponse, FilmRoomIntervalMetric, FilmRoomMoment, JsonObject, ReplayEntity, ReplayFrame, ReplayPayload } from "./types";

const FLAGSHIP_ASK = "After a regain, how often does the team progress the ball by carry and keep it with a controlled pass?";
const PRESSING_MAP_ASK = "Where does each team win the ball back?";
const PRESSING_MAP_KEY = "pressing_map";
const RETENTION_CHAIN_KEY = "counterattack_sequence_rate";

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
  return typeof value === "number" && Number.isFinite(value) ? Math.round(value).toLocaleString("en-US") : "0";
}

function periodLabel(period: string) {
  if (period === "firstHalf") return "First half";
  if (period === "secondHalf") return "Second half";
  return period.replaceAll("_", " ");
}

export function replayMatchClock(
  frame: ReplayFrame | undefined,
  replay: ReplayPayload | null | undefined,
  moment: FilmRoomMoment | null | undefined
) {
  if (!frame || !replay || typeof moment?.match_time_ms !== "number") return "match time not recorded";
  const seconds = Math.max(0, moment.match_time_ms / 1000 + (frame.frame_id - replay.anchor_frame_id) / replay.frame_rate_hz);
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const centis = Math.floor((seconds % 1) * 100);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(centis).padStart(2, "0")}`;
}

export function replaySamplingLabel(replay: ReplayPayload | null | undefined) {
  if (!replay?.frames.length) return "sampling not recorded";
  const steps = replay.frames
    .slice(1)
    .map((frame, index) => frame.frame_id - replay.frames[index].frame_id)
    .filter((step) => step > 0)
    .sort((a, b) => a - b);
  const stride = steps.length ? steps[Math.floor(steps.length / 2)] : 1;
  const sourceFrames = Math.max(1, replay.end_frame_id - replay.start_frame_id + 1);
  const duration = (sourceFrames - 1) / replay.frame_rate_hz;
  const strideText = stride === 1 ? "every frame" : `every ${stride}th frame`;
  return `${strideText} · ${duration.toFixed(1)} s window`;
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
  const roleLabel = roles.size === 2 && roles.has("home") && roles.has("away")
    ? "both teams"
    : roles.size === 1
      ? `${Array.from(roles)[0]} team`
      : "team scope pending";
  const chips = [
    matchIds.size ? `${matchIds.size} matches` : "scope pending",
    roleLabel,
    intervalCertificationChip(response)
  ];
  return chips;
}

export function intervalCertificationChip(response: FilmRoomAskResponse | null): string {
  if (!response) return "metric interval: loading";
  const source = asRecord(response.answer?.interval_metric?.source);
  const evidenceKind = typeof source.evidence_kind === "string" ? source.evidence_kind : "not recorded";
  return `metric interval: ${evidenceKind}`;
}

export function answeredQuestionScope(response: FilmRoomAskResponse | null): string {
  const [matchLabel, teamLabel] = headerChipsFromResponse(response);
  return `${teamLabel} across ${matchLabel}`;
}

export function orderedFilmRoomMoments(moments: FilmRoomMoment[]) {
  return moments
    .map((moment, index) => ({ moment, index }))
    .sort((a, b) => {
      const aRank = a.moment.chain_status === "PASS" ? 0 : 1;
      const bRank = b.moment.chain_status === "PASS" ? 0 : 1;
      return aRank - bRank || a.index - b.index;
    })
    .map(({ moment }) => moment);
}

export function momentCoverageText(answer: FilmRoomAskResponse["answer"] | null | undefined): string {
  const metricSource = asRecord(answer?.interval_metric?.source);
  const population = finiteNumber(metricSource.population_count) ?? 0;
  const raw = asRecord(answer?.raw_evidence);
  const descriptorIndex = asRecord(raw.descriptor_index);
  const coverage = asRecord(descriptorIndex.coverage);
  const shown = finiteNumber(coverage.shown_count) ?? answer?.visible_moment_count ?? answer?.moments.length ?? 0;
  const recordedPopulation = finiteNumber(coverage.population_count) ?? population;
  const base = `Showing ${Number(shown).toLocaleString("en-US")} of ${Number(recordedPopulation).toLocaleString("en-US")}`;
  if (shown >= recordedPopulation) return base;
  if (
    coverage.reason_code === "returned_classified_result_source_records" &&
    coverage.replay_partition_count === 1 &&
    coverage.completed_partition_count === 1
  ) {
    return `${base} — replay details exist only for the match-half containing the completed chain.`;
  }
  return `${base} — replay coverage reason not recorded.`;
}

export type PressingMapRow = {
  auditRole: string;
  matchId: string;
  teamName: string;
  defensive: number;
  middle: number;
  attacking: number;
  unknown: number;
  total: number;
};

export type PressingMapView = {
  population: number;
  located: number;
  unknown: number;
  thirds: { defensive: number; middle: number; attacking: number };
  rows: PressingMapRow[];
};

export function pressingMapViewModel(response: FilmRoomAskResponse | null): PressingMapView | null {
  if (response?.request_text !== PRESSING_MAP_ASK) return null;
  const raw = asRecord(response.answer?.raw_evidence);
  const table = asRecord(raw.certified_table);
  const totals = asRecord(table.totals);
  const thirds = asRecord(totals.third_counts);
  const rows = asArray(table.rows).map(asRecord).map((row) => {
    const counts = asRecord(row.third_counts);
    return {
      auditRole: String(row.audit_role ?? ""),
      matchId: String(row.match_id ?? ""),
      teamName: String(row.team_name ?? "Team not recorded"),
      defensive: finiteNumber(counts.defensive_third) ?? 0,
      middle: finiteNumber(counts.middle_third) ?? 0,
      attacking: finiteNumber(counts.final_third) ?? 0,
      unknown: finiteNumber(row.location_unknown_count) ?? 0,
      total: finiteNumber(row.population_count) ?? 0
    };
  });
  const population = finiteNumber(totals.population_count) ?? 0;
  const unknown = finiteNumber(totals.location_unknown_count) ?? 0;
  if (!population || rows.length === 0) return null;
  return {
    population,
    located: population - unknown,
    unknown,
    thirds: {
      defensive: finiteNumber(thirds.defensive_third) ?? 0,
      middle: finiteNumber(thirds.middle_third) ?? 0,
      attacking: finiteNumber(thirds.final_third) ?? 0
    },
    rows
  };
}

export function flagshipTabResponse(
  responses: Record<string, FilmRoomAskResponse>,
  key: string
): FilmRoomAskResponse | null {
  return responses[key] ?? null;
}

export function provenanceTreeView(tree: string | null | undefined): { text: string; title: string } {
  const value = tree?.trim() ?? "";
  if (!value || value.toLowerCase() === "unknown") {
    return { text: "not recorded", title: "Tree hash not recorded in this build" };
  }
  return { text: value.slice(0, 12), title: value };
}

export function partitionVisibilityNote(value: number, total: number): string | null {
  if (!(value > 0) || !(total > 0)) return null;
  const share = value / total;
  if (share >= 0.01) return null;
  const percent = share * 100;
  const precision = percent < 0.1 ? 2 : 1;
  return `segment enlarged to be visible — true share ${percent.toFixed(precision)}%`;
}

function IntervalCard({ metric, scope }: { metric: FilmRoomIntervalMetric | null | undefined; scope: string }) {
  const renderable = assertIntervalMetric(metric);
  const lower = Math.max(0, Math.min(100, renderable.lower * 100));
  const upper = Math.max(lower, Math.min(100, renderable.upper * 100));
  const observed = Math.max(0, Math.min(100, renderable.observed * 100));
  const source = renderable.source;
  const completed = finiteNumber(source.a_count) ?? 0;
  const brokeDown = (finiteNumber(source.b_count) ?? 0) + (finiteNumber(source.e_count) ?? 0);
  const unknown = renderable.unknown_count;
  const partitionTotal = Math.max(1, completed + brokeDown + unknown);
  const presentation = intervalPresentation(renderable);
  const observedCount = completed + brokeDown;
  const observedAlign = observed >= 75 ? "right" : observed <= 25 ? "left" : "center";
  const enlargementNote = partitionVisibilityNote(completed, partitionTotal);
  const segmentStyle = (value: number) => ({
    width: `${(value / partitionTotal) * 100}%`,
    minWidth: value > 0 ? "3px" : "0"
  });
  return (
    <section className={`filmPanel metricPanel ${presentation.findingFirst ? "findingFirst" : "rateFirst"}`}>
      <div className="filmPanelHeader">
        <span>Answer</span>
        <span>{formatCount(completed)} complete · {formatCount(renderable.unknown_count)} not fully seen</span>
      </div>
      <div className="answeredScope">{scope}</div>
      <div className="metricFinding">{presentation.headline}</div>
      <div className="metricObserved">
        <span>observed </span>
        <b>{formatCount(completed)}</b>
        <span>/{formatCount(observedCount)} ({formatPercent(renderable.observed)})</span>
      </div>
      <div className="metricSubtitle">{presentation.subtitle}</div>
      <div className="metricAnswer">{intervalAnswerText(renderable)}</div>
      <div className="intervalBar" aria-label="Bounded interval">
        <span className="intervalRange" style={{ left: `${lower}%`, width: `${upper - lower}%` }} />
        <span className="intervalObserved" style={{ left: `${observed}%` }} />
        <span className={`intervalObservedCallout ${observedAlign}`} style={{ left: `${observed}%` }}>
          <i aria-hidden="true" />
          <span>observed {formatPercent(renderable.observed)}</span>
        </span>
      </div>
      <div className="metricBounds">
        <span>{formatPercent(renderable.lower)}</span>
        <span>{formatPercent(renderable.upper)}</span>
      </div>
      <div className="partitionStrip" aria-label="Observed, failed, and unknown partition">
        <i className="partitionPass" style={segmentStyle(completed)} />
        <i className="partitionFail" style={segmentStyle(brokeDown)} />
        <i className="partitionUnknown" style={segmentStyle(unknown)} />
      </div>
      <div className="partitionDirectLabels">
        {completed > 0 ? <span className="partitionPassLabel">{formatCount(completed)} complete</span> : null}
        {brokeDown > 0 ? <span className="partitionFailLabel">{formatCount(brokeDown)} broke down</span> : null}
        {unknown > 0 ? <span className="partitionUnknownLabel">{formatCount(unknown)} unknown</span> : null}
      </div>
      {enlargementNote ? <div className="partitionScaleNote">{enlargementNote}</div> : null}
    </section>
  );
}

function PressingMapCard({ response }: { response: FilmRoomAskResponse | null }) {
  const view = pressingMapViewModel(response);
  const metric = response?.answer?.interval_metric;
  if (!view || !metric) return null;
  const presentation = intervalPresentation(assertIntervalMetric(metric));
  const locatedPercent = view.population ? view.located / view.population : 0;
  const thirdRows = [
    ["Defensive third", view.thirds.defensive],
    ["Middle third", view.thirds.middle],
    ["Attacking third", view.thirds.attacking]
  ] as const;
  return (
    <section className={`filmPanel metricPanel pressingMapPanel ${presentation.findingFirst ? "findingFirst" : "rateFirst"}`}>
      <div className="filmPanelHeader">
        <span>Answer</span>
        <span>{formatCount(view.population)} regains · {formatCount(view.unknown)} location unknown</span>
      </div>
      <div className="answeredScope">both teams across 7 matches</div>
      <div className="metricFinding">{formatCount(view.population)} regains mapped</div>
      <div className="metricObserved">
        <b>{formatPercent(locatedPercent)}</b><span> located to a registered pitch third</span>
      </div>
      <div className="metricSubtitle">
        {formatCount(view.located)} have a third. {formatCount(view.unknown)} stay location unknown at a boundary or without ball position.
      </div>
      <div className="pressingThirds" aria-label="Regains by orientation-aware pitch third">
        {thirdRows.map(([label, value]) => (
          <div className="pressingThird" key={label}>
            <span>{label}</span>
            <i><b style={{ width: `${(value / view.population) * 100}%` }} /></i>
            <strong>{formatCount(value)}</strong>
          </div>
        ))}
      </div>
      <div className="pressingTeamHeader">
        <span>{view.rows.length} team-match rows</span>
        <span>D · M · A · unknown · total</span>
      </div>
      <div className="pressingTeamRows">
        {view.rows.map((row) => (
          <div className="pressingTeamRow" key={`${row.matchId}-${row.auditRole}`}>
            <span><strong>{row.teamName}</strong><small>{row.matchId}</small></span>
            <b>{formatCount(row.defensive)} · {formatCount(row.middle)} · {formatCount(row.attacking)} · {formatCount(row.unknown)} · {formatCount(row.total)}</b>
          </div>
        ))}
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
  currentFrameId: number,
  toX: (x: number) => number,
  toY: (y: number) => number
) {
  const start = finiteNumber(trail.start_frame_id);
  const end = finiteNumber(trail.end_frame_id);
  if (start == null || end == null) return "";
  const entityId = typeof trail.player_id === "string" ? trail.player_id : null;
  const points = replay.frames
    .filter((frame) => frame.frame_id >= start && frame.frame_id <= end && frame.frame_id <= currentFrameId)
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

export function visibleWitnessLabels(labels: JsonObject[], currentFrameId: number): JsonObject[] {
  return labels.filter((label) => {
    const witnessFrameId = finiteNumber(label.frame_id);
    return witnessFrameId != null && witnessFrameId <= currentFrameId;
  });
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
  const pitchInsetX = 34;
  const pitchInsetY = 28;
  const toX = (x: number) => pitchInsetX + ((x + pitchLength / 2) / pitchLength) * (width - pitchInsetX * 2);
  const toY = (y: number) => pitchInsetY + ((pitchWidth / 2 - y) / pitchWidth) * (height - pitchInsetY * 2);
  const players = frame.entities.filter((entity) => entity.entity_type !== "ball");
  const ball = frame.entities.find((entity) => entity.entity_type === "ball");
  const hydratedOverlay = asRecord(replay.overlays);
  const overlay = Object.keys(hydratedOverlay).length ? hydratedOverlay : asRecord(moment?.evidence_overlay);
  const stageLabels = visibleWitnessLabels(asArray(overlay.stage_labels).map(asRecord), frame.frame_id);
  const anchorMarkers = visibleWitnessLabels(asArray(overlay.anchor_markers).map(asRecord), frame.frame_id);
  const carryTrails = asArray(overlay.carry_trails).map(asRecord);
  const unknown = asRecord(overlay.unknown);
  const evidenceUnknown = moment?.chain_status === "UNKNOWN" || unknown.is_unknown === true;
  const occupiedLabelBoxes: Array<{ x: number; y: number; width: number; height: number }> = [];
  const stageLabelLayouts = stageLabels.map((label) => {
    const point = entityPoint(
      replay,
      finiteNumber(label.frame_id),
      typeof label.player_id === "string" ? label.player_id : null,
      toX,
      toY
    );
    if (!point) return null;
    const stage = finiteNumber(label.stage);
    const clauseKey = stage && stage >= 1 && stage <= 3 ? ["①", "②", "③"][stage - 1] : "";
    const baseText = String(label.label);
    const text = evidenceUnknown ? `${baseText} — not verified` : baseText;
    const chipWidth = Math.min(width - 16, Math.max(78, text.length * 7 + 34));
    const chipX = Math.max(16, Math.min(width - chipWidth - 16, point.x - chipWidth / 2));
    const above = point.y - 42;
    const below = point.y + 20;
    const candidateYs = stage === 2
      ? [below, above, below + 28, above - 28]
      : [above, below, above - 28, below + 28];
    let chipY = Math.max(16, Math.min(height - 38, candidateYs[0]));
    for (const candidateY of candidateYs) {
      const nextY = Math.max(16, Math.min(height - 38, candidateY));
      const collides = occupiedLabelBoxes.some(
        (box) => chipX < box.x + box.width + 6 && chipX + chipWidth + 6 > box.x && nextY < box.y + box.height + 6 && nextY + 28 > box.y
      );
      if (!collides) {
        chipY = nextY;
        break;
      }
    }
    occupiedLabelBoxes.push({ x: chipX, y: chipY, width: chipWidth, height: 22 });
    const leaderX = Math.max(chipX + 8, Math.min(chipX + chipWidth - 8, point.x));
    const leaderY = chipY > point.y ? chipY : chipY + 22;
    return { clauseKey, text, chipWidth, chipX, chipY, point, leaderX, leaderY };
  });

  return (
    <section className="stagebox">
      <div className="stagehead">
        <span className="eyebrow">Replay</span>
        <span className="momentname">
          {moment ? `${moment.match_id} · ${periodLabel(moment.period)}` : "Selected moment"}
        </span>
        <span className="pitchTeamLegend" aria-label="Team color legend">
          <span><i className="homeTeamKey" />home team</span>
          <span><i className="awayTeamKey" />away team</span>
        </span>
      </div>
      {evidenceUnknown ? (
        <div className="unknownStrip">{moment ? unknownMomentText(moment) : "This part is not fully seen"}</div>
      ) : null}
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Canonical tracking replay with evidence overlay">
        <rect x="0" y="0" width={width} height={height} rx="4" className="pitchBase" />
        <rect x="34" y="28" width="612" height="384" className="pitchLine" />
        <line x1={width / 2} x2={width / 2} y1="28" y2="412" className="pitchLine" />
        <circle cx={width / 2} cy={height / 2} r="48" className="pitchLine" />
        <rect x="34" y="124" width="94" height="192" className="pitchLine" />
        <rect x="552" y="124" width="94" height="192" className="pitchLine" />
        {carryTrails.map((trail, index) => (
          <polyline
            key={`trail-${index}`}
            points={trailPoints(replay, trail, frame.frame_id, toX, toY)}
            className={`carryTrail ${evidenceUnknown ? "evidenceUnknown" : "evidenceComplete"}`}
          />
        ))}
        {anchorMarkers.map((marker, index) => {
          const point = entityPoint(
            replay,
            finiteNumber(marker.frame_id),
            typeof marker.player_id === "string" ? marker.player_id : null,
            toX,
            toY
          );
          return point ? (
            <circle
              key={`anchor-${index}`}
              cx={point.x}
              cy={point.y}
              r="13"
              className={`anchorMarker ${evidenceUnknown ? "evidenceUnknown" : "evidenceComplete"}`}
            />
          ) : null;
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
        {stageLabelLayouts.map((layout, index) => {
          if (!layout) return null;
          const { clauseKey, text, chipWidth, chipX, chipY, point, leaderX, leaderY } = layout;
          return (
            <g key={`label-${index}`}>
              <line
                x1={point.x}
                y1={point.y}
                x2={leaderX}
                y2={leaderY}
                className={`stageLeader ${evidenceUnknown ? "evidenceUnknown" : "evidenceComplete"}`}
              />
              <rect
                x={chipX}
                y={chipY}
                width={chipWidth}
                height="22"
                rx="3"
                className={`stageKeyChip ${evidenceUnknown ? "evidenceUnknown" : "evidenceComplete"}`}
              />
              <text
                x={chipX + 7}
                y={chipY + 15}
                className={`stageKeyText ${evidenceUnknown ? "evidenceUnknown" : "evidenceComplete"}`}
              >
                {clauseKey}
              </text>
              <text
                x={chipX + 26}
                y={chipY + 15}
                className={`stageLabel ${evidenceUnknown ? "evidenceUnknown" : "evidenceComplete"}`}
              >
                {text}
              </text>
            </g>
          );
        })}
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
          style={{ "--played": `${(frameIndex / Math.max(1, replay.frames.length - 1)) * 100}%` } as React.CSSProperties}
          onChange={(event) => setFrameIndex(Number(event.currentTarget.value))}
          aria-label="Replay frame"
        />
        <span className="replayClock">{replayMatchClock(frame, replay, moment)}</span>
        <span className="replayFrameCount">frame {frameIndex + 1} of {replay.frames.length} · {replay.frame_rate_hz} fps</span>
        <span className="replaySampling">{replaySamplingLabel(replay)}</span>
      </div>
    </section>
  );
}

function MomentList({
  moments,
  selected,
  setSelected,
  replay,
  coverage
}: {
  moments: FilmRoomMoment[];
  selected: number;
  setSelected: (value: number) => void;
  replay: ReplayPayload | null;
  coverage: string;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const [hiddenBelow, setHiddenBelow] = useState(0);
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const update = () => {
      const visibleBottom = list.getBoundingClientRect().bottom;
      const buttons = Array.from(list.querySelectorAll<HTMLElement>(".momentItem"));
      setHiddenBelow(buttons.filter((button) => button.getBoundingClientRect().bottom > visibleBottom + 1).length);
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(list);
    for (const button of list.querySelectorAll<HTMLElement>(".momentItem")) observer.observe(button);
    const timeout = window.setTimeout(update, 100);
    list.addEventListener("scroll", update, { passive: true });
    return () => {
      window.clearTimeout(timeout);
      observer.disconnect();
      list.removeEventListener("scroll", update);
    };
  }, [moments]);
  return (
    <section className="filmPanel">
      <div className="filmPanelHeader coverageHeader">
        <span>{coverage}</span>
      </div>
      <div className="momentList" ref={listRef}>
        {moments.map((moment, index) => (
          <button
            type="button"
            key={`${moment.result_id}-${moment.replay_window_id ?? index}`}
            className={`momentItem ${moment.chain_status === "PASS" ? "complete" : "unknown"}${index === selected ? " selected" : ""}`}
            onClick={() => setSelected(index)}
          >
            <strong className={`momentStatus ${moment.chain_status === "PASS" ? "complete" : "unknown"}`}>
              {moment.source_kind === "result"
                ? moment.chain_status === "PASS" ? "LOCATED" : "LOCATION UNKNOWN"
                : moment.chain_status === "PASS" ? "COMPLETE" : "UNKNOWN"}
            </strong>
            <span>{momentCardText(moment, index === selected ? replay : null)}</span>
          </button>
        ))}
      </div>
      {hiddenBelow > 0 ? <div className="momentListFade">{hiddenBelow} more below</div> : null}
    </section>
  );
}

function ProvenanceStrip({ response, replay }: { response: FilmRoomAskResponse | null; replay: ReplayPayload | null }) {
  const provenance = response?.answer?.provenance;
  const latency = response?.latency_breakdown_ms;
  const tree = provenanceTreeView(provenance?.tree);
  const timing = (value: number | undefined) => value && value > 0 ? `${value} ms` : "not measured";
  const artifactLabels = provenanceArtifactLabels(
    provenance?.plan_hash,
    provenance?.synthesized_document_hash
  );
  return (
    <section className="provenanceStrip">
      {artifactLabels.map((label) => <span key={label}>{label}</span>)}
      <span title={tree.title}>TREE {tree.text}</span>
      <span>REPLAY {replay?.replay_window_id ?? provenance?.replay_window_id ?? "none"}</span>
      <span>METRIC {response?.answer?.interval_metric?.label ?? "pending"}</span>
      <span title={`Hermes ${timing(latency?.hermes)} · Synthesis ${timing(latency?.synthesis)} · Execution ${timing(latency?.execution)}`}>
        {latency?.hermes || latency?.synthesis || latency?.execution
          ? `answered in ${(latency?.hermes ?? 0) + (latency?.synthesis ?? 0) + (latency?.execution ?? 0)} ms`
          : "timings not measured"}
      </span>
    </section>
  );
}

export function provenanceArtifactLabels(planHash: string | null | undefined, documentHash: string | null | undefined): string[] {
  const plan = planHash?.trim() || "pending";
  const document = documentHash?.trim() || "pending";
  if (plan !== "pending" && plan === document) return [`PLAN = DOC ${plan.slice(0, 12)}`];
  return [`PLAN ${plan.slice(0, 12)}`, `DOC ${document.slice(0, 12)}`];
}

function AskThread({
  response,
  error,
  loading,
  warming,
  clauseKeys,
  onClarify
}: {
  response: FilmRoomAskResponse | null;
  error: FilmRoomErrorView | null;
  loading: boolean;
  warming: string | null;
  clauseKeys: QuestionClauseKey[];
  onClarify: (state: JsonObject, answer: string) => void;
}) {
  const clarification = asRecord(response?.clarification);
  const state = asRecord(clarification.state);
  const outcomeClass = filmRoomOutcomeClass(response);
  const refusal = refusalViewModel(response?.refusal);
  return (
    <section className="askThread">
      <div className="bubble userBubble">
        <div>{response?.request_text ?? FLAGSHIP_ASK}</div>
        {clauseKeys.length ? (
          <div className="questionClauses" aria-label="The question's three operative clauses">
            {clauseKeys.map((clause) => (
              <span key={clause.stage}><b>{clause.key}</b>{clause.text}</span>
            ))}
          </div>
        ) : null}
      </div>
      {loading ? <div className="bubble hermesBubble">{warming ?? "Loading prewarmed film..."}</div> : null}
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

function EvidencePanel({
  moment,
  response,
  replay
}: {
  moment: FilmRoomMoment | null | undefined;
  response: FilmRoomAskResponse | null;
  replay: ReplayPayload | null;
}) {
  const [showRaw, setShowRaw] = useState(false);
  return (
    <section className="filmPanel notesPanel">
      <div className="filmPanelHeader">
        <span>Evidence</span>
        <button type="button" onClick={() => setShowRaw(!showRaw)}>{showRaw ? "SUMMARY" : "JSON"}</button>
      </div>
      {showRaw ? (
        <pre>{JSON.stringify(moment?.evidence_row ?? response?.answer?.raw_evidence ?? {}, null, 2)}</pre>
      ) : (
        <p className="evidenceSentence">
          {moment ? momentCardText(moment, replay) : "Choose a moment to see how it answers the question."}
        </p>
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
  const [flagshipResponses, setFlagshipResponses] = useState<Record<string, FilmRoomAskResponse>>({});
  const [activeFlagship, setActiveFlagship] = useState(PRESSING_MAP_KEY);
  const moments = useMemo(
    () => orderedFilmRoomMoments(response?.answer?.moments ?? []),
    [response?.answer?.moments]
  );
  const selected = moments[selectedMoment] ?? null;
  const clauseKeys = useMemo(
    () => deriveQuestionClauseKeys(response?.answer?.meaning_expression),
    [response?.answer?.meaning_expression]
  );
  async function submit(context?: JsonObject) {
    setBusy(true);
    setError(null);
    try {
      const demo_token = demoTokenFromBrowser();
      const next = await filmRoomAsk({ text: query, context, demo_token });
      setResponse(next);
      if (next.answer) setQuery("");
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
        const gallery = payload.flagship_responses ?? {};
        const initial = flagshipTabResponse(gallery, PRESSING_MAP_KEY) ?? prewarmed;
        setFlagshipResponses(gallery);
        setActiveFlagship(initial?.request_text === PRESSING_MAP_ASK ? PRESSING_MAP_KEY : RETENTION_CHAIN_KEY);
        setResponse(initial);
        if (initial?.answer) setQuery("");
        setReplay(initial?.answer?.replay ?? null);
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
        clauseKeys={clauseKeys}
        onClarify={(pending, answer) => void submit({ pending_clarification: pending, answer })}
      />

      <form
        className={`filmAskbar ${response?.answer ? "answered" : ""}`}
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <input
          value={query}
          placeholder={response?.answer ? "Ask another…" : undefined}
          onChange={(event) => setQuery(event.currentTarget.value)}
          aria-label="Ask the film anything"
        />
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
          <nav className="filmTabs filmChips" aria-label="Gallery questions">
            {[
              [PRESSING_MAP_KEY, "Where do they win it back?"],
              [RETENTION_CHAIN_KEY, "After a regain, do they keep it?"]
            ].map(([key, label]) => (
              <button
                type="button"
                key={key}
                aria-pressed={activeFlagship === key}
                className={activeFlagship === key ? "active" : ""}
                disabled={!flagshipTabResponse(flagshipResponses, key)}
                onClick={() => {
                  const next = flagshipTabResponse(flagshipResponses, key);
                  if (!next) return;
                  setActiveFlagship(key);
                  setResponse(next);
                  setReplay(next.answer?.replay ?? null);
                  setSelectedMoment(0);
                  setFrameIndex(0);
                  setError(null);
                }}
              >
                {label}
              </button>
            ))}
          </nav>
          {pressingMapViewModel(response) ? (
            <PressingMapCard response={response} />
          ) : response?.answer?.interval_metric ? (
            <IntervalCard metric={response.answer.interval_metric} scope={answeredQuestionScope(response)} />
          ) : null}
          <MomentList
            moments={moments}
            selected={selectedMoment}
            setSelected={setSelectedMoment}
            replay={replay}
            coverage={momentCoverageText(response?.answer)}
          />
          <EvidencePanel moment={selected} response={response} replay={replay} />
        </aside>
      </section>
    </main>
  );
}
