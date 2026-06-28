import { useEffect, useRef } from "react";
import momentZeroPayload from "./generated/moment-zero.json";
import { layoutPitch, pitchPointToPixel } from "./pitchGeometry";
import type { ReplayEntity, ReplayPayload } from "./types";

type MomentZeroPayload = typeof momentZeroPayload;
type MomentZeroMoment = MomentZeroPayload["moment"];

const PITCH_PALETTE = {
  turf: "#132f24",
  turf2: "#193d2e",
  line: "rgba(240, 239, 225, 0.50)",
  lineSoft: "rgba(240, 239, 225, 0.20)",
  home: "#d8efe3",
  homeEdge: "#163327",
  away: "#8d534c",
  awayEdge: "#f4ece0",
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

function MomentZeroPitch({ payload }: { payload: MomentZeroPayload }) {
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

  const frame = frameForProgress(replay, progress);
  const phase = revealPhase(progress);
  drawPitch(ctx, layout);
  drawAttackingEndCue(ctx, replay, moment, layout, phase);
  drawMomentVignette(ctx, layout, phase);
  drawPlayers(ctx, replay, moment, frame, phase);
  drawDefensiveLine(ctx, replay, moment, frame, phase);
  drawPassPath(ctx, replay, moment, phase);
  drawSupportRegion(ctx, replay, moment, phase);
  drawNearestSupportDistance(ctx, replay, moment, frame, phase);
  drawReceiverFocus(ctx, replay, moment, frame, phase);
  drawBall(ctx, replay, frame, phase);
}

function frameForProgress(replay: ReplayPayload, progress: number) {
  const eased = easeInOutCubic(Math.min(1, progress / 0.72));
  const index = Math.min(replay.frames.length - 1, Math.max(0, Math.round(eased * (replay.frames.length - 1))));
  return replay.frames[index];
}

function revealPhase(progress: number) {
  return {
    setup: fadeWindow(progress, 0.02, 0.18),
    line: fadeWindow(progress, 0.10, 0.28),
    pass: fadeWindow(progress, 0.18, 0.55),
    break: fadeWindow(progress, 0.42, 0.66),
    support: fadeWindow(progress, 0.58, 0.78),
    lonely: fadeWindow(progress, 0.76, 0.95),
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
  const candidateIds = new Set(moment.support_region.candidate_player_ids);
  for (const entity of frame.entities) {
    if (entity.entity_type === "ball") continue;
    const point = pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout);
    const isReceiver = entity.entity_id === moment.receiver_id;
    const isPasser = entity.entity_id === moment.passer_id;
    const isDefender = moment.defensive_line_player_ids.includes(entity.entity_id);
    const isCandidate = candidateIds.has(entity.entity_id);
    const isStory = isReceiver || isPasser || isDefender;
    const fadeIrrelevant = Math.max(phase.break, phase.support, phase.lonely);
    const radius = isReceiver ? 7.9 : isPasser ? 6.6 : isDefender ? 6.2 : isCandidate ? 4.8 : 4.2;
    const alpha = isStory
      ? 0.96
      : isCandidate
        ? 0.46 - 0.06 * fadeIrrelevant
        : 0.36 - 0.04 * fadeIrrelevant;
    ctx.save();
    ctx.globalAlpha = Math.max(0.08, alpha) * phase.resetFade;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = entity.team_role === moment.perspective_team_role ? PITCH_PALETTE.home : PITCH_PALETTE.away;
    ctx.strokeStyle = entity.team_role === moment.perspective_team_role ? PITCH_PALETTE.homeEdge : PITCH_PALETTE.awayEdge;
    ctx.lineWidth = isStory ? 1.5 : 0.8;
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }
}

function drawDefensiveLine(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const top = pitchPointToPixel(moment.line_x_m, replay.pitch.width_m / 2, replay.pitch, layout);
  const bottom = pitchPointToPixel(moment.line_x_m, -replay.pitch.width_m / 2, replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = (0.28 + 0.62 * phase.line) * phase.resetFade;
  ctx.strokeStyle = PITCH_PALETTE.lineBreak;
  ctx.lineWidth = 2.2 + 1.6 * phase.break;
  ctx.setLineDash([12, 10]);
  ctx.beginPath();
  ctx.moveTo(top.x, top.y);
  ctx.quadraticCurveTo(top.x + 6 * phase.break, (top.y + bottom.y) / 2, bottom.x, bottom.y);
  ctx.stroke();
  ctx.setLineDash([]);
  for (const id of moment.defensive_line_player_ids) {
    const entity = frame.entities.find((item) => item.entity_id === id);
    if (!entity) continue;
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

  ctx.save();
  ctx.globalAlpha = alpha * (0.64 + 0.34 * phase.lonely);
  ctx.beginPath();
  ctx.arc(reference.x, reference.y, radius, 0, Math.PI * 2);
  ctx.clip();
  ctx.shadowColor = "rgba(214, 193, 122, 0.46)";
  ctx.shadowBlur = 18 + 18 * phase.lonely;
  const glow = ctx.createRadialGradient(reference.x, reference.y, radius * 0.08, reference.x, reference.y, radius * (1.18 + 0.08 * phase.lonely));
  glow.addColorStop(0, PITCH_PALETTE.supportVoid);
  glow.addColorStop(0.48, PITCH_PALETTE.supportFill);
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

  ctx.globalAlpha = alpha * phase.lonely * 0.95;
  const voidGradient = ctx.createRadialGradient(reference.x, reference.y, radius * 0.08, reference.x, reference.y, radius * 0.62);
  voidGradient.addColorStop(0, "rgba(249, 246, 220, 0.16)");
  voidGradient.addColorStop(0.42, "rgba(249, 246, 220, 0.08)");
  voidGradient.addColorStop(1, "rgba(249, 246, 220, 0)");
  ctx.fillStyle = PITCH_PALETTE.supportVoid;
  ctx.beginPath();
  ctx.arc((left + right) / 2, reference.y, radius * 0.58, 0, Math.PI * 2);
  ctx.fillStyle = voidGradient;
  ctx.fill();
  ctx.restore();
}

function drawNearestSupportDistance(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  const alpha = phase.lonely * phase.resetFade;
  if (alpha <= 0) return;
  const receiver = frame.entities.find((entity) => entity.entity_id === moment.receiver_id);
  if (!receiver) return;
  const nearest = nearestCandidate(frame.entities, moment, receiver);
  if (!nearest) return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const receiverPoint = pitchPointToPixel(receiver.x_m, receiver.y_m, replay.pitch, layout);
  const nearestPoint = pitchPointToPixel(nearest.x_m, nearest.y_m, replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = alpha * 0.36;
  ctx.strokeStyle = "rgba(245, 241, 222, 0.42)";
  ctx.lineWidth = 1.1;
  ctx.setLineDash([2, 9]);
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(receiverPoint.x, receiverPoint.y);
  ctx.lineTo(nearestPoint.x, nearestPoint.y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = alpha * 0.55;
  ctx.fillStyle = PITCH_PALETTE.home;
  ctx.beginPath();
  ctx.arc(nearestPoint.x, nearestPoint.y, 3.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function nearestCandidate(
  entities: ReplayPayload["frames"][number]["entities"],
  moment: MomentZeroMoment,
  receiver: ReplayEntity
) {
  const candidateIds = new Set(moment.support_region.candidate_player_ids);
  let nearest: ReplayEntity | null = null;
  let nearestDistance = Number.POSITIVE_INFINITY;
  for (const entity of entities) {
    if (entity.entity_type === "ball" || entity.entity_id === receiver.entity_id || !candidateIds.has(entity.entity_id)) {
      continue;
    }
    const distance = Math.hypot(entity.x_m - receiver.x_m, entity.y_m - receiver.y_m);
    if (distance < nearestDistance) {
      nearest = entity;
      nearestDistance = distance;
    }
  }
  return nearest;
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

function drawBall(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  const ball = frame.entities.find((entity) => entity.entity_type === "ball");
  if (!ball) return;
  const layout = layoutPitch(replay.pitch, ctx.canvas.clientWidth);
  const point = pitchPointToPixel(ball.x_m, ball.y_m, replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = phase.resetFade;
  ctx.beginPath();
  ctx.arc(point.x, point.y, 4.6, 0, Math.PI * 2);
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
