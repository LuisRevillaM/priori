import { useEffect, useRef } from "react";
import type { ReplayPayload, ResultRow } from "./types";
import { layoutPitch, pitchPointToPixel } from "./pitchGeometry";
import { overlayVisibleAtFrame, type CorridorOverlay } from "./overlay";

// Replay canvas palette (canvas 2D fills/strokes — not CSS tokens). Named for legibility; values
// match the established warm-pitch look.
const PITCH = {
  grass: "#477556",
  line: "rgba(255,255,255,0.84)",
  label: "rgba(245,245,240,0.82)",
  labelDim: "rgba(245,245,240,0.78)",
  ball: "#f4f1e8",
  ballEdge: "#2b2f2b",
  home: "#1e4f7a",
  homeEdge: "#e7edf2",
  away: "#a9473f",
  awayEdge: "#f3e8df",
  corridor: "#f1d27a",
  corridorFill: "#fff7d2",
  anchorRing: "#d6b35a"
} as const;

type PitchCanvasProps = {
  replay: ReplayPayload | null;
  frameIndex: number;
  result?: ResultRow | null;
  overlay?: CorridorOverlay;
};

export function PitchCanvas({ replay, frameIndex, result, overlay }: PitchCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const parent = canvas.parentElement;
    const pitch = replay?.pitch ?? { length_m: 105, width_m: 68 };
    const layout = layoutPitch(pitch, parent?.clientWidth);
    const width = layout.canvasWidth;
    const height = layout.canvasHeight;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    ctx.fillStyle = PITCH.grass;
    ctx.fillRect(0, 0, width, height);

    const marginX = layout.marginX;
    const marginY = layout.marginY;
    const fieldW = layout.fieldWidth;
    const fieldH = layout.fieldHeight;

    ctx.strokeStyle = PITCH.line;
    ctx.lineWidth = 1.6;
    ctx.strokeRect(marginX, marginY, fieldW, fieldH);
    ctx.beginPath();
    ctx.moveTo(width / 2, marginY);
    ctx.lineTo(width / 2, height - marginY);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(width / 2, height / 2, Math.min(fieldW, fieldH) * 0.12, 0, Math.PI * 2);
    ctx.stroke();

    if (!replay || replay.frames.length === 0) {
      ctx.fillStyle = PITCH.labelDim;
      ctx.font = "14px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.fillText("No replay window loaded", marginX + 16, marginY + 28);
      return;
    }

    const frame = replay.frames[Math.min(Math.max(frameIndex, 0), replay.frames.length - 1)];
    ctx.fillStyle = PITCH.label;
    ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText(
      `${replay.replay_window_id} / frame ${frame.frame_id} / ${frameIndex + 1} of ${replay.frames.length}`,
      marginX + 14,
      marginY + 24
    );

    for (const entity of frame.entities) {
      const point = pitchPointToPixel(entity.x_m, entity.y_m, replay.pitch, layout);
      const isBall = entity.entity_type === "ball";
      const radius = isBall ? 4.4 : 7.5;
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      if (isBall) {
        ctx.fillStyle = PITCH.ball;
        ctx.strokeStyle = PITCH.ballEdge;
      } else if (entity.team_role === "home") {
        ctx.fillStyle = PITCH.home;
        ctx.strokeStyle = PITCH.homeEdge;
      } else {
        ctx.fillStyle = PITCH.away;
        ctx.strokeStyle = PITCH.awayEdge;
      }
      ctx.lineWidth = isBall ? 1.2 : 1.5;
      ctx.fill();
      ctx.stroke();
    }

    const evidence = result?.requested_evidence ?? {};
    const ball = frame.entities.find((entity) => entity.entity_type === "ball");
    // Draw the corridor only inside its valid evidence interval (or at the witness frame). Never
    // infer geometry: if the overlay state is "none" or the frame is outside the interval, hide it.
    const overlayTargetId =
      overlay && overlay.kind !== "none" ? overlay.targetPlayerId : typeof evidence.target_player_id === "string" ? evidence.target_player_id : null;
    const target = overlayTargetId
      ? frame.entities.find((entity) => entity.entity_id === overlayTargetId)
      : null;
    const overlayVisible = overlay ? overlayVisibleAtFrame(overlay, frame.frame_id) : frame.frame_id === Number(replay.anchor_frame_id);
    if (ball && target && overlayVisible) {
      const start = pitchPointToPixel(ball.x_m, ball.y_m, replay.pitch, layout);
      const end = pitchPointToPixel(target.x_m, target.y_m, replay.pitch, layout);
      ctx.save();
      ctx.strokeStyle = PITCH.corridor;
      ctx.fillStyle = PITCH.corridorFill;
      ctx.lineWidth = 3;
      ctx.setLineDash([8, 5]);
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(end.x, end.y, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = PITCH.corridor;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.fillText("target", end.x + 12, end.y - 10);
      ctx.restore();
    }

    const anchorX = replay.frames.findIndex((item) => item.frame_id === replay.anchor_frame_id);
    if (anchorX >= 0 && anchorX === frameIndex) {
      ctx.strokeStyle = PITCH.anchorRing;
      ctx.lineWidth = 2;
      ctx.strokeRect(marginX + 6, marginY + 6, fieldW - 12, fieldH - 12);
    }
  }, [frameIndex, replay, result]);

  return (
    <div className="canvasShell">
      <canvas ref={canvasRef} aria-label="Coordinate replay canvas" />
    </div>
  );
}
