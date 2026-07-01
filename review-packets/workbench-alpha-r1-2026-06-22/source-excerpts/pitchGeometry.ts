export type PitchDimensions = {
  length_m: number;
  width_m: number;
};

export type PitchLayout = {
  canvasWidth: number;
  canvasHeight: number;
  marginX: number;
  marginY: number;
  fieldWidth: number;
  fieldHeight: number;
  scalePxPerM: number;
};

const HORIZONTAL_MARGIN_RATIO = 0.035;
const VERTICAL_MARGIN_RATIO = 0.055;
const FALLBACK_WIDTH = 960;
const MIN_CANVAS_WIDTH = 320;

export function layoutPitch(pitch: PitchDimensions, requestedWidth: number | null | undefined): PitchLayout {
  const canvasWidth = Math.max(Math.round(requestedWidth || FALLBACK_WIDTH), MIN_CANVAS_WIDTH);
  const marginX = canvasWidth * HORIZONTAL_MARGIN_RATIO;
  const fieldWidth = canvasWidth - marginX * 2;
  const scalePxPerM = fieldWidth / pitch.length_m;
  const fieldHeight = pitch.width_m * scalePxPerM;
  const canvasHeight = Math.round(fieldHeight / (1 - VERTICAL_MARGIN_RATIO * 2));
  const marginY = (canvasHeight - fieldHeight) / 2;
  return {
    canvasWidth,
    canvasHeight,
    marginX,
    marginY,
    fieldWidth,
    fieldHeight,
    scalePxPerM
  };
}

export function pitchPointToPixel(
  x_m: number,
  y_m: number,
  pitch: PitchDimensions,
  layout: PitchLayout
) {
  return {
    x: layout.marginX + ((x_m + pitch.length_m / 2) / pitch.length_m) * layout.fieldWidth,
    y: layout.marginY + ((pitch.width_m / 2 - y_m) / pitch.width_m) * layout.fieldHeight
  };
}
