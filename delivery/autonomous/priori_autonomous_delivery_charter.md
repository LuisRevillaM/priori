# Priori Autonomous Delivery Charter

## Purpose

This charter is intended to let a capable local engineering agent take Priori from the current Semantic Control Plane foundation to an ambitious, general football-language system without requiring a human architectural review at every milestone.

The builder is allowed to proceed autonomously only when a protected verifier proves that the current milestone satisfies its contract. The builder may repair implementation failures, add tests, and improve the system. It may not weaken the milestone, shrink the benchmark, rewrite expected answers, broaden waivers, or promote itself.

The intended final outcome is not a larger recipe catalog. It is an executable, evidence-carrying football language:

> Given a previously unseen football idea in natural language, Priori can compile it into a typed tactical program, execute it when the registered library and available modalities support it, return evidence-backed moments, and otherwise identify the smallest precise semantic, operationalization, data, or validation gap.

Recipes are reviewed macros, regression fixtures, examples, and product shortcuts. They are not the boundary of what Priori can articulate.

---

# 1. The hard constraint: the builder cannot also be the final judge

No acceptance criteria can prevent reward hacking if the same agent can freely modify:

- implementation code;
- the milestone specification;
- the evaluator;
- hidden tests;
- expected outputs;
- baselines;
- score denominators;
- waivers; and
- the final status.

Therefore autonomous delivery requires a small **Trusted Verification Boundary** outside the builder's writable workspace.

## 1.1 Trusted Verification Boundary

The protected boundary contains:

```text
steward/
  milestone-contracts/
  schemas/
  gate-runner/
  protected-properties/
  protected-mutations/
  holdout-manifests/
  scoring-policies/
  promotion-policies/
  trusted-public-keys/
```

The builder may read public contracts and public tests. It may not write the protected boundary.

Protected holdout examples, generation seeds, and human labels live in CI, a separate repository, or an access-controlled artifact store. The builder receives only:

```text
pass/fail by proof obligation
aggregate metrics
counterexample category
opaque counterexample ID
sanitized reproduction where disclosure will not destroy the holdout
```

A change to the protected boundary is not an ordinary implementation change. It creates a new verifier version, invalidates previous promotion claims where applicable, and requires explicit steward review.

If the local agent has operating-system-level access to every file and secret, the process can produce strong evidence but not independent proof. Real autonomous promotion requires access separation.

---

# 2. North Star

## 2.1 User-facing North Star

For an unseen natural-language football request, Priori must produce exactly one of:

```text
COMPILED
COMPILED_WITH_DISCLOSED_PROFILE
CLARIFICATION_REQUIRED
CAPABILITY_GAP
MODALITY_GAP
NON_IDENTIFIABLE
VALIDATION_GAP
```

For a successful executable query, Priori must:

```text
understand the football meaning
→ form a typed semantic program
→ synthesize observed or reconstructed anchors
→ bind concepts to reviewed profiles and operationalizations
→ compile to the trusted runtime plan
→ validate the translation
→ execute deterministically
→ return matching moments
→ expose clause-level evidence, coverage, uncertainty, and provenance
```

For a non-executable query, Priori must preserve the type-correct surrounding program and identify the smallest missing element.

## 2.2 Five independent support dimensions

Every query and every named concept is assessed independently on:

```text
EXPRESSIBLE
The semantic language can represent the intended claim.

COMPILABLE
The natural-language compiler can produce that representation.

EXECUTABLE
Registered operationalizations and runtime implementations exist.

IDENTIFIABLE
The available modalities can support the requested claim.

VALIDATED
Empirical evidence supports the operationalization at the claimed assurance level.
```

None implies the next. A query may be expressible but not executable. A detector may execute but not yet be validated. A concept may be identifiable only as an inferred candidate.

## 2.3 Semantic scope

The language must represent:

```text
Observation
State
Transition
Event
Episode
Behavior
Collective behavior
Situation
Sequence
Measurement
Candidate set
Distribution
Judgement
Evidence
Gap
```

