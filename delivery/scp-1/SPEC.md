# SCP-1 - Semantic Expression Compiler and Generality Harness

## Outcome

SCP-1 establishes a typed semantic-expression language and natural-language
compiler whose scope is broader than the currently executable library.

Priori should be able to take a previously unseen football idea in ordinary
language and either:

1. compile it into a type-correct semantic program that lowers into the
   existing deterministic runtime; or
2. compile as much of the meaning as possible and return the smallest typed
   operationalization, modality, identifiability, or ambiguity gap preventing
   execution.

SCP-1 must not turn recipes into the boundary of the language. Recipes are
reviewed definitions, regression fixtures, examples, and shortcuts. They are
not the edge of what Priori can represent.

## North-Star Claim

For any football question whose meaning can be expressed in Priori's registered
semantic algebra and whose evidence is identifiable from the available
modalities, Priori can compile the question into a typed program, execute it,
and return evidence-backed moments, or identify the smallest semantic,
computational, or data gap preventing that result.

## Support Levels

SCP-1 evaluates support as five separate facts, not one binary flag.

```text
EXPRESSIBLE
The semantic language can represent the intended football meaning.

COMPILABLE
The compiler can translate natural language into that representation.

EXECUTABLE
The required operationalizations and runtime implementations exist.

IDENTIFIABLE
The available data modalities can support the requested claim.

VALIDATED
The resulting detector or behavior has empirical validation evidence.
```

A query can be expressible and compilable while not executable. It can be
executable but not identifiable from tracking/events alone. These distinctions
must be first-class output, not collapsed into "supported" or "unsupported."

## Typed Semantic Gaps

The semantic language must be broader than the executable library.

A natural-language request may compile into a type-correct semantic program even
when one node cannot yet execute. The missing node must be represented as a
typed gap, never as a free-text placeholder and never as executable runtime
code.

Typed gaps must declare:

- gap kind:
  - `MISSING_TYPE`
  - `MISSING_OPERATOR`
  - `MISSING_CONCEPT`
  - `MISSING_OPERATIONALIZATION`
  - `MISSING_RUNTIME_IMPLEMENTATION`
  - `MODALITY_GAP`
  - `NON_IDENTIFIABLE`
  - `CLARIFICATION_REQUIRED`
  - `COMPILER_ERROR`
- smallest missing concept or operationalization;
- expected input types;
- expected output type;
- semantic basis;
- required modalities;
- claim boundary;
- evidence obligations;
- whether the surrounding program remains type-correct;
- whether any executable prefix/suffix exists.

Example:

```yaml
status: CAPABILITY_GAP
semantic_program: valid
executable: false
blocking_gap:
  kind: MISSING_OPERATIONALIZATION
  concept: restart_taken
  expected_input:
    - dead_ball_state
    - ball_location
    - contact_candidate
    - ball_motion_transition
  expected_output:
    type: CandidateSet<RestartTaken>
  required_modalities:
    - tracking
  evidence_obligations:
    - stationary_ball_interval
    - restart_location
    - contact_actor
    - first_live_ball_frame
```

This lets Priori evaluate football understanding before every library component
exists, while still preventing non-existent capabilities from executing.

## Football Query Normal Form

Natural-language programs should compile toward a common structure before they
lower to runtime plans.

```text
SCOPE
Which matches, teams, possessions, phases, or game states?

ANCHOR
Which observed or reconstructed event, transition, episode, or behavior starts
the search?

BIND
Which players, roles, teams, units, regions, or dynamic sets are referenced?

MEASURE
Which states, movements, spatial relations, fields, counts, or episodes are
computed?

MATCH
Which logical, temporal, quantitative, and completeness conditions must hold?

OUTCOME
Which subsequent event, state, transition, or behavior must occur?

JUDGE
Which profile, threshold, definition, or classification applies?

RETURN
Which evidence, uncertainty, result fields, and replay objects are required?
```

Recipes become named macros over this normal form. The compiler should be able
to produce normal-form programs without selecting a recipe.

## Anchor Synthesis

SCP-1 must treat anchor creation as first-class. A search anchor may originate
from:

- provider events;
- existing runtime anchors;
- state transitions;
- boundary crossings;
- control gain or loss;
- ball becoming live or dead;
- region entry or exit;
- pressure change points;
- unit deformation;
- possession recovery;
- temporal sequences;
- reconstructed restart candidates.

This is required for questions about events not directly modeled in the source
data, such as restart-like situations, and for collective behavior that emerges
from continuous tracking rather than event labels.

## Goal-Kick Forcing Case

Goal kicks are a reference case for reconstructed anchors and typed gaps.

Priori must distinguish:

```text
GOAL_KICK_AWARDED
Requires enough evidence about why play stopped, including boundary crossing
and last-touch evidence.

GOAL_KICK_RESTART_TAKEN
Requires sufficient restart evidence.

GOAL_KICK_RESTART_CANDIDATE
Tracking configuration strongly resembles the restart, but one or more
authoritative premises are unresolved.
```

SCP-1 does not need to implement goal-kick execution. It must be able to compile
goal-kick-like natural-language requests into either a valid semantic program or
a precise typed gap such as `restart_taken_candidate`.

## Compiler Outcomes

The compiler must return one of:

```text
COMPILED
COMPILED_WITH_DISCLOSED_DEFAULT_PROFILE
CLARIFICATION_REQUIRED
CAPABILITY_GAP
MODALITY_GAP
NON_IDENTIFIABLE
COMPILER_ERROR
```

Gap responses must identify the smallest missing basis element. For example:

```text
Missing operationalization: restart_taken_candidate
```

not:

```text
Priori does not support goal kicks.
```

## Evaluation Modes

SCP-1 must evaluate compiler generality in two modes.

### Closed-Book Composition

The compiler may see:

- concepts;
- types;
- operators;
- definition profiles;
- evidence contracts;
- exposure limits.

It may not see tactically similar recipes. This tests whether Priori can compose
from the algebra rather than retrieve and adapt recipe-shaped plans.

### Open-Library Composition

The compiler may inspect reviewed recipes and examples. This tests normal
product usefulness.

Both results must be reported. A large gap means Priori is still mainly a
recipe retriever.

## Football Program Corpus

SCP-1 must introduce a corpus that drives compiler and library evaluation.

Each case should contain:

```yaml
natural_language:
  original:
  paraphrases:
  coaching_language_variants:

intended_semantics:
  acceptable_expression_graphs:
  unacceptable_interpretations:
  material_ambiguities:

expected_status:
  EXPRESSIBLE:
  COMPILABLE:
  EXECUTABLE:
  IDENTIFIABLE:
  VALIDATED:

expected_compiler_outcome:
  - COMPILED
  - COMPILED_WITH_DISCLOSED_DEFAULT_PROFILE
  - CLARIFICATION_REQUIRED
  - CAPABILITY_GAP
  - MODALITY_GAP
  - NON_IDENTIFIABLE

evidence_requirements:
prohibited_claims:
synthetic_test_worlds:
real_positive_examples:
real_negative_examples:
```

The corpus must include:

- observed events;
- reconstructed events;
- states;
- transitions;
- continuous behaviors;
- collective behavior;
- temporal sequences;
- absence and negative claims;
- ambiguity;
- modality gaps;
- non-identifiable claims.

Hold out combinations, not merely paraphrases. For example, if training cases
include restart reconstruction, high pressure, and opposite-side exits
separately, evaluation should include their novel composition.

## Initial Evaluation Classes

SCP-1 acceptance must include at least these six classes:

1. Existing-recipe parity.
2. Novel executable composition.
3. Reconstructed-anchor composition.
4. Precise capability gap.
5. Modality or identifiability gap.
6. Clarification-required ambiguity.

Initial target cases:

- High-Bypass Completed Pass: action-spanning parity case.
- Ball-Side Block Shift: continuous-behavior parity case.
- Goal-kick-like restart followed by short build-up and opposite-side exit:
  reconstructed-anchor or typed-gap case.
- Counterpress after central possession loss: novel collective sequence.
- No teammate arrived in support within three seconds of penetration: negative
  claim requiring complete evaluation-domain proof.
- Receiver scanned before receiving: modality-gap case.
- Find high presses: ambiguous-profile case.

For negative claims, Priori may return `FAIL` only when the eligible actors and
full evaluation interval were observed. Otherwise it must return `UNKNOWN`.

