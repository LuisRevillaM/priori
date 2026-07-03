# ADR 0012 — F2: Executor Extraction Behind a Typed Capability Contract

Date: 2026-07-02. Status: ACCEPTED (project director). Supersedes nothing;
implements the F2 phase of the 2026-07-01 foundation audit remediation plan
(`docs/audits/FOUNDATION_AUDIT_2026-07-01.md`) and is the hard precondition
for the operator releases in the General Compiler v1 strategy
(`docs/audits/ATLAS_STRATEGIC_REVIEW_2026-07-01.md`).

## Problem

`src/tqe/runtime/executor.py` is 11,037 lines. Roughly two thirds is
per-capability measurement code pasted inline behind an untyped
`state.signals` dict whose semantics are naming conventions
(`X_status`, `X_status_records`, `anchor_evaluations`), not contracts.
Consequences, all observed and documented:

- Capability names leaked into shared trace/evidence code (name-conditioned
  branches, hard-coded field fallbacks, fabricated experimental traces).
- A second source of parameter truth: ~180 call sites of
  `node_parameter_*(node, name, default)` carry hard-coded execution-time
  defaults that can silently disagree with the catalog (this exact class
  produced two shipped bugs: reception window 6.0 vs 4.0, and the F1-B
  round-1 unwired-filter rejection).
- Tri-state fail-open paths in shared operator fallbacks (audit T5–T8):
  `exists`/`count_at_least` degrade to `bool()`/`len()` on episode sets;
  coverage detection sniffs field names; the episode-trace path has no
  UNKNOWN channel.
- Witness/evidence binding is a global name-scan with a frame-id fallback,
  not a declared chain (V8).
- Dead-but-registered duplicate predicate implementations and noop dispatch
  registrations (V10); the legacy M1 parity profile interleaved through the
  core loop.

Thirteen compositional operators (R1/R2) cannot land safely in this module.

## Decision

### 1. A typed capability contract

Every capability implementation becomes a callable with this shape:

```text
inputs:
  resolved parameters   (from the bound plan ONLY — see §2)
  resolved input ports  (typed runtime values by declared port name)
  execution context     (match, period, canonical roots — no free state)
output:
  CapabilityEnvelope
    channels: declared outputs by name and temporal type
              (episode sets, frame signals, anchor evaluations, scalars)
    coverage: a MANDATORY typed coverage/status channel per output that
              declares it (replaces field-name sniffing — closes T6)
    evidence: records keyed to declared evidence fields
    witness:  explicit witness references from classification-relevant
              records (basis for the declared witness chain — V8)
```

The envelope is **mechanically validated against the catalog entry at
execution time**: undeclared channels, missing declared channels, undeclared
evidence fields, or enum values outside declared domains are hard errors.
Conformance stops being discipline and becomes physics.

### 2. One source of parameter truth

The binder already materializes catalog defaults into
`resolved_parameters`. The executor reads parameters ONLY from there.
`node_parameter_*` default arguments are deleted; an implementation reading
an undeclared parameter is a hard error. This retires the V4/D9 defect class
permanently.

### 3. Sharding

Per-capability code moves to `src/tqe/runtime/capabilities/` (one module per
family; existing kernel modules — controlled_pass, relations, lane_*,
support_arrival, etc. — stay where they are and gain envelope adapters).
`executor.py` shrinks to: dispatch registry (catalog → implementation
binding), operator evaluation, rule/classification engine, trace/evidence
projection, artifact emission. Target: under ~2,500 lines.

### 4. Kill list (audit V10 + friends)

Duplicate registry predicate implementations; `primitive_noop`
registrations for never-cataloged names; fabricated experimental traces;
`destination_entry` name-conditioning in shared evidence projection (replaced
by the witness chain). The legacy M1 parity profile is quarantined into its
own module behind an explicit profile flag, out of the core loop.

### 5. Tri-state closure in shared paths (T5–T8)

The `exists`/`count_at_least` anchor-evaluation rule moves into binder
operator signatures; the `bool()`/`len()` fallbacks are deleted. The
episode-trace path gains an UNKNOWN channel. Coverage flows through the
envelope's typed channel.

### 6. Binder and cache hardening (V9)

`ParameterRef` durations respect the temporal-horizon ceiling; complexity
limits apply to all output kinds, not only outputs named `episodes`; the
node-output cache key includes the canonical data manifest hash.

## Migration strategy: strangler, hash-pinned

Pure code moves must produce **zero hash drift**: `bound_plan_hash` derives
from documents and catalog declarations, not code layout — every extraction
packet asserts byte-identical gate results as its acceptance bar. Envelope
conformance additions that require new catalog declarations are batched
separately and deliberately (they cascade into frozen-expectation
re-freezes, handled at director acceptance as established in F1).

Packet sequence (each one dispatch, each suite-green, standing full-suite
bar applies):

```text
F2-0  scaffolding: envelope types, conformance checker, dispatch registry,
      CI guard (no capability names in shared modules — grep-enforced);
      zero behavior change, zero hash drift
F2-1  parameter-truth cutover: delete shadow defaults, read resolved
      parameters only (behavior identical by construction; the binder
      already materializes defaults)
F2-2..n  family extractions, one packet each:
      pass family (controlled_pass, bypass, pass_bypass, high_bypass,
      one_touch) -> corridor/relations -> lines family -> off-ball family
      (runs, support, time_to_arrival, marking) -> team-shape family
      (compactness, team_press, lateral shift) -> inline stragglers
      (carry, velocity/acceleration, set_piece, space_region, join,
      outcome_window, multi_line)
F2-X  kill list + legacy M1 quarantine
F2-Y  tri-state closure (T5-T8) + binder/cache hardening (V9) — the only
      packets with intended behavior deltas; quantified like F1 packets
```

## Success criteria

- `executor.py` ≤ ~2,500 lines; zero capability-name matches in shared
  modules (CI-enforced).
- Envelope conformance green for all 44 bound capabilities.
- All gates green; zero hash drift across pure-move packets.
- R1 operator work can begin with operators as first-class envelope
  consumers rather than god-module residents.

## What this does not do

No new football semantics, no new primitives, no operator implementations,
no atlas changes. F2 is plumbing that makes those safe.
