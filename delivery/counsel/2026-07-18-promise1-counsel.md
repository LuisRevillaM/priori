## Independent assessment

### Executive verdict

The current approach is building the right substrate, but it does **not yet deliver the owner’s full promise**.

GEO + ALG can become an unusually honest engine for retrieving formally expressible soccer evidence. Move 1 + Move 2 can make natural-language retrieval dependable. Together, they plausibly deliver:

- many observable moments;
- bounded, explicitly structured sequences;
- geometric team shapes;
- a restricted vocabulary of certified actions.

They do **not by themselves** deliver an LLM that can “understand the soccer” in found spans or investigate open coaching questions. That requires a separately designed **Analyst Layer** and a **Span Perception contract**. Neither should be smuggled into CoachQueryIR or the deterministic primitive registry.

The clean architecture is:

```text
Coach question
    ↓
Analyst: hypotheses, investigation plan, iteration
    ↓
CoachQueryIR: precise retrieval requests
    ↓
Certified algebra + primitives
    ↓
Replayable span dossiers + rendered span views
    ↓
Analyst interpretation
    ↓
Evidence-linked findings, alternatives, uncertainty, next queries
```

My strongest disagreement with any simple “finish ENGINE RUN and the promise is fulfilled” position is this: **query expressiveness is necessary, but soccer analysis is not equivalent to query compilation**.

---

# 1. Promise audit

Severity:

- **S0:** existential — promise cannot honestly be made.
- **S1:** major — useful product exists, but coaches repeatedly hit a hard wall.
- **S2:** material — answer quality or coverage is noticeably constrained.
- **S3:** refinement — does not prevent the core promise.

## Moments

**Current capability: partial. Planned capability: strong for observable, predefined moments.**

The registry already contains a credible base: possession and transition anchors, pressure/fragility, carries, passes, receptions, line relations, runs, marking, compactness, lane occupancy, switches, control outcomes, and geometric changes. GEO adds important missing predicates such as regions, distribution relative to references, control episodes, and pass attempts.

ALG supplies the missing honest logic for combining these moment predicates. Move 2 can make natural-language requests compile into them.

### Gaps

- **S0 — Natural-language correspondence is not certified today.**  
  A successful plan execution does not prove that the user’s sentence meant that plan. Move 1 is the correct remedy; Move 2 only becomes trustworthy when evaluated against it.

- **S1 — Closed-world vocabulary.**  
  The system can find moments that reduce to registered observations and compositions. It cannot safely invent the operational meaning of “caught flat,” “hesitant,” “aggressive,” “comfortable,” “disorganized,” or “should have stepped.”

- **S1 — Parameter grounding.**  
  “High,” “quickly,” “late,” “close,” “sustained,” and “dangerous” need saved, versioned definitions or explicit clarification. The algebra can bind thresholds; it cannot determine their football meaning.

- **S1 — Observation-bound moments.**  
  Body orientation, scanning, disguise, communication, visual attention, and many first-touch qualities remain unavailable under the current data boundary. The pack itself explicitly records these gaps.

- **S2 — Reference resolution.**  
  Follow-ups such as “those moments,” “the same thing on our left,” or “exclude the ones after poor clearances” require conversational result-set identity and typed reference resolution, not merely sentence-to-IR parsing.

- **S2 — Salience.**  
  Retrieving every match is not the same as finding the moments a coach considers revealing. Salience requires ranking criteria, diversity selection, or analyst interpretation, all separately labeled.

**Assessment:** The engine can deliver literal, observable moments. It cannot promise unrestricted soccer-language grounding.

---

## Sequences

**Current capability: narrow. Planned ALG capability: structurally strong, semantically bounded.**

The current fixed sequence machinery and action-chain primitives show feasibility. ALG’s proposed generalized sequence pattern, optional/negative stages, population identity, and temporal relations are the right foundation.

### Gaps

- **S0 — General sequences are not yet implemented and certified.**  
  Until generalized sequence patterns, temporal relations, absence semantics, and population alignment land, the engine remains recipe-bound.

- **S1 — Segmentation is itself football meaning.**  
  “The build-up,” “their pressing sequence,” “the recovery phase,” and “the attack after we broke pressure” do not have self-evident boundaries. The engine needs explicit episode/phase definitions or must return alternatives.

- **S1 — Variable and branching sequences.**  
  Real patterns are rarely one linear chain. Coaches ask for “they force us wide, unless the six drops, then they jump the fullback.” Bounded alternation is planned, but reusable branching tactical grammars are not yet a product abstraction.

