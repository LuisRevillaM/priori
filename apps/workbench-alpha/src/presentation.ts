// Pure presentation mappers for the Workbench product surface.
// Kept free of React/DOM so they can be unit-tested directly (tests/presentation.test.ts).
import type { ProvenanceSource } from "./types";

export type Tone = "neutral" | "good" | "warn" | "bad";

export type EntryMode = "PRESENT_AT_OPEN" | "ENTERED_AFTER_OPEN" | "NOT_ENTERED" | "UNKNOWN";

export function humanizeClassification(classification: string) {
  const spaced = classification.replaceAll("_", " ").toLowerCase().trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : "Tactical moment";
}

// Product-facing tactical headline for a result classification. Formal classification strings stay
// available via data attributes and Developer details; they never lead the card.
export function tacticalHeadline(classification: string) {
  switch (classification) {
    case "RETAINED_NO_SWITCH":
      return "Block held — no ball-side switch";
    case "BALL_SIDE_BLOCK_SHIFT":
      return "Defending block shifted to the ball side";
    case "PROGRESSIVE_CORRIDOR_AVAILABLE":
      return "Forward corridor available";
    case "NO_PROGRESSIVE_CORRIDOR":
      return "No forward corridor";
    default:
      return humanizeClassification(classification);
  }
}

export function provenanceLabel(source: ProvenanceSource | null | undefined) {
  switch (source) {
    case "REVIEWED_RECIPE":
      return "Reviewed recipe";
    case "MANUAL_PRESET":
      return "Manual preset";
    case "HERMES_RECIPE_SELECTION":
      return "Hermes selected recipe";
    case "HERMES_NOVEL_COMPOSITION":
      // Not product-ready: live N1 novel-composition proof is pending a runtime-provenance refresh.
      return "Novel composition · pending proof refresh";
    case "DETERMINISTIC_REPAIR":
      return "Safety repair applied";
    case "CAPABILITY_GAP":
      return "Capability gap";
    case "MODEL_UNAVAILABLE":
      return "Hermes unavailable";
    default:
      return "Not interpreted";
  }
}

export function provenanceTone(source: ProvenanceSource | null | undefined): Tone {
  if (source === "CAPABILITY_GAP") return "bad";
  // Novel composition is held back as pending/not-product-ready, so it reads as a caution, not success.
  if (source === "MODEL_UNAVAILABLE" || source === "DETERMINISTIC_REPAIR" || source === "HERMES_NOVEL_COMPOSITION") {
    return "warn";
  }
  return source ? "neutral" : "warn";
}

function formatScalar(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) return String(Math.round(value * 1000) / 1000);
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "true" : "false";
  return null;
}

// Compact, product-readable measurement line for a predicate trace. The full raw value/threshold
// payload stays out of the product surface (preserved in a data attribute for tooling/tests).
export function describeMeasurement(value: unknown, threshold: unknown, unit?: string | null): string {
  const suffix = unit ? ` ${unit}` : "";
  const measured = formatScalar(value);
  const limit = formatScalar(threshold);
  if (measured !== null && limit !== null) return `measured ${measured}${suffix} · threshold ${limit}${suffix}`;
  if (measured !== null) return `measured ${measured}${suffix}`;
  if (limit !== null) return `threshold ${limit}${suffix}`;
  return "Measurement detail in developer view";
}

function numericText(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) return String(Math.round(value * 1000) / 1000);
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
    return String(Math.round(Number(value) * 1000) / 1000);
  }
  return null;
}

// Find an evidence key matching a known field name. Evidence aliases may be plain ("minimum_clearance_m")
// or node-prefixed ("signed_shift.signed_shift_metres"), so match on exact name or dotted suffix.
function findEvidenceKey(evidence: Record<string, unknown>, names: string[]): string | null {
  for (const key of Object.keys(evidence)) {
    for (const name of names) {
      if (key === name || key.endsWith(`.${name}`)) return key;
    }
  }
  return null;
}