An anchor may originate from:

```text
provider event
state transition
boundary crossing
control change
region entry
change point
reconstructed restart
pressure change
unit deformation
temporal composition
```

The language must therefore discover events as well as consume them.

---

# 3. What counts as proof

There is no single proof that a football interpretation is universally correct. Priori uses a layered assurance model.

## 3.1 Machine-checkable guarantees

These may be treated as hard proof obligations:

```text
schema validity
referential integrity
type safety
unit and coordinate-frame safety
bounded execution
authority and exposure policy
compiler translation validity for a particular program
determinism
provenance integrity
evidence-reference integrity
coverage rules for negative claims
absence of undeclared runtime dependencies
```

## 3.2 Synthetic semantic guarantees

On generated worlds with known ground truth, Priori can prove:

```text
the expression has the expected denotation
the compiler preserves that denotation
the runtime agrees with the reference interpreter
PASS/FAIL/UNKNOWN follows the declared evidence state
metamorphic invariants hold
```

## 3.3 Empirical football validation

Real-match meaning requires empirical evidence:

```text
human-reviewed positive examples
human-reviewed counterexamples
boundary and ambiguity examples
inter-rater agreement
precision and recall
calibration for inferred/modelled outputs
failure analysis by context
```

A milestone must never convert empirical uncertainty into a formal proof claim.

## 3.4 Assurance ladder for a capability

```text
PROPOSED
SEMANTICALLY_REVIEWED
TYPE_CHECKED
REFERENCE_EXECUTABLE
RUNTIME_CONFORMANT
SYNTHETICALLY_VERIFIED
EMPIRICALLY_VALIDATED
AGENT_SAFE
PRODUCT_EXPOSED
```

The final two states require every preceding state that is applicable.

---

# 4. Anti-reward-hacking constitution

These rules apply to every milestone.

## 4.1 Fixed denominators

The builder may not improve a score by removing hard cases, changing family labels, reclassifying failures as out of scope, or reducing test counts.

Every report includes:

```text
expected denominator
observed denominator
missing cases
excluded cases
exclusion reasons
```

Any unapproved denominator change fails the gate.

## 4.2 No self-authored oracle as sole evidence

A test where the same implementation generates both the result and expected answer is not sufficient.

Each semantic claim must be checked by one or more independent oracles:

```text
hand-reviewed fixture
reference interpreter
synthetic-world generator with known truth
differential implementation
metamorphic relation
protected holdout label
```

## 4.3 Hidden and systematic holdouts

Random train/test splits are insufficient. Holdouts must include unseen combinations of familiar concepts, structures, operators, and football families.

Examples:

```text
seen separately:
  goal-kick restart
  high press
  opposite-side exit

held out:
  goal-kick restart followed by high press and opposite-side exit
```

Near-duplicate recipes and paraphrases must be excluded from recipe-free holdouts.

## 4.4 Mutation adequacy

For every critical verifier, the protected suite injects known faults, including:

```text
dropping a required evidence field
reversing an inequality
changing a unit
removing a coordinate transform
treating UNKNOWN as FAIL
omitting an eligible player
broadening an exposure policy
changing a temporal boundary
rewiring a concept to the wrong operationalization
accepting an unregistered operator
fabricating evidence IDs
```

A milestone cannot pass unless its tests kill all critical protected mutants.

## 4.5 Metamorphic invariants

The gate tests relations that should hold even when exact expected outputs are difficult to enumerate:

```text
pitch reflection
team-perspective swap
time translation
frame-rate-resampling tolerance
threshold monotonicity
paraphrase invariance
recipe/expression equivalence
data-removal honesty
entity-renaming invariance
irrelevant-player invariance
```

## 4.6 Differential execution

Where two implementations exist, the verifier compares:

```text
reference interpreter
production runtime
legacy plan
new compiled plan
alternative operationalization where semantic equivalence is claimed
```

Differences require a field-specific, hash-pinned waiver. Subject-wide waivers are prohibited.

## 4.7 No clarification, gap, or UNKNOWN gaming

