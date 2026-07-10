# Paper 1 — The compiler, all layers

## Position

The current system is an unusually rigorous proof harness, but it is not yet a general compiler. It can prove that a small vocabulary of deterministic programs is internally consistent, executable, reproducible, and honest about missing data. That is valuable. But the product promise requires something harder: proving that a coach’s sentence was understood correctly, that the decoded film supports the answer, and that both remain reproducible as models, footage, vocabulary, and seasons change.

Today, “certification” covers mostly the middle of that chain. The two dangerous ends—language-to-intent and pixels-to-world—remain uncertified.

The strongest defense of the present architecture is that it created hard semantic and evidentiary rails before product pressure could normalize guessing. Keep that constitution. But treat bounded search, the monolithic knowledge pack, and most of the current semantic front end as scaffolding.

## Layer-by-layer judgment

### 1. Typed registry and generated knowledge pack: too many semantic authorities

There is no single source of semantic truth.

The runtime catalog remains authoritative for execution. A separate semantic registry describes itself as a “shadow” layer. The knowledge pack is generated from the runtime catalog, workshop constants, hand-selected recipe files, and classification rules—not from that semantic registry. There are also two semantic-expression families: the earlier [`SemanticExpression`](/Users/luisrevilla/code/priori/src/tqe/semantic_compiler/models.py:129) and SCP2’s [`MeaningExpressionV0`](/Users/luisrevilla/code/priori/src/tqe/semantic_compiler/meaning_expression.py:132).

This is over-built in the wrong dimension. The project has invested in multiple exhaustive descriptions of meaning without establishing which one alone defines meaning.

The 1.25 MB pack also conflates:

- Type and capability declarations.
- Prompt instructions.
- Lexical routing lists.
- Tool schemas.
- Claims policy.
- Recipes.
- Product-authority policy.
- Complexity limits.
- Gap taxonomy.

That is convenient for reproducibility but poor as a model interface. As vocabulary grows, every ask carries an increasingly large global worldview even though a question normally needs perhaps six concepts and three operators.

Recommendation: one canonical, namespaced ontology and query IR; multiple generated projections from it. The LLM should receive a retrieved slice or interact with a typed schema service, not ingest the whole civilization on every ask.

### 2. Hermes NL-to-meaning: a disciplined prompt, not a semantic compiler

Hermes is asked to emit a complete, redundant document in one shot. For clarification it must emit two or more complete alternative expressions. Repair prompts include the full projection again plus rejected output. This will become disproportionately fragile for longer or nested questions.

More importantly, the model authors both:

- The ostensible football meaning.
- The lower-level target contract that determines what machinery search will find.

There is no independent check that those agree. A model can misunderstand “keep it after pressure,” produce a perfectly valid but different contract, and the rest of the stack will faithfully certify and execute the wrong question.

Refusals are not fully gated either. Model-authored `gap_code` values in direct refusal outcomes are structurally validated as non-empty strings, but not mechanically required to belong to the generated gap vocabulary. Conversely, an out-of-vocabulary expression can only become a typed refusal if its unknown name happens to contain an alias for an existing gap code. Novel but legitimate missing concepts tend toward repair failure rather than a principled new gap.

Hermes needs to produce a small parse with explicit ambiguity, not a full executable search brief. Grammar-constrained decoding or typed tool calls would remove most JSON repair work. For important asks, produce a small ranked parse forest and let deterministic elaboration expose where readings differ.

### 3. Vocabulary gate: string membership masquerading as typing

The gate is useful but far weaker than its name suggests.

It checks that concept names, operator names, fields, and parameter names occur somewhere in the pack. Operator parameters are validated against a global parameter-name set, not consistently against the specific operator application. `MeaningClause.subject` and `.action` are free strings. Units and values receive only limited checking. `concept_identity` and correspondence clauses are largely model-authored labels.

Most consequentially, `operator_applications` are not what target synthesis compiles. They mostly survive as correspondence metadata. `meaning_clauses` become a rendered English declaration. `group_by` does not directly become an executable group operation. The separately authored `target_contract`—a required-field bag plus constraints—is what drives synthesis.

