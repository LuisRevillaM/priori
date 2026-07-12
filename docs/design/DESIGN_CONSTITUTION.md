# DESIGN CONSTITUTION — Entrelíneas Film Room

Keystone, director-authored. All UI work is Grade A: executors
implement to spec and report ambiguity; executor edits to this file
or to the tokens are auto-REVISE. The owner's design notes are
ledgered as constitution defects — the missing RULE gets written, so
no note ever recurs.

## 1. Reference class (our craft peers — never the category median)

- **Linear** — operational density, typographic discipline, keyboard
  citizenship. The Film Room is a tool, not a brochure.
- **NYT Graphics desk** — honest data display: intervals shown, not
  hidden; annotation over decoration; every mark earns its ink.
- **Hudl Sportscode** — the film-room vernacular coaches already
  trust: clip lists, scrub culture, the pitch as the primary canvas.

The synthesis: operate like Linear, display data like the Times
graphics desk, speak film-room like Sportscode. If a screen wouldn't
survive review at any one of the three, it isn't done.

## 2. Tokens are the only styling currency (lint-enforced)

The palette and type ramp in docs/design/FILM_ROOM.md are the tokens:
ink #0B0F0D · panel #111814 · panel2 #0E1411 · turf #1E3A2A ·
turf-line #3A5C46 · chalk #E8F2EA · chalk-dim #9FB3A6 · amber #FFB13D
· amber-dim #8A6524 · slate #8B93A0 · fail #6E4A45 · home #5FB0FF ·
away #FF6E5E · ball #F5F0E6. Mono for numbers/hashes/clocks
(tabular-nums always); system sans for prose; radii 3-6px; hairline
#1C2620 borders; no shadows, no gradients.

Rules:
- T1. No raw color/size literals outside the token sheet. A lint gate
  (fixtures-gate style) fails the build on violations.
- T2. **Slate is UNKNOWN's color and nothing else's.** Amber is
  observed/accent and nothing else's. Semantic color is never
  decorative.
- T3. Home/away hues never appear except on pitch entities and their
  direct references.

## 3. Non-negotiables (deterministically enforceable; build fails)

- N1. **Every number carries its honesty**: no point estimate renders
  without bounds + unknown count (component-constructor law — already
  unrenderable; stays that way).
- N2. **Every state designed**: warming (narrative, not spinner),
  empty, the three typed error identities (schema / truncation-retry /
  internal+correlation-id), overflow (counts always shown, no silent
  truncation), slow-model (progress narrative for >10s asks).
- N3. **Provenance strip on every answer** — plan, doc, tree. Never
  optional, never collapsed by default.
- N4. Real content only — the fixtures gate stands; no lorem, no
  placeholder match ids, no fabricated numbers in any committed pixel.
- N5. A11y floor: visible focus states everywhere; keyboard scrub for
  the replay; contrast ≥ 4.5:1 for text on panel/turf; reduced-motion
  respected (already in the mockup — stays law).
- N6. Performance: warm gallery first-paint < 2s; replay at declared
  fps (decimation stated in the UI, never silent).
- N7. Microcopy: verbs say what happens ("Ask", "Replay"); errors say
  what went wrong and what to do; the system never blames the user
  for its own faults (SMOKE-1's law, now design law).

## 4. Anti-slop register (auto-REVISE on sight, regardless of gates)

- A1. Default component-library look: rounded-xl cards, drop shadows,
  gradient heroes, pill-button rainbows.
- A2. Spacing arrhythmia: gaps outside the 4/8/12/16/24 rhythm.
- A3. Hierarchy soup: >3 type sizes in one panel; bold used as color.
- A4. Empty-state poverty: bare "No data"; every empty state names
  what would fill it and how.
- A5. Spinner-forever: any wait >2s without narrative text.
- A6. Decorative icon/emoji noise; icons only where they carry
  meaning the label can't.
- A7. Chart junk: gridlines, legends, 3D, or colors the mockup's
  data displays don't use; the interval bar + partition strip are the
  canonical data displays.
- A8. Unmotivated motion; animation only for the replay, state
  transitions, and the evidence trail draw-in.

## 5. The perceptual gate stack (every UI packet, in order)

1. Deterministic: token lint, state inventory (N2 checklist per
   screen), fixtures gate, a11y checks, perf budget.
2. Golden screens: committed screenshots (R-AZ layout) diffed against
   goldens; goldens change only by director ruling.
3. Multimodal critic panel: ≥2 fresh-context frontier agents score
   the screenshots against THIS file, adversarially briefed as a
   discerning design director; every finding must cite screen,
   element, and the RULE violated. A persuasive finding naming no
   rule becomes a new rule (this file amends).
4. Cold walkthrough: a fresh agent drives the real UI as a football
   coach with a real task ("find how often we keep the ball under
   pressure, show me the worst moment") knowing nothing about the
   system; every hesitation, dead end, or misread is a finding.
5. Director delight pass on a real device. Never delegated, never
   skipped before an outsider sees the surface.

## 6. Owner taste calibration (scheduled once, then rare probes)

One high-resolution session: director brings the reference shortlist,
this token sheet, and 2-3 fully designed variants of the keystone
screens (gallery answer, moment replay, warming/error states); every
owner reaction is transcribed into rules here. Thereafter: rare taste
probes only (one gate-passed load-bearing screen, variants side by
side). KPI: owner intervention rate trends to zero while shipped
surface area grows.

## 7. Narrative correspondence (owner calibration note, 2026-07-10 —
##    the rule that was missing)

- N8. **The answer must be legible AS the question.** Every element
  the screen highlights must be traceable, by a first-time viewer, to
  the clause of the question it satisfies: the ask sentence renders
  with its operative clauses keyed (①②③…), each key appears ON the
  pitch at its witness moment (① regain ring, ② carry trail with its
  threshold label, ③ pass marker), and the moment card describes the
  moment in the QUESTION'S words, never in schema words. The test: a
  viewer who reads the question and watches one replay can point at
  the screen and narrate which part is which. If they cannot, the
  screen fails regardless of every other gate.
- Corollary: the interval card's label restates the question as
  answered ("Of 115 regains, 1 completed the full chain…"), never as
  a metric name. Schema vocabulary (anchors, statuses, node ids) is
  toggle-gated debug, never the default reading surface.

## 8. Amendments from perceptual stack run 1 (2026-07-13)

- N1-EW (EVIDENTIARY WEIGHT). A point estimate's display scale may
  never exceed what its observed-n warrants. When observed coverage
  is thin (observed-n below ~30, or unknowns dominate the
  population), the FINDING is the headline ("1 of 2,811 seen
  through"), never the ratio; the percentage demotes to body rank.
  Amber ink is budgeted in proportion to evidence: the interval's
  unknown-widened span renders in slate; only the observed point/mass
  wears amber. A 1/1 → "100%" at display scale is the canonical
  violation.
- N2-XR (CROSS-PANEL RECONCILIATION). Every population count visible
  on the surface must reconcile to every other visible count, with
  the transformation named ON the surface ("Showing 115 of 2,811 —
  the rest have no replayable footage"). Two unreconciled
  denominators on one screen is a violation regardless of each being
  individually true.
- T2 enforcement note: run 1 found UNKNOWN badges wearing amber in
  shipped pixels — the token lint gate has a hole (status badge
  classes). Golden review now includes a token audit pass: sample
  status colors against §2 before promotion.