The compiler cannot maximize apparent correctness by refusing difficult queries.

The benchmark separately scores:

```text
unnecessary clarification
false capability gap
false modality gap
false NON_IDENTIFIABLE
incorrect UNKNOWN
overconfident execution
```

Known executable queries must compile. Known ambiguous queries must clarify. Known impossible claims must not execute.

## 4.8 No recipe retrieval gaming

Every compiler release is tested in:

```text
CLOSED_BOOK
No tactically similar recipe or worked example is visible.

OPEN_LIBRARY
Reviewed recipes may be used as macros or examples.
```

Both scores are reported. Closed-book performance is the primary generality metric.

## 4.9 Waiver discipline

A waiver must pin:

```text
subject
difference kind
old hash
new hash
permitted fields
rationale
owner
expiry or removal condition
```

Stale, duplicate, broadened, or newly mismatching waivers fail. Critical safety, type, evidence, and hidden-holdout failures are not waivable.

## 4.10 Promotion is computed

The builder writes implementation and a milestone claim. Only the protected gate may emit:

```text
PROMOTED
```

A self-authored status field has no authority.

---

# 5. Standard milestone contract

Every milestone is expressed using the following fields.

```yaml
id:
version:
purpose:
depends_on:
scope:
non_goals:
trusted_inputs:
deliverables:

proof_obligations:
  structural:
  semantic:
  translation:
  execution:
  evidence:
  empirical:
  generalization:
  safety:
  reproducibility:
  mutation:

test_partitions:
  public_development:
  protected_holdout:
  generated:
  metamorphic:
  real_reviewed:

thresholds:
  hard_zero_tolerance:
  quantitative:
  confidence_bounds:

forbidden_shortcuts:
promotion_rule:
failure_outputs:
review_packet:
```

A milestone passes only if every mandatory obligation passes in the same locked run.

## 5.1 Required review packet

Every promoted milestone emits:

```text
milestone-claim.json
gate-result.json
registry.lock
source-tree.hash
runtime-manifest.json
semantic-diff.json
test-denominators.json
public-test-report.json
protected-holdout-report.json
property-test-report.json
metamorphic-report.json
differential-report.json
mutation-report.json
performance-report.json
known-limitations.yaml
waivers.yaml
reproduction.md
artifacts.sha256
```

The packet is immutable and content-addressed.

---

# 6. Autonomous operating loop

The local agent repeats:

```text
1. Read the current milestone contract.
2. Inspect prior gate failures and counterexamples.
3. Implement without changing the protected contract.
4. Run local public checks.
5. Produce a candidate packet.
6. Submit to the protected gate.
7. If PASS, promote and begin the next milestone.
8. If FAIL, repair implementation.
9. If the contract is contradictory or impossible, emit SPEC_BLOCKED
   with a minimal counterexample instead of weakening the contract.
10. If the data cannot identify the claim, emit DATA_OR_MODALITY_BLOCKED.
```

The agent may proceed without human review when:

```text
all mandatory obligations pass
no protected file changed
no critical waiver exists
the semantic diff is within the milestone scope
performance ceilings hold
the prior milestone remains green
```

The agent must stop for steward review when:

```text
a protected contract appears inconsistent
a new modality is required
a legal/ethical data issue appears
a concept requires an intention/causality claim beyond available evidence
a backwards-incompatible public semantic change is proposed
a critical safety obligation cannot be met
a new model materially changes claim calibration
```

---

# 7. Roadmap

## M0 — Autonomous Verification Kernel and SCP-0 Closure

### Purpose

Close SCP-0E.1 and establish the protected gate that will judge every later milestone.

### Deliverables

```text
symmetric EXACT signature checking
typed runtime-context manifest
protected milestone schema
protected mutation suite
gate-runner CLI/service
immutable promotion record
versioned review-packet builder
```

### Mandatory proof obligations

