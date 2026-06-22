import assert from "node:assert/strict";
import { advancePlaybackFrame, sourceFrameDurationMs } from "../src/playback";

assert.equal(sourceFrameDurationMs(25), 40);

const oneSecond = advancePlaybackFrame({
  currentFrameIndex: 0,
  frameCount: 101,
  frameRateHz: 25,
  playbackSpeed: 1,
  elapsedMs: 1000,
  carriedMs: 0
});
assert.equal(oneSecond.frameIndex, 25, "1x playback advances 25 frames in one real second at 25 Hz");
assert.equal(oneSecond.carriedMs, 0);

const halfSpeed = advancePlaybackFrame({
  currentFrameIndex: 0,
  frameCount: 101,
  frameRateHz: 25,
  playbackSpeed: 0.5,
  elapsedMs: 1000,
  carriedMs: 0
});
assert.equal(halfSpeed.frameIndex, 12, "0.5x playback advances about half the source frames");
assert.equal(halfSpeed.carriedMs, 20);

const doubleSpeed = advancePlaybackFrame({
  currentFrameIndex: 95,
  frameCount: 101,
  frameRateHz: 25,
  playbackSpeed: 2,
  elapsedMs: 1000,
  carriedMs: 0
});
assert.equal(doubleSpeed.frameIndex, 44, "2x playback wraps through the frame window");

console.log("playback tests passed");
