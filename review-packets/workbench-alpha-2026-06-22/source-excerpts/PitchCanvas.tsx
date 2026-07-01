import { useEffect, useRef } from "react";
import type { ReplayPayload } from "./types";

type PitchCanvasProps = {
  replay: ReplayPayload | null;
  frameIndex: number;
};

function transformPoint(x: number, y: number, replay: ReplayPayload, width: number, height: number) {
  const marginX = width * 0.035;
  const marginY = height * 0.055;
  const fieldW = width - marginX * 2;
  const fieldH = height - marginY * 2;
  return {
    x: marginX + ((x + replay.pitch.length_m / 2) / replay.pitch.length_m) * fieldW,
    y: marginY + ((replay.pitch.width_m / 2 - y) / replay.pitch.width_m) * fieldH
  };
}

export function PitchCanvas({ replay, frameIndex }: PitchCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const parent = canvas.parentElement;
    const width = parent?.clientWidth ? Math.max(parent.clientWidth, 720) : 960;
    const height = Math.round(width * 0.58);
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    ctx.fillStyle = "#477556";
    ctx.fillRect(0, 0, width, height);

    const marginX = width * 0.035;
    const marginY = height * 0.055;
    const fieldW = width - marginX * 2;
    const fieldH = height - marginY * 2;

    ctx.strokeStyle = "rgba(255,255,255,0.84)";
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
      ctx.fillStyle = "rgba(245,245,240,0.78)";
      ctx.font = "14px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.fillText("No replay window loaded", marginX + 16, marginY + 28);
      return;
    }

    const frame = replay.frames[Math.min(Math.max(frameIndex, 0), replay.frames.length - 1)];
    ctx.fillStyle = "rgba(245,245,240,0.82)";
    ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText(
      `${replay.replay_window_id} / frame ${frame.frame_id} / ${frameIndex + 1} of ${replay.frames.length}`,
      marginX + 14,
      marginY + 24
    );

    for (const entity of frame.entities) {
      const point = transformPoint(entity.x_m, entity.y_m, replay, width, height);
      const isBall = entity.entity_type === "ball";
      const radius = isBall ? 4.4 : 7.5;
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      if (isBall) {
        ctx.fillStyle = "#f4f1e8";
        ctx.strokeStyle = "#2b2f2b";
      } else if (entity.team_role === "home") {
        ctx.fillStyle = "#1e4f7a";
        ctx.strokeStyle = "#e7edf2";
      } else {
        ctx.fillStyle = "#a9473f";
        ctx.strokeStyle = "#f3e8df";
      }
      ctx.lineWidth = isBall ? 1.2 : 1.5;
      ctx.fill();
      ctx.stroke();
    }

    const anchorX = replay.frames.findIndex((item) => item.frame_id === replay.anchor_frame_id);
    if (anchorX >= 0 && anchorX === frameIndex) {
      ctx.strokeStyle = "#d6b35a";
      ctx.lineWidth = 2;
      ctx.strokeRect(marginX + 6, marginY + 6, fieldW - 12, fieldH - 12);
    }
  }, [frameIndex, replay]);

  return (
    <div className="canvasShell">
      <canvas ref={canvasRef} aria-label="Coordinate replay canvas" />
    </div>
  );
}
