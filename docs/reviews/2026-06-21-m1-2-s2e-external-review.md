# M1.2 S2E External Review

## Decision

`REJECT_KEEP_S3_BLOCKED`

The sealed S2D run exposed one compiler weakness and one evaluator weakness.
The failed run must remain preserved unchanged as diagnostic evidence and cannot
be reinterpreted as acceptance after code changes.

## Required Correction

Open **S2E - Clarification Fallback and Semantic Evaluation Codes**:

- introduce typed clarification dimensions, including `SUPPORT_DEFINITION`,
  `TIME_WINDOW`, and `DISTANCE_THRESHOLD`;
- introduce typed capability-gap codes, including `PRIMITIVE_MUTATION`,
  `CONFIRMATION_BYPASS`, `DIRECT_EXECUTION`, `PLAYER_INTENT`,
  `BODY_ORIENTATION`, `SCANNING`, `PASS_PROBABILITY`, and `OPTIMALITY`;
- add deterministic clarification fallback when semantic validation recognizes a
  known ambiguity that model repair still fails to express;
- evaluate expected semantics by exact codes rather than lexical synonyms;
- trace model decision, semantic-validation failure, repair attempt,
  deterministic fallback, and final decision source;
- report first-pass, after-model-repair, and
  after-deterministic-safety-fallback accuracy separately;
- add a dedicated sealed-acceptance command that exits nonzero when thresholds
  fail.

## Boundaries

Do not change runtime semantics, query IR, primitives, tool boundary, replay,
data pipeline, UI, or recipe families.

## Acceptance Position

S3 remains blocked after S2E until a fresh independently authored sealed mini-set
passes the acceptance thresholds. The original sealed set remains useful as a
diagnostic regression suite only.
