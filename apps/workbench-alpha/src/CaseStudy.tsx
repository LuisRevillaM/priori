import React from "react";
import { CoachMomentPitch, type CoachMomentPayload } from "./MomentZero";
import { layoutPitch, pitchPointToPixel } from "./pitchGeometry";
import type { ReplayPayload } from "./types";

// Set to the GitHub blob base for the pushed branch IF the repo is public to the
// reader (e.g. "https://github.com/<org>/<repo>/blob/codex/afl08-passport-loop").
// Leave null to render plain file paths instead of links — never ship a dead link.
const REPO_BASE: string | null = null;

const SOURCES = [
  { label: "Controlled-pass verification", path: "delivery/m2a-high-bypass-completed-pass/M2A_S1A_CONTROLLED_PASS.md" },
  { label: "High-bypass verification", path: "delivery/m2a-high-bypass-completed-pass/M2A_S1C_HIGH_BYPASS_RESULTS.md" },
  { label: "High-bypass typed plan", path: "config/query-plans/high_bypass_completed_pass.experimental.v1.json" },
  { label: "Typed query-plan library (the tactical language)", path: "config/query-plans/" }
];

const LAYERS = [
  "Raw event + tracking data (IDSSE / DFL)",
  "Canonical match state",
  "Primitive / relation catalog",
  "Typed query plan",
  "Compiler · binder · search",
  "Deterministic runtime",
  "PASS / FAIL / UNKNOWN evidence",
  "Replay + coach-facing wording"
];

const REPLAY_PACKET_PATH = "/case-study-high-bypass-replays.json";
const TEAM_PRESS_PACKET_PATH = "/case-study-team-press-replays.json";

type ReplayPacket = {
  replays: Array<{
    index: number;
    payload: unknown;
  }>;
};

type TeamPressPayload = {
  schema_version: "coach_moment.team_press.v0";
  moment: {
    match_id: string;
    period: string;
    team_role?: string | null;
    anchor_frame_id: number;
    carrier_id: string;
    team_press_status: string;
    pressure_actor_ids: string[];
    pressure_actor_count: number;
    nearby_defender_count: number;
    observed_defender_count: number;
    pressure_angle_spread_degrees: number;
    maximum_press_distance_m: number;
    minimum_pressing_defenders: number;
    minimum_angle_spread_degrees: number;
    coverage_status: string;
    pressure_actor_evidence: Array<{
      player_id: string;
      distance_m: number;
      bearing_degrees: number;
      closing_speed_mps: number;
      approach_angle_degrees: number;
      defender_point: { x_m: number; y_m: number };
      previous_defender_point?: { x_m: number; y_m: number };
    }>;
    carrier_point: { x_m: number; y_m: number };
    claim_boundary: string;
  };
  replay: ReplayPayload;
  visual_contract: Record<string, unknown>;
};

