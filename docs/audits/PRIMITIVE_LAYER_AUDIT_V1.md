# Primitive & Lowering Audit v1

Date: 2026-06-22

Source commit: `7ec9163a6d3fcd2e1c4f197f1a2d8da24de44341`

Source state: clean committed source snapshot (`git show HEAD:<path>` for source hashes)

Audited Tactical Knowledge Pack SHA-256: `28405b82d54b961459842d77f1547e3a37fa5bb1ce2b7435a8a919732f804854`

External review reference Tactical Knowledge Pack SHA-256: `44a9b5fb3f3748c0e8a7bc80a4134fe3cb062dd66807ca20a671cb980529b7c6`

Acceptance status: accepted for architectural planning only. This audit does not authorize implementing every proposed primitive and does not require a pause, runtime redesign, or broad primitive implementation campaign.

## Scope And Evidence

This audit was regenerated read-only against the clean committed source snapshot at `7ec9163a6d3fcd2e1c4f197f1a2d8da24de44341`. Source hashes embedded in the JSON artifacts are computed as `sha256(git show HEAD:<path>)`. The only files written are audit artifacts and audit documentation.

Hash reconciliation:

- The external review cited `44a9b5fb3f3748c0e8a7bc80a4134fe3cb062dd66807ca20a671cb980529b7c6`, which is recorded in `delivery/ledger.jsonl` and `docs/reviews/2026-06-21-m1-2-s2i-a-local-verification.md` for an earlier S2I-A local-verification state.
- The clean committed source snapshot audited here is `7ec9163a6d3fcd2e1c4f197f1a2d8da24de44341`, where `generated/tactical-knowledge-pack.json` hashes to `28405b82d54b961459842d77f1547e3a37fa5bb1ce2b7435a8a919732f804854`.
- This regenerated audit treats `28405b82d54b961459842d77f1547e3a37fa5bb1ce2b7435a8a919732f804854` as the exact audited pack hash and records `44a9b5fb3f3748c0e8a7bc80a4134fe3cb062dd66807ca20a671cb980529b7c6` as the historical review-reference hash.

Primary evidence reviewed:

- `CURRENT_STATE.md`, `PROJECT_CHARTER.md`, `MILESTONES.md`
- `delivery/status.yaml`, `delivery/ledger.jsonl`
- `delivery/m1.2/SPEC.md`, `delivery/m1.2/NEXT_TASKS.md`, `delivery/m1.2/status.yaml`
- `generated/tactical-knowledge-pack.json`, `generated/tactical-knowledge-pack.md`
- `generated/capability-context.json`
- `generated/tactical-query-plan.schema.json`, `generated/tactical-query-plan.types.ts`
- `docs/primitives/registry.yaml`
- `src/tqe/runtime/catalog.py`, `src/tqe/runtime/ir.py`, `src/tqe/runtime/binder.py`, `src/tqe/runtime/executor.py`, `src/tqe/runtime/relations.py`, `src/tqe/runtime/values.py`
- `src/tqe/workshop/m1_2.py`, `src/tqe/workshop/knowledge_pack.py`, `src/tqe/workshop/hermes_s2.py`
- `config/query-plans/ball_side_block_shift.ir.v1.json`
- `config/query-plans/possession_corridor_availability.experimental.v1.json`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`
- `docs/queries/ball-side-block-shift/*`
- `tests/test_m1_1_binder.py`, `tests/test_m1_1_runtime.py`
- relevant verifier files under `src/tqe/verification/`

Listed paths that do not exist as separate implementation directories:

- `src/tqe/primitives/`
- `src/tqe/relations/`
- `src/tqe/query_ir/`
- `src/tqe/recipes/`

The actual current implementation places primitive/relation catalog definitions and implementations under `src/tqe/runtime/`, with plan documents under `config/query-plans/`.

## Executive Summary

External review accepted the substantive verdict: `SUFFICIENT_WITH_TARGETED_ADDITIONS`. The verdict is accepted for architectural planning, not as authorization to implement all proposed primitives.

The foundation is sound enough to continue S2I and Workbench Alpha. The current system has a typed query document, deterministic binder, cataloged primitive/relation/operator signatures, generic executor, anchor model, PASS/FAIL/UNKNOWN traces, non-match inspection, evidence requests, safe caller profiles, and host-owned confirmation. Existing recipes lower deterministically to canonical tracking data.

The most important layering problem is that some current catalog entries are not primitive in the L1/L2 sense. `signed_lateral_shift` is a bundled detector stage: it performs wide-entry candidate extraction, baseline/search-window policy, quality gating, maximum-shift anchor selection, and anchor creation. `outcome_classification` is recipe-specific L4 M1 outcome logic registered as a primitive, although the boundary correctly blocks model-authored plans from using it except through the trusted frozen M1 recipe. `geometric_progressive_corridor` is a useful L3 relation, but its L1 kernel operations are embedded in Python rather than represented as reusable lower-level catalog operations.

This is not a foundational IR defect. It is an incremental vocabulary/lowering debt. The binder and executor already support safe composition of registered nodes, anchors, relation episodes, evidence requests, complexity limits, and tri-state predicate traces. The next tactical family should add a small set of measurable L2/L3 capabilities, not redesign the IR.

## Part 1 - Capability Inventory

Machine-readable inventory: `generated/audits/primitive-inventory.json`.

Current runtime catalog:

- 6 primitives: `possession_segment`, `ball_lateral_fraction`, `defensive_outfield_centroid`, `signed_lateral_shift`, `outcome_classification`, `relation_destination_entry_classification`
- 2 relations: `geometric_progressive_corridor`, `geometric_progressive_corridor_from_anchor_set`
- 8 operators: `gt`, `gte`, `lte`, `eq`, `neq`, `persists_for`, `exists`, `count_at_least`
- 3 tracked recipe documents: approved `ball_side_block_shift_v1`, experimental `possession_corridor_availability_v1`, experimental `opposite_corridor_after_shift_v1`

Capability visibility tiers:

| Tier | Count | Meaning |
| --- | ---: | --- |
| `USER_TACTICAL` | 1 | Named concepts appropriate for direct user-facing recipes. |
| `AGENT_COMPOSABLE` | 11 | Safe building blocks Hermes may use in experimental plans after contracts are complete. |
| `COMPILER_LOWERING` | 11 | Low-level geometry, kinematics, predicate, or source-fact lowering vocabulary not normally shown in recipe discovery. |
| `TRUSTED_RECIPE_ONLY` | 2 | High-level bundled logic usable only inside a reviewed recipe until hidden dependencies are formalized or split. |
| `LEGACY_DOCUMENTATION` | 4 | Historical or compatibility-only behavior, not a current authoring target. |

Legacy/documented or embedded capabilities also found:

- `wide_channel_dwell`
- `shift_persistence`
- `robust_team_width`
- `robust_team_length`
- `analysis_rate`

Important inventory findings:

- `docs/primitives/registry.yaml` is older/narrower M1 documentation. It lists primitives not present as current catalog entries, including `robust_team_width` and `robust_team_length`.
- The current generated capability context marks most catalog entries agent-authorable, but `src/tqe/workshop/m1_2.py` enforces additional safety: `outcome_classification` is non-authorable for Hermes-authored plans, and `exists` / `count_at_least` are safe only on `anchor_evaluations`.
- `geometric_progressive_corridor` and `geometric_progressive_corridor_from_anchor_set` duplicate the same football relation with different input contracts. This is acceptable as an adapter split, but it should be documented as such.
- `ball_lateral_fraction`, `defensive_outfield_centroid`, and comparison operators are visible in the current capability context, but they are better treated as internal/expert-mode lowering vocabulary than normal football-authoring language.
- `distance_point_to_segment` is now recorded explicitly as `COMPILER_LOWERING`, matching the intended split between deterministic geometry and user-facing recipe language.

Capabilities placed at the wrong layer:

- `outcome_classification`: L4 recipe-specific classifier registered as primitive; keep `TRUSTED_RECIPE_ONLY`.
- `signed_lateral_shift`: L3 detector stage registered as primitive; keep `TRUSTED_RECIPE_ONLY`.
- `wide_channel_dwell` / `shift_persistence`: legacy primitive labels now better represented by predicate/operator composition.

Capabilities whose names overstate what is measured:

- `geometric_progressive_corridor`: good name if "corridor" is explicitly geometric. It must keep rejecting pass-probability, intent, body-orientation, offside, and optimality claims.
- `signed_lateral_shift`: name sounds like a pure signed-distance measure, but implementation creates tactical candidate anchors and applies hidden selection policy.

Visibility posture corrections:

- L1/L2 raw geometry and comparison operators should normally remain `COMPILER_LOWERING`. Hermes can use them only through typed plans or expert mode with strict parameter and evidence constraints.
- `relation_destination_entry_classification` is reusable but should be documented as geometric ball-region entry, not pass usage.
- `ball_side_block_shift_v1` is `USER_TACTICAL`.
- `geometric_progressive_corridor` is `AGENT_COMPOSABLE`.
- `signed_lateral_shift` and `outcome_classification` are `TRUSTED_RECIPE_ONLY` until their complete dependencies are formalized.

## Part 2 - Dependency And Lowering Graph

Machine-readable graph: `generated/audits/primitive-dependency-graph.json`.

### Ball-Side Block Shift Trace

```text
Ball-Side Block Shift
-> possession_segment
-> ball_lateral_fraction
-> wide_entry_threshold(gt)
-> wide_entry_persists(persists_for)
-> defensive_outfield_centroid
-> signed_lateral_shift
-> shift_threshold(gte)
-> shift_persists(persists_for)
-> outcome_classification
-> not_stoppage(neq)
-> canonical ball/player coordinates, ball state, frame/time
```

Opaque or partially opaque nodes:

- `signed_lateral_shift`: embeds central-before-wide logic, baseline/search windows, quality gate, anchor selection, and anchor creation.
- `outcome_classification`: L4 M1 recipe classifier.

### Possession Corridor Availability Trace

```text
Possession Corridor Availability
-> possession_segment
-> geometric_progressive_corridor_from_anchor_set
-> geometric_progressive_corridor
-> point_segment_distance, forward progression, segment length, defender clearance
-> destination side/lane/bounds
-> open/close hysteresis
-> anchor_evaluations
-> has_progressive_corridor(exists)
-> canonical ball/player coordinates, orientation, frame/time
```

Opaque or partially opaque nodes:

- `geometric_progressive_corridor`: deterministic and inspectable, but L1 operations such as point-to-segment distance, projection, and lane-band assignment are internal Python functions rather than cataloged kernel ops.

No dependency cycles were found.

Undocumented dependencies that should be fixed before expanding heavily:

- `possession_segment` reads `minimum_possession_seconds` and `analysis_rate_hz` from shared resolved recipe parameters but declares no catalog parameters.
- `signed_lateral_shift` reads `baseline_window_seconds`, `shift_search_window_seconds`, `minimum_outfield_players_per_team`, `prior_central_fraction`, and `minimum_wide_dwell_seconds` without declaring them as node parameters.
- `outcome_classification` declares only `horizon`, but reads `result_id_seed_hash`, `analysis_rate_hz`, `dedupe_window_seconds`, `opposite_side_fraction`, and `retained_after_switch_seconds`.
- Corridor relation implementations read `analysis_rate_hz` from shared runtime parameters in addition to node parameters.

These are traceability problems, not proof that the architecture is unusable. The rule for future exposure is stricter: capabilities with hidden dependencies must either formalize all actual inputs and parameters in the contract, or be marked `TRUSTED_RECIPE_ONLY`. Incomplete contracts must not be exposed to Hermes as general authoring vocabulary.

Hidden-dependency treatments:

| Capability | Treatment | Current Exposure |
| --- | --- | --- |
| `possession_segment` | A. Formalize `minimum_possession_seconds` and `analysis_rate_hz` in the catalog contract. | Existing reviewed recipes may supply parameters; broad direct Hermes exposure should wait for the complete contract. |
| `signed_lateral_shift` | B. Keep `TRUSTED_RECIPE_ONLY` until baseline/search windows, quality gate, candidate extraction, anchor selection, and dwell dependencies are formalized or split. | Restricted to reviewed recipe use. |
| `outcome_classification` | B. Keep `TRUSTED_RECIPE_ONLY` because hidden M1 outcome dependencies are supplied by the enclosing reviewed recipe. | Restricted to reviewed recipe use. |
| `geometric_progressive_corridor` | A. Formalize shared `analysis_rate_hz` and document internal geometry lowering. | `AGENT_COMPOSABLE` relation, with `distance_point_to_segment` and lane/bounds helpers kept `COMPILER_LOWERING`. |
| `geometric_progressive_corridor_from_anchor_set` | A. Formalize adapter semantics and shared timing inputs. | `AGENT_COMPOSABLE` adapter for the same relation, not a separate football concept. |

## Part 3 - Query IR Expressiveness

Current typed IR supports:

- scopes: match IDs, periods, perspective team role, max results
- parameters: typed values with units, allowed values, min/max
- catalog nodes: primitive and relation nodes
- predicates: operator refs, typed compare values, durations
- anchors: `anchor_source` as `episode_set<anchor_ref>`
- frame signals, episode sets, relation episode sets
- relation episodes with evidence fields
- counts and aggregations through `exists` and `count_at_least`, currently safe only on `anchor_evaluations`
- persistence through `persists_for`
- classification rules
- requested evidence with aliases and required flags
- PASS/FAIL/UNKNOWN predicate traces
- unknown-evidence policy
- complexity limits
- non-match target inspection through `EvaluationTarget`

Current IR does not directly expose:

- generic before/after/within composition between arbitrary episode sets
- generic sequence operators
- generic appearance/disappearance operators outside relation-specific lifecycle outputs
- generic increase/decrease/delta operators
- entity selectors beyond team role and catalog-specific player filters
- named regions/lanes as first-class plan objects
- explicit data-quality requirements as a separate query-plan section

Assessment:

- Missing before/after/within and sequence constructs are not yet foundational blockers because the current anchor-relative relation pattern can express the next likely workflows with bounded relation nodes.
- The main gap is vocabulary, not the IR object model. Defensive lines, lane occupancy, local numerical difference, support arrival, and pressure change can be introduced as typed primitives/relations using existing nodes, anchors, evidence, and tri-state semantics.
- Broader generic temporal algebra should wait until at least one more tactical family proves the shape of the repeated need.

## Part 4 - Tactical Coverage Matrix

Machine-readable matrix: `generated/audits/tactical-query-coverage-matrix.json`.

Summary:

| Classification | Count |
| --- | ---: |
| EXPRESSIBLE_NOW | 2 |
| EXPRESSIBLE_BY_NEW_COMPOSITION | 1 |
| MISSING_PRIMITIVE | 8 |
| MISSING_RELATION | 4 |
| MISSING_IR_CONSTRUCT | 0 |
| UNAVAILABLE_DATA | 0 |
| SUBJECTIVE_OR_CAUSAL | 0 |

The subjective football wording in some questions can be lowered into measurable components, so none were classified as subjective-only. Examples:

- "trap" should lower to touchline proximity, pressure increase, local numerical difference, and reduced exits.
- "insufficient" rest defence should lower to a declared count threshold.
- "third-man" should lower to third-attacker support arrival in a lane/window, not intent.

## Part 5 - Worked Lowering Examples

### Example A - Ball-Side Block Movement

Natural language:

```text
Show possessions where the ball goes wide and the defending block moves toward that side.
```

Tactical interpretation:

```text
During active possession by the perspective team, the ball enters and dwells in a wide channel after being central; the defending outfield centroid shifts laterally toward that ball side by at least the configured threshold and persists.
```

Typed plan:

```text
recipe: ball_side_block_shift_v1
nodes:
  possession -> possession_segment
  ball_lateral -> ball_lateral_fraction
  wide_entry_threshold -> gt(ball_lateral.fraction, wide_entry_fraction)
  wide_entry_persists -> persists_for(wide_entry_threshold, minimum_wide_dwell_seconds)
  defensive_centroid -> defensive_outfield_centroid
  signed_shift -> signed_lateral_shift(possession, wide_entry_persists, defensive_centroid)
  shift_threshold -> gte(signed_shift.signed_shift, minimum_shift_metres)
  shift_persists -> persists_for(shift_threshold, minimum_shift_persistence_seconds)
  outcome -> outcome_classification
  not_stoppage -> neq(outcome.classification, STOPPAGE)
anchor_source: signed_shift.anchors
```

Relations / episodes:

- possession episode
- wide-entry persistence episode
- shift-persistence episode
- anchor at maximum signed defensive shift
- post-anchor outcome classification

Geometric operations:

- absolute lateral ball position normalized by pitch half-width
- defending outfield centroid y
- signed lateral centroid displacement relative to ball side
- persistence over configured windows

Source values:

- canonical ball x/y and frame IDs
- raw/canonical ball possession and active-ball state
- canonical defending player y positions
- frame rate and match period

Current status:

- Expressible now through approved plan.
- Deterministically executable with predicate traces and coordinate replay.
- Main audit caveat: `signed_lateral_shift` and `outcome_classification` are coarse nodes with hidden lowering details.

### Example B - Wide Isolation / Dead-End

Example request:

```text
Show when we sent the ball to the wing, progressive or inside support disappeared, defensive pressure increased, and possession was lost shortly afterward.
```

Ideal tactical plan:

```text
wide ball-side entry or wide carrier anchor
-> progressive/inside support relation exists before anchor
-> support relation disappears or support count drops below threshold
-> pressure_change increases over N seconds
-> possession lost within horizon
-> rank by support loss magnitude and pressure increase
```

Current reusable parts:

- `ball_lateral_fraction` can identify wide ball location.
- `possession_segment` can frame active possession.
- `geometric_progressive_corridor` can represent one kind of progressive support/open route.
- `relation_destination_entry_classification` can classify whether a destination region was entered.
- `outcome_classification` can classify loss, but only inside the frozen M1 block-shift chain and is not agent-authorable.

Missing pieces:

- ball carrier / nearest attacker selector
- inside/progressive support count or support-arrival/disappearance relation
- pressure increase signal
- generic loss-after-anchor primitive outside the M1 outcome classifier
- generic decrease/disappearance operator, unless packaged inside a support relation

Can it be expressed now?

- Not exactly.
- A narrow geometric proxy is possible by composing wide ball location with corridor disappearance and later loss, but current runtime lacks pressure and support-disappearance vocabulary. It should not silently approximate "dead-end" or "isolation."

Smallest safe next step:

- Define measurable `support_count` / `support_arrival_relation` and `pressure_change`, then compose a wide-isolation experimental recipe.

### Example C - Line-Break Support Response

Example request:

```text
Show controlled line breaks where no more than two attackers were beyond the second line, then measure whether teammates entered distinct lanes within the next three seconds.
```

Ideal tactical plan:

```text
line_break_anchor:
  controlled possession/ball-active state
  ball or receiver crosses beyond defensive second line
  attackers beyond second line <= 2

support_response:
  within 3 seconds after line_break_anchor
  teammates enter lanes distinct from ball/receiver lane
  emit support arrival delay, lane IDs, and player IDs
```

Required primitives and relations:

- defensive-line estimation
- relative position to defensive line
- line-break episode or anchor
- attacker count beyond a line
- lane occupancy / distinct lane count
- support-arrival relation

Current blockers:

- No defensive-line or second-line primitive.
- No position-relative-to-line signal.
- No general lane-occupancy primitive; lane fields exist only inside corridor relation evidence.
- No support-arrival relation.

Reusable current parts:

- `anchor_ref` and `anchor_source`
- relation episode and `anchor_evaluations` pattern
- `count_at_least` semantics, after safe source rules are extended to appropriate coverage records
- non-match inspection and replay retrieval
- PASS/FAIL/UNKNOWN trace model

Current status:

- Not expressible now.
- Does not require IR redesign if implemented as bounded anchor-relative capabilities.

## Part 6 - Capability Visibility Tiers

The previous `agent_authorable` posture is too coarse. Every capability should carry one of these tiers:

| Tier | Definition | Examples |
| --- | --- | --- |
| `USER_TACTICAL` | Named concepts appropriate for direct user-facing recipes. | `ball_side_block_shift_v1` |
| `AGENT_COMPOSABLE` | Safe building blocks Hermes may use in experimental plans after their contracts are complete. | `geometric_progressive_corridor`, `relation_destination_entry_classification`, `operator_exists` |
| `COMPILER_LOWERING` | Low-level geometry, kinematics, predicate, source-fact, or unit-lowering vocabulary not normally shown in recipe discovery. | `distance_point_to_segment`, `ball_lateral_fraction`, `defensive_outfield_centroid`, `operator_gt` |
| `TRUSTED_RECIPE_ONLY` | High-level bundled logic usable only inside a reviewed recipe until hidden dependencies are formalized or split. | `signed_lateral_shift`, `outcome_classification` |
| `LEGACY_DOCUMENTATION` | Historical or compatibility-only behavior, not a current authoring target. | `wide_channel_dwell`, `shift_persistence`, `robust_team_width`, `robust_team_length` |

Tier decisions are embedded in `generated/audits/primitive-inventory.json` and `generated/audits/primitive-dependency-graph.json`.

Important boundary rules:

- `distance_point_to_segment` is `COMPILER_LOWERING`. It is deterministic geometry used by corridor lowering, not user-facing tactical language.
- `geometric_progressive_corridor` is `AGENT_COMPOSABLE`. It is tactical enough for bounded experimental plans, while its point/segment distance, lane, and region-bounds helpers stay compiler-lowering details.
- `ball_side_block_shift_v1` is `USER_TACTICAL`. It is the reviewed user-facing recipe name.
- `outcome_classification` is `TRUSTED_RECIPE_ONLY`. It is high-level M1 bundled logic, not a reusable primitive contract.
- `signed_lateral_shift` is `TRUSTED_RECIPE_ONLY` until its complete detector-stage dependencies are formalized or split.
- Legacy M1 macro-style labels such as `wide_channel_dwell` and `shift_persistence` are `LEGACY_DOCUMENTATION`, not new authoring vocabulary.

### Standard-Library Extension Checklist

A new capability should enter the standard library only when it has:

- stable capability ID and version
- visibility tier
- typed inputs and outputs
- units
- entity scope
- temporal behavior
- `UNKNOWN` semantics
- host-owned cost limit
- deterministic lowering path
- positive / negative / `UNKNOWN` tests
- visual evidence representation
- limitations and prohibited claims
- at least one real tactical consumer

## Part 7 - Likely Second-Family Package

Machine-readable recommendations: `generated/audits/next-primitive-recommendations.json`.

Do not implement these during the audit. Record them as the likely package for the second tactical family:

1. `defensive_line_model`
2. `relative_position_to_defensive_line`
3. `controlled_line_break_episode`
4. `lane_occupancy`
5. `support_arrival_relation`

These are deliberately measurable components. They unlock multiple tactical questions without adding intent, optimality, body orientation, or causal inference.

Deferred near-term candidates:

- `local_numerical_difference` is valuable and may become part of `support_arrival_relation` or the next addition after the five-capability package.
- `pressure_change` should wait for wide-isolation, pressing, and counterpress queries so the pressure metric is not overfit or overclaimed.

Not recommended as immediate additions:

- universal football ontology
- general sequence language
- body orientation / scanning
- pass probability
- decision quality
- broad third-man or pressing-trap detectors before the measurable components exist

## Active Track Impact

No active S2I or Workbench Alpha track should pause.

Reasons:

- Existing plans lower deterministically to source tracking data.
- The binder rejects invalid refs, unit mismatches, invalid evidence fields, unsafe raw episode counting, non-authorable catalog nodes, and over-complex plans.
- The executor is catalog/operator keyed rather than recipe-ID keyed, with a legacy profile isolated for frozen M1 parity.
- PASS/FAIL/UNKNOWN, traces, requested evidence, non-match inspection, replay handles, and host confirmation already exist.
- Missing tactical breadth is expected before M2 and can be added incrementally.

Recommended non-blocking corrective work before a second tactical family:

- Declare hidden runtime parameter dependencies on catalog entries or explicitly document them as recipe-level lowering dependencies.
- Move `outcome_classification` out of the normal primitive mental model and keep it trusted-recipe-only.
- Reframe `signed_lateral_shift` as a block-shift relation/stage or split its hidden lowerings when the second family proves what should be shared.
- Document `geometric_progressive_corridor_from_anchor_set` as an input-contract adapter, not a separate football concept.
- Treat this audit as architectural planning input only. It does not authorize implementing the full recommendation set.

## Final Verdict

SUFFICIENT_WITH_TARGETED_ADDITIONS

The primitive/IR foundation is sound, but a small specified set of additions is needed before the second tactical family. The current architecture should continue through S2I and Workbench Alpha while the next tactical vocabulary is added incrementally with explicit lowering, evidence, tests, visibility tiers, and complete contracts. This is an accepted planning artifact, not a runtime redesign mandate and not authorization for a broad primitive implementation campaign.
