import assert from "node:assert/strict";
import { assertIntervalMetric } from "../src/FilmRoom";

const metric = assertIntervalMetric({
  label: "Certified interval",
  observed: 0.42,
  lower: 0.2,
  upper: 0.8,
  unknown_count: 11,
  source: { plan_hash: "abc" }
});

assert.equal(metric.observed, 0.42);
assert.equal(metric.lower, 0.2);
assert.equal(metric.upper, 0.8);
assert.equal(metric.unknown_count, 11);

for (const key of ["observed", "lower", "upper", "unknown_count"] as const) {
  const candidate: Record<string, unknown> = {
    label: "Certified interval",
    observed: 0.42,
    lower: 0.2,
    upper: 0.8,
    unknown_count: 11,
    source: {}
  };
  delete candidate[key];
  assert.throws(
    () => assertIntervalMetric(candidate),
    /missing finite/,
    `interval metrics without ${key} must be unrenderable`
  );
}

assert.throws(
  () => assertIntervalMetric({ label: "Point estimate", observed: 0.42 }),
  /missing finite/,
  "a point estimate without bounds must be unrenderable"
);

console.log("film room tests passed");
