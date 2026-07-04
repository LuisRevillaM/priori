# Work Packet R1-1 — Operator: project_onto_axis

Issued: 2026-07-04 by the project director. First operator of the R1 era.
Governing design: docs/adr/0013-r1-operator-era.md; scaffolding contract:
the R1-0 signature model, registry, and bind-time validation; input map:
R1-0's composition-space census (delivery/packets/R1-0-REPORT.md).

## Ground rules (standing; all laws apply)

Branch `packet/r1-1` off the frontier (latest). Report stage-committed from
commit one. Fences as always (catalog/IR edits only as the operator's
declarations require — enumerate). Full-suite table; eight pinned gates
(PASS expected — additive work); zero hash drift for existing plans.

## The operator

`project_onto_axis@0.1.0`: consume a vector-bearing channel (per the
census: displacement/velocity/point-pair evidence across capabilities) and
a declared AXIS, emit a signed-scalar channel (frame signal or per-record
scalar, matching the input's temporal type).

Declared axes (enum, versioned): `goalward` (attack-direction-normalized
x), `lateral` (y, mirror-consistent with the shared lane geometry),
`toward_point` (parameterized reference: ball, own goal, opponent goal,
declared coordinate), `along_lane_normal`. Also emit `angle_between` as a
declared second output where both vectors exist.

Semantics laws:
- Attack-direction normalization uses the SAME orientation source as the
  kernels (one convention, no local reinterpretation).
- Coverage: input records lacking the vector's evidence fields produce
  UNKNOWN outputs per the declaration — could-change-answer discipline;
  no silent drops.
- Witnesses: each output references its source record/frame per the R1-0
  witness rule.
- Determinism: declared units (metres/mps), declared signs, tie-free by
  construction.

## Acceptance composition (the packet's proof-of-power)

At least one previously-gap semantic program becomes executable end-to-end:
the atlas's support-geometry family is the target — compose
`observed_support_arrival` (or the census's best vector source) with
project_onto_axis to produce a real `support_depth`/`support_angle`-class
measurement over J03WOY, with results, traces, evidence, and replayable
moments. Then run the coverage-map reachability tooling and report the
compiler_reachable delta (before/after, with the map's own sweep — not
asserted).

## Required tests

House standard: mirror symmetry across attack directions; axis enum
completeness; UNKNOWN propagation on missing vector fields; angle
boundaries (0/90/180); executor-path test through real bind_document ->
execute for the acceptance composition; hash invariance for frozen plans.

## Deliverables

Branch `packet/r1-1`; the operator; the acceptance composition executing
with evidence; the compiler_reachable delta; catalog/IR edit enumeration;
full-suite table; pinned-gate proof; `delivery/packets/R1-1-REPORT.md`.
