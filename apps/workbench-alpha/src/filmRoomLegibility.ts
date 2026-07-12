import type { FilmRoomIntervalMetric, FilmRoomMoment, JsonObject, ReplayPayload } from "./types";

export const CLAUSE_KEYS = ["①", "②", "③"] as const;

export type QuestionClauseKey = {
  stage: 1 | 2 | 3;
  key: (typeof CLAUSE_KEYS)[number];
  text: string;
};

export const DEFAULT_SURFACE_SCHEMA_TOKENS = [
  "anchor_frame_id",
  "chain_status",
  "source_node_id",
  "stage_1",
  "stage_2",
  "stage_3"
] as const;

function asRecord(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
}

function asRecords(value: unknown): JsonObject[] {
  return Array.isArray(value) ? value.map(asRecord) : [];
}

function compactNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Math.round(value * 10) / 10);
}

function shortUnit(unit: unknown): string {
  return unit === "metre" || unit === "meter" ? "m" : String(unit ?? "");
}

export function deriveQuestionClauseKeys(expression: unknown): QuestionClauseKey[] {
  const payload = asRecord(expression);
  const clauses = asRecords(payload.meaning_clauses);
  const applications = asRecords(payload.operator_applications);
  const sequence = clauses.find(
    (clause) =>
      clause.subject === "sequence_pattern" &&
      clause.action === "links" &&
      clause.field === "chain_status" &&
      typeof clause.value === "string"
  );
  const threshold = clauses.find(
    (clause) =>
      clause.subject === "stage_2" &&
      clause.action === "requires" &&
      clause.field === "carry_forward_progression_m" &&
      clause.operator === "gte" &&
      typeof clause.value === "number"
  );
  const sequenceApplication = applications.find((application) => application.operator === "sequence_pattern");
  const sequenceParameters = asRecords(sequenceApplication?.parameters);
  const declaredNumericField = sequenceParameters.find(
    (parameter) => parameter.name === "stage_2_minimum_numeric_field"
  )?.value;
  const sequenceValue = typeof sequence?.value === "string" ? sequence.value : "";
  if (
    !sequenceValue.includes("regain") ||
    !sequenceValue.includes("controlled pass") ||
    !threshold ||
    declaredNumericField !== threshold.field
  ) {
    return [];
  }
  const thresholdValue = threshold.value as number;
  return [
    { stage: 1, key: "①", text: "they win the ball back" },
    {
      stage: 2,
      key: "②",
      text: `carry it forward at least ${compactNumber(thresholdValue)} ${shortUnit(threshold.unit)}`
    },
    { stage: 3, key: "③", text: "keep it with a completed pass" }
  ];
}

function matchClock(moment: FilmRoomMoment): string {
  const milliseconds = typeof moment.match_time_ms === "number" ? moment.match_time_ms : null;
  const totalSeconds = milliseconds == null ? moment.anchor_frame_id / 25 : milliseconds / 1000;
  const roundedSeconds = Math.round(totalSeconds);
  const minutes = Math.floor(roundedSeconds / 60);
  const seconds = roundedSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function momentOverlay(moment: FilmRoomMoment, replay?: ReplayPayload | null): JsonObject {
  if (replay && replay.replay_window_id === moment.replay_window_id) {
    const hydrated = asRecord(replay.overlays);
    if (Object.keys(hydrated).length) return hydrated;
  }
  return asRecord(moment.evidence_overlay);
}

function observedCarryMetres(moment: FilmRoomMoment, replay?: ReplayPayload | null): number | null {
  const overlay = momentOverlay(moment, replay);
  const stage = asRecords(overlay.stage_labels).find((label) => label.stage === 2);
  const trail = asRecords(overlay.carry_trails)[0];
  const value = stage?.observed_numeric_value ?? trail?.observed_numeric_value;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function unknownMomentText(moment: FilmRoomMoment): string {
  const reason = String(moment.chain_reason ?? moment.unknown_reason ?? "");
  if (reason === "stage_2_window_truncated") return "couldn't see whether ② happened — half ended";
  if (reason === "stage_3_window_truncated") return "couldn't see whether ③ happened — half ended";
  if (reason === "stage_1_unknown") return "couldn't see whether ① happened — the regain evidence is incomplete";
  if (reason === "stage_2_unknown_candidate") {
    return "couldn't see whether ② happened — the carry evidence is incomplete";
  }
  if (reason === "stage_3_unknown_candidate") {
    return "couldn't see whether ③ happened — the pass evidence is incomplete";
  }
  return "couldn't see whether the whole chain happened — the film evidence is incomplete";
}

export function momentCardText(moment: FilmRoomMoment, replay?: ReplayPayload | null): string {
  if (moment.chain_status === "UNKNOWN") return unknownMomentText(moment);
  const carry = observedCarryMetres(moment, replay);
  const carryText = carry == null ? "watching the carry…" : `+${carry.toFixed(1)} m carry`;
  return `① ${matchClock(moment)} regain → ② ${carryText} → ③ pass kept`;
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function countLabel(value: number): string {
  return Math.round(value).toLocaleString("en-US");
}

function boundPercent(value: number): string {
  const percent = value * 100;
  if (percent === 0 || Number.isInteger(percent)) return `${percent}%`;
  if (percent < 0.1) return `${percent.toFixed(2)}%`;
  return `${percent.toFixed(1)}%`;
}

export function intervalAnswerText(metric: FilmRoomIntervalMetric): string {
  const source = asRecord(metric.source);
  const population = count(source.population_count);
  const completed = count(source.a_count);
  const unknown = metric.unknown_count;
  return `Of ${countLabel(population)} regains, ${countLabel(completed)} completed the whole chain ①→②→③. ${countLabel(unknown)} couldn't be fully seen — they widen the honest bounds to [${boundPercent(metric.lower)}, ${boundPercent(metric.upper)}].`;
}

export function visibleSchemaTokens(text: string): string[] {
  const normalized = text.toLowerCase();
  return DEFAULT_SURFACE_SCHEMA_TOKENS.filter((token) => normalized.includes(token));
}
