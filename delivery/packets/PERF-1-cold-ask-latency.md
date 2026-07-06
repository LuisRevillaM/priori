# Work Packet PERF-1: the cold ask gets fast

**Branch**: `packet/perf-1` off the frontier (dispatches after
PRUNE-1 merges — one writer)
**Ground rules**: unchanged (stage-committed report; full-suite table
on the committed tree; commit locally, never push; R-AZ evidence law —
all timing evidence script-produced and self-stamped; deviation law;
DELIVERED-with-evidence).

**Fences**: unchanged. Plus the honesty fence specific to
performance work: NO semantic change may ride in as an optimization.
Every optimized path must produce BYTE-IDENTICAL results to the
unoptimized path on the same plan (the equivalence harness below is
the packet's teeth). tri-state semantics, bounds arithmetic, and
evidence contents are inviolable.

## Why (owner priority)

The Film Room's cold NL ask measured 431-477s, attributed: Hermes
~72s, synthesis ~14ms, EXECUTION ~359s. The sealed exam and any live
demo ask are gated on this number. Execution dominates; the model is
secondary.

## Headline risk

A fast wrong answer. Parallelism and caching are the two classic ways
to silently corrupt result identity (ordering, shared state, stale
keys). The equivalence harness is therefore not a test among tests —
it IS the acceptance: for a declared set of plans (the two flagships
+ the three scp2-1 round-trip fixtures + one novel live-synthesized
plan), optimized execution must produce byte-identical result
payloads (stable-hash equality) to sequential unoptimized execution
on the committed tree.

## Scope (in expected-value order)

1. **Parallel per-period execution.** The executor runs match-periods
   serially (14 period-runs per full-corpus plan). Parallelize across
   periods/matches with worker isolation (process pool or equivalent;
   period state is independent by construction — verify and state
   why). Concurrency declared and bounded; results merged
   deterministically (ordering law stated and tested).
2. **Persistent node-level cache.** Plans share primitive/relation
   nodes (possession episodes, pressure evaluations, carry episodes
   are recomputed by every plan touching them). Cache node outputs
   keyed by (node semantic identity, parameters, data manifest hash,
   code version) — the key derivation is the design core: it must be
   provably conservative (any input that could change the output is
   in the key; when in doubt, in the key). Persistent under the
   output root; invalidation by key, never by mutation. Cache hits
   must be byte-identical to recomputation (harness leg).
3. **Measure and attribute.** Timing table per stage
   (hermes/synthesis/bind/execute per-period/merge) for: the two
   flagship plans cold and warm, one novel live plan cold. R-AZ
   applies to timing evidence. Report the true numbers — improvements
   AND any regressions.
4. **(Only if 1-2 leave obvious headroom)** Hermes latency: the 204KB
   prompt projection is a known cost; trimming is allowed ONLY as a
   flagged proposal with before/after blind-quality evidence — not
   silently (SCP2-2 case law applies).

## Explicitly OUT of scope
Any change to operator semantics, bounds arithmetic, evidence
schemas, or the certification envelope; GPU/infra; model swaps.

## Tests
The equivalence harness (the acceptance); determinism under
parallelism (same plan twice → identical hashes); cache-key
conservatism (mutate a keyed input in a scratch copy → miss, named
test); cache poisoning resistance (corrupted cache entry → detected,
not served — decide detect-vs-recompute and state it).

## Deliverables
Parallel executor path + persistent node cache + equivalence harness
+ timing evidence; stage-committed report with the true latency
table; full-suite table. Nothing pushed.
