# Milestones

> **Historical document (2026-07-01 note).** This is the original M1–M6
> product roadmap. M1, M1.1 (via the M1.1S correction arc), and the M1.2
> S0–S2I slices were completed; per-milestone truth lives in
> `delivery/*/status.yaml` and `delivery/ledger.jsonl`, and some headers below
> reflect mid-flight states that were later superseded (e.g. M1.1's rejection
> was resolved by M1.1S; M2's family pivoted from Wide-Channel Support
> Collapse to High-Bypass Completed Pass). **Ongoing work is governed by the
> protected AFL milestone contract**
> (`delivery/autonomous/afl_milestone_contract.yaml`); do not extend this
> ladder. See `CURRENT_STATE.md` for the document hierarchy.

This roadmap ends at a completely independent, meeting-ready demo built from the public IDSSE/DFL dataset. It does not include Priori SDK/API integration, provider adapter readiness, private data, production deployment, or match-video ingestion.

## Dependency Graph

The milestones are not a strictly linear waterfall. The active dependency graph is:

```text
M1 Evidence Spine
        |
        v
M1.1 Composable Query Runtime
        |
        v
M1.2 Grounded Query Workshop
        |
        v
M2 Second Approved Tactical Family
        |
        v
M3 Analyst Workbench
       / \
      v   v
M5 Experience and Visual QA     M4 Agent Reliability and Lexicon Hardening
       \                         /
        \                       /
         v                     v
              M6 Demo Release
```

M1.1 and M1.2 are deliberately split. M1.1 proves the deterministic composable query runtime without Hermes. M1.2 proves Hermes and the feedback/versioning workshop as a client of that runtime. M4 remains architecturally first-class but not release-critical; it hardens the agent after the workbench exists and can run in parallel with M5. M6 integrates the assistant only if M4 passes its ship/cut gate.

## M1 - Verified Ball-Side Block-Shift Evidence Spine

Status: `VERIFIED_CONTROLLER_ONLY`

Outcome: From real IDSSE tracking data, produce auditable moments where the ball enters a wide area, the defending block shifts toward it, and the attack subsequently switches, retains without switching, or loses possession.

Acceptance requires:

- Gate A accepted: `J03WOH` source lock, Floodlight parse, canonical Parquet, raw XML parity, quality/orientation, real 30-second coordinate replay, and resource report;
- Gate B accepted: remaining six matches source-locked and canonicalized with corpus-wide invariants and holdout orientation checks;
- Gate C accepted: query calibrated only on `J03WOH`, frozen, evaluated unchanged on the Fortuna evaluation corpus, bundled, replayed, and independently reviewed;
- at least eight accepted real moments across at least three Fortuna evaluation matches;
- at least two `SWITCHED` and at least two non-`SWITCHED` accepted outcomes;
- every accepted result recomputable from canonical data;
- every accepted result replayable from generated evidence;
- independent review of source, primitives, query results, replay integrity, and proof pack;
- semantic gold set exists for Query 1 with clear positives, borderline accepted cases, clear negatives, threshold near misses, data-quality failures, allowed claims, and disallowed claims;
- no synthetic, mocked, manually selected, or manually edited accepted evidence.

Detailed spec: `delivery/m1/SPEC.md`

Current verification note: Gate A, Gate B, and Gate C pass automated verification and controller-only review. Final owner acceptance remains pending, and independent review was waived under the current controller-only execution mode.

## M1.1 - Composable Tactical Query Runtime

Status: `REJECTED_EXTERNAL_REVIEW_PENDING_M1_1R`

Outcome: A developer can add a validated tactical detector plan, bind it against approved primitives and relations, execute it over the real IDSSE corpus through a generic deterministic runtime, inspect every predicate trace, and replay resulting moments without adding query-specific backend code.

Correction note: the first implementation passed controller gates but failed independent external implementation review on 2026-06-19. M1.2 is blocked until the corrective M1.1R gates in `delivery/m1.1/CORRECTIVE_SPEC.md` pass and receive external approval or required changes are integrated.

Scope:

- typed Tactical Query IR v1;
- separated `RecipeDefinition`, `QueryInvocation`, `DraftQueryPlan`, `BoundQueryPlan`, and `QueryExecution`;
- deterministic compiler/binder from draft plans to bound plans;
- primitive and relation catalog with explicit temporal type, payload type, cardinality, units, limitations, missing-data semantics, and evidence fields;
- tri-state predicate logic: `TRUE`, `FALSE`, `UNKNOWN`;
- generic executor with no query-ID branches;
- M1 Ball-Side Block Shift represented as an approved plan;
- complete parity against the legacy M1 detector, which remains a read-only oracle;
- narrowed dynamic relation primitive: `geometric_progressive_corridor`;
- one experimental relation-based composition added as plan data;
- predicate traces for matches and formal `EvaluationTarget` non-match windows;
- developer-facing plan/result inspector artifacts.

