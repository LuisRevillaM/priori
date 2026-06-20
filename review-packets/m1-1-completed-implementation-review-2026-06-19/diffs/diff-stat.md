# Diff Stat

Command:

```text
git diff --stat 5becefc..HEAD
```

Output:

```text
 Makefile                                           |   26 +-
 .../query-plans/ball_side_block_shift.ir.v1.json   |  501 +++++++
 ...osite_corridor_after_shift.experimental.v1.json |  645 +++++++++
 delivery/ledger.jsonl                              |    7 +
 delivery/m1.1/reviews/gate-a-controller-review.md  |   33 +
 delivery/m1.1/reviews/gate-b-controller-review.md  |   34 +
 delivery/m1.1/reviews/gate-c-controller-review.md  |   32 +
 delivery/m1.1/reviews/gate-d-controller-review.md  |   35 +
 delivery/m1.1/reviews/gate-e-controller-review.md  |   39 +
 delivery/m1.1/reviews/gate-f-controller-review.md  |   36 +
 delivery/m1.1/status.yaml                          |   30 +-
 docs/learnings/2026-06-19-m1-1-gate-a-ir-binder.md |   20 +
 .../2026-06-19-m1-1-gate-b-runtime-parity.md       |   19 +
 .../2026-06-19-m1-1-gate-c-predicate-traces.md     |   24 +
 .../2026-06-19-m1-1-gate-d-geometric-corridor.md   |   24 +
 .../2026-06-19-m1-1-gate-e-no-code-composition.md  |   25 +
 .../2026-06-19-m1-1-gate-f-developer-inspector.md  |   26 +
 generated/capability-catalog.json                  |    1 +
 generated/tactical-query-plan.schema.json          |    1 +
 generated/tactical-query-plan.types.ts             |  168 +++
 scripts/m1_1/build_gate_a_artifacts.py             |   17 +
 src/tqe/inspector/__init__.py                      |    1 +
 src/tqe/inspector/m1_1.py                          |  789 ++++++++++
 src/tqe/runtime/__init__.py                        |    1 +
 src/tqe/runtime/artifacts.py                       |  253 ++++
 src/tqe/runtime/binder.py                          |  622 ++++++++
 src/tqe/runtime/catalog.py                         |  555 +++++++
 src/tqe/runtime/executor.py                        | 1520 ++++++++++++++++++++
 src/tqe/runtime/ir.py                              |  491 +++++++
 src/tqe/runtime/relations.py                       |  603 ++++++++
 src/tqe/verification/m1_1.py                       |   68 +
 src/tqe/verification/m1_1_gate_a.py                |  383 +++++
 src/tqe/verification/m1_1_gate_b.py                |  448 ++++++
 src/tqe/verification/m1_1_gate_c.py                |  372 +++++
 src/tqe/verification/m1_1_gate_d.py                |  367 +++++
 src/tqe/verification/m1_1_gate_e.py                |  659 +++++++++
 src/tqe/verification/m1_1_gate_f.py                |  325 +++++
 tests/test_m1_1_binder.py                          |  138 ++
 tests/test_m1_1_runtime.py                         |  166 +++
 39 files changed, 9488 insertions(+), 16 deletions(-)
```