- **S1 — Negative evidence depends on universe certification.**  
  “They never recovered their shape” or “no midfielder covered the runner” is only meaningful if eligible actors, temporal coverage, and observation completeness are certified.

- **S1 — Cross-possession and long-horizon narratives.**  
  The useful sequence may span restarts, rebounds, possession ambiguity, or repeated attacks over minutes. Host-enforced bounded horizons are right for safety but create a real expressiveness wall.

- **S2 — Identity continuity.**  
  Player, ball, possession, and episode identity errors poison a sequence more severely than an isolated moment. Provenance helps disclose this; it does not restore the missing evidence.

- **S2 — Sequence similarity.**  
  “Find more attacks like this” requires a declared similarity representation and distance law—or an explicitly exploratory embedding model. ALG set logic does not supply it.

**Assessment:** The planned algebra can deliver **declared sequence patterns**, not general recognition of football narratives.

---

## Shapes

**Current capability: useful but easy to overclaim. Planned GEO capability: materially better.**

Compactness, observed lines, lane occupancy, regional membership, point-pair metrics, and team distribution relative to a reference can describe geometric configurations well. The primitive charter correctly forbids silently converting geometry into formations, tactical roles, or intent.

### Gaps

- **S1 — “Shape” is underspecified.**  
  It may mean a frame geometry, a stabilized interval, lines and depths, coverage of space, relational organization, a named formation, or a phase-specific tactical role structure. The engine chiefly provides the first four.

- **S1 — Dynamic shape and deformation.**  
  Coaches usually care about how shape changes: compression, stretching, staggering, rotation, recovery, or loss of connectedness. Some can be composed from temporal geometry, but there is no general shape-trajectory representation yet.

- **S1 — Formation and role inference remain prohibited.**  
  This is the honest decision. It also means questions like “when did our 4-4-2 become a 4-2-4?” cannot receive certified answers from the deterministic tier.

- **S1 — Occlusion can make apparent structure misleading.**  
  Observed-line and distribution claims must remain explicitly “observed.” Missing one defender can alter the perceived topology, not merely widen a scalar.

- **S2 — Topological and relational shape vocabulary.**  
  Width, depth, compactness, and occupancy are insufficient for all coaching notions: stagger, connectivity, cover relations, isolation, overload structure, and accessible space need further saved definitions or primitives.

- **S2 — Perspective normalization.**  
  “Left,” “inside,” “behind,” “goal-side,” and “weak side” require stable team, phase, direction, and reference-frame semantics across period changes.

**Assessment:** The engine can find **measured geometric shapes and changes**, but not safely equate these with complete tactical organization.

---

## Actions

**Current capability: restricted. Planned GEO capability: moderate.**

Passes, attempts, controlled receptions, carries, switches, runs, pressure, and possession changes provide a meaningful action vocabulary. The action chain and temporal algebra can compose them.

### Gaps

- **S0 — “Actions” is broader than the observation model.**  
  Current tracking/event evidence cannot certify scanning, communication, body feints, pressing cues, cover shadows created by orientation, technical execution details, or intentions.

- **S1 — Event versus action ambiguity.**  
  A provider event is not always the action a coach means. A pressure action may be a trajectory and relationship over time; a decoy run may only be interpretable through its effect on defenders.

- **S1 — Actor attribution.**  
  Determining who acted, who reacted, and who caused an opening is often ambiguous. The CAR charter appropriately avoids causal credit. The same restraint must govern analyst outputs.

- **S1 — Attempt and non-action semantics.**  
  “Could have pressed,” “failed to track,” or “didn’t offer support” are not simple complements. They require a certified opportunity universe and frequently interpretation.

- **S2 — Simultaneous collective actions.**  
  A press, trap, rotation, or rest-defense response is a multi-actor pattern, not a single event. It can sometimes be defined compositionally but needs named, versioned definitions.

- **S2 — Technical quality.**  
  The engine may certify that a pass happened and control followed. It generally cannot certify whether the weight, disguise, receiving body shape, or decision was good.

**Assessment:** The promise must say **observable actions supported by the available evidence**, not “actions” without qualification.

---

## Where the coach’s tenth question defeats the product

A coach’s first questions often match the catalog. The tenth question is conditional, comparative, referential, and explanatory:

> “Those three times they pinned our fullback after we pressed—was the real issue that our winger arrived late, that the six failed to cover inside, or that the back line shifted too early? Compare them with the attacks where we escaped, and show me whether it also happens from goal kicks.”

This defeats the current/planned query stack in several ways:

