# LEGIBILITY-1 — the answer reads as the question (implements N8)

Status: DRAFT (commits at DEPLOY-2 merge; dispatches after — same surface)
Grade: A (all UI is Grade A; this spec dictates design and microcopy)
Branch: packet/legibility-1  Oracle: golden screens + component tests
(committed at dispatch) + the perceptual stack with the N8 walkthrough
task verbatim.
Headline risk: owner finding 2026-07-10 — a first-time viewer cannot
map the pixels to the phrase. Root cause two (root cause one was the
degraded gallery, DEPLOY-2): nothing keys the question's clauses to
what the screen highlights.

## The design (dictated)

1. CLAUSE KEYS, machine-derived. The answered question renders with
   its operative clauses keyed ① ② ③ — derived from the meaning
   expression's typed meaning_clauses + sequence stage parameters,
   NEVER hand-written per question. Plain-language clause rendering
   via a template over (action, field, value, unit): stage_1 regain →
   "① they win the ball back"; stage_2 carry_forward_progression_m
   >= 3.0 → "② carry it forward at least 3 m"; stage_3 controlled
   pass → "③ keep it with a completed pass".
2. KEYS ON THE TURF. Existing stage overlays gain their key badges:
   the regain ring wears ①, the carry trail's threshold label wears ②,
   the pass marker wears ③. Badge styling: mono, amber on ink chip,
   same size family as stage labels. No new colors.
3. MOMENT CARDS SPEAK THE QUESTION'S WORDS. PASS card: "① 63:12 regain
   → ② +11.2 m carry → ③ pass kept" (values from stage witnesses).
   UNKNOWN card: "couldn't see whether ② happened — half ended" (reason
   template from truncation_reason). Schema vocabulary (chain_status,
   anchor ids, node names) moves behind the existing JSON toggle —
   never on the default card face.
4. THE INTERVAL CARD RESTATES THE QUESTION AS ANSWERED. Template over
   population + partition: "Of 115 regains, 1 completed the whole
   chain ①→②→③. 90 couldn't be fully seen — they widen the honest
   bounds to [0.04%, 100%]." The metric-name label moves to the
   provenance strip.
5. STATES. Warming, empty, refusal, clarification cards inherit the
   same voice: plain football sentences, the system never blames the
   viewer, unknowns say what would resolve them.

## Required evidence at acceptance
Three golden screens (gallery answer, keyed moment replay, UNKNOWN
moment) reviewed by the director BEFORE committing as goldens;
multimodal critic panel scoring N8 by name; cold walkthrough running
the N8 test verbatim ("read the question, watch one replay, narrate
which part is which"); component tests: clause keys derive from a
FIXTURE expression (mutation: change a clause value → the rendered key
text changes); no schema tokens on the default surface (lint list).

## Fences
docs/design/** (constitution + tokens are director-only), both deploy
oracles, dev sets, blind pins, sealed evidence.