Non-goals:

- no Hermes or natural-language query compilation;
- no analyst feedback loop;
- no polished workbench;
- no arbitrary Python, SQL, generated code, or custom expressions;
- no runtime primitive invention or mutation;
- no optimality, intent, expected-pass, best-pass, or missed-opportunity claims.

Acceptance requires:

- clean committed M1 baseline exists before implementation;
- reviewed M1 semantic gold set exists before parity is claimed;
- M1 parity is complete on the frozen M1 corpus and result set;
- binder rejects invalid primitives, operators, units, cardinality, temporal references, evidence fields, and over-complex plans;
- missing data never silently evaluates as false;
- bound-plan hashes are stable across processes;
- repeated execution produces identical moment IDs and traces;
- `geometric_progressive_corridor` relation intervals are deterministic and reconstructable from real coordinates;
- corridor V1 remains a geometric forward connection and excludes pass probability, body orientation, intention, optimality, and unreliable offside or defensive-line claims;
- an experimental block-shift-plus-opposite-corridor plan executes without new backend detector code;
- every result and supplied non-match window has a complete predicate trace;
- a forced non-match window can return `NO_COMPATIBLE_ANCHOR`;
- replay coordinates match canonical source data;
- unsupported or invalid plans fail visibly.

Detailed spec: `delivery/m1.1/SPEC.md`

## M1.2 - Grounded Tactical Query Workshop

Status: `PLANNED`

Outcome: A soccer expert can describe a positional process, inspect Hermes's interpretation, execute the bound query, review real moments and non-matches, label good and bad results, approve explicit revisions, and save immutable experimental recipe versions.

Scope:

- Hermes tool-mediated drafting of `DraftQueryPlan` objects;
- recipe search across approved, user-saved, experimental, and deprecated recipes;
- visible interpretation and confirmation before execution;
- structured feedback labels;
- known-miss inspection against supplied `EvaluationTarget` windows;
- AST-aware semantic diffs for proposed revisions;
- full-corpus added/removed/retained result deltas;
- immutable query versioning;
- deliberately simple immutable local persistence;
- quantitative agent evaluation corpus;
- thin visual workshop loop proving describe, draft, run, review, revise, save.

Non-goals:

- no new primitives or runtime operators;
- no bypassing the M1.1 binder/executor;
- no arbitrary code, SQL, filesystem editing, primitive mutation, or result-row mutation;
- no raw million-row coordinate dumps into model context;
- no model training from feedback;
- no automatic promotion of experimental plans;
- no semantic vector search or embeddings;
- no M3/M5-grade polish.

Acceptance requires:

- Hermes produces only schema-valid draft plans or explicit refusals;
- ambiguous requests ask meaningful clarifying questions;
- unsupported primitives are not silently approximated;
- every execution records draft, bound plan, hashes, scope, results, and provenance;
- feedback cannot delete results;
- material revisions require confirmation and produce immutable versions;
- previous versions remain reproducible;
- added, removed, and retained results are inspectable and computed by the engine;
- feedback persists across restart;
- old recipe versions remain executable;
- unsupported/revision evaluation meets frozen quantitative thresholds;
- revisions that improve labelled examples but degrade held-out examples produce an overfitting warning;
- manual plan inspector remains usable when Hermes is unavailable;
- no canned assistant responses or hardcoded demo prompts exist.

Detailed spec: `delivery/m1.2/SPEC.md`

## M2 - Second Approved Tactical Family and Capability Catalog

Status: `PLANNED`

Outcome: A second meaningfully different tactical family is implemented and promoted to an approved recipe on top of the M1.1 runtime, while the capability catalog and common evidence envelope prove they are genuinely shared.

Scope:

- retain the M1 `Ball-Side Block Shift` query family as an approved recipe;
- add `Wide-Channel Support Collapse`, or replace it by ADR if it proves tactically unstable;
- maintain a versioned primitive and relation registry;
- publish a generated capability catalog for every query family;
- define two query-specific typed schemas;
- define one common result envelope with query-specific evidence payloads;
- run deterministic execution through the M1.1 runtime;
- validate parameters and declared ranges;
- generate comparison pairs;
- cache query results by source, query, and parameter hashes;
- generate JSON Schema and TypeScript contract types from authoritative Pydantic models.

