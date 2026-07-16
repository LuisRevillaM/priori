import assert from "node:assert/strict";
import {
  assertIntervalMetric,
  chainStatusLabel,
  filmRoomBootstrapWarmingMessage,
  filmRoomErrorViewModel,
  filmRoomOutcomeClass,
  headerChipsFromResponse,
  intervalCertificationChip,
  intervalHeadline,
  momentCoverageText,
  momentCollectionLabel,
  orderedFilmRoomMoments,
  partitionVisibilityNote,
  pressingMapViewModel,
  provenanceArtifactLabels,
  provenanceTreeView,
  replayMatchClock,
  replaySamplingLabel,
  refusalViewModel,
  flagshipTabResponse,
  visibleWitnessLabels
} from "../src/FilmRoom";
import {
  deriveQuestionClauseKeys,
  FILM_ROOM_STATUS_TOKENS,
  intervalAnswerText,
  intervalPresentation,
  momentCardText,
  unknownMomentText,
  visibleSchemaTokens
} from "../src/filmRoomLegibility";
import type { FilmRoomAskResponse, FilmRoomMoment, ReplayPayload } from "../src/types";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

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
    flagship_responses: {},
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

const pressingTable = JSON.parse(
  readFileSync(
    resolve(
      process.cwd(),
      "../../delivery/packets/gallery-2-pressing-map/pressing_map_regain_thirds_table.json"
    ),
    "utf8"
  )
);
const pressingResponse = {
  ...baseResponse,
  outcome: "expression",
  request_text: "Where does each team win the ball back?",
  answer: {
    status: "answer_ready",
    compiled_chips: [],
    document: {},
    certified_evidence_rows: pressingTable.rows,
    runtime_evidence_rows: [],
    evidence_rows_kind: "certified",
    interval_metric: {
      label: "CERTIFIED interval",
      observed: pressingTable.totals.rate_observed,
      lower: pressingTable.totals.rate_lower_bound,
      upper: pressingTable.totals.rate_upper_bound,
      unknown_count: pressingTable.totals.unknown_count,
      source: {
        evidence_kind: "certified",
        population_count: pressingTable.totals.population_count,
        a_count: pressingTable.totals.a_count,
        b_count: 0,
        c_count: pressingTable.totals.c_count,
        d1_count: 0,
        d2_count: 0,
        e_count: 0
      }
    },
    moments: [],
    moment_total_count: 0,
    visible_moment_count: 0,
    replay: null,
    executions: [],
    raw_evidence: { certified_table: pressingTable },
    provenance: {
      plan_hash: pressingTable.plan_hash,
      synthesized_document_hash: pressingTable.plan_hash,
      bound_plan_hashes: {},
      canonical_sources: {}
    }
  },
  clarification: null,
  refusal: null
} as FilmRoomAskResponse;
const pressingView = pressingMapViewModel(pressingResponse);
assert.ok(pressingView);
assert.equal(pressingView.population, 2811);
assert.equal(pressingView.located, 2758);
assert.equal(pressingView.unknown, 53);
assert.deepEqual(pressingView.thirds, { defensive: 1204, middle: 1054, attacking: 500 });
assert.equal(pressingView.rows.length, 14);
assert.equal(pressingView.rows.reduce((sum, row) => sum + row.total, 0), 2811);
assert.equal(intervalPresentation(pressingResponse.answer!.interval_metric!).findingFirst, false);
assert.equal(flagshipTabResponse({ pressing_map: pressingResponse }, "pressing_map"), pressingResponse);
assert.equal(flagshipTabResponse({ pressing_map: pressingResponse }, "counterattack_sequence_rate"), null);

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
    interval_metric: {
      label: "Certified interval",
      observed: 0.5,
      lower: 0.2,
      upper: 0.8,
      unknown_count: 5,
      source: { evidence_kind: "certified" }
    },
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
assert.deepEqual(chips, ["2 matches", "home team", "metric interval: certified"]);
assert.equal(intervalCertificationChip(null), "metric interval: loading");
assert.deepEqual(provenanceTreeView(null), {
  text: "not recorded",
  title: "Tree hash not recorded in this build"
});
assert.deepEqual(provenanceTreeView("unknown"), {
  text: "not recorded",
  title: "Tree hash not recorded in this build"
});
assert.deepEqual(provenanceTreeView("0123456789abcdef"), {
  text: "0123456789ab",
  title: "0123456789abcdef"
});
assert.deepEqual(provenanceArtifactLabels("d8179abcdef", "d8179abcdef"), ["PLAN = DOC d8179abcdef"]);
assert.deepEqual(provenanceArtifactLabels("plan123456789", "doc123456789"), [
  "PLAN plan12345678",
  "DOC doc123456789"
]);

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