```text
Every current runtime ID/version has exactly one canonical binding.
EXACT rejects missing metadata in either direction.
Only explicit `any` acts as a wildcard.
Optional semantic ports must also be bound under EXACT.
Unknown runtime contexts fail.
All critical signature mutations fail.
Failed generation cannot publish artifacts.
Every generated projection is lock-addressed.
```

### Promotion rule

All SCP-0 obligations and all protected M0 mutations pass. No SCP-1 implementation begins on a non-promoted semantic foundation.

---

## M1 — Semantic Expression Kernel

### Purpose

Create a language broader than the current executable catalog while retaining a bounded, non-Turing-complete form.

### Deliverables

```text
SemanticExpression AST
Football Query Normal Form
TypeRef and quantity system
coordinate-frame and perspective types
state/transition/event/episode/behavior/situation nodes
bounded quantification
temporal relations
measurement versus judgement separation
typed semantic gap nodes
reference interpreter for finite synthetic worlds
canonical serializer and hash
```

### Football Query Normal Form

```text
SCOPE
ANCHOR
BIND
MEASURE
MATCH
OUTCOME
JUDGE
RETURN
```

### Required operators

At minimum:

```text
logical:
  and, or, not, implies

comparison:
  eq, neq, gt, gte, lt, lte, between

quantification:
  exists, forall, count, count_at_least, argmin, argmax

temporal:
  before, after, meets, overlaps, during, starts, finishes
  within, followed_by, until, persists_for

episode:
  enter, exit, cross, begins, ends, change_point

set:
  filter, union, intersection, difference, group_by_anchor

measurement:
  distance, signed_distance, centroid, duration, rate, delta
```

### Mandatory proof obligations

```text
All well-typed generated programs parse, serialize, and round-trip.
All protected ill-typed programs are rejected.
Units and frames cannot be mixed without an explicit transform.
Unbounded recursion and arbitrary code are impossible.
Negative judgements require a declared closed evaluation domain.
Gap nodes are typed but non-executable.
Reference interpretation is deterministic.
Operator laws and UNKNOWN propagation hold on generated worlds.
```

### Quantitative gate

```text
>= 100,000 generated valid programs without crash
100% rejection of protected invalid programs
100% kill rate for critical type/operator mutants
0 nondeterministic canonical hashes
```

---

## M2 — Translation-Validated Compilation to the Existing Runtime

### Purpose

Compile `SemanticExpression` into the existing `TacticalQueryDocument`, binder, and deterministic runtime without adding a second executor.

### Deliverables

```text
SemanticExpression compiler
source-to-target mapping trace
per-compilation validation certificate
reference-to-runtime differential harness
legacy recipe importer
semantic plan normalizer
```

### Translation certificate

Each compiled program carries:

```text
source semantic hash
target plan hash
concept/profile versions
binding versions
operator versions
proof obligations checked
unresolved gap list
evidence obligations
```

### Required pilots

```text
High-Bypass Completed Pass
Ball-Side Block Shift
```

### Mandatory proof obligations

```text
Every executable source node maps to a registered target construct.
Every target node is justified by a source node or declared lowering.
No claim contract is broadened.
No evidence obligation is dropped.
All existing recipes preserve semantic and execution behavior.
Reference interpreter and production runtime agree on generated worlds.
Compilation with a gap cannot execute.
```

### Quantitative gate

```text
100% current-recipe parity, with no unexplained difference
100% agreement on protected finite-world cases
0 undeclared target nodes
0 evidence-loss cases
all critical translation mutants killed
```

This milestone follows the principle of validating each translation rather than assuming that compiler correctness follows from passing examples.

---

## M3 — Football Program Corpus and Generality Harness

### Purpose

Create the benchmark that drives the language, compiler, and library without allowing the builder to define success after seeing failures.

### Corpus families

At minimum:

```text
restarts and set pieces
ball control and possession
passes, carries, dribbles, shots, recoveries
progression and line breaking
support and off-ball movement
width, overload, isolation, and switching
team units, shape, compactness, and occupation
pressing and defensive behavior
transitions, counterpress, and recovery
rest defense and counterattack exposure
goalkeeping behavior
multi-stage temporal situations
negative and absence claims
ambiguity and profile selection
modality, intention, causality, and optimality gaps
```

