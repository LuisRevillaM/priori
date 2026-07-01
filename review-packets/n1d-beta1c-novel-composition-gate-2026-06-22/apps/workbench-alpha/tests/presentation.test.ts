import assert from "node:assert/strict";
import {
  describeMeasurement,
  entryModeLabel,
  principalMeasurement,
  provenanceLabel,
  provenanceTone,
  tacticalHeadline
} from "../src/presentation";

// --- Provenance honesty: a preset/recipe must never read as AI-authored ---
assert.equal(provenanceLabel("REVIEWED_RECIPE"), "Reviewed recipe");
assert.equal(provenanceLabel("MANUAL_PRESET"), "Manual preset");
assert.equal(provenanceLabel("HERMES_RECIPE_SELECTION"), "Hermes selected recipe");
assert.equal(provenanceTone("REVIEWED_RECIPE"), "neutral");
assert.equal(provenanceTone("MANUAL_PRESET"), "neutral");

// --- Novel composition is held back as pending/not-product-ready (never a success claim) ---
assert.match(provenanceLabel("HERMES_NOVEL_COMPOSITION"), /pending proof refresh/i);
assert.equal(
  provenanceTone("HERMES_NOVEL_COMPOSITION"),
  "warn",
  "novel composition must read as a caution, not a success"
);

// --- Capability gap / model unavailable read honestly ---
assert.equal(provenanceTone("CAPABILITY_GAP"), "bad");
assert.equal(provenanceTone("MODEL_UNAVAILABLE"), "warn");
assert.equal(provenanceLabel(null), "Not interpreted");

// --- entry_mode is rendered only for the four honest enum values; never inferred ---
assert.equal(entryModeLabel("PRESENT_AT_OPEN")?.value, "PRESENT_AT_OPEN");
assert.equal(entryModeLabel("ENTERED_AFTER_OPEN")?.tone, "good");
assert.equal(entryModeLabel("NOT_ENTERED")?.tone, "warn");
assert.equal(entryModeLabel("UNKNOWN")?.label, "Entry not observable");
// absent / non-enum values must NOT be inferred into an entry mode
assert.equal(entryModeLabel(null), null);
assert.equal(entryModeLabel(undefined), null);
assert.equal(entryModeLabel(""), null);
assert.equal(entryModeLabel(3.2), null, "a time_to_entry number must never become an entry mode");
assert.equal(entryModeLabel("SOMETHING_ELSE"), null);

// --- Tactical headlines lead the card; raw classification is humanized as a fallback ---
assert.equal(tacticalHeadline("RETAINED_NO_SWITCH"), "Block held — no ball-side switch");
assert.equal(tacticalHeadline("PROGRESSIVE_CORRIDOR_AVAILABLE"), "Forward corridor available");
assert.equal(tacticalHeadline("SOME_NEW_LABEL"), "Some new label");

// --- Predicate measurements read in product language; raw payload never leaks into the line ---
assert.equal(describeMeasurement(4.2, 3, "m"), "measured 4.2 m · threshold 3 m");
assert.equal(describeMeasurement(4.2, 3), "measured 4.2 · threshold 3");
assert.equal(describeMeasurement(5, null), "measured 5");
assert.equal(describeMeasurement(null, 3, "m"), "threshold 3 m");
assert.equal(describeMeasurement({ nested: true }, [1, 2]), "Measurement detail in developer view");

// --- principal measurement: first available in priority order; never inferred ---
assert.equal(principalMeasurement(null), null);
assert.equal(principalMeasurement({}), null, "no known fields -> no measurement (never inferred)");
assert.equal(principalMeasurement({ signed_shift_metres: 4.21 })?.label, "Shift 4.21 m");
assert.equal(
  principalMeasurement({ destination_time_to_entry_seconds: 0.16 })?.label,
  "Entry in 0.16 s"
);
assert.equal(principalMeasurement({ destination_entry_mode: "PRESENT_AT_OPEN" })?.label, "Entry: Already in destination at open");
assert.equal(principalMeasurement({ minimum_clearance_m: 4.35 })?.label, "Clearance 4.35 m");
assert.equal(principalMeasurement({ relation_duration_seconds: 3.8 })?.label, "Held 3.8 s");
// node-prefixed aliases (e.g. block-shift "signed_shift.signed_shift_metres") match by dotted suffix
assert.equal(principalMeasurement({ "signed_shift.signed_shift_metres": -3.4 })?.label, "Shift -3.4 m");
// priority: shift wins over clearance when both present
assert.equal(principalMeasurement({ minimum_clearance_m: 4.35, signed_shift_metres: 2 })?.key, "signed_shift_metres");
// raw value preserved for tooling
assert.equal(principalMeasurement({ signed_shift_metres: 4.2109 })?.raw, "4.2109");

console.log("presentation tests passed");
