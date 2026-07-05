# A soccer language compiler: approach, library, and what testing it revealed

> Canonical text of the public Entrelíneas case study. The live interactive version —
> with animated coordinate replays for every example — is served at
> `/case-study` on the deployed Workbench
> (currently https://priori-integrated-alpha.onrender.com/case-study) and rendered from
> `apps/workbench-alpha/src/CaseStudy.tsx`. This document is the
> version-controlled narrative of record; if the two drift, the component should
> be updated to match this text or vice versa in the same change.

A compiler for football concepts: describe a situation, compile it into
evidence-backed primitives, and find the real moments in tracking data where
that situation occurred.

```text
Raw event + tracking data (IDSSE / DFL)
-> Canonical match state
-> Primitive / relation catalog
-> Typed query plan
-> Compiler · binder · search
-> Deterministic runtime
-> PASS / FAIL / UNKNOWN evidence
-> Replay + coach-facing wording
```

Invariant across every layer: **product language cannot exceed evidence
strength.**

## What we're building

The goal is a compiler for football concepts. Someone describes a situation — a
pass that breaks a line, a switch of play, a team building out from the back —
and the system finds the real moments in tracking data where that situation
occurred. The input is public IDSSE/DFL data: per-frame positions for every
player and the ball, plus an event feed.

The hard part is not finding football-looking events. It is being precise about
what the system is allowed to claim about them. A "completed pass" in an event
feed is a label. Whether the receiver controlled it, whether the team kept it,
and whether it led anywhere are separate facts that need separate evidence. The
system treats each as a distinct claim, and the language shown to a user is
never allowed to be stronger than the evidence behind it.

## The approach

Every measurement is a primitive: a deterministic function over the tracking
data that returns a typed result plus the evidence for it. A primitive returns
PASS, FAIL, or UNKNOWN. UNKNOWN means the data was insufficient to decide, not
that the answer is no. Each primitive also has a claim boundary — an explicit
statement of what its result does and does not mean: geometry, for instance,
but not intent, quality, or causation.

Primitives compose. A coach-facing concept is a typed plan over several
primitives, with thresholds and a defined set of evidence fields it may expose.
A request either compiles to an executable plan or returns an honest gap.
Nothing is a hand-written highlight detector.

## What the library contains

The catalog currently has about forty primitives and relations. Grouped by what
they describe:

- **Build-up:** possession segments, pass chains, structured zones, controlled
  line breaks.
- **Ball movement:** switch of play, carries, one-touch relays, lateral shift,
  progressive corridors.
- **Progression:** forward progression and final-third entry, opponents
  bypassed.
- **Defending and pressing:** team press, pressure on the carrier, marking,
  cover shadow, defensive lines, compactness, local numerical advantage.
- **Off the ball:** runs and run types, support arrival, time to arrival, lane
  occupancy, space generation.
- **Set pieces:** set-piece structure and restart type.

Many primitives sit close to one observable condition. Some are spatial:
defenders around a carrier, or a defender on a ball-to-target lane. Some are
kinematic: a player speeding up, slowing down, or arriving at a point. Those
observations are useful, but a primitive existing in the catalog is a building
block, not a coach insight.

A coach-facing situation is compound. It can require geometry, relationships
between players, event context, control, and the words the surface is allowed
to use. The difference between a primitive and a claim is the spine of this
test.

### Geometric primitive: observed pressure on the carrier

- **Look for:** the carrier, nearby defenders, and the seven-metre radius at
  one measured frame.
- **Proves:** the highlighted defenders are close, closing, and spread around
  the carrier.
- **Does not claim:** a coordinated press, trap, intent, quality, or tactical
  cause.

> Observed pressure on the carrier: the highlighted defenders satisfy the
> distance, closing, and angle-spread gates. This is substrate-verified
> geometry, not a product-validated press interpretation.

### Geometric primitive: cover shadow on a lane

- **Look for:** the ball-to-target lane and the defender sitting inside its
  threshold band.
- **Proves:** a defender screens that lane under fixed distance and projection
  thresholds.
- **Does not claim:** defender intent, pass probability, pitch-control value,
  interception, or quality.

> Observed lane screening: one defender sits within the measured ball-target
> lane band. This is geometry only, not a claim that the pass was impossible or
> deliberately denied.

### On-ball primitive: observed carry

- **Look for:** the highlighted carrier and the ball-control path from
  reception to release.
- **Proves:** same-player movement under control across a measured carry
  interval.
- **Does not claim:** dribbling skill, defender bypass, pressure breaking,
  intent, decision quality, or value.

> Observed carry: the same player moves with the ball under the declared
> control thresholds. This is movement-under-control only, not a claim that the
> carry beat defenders or was valuable.

## Putting it to test: high-bypass passes

High-bypass is different. It is not a single primitive. It compounds a pass
event, opponent positions, forward progression, reception control, restart
context, and the words the surface is allowed to imply about outcome. The
geometry can be true while the coach-facing word is still too strong.

### Composed concept: high-bypass pass

- **Look for:** a pass that travels beyond multiple defending players.
- **Proves:** pass geometry, bypass count, and then whether clean control
  settled.
- **Does not claim:** success or value unless the stricter control gate also
  passes.

We took one concept all the way through: a high-bypass pass — a completed,
controlled pass that moves the ball forward and takes several opponents out of
the play. As a typed plan:

```text
controlled_pass_episode
+ opponents_bypassed_by_action
+ forward_progression ≥ 8 m
→ high_bypass_completed_pass
```

It was a useful test because it touches the whole stack: event feed, tracking,
geometry, control, possession, and the wording a coach finally sees.

## Findings

At the substrate level the controlled-pass primitive does what it should. On
the verified scope, match `J03WOY`, it evaluated 639 candidate events:

```text
453 PASS
135 FAIL
 51 UNKNOWN
```

The non-PASS cases carry specific reasons, among them
`another_player_controlled_first` (35), `possession_definitively_broke` (67),
`release_contradicted` (33), and `release_not_confirmed` (84). The system
records why a candidate failed instead of dropping it silently.

The same data shows the limit. Among verified controlled passes, the median
time from release to reception is 0.84 seconds and the median forward
progression is 0.53 metres. A controlled pass is often a brief touch that
barely advances. That is a sound primitive, but it does not support words like
"successful" or "kept it."

The first high-bypass surface ignored that limit and presented these moments as
successful attacking actions. When the replay was extended past the moment of
reception, the reception often never settled into clean control. The ball could
stay loose or contested without either side holding it cleanly. The geometry
was right; the word "successful" was not earned.

The first attempt to fix this used the provider's possession flag to confirm
the team kept the ball. It passed the same unsettled moments, because that flag
credits a team through contested and transitional touches. It agreed with the
original mistake instead of catching it.

A second issue surfaced once control was handled properly. Of the five moments
that passed a stricter control check, two came from restarts — a free kick and
a throw-in. They were valid high-bypass passes and valid controlled receptions,
but not open-play examples.

## What changed, and where

It is worth being exact about where these fixes live, because the location is
the point. None of them changed the core compiler. The primitives were already
truthful. The overclaims happened at the boundary between the substrate and the
coach-facing product, and that is where the fences were added.

**Clean-control check — generation layer.** The check,
`clean_control_retention_sequence`, is not a core catalog primitive. It runs
over the compiler's output, in the layer that prepares moments for the surface,
and keeps only the passes where control was genuinely held. Of twenty raw
high-bypass passes, five passed. Because it is currently a gate rather than a
registered primitive, the natural next step is to promote it into the catalog
so other concepts can reuse it.

**Event-context filter — runtime fields, surface default.** The restart typing
already existed in the core runtime, `set_piece_restart_type`. The change
carried `event_type`, `restart_type`, and `open_play_status` through to the
moment payload and defaulted the surface to open play. This was mostly plumbing
knowledge the runtime already had out to where a coach sees it, plus a filter —
not new detection.

**Claim-backing gate — coach API layer.** The coach service, `app_service.py`,
now holds a map of which composition each coach-facing claim requires, and
refuses to emit a claim unless that composition is present and passing. It
fails closed. "Controlled reception" requires the clean-control check;
"open-play example" requires open-play status.

The shared property: the core compiler stayed the same, and the product layer
stopped saying more than the compiler had proven.

## Where this leaves the approach

The substrate is broad and the claims are kept narrow. The library already
spans build-up, ball movement, progression, pressing, off-ball movement, and
set pieces. What the high-bypass work established is the rule the rest of the
library has to follow: a coach-facing claim is allowed only when the
composition beneath it proves that exact claim. The system gets better by
making each remaining overclaim easy to find and easy to fence, not by adding
cleverness on top.

---

# Part two: auditing the compiler with its own doctrine

*Added 2026-07-02. Part one ended with a rule: a claim is allowed only when
the composition beneath it proves that exact claim. Part two is what happened
when we turned that rule on the compiler itself — the measurement code, the
gates that verify it, and our own flagship numbers.*

## What we tested this time

Part one tested a concept (the high-bypass pass) against the stack. Part two
tested the stack against itself: a foundation audit of the runtime core and
every measurement kernel, with one standing question — *where can missing
evidence still become a definite answer?* Every finding below was reproduced
with synthetic geometry before it was believed, and every fix was reviewed
adversarially by a reviewer whose job was to reject it.

The audit also found something more uncomfortable than any single bug: the
machinery that was supposed to keep the vocabulary honest had gone stale
without anyone noticing. The checked-in parity report said all capabilities
were bound and clean; regenerating it fresh said nine capabilities were
executable with no registered contract at all. The report was written only on
success, so a failure left yesterday's success in place. Verification you
don't re-run is decoration.

## First, the gates had to stop lying

Before touching a single measurement, three structural changes:

- **Verifiers became read-only.** A gate used to regenerate its own evidence
  files when run, which once overwrote a verified historical report with a
  weaker local one. Now every gate is a pure check that fails loudly on
  drift; rewriting pinned evidence takes an explicit, logged opt-in — and a
  failing run writes the failing report, so stale success is impossible.
- **Continuous verification.** Every push now re-runs the test suite and the
  vocabulary parity checks on independent infrastructure, including a step
  that fails if any gate modified a tracked file.
- **A judge we cannot impersonate.** Promotion of a capability now requires a
  signature from a key held only in a protected environment, alongside the
  fingerprint of a privately-authored evaluation set. The builder — human or
  agent — cannot certify its own work. The first thing the configured gate
  did was refuse to promote, correctly, because one canary in its own
  machinery had been written backwards. We fixed the judge's code in the
  open; the certificate records the judge's own hash, so even that fix is
  auditable.

## Then the measurements: three numbers that had to change

**639 became 563, and 135 failures became 84.** Part one counted 639
candidate passes on the test match. It turns out 76 of them were throw-ins,
free kicks, goal kicks, and kick-offs — a substring filter had quietly
admitted set pieces, and a throw-in was being judged for ground control while
the ball was in the thrower's hands. Open play is now the declared default;
set pieces are included only by explicit declaration. And of the old FAIL
verdicts, a third were not failures at all: a pass still in flight at the
half-time whistle, or a passer visible in one frame out of a hundred, had
been recorded as *contradicted* when the honest answer was *unknown*. FAIL
now means the evidence contradicts the claim; UNKNOWN means we could not
decide. They are different facts.

**A corridor's 0.8 seconds became 0.6.** Episode durations were counted as
frames-times-rate, which silently awards one extra frame interval to every
episode. Measured as true elapsed span, fifteen corridors on the M1.1 corpus
that appeared to stay open for exactly 0.8 seconds had actually been open for
0.6. Durations also no longer bridge tracking dropouts: if the ball or the
target player is untracked mid-window, the episode closes with
`closed_on_missing_evidence` rather than quietly counting untracked time as
corridor time.

**The pitch got one lane model instead of two.** Lane occupancy divided the
pitch into five equal lanes; the corridor destination logic used a different,
fractional partition. The same point at y = 8.0 m was "central" to one
primitive and "half-space" to the other — two primitives that would disagree
inside a single composed query. There is now one declared partition (five
equal lanes, mirror-symmetric, ties toward center, with an explicit
epsilon), used by every consumer. Requirements like "two players in the
central lane" now count distinct players in a frame, not player-frames — one
player observed twice no longer impersonates two players.

## The hero number: 14 → 11 → 12

Part one's era produced an attested flagship result: fourteen moments where a
progressive corridor opened early in a possession, stayed open at least 0.8
seconds, and the ball entered its destination region in time. That attested
record still stands — it honestly describes what the June engine measured.

The live engine now finds twelve, and the path matters more than the number.
Honest durations removed three moments whose corridors had only appeared to
clear the threshold. The unified lane geometry then admitted one moment the
old fractional partition had wrongly excluded. Both steps are pinned in the
contract test with their causes, so the number's history is part of the
evidence: *fourteen under inflated time, eleven under honest time, twelve
under honest geometry.*

A system whose flagship number cannot change is advertising. A system whose
flagship number changes exactly when its measurements improve — and can show
you why, moment by moment — is an instrument.

## Where this leaves the approach, again

Part one's rule was about the boundary between substrate and product. Part
two extends it downward: the substrate itself, the gates that verify it, and
the numbers we are proudest of get no exemption. The discipline is now
mechanical rather than behavioral — read-only gates, continuous parity,
an unimpersonatable judge — because part two's real lesson is that honesty
maintained by memory decays, and honesty maintained by machinery doesn't.

Nothing in part two added a new football concept. Every change made an
existing claim smaller, truer, or better-declared. The library's next growth
— compositional operators that let one vocabulary answer many questions — now
builds on measurements that mean what they say.