export function CaseStudy() {
  const [replays, setReplays] = React.useState<Record<number, CoachMomentPayload>>({});
  const [teamPressReplays, setTeamPressReplays] = React.useState<Record<number, TeamPressPayload>>({});

  React.useEffect(() => {
    let cancelled = false;
    fetch(REPLAY_PACKET_PATH)
      .then((response) => {
        if (!response.ok) throw new Error(`Replay packet unavailable: ${response.status}`);
        return response.json() as Promise<ReplayPacket>;
      })
      .then((packet) => {
        if (cancelled) return;
        setReplays(
          Object.fromEntries(packet.replays.map((item) => [item.index, item.payload as CoachMomentPayload]))
        );
      })
      .catch(() => {
        if (!cancelled) setReplays({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    fetch(TEAM_PRESS_PACKET_PATH)
      .then((response) => {
        if (!response.ok) throw new Error(`Team-press replay packet unavailable: ${response.status}`);
        return response.json() as Promise<ReplayPacket>;
      })
      .then((packet) => {
        if (cancelled) return;
        setTeamPressReplays(
          Object.fromEntries(packet.replays.map((item) => [item.index, item.payload as TeamPressPayload]))
        );
      })
      .catch(() => {
        if (!cancelled) setTeamPressReplays({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="cs">
      <style>{CSS}</style>

      <article className="cs-col">
        <p className="cs-eyebrow">Priori · Engineering note</p>
        <h1>A soccer language compiler: approach, library, and what testing it revealed</h1>
        <p className="cs-lede">
          A compiler for football concepts: describe a situation, compile it into
          evidence-backed primitives, and find the real moments in tracking data where
          that situation occurred.
        </p>

        <section className="cs-diagram" aria-label="Architecture">
          {LAYERS.map((l, i) => (
            <React.Fragment key={l}>
              <div className="cs-node">{l}</div>
              {i < LAYERS.length - 1 && <div className="cs-arrow">↓</div>}
            </React.Fragment>
          ))}
          <div className="cs-invariant">
            Invariant across every layer: <strong>product language cannot exceed evidence strength.</strong>
          </div>
        </section>

        <h2>What we’re building</h2>
        <p>
          The goal is a compiler for football concepts. Someone describes a situation — a pass that
          breaks a line, a switch of play, a team building out from the back — and the system finds
          the real moments in tracking data where that situation occurred. The input is public
          IDSSE/DFL data: per-frame positions for every player and the ball, plus an event feed.
        </p>
        <p>
          The hard part is not finding football-looking events. It is being precise about what the
          system is allowed to claim about them. A “completed pass” in an event feed is a label.
          Whether the receiver controlled it, whether the team kept it, and whether it led anywhere
          are separate facts that need separate evidence. The system treats each as a distinct claim,
          and the language shown to a user is never allowed to be stronger than the evidence behind it.
        </p>

        <h2>The approach</h2>
        <p>
          Every measurement is a primitive: a deterministic function over the tracking data that
          returns a typed result plus the evidence for it. A primitive returns PASS, FAIL, or UNKNOWN.
          UNKNOWN means the data was insufficient to decide, not that the answer is no. Each primitive
          also has a claim boundary — an explicit statement of what its result does and does not mean:
          geometry, for instance, but not intent, quality, or causation.
        </p>
        <p>
          Primitives compose. A coach-facing concept is a typed plan over several primitives, with
          thresholds and a defined set of evidence fields it may expose. A request either compiles to
          an executable plan or returns an honest gap. Nothing is a hand-written highlight detector.
        </p>

        <h2>What the library contains</h2>
        <p>The catalog currently has about forty primitives and relations. Grouped by what they describe:</p>
        <ul>
          <li><strong>Build-up:</strong> possession segments, pass chains, structured zones, controlled line breaks.</li>
          <li><strong>Ball movement:</strong> switch of play, carries, one-touch relays, lateral shift, progressive corridors.</li>
          <li><strong>Progression:</strong> forward progression and final-third entry, opponents bypassed.</li>
          <li><strong>Defending and pressing:</strong> team press, pressure on the carrier, marking, cover shadow, defensive lines, compactness, local numerical advantage.</li>
          <li><strong>Off the ball:</strong> runs and run types, support arrival, time to arrival, lane occupancy, space generation.</li>
          <li><strong>Set pieces:</strong> set-piece structure and restart type.</li>
        </ul>
        <p>
          These compute geometric and kinematic facts. A primitive existing in the catalog is not the
          same as its coach-facing meaning being proven; each one still has to be validated on its own.
        </p>
        <p>
          The useful contrast is high-bypass beside team press. High-bypass asks whether one pass moved
          the ball past opponents and whether the receiver controlled it — an on-ball attacking action
          anchored on a pass event. Team press has no pass and no possession in it: it asks whether at
          least two defenders came within seven metres of the carrier, were closing on him, and were
          spread across at least thirty degrees, so the pressure arrived from more than one side. If too
          few defenders are tracked, it returns UNKNOWN rather than judging pressure it cannot see.
        </p>
        <p>
          That primitive is substrate-verified, not product-validated. It shows the range of the library:
          attacking action and defensive pressure geometry compile to different evidence. It does not
          claim a coordinated press, trap, intent, quality, or tactical cause.
        </p>
        <TeamPressMiniReplay
          payload={teamPressReplays[0]}
          verdict="Team-press geometry PASS · substrate example"
          caption="Observed pressure on the carrier: four defenders satisfy the distance, closing, and angle-spread gates. This shows convergence geometry, not a coordinated press or trap."
        />

        <h2>Putting it to test: high-bypass passes</h2>
        <p>
          We took one concept all the way through: a high-bypass pass — a completed, controlled pass
          that moves the ball forward and takes several opponents out of the play. As a typed plan:
        </p>
        <pre>{`controlled_pass_episode
+ opponents_bypassed_by_action
+ forward_progression ≥ 8 m
→ high_bypass_completed_pass`}</pre>
        <MiniReplay
          payload={replays[0]}
          verdict="Open-play clean-control PASS · catalog index 0"
          caption="What the surface should keep: an open-play high-bypass where clean control is held after reception."
        />
        <p>
          It was a useful test because it touches the whole stack: event feed, tracking, geometry,
          control, possession, and the wording a coach finally sees.
        </p>

        <h2>Findings</h2>
        <p>
          At the substrate level the controlled-pass primitive does what it should. On the verified
          scope, match <code>J03WOY</code>, it evaluated 639 candidate events:
        </p>
        <pre>{`453 PASS
135 FAIL
 51 UNKNOWN`}</pre>
        <p>
          The non-PASS cases carry specific reasons, among them <code>another_player_controlled_first</code>{" "}
          (35), <code>possession_definitively_broke</code> (67), <code>release_contradicted</code>{" "}
          (33), and <code>release_not_confirmed</code> (84). The system records why a candidate failed
          instead of dropping it silently.
        </p>
        <p>
          The same data shows the limit. Among verified controlled passes, the median time from release
          to reception is 0.84 seconds and the median forward progression is 0.53 metres. A controlled
          pass is often a brief touch that barely advances. That is a sound primitive, but it does not
          support words like “successful” or “kept it.”
        </p>
        <p>
          The first high-bypass surface ignored that limit and presented these moments as successful
          attacking actions. When the replay was extended past the moment of reception, the reception
          often never settled into clean control. The ball could stay loose or contested without either
          side holding it cleanly. The geometry was right; the word “successful” was not earned.
        </p>
        <MiniReplay
          payload={replays[5]}
          verdict="Clean-control FAIL · catalog index 5"
          caption="The first surface would have treated this as successful. The failure is narrower: clean control never settles long enough to back that word."
        />
        <p>
          The first attempt to fix this used the provider’s possession flag to confirm the team kept the
          ball. It passed the same unsettled moments, because that flag
          credits a team through contested and transitional touches. It agreed with the original mistake
          instead of catching it.
        </p>
        <p>
          A second issue surfaced once control was handled properly. Of the five moments that passed a
          stricter control check, two came from restarts — a free kick and a throw-in. They were valid
          high-bypass passes and valid controlled receptions, but not open-play examples.
        </p>
        <MiniReplay
          payload={replays[1]}
          verdict="Clean-control PASS · restart · catalog index 1"
          caption="A valid high-bypass and a genuine controlled reception, but from a free kick rather than open play."
        />

        <h2>What changed, and where</h2>
        <p>
          It is worth being exact about where these fixes live, because the location is the point. None
          of them changed the core compiler. The primitives were already truthful. The overclaims
          happened at the boundary between the substrate and the coach-facing product, and that is where
          the fences were added.
        </p>
        <p>
          <strong>Clean-control check — generation layer.</strong> The check,{" "}
          <code>clean_control_retention_sequence</code>, is not a core catalog primitive. It runs over
          the compiler’s output, in the layer that prepares moments for the surface, and keeps only the
          passes where control was genuinely held. Of twenty raw high-bypass passes, five passed.
          Because it is currently a gate rather than a registered primitive, the natural next step is to
          promote it into the catalog so other concepts can reuse it.
        </p>
        <p>
          <strong>Event-context filter — runtime fields, surface default.</strong> The restart typing
          already existed in the core runtime, <code>set_piece_restart_type</code>. The change carried{" "}
          <code>event_type</code>, <code>restart_type</code>, and <code>open_play_status</code> through
          to the moment payload and defaulted the surface to open play. This was mostly plumbing
          knowledge the runtime already had out to where a coach sees it, plus a filter — not new
          detection.
        </p>
        <p>
          <strong>Claim-backing gate — coach API layer.</strong> The coach service,{" "}
          <code>app_service.py</code>, now holds a map of which composition each coach-facing claim
          requires, and refuses to emit a claim unless that composition is present and passing. It fails
          closed. “Controlled reception” requires the clean-control check; “open-play example” requires
          open-play status.
        </p>
        <p>
          The shared property: the core compiler stayed the same, and the product layer stopped saying
          more than the compiler had proven.
        </p>

        <h2>Where this leaves the approach</h2>
        <p>
          The substrate is broad and the claims are kept narrow. The library already spans build-up,
          ball movement, progression, pressing, off-ball movement, and set pieces. What the high-bypass
          work established is the rule the rest of the library has to follow: a coach-facing claim is
          allowed only when the composition beneath it proves that exact claim. The system gets better
          by making each remaining overclaim easy to find and easy to fence, not by adding cleverness on
          top.
        </p>

        <h2>Sources</h2>
        <ul className="cs-sources">
          {SOURCES.map((s) => (
            <li key={s.path}>
              {REPO_BASE ? <a href={`${REPO_BASE}/${s.path}`} target="_blank" rel="noreferrer">{s.label}</a> : s.label}
              <code>{s.path}</code>
            </li>
          ))}
        </ul>
      </article>
    </main>
  );
}

function MiniReplay({
  payload,
  verdict,
  caption
}: {
  payload: CoachMomentPayload | undefined;
  verdict: string;
  caption: string;
}) {
  return (
    <figure className="cs-replay">
      <div className="cs-replay-frame">
        {payload ? <CoachMomentPitch payload={payload} overlayMode="clean" /> : <div className="cs-replay-loading">Loading replay</div>}
      </div>
      <figcaption>
        <span>{verdict}</span>
        {payload ? <ReplayFacts payload={payload} /> : null}
        {caption}
      </figcaption>
    </figure>
  );
}

function TeamPressMiniReplay({
  payload,
  verdict,
  caption
}: {
  payload: TeamPressPayload | undefined;
  verdict: string;
  caption: string;
}) {
  return (
    <figure className="cs-replay cs-replay-team-press">
      <div className="cs-replay-frame">
        {payload ? <TeamPressPitch payload={payload} /> : <div className="cs-replay-loading">Loading replay</div>}
      </div>
      <figcaption>
        <span>{verdict}</span>
        {payload ? <TeamPressFacts payload={payload} /> : null}
        {caption}
      </figcaption>
    </figure>
  );
}

function TeamPressPitch({ payload }: { payload: TeamPressPayload }) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const shellRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const shell = shellRef.current;
    if (!canvas || !shell) return;

    let animationFrame = 0;
    let startedAt: number | null = null;
    const resizeObserver = new ResizeObserver(() => drawAt(performance.now()));
    resizeObserver.observe(shell);

    const drawAt = (timestamp: number) => {
      if (startedAt === null) startedAt = timestamp;
      const progress = ((timestamp - startedAt) % 7200) / 7200;
      renderTeamPress(canvas, shell, payload, progress);
      animationFrame = window.requestAnimationFrame(drawAt);
    };

    animationFrame = window.requestAnimationFrame(drawAt);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
    };
  }, [payload]);

  return (
    <div className="momentCanvasShell" ref={shellRef}>
      <canvas ref={canvasRef} aria-label="Animated observed team-press geometry on a football pitch" />
    </div>
  );
}

function TeamPressFacts({ payload }: { payload: TeamPressPayload }) {
  const moment = payload.moment;
  return (
    <dl className="cs-replay-facts" aria-label="Team-press evidence facts">
      <div>
        <dt>Status</dt>
        <dd>{moment.team_press_status}</dd>
      </div>
      <div>
        <dt>Actors</dt>
        <dd>{moment.pressure_actor_count} / {moment.minimum_pressing_defenders} min</dd>
      </div>
      <div>
        <dt>Radius</dt>
        <dd>{moment.maximum_press_distance_m.toFixed(1)}m</dd>
      </div>
      <div>
        <dt>Spread</dt>
        <dd>{moment.pressure_angle_spread_degrees.toFixed(1)}° / {moment.minimum_angle_spread_degrees.toFixed(0)}° min</dd>
      </div>
      <div>
        <dt>Tracked</dt>
        <dd>{moment.observed_defender_count} defenders</dd>
      </div>
    </dl>
  );
}

function ReplayFacts({ payload }: { payload: CoachMomentPayload }) {
  const moment = asRecord(payload.moment);
  const clean = asRecord(moment.clean_control_retention);
  const receiver = seconds(clean.receiver_clean_control_max_seconds);
  const team = seconds(clean.team_clean_control_max_seconds);
  const receiverMin = seconds(clean.minimum_receiver_control_seconds);
  const teamMin = seconds(clean.minimum_team_control_seconds);
  const opponent = seconds(clean.opponent_clean_control_max_seconds);
  const phase = String(moment.open_play_status ?? "unknown");
  const restart = typeof moment.restart_type === "string" ? moment.restart_type.replaceAll("_", " ") : null;
  const status = String(clean.status ?? "UNKNOWN");
  return (
    <dl className="cs-replay-facts" aria-label="Replay control facts">
      <div>
        <dt>Control</dt>
        <dd>{status}</dd>
      </div>
      <div>
        <dt>Receiver</dt>
        <dd>{receiver} / {receiverMin} min</dd>
      </div>
      <div>
        <dt>Team</dt>
        <dd>{team} / {teamMin} min</dd>
      </div>
      <div>
        <dt>Opponent</dt>
        <dd>{opponent}</dd>
      </div>
      <div>
        <dt>Phase</dt>
        <dd>{phase === "restart" && restart ? restart : phase.replaceAll("_", " ")}</dd>
      </div>
    </dl>
  );
}

function renderTeamPress(
  canvas: HTMLCanvasElement,
  shell: HTMLDivElement,
  payload: TeamPressPayload,
  progress: number
) {
  const replay = payload.replay;
  const moment = payload.moment;
  const layout = layoutPitch(replay.pitch, Math.max(360, shell.clientWidth));
  const width = layout.canvasWidth;
  const height = layout.canvasHeight;
  const ratio = window.devicePixelRatio || 1;
  const physicalWidth = Math.round(width * ratio);
  const physicalHeight = Math.round(height * ratio);
  if (canvas.width !== physicalWidth || canvas.height !== physicalHeight) {
    canvas.width = physicalWidth;
    canvas.height = physicalHeight;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const frames = replay.frames;
  const eased = easeInOut(Math.min(1, progress / 0.86));
  const index = Math.min(frames.length - 1, Math.max(0, Math.round(eased * (frames.length - 1))));
  const frame = frames[index];
  const pressureReveal = smoothstep(0.32, 0.76, progress);
  const anchorReveal = smoothstep(0.44, 0.82, progress);
  drawCaseStudyPitch(ctx, layout);
  drawTeamPressPlayers(ctx, replay, moment, frame, pressureReveal, layout);
  drawTeamPressGeometry(ctx, replay, moment, frame, pressureReveal, anchorReveal, layout);
  drawCaseStudyBall(ctx, replay, frame, layout);
}

function drawCaseStudyPitch(ctx: CanvasRenderingContext2D, layout: ReturnType<typeof layoutPitch>) {
  ctx.fillStyle = "#102a20";
  ctx.fillRect(0, 0, layout.canvasWidth, layout.canvasHeight);
  const x = layout.marginX;
  const y = layout.marginY;
  const w = layout.fieldWidth;
  const h = layout.fieldHeight;
  ctx.save();
  ctx.strokeStyle = "rgba(240,239,225,.34)";
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);
  ctx.beginPath();
  ctx.moveTo(x + w / 2, y);
  ctx.lineTo(x + w / 2, y + h);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x + w / 2, y + h / 2, 9.15 * layout.scalePxPerM, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function drawTeamPressPlayers(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: TeamPressPayload["moment"],
  frame: ReplayPayload["frames"][number],
  reveal: number,
  layout: ReturnType<typeof layoutPitch>
) {
  const pressureActors = new Set(moment.pressure_actor_ids);
  const actorTeam = moment.team_role;
  for (const entity of frame.entities) {
    if (entity.entity_type === "ball" || entity.entity_id === moment.carrier_id || pressureActors.has(entity.entity_id)) continue;
    const point = pitchPointToPixel(Number(entity.x_m), Number(entity.y_m), replay.pitch, layout);
    const isCarrierTeam = actorTeam != null && entity.team_role === actorTeam;
    ctx.beginPath();
    ctx.fillStyle = isCarrierTeam ? "rgba(237,247,238,.42)" : "rgba(157,90,82,.30)";
    ctx.strokeStyle = isCarrierTeam ? "rgba(237,247,238,.52)" : "rgba(249,224,214,.42)";
    ctx.lineWidth = 1;
    ctx.arc(point.x, point.y, 3.7, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  const carrier = frame.entities.find((entity) => entity.entity_id === moment.carrier_id);
  if (carrier) {
    const point = pitchPointToPixel(Number(carrier.x_m), Number(carrier.y_m), replay.pitch, layout);
    ctx.save();
    ctx.shadowColor = "rgba(255,245,203,.55)";
    ctx.shadowBlur = 16 * reveal;
    ctx.beginPath();
    ctx.fillStyle = "#fff5cb";
    ctx.strokeStyle = "rgba(20,27,19,.72)";
    ctx.lineWidth = 1.6;
    ctx.arc(point.x, point.y, 6.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  for (const actorId of moment.pressure_actor_ids) {
    const actor = frame.entities.find((entity) => entity.entity_id === actorId);
    if (!actor) continue;
    const point = pitchPointToPixel(Number(actor.x_m), Number(actor.y_m), replay.pitch, layout);
    ctx.save();
    ctx.shadowColor = "rgba(242,207,115,.45)";
    ctx.shadowBlur = 10 * reveal;
    ctx.beginPath();
    ctx.fillStyle = `rgba(242,207,115,${0.42 + reveal * 0.38})`;
    ctx.strokeStyle = "rgba(255,249,220,.92)";
    ctx.lineWidth = 1.8;
    ctx.arc(point.x, point.y, 5.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }
}

function drawTeamPressGeometry(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: TeamPressPayload["moment"],
  frame: ReplayPayload["frames"][number],
  reveal: number,
  anchorReveal: number,
  layout: ReturnType<typeof layoutPitch>
) {
  const carrier = frame.entities.find((entity) => entity.entity_id === moment.carrier_id);
  if (!carrier) return;
  const carrierPoint = pitchPointToPixel(Number(carrier.x_m), Number(carrier.y_m), replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = 0.18 + 0.26 * reveal;
  ctx.strokeStyle = "#f2cf73";
  ctx.lineWidth = 1.4;
  ctx.setLineDash([5, 8]);
  ctx.beginPath();
  ctx.arc(carrierPoint.x, carrierPoint.y, moment.maximum_press_distance_m * layout.scalePxPerM, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();

  for (const actorId of moment.pressure_actor_ids) {
    const actor = frame.entities.find((entity) => entity.entity_id === actorId);
    if (!actor) continue;
    const actorPoint = pitchPointToPixel(Number(actor.x_m), Number(actor.y_m), replay.pitch, layout);
    ctx.save();
    ctx.globalAlpha = 0.16 + 0.58 * anchorReveal;
    ctx.strokeStyle = "#f2cf73";
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(actorPoint.x, actorPoint.y);
    ctx.lineTo(carrierPoint.x, carrierPoint.y);
    ctx.stroke();
    ctx.restore();
  }
}

function drawCaseStudyBall(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  frame: ReplayPayload["frames"][number],
  layout: ReturnType<typeof layoutPitch>
) {
  const ball = frame.entities.find((entity) => entity.entity_type === "ball");
  if (!ball) return;
  const point = pitchPointToPixel(Number(ball.x_m), Number(ball.y_m), replay.pitch, layout);
  ctx.save();
  ctx.shadowColor = "rgba(242,207,115,.62)";
  ctx.shadowBlur = 12;
  ctx.beginPath();
  ctx.fillStyle = "#f2cf73";
  ctx.strokeStyle = "rgba(20,27,19,.92)";
  ctx.lineWidth = 1.5;
  ctx.arc(point.x, point.y, 4.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function easeInOut(value: number) {
  return value < 0.5 ? 4 * value * value * value : 1 - Math.pow(-2 * value + 2, 3) / 2;
}

function smoothstep(edge0: number, edge1: number, value: number) {
  const x = Math.max(0, Math.min(1, (value - edge0) / (edge1 - edge0)));
  return x * x * (3 - 2 * x);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function seconds(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(2)}s` : "n/a";
}

const CSS = `
.cs{background:#faf9f5;color:#1e2320;min-height:100vh;padding:72px 24px 120px;font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.cs-col{max-width:680px;margin:0 auto}
.cs-eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:12px;font-weight:650;color:#5d7a68;margin:0 0 14px}
.cs h1{font-size:clamp(30px,5vw,42px);line-height:1.12;letter-spacing:-.02em;margin:0 0 18px;color:#1f2923}
.cs-lede{font-size:19px;line-height:1.55;color:#303831;margin:0 0 40px}
.cs h2{font-size:21px;letter-spacing:-.01em;margin:48px 0 14px;color:#1f2923}
.cs p{margin:0 0 18px}
.cs ul{margin:0 0 18px;padding-left:22px}.cs li{margin:0 0 6px}
.cs code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;background:#edefe8;padding:2px 6px;border-radius:5px;color:#28332b}
.cs pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;line-height:1.5;background:#f1f3ec;border:1px solid #e0e4da;border-radius:8px;padding:16px 18px;overflow-x:auto;margin:0 0 22px;color:#28332b}
.cs blockquote{margin:0 0 22px;padding:4px 0 4px 18px;border-left:3px solid #8fac9a;color:#303831;font-size:18px}
.cs-pull{font-size:22px;line-height:1.4;font-weight:600;color:#1f2923;margin:30px 0;letter-spacing:-.01em}
.cs-invariant-q{font-size:20px;font-weight:600;border-left-color:#c9a24a;color:#1f2923}
.cs-two{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0 0 22px}
@media(max-width:560px){.cs-two{grid-template-columns:1fr}}
.cs-cap{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#5d7a68;font-weight:650;margin:0 0 8px}
.cs-two pre{margin:0;height:100%}
.cs-diagram{margin:0 0 44px;display:flex;flex-direction:column;align-items:center;text-align:center}
.cs-node{width:100%;max-width:420px;background:#fff;border:1px solid #d8ddd2;border-radius:8px;padding:11px 14px;font-size:14px;font-weight:550;color:#28332b;box-shadow:0 1px 2px rgba(40,51,43,.04)}
.cs-arrow{color:#8fac9a;font-size:14px;line-height:1;margin:5px 0}
.cs-invariant{margin-top:18px;font-size:13px;color:#5d7a68;max-width:460px}
.cs-sources{list-style:none;padding:0}
.cs-sources li{display:flex;flex-direction:column;gap:3px;margin:0 0 12px}
.cs-sources a{color:#2f6b4f;text-decoration:none;font-weight:550}.cs-sources a:hover{text-decoration:underline}
.cs-sources code{align-self:flex-start;font-size:12px;background:none;color:#6a716a;padding:0}
.cs-replay{width:min(920px,calc(100vw - 40px));margin:28px 0 30px 50%;transform:translateX(-50%)}
.cs-replay-frame{background:#102a20;border:1px solid rgba(31,41,35,.18);border-radius:12px;overflow:hidden;box-shadow:0 18px 48px rgba(31,41,35,.18)}
.cs-replay .momentCanvasShell{width:100%;filter:none}
.cs-replay .momentCanvasShell canvas{border:0;border-radius:0}
.cs-replay-loading{display:grid;place-items:center;min-height:320px;color:rgba(250,249,245,.72);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;text-transform:uppercase;letter-spacing:.08em}
.cs-replay figcaption{margin:10px 2px 0;color:#4f5b52;font-size:13px;line-height:1.45}
.cs-replay figcaption span{display:block;margin:0 0 3px;color:#2f6b4f;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.cs-replay-facts{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin:8px 0 10px}
.cs-replay-facts div{min-width:0;border:1px solid #dfe4da;border-radius:6px;background:#f4f5ef;padding:6px 7px}
.cs-replay-facts dt{margin:0 0 2px;color:#6b756d;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;text-transform:uppercase;letter-spacing:.06em}
.cs-replay-facts dd{margin:0;color:#28332b;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:720px){.cs-replay-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.cs-replay{width:calc(100vw - 28px);margin-top:22px;margin-bottom:24px}}
`;