const partitionPreview = {
  result_id: "certified-partition-1",
  source_kind: "certified_table_partition" as const,
  classification: "CERTIFIED_TABLE_RATE_PARTITION",
  match_id: "J03WOY",
  period: "secondHalf",
  anchor_frame_id: 100000,
  requested_evidence: {},
  chain_status: null,
  evidence_overlay: {}
};
assert.equal(chainStatusLabel(partitionPreview), "certified partition · no chain witness");
assert.equal(
  momentCollectionLabel([partitionPreview], 1),
  "1 certified table partition previews"
);

const expression = JSON.parse(
  readFileSync(
    resolve(
      process.cwd(),
      "../../delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_sequence_rate.v0.json"
    ),
    "utf8"
  )
);
const clauses = deriveQuestionClauseKeys(expression);
assert.deepEqual(
  clauses.map((clause) => `${clause.key} ${clause.text}`),
  [
    "① they win the ball back",
    "② carry it forward at least 3 m",
    "③ keep it with a completed pass"
  ]
);

const mutatedExpression = structuredClone(expression);
const thresholdClause = mutatedExpression.meaning_clauses.find(
  (clause: Record<string, unknown>) => clause.subject === "stage_2"
);
thresholdClause.value = 5;
assert.equal(
  deriveQuestionClauseKeys(mutatedExpression)[1].text,
  "carry it forward at least 5 m",
  "the rendered clause must change when the fixture's typed value changes"
);

const passMoment: FilmRoomMoment = {
  result_id: "chain-pass",
  source_kind: "chain_record",
  classification: "PASS",
  match_id: "J03WOY",
  period: "secondHalf",
  anchor_frame_id: 121915,
  match_time_ms: 3_792_000,
  requested_evidence: {},
  replay_window_id: "replay-pass",
  chain_status: "PASS",
  chain_reason: "all_stages_pass",
  evidence_overlay: {}
};
const replay = {
  replay_window_id: "replay-pass",
  overlays: {
    stage_labels: [{ stage: 2, observed_numeric_value: 11.2 }]
  }
} as ReplayPayload;
assert.equal(momentCardText(passMoment), "① 63:12 regain → ② watching the carry… → ③ pass kept");
assert.equal(momentCardText(passMoment, replay), "① 63:12 regain → ② +11.2 m carry → ③ pass kept");

const unknownMoment: FilmRoomMoment = {
  ...passMoment,
  result_id: "chain-unknown",
  chain_status: "UNKNOWN",
  chain_reason: "stage_2_window_truncated"
};
assert.equal(unknownMomentText(unknownMoment), "couldn't see whether ② happened — half ended");
assert.equal(momentCardText(unknownMoment), "couldn't see whether ② happened — half ended");
assert.deepEqual(
  orderedFilmRoomMoments([unknownMoment, passMoment]).map((moment) => moment.chain_status),
  ["PASS", "UNKNOWN"]
);

const answerSentence = intervalAnswerText({
  label: "fixture metric name",
  observed: 1 / 25,
  lower: 0.0004,
  upper: 1,
  unknown_count: 90,
  source: { population_count: 115, a_count: 1 }
});
assert.equal(
  answerSentence,
  "Of 115 regains, 1 completed the whole chain ①→②→③. 90 couldn't be fully seen — they widen the honest bounds to [0.04%, 100%]."
);
assert.deepEqual(visibleSchemaTokens(`${clauses.map((clause) => clause.text).join(" ")} ${answerSentence}`), []);

const findingFirst = intervalPresentation({
  label: "fixture",
  observed: 1,
  lower: 0,
  upper: 1,
  unknown_count: 2810,
  source: { population_count: 2811, a_count: 1, b_count: 0, e_count: 0 }
});
assert.equal(findingFirst.findingFirst, true);
assert.equal(findingFirst.headline, "1 of 2,811 seen through");
assert.equal(findingFirst.observedFraction, "1/1 (100%)");
assert.equal(findingFirst.subtitle, "could be almost never, could be always — only 1 could be fully seen.");
assert.equal(
  intervalPresentation({
    label: "fixture",
    observed: 0.8,
    lower: 0.7,
    upper: 0.9,
    unknown_count: 10,
    source: { population_count: 100, a_count: 40, b_count: 10, e_count: 0 }
  }).findingFirst,
  false
);