So the meaning expression is not yet an AST. It is a narrative document adjacent to a search request.

### 4. Target synthesis: heuristic field search, not compilation

The key redesign target is here.

[`target_contract_payload()`](/Users/luisrevilla/code/priori/src/tqe/semantic_compiler/target_synthesis.py:58) discards much of the high-level expression and hands the search engine required fields, status semantics, and composition constraints. The 5,000-line search script then guesses providers using field overlap scores and operator-specific builders. It returns the first candidate that binds and executes within depth 4 and branching 6.

That is intelligent automated wiring. It is not semantic compilation.

Its scaling law is unfavorable:

- Each new operator adds signatures plus bespoke search construction.
- More overlapping evidence fields increase ambiguous candidate chains.
- Composition produces combinatorial branching.
- The first executable candidate is not necessarily the cheapest, clearest, or semantically strongest.
- Search behavior depends on heuristics hidden in a coverage-map script imported into product code.

Bounded search should remain as an offline discovery tool, mutation tester, or way to find missing reusable abstractions. Production compilation should elaborate a typed relational program deterministically. If the query IR says `rate(filter(P, fragile), P)`, the compiler should not rediscover that graph by searching for field names.

### 5. Correspondence-gated certification: the name outruns the proof

The current correspondence guard proves that the declaration has a `coverage_row`, a `meaning`, and the correct row identity. It does not judge the declaration, by constitutional design. That is correct for ledger governance.

But bridge serving then treats this shape check, successful synthesis, binding, complete requested evidence, and execution `PASS` as sufficient to answer. An “honest zero” can establish compiler reachability. The synthetic fallback coverage row in [`_coverage_row_or_synthetic()`](/Users/luisrevilla/code/priori/src/tqe/semantic_compiler/target_synthesis.py:200) is compatible with the rule that bridge queries do not write the ledger, but it also demonstrates that bridge “certification” is not an earned product-capability verdict.

Three different proofs are being compressed into one word:

1. **Parse fidelity:** Did the IR preserve what the coach meant?
2. **Program correctness:** Does the plan implement the IR?
3. **Empirical validity:** Do the input observations and primitives support the result within declared risk?

The system is strongest on number 2. It has limited tests around number 1 and no own-footage basis yet for number 3. Call current outputs “bound deterministic answers” until the full certificate exists.

### 6. Binder and composition laws: the best layer, but not proof-carrying

The binder is the architectural keeper. Typed ports, units, cardinalities, evidence fields, explicit constraints, fail-closed registration, and deterministic hashes are worth preserving.

Its weakness is that composition laws are represented as boolean parameters and upstream-chain inspections rather than type refinements. “Same team,” “frame aligned,” and “identity preserved” are declarations that the binder sees somewhere upstream. They are not proof objects carried by a relation type. Several laws can be opted out with a reason string.

Field validation also often unions fields from all inputs, meaning the generic check can establish that a field exists somewhere without proving it belongs to the semantically correct side. Operator-specific checks compensate unevenly.

Redesign relations to carry refinements such as:

```text
Relation<
  anchor=possession_id,
  perspective=team(home),
  frame_basis=canonical_25hz,
  identity=player_entity,
  observation_tier=camera_observed
>
```

Joins and aggregations should consume and produce those refinements mechanically. Composition law then becomes type derivation, not a collection of booleans.

### 7. Tri-state execution: correct foundation, insufficient uncertainty model

PASS/FAIL/UNKNOWN is the right product language and should survive. The mistake would be treating it as the entire internal uncertainty representation.

Own-footage decoding introduces:

- Detection probability and localization covariance.
- Alternative identities.
- Competing track associations.
- Correlated missing observations.
- Homography uncertainty.
- Imputed versus observed positions.
- Model-version-dependent evidence.

Collapsing these immediately to independent UNKNOWN rows loses information required for good bounds and useful diagnostics. Two UNKNOWN predicates caused by the same missing ball segment are not two independent uncertainties. Aggregation needs provenance tokens or shared latent identities to avoid unnecessary worst-case widening and double counting.

