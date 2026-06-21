# M1.2 Specification - Grounded Tactical Query Workshop

## Product Outcome

A soccer expert can describe a positional process, inspect the model-backed compiler's interpretation, execute the bound query plan, review real moments and non-matches, label good and bad results, approve an explicit revision, and save a new immutable experimental recipe version.

## Boundary Decision

M1.2 makes a model-backed tactical query compiler a bounded client of the M1.1 deterministic runtime. It does not invent a separate agent analytics path.

M1.2 begins only after M1.1 is accepted. If M1.1 fails, the problem is architectural. If M1.2 fails, the deterministic runtime remains valuable and the problem is language interpretation or interaction design.

M1.2 proves the workshop loop and bounded compilation. It does not prove broad soccer-language understanding; M4 remains the broader reliability and tactical lexicon hardening gate.

## Current Work Order

The externally approved M1.2 opening cut is:

```text
S0  Freeze the safe capability and tool boundary.
S1  Build the manual reference workshop before model-backed compilation.
S2  Add model-backed drafting and clarification only after S1 works manually.
S3  Add feedback-driven revision diffs and immutable recipe versions.
```

The first implementation stop is after S0 and S1. S2 and S3 remain out of
scope until the manual typed-plan -> execution -> traces -> coordinate replay
-> feedback loop receives review.

External review on 2026-06-21 required an S0R/S1R boundary correction before
S2. The corrected pre-S2 boundary is:

- the model-backed compiler and the manual client submit typed plan documents and receive opaque
  host-owned handles, not filesystem paths.
- Tool schemas are generated from Pydantic request and response models.
- The host selects compatibility mode; legacy parity is restricted to the frozen
  M1 recipe.
- Result inspection, non-match inspection, replay retrieval, and feedback
  resolve through immutable `execution_id` records.
- The manual reference proof must call the same serialized dispatcher that
  model-backed compiler will use later.

A second external review on 2026-06-21 approved that direction but required one
more S0R2/S1R2 trust-boundary patch before S2:

- Every tool call is evaluated under an explicit caller profile. The model-backed compiler sees
  only the S2-safe tool surface; host/manual verification can use the full
  reference surface.
- Execution confirmation is host-owned. `validate_query_plan` creates an
  unconfirmed bound handle, and `host_confirm_bound_plan` creates the execution
  authorization. The model-backed compiler cannot mint or choose authorization IDs.
- Draft, bound, execution, replay, recipe, and authorization handles are opaque,
  pattern-validated, storage-root confined, and create-once.
- model-authored submitted plans must be `EXPERIMENTAL`.
- Non-authorable catalog nodes cannot appear in model-authored plans. The only
  approved legacy path is the exact trusted frozen M1 recipe, selected by host
  binding/hash rather than by model request.
- model-visible replay responses return replay-window handles and summary
  metadata, not local filesystem paths. Host/UI code may resolve replay artifacts
  internally.
- Target-time replay resolution maps supplied timestamps to canonical frames and
  rejects empty replay windows as explicit capability gaps.
- Model-visible dispatcher responses are validated against the generated
  Pydantic response schemas before they are accepted as tool output.

A third external review on 2026-06-21 kept S2 blocked for one final focused
S0R3/S1R3 correction:

- `inspect_non_match` and `retrieve_replay_window` must resolve an
  `EvaluationTarget` through one shared canonical target resolver, so structural
  inspection and human replay refer to the same frame.
- Target inspection must expose the resolved canonical frame, resolved match
  time, and resolution distance.
- S1 must prove both `NO_COMPATIBLE_ANCHOR` style inspection and a compatible
  anchor that fails a declared predicate.
- Content-addressed tool resources must be retry-safe: repeated identical
  calls return the existing handle, while conflicting payloads remain hard
  collisions.
- The model-visible dispatcher must validate successful and failing responses
  for every S2-visible tool, not just a representative subset.

External review then approved S2 on 2026-06-21. S2 must begin with these
guardrails:

- prove a complete experimental happy path under `CallerProfile.HERMES_S2`:
  submit -> validate -> host confirmation -> execute -> inspect -> replay;
- keep host confirmation outside model control;
- use recipe lookup and drafting without exposing filesystem paths or allowing
  model-authored approved documents;
- persist the language-to-execution trace, including original language,
  selected recipe or draft, draft/bound hashes, validation, confirmation event,
  execution ID, result IDs, and tool calls;
- retain the current language request even when semantically equivalent plans
  share content-addressed draft or bound handles;
- keep unsupported concepts as explicit capability gaps;
- defer automatic revisions, threshold tuning, second tactical family, UI polish,
  recipe promotion, and production infrastructure.

The first S2 implementation is explicitly named **S2A - Deterministic Compiler
Contract**. It remains as a deterministic reference fixture and offline fallback,
but it is not sufficient for S3 by itself.

External review required **S2B - Model-Backed Compiler and Corpus
Evaluation** before S3:

- use a real model-backed compiler client, not a keyword router;
- keep model output bounded to trusted recipe selection, typed experimental
  draft, clarification request, or structured capability gap;
- prove two semantically different supported requests create different validated
  bound-plan hashes because parameters differ;
- prove an ambiguous support request can be clarified into a validated plan;
- run and score the frozen prompt corpus rather than only counting rows;
- persist provider/model, prompt/context/schema hashes, raw structured model
  output, all model-visible tool calls, confirmation event, execution ID,
  result IDs, inspection, and replay handles.

External sealed-set review on 2026-06-21 rejected S3 unblock and opened one
narrow correction: **S2E - Clarification Fallback and Semantic Evaluation
Codes**. S2E is limited to model-orchestration safety and evaluator integrity:

- typed clarification dimensions such as `SUPPORT_DEFINITION`, `TIME_WINDOW`,
  and `DISTANCE_THRESHOLD`;
- typed capability-gap codes such as `PRIMITIVE_MUTATION`,
  `CONFIRMATION_BYPASS`, `DIRECT_EXECUTION`, `PLAYER_INTENT`,
  `BODY_ORIENTATION`, `SCANNING`, `PASS_PROBABILITY`, and `OPTIMALITY`;
- deterministic clarification fallback when semantic validation identifies a
  known ambiguity that the model failed to express as a valid clarification;
- exact-code evaluation instead of free-text synonym scoring;
- trace fields that distinguish model decision, semantic-validation failure,
  repair attempt, deterministic fallback, and final decision source;
- separate reporting for first-pass, after-model-repair, and
  after-deterministic-safety-fallback accuracy;
- a dedicated sealed-acceptance command that exits nonzero when thresholds
  fail.

S2E must not modify the tactical runtime, query IR, primitives, tool boundary,
replay, data pipeline, UI, or recipe families. The failed S2D sealed set remains
diagnostic evidence and a regression suite; it cannot become S3 acceptance
evidence after S2E changes. S3 remains blocked until a fresh independently
authored sealed mini-set passes the acceptance thresholds.

The first S2E fresh sealed mini-set exposed one more narrow correction:
**S2F - Approved Recipe Synonyms and Capability-Code Normalization**. S2F is
limited to:

- recognizing trusted/reviewed/approved ball-side defensive movement synonyms
  as requests for `ball_side_block_shift_v1`;
- validating those synonyms before accepting a model-produced capability gap;
- mapping safe refusal language such as "approval step", "execution of the
  detector", and "body angle" to stable capability-gap codes.

The S2E fresh set is diagnostic after S2F. S3 still requires a new independent
sealed set created after S2F freeze.

The first S2F fresh sealed mini-set exposed **S2G - Analyst Vocabulary Boundary
and Deterministic Supported-Family Fallback**. S2G is limited to:

- bounded analyst synonyms for the two existing supported families;
- support-clarification vocabulary such as late-arriving attacker,
  reinforcements, cover underneath, and useful reach;
- capability-code normalization for approval, primitive-mutation, glance, and
  torso-position wording;
