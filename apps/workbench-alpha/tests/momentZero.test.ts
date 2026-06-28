import assert from "node:assert/strict";
import momentZero from "../src/generated/moment-zero.json";
import { momentZeroLineEvidenceFrameId, momentZeroVisualEndFrameId } from "../src/MomentZero";

assert.equal(momentZero.schema_version, "moment_zero.line_break_no_underneath_support.v0");
assert.equal(momentZero.moment.classification, "Q3_RECEIVER_SECOND_LINE_NO_UNDERNEATH_SUPPORT");
assert.equal(momentZero.moment.requested_evidence.line_break_status, "PASS");
assert.equal(momentZero.moment.requested_evidence.support_arrival_status, "FAIL");
assert.equal(momentZero.moment.requested_evidence.coverage_status, "COMPLETE");
assert.deepEqual(momentZero.moment.support_region.supporting_player_ids, []);
assert.equal(momentZero.moment.support_region.mode, "BEHIND_BALL_OUTLET");
assert.ok(momentZero.moment.support_region.maximum_support_distance_m > 0);
assert.ok(momentZero.replay.frames.length > 0);
assert.ok(momentZero.visual_contract.prohibited_visual_claims.includes("intent"));
assert.ok(momentZero.visual_contract.empty_support_region.includes("supporting_player_ids"));

const targetLine = momentZero.moment.observed_lines.find(
  (line) => line.line_rank === momentZero.moment.requested_evidence.target_line_rank
);
assert.ok(targetLine);
assert.equal(momentZeroLineEvidenceFrameId(momentZero.moment), momentZero.moment.release_frame_id);
assert.ok(targetLine.line_id.includes(`:${momentZero.moment.release_frame_id}:`));
assert.deepEqual(targetLine.defender_ids, momentZero.moment.defensive_line_player_ids);
assert.equal(momentZeroVisualEndFrameId(momentZero.moment), momentZero.moment.reception_frame_id + 8);
assert.ok(momentZeroLineEvidenceFrameId(momentZero.moment) < momentZeroVisualEndFrameId(momentZero.moment));

console.log("moment zero tests passed");
