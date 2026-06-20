# Prompt For External Review Agent

You are reviewing a planned architecture change for a soccer tactical evidence demo. You do not have repo access, so this prompt is self-contained. Please pressure-test the milestone design, sequencing, and downstream consequences. Do not treat the plan as gospel.

## Review Goal

We just completed M1 locally, according to the controller agent. Before implementing the next layer, we need your approval or critique of a proposed split:

- M1.1 - Composable Tactical Query Runtime
- M1.2 - Grounded Tactical Query Workshop

The central question:

> Is this the right architecture and sequencing before we build the broader query catalog, analyst workbench, Hermes assistant, and polished demo UI?

We especially care about downstream effects on M2-M6, not only whether M1.1/M1.2 are reasonable in isolation.

## Current Project Context

The project is an independent pre-meeting demo built from the public IDSSE / Sportec Open DFL tracking and event dataset. It does not assume Priori SDK/API access, private Priori data, production deployment, provider adapter readiness, or match video.

The desired final demo is a polished tactical evidence workbench:

- real coordinate replay from public tracking data;
- auditable tactical moments;
- deterministic query execution;
- evidence panels and predicate traces;
- eventually Hermes as a grounded assistant over deterministic tools;
- delightful UI and motion later, but only after the analytical architecture is stable.

## M1 Status

M1 is called `Verified Ball-Side Block-Shift Evidence Spine`.

M1 produced a verified first detector:

> From real IDSSE tracking data, produce auditable moments where the ball enters a wide area, the defending block shifts toward it, and the attack subsequently switches, retains without switching, or loses possession.

Controller-reported final verification:

- Gate A: 37 pass / 0 fail / 0 not_ready
- Gate B: 273 pass / 0 fail / 0 not_ready
- Gate C: 304 pass / 0 fail / 0 not_ready
- TypeScript replay proof: 82 pass / 0 fail

Important caveat: M1 was accepted `controller-only`; independent review was waived by the owner after a prior reviewer stalled. Final owner acceptance remains pending. Still, for purposes of this review, assume M1 has genuinely passed its local proof gates.

## Why We Are Revisiting Architecture Now

M1 proves a closed detector implementation. That is valuable, but it does not yet let an analyst or Hermes author materially new tactical detector plans at runtime.

The emerging product vision is:

> Hermes authors and refines tactical definitions; the deterministic engine measures the game; the evidence workbench lets the human decide whether the definition captured what they meant.

We want runtime detector authoring, but only from approved measurable primitives and relations. Hermes must not invent geometry algorithms, write code, execute SQL, mutate primitives, or silently approximate unsupported concepts.

## Prior Proposed Architecture

The first proposed M1.1 bundled all of this:

1. typed tactical-query representation;
2. generic temporal-spatial executor;
3. dynamic relation model;
4. Hermes-driven feedback and versioning interface.

We now believe that is too much to debug in one milestone.

## Proposed Split

### M1.1 - Composable Tactical Query Runtime

Product outcome:

> A developer can add a validated tactical detector plan, bind it against an approved primitive/relation catalog, execute it over the real IDSSE corpus through a generic deterministic runtime, inspect every predicate trace, and replay the resulting moments without adding query-specific backend code.

M1.1 is an architectural runtime proof. It explicitly excludes Hermes and natural-language query compilation.

Architecture:

```text
IDSSE tracking/events
        ↓
Canonical match store
        ↓
Primitive and relation catalog
        ↓
DraftQueryPlan
        ↓
Deterministic compiler / binder
        ↓
BoundQueryPlan
        ↓
Generic deterministic executor
        ↓
QueryExecution + predicate traces
        ↓
Evidence bundles + replay inspector
```

The compiler/binder is mandatory. Hermes or a human may author a draft plan later, but only a deterministically bound plan can execute.

Binder responsibilities:

- verify referenced primitives/relations exist;
- verify output types;
- validate operators for each type;
- validate units and values;
- resolve temporal references;
- require explicit match scope and team perspective;
- confirm requested evidence fields exist;
- enforce complexity limits;
- reject unsupported or ambiguous references visibly.

M1.1 uses only three analytical types:

- `FrameSignal<T>`: value at each analysis frame;
- `EpisodeSet`: intervals;
- `RelationEpisodeSet`: relationships that exist over intervals.

Required dynamic relation:

`geometric_progressive_corridor`

This is a transparent geometric relation, not a claim about optimality. It must not be called best pass, correct pass, expected completion, obvious opportunity, or missed opportunity.

At minimum it records:

- source entity or ball-carrier location;
- target attacking player;
- opened frame;
- closed frame;
- duration;
- distance;
- forward progression;
- minimum corridor clearance;
- destination side/lane;
- defensive lines crossed if available;
- evidence fields sufficient to redraw the corridor.

M1.1 internal gates:

1. **M1 Oracle Parity**
   Translate Ball-Side Block Shift into the new query IR and prove parity with the legacy M1 detector on result IDs, classifications, baseline frames, anchor frames, outcome frames, evidence values, ordering, and replay source frames. Legacy M1 remains a read-only oracle.

2. **Minimal Type System and Binder**
   Pydantic models, generated JSON Schema/TypeScript types, primitive/relation catalog, invalid-plan failures, deterministic plan hashes.

3. **Dynamic Relation Proof**
   `geometric_progressive_corridor` intervals are derived from real canonical coordinates and reconstructable from evidence.