// First available principal measurement for a result card, in priority order. Never infers a missing
// value — returns null if none of the known evidence fields are present. Raw value preserved in `raw`.
export function principalMeasurement(
  evidence: Record<string, unknown> | null | undefined
): { key: string; label: string; raw: string } | null {
  if (!evidence) return null;
  const groups: Array<{ names: string[]; kind: "num" | "entry"; fmt?: (n: string) => string }> = [
    { names: ["signed_shift_metres", "block_shift_metres", "signed_lateral_shift_m"], kind: "num", fmt: (n) => `Shift ${n} m` },
    { names: ["destination_time_to_entry_seconds", "time_to_entry_seconds"], kind: "num", fmt: (n) => `Entry in ${n} s` },
    { names: ["destination_entry_mode", "entry_mode"], kind: "entry" },
    { names: ["minimum_clearance_m", "corridor_minimum_clearance_m", "clearance_m"], kind: "num", fmt: (n) => `Clearance ${n} m` },
    { names: ["relation_duration_seconds", "corridor_duration_seconds", "duration_seconds"], kind: "num", fmt: (n) => `Held ${n} s` }
  ];
  for (const group of groups) {
    const key = findEvidenceKey(evidence, group.names);
    if (!key) continue;
    if (group.kind === "num" && group.fmt) {
      const text = numericText(evidence[key]);
      if (text !== null) return { key, label: group.fmt(text), raw: String(evidence[key]) };
    } else if (group.kind === "entry") {
      const info = entryModeLabel(evidence[key]);
      if (info) return { key, label: `Entry: ${info.label}`, raw: String(evidence[key]) };
    }
  }
  return null;
}

const PREDICATE_SUBJECTS: Record<string, string> = {
  has_progressive_corridor: "Progressive corridor exists",
  destination_region_entered: "Ball entered the destination region",
  ball_side_block_shift: "Ball-side block shift cleared the threshold",
  wide_possession: "Wide possession"
};

// Readable subject for a predicate id (product language); falls back to a humanized id.
export function humanizePredicate(predicateId: string | undefined): string {
  if (!predicateId) return "Predicate";
  if (PREDICATE_SUBJECTS[predicateId]) return PREDICATE_SUBJECTS[predicateId];
  const spaced = predicateId.replaceAll("_", " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : "Predicate";
}

// Readable "why matched / why not" phrase, backed by the trace measurement. Raw JSON stays in
// Developer details; this is the default-view summary.
export function predicateWhy(status: string | undefined, value: unknown, threshold: unknown, unit?: string | null): string {
  const measurement = describeMeasurement(value, threshold, unit);
  const detail = measurement === "Measurement detail in developer view" ? "" : ` (${measurement})`;
  if (status === "PASS") return `Matched${detail}`;
  if (status === "FAIL") return `Did not match${detail}`;
  return `Could not be determined${detail}`;
}

// Readable outcome for a known-timestamp / non-match inspection. Raw payload stays in Developer tools.
export function timestampOutcomeSummary(inspection: Record<string, unknown> | null | undefined): string | null {
  if (!inspection) return null;
  if (JSON.stringify(inspection).includes("NO_COMPATIBLE_ANCHOR")) {
    return "No matching moment at this timestamp for the current plan.";
  }
  const status = typeof inspection.status === "string" ? inspection.status : null;
  if (status) return `Timestamp inspection: ${status.replaceAll("_", " ").toLowerCase()}.`;
  return "Timestamp inspected — see Developer details for the raw record.";
}

// Honest rendering of relation destination-entry mode. Only the four backend enum values are
// recognised; an absent value returns null so the UI never infers entry from time_to_entry_seconds.
export function entryModeLabel(mode: unknown): { label: string; tone: Tone; value: EntryMode } | null {
  switch (mode) {
    case "PRESENT_AT_OPEN":
      return { value: "PRESENT_AT_OPEN", tone: "neutral", label: "Already in destination at open" };
    case "ENTERED_AFTER_OPEN":
      return { value: "ENTERED_AFTER_OPEN", tone: "good", label: "Entered destination after open" };
    case "NOT_ENTERED":
      return { value: "NOT_ENTERED", tone: "warn", label: "Did not enter destination" };
    case "UNKNOWN":
      return { value: "UNKNOWN", tone: "warn", label: "Entry not observable" };
    default:
      return null;
  }
}
