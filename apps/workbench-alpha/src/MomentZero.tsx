import { useEffect, useRef } from "react";
import momentHighBypassPayload from "./generated/moment-high-bypass.json";
import momentLineBreakSupportedPayload from "./generated/moment-line-break-supported.json";
import momentZeroPayload from "./generated/moment-zero.json";
import { layoutPitch, pitchPointToPixel } from "./pitchGeometry";
import type { ReplayEntity, ReplayPayload } from "./types";

export type MomentZeroPayload = typeof momentZeroPayload;
type MomentZeroMoment = MomentZeroPayload["moment"];
export type HighBypassPayload = typeof momentHighBypassPayload;
type HighBypassMoment = HighBypassPayload["moment"];
export type CoachMomentPayload = MomentZeroPayload | HighBypassPayload;

const PITCH_PALETTE = {
  turf: "#132f24",
  turf2: "#193d2e",
  line: "rgba(240, 239, 225, 0.50)",
  lineSoft: "rgba(240, 239, 225, 0.20)",
  attack: "#edf7ee",
  attackEdge: "rgba(250, 247, 226, 0.92)",
  attackCore: "#bfe4d1",
  defense: "#9d5a52",
  defenseEdge: "rgba(249, 224, 214, 0.86)",
  defenseCore: "#53312e",
  receiver: "#fff5cb",
  passer: "#d8efe3",
  ball: "#f4efe0",
  support: "#d6c17a",
  supportFill: "rgba(214, 193, 122, 0.38)",
  supportVoid: "rgba(249, 246, 220, 0.18)",
  pass: "#f2e5bd",
  lineBreak: "#e4cf82"
} as const;

const TOTAL_MS = 10000;
const POST_RECEPTION_HOLD_FRAMES = 8;

export const momentZeroEvidence = momentZeroPayload;
export const momentLineBreakSupportedEvidence = momentLineBreakSupportedPayload as unknown as MomentZeroPayload;
export const momentHighBypassEvidence = momentHighBypassPayload;

export function MomentZero() {
  return (
    <main className="momentZeroShell">
      <section className="momentStage" aria-label="Moment zero line-break replay">
        <MomentZeroPitch payload={momentZeroPayload} />
        <div className="momentCopy" aria-hidden="true">
          <span className="momentKicker">Moment 0</span>
          <h1>Line broken. The outlet space stays empty.</h1>
        </div>
      </section>
    </main>
  );
}

export function MomentZeroPitch({ payload }: { payload: MomentZeroPayload }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const shell = shellRef.current;
    if (!canvas || !shell) return;

    let animationFrame = 0;
    let startedAt: number | null = null;
    const resizeObserver = new ResizeObserver(() => drawAt(performance.now()));
    resizeObserver.observe(shell);

    const drawAt = (timestamp: number) => {
      if (startedAt === null) startedAt = timestamp;
      const progress = ((timestamp - startedAt) % TOTAL_MS) / TOTAL_MS;
      renderMoment(canvas, shell, payload, progress);
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
      <canvas ref={canvasRef} aria-label="Animated line-break moment on a football pitch" />
    </div>
  );
}

export function CoachMomentPitch({ payload }: { payload: CoachMomentPayload }) {
  if (isHighBypassPayload(payload)) {
    return <HighBypassPitch payload={payload} />;
  }
  return <MomentZeroPitch payload={payload as MomentZeroPayload} />;
}

export function isHighBypassPayload(payload: CoachMomentPayload | unknown): payload is HighBypassPayload {
  return Boolean(
    payload &&
      typeof payload === "object" &&
      "schema_version" in payload &&
      String((payload as { schema_version?: unknown }).schema_version) === "coach_moment.high_bypass_completed_pass.v0"
  );
}

function HighBypassPitch({ payload }: { payload: HighBypassPayload }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const shell = shellRef.current;
    if (!canvas || !shell) return;

    let animationFrame = 0;
    let startedAt: number | null = null;
    const resizeObserver = new ResizeObserver(() => drawAt(performance.now()));
    resizeObserver.observe(shell);

    const drawAt = (timestamp: number) => {
      if (startedAt === null) startedAt = timestamp;
      const progress = ((timestamp - startedAt) % TOTAL_MS) / TOTAL_MS;
      renderHighBypassMoment(canvas, shell, payload, progress);
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
      <canvas ref={canvasRef} aria-label="Animated high-bypass completed pass on a football pitch" />
    </div>
  );
}

function renderMoment(
  canvas: HTMLCanvasElement,
  shell: HTMLDivElement,
  payload: MomentZeroPayload,
  progress: number
) {
  const replay = payload.replay as ReplayPayload;
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

  const frame = frameForProgress(replay, moment, progress);
  const phase = revealPhase(progress);
  drawPitch(ctx, layout);
  drawAttackingEndCue(ctx, replay, moment, layout, phase);
  drawMomentVignette(ctx, layout, phase);
  drawPlayers(ctx, replay, moment, frame, phase);
  drawDefensiveLine(ctx, replay, moment, frame, phase);
  drawPassPath(ctx, replay, moment, phase);
  drawSupportRegion(ctx, replay, moment, phase);
  drawSupportArrivals(ctx, replay, moment, frame, phase);
  drawMeasuredOutcomeBeat(ctx, replay, moment, frame, phase);
  drawReceptionDock(ctx, replay, moment, frame, phase);
  drawReceiverFocus(ctx, replay, moment, frame, phase);
  drawBall(ctx, replay, moment, frame, phase);
}