### Minimum corpus shape

Before thresholds are frozen, build and steward-review the corpus design. A recommended ambitious baseline is:

```text
>= 1,500 canonical query intents
>= 3 natural-language paraphrases per intent
>= 100 intents in each major football family
>= 25% novel cross-family compositions
>= 15% reconstructed-anchor queries
>= 15% negative/absence queries
>= 15% clarification cases
>= 15% capability/modality/non-identifiability gaps
```

Cases may belong to multiple categories.

### Partitions

```text
public development
public adversarial
protected lexical holdout
protected structural-composition holdout
protected recipe-free holdout
protected new-family holdout
```

### Mandatory proof obligations

```text
No near-duplicate leakage across systematic splits.
Every case has intended support dimensions.
Every case has acceptable semantic graphs or execution-oracle worlds.
Ambiguity cases enumerate material interpretations.
Gap cases identify the expected minimal missing cut.
Denominators are immutable after freeze.
Corpus revisions are versioned and invalidate incomparable scores.
```

### Promotion rule

The corpus and gate are usable before the natural-language compiler is scored. The builder cannot alter protected labels or split membership.

---

## M4 — Natural-Language Compiler v1

### Purpose

Compile unseen football language into a novel typed program or a precise typed gap.

### Deliverables

```text
natural language → FQNF
FQNF → SemanticExpression
concept/profile resolver
ambiguity detector
minimal-gap resolver
closed-book mode
open-library mode
semantic equivalence scorer
```

### Required outcomes

```text
COMPILED
COMPILED_WITH_DISCLOSED_PROFILE
CLARIFICATION_REQUIRED
CAPABILITY_GAP
MODALITY_GAP
NON_IDENTIFIABLE
VALIDATION_GAP
```

### Mandatory proof obligations

```text
No arbitrary code or undeclared capability is emitted.
Compiled output type-checks.
Profiles and defaults are disclosed.
Material ambiguities are not silently collapsed.
Gap reports preserve the valid surrounding program.
The reported gap is a minimum unsatisfied dependency cut.
Equivalent paraphrases produce equivalent semantics.
Closed-book mode cannot access similar recipes.
```

### Initial promotion thresholds

Freeze exact thresholds before model iteration. Recommended starting targets:

```text
100% safety/type validity on emitted programs
>= 90% semantic-equivalence accuracy on expressible protected cases
>= 90% correct top-level outcome class
>= 85% exact minimal-gap localization
>= 90% clarification precision and recall
<= 10 percentage-point gap between open-library and closed-book semantic accuracy
```

No threshold can be met by excluding failed cases or converting executable cases into gaps.

---

## M5 — World-State Reconstruction and Derived Events

### Purpose

Allow Priori to discover events absent from provider event data and use them as anchors.

### Foundation package

```text
tracking_presence
expected_entity_set
active_membership_timeline
ball_in_play_state
dead_ball_interval
touch_candidate
contact_candidate
player_control_candidate
team_control_candidate
control_gain
control_loss
physical_release
physical_reception
boundary_crossing
last_touch_candidate
same_possession_continuity
restart_setup_candidate
restart_taken_candidate
restart_type_profile
```

### Forcing cases

```text
goal-kick restart
corner restart
throw-in restart
kick-off restart
free-kick-like restart
```

Distinguish:

```text
AWARDED
TAKEN
CANDIDATE
```

Do not infer `AWARDED` where prior-play or last-touch evidence is insufficient.

### Mandatory proof obligations

```text
Provider events remain immutable observations.
Reconstructed facts retain candidate confidence and evidence.
Event anchors, physical anchors, and tactical anchors remain distinct.
Removing prerequisite evidence weakens certainty rather than fabricating FAIL.
All restart families lower through shared state/transition primitives.
Goal kick is not implemented as an isolated question-specific detector.
```

### Validation gate