1. “Those three” requires conversational result identity.
2. “Pinned” requires a saved operational definition.
3. “The real issue” requests causal diagnosis.
4. “Arrived late” requires a reference event and normative threshold.
5. “Failed to cover” requires a certified responsibility/opportunity universe.
6. “Shifted too early” combines sequence timing with a normative counterfactual.
7. “Compare with attacks where we escaped” requires matched contrast construction.
8. “Also happens from goal kicks” requires iterative decomposition and population rebasing.
9. A useful answer requires seeing each span, not merely counting predicates.
10. The answer must distinguish measurements from interpretation.

No larger primitive registry alone solves this.

---

# 2. The Analyst Layer

The Analyst should be an evidence-seeking controller above CoachQueryIR, not a more permissive compiler.

## Investigation contract

An open question such as “How could we improve our defense?” should first become an **investigation brief**, not one giant query.

The brief contains:

- team, matches, phases, score states, and available footage;
- working meaning of “defense”;
- desired outcome: reduce entries, shots, progression, losses after pressure, or something else;
- candidate mechanisms;
- observable proxies for each mechanism;
- comparison populations;
- evidence limitations;
- stopping budget.

If the user gives little context, the Analyst should choose a transparent exploratory scope and say so.

## Planning

For “improve our defense,” a reasonable first hypothesis tree is:

```text
Defensive outcomes
├── Prevent progression
│   ├── pressure engagement
│   ├── line integrity
│   └── wide/central access
├── Defend after progression
│   ├── compactness and depth
│   ├── marking/cover relations
│   └── box or destination-region occupation
├── Transitions
│   ├── rest-defense geometry
│   ├── counterpressure
│   └── recovery sequence
└── Possession losses that expose defense
    ├── loss location
    ├── support around carrier
    └── successor sequence
```

This is a hypothesis menu, not a claim that these are the causes.

## Query decomposition

Each branch becomes small typed queries:

1. Establish population and coverage.
2. Retrieve adverse outcomes.
3. Retrieve matched or stratified successful contrasts.
4. Measure candidate precursors.
5. Retrieve representative spans from each cell.
6. Inspect spans.
7. Generate revised hypotheses.
8. Run discriminating follow-up queries.

The Analyst should prefer queries that distinguish hypotheses rather than merely accumulate examples.

Example:

- Find opponent central progressions ending in the final third.
- Partition by phase, origin, and possession type.
- Measure pressure status, observed line spacing, width, depth, and weak-side occupation before entry.
- Construct a contrast population where similar attacks were stopped.
- Select diverse examples and near-boundary cases.
- Inspect spans to determine whether the measured difference corresponds to a coherent football pattern.
- Form a narrower hypothesis, such as “the wide midfielder’s pressure begins while the back line remains deep, opening the half-space.”
- Translate only the measurable part into a saved definition and rerun it.
- Present the interpretation separately.

## Iteration policy

Every cycle should update an investigation state:

```text
question
scope
hypotheses:
  - status: untested | supported | weakened | unresolved
  - certified observations
  - interpretive observations
  - counterexamples
  - missing evidence
queries_run
spans_reviewed
next_best_query
stop_reason
```

The agent should actively search for:

- counterexamples;
- alternative mechanisms;
- subgroup instability;
- coverage-correlated findings;
- threshold sensitivity;
- duplicate variants of the same episode;
- findings that disappear under matched comparisons.

It should not repeatedly query until something “interesting” appears without recording the search path. That would create undisclosed researcher degrees of freedom.

## Stopping

Stop when one of these conditions is reached:

- the question has a stable evidence-backed answer at the requested scope;
- additional queries have low expected discrimination between live hypotheses;
- coverage or vocabulary makes the remaining question unanswerable;
- findings are too unstable across matches or thresholds;
- the investigation budget is exhausted;
- the next step requires a new owner/coach definition;
- a causal or normative conclusion would require unavailable evidence.

A good final response may be: “We found a repeated geometric association, but cannot yet distinguish coaching instruction, player choice, and tracking artifact.”

---

# 3. Span perception

The owner is right: an analyst that never examines the found spans is operating half-blind. But “seeing” must not be treated as one homogeneous capability.

## A. Structured dossiers from certified primitives

A dossier should contain:

- match and span identity;
- time-aligned events and episodes;
- player/team identities where licensed;
- certified primitive outputs at key anchors;
- interval trajectories for relevant fields;
- PASS/FAIL/UNKNOWN and reasons;
- provenance and coverage;
- query membership explanation;
- neighboring context before and after the matched span;
- clip/render references;
- contrast-span references.

