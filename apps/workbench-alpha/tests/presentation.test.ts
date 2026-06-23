import assert from "node:assert/strict";
import {
  describeMeasurement,
  entryModePresentation,
  humanizePredicate,
  predicateWhy,
  principalMeasurement,
  provenanceLabel,
  provenanceTone,
  tacticalHeadline,
  timestampOutcomeSummary
} from "../src/presentation";

// --- Provenance honesty: a preset/recipe must never read as AI-authored ---
assert.equal(provenanceLabel("REVIEWED_RECIPE"), "Reviewed recipe");
assert.equal(provenanceLabel("MANUAL_PRESET"), "Manual preset");
assert.equal(provenanceLabel("HERMES_RECIPE_SELECTION"), "Hermes selected recipe");
assert.equal(provenanceTone("REVIEWED_RECIPE"), "neutral");
assert.equal(provenanceTone("MANUAL_PRESET"), "neutral");

// --- Verified novel composition reads as attested model authorship; unverified drafts stay cautious ---
assert.equal(provenanceLabel("HERMES_NOVEL_COMPOSITION"), "Verified Hermes-authored composition");
assert.equal(provenanceTone("HERMES_NOVEL_COMPOSITION"), "good");
assert.equal(provenanceLabel("HERMES_EXPERIMENTAL_UNVERIFIED"), "Experimental draft · unverified");
assert.equal(provenanceTone("HERMES_EXPERIMENTAL_UNVERIFIED"), "warn");

// --- Capability gap / model unavailable read honestly ---
assert.equal(provenanceTone("CAPABILITY_GAP"), "bad");
assert.equal(provenanceTone("MODEL_UNAVAILABLE"), "warn");
assert.equal(provenanceLabel(null), "Not interpreted");

// --- combined entry-mode mapper: honest for the four enum values; PRESENT_AT_OPEN at t=0 ---
assert.equal(entryModePresentation("PRESENT_AT_OPEN", 0)?.value, "PRESENT_AT_OPEN");
assert.equal(entryModePresentation("PRESENT_AT_OPEN", 0)?.label, "Already in destination when corridor opened");
assert.equal(entryModePresentation("ENTERED_AFTER_OPEN", 0.16)?.label, "Entered destination 0.16s after opening");
assert.equal(entryModePresentation("NOT_ENTERED", null)?.label, "Did not enter destination in the observed window");
assert.equal(entryModePresentation("UNKNOWN")?.label, "Destination entry could not be determined");
// absent / non-enum values must NOT be inferred into an entry mode
assert.equal(entryModePresentation(null), null);
assert.equal(entryModePresentation(undefined), null);
assert.equal(entryModePresentation("SOMETHING_ELSE"), null);
assert.equal(entryModePresentation(3.2), null, "a time_to_entry number must never become an entry mode");

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
// PRESENT_AT_OPEN must win over raw "Entry in 0 s"
assert.equal(
  principalMeasurement({ destination_entry_mode: "PRESENT_AT_OPEN", destination_time_to_entry_seconds: 0 })?.label,
  "Already in destination when corridor opened"
);
assert.equal(
  principalMeasurement({ destination_entry_mode: "ENTERED_AFTER_OPEN", destination_time_to_entry_seconds: 0.16 })?.label,
  "Entered destination 0.16s after opening"
);
assert.equal(principalMeasurement({ minimum_clearance_m: 4.35 })?.label, "Clearance 4.35 m");
assert.equal(principalMeasurement({ relation_duration_seconds: 3.8 })?.label, "Held 3.8 s");
// node-prefixed aliases (e.g. block-shift "signed_shift.signed_shift_metres") match by dotted suffix
assert.equal(principalMeasurement({ "signed_shift.signed_shift_metres": -3.4 })?.label, "Shift -3.4 m");
// priority: shift wins over clearance when both present
assert.equal(principalMeasurement({ minimum_clearance_m: 4.35, signed_shift_metres: 2 })?.key, "signed_shift_metres");
// raw value preserved for tooling
assert.equal(principalMeasurement({ signed_shift_metres: 4.2109 })?.raw, "4.2109");

// --- product-language predicate summaries ---
assert.equal(humanizePredicate("has_progressive_corridor"), "Progressive corridor exists");
assert.equal(humanizePredicate("some_other_predicate"), "Some other predicate");
assert.equal(humanizePredicate(undefined), "Predicate");
assert.equal(predicateWhy("PASS", 4.35, 3, "m"), "Matched (measured 4.35 m · threshold 3 m)");
assert.equal(predicateWhy("FAIL", 1, 3), "Did not match (measured 1 · threshold 3)");
assert.equal(predicateWhy("UNKNOWN", null, null), "Could not be determined");

// --- timestamp outcome summary ---
assert.match(String(timestampOutcomeSummary({ status: "NO_COMPATIBLE_ANCHOR" })), /No matching moment/);
assert.equal(timestampOutcomeSummary(null), null);
assert.match(String(timestampOutcomeSummary({ status: "MATCHED" })), /matched/);

console.log("presentation tests passed");