Use a provenance-bearing uncertain relation internally, then project to PASS/FAIL/UNKNOWN at claim boundaries. Tri-state remains the public law, not necessarily the only internal mathematics.

### 8. Aggregation: mathematically careful, structurally immature

The joint-partition rate construction is one of the better parts of the system. It avoids dividing independent intervals and handles subset violations honestly.

The surrounding aggregation model is weak:

- `aggregate_over` supports only count.
- `population_expression` is an echoed human-authored string, not an executable population AST.
- Aggregation runs within period execution; cross-period and cross-match totals are reconstructed later in the Film Room.
- Empty-group behavior differs between count and rate.
- Correlated UNKNOWN evidence is not represented.
- The interval formulas are reimplemented in runtime operators, certified-table production, and Film Room serving.

That duplication will eventually create semantic drift even if it is currently tested.

Make population expressions first-class relational values. Add field-domain declarations for sum, mean, extrema, quantiles, shares, and comparisons. Put interval construction in one library that emits both machine values and presentation objects; the Film Room should never recalculate analytics.

### 9. Execution and serving: optimized batch research runtime, not a concurrent product runtime

Each query builds a `PeriodState` by loading whole Parquet periods into pandas and parsing raw tracking state. Parallelism is match-period process parallelism. That is reasonable for seven matches, but more matches scale linearly in I/O and multiply memory. The binder’s cost estimate—nodes × matches × periods × result limit—does not model frames, candidate sets, spatial joins, or pairwise relation explosion.

Concurrency is more concerning. Public asks use a thread-per-request server and add another daemon worker thread for timeout. When the timeout expires, the underlying Hermes call or execution is not cancelled; it keeps consuming resources. Concurrent asks can therefore outlive their clients while launching model processes, period workers, cache writes, and large dataframe loads.

The system needs:

- Admission control and per-tenant quotas.
- A durable job queue.
- Cooperative cancellation and deadlines propagated through Hermes, synthesis, and execution.
- Shared read-optimized match state.
- Materialized reusable facts.
- Async result retrieval.
- Resource-aware plan costing.

### 10. Film Room: convincing evidence viewer, not yet “ask forever”

The Film Room shows a metric, interval, moments, replay overlays, provenance, raw evidence, clarification, and refusals. As a Gate 1 demonstration it is focused and honest.

As a product loop it lacks:

- Durable conversations and follow-up reference resolution.
- Saved questions, definitions, cohorts, and comparisons.
- Coach-specific meanings such as “our pressing trigger.”
- Multiple uploaded matches and season scopes.
- Re-execution versus historical-result controls.
- Semantic migrations when concepts or models change.
- Team tenancy, permissions, retention, and deletion.
- Vocabulary-demand capture from refusals and corrections.
- A natural-language answer that interprets the evidence.
- Upload processing status and per-match quality profiles.

The current UI replaces one ask with the next. “Forever” requires a durable semantic workspace, not an indefinitely available text box.

## Scaling failure modes

**More matches:** full-period loading per ask, per-role duplicate execution, late aggregation, fixed match defaults, and no materialized feature store. Season-scale questions will be dominated by repeated decoding rather than query computation.

**More sports:** the current IR hardcodes home/away, first/second halves, soccer field semantics, possession, a 15-second horizon, and soccer-specific evidence fields. Adding basketball or rugby by expanding the same global catalog will create a vocabulary landfill. Use sport ontology modules above a sport-neutral temporal relational algebra.

**More concurrent users:** Hermes subscription dependence, synchronous request threads, uncancelled timeouts, process-based match execution, and shared local handles are a single-user demonstration architecture.

**Longer questions:** 40-node plans, search depth 4, exactly three sequence stages, 15-second default temporal horizons, one-shot JSON, and complete alternative expressions for clarification. Long questions need decomposition into named subqueries, common subexpression reuse, and multi-turn scope confirmation.

## What is missing for “upload film and ask forever”

The missing core is not another primitive. It is a versioned match knowledge system.

