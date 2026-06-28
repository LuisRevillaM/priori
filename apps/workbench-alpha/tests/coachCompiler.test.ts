import assert from "node:assert/strict";
import { coachExamplePrompts, interpretCoachQuery } from "../src/coachCompiler";

const lineBreak = interpretCoachQuery("Find moments where the receiver breaks the second line without support");

assert.equal(lineBreak.kind, "moment");
if (lineBreak.kind !== "moment") {
  throw new Error("line-break query did not resolve to a moment");
}

assert.equal(lineBreak.moment_id, "line_break_no_underneath_support");
assert.equal(lineBreak.display_answer, "Line broken. The outlet space stays empty.");
assert.match(lineBreak.meaning_definition, /observed controlled pass/);
assert.equal(lineBreak.source_trace.preview_rule, "coach.preview.line_break_no_underneath_support");
assert.match(lineBreak.source_trace.source_plan, /q3_receiver_second_line_no_underneath_support/);
assert.ok(lineBreak.source_trace.evidence_fields.includes("line_break_status"));
assert.ok(lineBreak.source_trace.evidence_fields.includes("support_arrival_status"));
assert.ok(lineBreak.source_trace.evidence_fields.includes("supporting_player_ids"));
assert.ok(lineBreak.source_trace.prohibited_claims.includes("intent"));
assert.ok(lineBreak.source_trace.prohibited_claims.includes("quality"));
assert.ok(lineBreak.source_trace.prohibited_claims.includes("causation"));

const ambiguous = interpretCoachQuery("show me dangerous attacks");
assert.equal(ambiguous.kind, "clarification");
if (ambiguous.kind !== "clarification") {
  throw new Error("ambiguous query did not request clarification");
}
assert.match(ambiguous.prompt, /observable part/);
assert.ok(ambiguous.suggestions.includes("Show line breaks with no underneath outlet"));

const unsupported = interpretCoachQuery("show expected pass completion probability");
assert.equal(unsupported.kind, "redirect");
if (unsupported.kind !== "redirect") {
  throw new Error("expected-model query did not redirect");
}
assert.equal(unsupported.reason, "unsupported_modality");
assert.equal(unsupported.prompt, "This preview stays with observed moments.");

const outOfPreview = interpretCoachQuery("show give and gos");
assert.equal(outOfPreview.kind, "redirect");
if (outOfPreview.kind !== "redirect") {
  throw new Error("out-of-preview query did not redirect");
}
assert.equal(outOfPreview.reason, "not_in_preview");
assert.ok(outOfPreview.suggestions.length > 0);

assert.deepEqual(coachExamplePrompts(), [
  "Show line breaks with no underneath outlet",
  "Find moments where the receiver breaks the second line without support",
  "Show unsupported line breaks"
]);

console.log("coach compiler tests passed");