### What it perceives best

- exact distances, timings, identities, and thresholds;
- which certified conditions held;
- uncertainty and missing evidence;
- comparisons across many spans;
- reproducible causal provenance of the computation.

### What it cannot perceive

- visual gestalt;
- body orientation unless separately observed;
- deceptive or communicative behavior;
- whether the clip “looks coordinated”;
- contextual cues omitted from the dossier;
- soccer phenomena for which no field was requested.

### Honesty tier

**Certified Observation**, when directly populated from certified primitives.  
Any tactical summary generated from it is **Agent Interpretation**, not automatically certified.

---

## B. Multimodal reads of rendered pitch frames or animation

The best input is not a few disconnected screenshots. It is a time-controlled animation or contact sheet with:

- normalized attacking direction;
- player and team identity;
- ball trail;
- timestamps;
- event anchors;
- optional overlays for lines, regions, pressure, and trajectories;
- a clean view alongside the annotated view.

### What it perceives best

- emergent spatial gestalt;
- synchronization and relative movement;
- openings, compression, staggering, rotations, and recovery behavior;
- patterns not anticipated in the requested dossier fields;
- whether a proposed tactical description is visually coherent.

### What it cannot reliably perceive

- exact metric thresholds;
- hidden or missing actors;
- whether an overlay derives from uncertain evidence;
- intent, responsibility, or optimality;
- subtle action cues absent from tracking-only renders;
- certified truth merely by looking.

A rendered pitch animation is still an abstraction. It does not restore body shape or video cues.

### Honesty tier

**Model-Assisted Visual Interpretation**.  
It can motivate hypotheses and summarize apparent patterns. It cannot upgrade a claim to certified status.

---

## C. Raw coordinate serialization

This might provide sampled trajectories, entity IDs, ball coordinates, velocities, and timestamps in a machine-readable window.

### What it perceives best

- exact numerical access for custom calculations;
- patterns omitted by the current dossier schema;
- independent recomputation and debugging;
- dense trajectory detail without raster loss.

### What it cannot perceive well

- holistic soccer organization over many entities and frames;
- perceptual continuity without extensive preprocessing;
- semantic meaning from thousands of coordinate tuples;
- reliable interpretation within ordinary LLM context limits.

Raw coordinates encourage false confidence: the model may narrate numerical material it has not robustly integrated.

### Honesty tier

**Exploratory Computation** unless processed through registered, verified code.  
Free-form LLM conclusions from coordinate dumps should be the lowest-confidence analyst evidence.

---

## D. Hybrid perception

This should be the product design.

For every important span, give the Analyst:

1. a certified structured dossier;
2. an animated or key-frame pitch rendering;
3. the corresponding clean footage clip when rights and video availability allow;
4. scoped access to raw coordinates through tools, not massive prompt dumps;
5. contrast examples;
6. the ability to issue follow-up queries from a selected time range or entity.

The Analyst can then say:

- “The certified record shows X.”
- “The rendered span appears to show Y.”
- “I tested that interpretation with query Z.”
- “The result supports/weakens Y under these conditions.”
- “Intent or responsibility remains unresolved.”

### What hybrid uniquely enables

It closes the loop between formal retrieval and football interpretation. Visual perception discovers candidate explanations; certified queries test their observable consequences; counterexamples discipline the narrative.

### Proposed honesty ladder

| Tier | Label | Permitted meaning |
|---|---|---|
| T0 | **Source Observation** | Provider/video/tracking evidence with manifest and coverage |
| T1 | **Certified Derived Claim** | Deterministic primitive/algebra result with provenance |
| T2 | **Certified Descriptive Synthesis** | Mechanical summary of T1 results, with no new football inference |
| T3 | **Agent Interpretation** | Soccer reading of dossiers/renders/clips, evidence-linked but not certified |
| T4 | **Hypothesis / Recommendation** | Proposed mechanism or intervention requiring validation |
| T5 | **Unsupported** | Intent, causation, responsibility, or counterfactual asserted without adequate evidence; must not ship as a conclusion |

---

# 4. The Tier Law

The core separation law should be:

> **Agent interpretation may select, organize, compare, and explain certified evidence, but it may not inherit the certification status of that evidence. Certification crosses the boundary only through a registered deterministic claim whose inputs, semantics, coverage, and provenance are certified.**

Corollaries:

1. **No prose laundering.**  
   Ten certified measurements do not make the LLM’s tactical explanation certified.

2. **No visual laundering.**  
   A multimodal model seeing a pattern does not turn that pattern into an observed fact.