Every upload needs an immutable observation manifest containing footage hash, decoder version, calibration version, tracking version, model weights, coverage, uncertainty, rights policy, and derived-fact versions. Every query needs to bind to a corpus snapshot and remain replayable years later. A later model may provide a better answer, but it must not silently rewrite the old one.

There must also be two connected learning loops:

- Semantic demand: what coaches ask, clarify, save, reject, and redefine.
- Perceptual failure: which observation uncertainties actually widened those answers.

At present those loops are plans, not architecture.

## Ranked moves

| Rank | Move | Effort | Payoff |
|---|---|---:|---:|
| 1 | Build an external-correspondence evaluation system: sentence→IR contrast sets, IR→plan equivalence tests, plan→ground-truth query fidelity, selective-risk curves, and a rotating sealed domain panel. | M | Existential |
| 2 | Replace both semantic-expression models and production field search with one canonical `CoachQueryIR`: a typed temporal relational algebra with deterministic elaboration and proof-carrying composition. Keep bounded search offline. | XL | Transformational |
| 3 | Build an immutable, versioned `MatchFactStore` and compile plans to a columnar/materialized execution backend. Cache facts by match/model/kernel version instead of rereading whole periods per ask. | XL | Transformational |
| 4 | Enrich the evidence algebra: observation tiers, uncertainty/covariance, shared provenance tokens, identity alternatives, structured populations, and general numeric aggregation. Continue projecting public claims to PASS/FAIL/UNKNOWN. | L | Very high |
| 5 | Build the “forever” service around the compiler: uploads, tenancy, rights/retention, saved definitions, corpus snapshots, query history, follow-ups, semantic migrations, feedback, and model-result comparison. | XL | Existential |

If only one large rewrite is authorized, do move 2 after move 1. A new compiler without an independent semantic oracle would merely make wrong meanings compile more elegantly.

---

# Paper 2 — The training doctrine

## Position

The doctrine correctly identifies that the current ladder trained almost nothing, that query fidelity matters more than leaderboard metrics, and that QA—not raw GPU spend—is the real bottleneck. T-0’s rights discipline is sound. The insist-path is directionally right.

But the proposed ladder is ordered like five independent component fine-tunes. The actual problem is joint inference over geometry, camera motion, players, ball, possession, tracklets, identity, and sparse text evidence. Calibration is far too late. Jersey OCR is before the tracklet substrate it needs. Team identity is framed as a conventional supervised head when it is mostly a match-conditioned structured inference problem. The flywheel assumes uncertainty is trustworthy before it has been calibrated.

The doctrine also overweights broadcast footage even though the first paying-customer substrate is likely club-owned tactical/Veo-style footage. These should be separate domain profiles, not one average model.

## The north star is Goodhartable

“Interval narrowing per dollar on flagship question families” is much better than AP50, but unsafe as the sole binding number.

A system can narrow intervals by becoming more willing to emit PASS or FAIL while becoming wrong. It can narrow a favored family by overfitting its denominator. It can repeatedly inspect a frozen evaluation set until that set becomes training data by policy. It ignores human correction time, review, storage, failed experiments, and deployment cost. It also rewards the current question distribution at the expense of new vocabulary.

Use a lexicographic objective:

1. **Selective correctness first:** false claim rate and calibration under a frozen risk ceiling, including worst camera/domain groups.
2. **Usefulness second:** a predeclared answered-question floor across valuable families.
3. **Information third:** interval width or risk-coverage area.
4. **Economics fourth:** total marginal cost, including annotation and review minutes.

A reasonable summary metric is: **verified useful information gain per total euro, subject to fixed selective-risk and usefulness floors.** But keep the underlying scorecard visible; one number will always hide a failure mode.

Crucially, interval narrowing should be causal. The compiler must identify which shared UNKNOWN evidence tokens widened a particular answer, then estimate which annotation or model improvement would shrink it. Without that sensitivity analysis, “train the ball model” remains an intuition rather than an allocation rule.

## The ladder order is wrong