- deterministic fallback when semantic validation already proves a supported
  recipe family or clarification requirement but model repair is malformed or
  still semantically wrong.

S2G does not add tactical primitives, runtime semantics, recipe families, or UI
behavior. The first S2F fresh set is diagnostic after S2G. S3 still requires a
new independent sealed set created after S2G freeze.

The first S2G fresh sealed mini-set exposed **S2H - Stable Agent Vocabulary
Codes and Sealed-Set Drift Control**. S2H is limited to:

- additional bounded synonyms for existing approved block-shift and corridor
  families;
- additional support-clarification aliases around receiver isolation, extra
  runners, teammate arrival, and close-enough combination options;
- unsupported-code aliases for primitive redefinition, confirmation bypass,
  direct detector launch, head checks, and hip angle;
- host-owned capability-gap code extraction from both the model refusal and the
  original request text, so safe refusals are not under-credited when the model
  summarizes the unsupported concept.

S2H does not add runtime semantics, tactical primitives, recipe families, or UI
behavior. The first S2G fresh set is diagnostic after S2H. S3 still requires a
new independent sealed set created after S2H freeze.

## Scope

M1.2 includes:

- model/tool-mediated drafting of `DraftQueryPlan` objects;
- recipe search across approved, user-saved, experimental, and deprecated recipes;
- deterministic validation and binding before execution;
- visible interpretation and confirmation before execution;
- structured feedback labels;
- known-miss inspection against a supplied `EvaluationTarget`;
- agent-proposed revisions using AST-aware semantic diffs;
- result deltas: added, removed, retained, feedback effects, and held-out warnings;
- immutable query versioning;
- deliberately simple local persistence;
- experimental recipe saving;
- a thin visual workshop loop sufficient to prove describe, draft, run, review, revise, save.

## Non-Goals

M1.2 excludes:

- new primitive implementation;
- new runtime operators;
- bypassing M1.1 binder or executor;
- arbitrary Python, SQL, filesystem editing, generated code, or primitive mutation;
- threshold auto-tuning without explicit user approval;
- complete raw-match coordinate dumps into model context;
- model training from feedback;
- automatic promotion of experimental plans to approved recipes;
- semantic vector search or embeddings;
- polished M3/M5-grade workbench design;
- production persistence, auth, cloud deployment, or match video.

## Model-Visible Tool Boundary

During S0/S1, the exposed tool surface is intentionally limited to:

```text
list_capabilities
describe_capability
submit_query_plan
validate_query_plan
execute_query_plan
inspect_result
inspect_non_match
retrieve_replay_window
```

The following tools are manual/host-only until S3:

```text
compare_query_versions
record_feedback
save_experimental_recipe
```

Model-backed drafting tools are deferred to S2 and must be added only after this
manual surface is reviewed.

The model-backed compiler may not use:

```text
arbitrary Python execution
unrestricted SQL
filesystem editing
primitive implementation access
result-row mutation
threshold auto-tuning
complete raw-match coordinate dumps
```

The model-backed compiler has access to the complete dataset through scoped tools, not by loading coordinates into model context.

`retrieve_tracking_window` returns:

- artifact or replay-window ID;
- summary metadata;
- available derived signals;
- links usable by the interface.

It must not place hundreds or thousands of coordinate rows into the model context. The browser or local workbench can retrieve replay frames directly.

## Runtime Decision Process

The model-backed compiler follows this order:

1. Search approved recipes.
2. Search user-saved recipes.
3. Compose an experimental plan only if all needed primitives/relations exist.
4. Report a capability gap if a required primitive or relation is unavailable.

Unsupported concepts must not be silently approximated. A disclosed approximation can be proposed, but it cannot execute as if it were exact.

The model-backed compiler may not fabricate explanations for non-matches. It must present the engine result, including `NO_COMPATIBLE_ANCHOR` when applicable.

## M1.2 S0 Capability Guard

The model-visible capability context is stricter than the internal catalog. S0 must expose only operator/source combinations with positive proof coverage.

Until broader collection semantics are intentionally designed and tested:

