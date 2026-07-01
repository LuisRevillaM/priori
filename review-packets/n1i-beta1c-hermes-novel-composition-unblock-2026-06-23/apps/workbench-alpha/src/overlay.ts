// Pure corridor-overlay geometry/validity helpers. Kept framework-free so the timing and legend
// logic is unit-tested (tests/overlay.test.ts). The overlay uses EXACT evidence geometry only:
// it shows a corridor across a valid open/close interval when those frames exist, falls back to a
// clearly-labeled witness-frame-only overlay when only witness geometry exists, and otherwise hides
// rather than inferring missing geometry.
import type { ReplayPayload } from "./types";

export type CorridorOverlay =
  | {
      kind: "interval";
      targetPlayerId: string;
      openFrameId: number;
      closeFrameId: number;
      clearanceM: number | null;
      limitingDefenderId: string | null;
    }
  | { kind: "witness"; targetPlayerId: string; witnessFrameId: number; clearanceM: number | null }
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

export function corridorOverlayState(
  evidence: Record<string, unknown> | null | undefined,
  replay: ReplayPayload | null
): CorridorOverlay {
  if (!evidence || !replay || replay.frames.length === 0) {
    return { kind: "none", reason: "No selected result overlay" };
  }
  const targetPlayerId = evidenceString(evidence, ["target_player_id"]);
  if (!targetPlayerId) return { kind: "none", reason: "No exact corridor witness available" };

  const clearanceM = evidenceNumber(evidence, ["minimum_clearance_m", "corridor_minimum_clearance_m", "clearance_m"]);
  const limitingDefenderId = evidenceString(evidence, ["limiting_defender_id"]);
  const openFrameId = evidenceNumber(evidence, ["relation_open_frame_id", "open_confirm_frame_id", "open_frame_id"]);
  const closeFrameId = evidenceNumber(evidence, ["relation_close_frame_id", "close_frame_id"]);
  const frameIds = replay.frames.map((frame) => frame.frame_id);

  if (
    openFrameId !== null &&
    closeFrameId !== null &&
    closeFrameId >= openFrameId &&
    frameIds.some((frameId) => frameId >= openFrameId && frameId <= closeFrameId)
  ) {
    return { kind: "interval", targetPlayerId, openFrameId, closeFrameId, clearanceM, limitingDefenderId };
  }

  const witnessFrameId = Number(replay.anchor_frame_id);
  if (Number.isFinite(witnessFrameId) && frameIds.includes(witnessFrameId)) {
    return { kind: "witness", targetPlayerId, witnessFrameId, clearanceM };
  }
  return { kind: "none", reason: "No exact corridor witness available" };
}

export function overlayVisibleAtFrame(state: CorridorOverlay, frameId: number | null | undefined): boolean {
  if (frameId === null || frameId === undefined) return false;
  if (state.kind === "interval") return frameId >= state.openFrameId && frameId <= state.closeFrameId;
  if (state.kind === "witness") return frameId === state.witnessFrameId;
  return false;
}

// Keeps the existing overlay-proof strings ("Witness-frame corridor", "No exact corridor witness
// available") so the proof remains stable, and adds honest interval phrasing.
export function overlayProofText(state: CorridorOverlay, frameId: number | null | undefined): string {
  if (state.kind === "none") return state.reason;
  if (overlayVisibleAtFrame(state, frameId)) {
    return state.kind === "interval"
      ? "Corridor visible: ball to target within the valid interval"
      : "Witness-frame corridor: ball to selected receiver";
  }
  return state.kind === "interval"
    ? "Corridor hidden outside its valid interval"
    : "Corridor witness hidden outside the witness frame";
}

const NON_OPTIMALITY =
  "A geometric corridor is a sufficiently clear forward connection from the ball to a teammate. It does not establish that this was the optimal pass.";

export function overlayLegendLines(state: CorridorOverlay): string[] {
  const lines: string[] = [];
  if (state.kind === "witness") {
    lines.push("Witness-frame corridor — exact geometry exists only at the witness frame, so it is shown there only.");
    lines.push(`Target receiver: ${state.targetPlayerId}.`);
    if (state.clearanceM !== null) lines.push(`Minimum clearance to the nearest defender: ${state.clearanceM} m.`);
  } else if (state.kind === "interval") {
    lines.push(`Corridor visible from frame ${state.openFrameId} to ${state.closeFrameId}; hidden outside that interval.`);
    lines.push(`Target receiver: ${state.targetPlayerId}.`);
    if (state.clearanceM !== null) lines.push(`Minimum clearance: ${state.clearanceM} m.`);
    if (state.limitingDefenderId) lines.push(`Limiting defender: ${state.limitingDefenderId}.`);
  }
  lines.push(NON_OPTIMALITY);
  return lines;
}