const coverageAnswer = {
  interval_metric: { source: { population_count: 2811 } },
  visible_moment_count: 115,
  moments: Array.from({ length: 115 }),
  raw_evidence: {
    descriptor_index: {
      coverage: {
        reason_code: "returned_classified_result_source_records",
        shown_count: 115,
        population_count: 2811,
        replay_partition_count: 1,
        completed_partition_count: 1
      }
    }
  }
} as unknown as NonNullable<FilmRoomAskResponse["answer"]>;
assert.equal(
  momentCoverageText(coverageAnswer),
  "Showing 115 of 2,811 — replay details exist only for the match-half containing the completed chain."
);

const sampledReplay = {
  ...replay,
  frame_rate_hz: 25,
  start_frame_id: 121_885,
  end_frame_id: 121_945,
  anchor_frame_id: 121_915,
  frames: [
    { frame_id: 121_885, entities: [] },
    { frame_id: 121_890, entities: [] }
  ]
} as ReplayPayload;
assert.equal(replaySamplingLabel(sampledReplay), "every 5th frame · 2.4 s window");
assert.equal(replayMatchClock(sampledReplay.frames[0], sampledReplay, passMoment), "63:10.80");

const witnessLabels = [
  { stage: 1, frame_id: 100 },
  { stage: 2, frame_id: 110 },
  { stage: 3, frame_id: 120 }
];
assert.deepEqual(visibleWitnessLabels(witnessLabels, 99), []);
assert.deepEqual(visibleWitnessLabels(witnessLabels, 110).map((label) => label.stage), [1, 2]);
assert.deepEqual(visibleWitnessLabels(witnessLabels, 999).map((label) => label.stage), [1, 2, 3]);
assert.equal(partitionVisibilityNote(1, 2811), "segment enlarged to be visible — true share 0.04%");
assert.equal(partitionVisibilityNote(10, 100), null);

assert.deepEqual(FILM_ROOM_STATUS_TOKENS, { COMPLETE: "#FFB13D", UNKNOWN: "#8B93A0" });
const css = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");
for (const selector of [".momentStatus.unknown", ".momentItem.unknown.selected", ".stageKeyChip.evidenceUnknown"]) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const rule = css.match(new RegExp(`^${escapedSelector}\\s*\\{([^}]*)\\}`, "m"));
  assert.ok(rule, `status token lint selector missing: ${selector}`);
  assert.match(rule[1].toUpperCase(), /#8B93A0/, `UNKNOWN selector escaped slate: ${selector}`);
}

const cssRule = (selector: string) => {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const rules = Array.from(css.matchAll(new RegExp(`^${escapedSelector}\\s*\\{([^}]*)\\}`, "gm")));
  const rule = rules.at(-1);
  assert.ok(rule, `composition selector missing: ${selector}`);
  return rule[1].toUpperCase();
};
assert.match(cssRule(".intervalRange"), /BACKGROUND:\s*#8B93A0/);
assert.doesNotMatch(cssRule(".intervalRange"), /OPACITY/);
assert.match(cssRule(".intervalObserved"), /BACKGROUND:\s*#FFB13D/);
assert.match(cssRule(".partitionUnknown"), /BACKGROUND:\s*#8B93A0/);
assert.match(cssRule(".unknownStrip"), /BACKGROUND:\s*#8B93A0/);
assert.match(cssRule(".stageLeader.evidenceUnknown"), /STROKE:\s*#8B93A0/);
assert.match(cssRule(".metricObserved b"), /COLOR:\s*#FFB13D/);
assert.doesNotMatch(css, /\.partitionLegend\s*\{/);

// T1 lint extension (perceptual run 3): form controls must not leak native
// grays — the scrubber track/thumb wear tokens in every engine.
assert.match(css, /input\[type="range"\]::-webkit-slider-runnable-track/);
assert.match(css, /input\[type="range"\]::-moz-range-track/);
assert.match(css, /input\[type="range"\]::-webkit-slider-thumb/);
assert.match(cssRule('.filmControls input[type="range"]::-moz-range-progress'), /BACKGROUND:\s*#FFB13D/);
const rawGrays = css.match(/#(3B3B3B|858585|808080|D3D3D3)/gi);
assert.equal(rawGrays, null, `raw native grays leaked into css: ${rawGrays}`);

const filmRoomSource = readFileSync(resolve(process.cwd(), "src/FilmRoom.tsx"), "utf8");
assert.equal((filmRoomSource.match(/momentCoverageText\(response\?\.answer\)/g) ?? []).length, 1);
assert.equal((filmRoomSource.match(/placeholder=\{response\?\.answer \? "Ask another…"/g) ?? []).length, 1);
assert.match(filmRoomSource, /className=\{`stageLeader/);

console.log("film room tests passed");
