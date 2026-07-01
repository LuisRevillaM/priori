# M1.2 S2B External Review

Date: 2026-06-21

Decision: APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S3

## Accepted Findings

The external review accepted S2A as a deterministic compiler-shell contract. It
proves the tool plumbing, host confirmation boundary, typed draft submission,
trace shape, and deterministic fallback.

## Blocking Findings Before S3

S2A did not prove the actual Hermes capability because:

- it was a keyword router, not a model-backed agent;
- supported prompts copied one fixed plan instead of compiling semantic
  differences into parameters;
- clarification questions could not be answered into a plan;
- the corpus was counted but not evaluated;
- session traces omitted post-compilation execute, inspect, and replay tool
  calls.

## Integrated S2B Corrections

- Added a model-backed Hermes client using the OpenAI chat completions API via
  stdlib HTTPS.
- Kept model output bounded to recipe selection, experimental draft,
  clarification, or capability gap.
- Preserved the deterministic S2A compiler as a reference fallback.
- Added language-sensitive plan generation through corridor parameter overrides.
- Added clarification round trip from ambiguous support language to a two-second
  progressive-corridor plan.
- Added full prompt-corpus execution and scoring.
- Added complete session traces including model metadata, prompt/context/schema
  hashes, raw model output, ordered tool calls, request/response hashes, host
  confirmation, execution, inspection, and replay.

## Current Controller Decision

S2B is controller-verified and ready for external review. S3 remains blocked
until S2B is externally approved or required changes are integrated.
