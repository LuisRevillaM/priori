# LEGIBILITY-2 — truth in ink (perceptual run 1 fix packet)

Status: READY  Grade: A (design dictated; report ambiguity, never
improvise on tokens or constitution)
Branch: packet/legibility-2 off the frontier
Oracle: the committed Playwright producer (extended per below) + the
panel re-runs at acceptance; goldens re-promoted by director ruling
only. Fences: docs/design/** (the constitution INCLUDING the new
N1-EW and N2-XR amendments is director-only and governs this packet),
delivery/oracles/, dev sets, sealed evidence.
Headline risk: perceptual run 1 verdict (REVISE) — "the pixels that
carry certainty are large, amber, and instant; the pixels that carry
doubt are small, gray, and effortful." Full verdict:
delivery/packets/perceptual-run-1/VERDICT.md.

## Gating fixes (constitution violations)

1. ANSWER CARD INVERSION (N1-EW, dictated): when unknowns dominate,
   headline becomes the finding — "1 of 2,811 seen through" at
   display rank; "observed: 1/1 (100%)" demotes to body rank beside
   the bounds. Coach-language subtitle under the bounds: "could be
   almost never, could be always — only 1 could be fully seen."
   Threshold: observed-n < 30 OR unknown share > 50% triggers
   finding-first layout; both layouts implemented, chosen by data.
2. INTERVAL BAR RE-INKED (N1-EW): slate span for the unknown-widened
   interval (dim or hatched), single amber tick/segment for observed
   mass only. Partition strip below stays as-is (it is already
   correct) — the two must speak one color language. Min 2px for any
   nonzero segment (S9).
3. UNKNOWN WEARS SLATE (T2): every UNKNOWN badge, banner accent, and
   legend swatch renders #8B93A0, everywhere. Find and CLOSE the
   token-lint gate hole that let status badges escape (extend the
   lint list; add a test that samples rendered badge colors per
   status).
4. RECONCILE THE DENOMINATORS (N2-XR): banner and moment-list header
   state the transformation: "Showing 115 of 2,811 — …" with the TRUE
   reason read from the data (determine from code why 115: replayable
   footage? per-match scope? state it accurately, never guess).
5. UNKNOWN MOMENT PITCH MARKERS (S4): on UNKNOWN moments, clause
   markers render slate + dashed with doubt-carrying labels
   ("① regain — not verified"), or are omitted where genuinely
   unwitnessed; never amber, never confident.

## High fixes

6. PASS badge → COMPLETE (S5 homonym: pass-the-ball vs
   pass-the-test); matches the header strip's existing word. Pass/
   fail vocabulary retreats to the JSON toggle.
7. Banner box contains its sentence (intrinsic width, panel2 ~92%
   opacity, hairline border, 8/12px padding, 12px inset).
8. Scrubber restyled to tokens with a visible keyboard-focus ring
   (kills the last native-control artifact; also N5 focus evidence).

## Medium fixes

9. Provenance strip (S6): never ellipsize the certification claim;
   absence explained ("TREE not recorded"); H/S/E legended or spelled
   out; real timings or "not measured", never unmeasured zeros.
10. "certified evidence" header badge scoped (S7): "evidence
    pipeline: certified" or moved into the strip.
11. Name the team (S8): the answered-question label carries whose
    regains these are; kill or reword "away+home perspective" jargon.
12. Replay declarations (N6/S11): fps + decimation stated in the UI;
    explain the /101 vs /603 fork; anchor clip clock to match time.
13. Moment list overflow: fade mask + off-screen count (no
    mid-glyph guillotine); ②③ witness-label collision avoidance on
    the pitch (craft runner-up); answer-card type sizes within the
    three-size budget (A3); PASS/COMPLETE moment sorts above UNKNOWNs
    in the list (the star exhibit should not live below the fold).

## Acceptance

Committed Playwright producer extended to capture BOTH answer-card
layouts (finding-first and ratio-first) plus one UNKNOWN-moment
replay with slate markers; three re-captured candidates + the two new
ones reviewed by the director WITH the token audit pass (colors
sampled against §2) before golden promotion; panel round 2 re-runs
after deploy. Full-suite table. Frontend unit tests extended: badge
color per status, denominator reconciliation string derives from
data, headline layout switches on the threshold.
