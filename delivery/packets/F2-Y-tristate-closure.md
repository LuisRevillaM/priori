# Work Packet F2-Y — Tri-State Closure, Witness Chain, Binder Hardening

Issued: 2026-07-04 by the project director. The final packet of phase F2
(ADR 0012 §5-6). UNLIKE the extractions, this packet CHANGES BEHAVIOR
deliberately — it closes the last fail-open truth paths from the foundation
audit (T5-T8), replaces the name-scan witness heuristic with a declared
chain (V8), and hardens the binder/cache (V9). Full adversarial review;
every behavior delta must be quantified on the corpus.

Branch `packet/f2-y` off the frontier (tip `ce1fc9f` or later). Stage
commits, one per numbered item. Standing bars: full-suite table on the
committed tree; the eight pinned gates with any drift attributed;
`semantic-registry/`, `generated/`, `frozen-expectations/`, `delivery/n1d/`,
`artifacts/` fenced (director regenerates/re-freezes at acceptance). Catalog
edits ARE allowed where an item requires a declaration — enumerate every
one in the report.

## Items (audit refs T5-T8, V8, V9; line numbers have moved since the
audit — locate current homes and record them in the report)

1. **T5 — operator fail-open fallbacks.** The live `exists` and
   `count_at_least` paths still degrade to `bool(source)`/`len(source)` on
   sources without anchor-evaluation semantics: an episode set that is
   empty BECAUSE COVERAGE WAS MISSING evaluates FALSE. Move the
   "anchor-evaluations-only" rule into the binder (operator signatures /
   entity-scope validation) so such plans are REJECTED at bind time, and
   delete the fallbacks. Quantify: which checked-in plans/recipes (if any)
   bind exists/count_at_least against non-anchor sources today?
2. **T6 — coverage by field-name convention.** Coverage detection sniffs
   `evaluation_status`/`relation_count` field names; newer kernels emit
   different names, so `exists` over their anchor evaluations returns PASS
   for every record including FAIL/UNKNOWN (latent, one composition away).
   Introduce the typed coverage declaration on CatalogOutput (the F2-0
   envelope's CoverageChannel gets its typed status domain here — replace
   the field-name strings), declare it for every anchor-evaluation output,
   and route the operator coverage logic through the declaration. This is
   the item most likely to require catalog edits — enumerate them all.
3. **T7 — episode-trace UNKNOWN channel.** The episode-trace path emits
   FAIL for anchors no window covered, with no UNKNOWN channel. Add it:
   absence-of-coverage produces UNKNOWN traces, observed non-satisfaction
   produces FAIL. Quantify the corpus delta (which existing traces change
   status).
4. **V8 — witness chain.** Replace the global name-scan +
   frame-id-fallback witness selection with an explicit chain: classification
   nodes declare their witness relation/anchor; evidence projection follows
   the declaration; `record_matches_anchor` requires anchor_id-exact
   matching (delete the frame-id fallback). Delete
   `destination_entry_relation_id_for_source` and the eq/neq hard-coded
   frame-id fallbacks — the boundary-freeze allowlist shrinks to ZERO
   capability leaks (update the test to assert emptiness). The fabricated-
   trace helper stays (F2-X ruling R-A) — do not touch it.
5. **V9 — binder/cache hardening.** (a) ParameterRef-supplied durations
   respect max_temporal_horizon_seconds (close the indirection bypass);
   (b) complexity limits apply to anchor-evaluation outputs, not only
   outputs named "episodes"; (c) the node-output cache key includes the
   canonical data manifest hash (stale-cache-after-data-regeneration
   becomes impossible). Also retire the `_predicate_status` legacy
   side-channel write from the live dispatcher (F2-X reviewer note) if the
   quarantined profile alone consumes it — prove consumption first.

## Expected ripples (report, don't fix)

Items 1-4 can change bound-plan hashes (binder validation, catalog
declarations) and result/trace content (UNKNOWN surfacing). Enumerate every
drifting gate with drift class; quantify every content delta (counts
before/after per gate/plan). The hero contract test may move again — if it
does, report the mechanism precisely (it has a documented genealogy; the
director extends it at acceptance).

## Required tests

House standard, adversarial: empty-because-uncovered vs genuinely-empty
episode sets under exists/count_at_least (bind-time rejection); coverage
declaration honored for at least three kernels with different old field
names; episode-trace UNKNOWN vs FAIL; witness chain exactness (same-frame
anchors no longer cross-bind); ParameterRef horizon rejection; cache-key
data-hash sensitivity.

## Deliverables

Branch `packet/f2-y`; one commit per item; catalog-edit enumeration;
corpus deltas quantified; full-suite table; pinned-gate proof with drift
attribution; `delivery/packets/F2-Y-REPORT.md`.