T-0 is necessary but incomplete. It needs label ontology, split policy, annotation QA, and evaluation methodology—not only rights provenance.

After T-0, a strict serial ladder is the wrong shape. Use parallel lanes that integrate repeatedly:

1. **D-0 — Product and evaluation contract.** Define claim-bearing labels, observation tiers, correction semantics, domain splits, selective-risk metrics, and query-level error attribution.
2. **D-1 — Rights-clean real corpus and annotation system.** Include clip/tracklet labeling, blind audits, inter-annotator agreement, roster/substitution data, model-assisted correction, and deletion lineage.
3. **D-2A — Scene geometry.** Shot/cut detection, field-line and keypoint perception, hybrid camera solving, temporal smoothing, and calibration covariance.
4. **D-2B — Shared visual candidates.** Player, goalkeeper, referee, and ball proposals from a shared video backbone, using synthetic data as augmentation.
5. **D-3 — Temporal game-state inference.** Player tracking plus ball trajectory, ball state, and possessor inference over clips.
6. **D-4 — Global identity graph.** Team role, sparse jersey evidence, appearance embeddings, motion, roster, substitutions, and impossible-transition constraints jointly.
7. **D-5 — Promotion and adaptation.** Untouched-domain tests, calibration, canaries, rollback, replay buffers, and customer-domain adapters.

The flywheel begins in D-1. It is not T-∞ after the “real work”; annotation and model-assisted correction are the work.

## Concrete disagreements with the rung designs

### T-1 ball specialist: detector-then-temporal is the wrong decomposition

Ball detection should not be optimized as isolated frame AP followed by a sequence model. A soccer ball may be only a few pixels, blurred, occluded, or absent while player motion and possession strongly constrain its state.

Train a candidate detector, but decode a posterior trajectory using camera geometry, player trajectories, candidate detections, and ball-state/possessor predictions. A joint temporal transformer, factor graph, or probabilistic trajectory decoder is a better architecture than “YOLO fine-tune, then temporal repair.”