- the model-backed compiler may use `exists` and `count_at_least` only for declared `anchor_evaluations` coverage outputs;
- the model-backed compiler must not bind `exists` or `count_at_least` directly to raw relation episode collections;
- the model-backed compiler must not use generic Boolean `EpisodeSet` counting as if it were anchor-relative;
- rejected or hidden combinations must appear as explicit capability gaps, not silent approximations.

The S0 verifier must prove that the model-facing capability context enforces this safe subset even if the internal runtime contains broader compatibility paths.

## Human Visual Inspection Boundary

M1.2 requires human visual inspection, but not polished UI. The manual reference workshop in S1 must let a user open each result and relevant non-match in a coordinate replay window.

Structural traces answer why the engine matched. Coordinate replay lets the user decide whether the spatial sequence captures the intended football concept.

Final typography, transitions, guided mode, and visual polish remain outside M1.2.

## Feedback Labels

Structured feedback labels:

```text
MATCHES_INTENT
NEAR_MATCH
FALSE_POSITIVE
KNOWN_MISS
UNUSABLE_DATA
```

Feedback records contain:

- query version;
- moment ID or supplied `EvaluationTarget`;
- label;
- reason code;
- optional analyst note;
- reviewer;
- timestamp.

Feedback cannot delete results. It can only inform a proposed new query version.

## Revision Requirements

Every material revision requires user confirmation and produces a new immutable query version.

The interface must show:

- semantic plan diff;
- raw JSON diff in a developer drawer;
- prior result count;
- revised result count;
- full-corpus added results;
- full-corpus removed results;
- full-corpus retained results;
- effect on prior positive labels;
- effect on prior false positives;
- effect on known misses;
- held-out warning when labelled examples improve but held-out examples degrade.

Use AST-aware diffs. Do not rely only on textual JSON diffs.

Example semantic diff:

```text
Support definition changed

Before:
Any teammate within 12 metres

After:
Inside or progressive geometric corridor
persisting at least 0.4 seconds
```

All result deltas must be computed by the deterministic engine, not by the model-backed compiler.

## Persistence

M1.2 needs immutable recipe versions, not a platform database.

A local content-addressed file store or SQLite database is sufficient.

Every saved version preserves:

- parent version;
- draft plan;
- bound plan;
- semantic diff;
- query hash;
- execution IDs;
- feedback references;
- creator;
- timestamp.

Saved versions may never be overwritten. Previous versions remain executable.

## Recipe States

```text
APPROVED
Reviewed and regression-tested.

USER_SAVED
Saved intentionally by an analyst or workspace.

EXPERIMENTAL
Agent-authored composition not independently validated.

DEPRECATED
Retained for history but no longer recommended.
```

Experimental recipes cannot promote themselves.

## Quantitative Agent Evaluation

Before M1.2 begins, freeze a test corpus containing at least:

```text
20 supported requests
10 ambiguous requests
10 unsupported requests
10 revision instructions
```

Initial acceptance:

- 100 percent schema-valid plan or explicit refusal;
- at least 90 percent correct capability/recipe selection for supported requests;
- at least 90 percent appropriate clarification for ambiguous requests;
- 100 percent explicit capability-gap handling for unsupported primitives;
- zero unconfirmed material revisions;
- zero invented primitive or operator IDs.

M4 can later harden broader language reliability with a larger corpus.

## Internal Gates

### S0 - Capability and Tool Boundary

Hard acceptance:

- generated capability context exists at `generated/capability-context.json`;
- the exposed tool list is exactly the S0/S1 list above;
- tool request and response schemas are concrete, generated schemas rather than
  placeholders;
- `exists` and `count_at_least` are agent-visible only for declared
  `anchor_evaluations`;
- host-owned complexity ceilings are visible and enforced by validation;
- unsupported concepts fail as capability gaps;
- manual plan validation works without the model-backed compiler;
- clients use `draft_plan_id`, `bound_plan_id`, `execution_id`, and
  `replay_window_id` handles instead of local paths.
