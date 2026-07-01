import assert from "node:assert/strict";
import { layoutPitch, pitchPointToPixel } from "../src/pitchGeometry";

const pitch = { length_m: 105, width_m: 68 };
const layout = layoutPitch(pitch, 1000);
const epsilon = 1e-6;

function close(actual: number, expected: number, label: string) {
  assert.ok(Math.abs(actual - expected) < epsilon, `${label}: expected ${expected}, got ${actual}`);
}

const center = pitchPointToPixel(0, 0, pitch, layout);
close(center.x, layout.canvasWidth / 2, "center x");
close(center.y, layout.canvasHeight / 2, "center y");

const topLeft = pitchPointToPixel(-52.5, 34, pitch, layout);
close(topLeft.x, layout.marginX, "top left x");
close(topLeft.y, layout.marginY, "top left y");

const topRight = pitchPointToPixel(52.5, 34, pitch, layout);
close(topRight.x, layout.marginX + layout.fieldWidth, "top right x");
close(topRight.y, layout.marginY, "top right y");

const bottomLeft = pitchPointToPixel(-52.5, -34, pitch, layout);
close(bottomLeft.x, layout.marginX, "bottom left x");
close(bottomLeft.y, layout.marginY + layout.fieldHeight, "bottom left y");

const bottomRight = pitchPointToPixel(52.5, -34, pitch, layout);
close(bottomRight.x, layout.marginX + layout.fieldWidth, "bottom right x");
close(bottomRight.y, layout.marginY + layout.fieldHeight, "bottom right y");

close(pitchPointToPixel(0, 34, pitch, layout).y, layout.marginY, "top touchline");
close(pitchPointToPixel(0, -34, pitch, layout).y, layout.marginY + layout.fieldHeight, "bottom touchline");
close(pitchPointToPixel(0, 0, pitch, layout).x, layout.canvasWidth / 2, "halfway line");

const tenMetersX = Math.abs(
  pitchPointToPixel(10, 0, pitch, layout).x - pitchPointToPixel(0, 0, pitch, layout).x
);
const tenMetersY = Math.abs(
  pitchPointToPixel(0, 10, pitch, layout).y - pitchPointToPixel(0, 0, pitch, layout).y
);
close(tenMetersX, tenMetersY, "equal metre distance scale");

console.log("pitch geometry tests passed");
