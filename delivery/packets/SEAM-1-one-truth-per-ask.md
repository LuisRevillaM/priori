# Work Packet SEAM-1: one truth per ask

**Source**: EXAM-1 findings F-D, F-A, F-C, F-F (delivery/packets/
EXAM-1-FINDINGS.md — read it first; every finding has a committed
exhibit and reproduction command).
**Branch**: `packet/seam-1` off the frontier
**Ground rules**: unchanged (stage-committed report; full-suite table;
commit locally, never push; R-AZ; DELIVERED-with-evidence; deviation
law; alternate-index verification statement if used).

## Headline risk

F-D is a correctness-of-meaning defect on the product's main path:
the same ask can return intervals over two different denominators
depending on cache state. The fix must NOT be "pick whichever number
looks better" — it is: ONE denominator convention, declared in the
plan, produced identically by every serving path, with the label
derived from the declaration.

## Scope

### 1. F-D — one denominator, both paths
Root-cause first, in the report: state precisely what population the
runtime interval extraction uses (chain records) vs what the
committed R2-4 certified table uses (regain seeds), and which one the
RATIFIED R2-4 question means ("per-regain rate" — the review record
says per-regain). Then: the rate plan's denominator is DECLARED
(it already is — denominator_status_field=stage_1_status); the
runtime extraction computes over that declared population — if
stage_1 seeds that never became chain records are today invisible to
the runtime rate rows, that is the defect to fix at the operator/
evidence level (seeds enter the partition as their honest tri-state,
not silently dropped). The certified-table fast path and the runtime
path must produce the SAME partition counts for the same document
hash — add an equivalence check to the harness family: for the
flagship, certified-table numbers == fresh runtime numbers, asserted
in a committed test. Labels derive from the declared denominator.

### 2. F-A — clauses cannot disagree with parameters
At expression validation (the gate), every numeric meaning_clause
whose field names an operator parameter's subject must MATCH the
parameter's value; mismatch is a typed refusal (the clause describes
a plan the contract would not execute), never a silent preference.
Alternative (acceptable if cleaner): numeric clauses are DERIVED from
parameters at load so disagreement is unrepresentable — choose one,
state why. Mutation test: the exam's own exhibit (clause 8.0 /
parameter 3.0) must refuse.

### 3. F-C — evidence-bearing responses or a declared contract
Decide with evidence: either ExecuteQueryPlanResponse rows carry
their evidence (measure the payload-size cost on the flagship;
result_limit already bounds it) or the response schema documents the
side-channel explicitly (where the evidence lives, how to fetch it)
and the empty dict is replaced by an honest omission. No third state
where a consumer silently sees {}.

### 4. F-F — the payload shape gets a home
One documentation page (docs/ or in-code schema doc) for the
execution payload chain (submit/validate/confirm/execute response,
where evidence and requested-evidence rows live); a stated definition
of moment_total_count vs rate population (205 moments vs 115 chains
at threshold 1.0 — define what moments counts, or fix it to mean the
chain population).

## Tests
The F-D cross-path equivalence test (certified == runtime partition
counts, flagship); the F-A refusal mutation test; full suite. The
exam's sweep script must run unmodified afterward and produce
denominator-consistent curves (the director re-runs it at
acceptance).

## Deliverables
Root-cause statement + fixes + tests + report with full-suite table.
Nothing pushed.