function renderHighBypassMoment(
  canvas: HTMLCanvasElement,
  shell: HTMLDivElement,
  payload: HighBypassPayload,
  progress: number
) {
  const replay = payload.replay as ReplayPayload;
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

  const frame = highBypassFrameForProgress(replay, moment, progress);
  const phase = highBypassPhase(progress);
  drawPitch(ctx, layout);
  drawHighBypassAttackingEndCue(ctx, replay, moment, layout, phase);
  drawHighBypassVignette(ctx, layout, moment, replay, phase);
  drawHighBypassPlayers(ctx, replay, moment, frame, phase);
  drawHighBypassPath(ctx, replay, moment, phase);
  drawBypassedOpponents(ctx, replay, moment, phase);
  drawMeasuredOutcomeBeat(ctx, replay, moment, frame, phase);
  drawReceptionDock(ctx, replay, moment, frame, phase);
  drawHighBypassBall(ctx, replay, moment, frame, phase);
}

function frameForProgress(replay: ReplayPayload, moment: MomentZeroMoment, progress: number) {
  const visualEndFrameId = momentZeroVisualEndFrameId(moment);
  const visibleFrames = replay.frames.filter((frame) => frame.frame_id <= visualEndFrameId);
  const frames = visibleFrames.length > 0 ? visibleFrames : replay.frames;
  const eased = easeInOutCubic(Math.min(1, progress / 0.84));
  const index = Math.min(frames.length - 1, Math.max(0, Math.round(eased * (frames.length - 1))));
  return frames[index];
}

function highBypassFrameForProgress(replay: ReplayPayload, moment: HighBypassMoment, progress: number) {
  const visualEndFrameId = moment.outcome_sequence.end_frame_id;
  const visibleFrames = replay.frames.filter((frame) => frame.frame_id <= visualEndFrameId);
  const frames = visibleFrames.length > 0 ? visibleFrames : replay.frames;
  const eased = easeInOutCubic(Math.min(1, progress / 0.84));
  const index = Math.min(frames.length - 1, Math.max(0, Math.round(eased * (frames.length - 1))));
  return frames[index];
}

export function momentZeroVisualEndFrameId(moment: MomentZeroMoment) {
  if (moment.outcome_sequence.status === "PASS") {
    return moment.outcome_sequence.end_frame_id;
  }
  if (hasObservedSupport(moment)) {
    return moment.support_window_end_frame_id;
  }
  return moment.reception_frame_id + POST_RECEPTION_HOLD_FRAMES;
}

export function momentZeroLineEvidenceFrameId(moment: MomentZeroMoment) {
  const lineId = targetObservedLine(moment)?.line_id;
  const match = typeof lineId === "string" ? lineId.match(/:(\d+):\d+$/) : null;
  return match ? Number(match[1]) : moment.release_frame_id;
}

export function momentZeroBallEvidenceFrameId(moment: MomentZeroMoment, frameId: number) {
  if (moment.outcome_sequence.status === "PASS" && frameId <= moment.outcome_sequence.end_frame_id) {
    return frameId;
  }
  return frameId > moment.reception_frame_id ? moment.reception_frame_id : frameId;
}

function targetObservedLine(moment: MomentZeroMoment) {
  const targetRank = moment.requested_evidence.target_line_rank;
  return moment.observed_lines.find((line) => line.line_rank === targetRank) ?? null;
}

function hasObservedSupport(moment: MomentZeroMoment) {
  return moment.support_region.support_arrival_status === "PASS" && moment.support_region.supporting_player_ids.length > 0;
}

function revealPhase(progress: number) {
  return {
    setup: fadeWindow(progress, 0.02, 0.18),
    line: fadeWindow(progress, 0.10, 0.28),
    pass: fadeWindow(progress, 0.18, 0.55),
    break: fadeWindow(progress, 0.42, 0.66),
    reception: fadeWindow(progress, 0.50, 0.70),
    support: fadeWindow(progress, 0.58, 0.78),
    lonely: fadeWindow(progress, 0.76, 0.95),
    outcome: fadeWindow(progress, 0.74, 0.94),
    resetFade: 1 - fadeWindow(progress, 0.94, 1),
    pulse: 0.5 + 0.5 * Math.sin(progress * Math.PI * 2)
  };
}