## Generality Metrics

SCP-1 should report:

- recipe-free novel query success;
- semantic-equivalence accuracy;
- minimal-gap localization accuracy;
- clarification accuracy;
- execution retrieval precision and recall where executable;
- evidence completeness;
- `UNKNOWN` correctness;
- paraphrase invariance;
- open-library versus closed-book performance delta.

The main dashboard should be a query coverage matrix:

| Query | Expressible | Compilable | Executable | Identifiable | Validated | Smallest Gap |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Goal-kick opposite exit | Yes | Yes | No | Likely | No | restart reconstruction |
| High-bypass pass | Yes | Yes | Yes | Yes | Partial | validation depth |
| Scanning before receive | Yes | Yes | No | No | No | video/pose |
| No support after break | Yes | Yes | Partial | Conditional | No | coverage certificate |

## Library Priority Rule

Every failed program should be classified as:

- missing type;
- missing operator;
- missing concept;
- missing operationalization;
- missing runtime implementation;
- missing modality;
- ambiguous definition;
- non-identifiable claim;
- compiler error.

Implementation priority should follow query classes unlocked:

```text
unlock value =
  number of blocked queries
  x diversity of football families unlocked
  x expected reuse
  x evidenceability
  / implementation and validation cost
```

This should push investment toward reusable foundations before many isolated
named detectors:

- ball live/dead state;
- control candidates;
- touch/contact candidates;
- boundary crossings;
- restart setup and restart taken;
- possession continuity;
- dynamic player sets;
- team units and shape;
- pressure and reachability;
- support relations.

## Implementation Constraint

SCP-1 must lower into the existing `TacticalQueryDocument`, binder, and
deterministic runtime. It should not introduce a new executor.

Conceptual path:

```text
SemanticExpression
-> Football Query Normal Form
-> existing TacticalQueryDocument
-> existing binder
-> existing deterministic runtime
```

Typed gaps stop before runtime execution.

## Non-Goals

SCP-1 must not:

- implement the full five-year capability atlas;
- expose unimplemented concepts as executable;
- let Hermes run arbitrary code;
- add a new executor;
- replace the existing binder/runtime authority chain;
- infer unsupported modalities such as scanning, intent, body orientation, or
  pass probability from tracking alone;
- hide ambiguity behind default profiles without disclosure;
- treat recipes as the language boundary.

## Acceptance Criteria

SCP-1 is accepted only when:

1. `SemanticExpression` has typed references for scopes, anchors, bindings,
   measures, match conditions, outcomes, judgments, returns, and typed gaps.
2. Semantic programs can represent both executable nodes and non-executable
   typed gaps.
3. Typed gaps include expected input/output types, modality requirements, claim
   boundaries, and evidence obligations.
4. The compiler can produce Football Query Normal Form before lowering to
   runtime plans.
5. Anchor synthesis is representable for at least one reconstructed-anchor case,
   even if it returns a typed missing-operationalization gap.
6. Existing High-Bypass Completed Pass can be represented and lowered to the
   current runtime path.
7. Existing Ball-Side Block Shift can be represented and lowered while
   preserving reviewed-plan-only boundaries.
8. At least one novel executable composition compiles without relying on a
   tactically similar recipe.
9. At least one reconstructed-anchor request compiles to a precise typed gap.
10. At least one modality-gap request compiles to a precise modality gap.
11. At least one ambiguous request returns `CLARIFICATION_REQUIRED`.
12. At least one negative/absence request preserves completeness and `UNKNOWN`
    semantics.
13. Closed-book and open-library evaluation modes both run and report results.
14. The Football Program Corpus exists with held-out combinations.
15. Evaluation judges semantic or execution equivalence, not raw JSON string
    equality alone.
16. No typed gap is executable.
17. No unimplemented concept appears in the AI-visible surface as if executable.
18. All successful executable compilations still pass through the existing
    binder, host confirmation, deterministic runtime, evidence projection, and
    replay contracts.

## Side Effects

SCP-1 is Tier 1 local reversible work until explicitly promoted. It may add
schemas, corpus fixtures, compiler code, tests, generated reports, and review
packets. It must not deploy, change production behavior, or alter runtime
authority without explicit approval.
