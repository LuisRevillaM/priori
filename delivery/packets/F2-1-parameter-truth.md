# Work Packet F2-1 — Single Source of Parameter Truth

Issued: 2026-07-02 by the project director. Implements ADR 0012 §2.
Retires the defect class behind two shipped bugs (the 6.0-vs-4.0 reception
default and the F1-B round-1 unwired filter): executor-side shadow defaults.

## Ground rules

- Branch `packet/f2-1` off `codex/afl08-passport-loop` (tip `418d03c` or
  later). Commit locally, do NOT push. Standing bar: full-suite table on the
  committed tree.
- Fences: `semantic-registry/`, `generated/`, `frozen-expectations/`,
  `delivery/n1d/`, `artifacts/` untouched (registry updates and re-freezes
  are the director's at acceptance).
- Behavior constraint: **zero behavior change.** Every default VALUE in
  effect today stays in effect — only its home changes (catalog declaration
  instead of hardcoded literal).

## Phase 1 — survey (commit the census with the code)

For every `node_parameter_number/integer/text(...)` call site in
`src/tqe/runtime/` (~180) and every capability-implementation read of
shared `state.params`:

1. Is the parameter DECLARED in the capability's catalog entry?
2. If declared: does the hardcoded default equal the catalog default?
   (Any disagreement is a live bug of the F1-B class — report it
   prominently; fix direction: catalog wins ONLY if that preserves current
   runtime behavior, i.e. the binder already materializes the catalog value;
   otherwise flag for director decision, do not choose silently.)
3. If undeclared: the parameter must be DECLARED in the catalog with
   payload type, unit, min/max where sensible, and TODAY'S hardcoded value
   as the default — preserving behavior exactly while making the contract
   honest.

Census goes in the report as a table: call site, parameter, declared?,
default agreement?, action taken.

`state.params` reads by capability implementations: CENSUS ONLY in this
packet (list them; F2-Y handles them). Exception: none may gain new reads.

## Phase 2 — cutover

1. Change the `node_parameter_*` helpers to read from the bound node's
   resolved parameters ONLY: no default arguments. A read of a parameter
   absent from resolved parameters raises a typed hard error naming the
   capability, node, and parameter (this is a programming-contract
   violation, not an UNKNOWN — the binder materializes every declared
   default, so absence means an undeclared read).
2. Delete every hardcoded default argument at every call site.
3. Add the mechanical guard: a test that walks the dispatch registry, binds
   a minimal document per capability, executes far enough to assert no
   implementation raises the undeclared-parameter error (or statically:
   every parameter name read by each implementation appears in its catalog
   entry — choose the enforceable variant and justify).

## Expected legitimate ripples (report, don't fix)

- Catalog declarations added in phase 1 change `bound_plan_hash` for every
  plan binding those capabilities → frozen-expectation gates and SCP-0
  parity will drift. Enumerate every affected gate with its drift class.
  Director re-freezes and updates registry bindings at acceptance.
- The conformance census (`make envelope-conformance-report`) may shift —
  regenerate to gitignored check-runs and report the delta.

## Required tests

Helper raises on undeclared read (typed error, names the read); per-site
behavior preservation spot checks for the highest-risk call sites (any
where phase-1 found disagreement); the mechanical guard from phase 2.3;
house style throughout.

## Deliverables

Branch `packet/f2-1`; census table; cutover; full-suite table on the
committed tree with every failure attributed; gate-drift enumeration;
`delivery/packets/F2-1-REPORT.md`.
