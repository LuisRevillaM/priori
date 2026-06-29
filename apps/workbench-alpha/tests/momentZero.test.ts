import assert from "node:assert/strict";
import highBypassCatalog from "../src/generated/moment-high-bypass-catalog.json";
import highBypassMoment from "../src/generated/moment-high-bypass.json";
import supportedMomentCatalog from "../src/generated/moment-line-break-supported-catalog.json";
import supportedMoment from "../src/generated/moment-line-break-supported.json";
import momentZeroCatalog from "../src/generated/moment-zero-catalog.json";
import momentZero from "../src/generated/moment-zero.json";
import { coachProductClaimGate } from "../src/coachProductClaims";
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
assert.ok(momentZero.replay.frames.every((frame) => frame.ball_state));
assert.ok(momentZero.visual_contract.prohibited_visual_claims.includes("intent"));
assert.ok(momentZero.visual_contract.empty_support_region.includes("supporting_player_ids"));

const targetLine = momentZero.moment.observed_lines.find(
  (line) => line.line_rank === momentZero.moment.requested_evidence.target_line_rank
);
assert.ok(targetLine);
assert.equal(momentZeroLineEvidenceFrameId(momentZero.moment), momentZero.moment.release_frame_id);
assert.ok(targetLine.line_id.includes(`:${momentZero.moment.release_frame_id}:`));
assert.deepEqual(targetLine.defender_ids, momentZero.moment.defensive_line_player_ids);
assert.equal(momentZero.moment.outcome_sequence.status, "PASS");
assert.equal(momentZero.moment.outcome_sequence.mode, "measured_ball_outcome_after_reception");
assert.equal(momentZero.moment.outcome_sequence.claim_boundary.includes("no quality"), true);
assert.ok(
  ["reached_final_third", "remained_in_final_third", "did_not_reach_final_third"].includes(
    momentZero.moment.outcome_sequence.final_third_outcome
  )
);
assert.ok(["PASS", "FAIL", "UNKNOWN"].includes(momentZero.moment.outcome_sequence.progression_status));
assert.equal(momentZero.moment.possession_retention.mode, "raw_ball_possession_retention_after_reception");
assert.ok(["PASS", "FAIL", "UNKNOWN"].includes(momentZero.moment.possession_retention.status));
assert.equal(momentZero.moment.possession_retention.claim_boundary.includes("no control quality"), true);
assert.equal(momentZeroVisualEndFrameId(momentZero.moment), momentZero.moment.outcome_sequence.end_frame_id);
assert.ok(momentZeroLineEvidenceFrameId(momentZero.moment) < momentZeroVisualEndFrameId(momentZero.moment));
assert.equal(momentZeroBallEvidenceFrameId(momentZero.moment, momentZeroVisualEndFrameId(momentZero.moment)), momentZero.moment.outcome_sequence.end_frame_id);
assert.ok(momentZero.replay.end_frame_id > momentZero.moment.outcome_sequence.end_frame_id);

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
assert.equal(supportedMoment.moment.outcome_sequence.status, "PASS");
assert.equal(supportedMoment.moment.outcome_sequence.final_third_outcome, "remained_in_final_third");
assert.equal(supportedMoment.moment.possession_retention.status, "FAIL");
assert.equal(momentZeroVisualEndFrameId(supportedMoment.moment), supportedMoment.moment.outcome_sequence.end_frame_id);
assert.equal(
  momentZeroBallEvidenceFrameId(supportedMoment.moment, supportedMoment.moment.outcome_sequence.end_frame_id),
  supportedMoment.moment.outcome_sequence.end_frame_id
);

assert.equal(highBypassMoment.schema_version, "coach_moment.high_bypass_completed_pass.v0");
assert.ok(isHighBypassPayload(highBypassMoment));
assert.equal(highBypassMoment.moment.classification, "HIGH_BYPASS_COMPLETED_PASS");
assert.equal(highBypassMoment.moment.requested_evidence.evaluation_status, "PASS");
assert.ok(highBypassMoment.moment.opponents_bypassed_count >= 5);
assert.equal(highBypassMoment.moment.opponents_bypassed_count, highBypassMoment.moment.bypassed_player_ids.length);
assert.ok(highBypassMoment.moment.forward_progression_m >= 8);
assert.equal(highBypassMoment.moment.outcome_sequence.status, "PASS");
assert.equal(highBypassMoment.moment.outcome_sequence.final_third_status, "PASS");
assert.equal(highBypassMoment.moment.outcome_sequence.final_third_outcome, "reached_final_third");
assert.equal(highBypassMoment.moment.outcome_sequence.progression_status, "PASS");
assert.equal(highBypassMoment.moment.possession_retention.status, "PASS");
assert.equal(highBypassMoment.moment.possession_retention.possession_team_role_at_start, highBypassMoment.moment.perspective_team_role);
assert.equal(highBypassMoment.moment.possession_retention.possession_team_role_at_end, highBypassMoment.moment.perspective_team_role);
assert.ok(highBypassMoment.replay.frames.every((frame) => frame.ball_state));
assert.ok(highBypassMoment.replay.end_frame_id > highBypassMoment.moment.outcome_sequence.end_frame_id);
assert.ok(highBypassMoment.replay.frames.length > 0);
assert.ok(highBypassMoment.visual_contract.prohibited_visual_claims.includes("intent"));
assert.ok(highBypassMoment.visual_contract.prohibited_visual_claims.includes("defensive line broken"));
assert.ok(highBypassMoment.visual_contract.observed_outcome_sequence.includes("outcome_sequence.final_third_status"));
assert.ok(highBypassMoment.visual_contract.observed_outcome_sequence.includes("outcome_sequence.progression_status"));
assert.ok(highBypassMoment.visual_contract.observed_possession_retention.includes("possession_retention.status"));
assert.equal(highBypassCatalog.count, highBypassCatalog.moments.length);
assert.equal(highBypassCatalog.count, 5);
assert.ok(highBypassCatalog.moments.some((payload) => payload.moment.possession_retention.status === "PASS"));
assert.ok(highBypassCatalog.moments.some((payload) => payload.moment.possession_retention.status === "FAIL"));
assert.equal(supportedMomentCatalog.count, supportedMomentCatalog.moments.length);
assert.equal(supportedMomentCatalog.count, 2);
assert.equal(momentZeroCatalog.count, momentZeroCatalog.moments.length);
assert.equal(momentZeroCatalog.count, 13);

assert.equal(coachProductClaimGate("high_bypass_completed_pass", highBypassMoment).passed, true);
const unretainedHighBypass = structuredClone(highBypassMoment);
unretainedHighBypass.moment.possession_retention.status = "FAIL";
const unretainedHighBypassGate = coachProductClaimGate("high_bypass_completed_pass", unretainedHighBypass);
assert.equal(unretainedHighBypassGate.passed, true);
const missingPossessionFeedHighBypass = structuredClone(highBypassMoment);
missingPossessionFeedHighBypass.moment.possession_retention.mode = "clean_control_retention";
const missingPossessionFeedGate = coachProductClaimGate("high_bypass_completed_pass", missingPossessionFeedHighBypass);
assert.equal(missingPossessionFeedGate.passed, false);
assert.deepEqual(missingPossessionFeedGate.failures[0], {
  path: "moment.possession_retention.mode",
  expected: "raw_ball_possession_retention_after_reception",
  actual: "clean_control_retention"
});

assert.equal(coachProductClaimGate("line_break_with_underneath_outlet", supportedMoment).passed, true);
assert.equal(coachProductClaimGate("line_break_no_underneath_support", momentZero).passed, true);

console.log("moment zero tests passed");
