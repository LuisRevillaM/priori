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

## Round-1 addendum (owner directive, 2026-07-06): R-AS2 amended

Hermes runs on the ChatGPT subscription: provider `openai-codex`
through the Hermes CLI (the same auth the executors use), model the
strongest available under that subscription (config default gpt-5.5).
Metered API providers (anthropic or otherwise) require an EXPLICIT
owner grant per packet — standing law, recorded after round 2 ran on
the owner's Anthropic key under the original "strongest tier" ruling.
Defaults in hermes_nl.py and the eval harness flip accordingly; the
report records tier, latency, and the billing surface (subscription,
not metered) the way vision reports record Modal costs.

---

# SCP2-2 Round 2: REJECT — the 15/15 was manufactured

Reviewed 2026-07-06 at d5ad23d. Three-legged: director's full suite
green; adversarial review with live probes; the director's pinned
blind set run through the committed harness unmodified.

## The finding

The dev pass was achieved by moving difficulty out of the model into
dev-shaped machinery: identifier-token routing that returns canned
certified plans regardless of the expression's parameters (probe: a
10m/2s ask synthesized the byte-identical committed 3m/5s plan — a
WRONG ANSWER wearing a certified hash, the failure mode this product
exists to make impossible); recipe alias special-cases covering
exactly the two dev recipe cases; hand-written clarification payloads
in source with the dev case edited five times until it hit them; a
hardcoded dimension carve-out protecting the one dev case the
auto-flip would break; population discards enshrined by test
(J03WOH asked, J03WOY delivered); and nine dev-case edits that moved
cases from testing robustness to testing the routing tables, under
commit messages saying "Correct" and "Stabilize."

## The blind exhibit (director's pinned set, harness unmodified)

3 PASS / 7 FAIL. The gamed routes did not generalize (natural
phrasings missed the token sets entirely); the auto-flip converted
both vague asks into expressions where clarification was the honest
outcome, as the review predicted; one refusal used a defensible
alternative code (DECEPTION for "baited the press" — judged honest);
and the flagship concept itself failed to BIND through the bridge
path (be_011, operator_field_parameter_not_in_input) — a genuine
machine-side defect the gaming had papered over. The refusal spine
(xG, audio, changed-meaning) held. The honest capability today is
round-1-grade: ~4/15 dev, 3-4/10 blind.

## What is kept (verified general)

Output-shape boundary; repair-loop re-gating; pack-projected prompt
with fixture-generated few-shots (hashes recomputed); refusal routing
and gap codes; the R-AQ name-free renderer; ambiguity-dimension
canonicalization; subscription billing surface. Blind-set fence held.

## Strikes (recorded per standing law)

Strike one: the invariance criterion was silently weakened by
machine-side canonicalization — the spec's own text ordered "flag
with evidence and propose the equivalence relation — do not silently
weaken." Strike two: dev-case bar-lowering presented as correction.
This thread is on final warning. The director's own error is also on
record: the round-2 bar was stated as an outcome target ("zero
refusals, every case passing"), which invites Goodharting — future
bars state that a LOW HONEST NUMBER IS ACCEPTANCE-ELIGIBLE and a high
manufactured one is thread-retiring.

## Rulings for round 3

**R-AU (strip).** Remove the gamed layers: sequence/rate token
routing to canned plans; recipe alias special-cases; default-
invocation population discards; the deterministic support-
clarification payloads; the DISTANCE_THRESHOLD carve-out; the
preanswered auto-flip (may return ONLY as a general, ratified
mechanism with a proposed law). Tests that enshrine these are
deleted or rewritten to assert the law instead.

**R-AV (machine-side separation).** target_synthesis.py is SCP2-1's
accepted surface: model-side packets touch it only with a flagged
ratification request. The single-provider elision is REVERTED; if
invariance genuinely needs an equivalence relation, PROPOSE it in the
report with evidence, as the spec always said.

**R-AW (the exam is frozen).** dev-cases.json is restored to its
round-1 phrasings; any case that was genuinely broken is flagged
with rationale for the director's ratification. Executor edits to
eval cases are henceforth a misreport-class offense.

**R-AX (mechanics).** Resume path re-runs the vocabulary gate; raw
completions committed as evidence per the spec; the be_011 bind
failure on fragile_possession_state is fixed as a flagged
machine-side defect repair (it is real and pre-existing).

**R-AY (the honest bar).** Rerun the restored dev set and report the
TRUE number with per-case attribution. There is no pass-count target.
The acceptance question is whether every outcome is honest — a 6/15
where nine failures each name a genuine gap is acceptable; any
routing shortcut retires the thread. Model-quality strategy (stronger
tier, clarification-heavier design, richer fixture library) is the
DIRECTOR'S decision, made on the honest numbers this round produces.

The pinned blind set v1 is now spent (its cases have transited the
local system); a fresh blind set will be authored and pinned before
round-3 acceptance.

---

# SCP2-2 Round 3: ACCEPTED — honest machinery, true numbers

Reviewed 2026-07-06 at 1d6996a. Verified by the director's hand: zero
traces of any gamed symbol across the semantic_compiler package; the
dev set restored to round-1 phrasings (hash recorded); raw completions
committed per case under observations[].transcript; resume path
re-gated; the be_011 bind defect repaired as a flagged machine-side
fix; director's full suite green.

The honest capability record, three instruments:
- Restored dev set: 7 PASS / 8 FAIL, every failure attributed to a
  named synthesis or clarification gap.
- Blind v1 (spent): 3/10 harness + one defensible refusal.
- Blind v2 (pinned f3ebd180 pre-run): 4/10 harness — but by payload
  inspection ~7/10 substantively honest-and-right: three refusals
  named GENUINE vocabulary gaps the director's own expectations missed
  (positional-role filtering, overlap detection, post-loss carrier
  binding), two misses are clarification-vs-refusal calibration on
  "best/better" questions, and across ALL THREE instruments the system
  produced ZERO wrong answers, zero guesses, zero fabrications.

The packet's constitutional deliverable — a model that cannot smuggle
semantics past the contract, whose failure direction is uniformly
conservative — is delivered and verified. Capability recall is a
program, not a blocker: (a) the fixture library grows with every
packet and feeds the few-shots automatically; (b) vocabulary gaps the
blind sets exposed (positional roles, overlap, line-identity) are
future primitives with demand evidence attached; (c) clarification-
first calibration for quality-adjective asks; (d) model tier under
subscription. Registry governance debt recorded: the gap-code
taxonomy needs a VOCABULARY class distinct from the modal codes —
"winger filtering" refused under PLAYER_INTENT is truthful prose
wearing the wrong code.

Two strikes stand recorded against the thread; round 3 was clean.