3. **No recommendation laundering.**  
   Evidence that a pattern correlates with poor outcomes does not certify that changing it will improve defense.

4. **Sentence-level attribution.**  
   A mixed paragraph must identify which statements are certified, interpreted, hypothetical, or unavailable. One badge on the whole answer is insufficient.

5. **Bidirectional traceability.**  
   Every certified statement links to its plan, definition version, population, evidence, and spans. Every interpretation links to the observations and spans that motivated it.

6. **Interpretation can create queries, not facts.**  
   The Analyst may convert “they look disconnected” into measurable follow-ups about distances, support, lanes, and timing. The interpretation remains provisional until those queries return.

7. **Disagreement is preserved.**  
   If visual interpretation conflicts with a certified result, show the conflict. Do not silently prefer either. It may reveal a primitive-definition problem, rendering defect, missing visual variable, or model error.

8. **Advice must expose the inference bridge.**  
   “Try stepping the line earlier” must state the observed pattern, the interpretive mechanism, and what future evidence would validate the intervention.

This law makes a sophisticated Analyst compatible with the honesty brand. Without it, adding multimodal reasoning would blur the product’s most valuable distinction.

---

# 5. Verdict and sequence

## Does the approach deliver the promise?

**Qualified yes for retrieval; no for the expanded Analyst promise without additional architecture.**

The ENGINE RUN is correctly sequenced for the retrieval engine:

1. finish ALG;
2. build the external correspondence oracle;
3. complete GEO;
4. land canonical CoachQueryIR;
5. add versioned coach definitions;
6. serve and report the full grammar honestly.

That can deliver a compelling language-to-query system for **observable, formally expressible soccer moments, bounded sequences, geometric shapes, and supported actions**.

It should not be described as universal soccer understanding.

## Designed additions

### Add now, without delaying the ALG spine

**A. Span Dossier Contract**

Define the standard output of every match-producing query:

- span boundaries and context window;
- stable identities;
- certified facts and trajectories;
- provenance/coverage;
- query-membership explanation;
- render and clip references;
- counterexample eligibility.

This is a low-regret interface and prevents every later Analyst feature from inventing its own evidence representation.

**B. Analyst Tier Law**

Ratify the claim labels and sentence-level provenance now. It affects schemas, UI, evaluation, and language generation; retrofitting it later will be painful.

**C. Move 1 expansion**

The correspondence oracle should test not only sentence → IR, but:

- conversational references;
- ambiguity and clarification;
- threshold grounding;
- open question → investigation plan;
- plan → discriminating query set;
- evidence → correctly tiered prose;
- adversarial “tenth questions.”

### Build immediately after stable CoachQueryIR

**D. Analyst v0**

A bounded read-only investigator that:

- creates explicit hypothesis trees;
- runs a capped number of queries;
- constructs contrast populations;
- selects diverse spans;
- records every query and revision;
- stops under declared rules;
- produces tiered findings rather than one unqualified answer.

**E. Hybrid Span Viewer**

Begin with certified dossiers plus deterministic pitch animation. Add source video when the MatchFactStore and rights manifests support it. Give the model coordinate tools for scoped calculations; do not stuff raw trajectories into prompts.

### Build after Analyst v0 proves useful

**F. Saved Investigation Definitions**

Version:

- tactical concepts;
- comparison strategies;
- investigation templates;
- span-selection policies;
- perceptual prompts;
- recommendation language.

**G. Analyst evaluation**

Use separate scorecards for:

- query-plan validity;
- evidence citation correctness;
- interpretation faithfulness;
- counterexample seeking;
- hypothesis discrimination;
- calibration and abstention;
- coach-rated usefulness;
- recommendation stability.

Do not collapse these into the compiler’s three-proof certificate.

## Final position

The present architecture is closer to the promise than a conventional “LLM over tracking data” system because it takes semantics, uncertainty, and provenance seriously. Its danger is the opposite of technical weakness: it may become so rigorous about query execution that it mistakes retrieval for analysis.

Finish the ENGINE RUN. Preserve its primitive/algebra/compiler boundaries. But formally add the Analyst and Span Perception layers as distinct post-IR product architecture, while defining their evidence contracts and Tier Law now.

The shippable promise should be:

> Ask soccer questions in natural language; Priori compiles the observable parts into inspectable spatiotemporal queries, shows the exact moments and sequences it found, and helps investigate what they may mean—clearly separating certified evidence from analyst interpretation and coaching hypotheses.

That promise is both compelling and achievable. The broader claim that the system simply “understands the soccer” would still be premature.