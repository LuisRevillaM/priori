import type { CoachMomentPayload } from "./MomentZero";

type ClaimRequirement = {
  path: string;
  equals?: unknown;
  gte?: number;
};

type ClaimFailure = {
  path: string;
  expected?: unknown;
  expectedGte?: number;
  actual?: unknown;
  reason?: string;
};

const PRODUCT_CLAIM_REQUIREMENTS: Record<string, { claimId: string; requirements: ClaimRequirement[] }> = {
  line_break_no_underneath_support: {
    claimId: "observed_line_break_without_underneath_outlet",
    requirements: [
      { path: "moment.requested_evidence.line_break_status", equals: "PASS" },
      { path: "moment.requested_evidence.support_arrival_status", equals: "FAIL" },
      { path: "moment.support_region.support_arrival_status", equals: "FAIL" }
    ]
  },
  line_break_with_underneath_outlet: {
    claimId: "observed_line_break_with_underneath_outlet",
    requirements: [
      { path: "moment.requested_evidence.line_break_status", equals: "PASS" },
      { path: "moment.requested_evidence.support_arrival_status", equals: "PASS" },
      { path: "moment.support_region.support_arrival_status", equals: "PASS" }
    ]
  },
  high_bypass_completed_pass: {
    claimId: "completed_high_bypass_pass_reached_final_third_and_retained",
    requirements: [
      { path: "moment.requested_evidence.evaluation_status", equals: "PASS" },
      { path: "moment.opponents_bypassed_count", gte: 5 },
      { path: "moment.outcome_sequence.final_third_status", equals: "PASS" },
      { path: "moment.possession_retention.status", equals: "PASS" }
    ]
  }
};

export function coachProductClaimGate(kind: string, payload: CoachMomentPayload) {
  const spec = PRODUCT_CLAIM_REQUIREMENTS[kind];
  if (!spec) {
    return {
      passed: false,
      kind,
      claimId: null,
      failures: [{ path: "kind", reason: "claim_requirements_missing" } satisfies ClaimFailure]
    };
  }

  const failures: ClaimFailure[] = [];
  for (const requirement of spec.requirements) {
    const value = dottedGet(payload as unknown as Record<string, unknown>, requirement.path);
    if ("equals" in requirement && value !== requirement.equals) {
      failures.push({ path: requirement.path, expected: requirement.equals, actual: value });
    }
    if (requirement.gte !== undefined) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric) || numeric < requirement.gte) {
        failures.push({ path: requirement.path, expectedGte: requirement.gte, actual: value });
      }
    }
  }

  return {
    passed: failures.length === 0,
    kind,
    claimId: spec.claimId,
    failures
  };
}

function dottedGet(payload: Record<string, unknown>, path: string): unknown {
  let current: unknown = payload;
  for (const part of path.split(".")) {
    if (typeof current === "object" && current !== null && part in current) {
      current = (current as Record<string, unknown>)[part];
      continue;
    }
    return undefined;
  }
  return current;
}
