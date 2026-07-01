# Workbench Product, Visualization, and Novel-Composition Audit v1

Audit date: 2026-06-22  
Deployed app: https://priori-integrated-alpha.onrender.com  
Deployed commit: `25f29a146e475ef573dbf59da1901bec4d9c8253`  
Branch inspected: `codex/integrated-alpha`

## Executive Finding

The deployed Workbench is a credible engineering workbench for manually running the approved block-shift recipe and the experimental corridor recipe over real DFL/IDSSE tracking data. The host scope model, deterministic execution, cache keying, result rail, replay retrieval, and exact-geometry caution are substantially better than the prior alpha.

It is not yet an emailable client preview of the full product thesis. The blocking gap is not primitive-library breadth; it is product proof. The current link does not reliably demonstrate that Hermes can translate a football-language request into a safe typed plan in the deployed product, and it does not prove true novel tactical composition beyond selecting or parameterizing known recipes/templates.

## Evidence Inspected

- Live health endpoint: `/healthz` returned `ALIVE`.
- Live match library: `/api/matches` exposes only the four deployed Fortuna Düsseldorf matches from the manifest.
- Live bootstrap: model status advertises `HERMES_FRONTIER_READY`.
- Live model-mode interpretation: `/api/interpret` returned HTTP 500 for supported, ambiguous, unsupported, and novel-candidate prompts.
- Source inspected:
  - `apps/workbench-alpha/src/App.tsx`
  - `apps/workbench-alpha/src/PitchCanvas.tsx`
  - `src/tqe/workshop/app_service.py`
  - `src/tqe/workshop/hermes_s2.py`
  - `generated/tactical-knowledge-pack.json`
  - `config/query-plans/*.json`
  - `apps/workbench-alpha/tests/workbench-alpha.spec.ts`
- Existing visual proof artifacts:
  - `artifacts/workbench-alpha/review-proof/screenshots/approved-result-replay.png`
  - `artifacts/workbench-alpha/review-proof/screenshots/experimental-overlay-evidence-correlation.png`
  - `artifacts/workbench-alpha/review-proof/screenshots/state-clarification.png`
  - `artifacts/workbench-alpha/review-proof/screenshots/state-capability-gap.png`

## Product Journey Reconstruction

The current user journey is:

```text
load app
→ choose match scope
→ type query or choose preset
→ interpret
→ validate
→ host confirm
→ execute
→ select result
→ inspect coordinate replay, evidence aliases, and predicate trace
```

Every interpretation should carry an explicit source label:

```text
REVIEWED_RECIPE
MANUAL_PRESET
HERMES_RECIPE_SELECTION
HERMES_NOVEL_COMPOSITION
DETERMINISTIC_REPAIR
CAPABILITY_GAP
```

A plan must never appear AI-authored when it was actually a reviewed recipe, manual preset, or deterministic host fallback. This provenance distinction belongs in both the UI and trace.

The strongest implemented path is manual Browse recipes. It can run:

- approved `ball_side_block_shift_v1`;
- experimental `possession_corridor_availability_v1`.

The live app exposes the right high-level objects: match scope, interpretation, confirmation, deterministic execution, cache state, result rail, replay, evidence, and trace. But the ordinary user has to understand too many implementation terms: host API, busy keys, host confirm, typed plan JSON, evidence aliases, predicate IDs, replay IDs, execution IDs, and formal result labels.

### State Coverage

The detailed state audit is in `generated/audits/workbench-state-machine.json`.

Important state findings:

- Scope changes are handled well. Changing match scope clears validation, confirmation, execution, selected result, replay, and timestamp inspection.
- Mode changes are not fail-closed. Switching Ask Hermes/Browse recipes should clear prior interpretation and execution artifacts.
- Query edits are not fail-closed. Editing the query after interpretation should mark the interpretation stale and disable validation.
- Preset selection can contradict query text. For example, a corridor preset can remain selected while block-shift language remains in the text box.
- Live Hermes errors currently surface as server failures rather than a typed product state.

## Loading and Waiting

The app honestly distinguishes cache HIT/MISS, which is good. The problem is that cold execution is long enough to need a real waiting experience.

Observed prior cloud execution smoke:

- approved first run: about 63 seconds;
- experimental corridor first run: about 171 seconds;
- cached approved run: about 209 ms;
- cached corridor run: about 160 ms.

The cold execution state should say:

```text
Searching selected matches frame by frame.
First run may take 1-3 minutes and will be cached.
Elapsed: …
Scope: …
Cancel
```

Detailed recommendations are in `generated/audits/workbench-loading-audit.json`.

## Information Architecture

Recommended default product structure:

```text
ASK OR CHOOSE
→ UNDERSTAND
→ APPROVE AND RUN
→ EXPLORE MOMENTS
```

Move these behind Developer details by default:

- raw typed-plan JSON;
- bound-plan IDs and hashes;
- authorization IDs;
- execution IDs;
- compatibility profiles;
- raw predicate payloads;
- replay IDs;
- known-timestamp debugging form;
- host/API health badges;
- raw confirmation/execution responses.

The user-facing interpretation panel should use:

```text
USER ASKED
…

INTERPRETED TACTICALLY
…

MEASURED AS
…

DOES NOT ESTABLISH
…
```

The UI inventory is in `generated/audits/workbench-ui-inventory.json`.

## Match Scope and Result Context

This area is mostly good.

Passes:

- perspective team is visible;
- selected match count is visible;
- zero selected matches disables validation;
- live `/api/matches` exposes only deployed manifest matches;
- result replay header shows match, period, canonical `match_time_ms`, possession, selected result index, and result ID.

Remaining product issue:

- result cards still lead with formal implementation labels such as `RETAINED_NO_SWITCH` and `PROGRESSIVE_CORRIDOR_AVAILABLE`;
- principal measurements are not surfaced in the result card;
- the raw result ID is visible in primary card copy.

## Tactical Visualization

### Corridor Overlay

Current behavior:

- `PitchCanvas` draws a dashed line from the current ball position to the player whose ID is in `requested_evidence.target_player_id`.
- The proof artifact confirms exact correlation to the selected witness target player.
- The overlay does not include relation open frame, close frame, limiting defender, clearance line, actual ball path, or temporal validity.

Therefore the current corridor overlay is useful but under-explained. It should be described as a hypothetical geometric connection from ball to teammate for the selected witness, not as an actual pass, optimal pass, or player intention.

Required visible legend:

```text
A geometric corridor is a sufficiently clear forward connection from the ball
to a teammate. It does not establish that this was the optimal pass.
```

### Block-Shift Overlay

The app currently hides block-shift overlays when exact geometry is unavailable. That is the right behavior. Do not reconstruct centroid arrows or ball-side regions from scalar fields until exact geometry is projected.

The full overlay audit is in `generated/audits/tactical-overlay-audit.json`.

## Hermes Interpretation

The desired distinction is:

- `EXISTING_RECIPE`: Hermes selects an approved reviewed recipe.
- `NOVEL_COMPOSITION`: Hermes authors a new typed plan from registered capabilities.
- `CAPABILITY_GAP`: Hermes refuses unavailable data or unimplemented primitives.

For the product UI and trace, those should lower to more explicit sources:

- `REVIEWED_RECIPE`: stored reviewed recipe artifact;
- `MANUAL_PRESET`: user-selected preset, no model authorship;
- `HERMES_RECIPE_SELECTION`: Hermes selected a reviewed/saved recipe, host loaded it;
- `HERMES_NOVEL_COMPOSITION`: Hermes authored a new typed plan with a new plan hash;
- `DETERMINISTIC_REPAIR`: host deterministic repair/fallback decided the final safe state;
- `CAPABILITY_GAP`: no safe measurable plan exists.

Current deployed state:

- Bootstrap advertises Hermes readiness.
- Live model interpretation calls returned HTTP 500 during audit.
- Manual mode can produce clarification and capability gaps for several known terms.
- Manual mode still misses some high-risk unsupported language. Example: “scanning and body angle” can fall through to the selected preset because those exact terms are not fully covered in `app_service.py`.

This is a P0 trust issue. Unsupported football language must not silently become the nearest available recipe.

## Novel Composition Proof

This is the largest product-thesis gap.

The repo has the ingredients for richer composition, including:

- `possession_segment`;
- `ball_lateral_fraction`;
- `defensive_outfield_centroid`;
- `signed_lateral_shift`;
- `geometric_progressive_corridor`;
- `geometric_progressive_corridor_from_anchor_set`;
- `persists_for`;
- `exists`;
- `count_at_least`;
- registered experimental `opposite_corridor_after_shift_v1`.

But the deployed product does not yet prove true novel composition. Source inspection shows the active compiler path is centered on:

- selecting the approved block-shift recipe;
- drafting the experimental corridor family;
- clarification;
- capability gap.

That is valuable, but it is not the same as Hermes authoring a fresh plan whose hash differs from registered recipes/templates and combining multiple capabilities live.

Binary acceptance test:

```text
Novel composition passes only if Hermes creates a schema-valid plan that is
structurally different from both registered recipes/templates, combines at least
two agent-composable capabilities, uses temporal or relational logic, requires
no code or prompt change for the request, produces a new plan hash, starts with
a cache miss, and executes honestly over real data.
```

The current deployed product does not pass that test today. That does not invalidate the product; it precisely identifies the next functional milestone before the email preview can claim model-authored tactical composition.

Recommended hero composition:

```text
Find possessions where the ball-side block shifts,
then an opposite-side forward lane opens within five seconds.
```

The novel-composition audit is in `generated/audits/novel-composition-audit.json`.

## Capability-Gap Experience

Passes:

- optimality can produce a capability gap;
- communication can produce a capability gap;
- pressure/counterpress can produce a planned-capability gap;
- video/body orientation can produce a capability gap.

Fails or partials:

- model-mode capability gaps were not reachable because live model interpretation returned HTTP 500;
- manual fallback does not catch all unsupported variants before preset fallback;
- capability gaps should offer adjacent measurable alternatives without silently substituting them.

## First-Time User Walkthrough

Task results from audit perspective:

1. Select one match: pass.
2. Ask one supported natural-language question: partial. Manual mode works; live Hermes model mode fails.
3. Understand the interpretation: partial. The interpretation bullets help, but implementation terms compete with the explanation.
4. Confirm and run: partial. The three-step validation/host-confirm/execute sequence is technically correct but not product-clear.
5. Open one result: pass.
6. Explain the replay overlay: partial/fail. The user cannot safely infer line meaning without coaching.
7. Switch to Browse recipes: pass.
8. Run an approved recipe: pass.
9. Identify ambiguous or unsupported request: partial. Some manual cases work; model mode fails; unsupported synonym coverage is incomplete.

Expected uncoached hesitations:

- “Is Ask Hermes actually running?”
- “Why do I need both Confirm interpretation and Host confirm?”
- “What is `PROGRESSIVE_CORRIDOR_AVAILABLE`?”
- “Is the yellow line the pass, the best pass, or just an available lane?”
- “Why does the app show replay IDs and result IDs?”
- “What happens if I change the query after results?”

## Email Sendability

Scorecard: `generated/audits/email-sendability-scorecard.json`

P0 blockers:

1. Live Hermes model interpretation must stop returning HTTP 500 and must fail closed into typed product states.
2. The product must either prove one true novel composition or remove that claim from the email/demo framing.
3. UI and trace must distinguish `REVIEWED_RECIPE`, `MANUAL_PRESET`, `HERMES_RECIPE_SELECTION`, `HERMES_NOVEL_COMPOSITION`, `DETERMINISTIC_REPAIR`, and `CAPABILITY_GAP`.
4. Unsupported concepts must not silently map to selected presets.
5. Query, mode, and preset changes must clear or stale-mark dependent artifacts.

P1 requirements for a good preview:

1. Add corridor overlay legend and temporal validity.
2. Simplify the default IA and hide developer internals.
3. Improve cold execution waiting state.
4. Replace implementation-heavy result labels with tactical summaries and measurements.

Prioritized backlog: `generated/audits/workbench-prioritized-backlog.json`

## Deliverables

- `generated/audits/workbench-state-machine.json`
- `generated/audits/workbench-ui-inventory.json`
- `generated/audits/workbench-loading-audit.json`
- `generated/audits/tactical-overlay-audit.json`
- `generated/audits/novel-composition-audit.json`
- `generated/audits/email-sendability-scorecard.json`
- `generated/audits/workbench-prioritized-backlog.json`

## Overall Verdict

SENDABLE_AFTER_P0_P1
