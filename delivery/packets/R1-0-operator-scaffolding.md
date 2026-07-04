# Work Packet R1-0 — Operator Scaffolding

Issued: 2026-07-04 by the project director. First packet of the R1
operator era. Governing design: docs/adr/0013-r1-operator-era.md (read
fully). Like F2-0: pure scaffolding, ZERO behavior change, zero hash drift
for existing plans.

## Ground rules (standing; all F2-era laws apply)

Branch `packet/r1-0` off the frontier (tip `60d913f` or later). Report
stage-committed from the FIRST commit (law L1). Stage commits throughout.
Fences: `semantic-registry/`, `generated/`, `frozen-expectations/`,
`delivery/n1d/`, `artifacts/` untouched; catalog/IR edits allowed ONLY as
the additive operator node kind requires — enumerate every one. Full-suite
table on the committed tree; the eight pinned gates as drift proof (all
must PASS untouched — this packet adds a node kind no existing plan uses).

## Scope

1. **IR:** additive `operator` node kind — versioned, typed inputs by
   channel reference (source node + output name), declared parameters,
   declared output channels with temporal types. Existing document/plan
   hashing untouched for plans without operator nodes (prove it: hash a
   frozen plan before/after).
2. **Operator signature model:** a typed declaration (name, version,
   consumed channel types, emitted channel types, parameter schema,
   coverage-propagation rule id, witness rule id) — the operator-side
   analogue of a catalog entry. Registry in
   `src/tqe/runtime/operators/__init__.py` following the capabilities
   pattern exactly: explicit dict, completeness test both directions,
   EMPTY at this packet's end (zero operators — the test asserts the
   registry matches the declared-signature set, both empty).
3. **Binder:** operator-node validation — unknown operator name, channel
   type mismatch against the signature, undeclared parameter, missing
   input reference = typed bind-time issues, house style. Fail-closed: any
   operator node in a document REJECTS at bind time in this packet (no
   implementations exist) with a distinct issue code
   (`operator_not_implemented`) — tested.
4. **Executor:** dispatch shell only — routes bound operator nodes to the
   registry; with an empty registry this path is provably unreachable
   (binder rejects first); assert that in a test.
5. **Boundary ratchets extended:** zero operator names in shared
   executor/binder code (same mechanism as capability leaks); the
   conformance shadow checker learns the operator envelope shape.
6. **Census (spec-as-first-class):** for each of the five R1 operators,
   survey which existing envelope channels across the 44 capabilities they
   can legally consume TODAY (by temporal type + coverage declaration) —
   a table in the report. This is R1-1..R1-5's input map and the first
   honest picture of the composition space.

## Deliverables

Branch `packet/r1-0`; the scaffolding; hash-invariance proof for a frozen
plan; the composition-space census; full-suite table; pinned-gate proof;
`delivery/packets/R1-0-REPORT.md` (stage-committed from commit one).
