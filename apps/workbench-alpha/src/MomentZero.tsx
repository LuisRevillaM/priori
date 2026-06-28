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
  supportFill: "rgba(214, 193, 122, 0.20)",
  supportVoid: "rgba(249, 246, 220, 0.08)",
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
  drawPlayers(ctx, replay, moment, frame, phase);
  drawDefensiveLine(ctx, replay, moment, frame, phase);
  drawPassPath(ctx, replay, moment, phase);
  drawSupportRegion(ctx, replay, moment, phase);
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
    resetFade: 1 - fadeWindow(progress, 0.94, 1)
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

function drawPlayers(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: MomentZeroMoment,
  frame: ReplayPayload["frames"][number],
  phase: ReturnType<typeof revealPhase>
) {
  for (const entity of frame.entities) {
    if (entity.entity_type === "ball") continue;
    const point = pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layoutPitch(replay.pitch, ctx.canvas.clientWidth));
    const isReceiver = entity.entity_id === moment.receiver_id;
    const isPasser = entity.entity_id === moment.passer_id;
    const isDefender = moment.defensive_line_player_ids.includes(entity.entity_id);
    const radius = isReceiver ? 7.8 : isPasser ? 6.8 : isDefender ? 6.6 : 5.2;
    ctx.save();
    ctx.globalAlpha = (isReceiver || isPasser || isDefender ? 0.95 : 0.46) * phase.resetFade;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = entity.team_role === moment.perspective_team_role ? PITCH_PALETTE.home : PITCH_PALETTE.away;
    ctx.strokeStyle = entity.team_role === moment.perspective_team_role ? PITCH_PALETTE.homeEdge : PITCH_PALETTE.awayEdge;
    ctx.lineWidth = isReceiver || isDefender ? 1.8 : 1.1;
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
    ctx.beginPath();
    ctx.arc(point.x, point.y, 11 + 2 * phase.break, 0, Math.PI * 2);
    ctx.strokeStyle = PITCH_PALETTE.lineBreak;
    ctx.lineWidth = 1.8;
    ctx.stroke();
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

  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  ctx.arc(reference.x, reference.y, radius, 0, Math.PI * 2);
  ctx.clip();
  ctx.fillStyle = PITCH_PALETTE.supportFill;
  ctx.fillRect(
    behindToLeft ? reference.x - radius : reference.x,
    reference.y - radius,
    radius,
    radius * 2
  );
  ctx.restore();

  ctx.save();
  ctx.globalAlpha = alpha * (0.7 + 0.3 * phase.lonely);
  ctx.strokeStyle = PITCH_PALETTE.support;
  ctx.lineWidth = 1.8;
  ctx.setLineDash([7, 7]);
  ctx.beginPath();
  if (behindToLeft) {
    ctx.arc(reference.x, reference.y, radius, Math.PI / 2, Math.PI * 1.5);
  } else {
    ctx.arc(reference.x, reference.y, radius, -Math.PI / 2, Math.PI / 2);
  }
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = PITCH_PALETTE.supportVoid;
  ctx.beginPath();
  ctx.arc(reference.x, reference.y, radius * 0.48, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
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
  ctx.globalAlpha = Math.max(phase.break, phase.lonely) * phase.resetFade;
  ctx.strokeStyle = PITCH_PALETTE.receiver;
  ctx.lineWidth = 2.6;
  ctx.beginPath();
  ctx.arc(point.x, point.y, 15 + 8 * phase.lonely, 0, Math.PI * 2);
  ctx.stroke();
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