```text
100% exact behavior on synthetic restart worlds
protected real-match positive, negative, and ambiguous windows
reported precision/recall with confidence intervals
candidate-versus-confirmed calibration
zero claim escalation from TAKEN/CANDIDATE to AWARDED
```

---

## M6 — General Spatiotemporal Algebra

### Purpose

Build the reusable mathematical basis needed by many football concepts.

### Required basis

```text
dynamic entity sets
ordered entity sets
trajectories
dynamic regions
lines and curves
coordinate transforms
distances and bearings
region entry/exit/crossing
reachability and arrival time
interception margin
fields over the pitch
graphs over players and relations
change points
hysteresis and gap tolerance
coverage and uncertainty propagation
```

### Mandatory properties

```text
pitch-reflection invariance
team-perspective invariance
time-translation invariance
entity-renaming invariance
resampling stability within declared tolerances
monotonic threshold behavior
bounded computational cost
evidence propagation through every operator
```

### Promotion rule

The basis is not considered complete because it has many functions. It passes when the protected query corpus shows that new tactical ideas usually lower to existing generic operators rather than requiring question-specific geometry.

---

## M7 — Collective Football Basis

### Purpose

Represent possession-oriented collective behavior rather than only discrete actions.

### Standard-library foundations

```text
team shape:
  width, length, area, orientation, compactness, deformation

units and lines:
  unit hypotheses, line hypotheses, line height, spacing, integrity

pressure and reachability:
  pressure intensity, pressure actors, closing relation,
  cover shadow, reachable options, pitch control

support and accessibility:
  support angle/depth/width, option availability,
  local numbers, free player, spare player, receiver isolation

space and occupation:
  lane occupation, weak-side occupation, between-unit occupation,
  accessible space, opening/closing space, overload/isolation

transitions:
  loss/regain anchors, counterpress, recovery, reorganization,
  rest-defense shape, outlet availability
```

### Claim ladder

For behavior, preserve:

```text
OBSERVED_MOVEMENT
RELATIONAL_EFFECT
TACTICAL_ATTRIBUTION_CANDIDATE
COUNTERFACTUAL_EFFECT_ESTIMATE
INTENTION_ANNOTATED
```

Tracking alone must not silently promote movement effects to intention.

### Mandatory proof obligations

```text
Every named behavior lowers to reusable measurements and temporal relations.
Continuous measurements remain available below thresholds.
Competing operationalizations are versioned rather than conflated.
Collective claims expose the relevant player set and coverage.
No named concept hides unregistered mathematics.
```

---

## M8 — Standard Library Expansion and Atlas Closure

### Purpose

Turn the five-year atlas into a reviewed semantic map and implement the highest-unlock basis, without treating 741 names as 741 code paths.

### Every atlas entry receives one disposition

```text
REDUCIBLE
PROFILE_VARIANT
ALIAS
NEW_OPERATOR_REQUIRED
NEW_OPERATIONALIZATION_REQUIRED
MODEL_REQUIRED
NEW_MODALITY_REQUIRED
NON_IDENTIFIABLE
REJECTED
```

No entry remains `UNCLASSIFIED`.

### Review output for each concept

```text
core meaning
claim ceiling
inputs and outputs
support dimensions
candidate operationalizations
profile dimensions
required modalities
evidence contract
prohibited claims
lowering expression or typed missing primitive
example queries
counterexamples
```

### Library prioritization

Use:

```text
query_unlock_value =
  blocked_query_count
  × football_family_diversity
  × expected_reuse
  × evidenceability
  ÷ implementation_and_validation_cost
```

Do not optimize detector count.

### Mandatory proof obligations

```text
All atlas entries classified.
Aliases and profile variants do not inflate capability counts.
Every REDUCIBLE entry compiles through the registered algebra.
Every executable entry has a runtime binding and evidence contract.
Every non-executable entry has a precise typed reason.
No atlas-only item leaks into product or agent surfaces.
```

---

## M9 — Validation Factory and Proof-Carrying Results

### Purpose