- repeated submit, validate, execute, and replay calls are idempotent for
  identical content-addressed resources and fail only on true handle collision;
- every S2-visible model-facing tool has both successful and failing
  response-schema validation coverage.

### S1 - Manual Reference Workshop

Hard acceptance:

- approved M1 recipe and experimental corridor recipe both execute manually;
- returned results expose ranked rows, predicate traces, requested evidence,
  and coordinate replay windows;
- known-timestamp inspection explains non-matches with failed/unknown
  predicates;
- known-timestamp inspection and target replay resolve to the same canonical
  frame;
- target inspection includes a real compatible-anchor predicate-failure example,
  not only a no-compatible-anchor case;
- all manual actions flow through the same serialized dispatcher the model-backed compiler will use
  later;
- feedback labels `MATCHES_INTENT`, `NEAR_MATCH`, `FALSE_POSITIVE`,
  `KNOWN_MISS`, and `UNUSABLE_DATA` are recorded through a schema-valid tool;
- an experimental recipe can be saved as an immutable content-addressed
  version;
- a plain local replay workshop artifact is generated;
- no model calls, canned prompts, or hardcoded result moments are used.

### Gate A - Tool Boundary and Capability Context

Hard acceptance:

- model-visible tool surface is bounded to the approved tools;
- no filesystem editing, code execution, SQL, primitive mutation, result-row mutation, threshold auto-tuning, or raw coordinate dumps are available;
- generated capability context includes primitives, relations, operators, recipe states, limitations, and supported evidence fields;
- unsupported concepts produce capability-gap responses;
- manual plan entry remains usable without the model-backed compiler.

### Gate B - Draft, Bind, Confirm, Execute

Hard acceptance:

- the model-backed compiler produces only schema-valid draft plans or explicit refusals;
- all plans are validated/bound by the deterministic compiler before execution;
- user sees the interpretation before execution;
- every assistant execution records original text, draft plan, bound plan, confirmation, result IDs, hashes, scope, and provenance;
- the same bound plan produces identical results whether invoked manually or by the model-backed compiler;
- manual plan inspector remains usable when the model-backed compiler is unavailable.

### S2A - Deterministic Compiler Contract

Hard acceptance:

- supported progressive-corridor prompts compile to `EXPERIMENTAL` typed draft
  plans through `dispatch_model_visible(..., caller_profile=HERMES_S2)`;
- approved recipes are selected as trusted host records, not submitted as
  model-authored approved documents;
- ambiguous support language asks clarification before drafting;
- unsupported concepts such as body orientation, intent, optimality,
  communication, video, and pass probability return explicit capability gaps;
- host confirmation remains outside the compile response and outside model-visible tool
  calls;
- after host confirmation, execution, result inspection, and replay retrieval
  succeed through the agent caller profile;
- semantically equivalent language requests may share content-addressed handles
  while preserving separate language traces;
- the initial evaluation corpus contains at least 20 supported, 10 ambiguous,
  and 10 unsupported prompts.

### S2B - Model-Backed Compiler And Corpus Evaluation

Hard acceptance:

- a real model-backed compiler client receives the tactical system instructions,
  safe capability context, tool schemas, trusted recipe summaries, user request,
  and clarification history;
- model output is bounded to trusted recipe selection, typed experimental draft,
  clarification request, or structured capability gap;
- every model-authored draft is submitted, bound, and validated through
  `dispatch_model_visible(..., caller_profile=HERMES_S2)`;
- two supported prompts with different tactical meanings produce different
  validated bound-plan hashes through parameter changes, not cosmetic IDs;
- an ambiguous support prompt asks clarification, and an answer such as
  "Progressive corridor within two seconds" produces a validated plan with
  `corridor_max_window_seconds=2.0`;
- the corpus evaluation report contains every prompt, expected category, actual
  category, selected recipe or capability, draft validity, clarification or gap,
  invented identifier count, tool calls, and review outcome;