Recent work already points toward joint inference: a 2026 soccer model jointly infers ball trajectory, ball state, and possessor from player trajectories, player types, and player crops using sociotemporal transformer blocks rather than relying solely on observed ball positions. [Multi-Modal Soccer Scene Analysis with Masked Pre-Training](https://openaccess.thecvf.com/content/WACV2026/papers/Peral_Multi-Modal_Soccer_Scene_Analysis_with_Masked_Pre-Training_WACV_2026_paper.pdf).

Physics should be a trajectory prior, test generator, or separately typed inference tier. It is a weak primary source of detector pixels.

### T-2 team identity: 97% crop accuracy would be a misleading victory

Team identity is largely match-conditioned. Kits, lighting, compression, referees, goalkeepers, and kit clashes vary by match. A generic supervised-contrastive encoder is useful as a feature extractor, but a hard trained head is not the product solution.

Use per-match transductive inference:

- Match-specific kit prototypes.
- Tracklet consensus rather than crop votes.
- Referee and goalkeeper roles.
- Temporal continuity.
- Roster constraints.
- Explicit UNKNOWN when clusters overlap.

Measure team-role errors at the tracklet and downstream-query levels, not crop accuracy. A 97% crop head can still create catastrophic identity switches at the exact transition that anchors a tactical answer.

### T-3 jersey OCR: synthetic-first is oversold and sequenced too early

Jersey evidence is sparse. The number may be absent, folded, occluded, seen only from behind, or legible in three frames out of a 200-frame tracklet. Per-crop OCR is the wrong unit.

The rung needs:

- Number-presence and view-quality selection.
- Pose-aware rectification.
- A sequence recognizer such as PARSeq/TrOCR-class architecture.
- Tracklet-level probabilistic aggregation.
- “No visible number” as a legitimate observation.
- Fusion into the global identity graph.

Tracklet aggregation has already shown itself central to soccer jersey recognition rather than optional post-processing. [A General Framework for Jersey Number Recognition in Sports Video](https://arxiv.org/abs/2405.13896).

Therefore tracking must precede or co-evolve with jersey recognition. T-3 and T-4 should be merged into an identity program.

### T-4 ReID: appearance cannot solve same-kit football identity

A soccer-specific ReID embedding helps association, but the doctrine places too much faith in it. Teammates intentionally look alike; appearance changes with pose and camera, while different players share kits. Long gaps across broadcast cuts are frequently non-identifiable from appearance alone.

Compare at least three approaches:

- A strong sports-specific association tracker such as [Deep HM-SORT](https://arxiv.org/abs/2406.12081).
- Track-query/memory architectures such as MOTR or MeMOTR.
- A global factor graph or min-cost-flow association layer combining motion, field position, team, jersey posterior, roster, substitutions, and camera-cut constraints.

For Entrelíneas, the third is likely the best production authority because it can preserve competing identities and expose why continuity is UNKNOWN. A learned association model can supply edge scores without becoming the final uninspectable judge.

### T-5 calibration: it belongs near the beginning

Calibration is a substrate, not cleanup. Every spatial primitive depends on it. It also improves tracking because field-space motion is more stable than screen-space motion across pans and zooms. Recent sports tracking work explicitly argues for “register then track.” [FieldMOT](https://www.openaccess.thecvf.com/content/CVPR2025W/CVSPORTS/html/Chen_FieldMOT_A_Field-Registered_Multi-Object_Tracking_for_Sports_Videos_CVPRW_2025_paper.html).

Do not replace one end-to-end keypoint model with another. Use a hybrid:

- Learned line/arc/keypoint segmentation.
- Geometric correspondence.
- Differentiable or nonlinear camera optimization.
- Temporal smoothing with reset at cuts.
- Per-frame covariance and failure detection.

[TVCalib](https://arxiv.org/abs/2207.11709) and [PnLCalib](https://arxiv.org/abs/2404.08401) are closer to the right architecture: learned perception feeding an explicit camera model and reprojection objective.

Synthetic pitch renders are excellent for the perception front end and adversarial camera coverage. They do not eliminate the need for real-line annotations and real-domain validation.

## Synthetic data: useful, not a superpower

My rating:

- **Pitch renders: 7/10.** Strong for geometry, controlled camera coverage, regression tests, and pretraining. Domain gap remains in turf, lighting, occlusion, lens distortion, line wear, shadows, overlays, and compression.
- **Jersey composites: 4/10.** Useful for digit-shape pretraining and rare-number balance. Weak on cloth deformation, pose, partial visibility, font distributions, compression, and contextual crop selection.
- **Physics-composited balls: 2/10 as detector training; 8/10 as an inference prior and test generator.** The hard part is not generating a legal parabola. It is matching tiny-object appearance, blur, camera motion, occlusion, compression, distractors, and player interaction.

“Zero rights risk” is also too broad. A synthetic jersey placed on a real player crop and a simulated ball placed over a real background still inherit the rights status of those real images. Only fully synthetic scenes or composites over rights-green media are clean by construction.

Likewise, SkillCorner data as described in the charter clearly supplies canonical tracking. It should not be counted as rights-clean pixel-training data unless the registry proves that corresponding video and derivative training rights are included.

Synthetic data should earn its place through ablations: real-only, synthetic-only, real-plus-synthetic, and matched-label-budget comparisons on untouched real domains. Infinite volume is irrelevant if the generated distribution omits the failure modes.

## The flywheel is naive

“Pre-label → uncertainty-sample → correct → retrain” omits the difficult parts.

First, model uncertainty is least trustworthy under domain shift. High-confidence errors will never be selected. Straight uncertainty sampling also over-selects inherently ambiguous or unlabelable examples and redundant adjacent frames.

Second, video labels are structured. Correcting one player box without correcting the surrounding tracklet, calibration, identity, and occlusion status can create internally inconsistent supervision.

Third, prelabels anchor annotators. Pseudo-label bias in object detection is established enough that teacher-student systems explicitly compensate for it rather than treating prelabels as neutral. [Unbiased Teacher](https://arxiv.org/abs/2102.09480).

Fourth, “every pilot match improves every future match” is false. A Veo tactical camera, a TV broadcast, a rainy night match, and a low-resolution academy recording are different domains. Updating globally on one may harm another. Maintain a global foundation plus domain profiles or adapters, and promote only when cross-domain gates pass.

The corrected loop is:

1. Attribute wide intervals and wrong answers to concrete evidence failures.
2. Form candidate clips and tracklets from uncertainty, model disagreement, high-confidence audit failures, domain novelty, rare events, and coach value.
3. Select a temporally diverse batch by expected downstream value per annotation minute.
4. Correct structured clips with blind gold audits and occasional double labeling.
5. Train with labeled data, replay data, and guarded teacher-student pseudo-labels.
6. Evaluate on untouched and rotating camera/team domains, including calibration and worst-group risk.
7. Canary the new model; compare query outputs; roll back automatically on safety regression.
8. Preserve consent, provenance, deletion, and customer-domain boundaries.

Clip-level uncertainty and temporal diversity are already a more appropriate active-learning unit for modern MOT than independent frames. [CUTAL](https://arxiv.org/abs/2605.09858).

## What the doctrine missed entirely

### The capture system is part of the model

The own-footage charter already knows this, but the training doctrine sidelines it. For the intended pilot, better mounting, more pixels per player, stable all-22 coverage, or a second cheap camera may narrow intervals more cheaply than another model run.

Capture specification belongs in the same investment optimizer as training. The best model improvement may be changing the input distribution.

### Broadcast and club tactical film need separate profiles

The doctrine lets broadcast ball difficulty dominate priorities. But the coach-upload promise may first encounter Veo/Hudl-style tactical footage: wider coverage, fewer cuts, steadier calibration, smaller players, and different compression.

Build separate fidelity tables and model profiles. Do not spend the first training era solving the hardest broadcast identity problem if the first customer distribution is controlled tactical video.

### Player detection is not explicitly a rung

The audit says the player detector is also off-the-shelf, yet the ladder names only ball detection. Player, goalkeeper, referee, substitute, and staff detection need their own error taxonomies. Every later rung depends on player crops and tracklets.

### Possession and event state are missing

The flagship is not merely a ball-position query. “Carry,” “controlled pass,” “under pressure,” and “keep it” require ball state, possessor identity, contact transitions, and synchronized event inference. A better ball detector can leave the flagship vacuous if possession state is wrong.

### Uncertainty calibration and propagation are absent

Detection confidences, identity posteriors, and homography errors must be calibrated on target domains and propagated into the canonical layer. Otherwise UNKNOWN thresholds are arbitrary. The vision pipeline needs selective-risk curves and coverage calibration, not only point metrics and query agreement.

### Frozen evaluation is not enough

A frozen set repeatedly consulted for model and ladder decisions becomes an adaptive development set. Keep:

- A visible development panel.
- An untouched sealed panel.
- A rotating acquisition panel.
- Leave-camera, leave-venue, leave-team, and leave-season splits.

The public SoccerNet-GSR task itself is integrated across camera localization, tracking, role, team, and jersey identity; that is a warning against optimizing isolated heads. [SoccerNet Game State Reconstruction](https://arxiv.org/abs/2404.11335).

### Annotation QA needs a constitution equal to execution QA

The doctrine governs model runs more strongly than the labels those runs would trust. It needs:

- Label schemas and ambiguity policy.
- Inter-annotator agreement.
- Gold tasks and reviewer calibration.
- Prelabel-hidden audits.
- Structured consistency checks.
- Dataset-version diffs.
- Contamination and leakage checks.
- Revocation and deletion propagation.

### The compiler and perception flywheels must be one allocation system

This is the largest omission.

A coach’s wide interval should decompose into its causal upstream bottlenecks: missing ball segment, ambiguous team identity, calibration variance, or unsupported concept. Those evidence tokens should drive annotation and model investment. Conversely, a model improvement should be credited only for the query bounds it actually narrows without increasing false claims.

That is the real moat: not simply an honest compiler plus trained vision, but a compiler that tells the vision program exactly what evidence is economically worth improving.