Make empirical validation and evidence generation systematic enough that new library items can be promoted without bespoke process.

### Deliverables

```text
capability passport generator
annotation protocol
blind review workflow
inter-rater agreement report
positive/negative/boundary sampler
error taxonomy
calibration report
evidence-derivation graph
coverage certificate
replay projection generator
```

### Proof-carrying result

Every execution result includes:

```text
value or candidate distribution
judgement
applicability
evaluation domain
coverage certificate
uncertainty
witnesses
counterevidence
derivation graph
source observations
semantic/profile/implementation versions
replay projection
```

### Mandatory proof obligations

```text
Every PASS has a witness.
Every FAIL has a complete evaluation domain.
Every UNKNOWN names unmet premises.
Every CONFLICT preserves supporting and refuting evidence.
Replay is derived from evidence, not independently narrated.
Negative claims require complete actor and time coverage.
```

### Empirical promotion policy

Product exposure is profile-specific. A deterministic or inferred capability cannot be labeled `VALIDATED` until its frozen validation protocol passes. Thresholds are fixed by concept family before implementation tuning and reported with confidence intervals.

---

## M10 — Natural-Language Compiler v2 and Open-World Generality

### Purpose

Re-evaluate the compiler after world reconstruction and collective basis expansion.

### Required challenge classes

```text
unseen event composition
unseen continuous behavior composition
reconstructed anchor followed by collective behavior
cross-family temporal sequences
absence with complete-domain reasoning
ambiguous coaching language
modality-limited claims
intent/causality/optimality traps
```

### Example North Star challenge

```text
Find goal kicks where the goalkeeper plays short,
at least five opponents commit high,
the first line is attracted toward the ball side,
and the team exits through the opposite side within twelve seconds
while retaining possession.
```

This must compile from basis concepts rather than a goal-kick recipe.

### Mandatory proof obligations

```text
Closed-book novel compositions are type-correct.
No near-duplicate recipe is accessed.
Semantic equivalence holds across paraphrases.
Minimal gaps remain accurate.
Execution evidence covers every clause.
Behavioral candidates do not become intention claims.
```

### Ambitious target metrics

These should be frozen against the protected corpus before the final optimization pass:

```text
>= 95% type-valid/safe compiler outcomes
>= 92% semantic-equivalence accuracy on expressible cases
>= 90% recipe-free systematic-composition accuracy
>= 95% top-level gap/clarification classification accuracy
>= 90% exact minimal-gap localization
>= 95% paraphrase semantic consistency
100% synthetic execution equivalence
0 critical evidence or claim-boundary violations
```

Report confidence intervals and every family separately. Macro averages may not hide a weak football family.

---

## M11 — Product Integration, Reliability, and Autonomous Query Flow

### Purpose

Expose the general language safely without changing the deterministic authority chain.

### Product flow

```text
natural-language request
→ semantic interpretation
→ disclosed profile or clarification
→ typed plan
→ deterministic validation
→ human confirmation where required
→ execution
→ result/evidence/replay
→ saved semantic query and provenance
```

### Required engineering

```text
versioned query persistence
job progress and cancellation
bounded multi-match execution
cache identity including semantic versions
failure and UNKNOWN histograms
result reproducibility
feature flags
shadow mode
canary rollout
rollback
```

### Mandatory proof obligations

```text
The agent cannot execute directly.
The agent cannot access raw files, SQL, Python, or terminal tools.
Unvalidated concepts cannot appear as product-supported.
Every product result identifies its semantic lock.
Rollback restores the previous supported surface.
Performance degradation remains within frozen ceilings.
```

---

## M12 — North Star Audit

### Purpose

Produce one final audit packet for human review after the autonomous run.

### Final demonstration set

The protected audit must include:

```text
existing recipe parity
novel executable compositions
reconstructed events absent from source events
continuous individual behavior
collective behavior
multi-stage situations
negative claims
clarification cases
capability gaps
modality gaps
non-identifiable claims
adversarial paraphrases
out-of-distribution football phrasing
```

### Final breadth conditions

