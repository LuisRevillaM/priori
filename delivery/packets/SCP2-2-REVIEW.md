# SCP2-2 Review — Round 1: REVISE (the honest kind)

Reviewed 2026-07-05 at 8227fb7. Process: exemplary — the environment
deviation was flagged with a ratification request before proceeding,
the blind set was fenced (hash read only), and a 4/15 dev result was
reported plainly with every failure attributed and a follow-up
requested. This is what the deviation law looks like when followed.
The boundary work (no fifth outcome, gate on every expression,
pack-projected prompt, typed multi-turn state) is in and tested; the
model side is not yet producing synthesizable expressions. Verdict:
REVISE, quality round.

## Diagnosis (from the executor's own evidence, confirmed by reading)

1. The dominant failure is NOT model weakness: "Target contract
   contains the reporting concept name; refusing hinted target" — the
   certification envelope's anti-hint gate fires because the RENDERED
   contract echoes the concept name. SCP2-1's accepted fixtures prove
   the name-free path works; the renderer must guarantee it
   mechanically. A model should not have to learn what the renderer
   can enforce.
2. "No registered operator composition satisfied the target contract"
   — over-constrained contracts; the model needs to see what
   satisfiable asks look like.
3. Output-shape errors (HermesNLModelOutputError) — prompt contract
   tightening plus the stronger tier.

## Rulings

**R-AQ.** The expression-to-target renderer emits NAME-FREE contract
bodies mechanically: the concept identity lives ONLY in coverage_row
and the rendered meaning label (the path the envelope permits and
SCP2-1's fixtures used). No prompt instruction may be the sole
defense against the anti-hint gate — the renderer guarantees it, with
a test (expression whose free-text echoes its concept name still
renders a name-free contract).

**R-AS.** Few-shot examples in the prompt projection are GENERATED
from the committed certified meaning-expression fixtures
(scp2-1-roundtrip, r2-4-flagship) — provably synthesizable examples,
regenerated with the projection, never hand-written. Guidance toward
minimal contracts (request only the evidence the question needs)
rides in the same projection.

**R-AS2.** Model tier: use the strongest available in the configured
provider (claude-opus-4-8 or above if configured); record the tier
and per-case latency in the report. Tier is a knob, not a design
constraint — we build for models improving into the design.

**R-AT.** The temp-home invocation is RATIFIED for round 1 — the real
invocation path was used and the canonical home was untouched. The
director has now repointed the canonical home
(~/.hermes-priori/config.yaml: command, output root, PYTHONPATH → the
live checkout; backup kept). Round 2 uses the canonical home and says
so.

## Round-2 acceptance bar

Dev set re-run through the committed harness: every expression and
clarification case either PASSES or fails with an attributed cause
that names a genuine missing capability — zero anti-hint refusals,
zero output-shape errors. The blind set stays sealed until the
director's run. Full-suite table on the committed tree.
