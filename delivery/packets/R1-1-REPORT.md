# R1-1 Report - project_onto_axis Operator

Branch: `packet/r1-1`
Frontier base: `8431afb`
Packet: `delivery/packets/R1-1-project-onto-axis.md`
ADR: `docs/adr/0013-r1-operator-era.md`
Push: no push, per direct-channel protocol.

## Scope

Implement the first real R1 operator, `project_onto_axis@0.1.0`, under the
R1-0 operator scaffolding. Acceptance requires at least one previously-gap
semantic program to execute end-to-end and a compiler-reachable delta measured
by the coverage map tooling.

Required fences: additive/operator-scoped edits only; existing plan hashes must
not drift; generated/frozen artifacts are not touched unless explicitly
required by the packet.

## Implementation Ledger

| Step | Status | Evidence |
| --- | --- | --- |
| L1 report first commit | PASS | Commit `7313025` created this report before implementation. |
| Operator declaration | PASS | `project_onto_axis@0.1.0` registered as the sole R1 operator signature/implementation. |
| Operator implementation | PASS | `src/tqe/runtime/operators/project_onto_axis.py` emits witnessed `axis_projection_records`, `axis_projection_status`, `signed_projection_m`, and `angle_between_degrees`. |
| Acceptance composition | IN_PROGRESS | Focused executor-path probe passes over J03WOY; compiler-search target wiring still pending. |
| Reachability delta | PENDING | Not started. |
| Full suite and pinned gates | PENDING | Not started. |

## Verification

Focused unit/executor slice:

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_r1_0_operator_scaffolding tests.test_r1_1_project_onto_axis` | PASS | 11 tests. Covers explicit registry completeness, shared-code name boundary, mirror symmetry, axis enum completeness, UNKNOWN propagation, 0/90/180 angle boundaries, and real bind/execute on J03WOY. |