4. **No-Code Composition Proof**
   Add one experimental plan as data only:

   ```text
   ball enters wide area
   -> defending block shifts toward ball side
   -> opposite-side geometric progressive corridor appears
   -> corridor persists
   -> classify whether ball enters destination region
   ```

   It must execute without adding a new Python detector or query-ID branch.

5. **Predicate Trace and Non-Match Inspection**
   Every result has full predicate traces; a supplied non-match timestamp/window can be evaluated against the same bound plan; failed predicates come from the engine, not Hermes.

M1.1 non-goals:

- no Hermes;
- no natural-language query compilation;
- no analyst feedback;
- no polished workbench;
- no arbitrary DSL syntax/custom parser;
- no Python/SQL/generated code/custom expressions;
- no runtime primitive invention/mutation;
- no optimality, intent, best-pass, expected-pass, or missed-opportunity claims.

### M1.2 - Grounded Tactical Query Workshop

Product outcome:

> A soccer expert can describe a positional process, inspect Hermes's interpretation, execute the bound query plan, review real moments and non-matches, label good and bad results, approve an explicit revision, and save a new immutable experimental recipe version.

M1.2 begins only after M1.1 is accepted. Hermes becomes a client of M1.1, not a separate analytics engine.

Hermes may use bounded tools:

```text
list_capabilities
search_recipes
describe_primitive
describe_relation
draft_query_plan
validate_query_plan
execute_query_plan
inspect_result_trace
inspect_non_match
retrieve_tracking_window
record_feedback
compare_query_versions
save_experimental_recipe
```

Hermes may not use:

```text
arbitrary Python execution
unrestricted SQL
filesystem editing
primitive implementation access
result-row mutation
threshold auto-tuning
complete raw-match coordinate dumps
```

Runtime decision process:

1. Search approved recipes.
2. Search user-saved recipes.
3. Compose an experimental plan only if all needed primitives/relations exist.
4. Report a capability gap if a required primitive/relation is unavailable.

Feedback labels:

```text
MATCHES_INTENT
NEAR_MATCH
FALSE_POSITIVE
KNOWN_MISS
UNUSABLE_DATA
```

Revision requirements:

- every material revision requires confirmation;
- every revision creates immutable query version;
- show semantic plan diff;
- show raw JSON diff in developer drawer;
- show prior/revised result count;
- show added/removed/retained results;
- show effect on previous positive labels, false positives, and known misses.

Recipe states:

```text
APPROVED
USER_SAVED
EXPERIMENTAL
DEPRECATED
```

M1.2 internal gates:

1. tool boundary and capability context;
2. draft, bind, confirm, execute;
3. feedback and non-match inspection;
4. revision and versioning;
5. workshop thin slice.

M1.2 non-goals:

- no new primitive implementation;
- no runtime operators;
- no bypassing M1.1 binder/executor;
- no arbitrary code/SQL/filesystem/primitive mutation/result mutation;
- no raw coordinate dumps into model context;
- no model training from feedback;
- no automatic promotion of experimental plans;
- no final UI polish.

## Downstream Roadmap After Split

Current proposed roadmap:

```text
M1      Completed evidence spine and trusted first detector

M1.1    Composable query runtime
        IR · binder · generic executor · relations · traces · M1 parity

M1.2    Grounded tactical query workshop
        Hermes · feedback · versioning · semantic diffs · thin loop

M2      Second approved tactical family and capability catalog
        implemented on top of M1.1 runtime, not as a bespoke detector

M3      Analyst workbench v1
        catalog · filters · replay · comparison · recipe studio

M4      Agent reliability and tactical lexicon hardening
        post-workshop hardening, ship/cut gate

M5      Demo experience, motion, and visual QA

M6      Meeting-ready independent demo release
```

Important downstream shifts:

- M2 is no longer “write a second bespoke detector, then maybe abstract.” It should build the second approved tactical family on top of M1.1.
- M3 should assume query executions, traces, recipe states, and evidence bundles already exist.
- M4 is no longer the first assistant milestone. M1.2 introduces the basic Hermes workshop; M4 hardens reliability, lexicon, and ship/cut readiness.
- M5 should not change analytics. Once visual polish begins, query semantics should be frozen except for verified defects.

## Core Claims To Review

Please review these claims critically:

1. Splitting M1.1/M1.2 is safer than one oversized M1.1.
2. The DraftQueryPlan -> binder -> BoundQueryPlan separation is necessary.
3. The three-type model, `FrameSignal<T>`, `EpisodeSet`, `RelationEpisodeSet`, is enough for now.
4. `geometric_progressive_corridor` is the right first dynamic relation.
5. M1 parity should be the first and hardest gate.
6. The no-code composition proof is strong enough to prove runtime detector authoring.
7. M1.2 should wait until M1.1 passes.
8. M2 should be rebuilt as the second approved family on top of the runtime.
9. The thin workshop in M1.2 is enough before the full analyst workbench.
10. The roadmap still supports a beautiful demo soon enough, rather than over-investing in architecture.

## Specific Review Questions

Please answer in this format:

```text
Decision:
APPROVE / APPROVE_WITH_REQUIRED_CHANGES / REJECT

Blocking findings:
1. ...

Required changes before implementation:
1. ...

Non-blocking concerns:
1. ...

Downstream roadmap changes:
1. ...

Missing acceptance criteria:
1. ...

Reward-hacking risks:
1. ...

What to build first in M1.1:
1. ...

What not to build yet:
1. ...
```

Please be direct. We especially want to know if this is still too much architecture for a demo, whether any layer is premature, whether the binder/type system is under-specified, and whether the dynamic relation proof should be changed before implementation starts.