- corpus thresholds are met: 100 percent schema-valid plan or explicit refusal,
  at least 90 percent supported accuracy, at least 90 percent ambiguous
  clarification accuracy, 100 percent unsupported capability-gap accuracy, zero
  invented IDs, zero unauthorized tool calls, and zero unconfirmed executions;
- session traces record model/provider/version, system prompt hash, capability
  context hash, tool schema hash, raw structured model outputs, all tool calls
  with request/response hashes, host confirmation event, execution ID, result
  IDs, inspection, and replay handles.

### S2C - Agent Identity, Strict Output, And Blind Evaluation

External S2B review approved progress but blocked S3 until the compiler stopped
over-claiming Hermes runtime integration and proved stricter language reliability.

Hard acceptance:

- S2 is represented honestly as `ModelBackedTacticalQueryCompiler`, an
  agent-neutral model-backed compiler over the bounded caller profile, not as a
  completed Hermes runtime integration;
- model output is validated by a strict action-specific Pydantic union with
  `extra="forbid"`, action-specific required fields, parameter bounds,
  approved recipe IDs, nonempty clarification questions, nonempty capability
  gaps, and allowed evidence IDs;
- invalid model output receives at most one explicit repair turn and otherwise
  fails closed as `MODEL_OUTPUT_INVALID`;
- model outputs must also pass semantic validation against explicit
  capability/recipe rules: supported corridor aliases cannot be refused,
  unsupported concepts must be named, support/help/second-runner language must
  clarify, and answered clarifications are authoritative;
- failed plan binding returns `PLAN_VALIDATION_FAILED`, never
  `DRAFT_VALIDATED`;
- supported evaluation rows pass only when the correct recipe is selected or
  drafted, the plan binds successfully, requested parameters are correct, and no
  unintended parameter override is introduced;
- ambiguous rows pass only when the clarification addresses the expected
  ambiguity;
- unsupported rows pass only when the capability gap names the material
  unsupported concept;
- a separate blind corpus from `config/evaluation/m1_2_s2c_blind_corpus.json`
  is scored and copied to artifacts without being included as compiler prompt
  examples;
- confirmed execution traces include session ID, original language,
  clarification answers, model/provider/version, temperature/seed where
  available, system prompt hash, capability-context hash, full tool-schema hash,
  trusted-recipe-context hash, raw structured model output, all ordered tool
  calls, host confirmation event, execution ID, result IDs, inspection handles,
  and replay handles;
- adversarial tests prove negative parameters, excessive windows, unsupported
  parameter names, wrong units, and hostile complexity limits fail validation;
- prompt-injection and unauthorized-action tests remain fail-closed.

### S2D - Session Provenance And Evaluation Integrity

External S2C review approved the core compiler but blocked S3 until provenance
and evaluation integrity were strong enough for feedback and revision lineage.

Hard acceptance:

- every compiler request receives a host-owned `session_id` and `turn_id`;
- clarification answers reference the original clarification turn through
  `parent_turn_id`;
- session records contain the original request, model questions, user answers,
  model decisions, draft/bound plan hashes, confirmation event, execution ID,
  inspection handle, and replay handle;
- every model decision trace records all attempts, raw outputs, schema
  validation results, semantic validation results, `repair_count`, and the final
  accepted output;
- evaluation summaries report first-pass accuracy, after-repair accuracy, and
  repair rate by category;
- the previous "blind" corpus is described as a separate held-out regression set,
  not proof of external blindness;
- the verifier supports an externally sealed prompt set at
  `config/evaluation/m1_2_s2d_sealed_prompt_set.json`;
- S3 remains blocked until an owner or independent reviewer supplies that sealed
  set after code/prompt freeze and the frozen compiler run is preserved;
- `requested_evidence` is not accepted in the model decision schema until it has
  real execution semantics;
- product/spec/verifier language uses "model-backed compiler", "agent caller
  profile", and "model-visible tool boundary"; "Hermes integration" is reserved
  for a real Hermes adapter.

### Gate C - Feedback and Non-Match Inspection

Hard acceptance:

- analyst can label returned moments with structured labels;
- analyst can provide an `EvaluationTarget`;
- engine evaluates that target against the bound plan and returns failed/unknown predicates or `NO_COMPATIBLE_ANCHOR`;
- feedback persists across restart;
- feedback remains associated with the query version on which it was given;
- feedback cannot silently alter results.

### Gate D - Revision and Versioning

Hard acceptance:

- the model-backed compiler proposes explicit revisions using available primitives/relations only;
- semantic and raw diffs are visible;
- full-corpus added, removed, and retained result sets are inspectable;
- previous versions remain reproducible and executable;
- old recipe versions remain immutable;
- material revisions require confirmation;
- revisions that improve labelled examples but degrade held-out examples produce an overfitting warning;
- saved recipes are immutable versions.

### Gate E - Workshop Thin Slice

Hard acceptance:

- user can complete the full describe, draft, run, review, revise, save loop;
- every result opens in real coordinate replay;
- predicate values displayed in the UI equal evidence values;
- no featured result is hardcoded;
- no canned assistant responses or hardcoded demo prompts are present.

### Gate F - Agent Evaluation

Hard acceptance:

- frozen M1.2 request corpus exists;
- supported, ambiguous, unsupported, and revision-instruction tests meet the quantitative thresholds;
- hidden paraphrases are included;
- all tool calls are logged;
- zero invented primitive or operator IDs occur.

## Required Artifacts

```text
delivery/m1.2/SPEC.md
delivery/m1.2/status.yaml
generated/capability-context.json
artifacts/m1.2/gate-s0-verification-report.json
artifacts/m1.2/gate-s1-verification-report.json
artifacts/m1.2/workshop/index.html
artifacts/m1.2/workshop/manual-workshop-data.json
artifacts/m1.2/workshop/feedback-records.jsonl
artifacts/m1.2/workshop/recipes/*.json
artifacts/m1.2/agent-evaluation-corpus.json
artifacts/m1.2/agent-evaluation-report.json
config/evaluation/m1_2_s2c_blind_corpus.json
artifacts/m1.2/agent-blind-evaluation-corpus.json
artifacts/m1.2/agent-blind-evaluation-report.json
artifacts/m1.2/gate-s2-verification-report.json
artifacts/m1.2/hermes-s2-trace-report.json
artifacts/m1.2/workshop-loop-trace.json
artifacts/m1.2/query-version-manifest.json
artifacts/m1.2/feedback-records.jsonl
artifacts/m1.2/revision-delta-report.json
artifacts/m1.2/persistence-restart-report.json
artifacts/m1.2/verification-report.json
```

## Required Commands

```bash
make m1-1-verify
make m1-2-verify
```

`make m1-2-verify` must fail if the model-backed compiler bypasses the binder, unsupported concepts are silently approximated, revisions happen without confirmation, prior versions are unreproducible, feedback is lost across restart, result deltas are model-computed, or workshop evidence is hardcoded.

## Anti-Reward-Hacking Rules

- The model-backed compiler never executes generated code.
- The model-backed compiler never mutates primitive implementations.
- The model-backed compiler never silently changes thresholds or semantics.
- Agent memory cannot change query semantics; persisted recipes and feedback are explicit and versioned.
- Unsupported concepts produce capability gaps, not nearby substitute executions.
- Experimental, user-saved, approved, and deprecated recipes remain visually distinct.
- No result is deleted to satisfy feedback.
- Known misses remain visible even when a revision still fails to find them.
- Revisions cannot claim improvement from labelled examples alone; held-out effects must be shown.
- Canned demo prompt mappings are forbidden.

## Stop Conditions

Stop and reassess if:

- The model-backed compiler succeeds only on canned prompts;
- unsupported prompts execute as approximate supported prompts;
- feedback causes hidden threshold tuning;
- query versions cannot be reproduced;
- result deltas cannot be explained;
- the workshop UI bypasses the M1.1 runtime;
- the assistant becomes necessary for manual execution;
- old recipe versions cannot be executed after a restart.