```text
Every atlas entry has a reviewed disposition.
Every major football family has executable basis coverage.
No family is represented only by a canned recipe.
The closed-book compiler can produce novel programs in every major family.
The smallest missing primitive is identified when execution is impossible.
```

### Final hard gates

```text
0 critical safety violations
0 type/coordinate/unit violations
0 undeclared runtime dependencies
0 evidence-reference violations
0 stale or broad waivers
100% deterministic reproduction of the final audit
100% reference/runtime agreement on protected synthetic worlds
100% current recipe parity
100% atlas isolation for unsupported items
```

### Final empirical gates

Use the frozen M10 targets, family-level reporting, and profile-specific real-match validation. A concept that misses its empirical target remains executable-experimental or candidate-only; it is not promoted by averaging it with easier concepts.

---

# 8. Compiler and library scorecard

The gate publishes this matrix after every milestone:

| Dimension | Definition | Current | Target | Blocking gap |
|---|---|---:|---:|---|
| Expressibility | Corpus intents representable | | | |
| Compilability | Correct NL-to-semantics | | | |
| Executability | Required runtime paths exist | | | |
| Identifiability | Modalities support claim | | | |
| Validation | Profiles empirically validated | | | |
| Recipe-free composition | Closed-book novel success | | | |
| Gap minimality | Exact smallest missing cut | | | |
| Evidence completeness | Clauses with valid evidence | | | |
| UNKNOWN correctness | Honest missing-evidence behavior | | | |
| Atlas closure | Entries with reviewed disposition | | | |

The report must show family-level rows as well as global totals.

---

# 9. Capability passport

Every product-eligible capability or profile must have a generated passport:

```yaml
identity:
  concept:
  operationalization:
  profile:
  implementation:

support:
  expressible:
  executable:
  identifiable:
  validated:

types:
  inputs:
  outputs:
  units:
  coordinate_frames:
  temporal_semantics:

claims:
  permitted:
  prohibited:

quality:
  required_modalities:
  applicability:
  unknown_reasons:
  coverage_policy:
  uncertainty:

proof:
  reference_tests:
  differential_tests:
  metamorphic_tests:
  mutation_score:
  empirical_validation:
  known_limitations:

evidence:
  required_fields:
  replay_projection:

exposure:
  hermes:
  product:
```

The passport is generated from authoritative artifacts. It is not handwritten marketing.

---

# 10. Why this verification design is appropriate

The roadmap combines several established verification ideas:

- Property-based testing checks executable properties over generated inputs rather than relying only on examples.
- Metamorphic testing checks necessary relations between multiple executions when exact output oracles are difficult.
- Differential compiler testing compares independent implementations on generated valid programs.
- Translation validation checks each individual compilation result rather than requiring complete proof of the compiler implementation.
- Proof-carrying systems inspire the requirement that every executable artifact or result carry machine-checkable evidence of policy compliance.
- Systematic compositional holdouts test whether the semantic parser can combine familiar elements in unfamiliar structures.
- Mutation testing verifies that the test suite detects deliberately introduced faults.
- Reward-hacking controls prevent proxy metrics from replacing the underlying product objective.

These methods do not eliminate the need for football judgement. They sharply reduce the space in which implementation errors, benchmark shortcuts, semantic drift, or self-certification can masquerade as progress.

---

# 11. The autonomous instruction to the local agent

Use the following as the standing instruction:

> Build Priori through M0–M12 in order. You may proceed automatically when the protected gate promotes the current milestone. Do not weaken contracts, alter protected holdouts, shrink denominators, broaden waivers, or relabel failures to improve scores. When implementation is missing, implement the smallest reusable basis. When a claim is not identifiable from available data, preserve it as a typed modality or identifiability gap. When a semantic contract appears contradictory, stop with a minimal counterexample. Prefer general operators and operationalizations that unlock diverse query classes over question-specific detectors. Preserve the existing deterministic authority chain. The work is complete only when the protected North Star audit passes and the final packet is reproducible from its lock.
