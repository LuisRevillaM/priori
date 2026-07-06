import { useEffect, useMemo, useState } from "react";
import { filmRoomAsk, filmRoomReplayFrame } from "./api";
import type { FilmRoomAskResponse, FilmRoomIntervalMetric, FilmRoomMoment, JsonObject, ReplayFrame, ReplayPayload } from "./types";

const FLAGSHIP_ASK = "After a regain, how often does the team progress the ball by carry and keep it with a controlled pass?";

function asRecord(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "UNKNOWN";
  return `${Math.round(value * 1000) / 10}%`;
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
    label: String(record.label ?? "Certified interval"),
    observed: record.observed as number,
    lower: record.lower as number,
    upper: record.upper as number,
    unknown_count: record.unknown_count as number,
    source: asRecord(record.source)
  };
}

function IntervalCard({ metric }: { metric: FilmRoomIntervalMetric | null | undefined }) {
  const renderable = assertIntervalMetric(metric);
  const lower = Math.max(0, Math.min(100, renderable.lower * 100));
  const upper = Math.max(lower, Math.min(100, renderable.upper * 100));
  const observed = Math.max(0, Math.min(100, renderable.observed * 100));
  return (
    <section className="filmPanel metricPanel">
      <div className="filmPanelHeader">
        <span>Certified interval</span>
        <span>UNKNOWN {renderable.unknown_count}</span>
      </div>
      <div className="metricValue">{formatPercent(renderable.observed)}</div>
      <div className="metricLabel">{renderable.label}</div>
      <div className="partitionStrip" aria-label="Bounded interval">
        <span className="partitionRange" style={{ left: `${lower}%`, width: `${upper - lower}%` }} />
        <span className="partitionObserved" style={{ left: `${observed}%` }} />
      </div>
      <div className="metricBounds">
        <span>{formatPercent(renderable.lower)}</span>
        <span>{formatPercent(renderable.upper)}</span>
      </div>
    </section>
  );
}