By the end of M2, every query family must expose a generated capability description containing:

- query ID and version;
- what it measures;
- what it does not establish;
- parameter schema and valid ranges;
- required primitives;
- result classifications;
- evidence schema;
- supported filters;
- example natural-language requests;
- related unsupported concepts.

The manual workbench, CLI, tests, and assistant tools must use the same capability catalog. There must never be separate agent query logic.

M2 follows a strict second-query-first rule:

```text
Query family 1 works
-> Query family 2 works independently
-> compare actual duplication
-> extract only proven common structures
```

Do not create a generic tactical DSL, universal query-planning engine, extensible visualization grammar, or broad base classes for hypothetical future query types before the second query works independently. Abstractions must remove duplication that exists now, not prepare for an imagined third query.

The exact second query remains subject to M1 evidence. It must:

- use meaningfully different primitives from M1;
- produce defensible real examples;
- avoid intent or optimality claims;
- support at least two useful outcome classes;
- visibly justify classification in replay.

Non-goals:

- no natural-language compilation;
- no new assistant capability beyond the M1.2 workshop boundary;
- no arbitrary tactical DSL;
- no third full query family;
- no polished UI;
- no production API;
- no model-generated tactical logic.

Acceptance requires:

- both query families are frozen before evaluation;
- Query 1 continues to pass M1 regression gates;
- Query 1 continues to pass M1.1 runtime parity;
- Query 2 returns at least six accepted real moments across at least three matches;
- Query 2 includes at least two outcome classes;
- at least two defensible comparison pairs exist for each family;
- every accepted moment passes independent predicate recomputation;
- semantic gold set exists for each query family, with 15-25 reviewed moments per family across clear positives, borderline accepted cases, clear negatives, threshold near misses, and data-quality failures;
- designated monotonic parameter tests pass;
- invalid parameter combinations are rejected before execution;
- repeated identical queries return identical moment IDs and order;
- shared provenance, match, timing, outcome, quality, and replay fields are common;
- query-specific evidence remains isolated;
- schema/type generation has no drift.

Planner consultation after M2 should challenge whether the common contract is genuinely shared, whether either query relies on weak assumptions, and whether any third analytical flow should be a preset/filter rather than a full query family.

## M3 - Analyst Workbench v1

Status: `PLANNED`

Outcome: A complete functional analyst workflow lets a user select, parameterize, execute, browse, replay, explain, and compare real results from both tactical query families.

Core workflow:

- query catalog for `Ball-Side Block Shift` and `Wide-Channel Support Collapse`;
- perspective team, match, outcome, quality, and threshold controls;
- typed execution through the deterministic local runtime;
- result rail with match, time, query family, classification, principal evidence, and quality;
- coordinate-only pitch replay with players, ball, trails, possession, overlays, landmarks, smooth play, and scrubbing;
- evidence panel tying every explanatory statement to structured measurements;
- storyboard/timeline for each query family;
- comparison mode for outcome contrasts and synchronized anchor-based replay;
- provenance and caveats panel.

Every manual or assistant-driven execution must produce one query trace:

```text
request source
-> selected capability
-> typed query and parameters
-> validation result
-> dataset and match scope
-> execution/cache record
-> returned moment IDs
-> evidence bundle IDs
-> generated explanation, if present
```

The trace is required even for cache hits. It prevents hidden substitutions, fake assistant behavior, and preselected-result fallbacks.

M3 may introduce a thin local Python HTTP layer around the deterministic query engine for demo/runtime ergonomics. It is not a production service.

Non-goals:

- no AI assistant;
- no final motion system;
- no guided presenter mode;
- no cloud deployment;
- no authentication;
- no multi-user state;
- no video pane;
- no general-purpose dashboard builder.

Acceptance requires:

- both query families execute through the same workbench shell;
- no production build contains hardcoded moment coordinates;
- every displayed result comes from an actual query execution;
- every accepted result can be opened and replayed;
- parameter changes produce an updated typed query and execution record;
- every execution produces a query trace with execution ID, source, selected capability, typed query, dataset/query/cache hashes, returned moment IDs, and evidence bundle IDs;
- empty and invalid states are designed;
- comparison mode works with at least two real pairs per query family;
- deep links restore query, parameter, result, and replay position;
- keyboard play, pause, scrub, and landmark navigation work;
- app functions with network access disabled after provisioning;
- Playwright completes the principal analyst journeys;
- no browser console errors occur during the full test corpus;
- UI displays no unsupported causal or optimality claim.

Planner consultation after M3 is the main product checkpoint: review whether the interface communicates a tactical argument, whether comparison mode is the strongest hero flow, whether parameters are understandable, and whether an assistant should be built, reduced, or cut.

