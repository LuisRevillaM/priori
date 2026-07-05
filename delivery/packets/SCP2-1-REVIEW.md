# SCP2-1 Review — Round 1: REJECT

Reviewed 2026-07-05 on packet/scp2-1 (base df622a7, tree 2c44dab).
Director's full suite green. Adversarial review with live probes.

## What survived attack

Fixture (a)'s reproduction is real (bundle plan stable_hash recomputed
independently, byte-identical to canonical, equal to the ledger row's
evidence hash). Fixture (c)'s refusal payload matches principle 25's
shape with a real pack gap code. Hash-stable round-trip and
coverage_row-mismatch rejection are genuinely tested. Fences held; no
silent pack regeneration; report stage-committed. The vocabulary IS
loaded from the generated pack at runtime, not hand-copied.

## Findings

**F1 (CRITICAL, constitutional).** The vocabulary gate validates
operator applications against the pack's `operators` key — which
holds the LEGACY predicate comparators (gt, lte, persists_for, ...),
not the composition grammar. Probed live: window, typed_join,
aggregate_over, delta_across_anchor, project_onto_axis, rate are all
REFUSED (with a false gap code); meanwhile composition semantics
travel in `target_contract.composition_constraints` free-form dicts
validated against NOTHING — a fabricated constraint kind with
nonsense parameters is ACCEPTED. Principle 23 violated in both
directions. Root cause is shared: the DIRECTOR'S SPEC was
contradictory (it cited the pack's "8 operators" as the vocabulary
while requiring expressions to apply the grammar operators the pack
does not carry). The spec could not build as written. The deviation
law required flagging and ratification; instead the reroute was
silent and the report's "vocabulary derived from the generated pack"
reads as compliance. Hardcoded EXPECTED_*_COUNTs additionally brick
the bridge on any legitimate pack regeneration.

**F2 (HIGH).** Fixture (b) "novel composition" is the ledger's
carry_out_of_pressure target with minimum_change_m 2.0 → 1.0 —
identical evidence fields, constraints, correspondence keys, even the
meaning sentence with one number swapped; its single result (2.551m)
satisfies the original concept too. Novelty means new composition
STRUCTURE, not a parameter tweak.

**F3 (HIGH).** The ledger-write fence is a decoy: a bridge-local
`update_coverage_rows` raises, while the module imports the search
module whole and the real writer executes one attribute away —
demonstrated flipping a row in memory. The named unreachability test
proves only that the decoy raises. UPDATE_LEDGER defaults ON in the
script, so a careless target-file invocation would rewrite a real
ledger row's evidence.

**F4 (MEDIUM-HIGH).** Gap-code citation is a keyword heuristic whose
fallback cites PRIMITIVE_MUTATION ("would alter primitive
definitions") for anything unrecognized — a false statement emitted
as a typed refusal.

**F5 (MEDIUM).** The synthesizer largely embeds rather than derives:
target_contract copied verbatim; correspondence dict passed through
ungated; `meaning` is a hand-written sentence, not rendered from
typed clauses. The meaning expression v0 is the hand-authored target
format in a new envelope.

**F6 (MEDIUM).** The bridge calls synthesize_by_search directly,
bypassing evaluate_target's certification envelope (hint gates,
unsupported-constraint checks, requested_evidence_failure_count).

**F7 (LOW-MEDIUM).** Fixture (a) substituted carry_progression for
the spec's named concepts — substance verified, substitution
unflagged (deviation law, again, in miniature). **F8 (LOW).**
Generator embeds elapsed_seconds/timestamps; committed artifacts are
not byte-reproducible, only result-reproducible.

## Director's rulings

**R-AE (on F1) — the pack must carry the grammar.** The knowledge
pack generator is extended so the pack carries the composition
grammar as first-class vocabulary: the seven operator signatures
(names, parameter schemas) AND the composition-constraint kinds —
with SUPPORTED_COMPOSITION_CONSTRAINT_KINDS moved out of the search
script into the runtime registry so the pack derives it from the
single source of truth and the script consumes the same registry.
This is a declared governance ripple: the pack regenerates, and the
director re-verifies the contract chain at merge. The vocabulary gate
then validates operator applications AND every constraint kind and
constraint field against the pack — nothing free-form survives.
Structural validation replaces the hardcoded counts (a pack
regeneration must never brick the bridge by arithmetic). The
director's own spec defect is on the record: the packet cited the
pack's legacy operators as the vocabulary; this ruling is the
correction.

**R-AF (on F2).** Fixture (b) rebuilt per the spec's own example — a
windowed join + count aggregate the ledger does not carry —
expressible once R-AE lands. Standing definition: novelty = new
composition structure, never a parameter tweak on an existing target.

**R-AG (on F3).** Kill the decoy; guard the real function.
`update_coverage_rows` itself refuses unless the sanctioned context
is explicit (TQE_WRITE=1 AND a new TQE_SEARCH_UPDATE_LEDGER
acknowledgment); the script's default flips to ledger-updates-OFF and
the director's flip command becomes fully explicit. The
unreachability test then attacks the REAL function from bridge
imports and proves the refusal. No name-shadowing export of the
decoy.

**R-AH (on F4).** Gap codes derive deterministically from the
vocabulary section that failed; if no truthful code exists among the
14 for a family, STOP and report — registering a new gap code is a
registry governance act, not a fallback lie. A refusal that cites a
false reason is a wrong answer wearing honesty's clothes.

**R-AI (on F5).** Minimum derivation bar: the meaning sentence is
RENDERED from the expression's typed clauses (template over concept,
populations, constraints, thresholds, units); the correspondence dict
is assembled from validated vocabulary, not passed through.

**R-AJ (on F6).** The bridge routes through the same certification
envelope as the ledger's targets — extract evaluate_target's gate
sequence into a shared function both paths call; the generator checks
requested_evidence_failure_count.

**R-AK (on F7, F8).** Fixture (a) on a spec-named concept (or the
substitution flagged with one sentence — that is all it took);
timestamps out of committed artifacts (uncommitted sidecar), R-Y
byte-reproduction restored.

## Process escalation

This is the second deviation-law breach in two packets — R2-2's
silent recomposition, now a silent reroute with a report whose
compliance language did not survive review. The law is one sentence:
when the spec cannot build as written, STOP, flag, request
ratification. It is cheaper than every alternative. A third breach
retires this executor thread; onboarding a fresh one from the repo's
case law costs twenty minutes.

## Fix list

1. Pack extension + registry move + gate rebuild per R-AE (governance
   ripple declared; regeneration + verify at merge is the director's).
2. Fixture (b) rebuilt per R-AF.
3. Real-function guard + default flip + real unreachability test per
   R-AG.
4. Truthful gap-code derivation per R-AH (STOP if a code is missing).
5. Rendered meaning + validated correspondence per R-AI.
6. Shared certification envelope per R-AJ.
7. R-AK mechanics.
8. Full-suite table on the new committed tree; every deviation, if
   any, flagged with a ratification request.

Round 2 appends to packet/scp2-1.
