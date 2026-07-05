# Work Packet SCP2-1: the meaning expression and its synthesizer

**Era**: SCP-2 bridge (ADR 0015 governs; read it first)
**Branch**: `packet/scp2-1` off the frontier
**Executor ground rules**: unchanged (stage-committed report at
`delivery/packets/SCP2-1-REPORT.md`; full-suite table on the committed
tree; commit locally, never push; clone route with prominent
provenance if blocked).

**Fences**: `generated/coverage-map.json`/`.csv` (the bridge NEVER
touches the ledger — principle 24); `semantic-registry/atlas/`; sealed
packet evidence; `artifacts/autonomous/` except the search tool's
canonical report path; no freezes, no re-pins.

## Headline risk

The meaning expression is the contract both halves of the bridge meet
at (principle 23). If its vocabulary drifts from the knowledge pack —
expressing things the pack doesn't declare, or failing to express
things it does — every later packet inherits the gap. The risk is a
schema that mirrors the pack loosely instead of being DERIVED from it
verifiably.

## Scope

### 1. Meaning-expression schema v0
`src/tqe/semantic_compiler/meaning_expression.py` (or the package's
natural home): a typed, versioned, hash-stable document. Contents, at
minimum: concept references (pack primitives/known compositions),
operator applications with their parameters (window, join,
aggregate, rate — mirroring bind-time law), population scoping,
declared group-by keys, team-perspective declarations. A VOCABULARY
GATE: every referenced primitive, operator, parameter, and field is
validated against the generated knowledge pack at load — an
out-of-pack reference produces the typed gap
understood_but_not_expressible with the smallest missing capability
cited by gap code (the pack carries 14 gap codes), never a generic
error. Round-trips stably (parse → dump → parse, hash-identical).

### 2. The synthesizer: expression → search target
`src/tqe/semantic_compiler/target_synthesis.py`: mechanically derive
a search-target document (the format in config/compiler-reachability/
*-targets.v0.json) from a meaning expression, including the
semantic_correspondence declaration DERIVED from the expression
(coverage_row from the expression's declared concept identity;
meaning text rendered from the expression's clauses — the declaration
states the meaning, per principle 19; it does not assert a verdict).
The synthesized target must pass the R1-C hardened guard's shape
checks and bind through the real binder. NO ledger update path is
reachable from this code (principle 24): the synthesizer emits
targets for query execution, and any coverage-map write from bridge
code raises.

### 3. Acceptance: round-trip against the earned rails
Take THREE held-out meaning expressions, hand-authored by the
executor as fixtures and named in the report:
(a) one reproducing an existing ledger concept (support_depth or
    fragile_possession_state) — its synthesized target's certified
    plan must reproduce the known-good answer (document_hash match or
    result-set identity with the committed evidence);
(b) one NOVEL composition within the current grammar (e.g. a windowed
    join + count aggregate the ledger does not carry) — synthesized,
    searched, certified, executed; results reported with intervals;
(c) one deliberately out-of-vocabulary expression — must produce the
    typed gap with the correct gap code, and the report shows the
    exact refusal payload.
Commit all three under `delivery/packets/scp2-1-roundtrip/` with a
generator that reproduces them on the committed tree (R-Y standing
law). Long executions: note in the report which runs exceed ~5
minutes so the director schedules them detached.

### 4. Tests (mutation standard)
Vocabulary gate rejects out-of-pack references (mutate the pack copy
in a scratch fixture → named test fails); schema round-trip hash
stability; synthesized targets pass the hardened guard's declaration
shape checks; the correspondence declaration's coverage_row always
equals the expression's concept identity; ledger-write
unreachability (attempting update_coverage_rows from bridge code
raises — test it); binder acceptance of a synthesized target.

## Explicitly OUT of scope
The model/NL side (SCP2-2); any presentation surface; new operators;
any ledger flips or new coverage rows.

## Deliverables
Schema + synthesizer + vocabulary gate; three round-trip fixtures
with generator and committed evidence; tests; stage-committed report
with full-suite table. Nothing pushed.