function drawPitch(ctx: CanvasRenderingContext2D, layout: ReturnType<typeof layoutPitch>) {
  const { canvasWidth: width, canvasHeight: height, marginX, marginY, fieldWidth, fieldHeight } = layout;
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, PITCH_PALETTE.turf);
  gradient.addColorStop(1, PITCH_PALETTE.turf2);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.strokeStyle = PITCH_PALETTE.line;
  ctx.lineWidth = 1.3;
  ctx.strokeRect(marginX, marginY, fieldWidth, fieldHeight);
  ctx.strokeStyle = PITCH_PALETTE.lineSoft;
  ctx.beginPath();
  ctx.moveTo(width / 2, marginY);
  ctx.lineTo(width / 2, height - marginY);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(width / 2, height / 2, Math.min(fieldWidth, fieldHeight) * 0.12, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function drawMomentVignette(
  ctx: CanvasRenderingContext2D,
  layout: ReturnType<typeof layoutPitch>,
  phase: ReturnType<typeof revealPhase>
) {
  const { canvasWidth: width, canvasHeight: height } = layout;
  ctx.save();
  ctx.globalAlpha = (0.06 + 0.10 * phase.lonely) * phase.resetFade;
  const gradient = ctx.createRadialGradient(width * 0.47, height * 0.35, height * 0.20, width * 0.47, height * 0.35, height * 0.76);
  gradient.addColorStop(0, "rgba(255, 255, 255, 0)");
  gradient.addColorStop(0.58, "rgba(3, 13, 10, 0.04)");
  gradient.addColorStop(1, "rgba(3, 13, 10, 0.78)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
  ctx.restore();
}

function drawAttackingEndCue(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  layout: ReturnType<typeof layoutPitch>,
  phase: ReturnType<typeof revealPhase>
) {
  const attackingLeft = moment.support_region.attacking_direction === -1;
  const goalX = attackingLeft ? layout.marginX : layout.marginX + layout.fieldWidth;
  const goalMouthWidthM = 7.32;
  const goalHalf = (goalMouthWidthM / 2) * layout.scalePxPerM;
  const center = pitchPointToPixel(attackingLeft ? -replay.pitch.length_m / 2 : replay.pitch.length_m / 2, 0, replay.pitch, layout);
  const outside = attackingLeft ? -1 : 1;
  ctx.save();
  ctx.globalAlpha = (0.20 + 0.08 * phase.pass) * phase.resetFade;
  ctx.strokeStyle = "rgba(240, 239, 225, 0.34)";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(goalX, center.y - goalHalf);
  ctx.lineTo(goalX + outside * 12, center.y - goalHalf);
  ctx.lineTo(goalX + outside * 12, center.y + goalHalf);
  ctx.lineTo(goalX, center.y + goalHalf);
  ctx.stroke();
  ctx.restore();
}

function drawPlayers(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const candidateIds = new Set<string>(moment.support_region.candidate_player_ids);
  const supportIds = new Set<string>(moment.support_region.supporting_player_ids);
  for (const entity of frame.entities) {
    if (entity.entity_type === "ball") continue;
    const point = pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout);
    const isReceiver = entity.entity_id === moment.receiver_id;
    const isPasser = entity.entity_id === moment.passer_id;
    const isDefender = moment.defensive_line_player_ids.includes(entity.entity_id);
    const isCandidate = candidateIds.has(entity.entity_id);
    const isSupporter = supportIds.has(entity.entity_id);
    const isStory = isReceiver || isPasser || isDefender || isSupporter;
    const isAttack = entity.team_role === moment.perspective_team_role;
    const fadeIrrelevant = Math.max(phase.break, phase.support, phase.lonely);
    const radius = isReceiver ? 7.9 : isSupporter ? 6.9 : isPasser ? 6.6 : isDefender ? 6.2 : isCandidate ? 4.8 : 4.2;
    const alpha = isStory
      ? 0.98
      : isCandidate
        ? 0.62 - 0.04 * fadeIrrelevant
        : 0.54 - 0.04 * fadeIrrelevant;
    ctx.save();
    ctx.globalAlpha = Math.max(0.08, alpha) * phase.resetFade;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = isAttack ? PITCH_PALETTE.attack : PITCH_PALETTE.defense;
    ctx.strokeStyle = isAttack ? PITCH_PALETTE.attackEdge : PITCH_PALETTE.defenseEdge;
    ctx.lineWidth = isStory ? 1.8 : 1.05;
    ctx.fill();
    ctx.stroke();
    ctx.globalAlpha = Math.max(0.08, alpha * (isAttack ? 0.44 : 0.58)) * phase.resetFade;
    ctx.fillStyle = isAttack ? PITCH_PALETTE.attackCore : PITCH_PALETTE.defenseCore;
    ctx.beginPath();
    ctx.arc(point.x, point.y, Math.max(1.7, radius * 0.34), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

function drawDefensiveLine(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  _frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  // The broken line is the observed line at the evidence frame, not the defenders' later positions.
  const lineFrameId = momentZeroLineEvidenceFrameId(moment);
  const lineFrame = replay.frames.find((item) => item.frame_id === lineFrameId) ?? replay.frames[0];
  const targetLine = targetObservedLine(moment);
  const witnessIds = targetLine?.defender_ids ?? moment.defensive_line_player_ids;
  const witnesses = witnessIds
    .map((id) => lineFrame.entities.find((item) => item.entity_id === id))
    .filter((entity): entity is ReplayEntity => Boolean(entity))
    .sort((left, right) => left.y_m - right.y_m);
  ctx.save();
  ctx.globalAlpha = (0.28 + 0.62 * phase.line) * phase.resetFade;
  ctx.strokeStyle = PITCH_PALETTE.lineBreak;
  ctx.lineWidth = 2.2 + 1.6 * phase.break;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  if (witnesses.length >= 2) {
    const lineX = targetLine?.line_x_m ?? moment.line_x_m;
    const start = pitchPointToPixel(lineX, witnesses[0].y_m, replay.pitch, layout);
    const end = pitchPointToPixel(lineX, witnesses[witnesses.length - 1].y_m, replay.pitch, layout);
    const extend = (4 + 1.5 * phase.break) * layout.scalePxPerM;
    ctx.beginPath();
    ctx.moveTo(start.x, start.y - extend);
    ctx.lineTo(end.x, end.y + extend);
    ctx.stroke();
  } else {
    const center = pitchPointToPixel(moment.line_x_m, 0, replay.pitch, layout);
    ctx.beginPath();
    ctx.moveTo(center.x, center.y - 44);
    ctx.lineTo(center.x, center.y + 44);
    ctx.stroke();
  }
  for (const entity of witnesses) {
    const point = pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout);
    const halo = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, 20 + 7 * phase.break);
    halo.addColorStop(0, "rgba(228, 207, 130, 0.22)");
    halo.addColorStop(1, "rgba(228, 207, 130, 0)");
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 20 + 7 * phase.break, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawPassPath(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  phase: ReturnType<typeof revealPhase>
) {
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const points = replay.frames
    .filter((frame) => frame.frame_id >= moment.release_frame_id && frame.frame_id <= moment.reception_frame_id)
    .map((frame) => frame.entities.find((entity) => entity.entity_type === "ball"))
    .filter((entity): entity is ReplayEntity => Boolean(entity))
    .map((entity) => pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout));
  const visibleCount = Math.max(2, Math.round(points.length * phase.pass));
  ctx.save();
  ctx.globalAlpha = phase.pass * phase.resetFade;
  ctx.strokeStyle = PITCH_PALETTE.pass;
  ctx.lineWidth = 3.4;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  points.slice(0, visibleCount).forEach((point, index) => {
    if (index === 0) ctx.moveTo(point.x, point.y);
    else ctx.lineTo(point.x, point.y);
  });
  ctx.stroke();
  ctx.restore();
}

function drawSupportRegion(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  phase: ReturnType<typeof revealPhase>
) {
  const support = moment.support_region;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const reference = pitchPointToPixel(support.reference_point.x_m, support.reference_point.y_m, replay.pitch, layout);
  const radius = support.maximum_support_distance_m * layout.scalePxPerM;
  const behindToLeft = support.attacking_direction === 1;
  const alpha = phase.support * phase.resetFade;
  if (alpha <= 0) return;
  const left = behindToLeft ? reference.x - radius : reference.x;
  const right = behindToLeft ? reference.x : reference.x + radius;
  const top = reference.y - radius;
  const height = radius * 2;
  const pulse = 0.82 + 0.18 * phase.pulse;
  const observedSupport = hasObservedSupport(moment);
  const centerX = (left + right) / 2;
  const centerY = reference.y;

  ctx.save();
  ctx.globalAlpha = alpha * (observedSupport ? 0.34 + 0.28 * phase.lonely : 0.48 + 0.42 * phase.lonely);
  ctx.beginPath();
  ctx.arc(reference.x, reference.y, radius, 0, Math.PI * 2);
  ctx.clip();
  ctx.shadowColor = observedSupport ? "rgba(216, 239, 227, 0.32)" : "rgba(214, 193, 122, 0.46)";
  ctx.shadowBlur = 18 + 18 * phase.lonely;
  const glow = ctx.createRadialGradient(centerX, centerY, radius * 0.06, centerX, centerY, radius * (0.96 + 0.12 * phase.lonely));
  glow.addColorStop(0, observedSupport ? "rgba(216, 239, 227, 0.14)" : "rgba(249, 246, 220, 0.28)");
  glow.addColorStop(0.50, observedSupport ? "rgba(216, 239, 227, 0.24)" : "rgba(214, 193, 122, 0.24)");
  glow.addColorStop(1, "rgba(214, 193, 122, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(left, top, radius, height);
  ctx.restore();

  ctx.save();
  ctx.globalAlpha = alpha * (0.62 + 0.38 * phase.lonely) * pulse;
  ctx.strokeStyle = PITCH_PALETTE.support;
  ctx.shadowColor = "rgba(214, 193, 122, 0.40)";
  ctx.shadowBlur = 10 + 10 * phase.lonely;
  ctx.lineWidth = 2.2 + 0.7 * phase.lonely;
  ctx.lineCap = "round";
  ctx.beginPath();
  if (behindToLeft) {
    ctx.arc(reference.x, reference.y, radius, Math.PI / 2, Math.PI * 1.5);
  } else {
    ctx.arc(reference.x, reference.y, radius, -Math.PI / 2, Math.PI / 2);
  }
  ctx.stroke();

  if (!observedSupport) {
    ctx.globalAlpha = alpha * phase.lonely * 0.98;
    const voidGradient = ctx.createRadialGradient(centerX, centerY, radius * 0.04, centerX, centerY, radius * 0.72);
    voidGradient.addColorStop(0, "rgba(249, 246, 220, 0.28)");
    voidGradient.addColorStop(0.42, "rgba(249, 246, 220, 0.11)");
    voidGradient.addColorStop(1, "rgba(249, 246, 220, 0)");
    ctx.beginPath();
    ctx.ellipse(centerX, centerY, radius * 0.56, radius * 0.76, 0, 0, Math.PI * 2);
    ctx.fillStyle = voidGradient;
    ctx.fill();
  }
  ctx.restore();
}

function drawSupportArrivals(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  if (!hasObservedSupport(moment)) return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const supportIds = new Set<string>(moment.support_region.supporting_player_ids);
  const supportEntities = frame.entities.filter((entity) => supportIds.has(entity.entity_id));
  if (supportEntities.length === 0) return;
  const alpha = phase.support * phase.resetFade;
  ctx.save();
  for (const entity of supportEntities) {
    const trail = trackedEntityTrail(
      replay,
      entity.entity_id,
      moment.release_frame_id,
      Math.min(frame.frame_id, moment.support_window_end_frame_id),
      layout,
      22
    );
    if (trail.length > 1) {
      const start = trail[0];
      const end = trail[trail.length - 1];
      const trailGradient = ctx.createLinearGradient(start.x, start.y, end.x, end.y);
      trailGradient.addColorStop(0, "rgba(216, 239, 227, 0)");
      trailGradient.addColorStop(0.58, "rgba(216, 239, 227, 0.22)");
      trailGradient.addColorStop(1, "rgba(255, 245, 203, 0.66)");
      ctx.globalAlpha = alpha * (0.42 + 0.30 * phase.lonely);
      ctx.strokeStyle = trailGradient;
      ctx.shadowColor = "rgba(216, 239, 227, 0.16)";
      ctx.shadowBlur = 8;
      ctx.lineWidth = 2.15 + 0.75 * phase.lonely;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      trail.forEach((point, index) => {
        if (index === 0) ctx.moveTo(point.x, point.y);
        else ctx.lineTo(point.x, point.y);
      });
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
    const point = pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout);
    const haloRadius = 28 + 10 * phase.lonely;
    const halo = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, haloRadius);
    halo.addColorStop(0, "rgba(216, 239, 227, 0.34)");
    halo.addColorStop(0.48, "rgba(216, 239, 227, 0.14)");
    halo.addColorStop(1, "rgba(216, 239, 227, 0)");
    ctx.globalAlpha = alpha * (0.72 + 0.28 * phase.pulse);
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(point.x, point.y, haloRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = PITCH_PALETTE.attack;
    ctx.strokeStyle = "rgba(244, 239, 224, 0.80)";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 5.2 + 0.8 * phase.lonely, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function trackedEntityTrail(
  replay: ReplayPayload,
  entityId: string,
  startFrameId: number,
  endFrameId: number,
  layout: ReturnType<typeof layoutPitch>,
  maxPoints: number
) {
  const points = replay.frames
    .filter((item) => item.frame_id >= startFrameId && item.frame_id <= endFrameId)
    .map((item) => item.entities.find((entity) => entity.entity_id === entityId))
    .filter((entity): entity is ReplayEntity => Boolean(entity))
    .map((entity) => pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout));
  return points.slice(Math.max(0, points.length - maxPoints));
}

function drawReceiverFocus(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  const receiver = frame.entities.find((entity) => entity.entity_id === moment.receiver_id);
  if (!receiver) return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const point = pitchPointToPixel(receiver.x_m, receiver.y_m, replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = Math.max(phase.break, phase.lonely) * phase.resetFade * 0.92;
  const halo = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, 34 + 10 * phase.lonely);
  halo.addColorStop(0, "rgba(255, 245, 203, 0.32)");
  halo.addColorStop(0.45, "rgba(255, 245, 203, 0.12)");
  halo.addColorStop(1, "rgba(255, 245, 203, 0)");
  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(point.x, point.y, 34 + 10 * phase.lonely, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = Math.max(phase.break, phase.lonely) * phase.resetFade;
  ctx.fillStyle = PITCH_PALETTE.receiver;
  ctx.beginPath();
  ctx.arc(point.x, point.y, 4.2 + 1.2 * phase.lonely, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawReceptionDock(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: Pick<MomentZeroMoment, "receiver_id" | "reception_frame_id">,
  frame: ReplayPayload["frames"][number],
  phase: { reception: number; outcome: number; resetFade: number; pulse: number }
) {
  if (frame.frame_id < moment.reception_frame_id) return;
  const receptionFrame = replay.frames.find((item) => item.frame_id === moment.reception_frame_id);
  const receiver = receptionFrame?.entities.find((entity) => entity.entity_id === moment.receiver_id);
  const ball = receptionFrame?.entities.find((entity) => entity.entity_type === "ball");
  if (!receiver || !ball) return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const receiverPoint = pitchPointToPixel(receiver.x_m, receiver.y_m, replay.pitch, layout);
  const ballPoint = pitchPointToPixel(ball.x_m, ball.y_m, replay.pitch, layout);
  const alpha = Math.max(phase.reception, phase.outcome * 0.58) * phase.resetFade;
  if (alpha <= 0) return;

  ctx.save();
  ctx.globalAlpha = alpha;
  const dockRadius = 25 + 7 * phase.pulse;
  const dock = ctx.createRadialGradient(receiverPoint.x, receiverPoint.y, 0, receiverPoint.x, receiverPoint.y, dockRadius);
  dock.addColorStop(0, "rgba(255, 245, 203, 0.30)");
  dock.addColorStop(0.46, "rgba(255, 245, 203, 0.12)");
  dock.addColorStop(1, "rgba(255, 245, 203, 0)");
  ctx.fillStyle = dock;
  ctx.beginPath();
  ctx.arc(receiverPoint.x, receiverPoint.y, dockRadius, 0, Math.PI * 2);
  ctx.fill();

  ctx.globalAlpha = alpha * 0.72;
  ctx.strokeStyle = "rgba(244, 239, 224, 0.54)";
  ctx.lineWidth = 1.45;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(ballPoint.x, ballPoint.y);
  ctx.lineTo(receiverPoint.x, receiverPoint.y);
  ctx.stroke();
  ctx.restore();
}

function drawMeasuredOutcomeBeat(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment | HighBypassMoment,
  frame: ReplayPayload["frames"][number],
  phase: { outcome: number; resetFade: number; pulse: number }
) {
  const sequence = moment.outcome_sequence;
  if (sequence.status !== "PASS" || frame.frame_id <= moment.reception_frame_id) return;
  const pathEndFrameId = Math.min(frame.frame_id, sequence.end_frame_id);
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const points = replay.frames
    .filter((item) => item.frame_id >= sequence.start_frame_id && item.frame_id <= pathEndFrameId)
    .map((item) => item.entities.find((entity) => entity.entity_type === "ball"))
    .filter((entity): entity is ReplayEntity => Boolean(entity))
    .map((entity) => pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout));
  if (points.length < 2) return;
  const progress = clamp01((pathEndFrameId - sequence.start_frame_id) / Math.max(1, sequence.end_frame_id - sequence.start_frame_id));
  const alpha = Math.max(phase.outcome, progress * 0.38) * phase.resetFade;
  const start = points[0];
  const end = points[points.length - 1];

  ctx.save();
  drawFinalThirdOutcomeZone(ctx, replay, moment, sequence, phase, progress);

  ctx.globalAlpha = alpha * 0.32;
  const trail = ctx.createLinearGradient(start.x, start.y, end.x, end.y);
  trail.addColorStop(0, "rgba(216, 239, 227, 0)");
  trail.addColorStop(0.42, "rgba(216, 239, 227, 0.18)");
  trail.addColorStop(1, sequence.final_third_status === "PASS" ? "rgba(255, 245, 203, 0.42)" : "rgba(216, 239, 227, 0.34)");
  ctx.strokeStyle = trail;
  ctx.shadowColor = "rgba(216, 239, 227, 0.08)";
  ctx.shadowBlur = 5 + 3 * phase.pulse;
  ctx.lineWidth = 1.55;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) ctx.moveTo(point.x, point.y);
    else ctx.lineTo(point.x, point.y);
  });
  ctx.stroke();

  if (sequence.final_third_status === "PASS" && progress > 0.72) {
    const endpoint = points[points.length - 1];
    const outcomeBoost = sequence.progression_status === "PASS" ? 1 : 0.72;
    const haloRadius = 28 + 9 * phase.pulse * outcomeBoost;
    const halo = ctx.createRadialGradient(endpoint.x, endpoint.y, 0, endpoint.x, endpoint.y, haloRadius);
    halo.addColorStop(0, `rgba(255, 245, 203, ${0.26 * outcomeBoost})`);
    halo.addColorStop(0.52, `rgba(255, 245, 203, ${0.12 * outcomeBoost})`);
    halo.addColorStop(1, "rgba(255, 245, 203, 0)");
    ctx.globalAlpha = alpha * 0.94;
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(endpoint.x, endpoint.y, haloRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.globalAlpha = alpha * 0.76;
    ctx.strokeStyle = "rgba(255, 245, 203, 0.62)";
    ctx.lineWidth = 1.55 + 0.55 * phase.pulse;
    ctx.beginPath();
    ctx.arc(endpoint.x, endpoint.y, 7.2 + 1.6 * phase.pulse, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function drawFinalThirdOutcomeZone(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment | HighBypassMoment,
  sequence: (MomentZeroMoment | HighBypassMoment)["outcome_sequence"],
  phase: { outcome: number; resetFade: number; pulse: number },
  progress: number
) {
  if (sequence.final_third_status !== "PASS") return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const direction = outcomeAttackingDirection(moment);
  const threshold = sequence.final_third_threshold_normalized_x_m ?? replay.pitch.length_m / 6;
  const boundaryX = direction === 1 ? threshold : -threshold;
  const boundary = pitchPointToPixel(boundaryX, 0, replay.pitch, layout).x;
  const left = direction === 1 ? boundary : layout.marginX;
  const right = direction === 1 ? layout.marginX + layout.fieldWidth : boundary;
  const width = Math.max(0, right - left);
  if (width <= 0) return;
  const outcomeAlpha = Math.max(phase.outcome, progress * 0.64) * phase.resetFade;
  const goalSide = direction === 1 ? right : left;
  const gradient = ctx.createLinearGradient(boundary, 0, goalSide, 0);
  gradient.addColorStop(0, "rgba(255, 245, 203, 0)");
  gradient.addColorStop(0.36, "rgba(255, 245, 203, 0.055)");
  gradient.addColorStop(1, "rgba(255, 245, 203, 0.16)");

  ctx.save();
  ctx.globalAlpha = outcomeAlpha;
  ctx.fillStyle = gradient;
  ctx.fillRect(left, layout.marginY, width, layout.fieldHeight);
  ctx.globalAlpha = outcomeAlpha * (0.36 + 0.18 * phase.pulse);
  ctx.strokeStyle = "rgba(255, 245, 203, 0.46)";
  ctx.lineWidth = 1.25;
  ctx.beginPath();
  ctx.moveTo(boundary, layout.marginY);
  ctx.lineTo(boundary, layout.marginY + layout.fieldHeight);
  ctx.stroke();
  ctx.restore();
}

function outcomeAttackingDirection(moment: MomentZeroMoment | HighBypassMoment) {
  if ("attacking_direction" in moment) return moment.attacking_direction;
  return moment.support_region.attacking_direction;
}

function drawBall(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  const ballFrameId = momentZeroBallEvidenceFrameId(moment, frame.frame_id);
  const ballFrame = replay.frames.find((item) => item.frame_id === ballFrameId) ?? frame;
  const ball = ballFrame.entities.find((entity) => entity.entity_type === "ball");
  if (!ball) return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const point = pitchPointToPixel(ball.x_m, ball.y_m, replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = phase.resetFade;
  const receptionSettled = frame.frame_id >= moment.reception_frame_id;
  if (receptionSettled) {
    const dock = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, 16 + 4 * phase.support);
    dock.addColorStop(0, "rgba(244, 239, 224, 0.22)");
    dock.addColorStop(1, "rgba(244, 239, 224, 0)");
    ctx.fillStyle = dock;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 16 + 4 * phase.support, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.beginPath();
  ctx.arc(point.x, point.y, receptionSettled ? 5.2 : 4.6, 0, Math.PI * 2);
  ctx.fillStyle = PITCH_PALETTE.ball;
  ctx.fill();
  ctx.restore();
}

function highBypassPhase(progress: number) {
  return {
    setup: fadeWindow(progress, 0.02, 0.18),
    pass: fadeWindow(progress, 0.16, 0.55),
    bypass: fadeWindow(progress, 0.43, 0.82),
    settle: fadeWindow(progress, 0.72, 0.94),
    reception: fadeWindow(progress, 0.50, 0.70),
    outcome: fadeWindow(progress, 0.74, 0.94),
    resetFade: 1 - fadeWindow(progress, 0.94, 1),
    pulse: 0.5 + 0.5 * Math.sin(progress * Math.PI * 2)
  };
}

function drawHighBypassAttackingEndCue(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: HighBypassMoment,
  layout: ReturnType<typeof layoutPitch>,
  phase: ReturnType<typeof highBypassPhase>
) {
  const attackingLeft = moment.attacking_direction === -1;
  const goalX = attackingLeft ? layout.marginX : layout.marginX + layout.fieldWidth;
  const goalMouthWidthM = 7.32;
  const goalHalf = (goalMouthWidthM / 2) * layout.scalePxPerM;
  const center = pitchPointToPixel(attackingLeft ? -replay.pitch.length_m / 2 : replay.pitch.length_m / 2, 0, replay.pitch, layout);
  const outside = attackingLeft ? -1 : 1;
  ctx.save();
  ctx.globalAlpha = (0.18 + 0.10 * phase.pass) * phase.resetFade;
  ctx.strokeStyle = "rgba(240, 239, 225, 0.34)";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(goalX, center.y - goalHalf);
  ctx.lineTo(goalX + outside * 12, center.y - goalHalf);
  ctx.lineTo(goalX + outside * 12, center.y + goalHalf);
  ctx.lineTo(goalX, center.y + goalHalf);
  ctx.stroke();
  ctx.restore();
}

function drawHighBypassVignette(
  ctx: CanvasRenderingContext2D,
  layout: ReturnType<typeof layoutPitch>,
  moment: HighBypassMoment,
  replay: ReplayPayload,
  phase: ReturnType<typeof highBypassPhase>
) {
  const start = pitchPointToPixel(moment.release_ball_point.x_m, moment.release_ball_point.y_m, replay.pitch, layout);
  const end = pitchPointToPixel(moment.reception_ball_point.x_m, moment.reception_ball_point.y_m, replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = (0.05 + 0.12 * phase.bypass) * phase.resetFade;
  const gradient = ctx.createRadialGradient(end.x, end.y, layout.fieldHeight * 0.08, start.x, start.y, layout.fieldHeight * 0.82);
  gradient.addColorStop(0, "rgba(242, 229, 189, 0.12)");
  gradient.addColorStop(0.52, "rgba(3, 13, 10, 0.04)");
  gradient.addColorStop(1, "rgba(3, 13, 10, 0.70)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, layout.canvasWidth, layout.canvasHeight);
  ctx.restore();
}

function drawHighBypassPlayers(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: HighBypassMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof highBypassPhase>
) {
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const bypassedIds = new Set<string>(moment.bypassed_player_ids);
  for (const entity of frame.entities) {
    if (entity.entity_type === "ball") continue;
    const point = pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout);
    const isAttack = entity.team_role === moment.perspective_team_role;
    const isPasser = entity.entity_id === moment.passer_id;
    const isReceiver = entity.entity_id === moment.receiver_id;
    const isBypassed = bypassedIds.has(entity.entity_id);
    const isStory = isPasser || isReceiver || isBypassed;
    const radius = isReceiver ? 7.8 : isPasser ? 6.8 : isBypassed ? 5.9 : 4.2;
    const alpha = isBypassed ? 0.78 - 0.18 * phase.bypass : isStory ? 0.98 : 0.54 - 0.06 * phase.bypass;
    ctx.save();
    ctx.globalAlpha = Math.max(0.12, alpha) * phase.resetFade;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = isAttack ? PITCH_PALETTE.attack : PITCH_PALETTE.defense;
    ctx.strokeStyle = isAttack ? PITCH_PALETTE.attackEdge : PITCH_PALETTE.defenseEdge;
    ctx.lineWidth = isStory ? 1.8 : 1.05;
    ctx.fill();
    ctx.stroke();
    ctx.globalAlpha = Math.max(0.10, alpha * (isAttack ? 0.44 : 0.58)) * phase.resetFade;
    ctx.fillStyle = isAttack ? PITCH_PALETTE.attackCore : PITCH_PALETTE.defenseCore;
    ctx.beginPath();
    ctx.arc(point.x, point.y, Math.max(1.7, radius * 0.34), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

function drawHighBypassPath(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: HighBypassMoment,
  phase: ReturnType<typeof highBypassPhase>
) {
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const observedPoints = replay.frames
    .filter((frame) => frame.frame_id >= moment.release_frame_id && frame.frame_id <= moment.reception_frame_id)
    .map((frame) => frame.entities.find((entity) => entity.entity_type === "ball"))
    .filter((entity): entity is ReplayEntity => Boolean(entity))
    .map((entity) => pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout));
  const fallbackPoints = [
    pitchPointToPixel(moment.release_ball_point.x_m, moment.release_ball_point.y_m, replay.pitch, layout),
    pitchPointToPixel(moment.reception_ball_point.x_m, moment.reception_ball_point.y_m, replay.pitch, layout),
  ];
  const points = observedPoints.length >= 2 ? observedPoints : fallbackPoints;
  const visibleCount = Math.max(2, Math.round(points.length * phase.pass));
  ctx.save();
  ctx.globalAlpha = phase.pass * phase.resetFade;
  ctx.strokeStyle = PITCH_PALETTE.pass;
  ctx.shadowColor = "rgba(242, 229, 189, 0.18)";
  ctx.shadowBlur = 10 + 8 * phase.bypass;
  ctx.lineWidth = 3.6;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  points.slice(0, visibleCount).forEach((point, index) => {
    if (index === 0) ctx.moveTo(point.x, point.y);
    else ctx.lineTo(point.x, point.y);
  });
  ctx.stroke();
  const end = pitchPointToPixel(moment.reception_ball_point.x_m, moment.reception_ball_point.y_m, replay.pitch, layout);
  ctx.globalAlpha = phase.bypass * phase.resetFade;
  const endHalo = ctx.createRadialGradient(end.x, end.y, 0, end.x, end.y, 35 + 10 * phase.pulse);
  endHalo.addColorStop(0, "rgba(255, 245, 203, 0.30)");
  endHalo.addColorStop(0.48, "rgba(255, 245, 203, 0.11)");
  endHalo.addColorStop(1, "rgba(255, 245, 203, 0)");
  ctx.fillStyle = endHalo;
  ctx.beginPath();
  ctx.arc(end.x, end.y, 35 + 10 * phase.pulse, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawBypassedOpponents(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: HighBypassMoment,
  phase: ReturnType<typeof highBypassPhase>
) {
  const receptionFrame = replay.frames.find((frame) => frame.frame_id === moment.reception_frame_id);
  if (!receptionFrame) return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const bypassedIds = new Set<string>(moment.bypassed_player_ids);
  const entities = receptionFrame.entities
    .filter((entity) => bypassedIds.has(entity.entity_id))
    .sort((left, right) => {
      const xOrder = moment.attacking_direction === -1 ? right.x_m - left.x_m : left.x_m - right.x_m;
      return xOrder || left.y_m - right.y_m;
    });
  if (entities.length === 0) return;
  ctx.save();
  const revealAmount = phase.bypass * (entities.length + 0.65);
  for (const [index, entity] of entities.entries()) {
    const localReveal = clamp01(revealAmount - index);
    if (localReveal <= 0) continue;
    const point = pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout);
    const isCurrent = localReveal < 1;
    const impact = isCurrent ? 1 : 0.45;
    const haloRadius = 15 + 9 * localReveal + 7 * impact * phase.pulse;
    const halo = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, haloRadius);
    halo.addColorStop(0, `rgba(228, 207, 130, ${0.16 + 0.15 * localReveal})`);
    halo.addColorStop(1, "rgba(228, 207, 130, 0)");
    ctx.globalAlpha = localReveal * phase.resetFade;
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(point.x, point.y, haloRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = `rgba(228, 207, 130, ${0.42 + 0.34 * localReveal})`;
    ctx.lineWidth = 1.35 + 0.85 * localReveal + 0.55 * impact * phase.pulse;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 7.4 + 2.4 * localReveal + 1.2 * impact * phase.pulse, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function drawHighBypassBall(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: HighBypassMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof highBypassPhase>
) {
  const ballFrameId = frame.frame_id > moment.outcome_sequence.end_frame_id ? moment.outcome_sequence.end_frame_id : frame.frame_id;
  const ballFrame = replay.frames.find((item) => item.frame_id === ballFrameId) ?? frame;
  const ball = ballFrame.entities.find((entity) => entity.entity_type === "ball");
  if (!ball) return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const point = pitchPointToPixel(ball.x_m, ball.y_m, replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = phase.resetFade;
  const receptionSettled = frame.frame_id >= moment.reception_frame_id;
  if (receptionSettled) {
    const dock = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, 18 + 5 * phase.bypass);
    dock.addColorStop(0, "rgba(244, 239, 224, 0.24)");
    dock.addColorStop(1, "rgba(244, 239, 224, 0)");
    ctx.fillStyle = dock;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 18 + 5 * phase.bypass, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.beginPath();
  ctx.arc(point.x, point.y, receptionSettled ? 5.3 : 4.6, 0, Math.PI * 2);
  ctx.fillStyle = PITCH_PALETTE.ball;
  ctx.fill();
  ctx.restore();
}

function fadeWindow(value: number, start: number, end: number) {
  if (value <= start) return 0;
  if (value >= end) return 1;
  return easeOutCubic((value - start) / (end - start));
}

function easeOutCubic(value: number) {
  return 1 - Math.pow(1 - value, 3);
}

function easeInOutCubic(value: number) {
  return value < 0.5 ? 4 * value * value * value : 1 - Math.pow(-2 * value + 2, 3) / 2;
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value));
}
