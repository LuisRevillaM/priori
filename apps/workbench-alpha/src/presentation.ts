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
