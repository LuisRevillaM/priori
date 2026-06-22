export type PlaybackStep = {
  frameIndex: number;
  carriedMs: number;
};

export function sourceFrameDurationMs(frameRateHz: number): number {
  return 1000 / Math.max(frameRateHz, 1);
}

export function advancePlaybackFrame(input: {
  currentFrameIndex: number;
  frameCount: number;
  frameRateHz: number;
  playbackSpeed: number;
  elapsedMs: number;
  carriedMs: number;
}): PlaybackStep {
  if (input.frameCount <= 0) {
    return { frameIndex: 0, carriedMs: 0 };
  }
  const sourceMs = sourceFrameDurationMs(input.frameRateHz);
  const accumulated = input.carriedMs + Math.max(0, input.elapsedMs) * input.playbackSpeed;
  const frames = Math.floor(accumulated / sourceMs);
  if (frames <= 0) {
    return { frameIndex: input.currentFrameIndex, carriedMs: accumulated };
  }
  return {
    frameIndex: (input.currentFrameIndex + frames) % input.frameCount,
    carriedMs: accumulated - frames * sourceMs
  };
}
