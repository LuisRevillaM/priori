// Exact completed-pass overlay helpers. This is separate from corridor overlays because the
// semantics are different: a high-bypass result is an observed completed pass, not a suggested lane.
import type { ReplayPayload } from "./types";

export type PitchPoint = { x_m: number; y_m: number };

export type PassOverlay =
  | {
      kind: "completed_pass";
      releaseFrameId: number;
      receptionFrameId: number;
      releaseBallPoint: PitchPoint;
      receptionBallPoint: PitchPoint;
      passerId: string | null;
      receiverId: string | null;
      bypassedPlayerIds: string[];
      opponentsBypassedCount: number | null;
      forwardProgressionM: number | null;
    }
  | { kind: "none"; reason: string };

function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function findEvidenceKey(evidence: Record<string, unknown>, names: string[]): string | null {
  for (const key of Object.keys(evidence)) {
    for (const name of names) {
      if (key === name || key.endsWith(`.${name}`)) return key;
    }
  }
  return null;
}

function evidenceNumber(evidence: Record<string, unknown>, names: string[]): number | null {
  const key = findEvidenceKey(evidence, names);
  return key ? numericValue(evidence[key]) : null;
}

function evidenceString(evidence: Record<string, unknown>, names: string[]): string | null {
  const key = findEvidenceKey(evidence, names);
  const value = key ? evidence[key] : null;
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function evidenceStringList(evidence: Record<string, unknown>, names: string[]): string[] {
  const key = findEvidenceKey(evidence, names);
  const value = key ? evidence[key] : null;
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim() !== "");
}

function evidencePoint(evidence: Record<string, unknown>, names: string[]): PitchPoint | null {
  const key = findEvidenceKey(evidence, names);
  const value = key ? evidence[key] : null;
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  const x = numericValue(record.x_m);
  const y = numericValue(record.y_m);
  if (x === null || y === null) return null;
  return { x_m: x, y_m: y };
}

export function passOverlayState(
  evidence: Record<string, unknown> | null | undefined,
  replay: ReplayPayload | null
): PassOverlay {
  if (!evidence || !replay || replay.frames.length === 0) {
    return { kind: "none", reason: "No completed-pass evidence selected" };
  }
  const releaseFrameId = evidenceNumber(evidence, ["release_frame_id"]);
  const receptionFrameId = evidenceNumber(evidence, ["reception_frame_id"]);
  const releaseBallPoint = evidencePoint(evidence, ["release_ball_point"]);
  const receptionBallPoint = evidencePoint(evidence, ["reception_ball_point"]);
  if (
    releaseFrameId === null ||
    receptionFrameId === null ||
    receptionFrameId < releaseFrameId ||
    !releaseBallPoint ||
    !receptionBallPoint
  ) {
    return { kind: "none", reason: "No exact completed-pass geometry available" };
  }
  const frameIds = replay.frames.map((frame) => frame.frame_id);
  if (!frameIds.some((frameId) => frameId >= releaseFrameId && frameId <= receptionFrameId)) {
    return { kind: "none", reason: "Completed-pass frames are outside this replay window" };
  }
  return {
    kind: "completed_pass",
    releaseFrameId,
    receptionFrameId,
    releaseBallPoint,
    receptionBallPoint,
    passerId: evidenceString(evidence, ["passer_id"]),
    receiverId: evidenceString(evidence, ["receiver_id"]),
    bypassedPlayerIds: evidenceStringList(evidence, ["bypassed_player_ids"]),
    opponentsBypassedCount: evidenceNumber(evidence, ["opponents_bypassed_count", "bypassed_opponents_count"]),
    forwardProgressionM: evidenceNumber(evidence, ["forward_progression_m", "pass_forward_progression_m"])
  };
}

export function passOverlayVisibleAtFrame(state: PassOverlay, frameId: number | null | undefined): boolean {
  if (state.kind !== "completed_pass" || frameId === null || frameId === undefined) return false;
  return frameId >= state.releaseFrameId && frameId <= state.receptionFrameId;
}

export function passOverlayEndpointVisibleAtFrame(state: PassOverlay, frameId: number | null | undefined): boolean {
  if (state.kind !== "completed_pass" || frameId === null || frameId === undefined) return false;
  return frameId === state.releaseFrameId || frameId === state.receptionFrameId;
}

export function passOverlayProofText(state: PassOverlay, frameId: number | null | undefined): string {
  if (state.kind === "none") return state.reason;
  if (passOverlayVisibleAtFrame(state, frameId)) return "Completed-pass overlay: observed release to controlled reception";
  return "Completed-pass overlay hidden outside the release-to-reception interval";
}

export function passOverlayLegendLines(state: PassOverlay): string[] {
  if (state.kind === "none") return [];
  const lines = [
    `Observed completed pass from frame ${state.releaseFrameId} to ${state.receptionFrameId}.`,
    "Bypassed opponents are highlighted at the controlled-reception frame only."
  ];
  if (state.opponentsBypassedCount !== null) lines.push(`Opponents bypassed: ${state.opponentsBypassedCount}.`);
  if (state.forwardProgressionM !== null) lines.push(`Forward progression: ${state.forwardProgressionM} m.`);
  lines.push("This counts opponent positions relative to the ball; it does not prove which defensive line was broken.");
  return lines;
}
