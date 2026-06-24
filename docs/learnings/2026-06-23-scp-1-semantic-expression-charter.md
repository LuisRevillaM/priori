# 2026-06-23 - SCP-1 Semantic Expression Charter

## Fact

External review of the post-SCP-0 direction strengthened the goal: Priori's
semantic language must be broader than the currently executable library.
Otherwise `EXPRESSIBLE`, `COMPILABLE`, and `EXECUTABLE` collapse into the same
state, and the system can only appear to understand football ideas it already
knows how to run.

## Decision

SCP-1 will include typed semantic gaps as first-class compiler outputs. A
natural-language request may compile into a type-correct semantic program even
when one operationalization, runtime implementation, data modality, or
definition profile is missing. Such a gap must be typed, reviewable, and
non-executable.

SCP-1 will also adopt Football Query Normal Form:

```text
SCOPE -> ANCHOR -> BIND -> MEASURE -> MATCH -> OUTCOME -> JUDGE -> RETURN
```

Recipes remain examples, reviewed shortcuts, and regression fixtures. They do
not define the boundary of the language.

## Learning

A compiler that only emits executable current-runtime plans will bias the
library toward demos and recipes. A compiler that can emit precise typed gaps
turns failed queries into library-design evidence. That is the path from a
recipe runner to an executable football semantic language.

## Evidence

- `delivery/scp-1/SPEC.md`
- `delivery/scp-1/status.yaml`
- `delivery/scp-1/progress.md`

## Follow-up

After SCP-0E.1 external acceptance, begin SCP-1 in three tracks:

1. `SCP-1L` - minimal executable semantic language and lowering.
2. `SCP-1C` - natural-language compiler outcomes and typed gaps.
3. `SCP-1G` - Football Program Corpus and recipe-free generality harness.
