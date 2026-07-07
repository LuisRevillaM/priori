import assert from "node:assert/strict";
import {
  assertIntervalMetric,
  chainStatusLabel,
  filmRoomBootstrapWarmingMessage,
  filmRoomErrorViewModel,
  filmRoomOutcomeClass,
  headerChipsFromResponse,
  intervalHeadline,
  refusalViewModel
} from "../src/FilmRoom";
import type { FilmRoomAskResponse } from "../src/types";

const metric = assertIntervalMetric({
  label: "Certified interval",
  observed: 0.42,
  lower: 0.2,
  upper: 0.8,
  unknown_count: 11,
  source: { evidence_kind: "certified", plan_hash: "abc" }
});

assert.equal(metric.observed, 0.42);
assert.equal(metric.lower, 0.2);
assert.equal(metric.upper, 0.8);
assert.equal(metric.unknown_count, 11);
assert.equal(intervalHeadline(metric), "Certified interval");
assert.equal(
  intervalHeadline({ ...metric, source: { evidence_kind: "runtime" } }),
  "Runtime evidence interval"
);

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

const baseResponse = {
  ok: true,
  request_text: "How often?",
  provider: "openai-codex",
  model: "gpt-5.5",
  latency_ms: 12,
  latency_breakdown_ms: { hermes: 3, synthesis: 4, execution: 5, total: 12 },
  hermes: {},
  clarification: null,
  refusal: null
} satisfies Partial<FilmRoomAskResponse>;

assert.equal(filmRoomOutcomeClass(null), "pending");
assert.equal(
  filmRoomOutcomeClass({
    ...baseResponse,
    outcome: "clarification_required",
    clarification: { question: "Which reading?", readings: [], state: {} },
    answer: null
  } as FilmRoomAskResponse),
  "clarification"
);
assert.equal(
  filmRoomOutcomeClass({
    ...baseResponse,
    outcome: "understood_but_not_expressible",
    refusal: { missing_capability: "concept:body_orientation", gap_code: "BODY_ORIENTATION", message: "Pose data is absent." },
    answer: null
  } as FilmRoomAskResponse),
  "refusal"
);

const refusal = refusalViewModel({
  missing_capability: "concept:body_orientation",
  gap_code: "BODY_ORIENTATION",
  message: "Pose data is absent."
});
assert.equal(refusal.missing, "concept:body_orientation");
assert.equal(refusal.gapCode, "BODY_ORIENTATION");

const truncationRefusal = refusalViewModel({
  missing_capability: "model_output_completion",
  gap_code: "MODEL_OUTPUT_TRUNCATED",
  message: "cut off"
});
assert.equal(truncationRefusal.missing, "Model answer got cut off");
assert.equal(truncationRefusal.message, "The model's answer got cut off. Retry the ask.");

assert.deepEqual(
  filmRoomErrorViewModel({
    error_code: "REQUEST_SCHEMA_INVALID",
    details: { expected: "JSON object with non-empty text" }
  }),
  {
    title: "Couldn't understand the request",
    code: "REQUEST_SCHEMA_INVALID",
    message: "The request body did not match the Film Room API contract.",
    detail: "JSON object with non-empty text",
    tone: "schema"
  }
);
assert.deepEqual(
  filmRoomErrorViewModel({
    error_code: "MODEL_OUTPUT_TRUNCATED",
    details: { reason: "end-of-output JSON parse" }
  }),
  {
    title: "The model's answer got cut off",
    code: "MODEL_OUTPUT_TRUNCATED",
    message: "Retry the ask; the model stopped before it produced complete JSON.",
    detail: "end-of-output JSON parse",
    tone: "truncation"
  }
);
assert.deepEqual(
  filmRoomErrorViewModel({
    error_code: "INTERNAL_ERROR",
    details: { correlation_id: "err_abc123def456" }
  }),
  {
    title: "Something broke on our side",
    code: "INTERNAL_ERROR",
    message: "The server logged a traceback for this failure.",
    detail: "correlation err_abc123def456",
    tone: "internal"
  }
);
assert.deepEqual(
  filmRoomErrorViewModel({
    error_code: "DEMO_TOKEN_REQUIRED",
    details: { token_source: "demo_token body field" }
  }),
  {
    title: "Demo token required",
    code: "DEMO_TOKEN_REQUIRED",
    message: "Live asks are gated in public mode.",
    detail: "demo_token body field",
    tone: "gate"
  }
);
assert.deepEqual(
  filmRoomErrorViewModel({
    error_code: "ASKS_DISABLED",
    details: { reason: "hermes_auth_missing" }
  }),
  {
    title: "Live asks disabled",
    code: "ASKS_DISABLED",
    message: "The gallery is available, but model-backed asks are not connected in this runtime.",
    detail: "hermes_auth_missing",
    tone: "disabled"
  }
);
assert.equal(
  filmRoomBootstrapWarmingMessage({
    ok: true,
    state: "warming",
    provider: "openai-codex",
    model: "gpt-5.5",
    billing_surface: "subscription",
    flagship_plan_hashes: {},
    prewarm_records: [],
    warming: {
      items: [
        { key: "fragile_retention", status: "ready" },
        { key: "counterattack_sequence_rate", status: "running" }
      ]
    },
    prewarmed_response: null,
    answer: null,
    provenance: null
  }),
  "Warming counterattack sequence rate."
);

const chips = headerChipsFromResponse({
  ...baseResponse,
  outcome: "expression",
  answer: {
    status: "answer_ready",
    compiled_chips: [],
    document: {
      documents: {
        home: { default_invocation: { match_ids: ["J03WOY", "J03WPY"], perspective_team_role: "home" } }
      }
    },
    certified_evidence_rows: [],
    runtime_evidence_rows: [],
    evidence_rows_kind: "runtime",
    interval_metric: null,
    moments: [],
    moment_total_count: 0,
    visible_moment_count: 0,
    replay: null,
    executions: [],
    raw_evidence: {},
    provenance: {
      plan_hash: "abc",
      synthesized_document_hash: "def",
      bound_plan_hashes: {},
      canonical_sources: {},
      tree: "1234567890"
    }
  },
  clarification: null,
  refusal: null
} as FilmRoomAskResponse);
assert.deepEqual(chips, ["2 matches", "home perspective", "openai-codex · gpt-5.5", "tree 1234567"]);

assert.equal(chainStatusLabel(null), "no chain selected");
assert.equal(
  chainStatusLabel({
    result_id: "chain-1",
    source_kind: "chain_record",
    classification: "COUNTERATTACK",
    match_id: "J03WOY",
    period: "secondHalf",
    anchor_frame_id: 121915,
    requested_evidence: {},
    chain_status: null,
    evidence_overlay: {}
  }),
  "chain_status not emitted"
);
assert.equal(
  chainStatusLabel({
    result_id: "chain-2",
    source_kind: "chain_record",
    classification: "COUNTERATTACK",
    match_id: "J03WOY",
    period: "secondHalf",
    anchor_frame_id: 121915,
    requested_evidence: {},
    chain_status: "UNKNOWN",
    evidence_overlay: {}
  }),
  "UNKNOWN"
);

console.log("film room tests passed");
