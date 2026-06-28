export type CoachMomentInterpretation = {
  kind: "moment";
  moment_id: "line_break_no_underneath_support";
  user_query: string;
  display_answer: "Line broken. The outlet space stays empty.";
  meaning_definition: string;
  source_trace: {
    preview_rule: string;
    evidence_contract: string;
    source_plan: string;
    evidence_fields: string[];
    prohibited_claims: string[];
  };
};

export type CoachClarification = {
  kind: "clarification";
  user_query: string;
  prompt: string;
  suggestions: string[];
};

export type CoachRedirect = {
  kind: "redirect";
  user_query: string;
  prompt: string;
  suggestions: string[];
  reason: "unsupported_modality" | "not_in_preview";
};

export type CoachInterpretation = CoachMomentInterpretation | CoachClarification | CoachRedirect;

const LINE_BREAK_SUGGESTIONS = [
  "Show line breaks with no underneath outlet",
  "Find moments where the receiver breaks the second line without support",
  "Show unsupported line breaks"
];

export function interpretCoachQuery(query: string): CoachInterpretation {
  const normalized = normalize(query);
  if (!normalized) {
    return {
      kind: "clarification",
      user_query: query,
      prompt: "Ask for an observable football moment.",
      suggestions: LINE_BREAK_SUGGESTIONS
    };
  }

  if (isLineBreakSupportRequest(normalized)) {
    return lineBreakMoment(query);
  }

  if (isAmbiguousAttackRequest(normalized)) {
    return {
      kind: "clarification",
      user_query: query,
      prompt: "Pick the observable part of the attack you want to see.",
      suggestions: LINE_BREAK_SUGGESTIONS
    };
  }

  if (isExpectedModelRequest(normalized)) {
    return {
      kind: "redirect",
      user_query: query,
      prompt: "This preview stays with observed moments.",
      reason: "unsupported_modality",
      suggestions: LINE_BREAK_SUGGESTIONS
    };
  }

  return {
    kind: "redirect",
    user_query: query,
    prompt: "I can show the line-break isolation moment now.",
    reason: "not_in_preview",
    suggestions: LINE_BREAK_SUGGESTIONS
  };
}

export function coachExamplePrompts() {
  return LINE_BREAK_SUGGESTIONS;
}

function lineBreakMoment(query: string): CoachMomentInterpretation {
  return {
    kind: "moment",
    moment_id: "line_break_no_underneath_support",
    user_query: query,
    display_answer: "Line broken. The outlet space stays empty.",
    meaning_definition:
      "An observed controlled pass breaks the second observed defensive line and the declared underneath outlet region has no observed support arrival.",
    source_trace: {
      preview_rule: "coach.preview.line_break_no_underneath_support",
      evidence_contract: "q3.receiver_second_line_no_underneath_support",
      source_plan: "config/query-plans/q3_receiver_second_line_no_underneath_support.experimental.v1.json",
      evidence_fields: [
        "line_break_status",
        "target_line_rank",
        "support_region_mode",
        "support_arrival_status",
        "supporting_player_ids",
        "coverage_status"
      ],
      prohibited_claims: ["intent", "quality", "causation", "optimality", "who should have supported"]
    }
  };
}

function normalize(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function isLineBreakSupportRequest(value: string) {
  const asksForLineBreak =
    value.includes("line break") ||
    value.includes("line-break") ||
    value.includes("break the line") ||
    value.includes("breaks the line") ||
    value.includes("broke the line") ||
    value.includes("second line") ||
    value.includes("behind the line");
  const asksForNoSupport =
    value.includes("no support") ||
    value.includes("without support") ||
    value.includes("unsupported") ||
    value.includes("no outlet") ||
    value.includes("without outlet") ||
    value.includes("underneath") ||
    value.includes("alone") ||
    value.includes("isolated");
  return asksForLineBreak && asksForNoSupport;
}

function isAmbiguousAttackRequest(value: string) {
  return ["dangerous attack", "dangerous attacks", "good attack", "threatening attack"].some((phrase) =>
    value.includes(phrase)
  );
}

function isExpectedModelRequest(value: string) {
  const asksForPass = value.includes("pass") || value.includes("xg") || value.includes("expected");
  const asksForModel = ["expected", "probability", "likelihood", "xg", "xpass"].some((token) => value.includes(token));
  return asksForPass && asksForModel;
}
