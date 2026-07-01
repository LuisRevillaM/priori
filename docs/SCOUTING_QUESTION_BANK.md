# Scouting Question Bank

Status: living steering document, started 2026-07-01 from a brainstorming
session with the owner. These are the questions the system exists to answer.
They serve three purposes:

1. **Product north star** — the two flagship use cases are the *opponent
   dossier* (scout a team: how do they progress, where do they bleed) and the
   *player dossier* (CAR-style: who keeps fragile possessions alive).
2. **Steering function** — primitive/vocabulary prioritization should be
   scored by how many of these questions each new capability unlocks
   (alongside atlas coverage-unlock and CAR-unlock).
3. **Benchmark corpus** — a development benchmark for the semantic compiler:
   each question should eventually compile to an executable typed program or
   a precise typed gap. NOTE ON SEALED-SET HYGIENE: because this file is
   visible to the builder side, it must NOT be the S2I-F sealed set. The
   sealed set should be authored privately (variations and holdouts of these
   themes work well) and hash-pinned before any run.

Claim discipline applies to every question: the engine answers with observed
geometry/kinematics and typed outcomes, never intent ("they *want* to
overload the left") or quality judgments. A question that inherently requires
intent should compile to a typed gap or be rephrased to its observable proxy.

---

## A. Opponent dossier — with the ball

**A1. Build-up shape and first phase.**
- What shape do they build in? (back three vs back four with a dropping
  pivot; GK involvement; fullback height at first-phase possessions)
- Where does the goalkeeper distribute — short to CBs, into the pivot, or
  long — and how does that split change when the first line of pressure is
  high vs absent?
- How do they escape the first line: CB carries into midfield, third-man
  combinations off the pivot, wall passes, direct switches, or long balls to
  a target?

**A2. Progression mechanisms (the core question: *how* do they achieve
progress, not how good they are).**
- Taxonomy share: of their progressions into midfield / final third, what
  fraction came by (a) line-breaking pass, (b) carry, (c) switch of play
  after moving the block, (d) long ball + second ball, (e) transition after
  a high recovery, (f) set-piece restart?
- Where do progressions happen — which lanes/corridors, which side?
- Who are the progression hubs — which players' passes/carries account for
  the line breaks; who receives between the lines?
- Block manipulation: show sequences where circulation shifts the opposing
  block laterally and the entry comes through the vacated space (the M1
  ball-side block-shift family, run in reverse perspective).
- Press response: when pressed high, do they play through (one-touch relays,
  bump-and-set), around (fullback-to-fullback), or over (long)? What is the
  observed completion/retention of each route?

**A3. Arrival and chance genealogy.**
- How are their chances born? Trace back from shots/box entries: what
  happened in the preceding N seconds — established possession, transition,
  set piece? Which mechanism delivered the final entry (cross, cutback,
  central combination, run in behind)?
- Final-third entry patterns: wide overloads then cutback? Early crosses?
  Which channel?

## B. Opponent dossier — losing the ball (vulnerability map)

**B1. Circumstances of dispossession.**
- Under which circumstances do they lose the ball: at reception under
  pressure, on the carry, on risky line-break attempts, on long-ball
  seconds?
- Where are the highest-frequency losses when building up through midfield?
  (zone map of build-up turnovers)

**B2. Transition exposure.**
- Show losses in high/advanced areas that are NOT terminal actions (cross,
  shot) — i.e. live turnovers that gift counter-attacks.
- Rest-defense at the moment of loss: how many players behind the ball, how
  much space behind the last line, distance of nearest recoverers to the
  loss point. Where is the structural vulnerability to transition?
- After they lose it, do they counter-press (defenders converging on the
  ball within N seconds) or retreat — and does the counter-press actually
  win the ball back or get bypassed?

**B3. Defensive block (for attacking them with the ball).**
- Where do they engage — line of engagement height by game phase?
- How does their block shift when the ball goes wide, and how quickly — can
  a switch beat the shift? (the original M1 family, product-facing)
- Compactness between the lines: when does space open between midfield and
  defensive lines, and what opens it?
- Press triggers and press decay: after which observable events do they jump
  (back pass, slow wide reception), and how often is that press bypassed
  within N seconds?
- Asymmetries: which flank is bypassed more; which defender steps out and
  leaves the gap.

## C. Player dossier

**C1. CAR family (see docs/CAR_NORTH_STAR.md).**
- Show situations where a player kept possession alive under observed
  pressure (fragile possession states) — and how it resolved (progressed,
  reset, lost).
- Which players retain above the spatially-conditioned baseline in fragile
  states? (the CAR number itself, methodology-labeled on 7 matches)

**C2. Progression contribution.**
- A player's line-breaking passes, progressive carries, one-touch escapes
  under pressure, receptions between the lines.

**C3. Off-ball value.**
- Support arrival: who consistently arrives to give the carrier an option in
  fragile moments?
- Lane occupancy and space generation: whose runs drag defenders and open
  lanes for others (observable proxy: defender displacement correlated with
  run, claim-bounded to geometry)?

**C4. Defensive actions (observable only).**
- Closing speed and press participation; cover-shadow discipline while
  pressing; recovery runs after team loss.

## D. What these questions demand from the engine (director's notes)

1. **The aggregation layer is the missing product piece.** Today the engine
   answers "show me the moments matching X." Most dossier questions are
   *tendency* questions: shares, zone maps, rates, per-player baselines.
   That is a new, thin layer — run a battery of typed queries, aggregate
   with honest denominators — but it has real claim discipline: every rate
   needs UNKNOWN accounting (a "loss rate in zone 14" over frames with
   tracking dropout must surface its coverage), and every aggregate must
   decompose back to replayable moments. No aggregate may exist that cannot
   be exploded into its evidence.
2. **Chance genealogy needs backward temporal tracing** (from an outcome
   event to the preceding sequence window) — largely composable from
   existing possession/episode machinery plus `transition_anchor` (already
   the top coverage-unlock primitive).
3. **Several questions are typed-gap bait by design** — "do they *want* to
   press," "was the run *decoy*" — and should stay in the bank as compiler
   honesty tests: the correct answer is a MODALITY_GAP or a rephrase to the
   observable proxy.
4. **The two dossiers are the demo.** An opponent dossier for one of the 7
   corpus teams and a player dossier for one player, every claim clickable
   down to coordinate replay, is the meeting-ready artifact this system was
   built to produce.
