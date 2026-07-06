# PERF-1 Addendum: the cache key schema (director-authored)

This addendum is keystone design per the director-loop's §0: a cache
key is where a subtle omission produces fast, stale, WRONG answers
that the equivalence harness cannot catch (it tests today's plans on
today's tree; a wrong key fails silently later). The schema below is
LAW for PERF-1's node cache. The key-derivation code receives the
director's line-by-line review at acceptance, independent of the
harness verdict.

## The key

A node's cache key is `stable_hash` of a preimage with EXACTLY these
components — none optional:

1. **cache_schema_version** — version of this key schema itself;
   bumping it invalidates the world, which is the point.
2. **code_epoch** — hash over the source of the code that computes
   this node family AND the shared execution machinery it rides on
   (the family module + the executor's node-evaluation core). Any
   code change that could alter an output changes the epoch. Coarse
   is acceptable; clever is not: when in doubt, hash more source.
3. **node_semantic_identity** — the node family/kind plus
   CANONICALIZED parameters: sorted keys, typed payloads, and ALL
   defaults expanded — an omitted parameter and its explicit default
   must produce the same key only because canonicalization makes them
   the same preimage, never by accident.
4. **upstream_lineage (the Merkle clause)** — the ordered list of the
   CACHE KEYS of every upstream input node. A node's output depends
   on its inputs' outputs; therefore its key must transitively
   incorporate everything that determines them. Two plans that
   compose different upstreams into an identically-parameterized node
   MUST produce different keys. No node may be keyed on its own
   name and parameters alone.
5. **data_scope** — the (match_id, period) the evaluation runs over
   PLUS the data manifest entries (path, size, sha256) for the
   canonical files feeding that scope. Global-manifest-hash is an
   acceptable conservative fallback (any data change invalidates
   everything); silent narrowing below per-file granularity is not.
6. **perspective bindings** — team-role/perspective assignments, if
   not already canonicalized into parameters.

## The laws

- **Conservatism is the tie-breaker.** Any input not PROVABLY
  irrelevant to the output goes in the key. The cost of a spurious
  miss is seconds; the cost of a spurious hit is a wrong answer
  wearing a certified hash.
- **Entries are self-describing (R-AZ for caches).** Every cache
  entry stores its full key PREIMAGE (not just the hash) plus the
  producing code_epoch and a content hash of the stored output. On
  read: preimage re-hashes to the key AND output matches its content
  hash, or the entry is treated as ABSENT and recomputed — corruption
  is detected, never served, and logged.
- **One derivation function.** The key derivation lives in exactly
  one function; nothing composes keys ad hoc. Property tests mutate
  each preimage component independently and assert the key changes
  (mutation standard applied to every numbered component above).
- **The harness still rules.** Cache hits must be byte-identical to
  recomputation on the declared plan set; this schema exists for the
  cases the harness cannot see.
