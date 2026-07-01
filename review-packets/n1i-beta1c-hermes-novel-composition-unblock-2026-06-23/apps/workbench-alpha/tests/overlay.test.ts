import assert from "node:assert/strict";
import {
  corridorOverlayState,
  overlayLegendLines,
  overlayProofText,
  overlayVisibleAtFrame
} from "../src/overlay";
import type { ReplayPayload } from "../src/types";

const replay = (anchor: number, frameIds: number[]) =>
  ({ anchor_frame_id: anchor, frames: frameIds.map((frame_id) => ({ frame_id, entities: [] })) } as unknown as ReplayPayload);

// --- none: no evidence / no target ---
assert.equal(corridorOverlayState(null, replay(100, [100])).kind, "none");
assert.equal(corridorOverlayState({}, null).reason, "No selected result overlay");
assert.equal(corridorOverlayState({ minimum_clearance_m: 4 }, replay(100, [100])).reason, "No exact corridor witness available");

// --- witness-frame only (corridor preset: target + clearance, no open/close frames) ---
const witness = corridorOverlayState(
  { target_player_id: "DFL-OBJ-1", minimum_clearance_m: 4.35 },
  replay(100, [98, 99, 100, 101])
);
assert.equal(witness.kind, "witness");
if (witness.kind === "witness") {
  assert.equal(witness.witnessFrameId, 100);
  assert.equal(witness.clearanceM, 4.35);
}
assert.equal(overlayVisibleAtFrame(witness, 100), true);
assert.equal(overlayVisibleAtFrame(witness, 99), false, "hidden outside the witness frame");
assert.equal(overlayProofText(witness, 100), "Witness-frame corridor: ball to selected receiver");
assert.equal(overlayProofText(witness, 99), "Corridor witness hidden outside the witness frame");
const witnessLegend = overlayLegendLines(witness).join(" ");
assert.match(witnessLegend, /witness frame/i);
assert.match(witnessLegend, /4\.35 m/);
assert.match(witnessLegend, /optimal pass/i);

// --- interval (evidence carries open/close frames covered by the replay) ---
const interval = corridorOverlayState(
  {
    target_player_id: "DFL-OBJ-2",
    relation_open_frame_id: 200,
    relation_close_frame_id: 210,
    minimum_clearance_m: 3.1,
    limiting_defender_id: "DFL-OBJ-9"
  },
  replay(205, [198, 200, 205, 210, 215])
);
assert.equal(interval.kind, "interval");
if (interval.kind === "interval") {
  assert.equal(interval.openFrameId, 200);
  assert.equal(interval.closeFrameId, 210);
  assert.equal(interval.limitingDefenderId, "DFL-OBJ-9");
}
assert.equal(overlayVisibleAtFrame(interval, 205), true);
assert.equal(overlayVisibleAtFrame(interval, 199), false);
assert.equal(overlayVisibleAtFrame(interval, 211), false);
assert.equal(overlayProofText(interval, 205), "Corridor visible: ball to target within the valid interval");
assert.equal(overlayProofText(interval, 199), "Corridor hidden outside its valid interval");
const intervalLegend = overlayLegendLines(interval).join(" ");
assert.match(intervalLegend, /from frame 200 to 210/);
assert.match(intervalLegend, /Limiting defender: DFL-OBJ-9/);

// --- never infer: open/close present but no replay frame inside the interval falls back to witness ---
const noCover = corridorOverlayState(
  { target_player_id: "t", relation_open_frame_id: 500, relation_close_frame_id: 510 },
  replay(100, [98, 100, 102])
);
assert.equal(noCover.kind, "witness", "interval with no covered frames downgrades, not guesses");

console.log("overlay tests passed");