## M4 - Agent Reliability and Tactical Lexicon Hardening

Status: `CONDITIONAL`

Outcome: The M1.2 Hermes workflow is hardened against realistic football language, ambiguity, unsupported concepts, and revision requests before it is allowed into the meeting demo.

M4 is a ship gate, not an unconditional feature commitment. The final demo must remain complete without it.

M4 may begin only after M1.2 has passed and M3 has a functioning workbench/query trace. It can run in parallel with M5. M4 must reach a `SHIP_BEHIND_FEATURE_FLAG` or `CUT_FROM_MEETING_DEMO` decision before M6 integration begins.

Tool surface remains bounded to deterministic runtime and workshop tools:

- `list_query_capabilities`
- `search_recipes`
- `describe_query`
- `describe_primitive`
- `describe_relation`
- `draft_query_plan`
- `validate_query_plan`
- `execute_query_plan`
- `inspect_result_trace`
- `inspect_non_match`
- `open_moment`
- `compare_moments`
- `record_feedback`
- `save_experimental_recipe`

Forbidden tool surface:

- raw filesystem;
- raw tracking coordinates;
- code execution;
- primitive modification;
- primitive or recipe mutation outside approved versioned tools;
- unrestricted SQL.

Runtime expansion and development expansion are separate:

- the runtime agent may search recipes, draft plans, clarify ambiguity, execute bound plans, inspect moments, compare versions, explain evidence, record feedback, and identify capability gaps;
- the runtime agent may not invent primitives, change detectors, modify global thresholds, write production code, bypass the binder, or hot-load new query families;
- for unsupported concepts, it may produce a version-controlled proposal describing requested concept, related capabilities, missing data/primitives, possible operational definition, assumptions, tests, and acceptance requirements.

Non-goals:

- no autonomous discovery over raw coordinates;
- no generated detector code;
- no modification of tactical definitions at runtime;
- no freeform tactical claims;
- no assistant-only capability;
- no hiding query substitutions;
- no multi-agent research workflow in the meeting demo.

Ship gates:

- frozen assistant evaluation corpus: 30 supported paraphrases, 15 ambiguous requests, 15 unsupported requests, and 15 revision/feedback requests;
- 100% of outputs are schema-valid or explicitly rejected;
- at least 90% of supported prompts select the correct recipe or draft a materially correct plan;
- at least 90% of ambiguous prompts ask a relevant clarification rather than guessing;
- 100% of unsupported prompts avoid silently executing a supported substitute;
- 100% of material revisions require confirmation and produce a visible semantic diff;
- every execution requires visible interpretation or confirmation;
- all tool calls are logged;
- assistant cannot access raw tracking;
- assistant never invents a metric absent from the primitive registry;
- manual workbench remains fully usable when assistant is disabled;
- meeting package has a no-network fallback path.

If the assistant misses these gates, cut it from the meeting flow. Do not disguise it with scripted prompts or canned responses.

Planner consultation after M4 ends with a binary decision: `SHIP_BEHIND_FEATURE_FLAG` or `CUT_FROM_MEETING_DEMO`.

## M5 - Demo Experience, Motion, and Visual QA

Status: `PLANNED`

Outcome: The functional workbench becomes delightful, immediately legible, and choreographed for a persuasive live demonstration without compromising analytical honesty.

Scope:

- smooth coordinate replay at display refresh rate from 25 Hz source data;
- deliberate layer entry/exit animations;
- storyboard landmark transitions;
- synchronized comparison playback around anchors;
- reduced-motion behavior;
- progressive evidence reveal;
- guided demo mode with one-click start/reset and keyboard next/back;
- ability to leave guided mode and explore freely;
- consistent typography, spacing, team distinction, selected states, and time-state hierarchy;
- designed empty, loading, warning, unsupported, and malformed states;
- microcopy that distinguishes observed, derived, classified, inferred, and unsupported.

Once M5 begins, analytical changes are prohibited except to fix a verified defect. No new primitives, query semantics, thresholds, or result-selection rules may be introduced during experience polish.

Non-goals:

- no new primitives;
- no new detector;
- no third query family;
- no architectural rewrite;
- no assistant expansion;
- no production feature work.

Acceptance requires:

- replay visual cadence is stable on a documented reference laptop;
- p95 scrubbing response stays within 100 ms;
- switching moments does not freeze the interface;
- comparison mode remains usable under simultaneous playback;
- no clipping, overlap, or unreadable evidence at `1280x720`, `1440x900`, and `1920x1080`;
- at least three independent reviewers can run a query, understand why a result matched, move through setup/anchor/outcome, compare two moments, and find provenance/limitations without coaching;
- primary guided presentation completes in six to eight minutes;
- compressed guided flow completes in three minutes;
- both flows reset without reloading the project;
- no required step depends on the assistant;
- screenshot matrix, visual-regression checks, reduced-motion review, color-contrast review, empty/error/warning review, and guided-flow recordings exist;
- no unresolved severity-one visual defect.

Planner consultation during M5 should happen twice: a midpoint visual critique using screenshots/short recordings, then a final narrative critique of the live presentation as an argument.

## M6 - Meeting-Ready Independent Demo Release

Status: `PLANNED`

Outcome: A frozen, self-contained, evidence-backed demo can be launched offline on a clean machine, presented reliably, explored after the scripted flow, and defended technically.

Scope:

- pinned raw-data manifest;
- frozen canonical and feature versions;
- frozen query versions;
- accepted evidence corpus;
- built query runtime;
- built workbench;
- assistant only if M4 passed;
- licenses and attribution;
- proof manifest;
- versioned release identifier;
- one-command `make demo` or equivalent launcher;
- preflight checks for data version, feature hashes, query hashes, evidence bundles, local port, browser compatibility, and assistant availability if enabled;
- six-to-eight-minute primary script;
- three-minute compressed script;
- technical architecture one-pager;
- query-definition appendix;
- limitations statement;
- dataset attribution;
- meeting FAQ;
- backup screenshots and generated coordinate-replay screen recording.

Non-goals:

- no new feature development after code freeze;
- no Priori integration;
- no production hosting;
- no video synchronization;
- no private data;
- no provider-generalization work;
- no live match processing;
- no multi-user support;
- no cloud architecture;
- no model training.

Acceptance requires:

- clean-machine proof: provisioned release starts without source-code edits;
- core demo works with network access disabled;
- all featured queries execute;
- all featured evidence bundles replay;
- guided and free-exploration modes work;
- no missing asset or console error occurs;
- three consecutive primary-flow rehearsals complete without reset failure, dead link, unexplained query result, timing overrun, or developer intervention;
- independent technical review passes provenance, deterministic execution, query integrity, and replay correspondence;
- independent product review passes clarity, interaction, narrative, visual quality, and meeting fitness;
- final proof records release commit, raw manifest hash, feature-store hash, query hashes, accepted result IDs, app build hash, verification report hash, review reports, and assistant ship/cut decision.

## Demo-Complete Definition

The project is complete only when:

- every displayed coordinate comes from real IDSSE source data;
- every accepted result traces through canonical data to raw file hashes;
- two distinct tactical query families are implemented;
- both query families have frozen definitions, independent evaluation, multiple real moments, and multiple outcomes;
- an analyst can choose a tactical question, select scope/parameters, execute it, browse ranked moments, replay a moment, inspect why it matched, move through tactical phases, compare it with another result, and inspect provenance/limitations;
- replay is smooth, evidence reveal is legible, comparison is understandable, and guided flow is rehearsable/resettable;
- core demo runs offline with one command on a clean machine;
- backup presentation path exists;
- assistant either ships behind a feature flag after passing M4 or is absent.

## Cross-Cutting Invariants

- Minimal coordinate replay begins in Gate A; polished visualization is later, but replay is never deferred.
- No silent fallback: parser failure, schema mismatch, unknown capability, unsupported tactical request, invalid parameter, missing evidence field, empty result, assistant unavailability, and cache mismatch must fail visibly.
- The runtime agent operates approved capabilities; coding agents can implement new capabilities only through version-controlled delivery work.
- Featured moments must be complete outputs of frozen queries, never hand-authored clips.
- Query controls must change the actual typed query.
- Cache keys must include dataset version, query version, parameters, perspective, and match scope.
- Screenshots are never proof without a corresponding bundle, execution record, and query/source hash.

## Explicit Out Of Scope

- Priori SDK or API integration.
- Priori private data.
- Reverse engineering Priori metrics.
- Provider-neutral ingestion architecture.
- Additional tracking providers.
- Production deployment.
- Cloud infrastructure.
- Authentication and authorization.
- Multi-user workflows.
- Live or near-live match processing.
- Match-video ingestion or synchronization.
- Club data warehouse integration.
- Production-scale performance.
- Mobile application.
- Model training.
- Automatic discovery of arbitrary tactical concepts.
- Causal claims about goals, turnovers, mistakes, or optimal choices.
- Claims that seven-match findings generalize to teams, competitions, or soccer broadly.
