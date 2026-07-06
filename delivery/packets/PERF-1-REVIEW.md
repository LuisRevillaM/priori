# PERF-1 Review — Round 1: ACCEPT-WITH-FIXES

Reviewed 2026-07-06 at 800bb0b. Three legs: director's line-by-line
review of the key derivation (the keystone commitment — live path
faithful to the schema: Merkle lineage at every cache use,
self-describing persistent entries, detected-never-served, per-scope
manifest entries, runtime-wide code epoch); director's full suite
green; adversarial review with recomputation and forensic timeline
closure.

## The numbers (true, committed, reproduced to the millisecond)

Sequential → optimized-cold → optimized-warm: fragile retention
435.2s → 117.1s → 43.4s; counterattack 288.6s → 60.7s → 16.8s; known
fragile state 446.4s → 125.0s → 52.3s; novel live document 294.0s →
67.4s → 18.7s. Equivalence: all 9 executable plan-roles byte-identical
across all three variants (full canonical payloads, not summaries);
zero detected-never-served; result and trace ordering identical. The
excluded sixth plan set is the OOV refusal fixture — honest by
construction. Process pools were sandbox-blocked; the committed gains
ride the thread fallback and are attributed as such.

## Fix list (numbered; mechanical)

1. Delete the dead lineage-less wrappers (catalog_node_cache_key,
   shared_catalog_node_cache_key, synthetic_cache_state) and rewrite
   the one test that calls them — a scope-blind key function in the
   tree is a loaded footgun (director's finding).
2. Complete the mutation matrix to sub-components: runtime-parameter
   default VALUE, match_id/period within data_scope,
   resolved_parameters value, corrupted-PREIMAGE persistent entry.
3. encode_cache_output: LOUD rejection of tuples/ndarrays (director's
   ruling — fail-closed beats a documented caveat; silent tuple→list
   on warm hits is the class the harness cannot see).
4. Record the pool backend in the evidence variant summaries.
5. Report discloses: cache-entry files deleted from the run dir
   before commit (and why), the two abandoned run dirs, and the
   render.yaml production activation (TQE_NODE_CACHE_ROOT,
   TQE_EXECUTION_WORKERS=4) as a deliberate scope item the director
   ratifies at merge.
6. Fresh focused-test evidence naming the tests; full-suite table.

## Recorded without action

The independence statement's slight overclaim (global parquets are
read-only shared; persistent-cache thread sharing is same-bytes +
atomic rename + detect-never-served) — adjudicated harmless, now
documented here. The narrow PermissionError fallback is fail-loud,
acceptable. The MutableMapping/dict narrowing has no in-repo caller;
carried.

---

# PERF-1 Fix Round: ACCEPTED — the engine is fast and provably the same

Reviewed 2026-07-06 at 8233348. All six fixes verified by the
director: dead wrappers deleted (zero occurrences); the mutation
matrix extended to sub-components; unsupported cache types rejected
loudly per ruling; the pool backend recorded in evidence — and the
fix-round equivalence ran on REAL process pools ("backend":
"process"), strengthening the acceptance; disclosure paragraphs in;
director's full suite green on the committed tree.