function PitchReplay({
  replay,
  frameIndex,
  setFrameIndex
}: {
  replay: ReplayPayload | null | undefined;
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

  return (
    <section className="stagebox">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Canonical tracking replay">
        <rect x="0" y="0" width={width} height={height} rx="4" className="pitchBase" />
        <rect x="34" y="28" width="612" height="384" className="pitchLine" />
        <line x1={width / 2} x2={width / 2} y1="28" y2="412" className="pitchLine" />
        <circle cx={width / 2} cy={height / 2} r="48" className="pitchLine" />
        <rect x="34" y="124" width="94" height="192" className="pitchLine" />
        <rect x="552" y="124" width="94" height="192" className="pitchLine" />
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
      </svg>
      <div className="filmControls">
        <button type="button" onClick={() => setPlaying(!playing)}>
          {playing ? "PAUSE" : "PLAY"}
        </button>
        <input
          type="range"
          min="0"
          max={Math.max(0, replay.frames.length - 1)}
          value={frameIndex}
          onChange={(event) => setFrameIndex(Number(event.currentTarget.value))}
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
  selected,
  setSelected
}: {
  moments: FilmRoomMoment[];
  selected: number;
  setSelected: (value: number) => void;
}) {
  return (
    <section className="filmPanel">
      <div className="filmPanelHeader">
        <span>Moments</span>
        <span>{moments.length}</span>
      </div>
      <div className="momentList">
        {moments.map((moment, index) => (
          <button
            type="button"
            key={moment.result_id}
            className={index === selected ? "momentItem selected" : "momentItem"}
            onClick={() => setSelected(index)}
          >
            <span>{moment.match_id}</span>
            <span>{moment.period}</span>
            <strong>{moment.anchor_frame_id}</strong>
            {moment.unknown_reason ? <em>{moment.unknown_reason}</em> : null}
          </button>
        ))}
      </div>
    </section>
  );
}

function ProvenanceStrip({ response }: { response: FilmRoomAskResponse | null }) {
  const provenance = response?.answer?.provenance;
  return (
    <section className="provenanceStrip">
      <span>PLAN {provenance?.plan_hash?.slice(0, 12) ?? "pending"}</span>
      <span>DOC {provenance?.synthesized_document_hash?.slice(0, 12) ?? "pending"}</span>
      <span>REPLAY {provenance?.replay_window_id ?? "none"}</span>
      <span>{response ? `${response.provider} · ${response.model} · ${response.latency_ms}ms` : "openai-codex · gpt-5.5"}</span>
    </section>
  );
}

function AskThread({
  response,
  error,
  onClarify
}: {
  response: FilmRoomAskResponse | null;
  error: string | null;
  onClarify: (state: JsonObject, answer: string) => void;
}) {
  const clarification = asRecord(response?.clarification);
  const state = asRecord(clarification.state);
  return (
    <section className="askThread">
      <div className="bubble userBubble">{response?.request_text ?? FLAGSHIP_ASK}</div>
      {response?.answer ? (
        <div className="bubble hermesBubble">
          {response.answer.moments.length} {response.answer.provenance.certified_table_path ? "certified" : "executed"} moment
          {response.answer.moments.length === 1 ? "" : "s"} · plan{" "}
          {response.answer.provenance.plan_hash.slice(0, 12)}
        </div>
      ) : null}
      {response?.outcome === "clarification_required" ? (
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
      {response?.refusal ? <pre className="bubble refusalBubble">{JSON.stringify(response.refusal, null, 2)}</pre> : null}
      {error ? <div className="bubble refusalBubble">{error}</div> : null}
    </section>
  );
}

export function FilmRoom() {
  const [query, setQuery] = useState(FLAGSHIP_ASK);
  const [response, setResponse] = useState<FilmRoomAskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedMoment, setSelectedMoment] = useState(0);
  const [frameIndex, setFrameIndex] = useState(0);
  const replay = response?.answer?.replay;
  const moments = response?.answer?.moments ?? [];

  const selectedFrame = useMemo(() => {
    if (!replay?.frames.length) return null;
    return replay.frames[Math.min(frameIndex, replay.frames.length - 1)];
  }, [frameIndex, replay]);

  async function submit(context?: JsonObject) {
    setBusy(true);
    setError(null);
    try {
      const next = await filmRoomAsk({ text: query, context });
      setResponse(next);
      setSelectedMoment(0);
      setFrameIndex(0);
      const replayWindowId = next.answer?.provenance.replay_window_id;
      const firstFrame = next.answer?.replay?.frames[0];
      if (replayWindowId && firstFrame) {
        await filmRoomReplayFrame({ replay_window_id: replayWindowId, frame_id: firstFrame.frame_id });
      }
    } catch (event) {
      setError(event instanceof Error ? event.message : String(event));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void submit();
  }, []);

  return (
    <main className="filmRoom">
      <header className="filmHeader">
        <div className="filmWordmark">ENTRELÍNEAS · FILM ROOM</div>
        <div className="filmChips">
          <span>ALL 7 MATCHES</span>
          <span>J03WOH</span>
          <span>HERMES v2</span>
        </div>
      </header>

      <AskThread
        response={response}
        error={error}
        onClarify={(pending, answer) => void submit({ pending_clarification: pending, answer })}
      />

      <form
        className="filmAskbar"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <input value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
        <button type="submit" disabled={busy}>
          {busy ? "RUNNING" : "ASK"}
        </button>
      </form>

      <section className="filmGrid">
        <div>
          <PitchReplay replay={replay} frameIndex={frameIndex} setFrameIndex={setFrameIndex} />
          <ProvenanceStrip response={response} />
        </div>
        <aside className="filmRail">
          {response?.answer?.interval_metric ? <IntervalCard metric={response.answer.interval_metric} /> : null}
          <MomentList moments={moments} selected={selectedMoment} setSelected={setSelectedMoment} />
          <section className="filmPanel notesPanel">
            <div className="filmPanelHeader">
              <span>Evidence</span>
              <span>{selectedFrame?.frame_id ?? "none"}</span>
            </div>
            <pre>{JSON.stringify(moments[selectedMoment]?.evidence_row ?? moments[selectedMoment]?.requested_evidence ?? {}, null, 2)}</pre>
          </section>
        </aside>
      </section>
    </main>
  );
}
