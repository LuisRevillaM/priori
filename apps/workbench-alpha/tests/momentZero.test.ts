import assert from "node:assert/strict";
import highBypassMoment from "../src/generated/moment-high-bypass.json";
import supportedMoment from "../src/generated/moment-line-break-supported.json";
import momentZero from "../src/generated/moment-zero.json";
import {
  isHighBypassPayload,
  momentZeroBallEvidenceFrameId,
  momentZeroLineEvidenceFrameId,
  momentZeroVisualEndFrameId
} from "../src/MomentZero";

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
assert.equal(momentZeroBallEvidenceFrameId(momentZero.moment, momentZeroVisualEndFrameId(momentZero.moment)), momentZero.moment.reception_frame_id);

assert.equal(supportedMoment.schema_version, "moment_zero.line_break_with_underneath_support.v0");
assert.equal(supportedMoment.moment.requested_evidence.line_break_status, "PASS");
assert.equal(supportedMoment.moment.requested_evidence.support_arrival_status, "PASS");
assert.ok(supportedMoment.moment.support_region.supporting_player_ids.length > 0);
assert.equal(supportedMoment.moment.support_region.mode, "BEHIND_BALL_OUTLET");
assert.ok(supportedMoment.visual_contract.prohibited_visual_claims.includes("intent"));
const supportedTargetLine = supportedMoment.moment.observed_lines.find(
  (line) => line.line_rank === supportedMoment.moment.requested_evidence.target_line_rank
);
assert.ok(supportedTargetLine);
assert.equal(momentZeroLineEvidenceFrameId(supportedMoment.moment), supportedMoment.moment.release_frame_id);
assert.ok(supportedTargetLine.line_id.includes(`:${supportedMoment.moment.release_frame_id}:`));
assert.deepEqual(supportedTargetLine.defender_ids, supportedMoment.moment.defensive_line_player_ids);
assert.equal(momentZeroVisualEndFrameId(supportedMoment.moment), supportedMoment.moment.support_window_end_frame_id);
assert.equal(
  momentZeroBallEvidenceFrameId(supportedMoment.moment, supportedMoment.moment.support_window_end_frame_id),
  supportedMoment.moment.reception_frame_id
);

assert.equal(highBypassMoment.schema_version, "coach_moment.high_bypass_completed_pass.v0");
assert.ok(isHighBypassPayload(highBypassMoment));
assert.equal(highBypassMoment.moment.classification, "HIGH_BYPASS_COMPLETED_PASS");
assert.equal(highBypassMoment.moment.requested_evidence.evaluation_status, "PASS");
assert.ok(highBypassMoment.moment.opponents_bypassed_count >= 5);
assert.equal(highBypassMoment.moment.opponents_bypassed_count, highBypassMoment.moment.bypassed_player_ids.length);
assert.ok(highBypassMoment.moment.forward_progression_m >= 8);
assert.ok(highBypassMoment.replay.frames.length > 0);
assert.ok(highBypassMoment.visual_contract.prohibited_visual_claims.includes("intent"));
assert.ok(highBypassMoment.visual_contract.prohibited_visual_claims.includes("defensive line broken"));

console.log("moment zero tests passed");
