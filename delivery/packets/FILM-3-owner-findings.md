# FILM-3 — the owner's second smoke test (three findings, one packet)

Status: READY  Grade: A (surface + perf; design dictated where stated)
Branch: packet/film-3 off the frontier
Owner findings (2026-07-18, verbatim intents): "weirdness in the
results of the regain" / "the replays are a little slow" / "that UI
could use some serious pruning."
Oracle: committed Playwright producer re-captures; frontend tests
per fix; replay-latency measurement BEFORE and AFTER committed as
evidence (no perf claim without numbers).

## Finding 1 — the regain results read as a bug (they are true)

Five of seven matches are Fortuna home games; the team-match table
shows only one club name per row, so the truth looks like
duplication. Fixes (dictated):
1a. Rows render the FIXTURE from matches.parquet match_title
    ("Fortuna Düsseldorf : FC St. Pauli"), with the counted team's
    name emphasized and the counts labeled per team perspective.
1b. The headline stat becomes the football answer, not the coverage
    stat: "Most regains happen in the defensive third — 1,204 of
    2,811" style, derived from data; the 98.1%-located line demotes
    to the reconciliation strip (N2-XR wording stays).
1c. Moment badges: "LOCATED" is coverage vocabulary on the reading
    surface — replace with the third itself as the badge ("DEF /
    MID / ATT"), slate for location-unknown, per token law.
1d. Moment list default order: chronological within match, matches
    in corpus order (no invisible sort).

## Finding 2 — replay latency (measure, then fix the biggest lever)

Measure and commit: time-to-first-frame on moment click (cold and
warm) against the live URL. Expected levers, in order: (2a) descriptor
carries the first N frames inline so the pitch animates instantly
while the full window hydrates; (2b) client caches hydrated windows
(session-scoped LRU); (2c) prefetch the next/selected-adjacent
moment's window. Implement 2a+2b minimum; 2c if cheap. NO quality
regression: hydrated-window content byte-identical to today's.

## Finding 3 — pruning (dictated deletions; resist adding)

3a. The team-match table collapses behind a "by match" disclosure
    (top summary: thirds bars only); 14 rows never render by default.
3b. Evidence panel merges with the selected moment card (they
    duplicate); JSON toggle stays.
3c. Provenance strip: two rows max; "timings not measured" line
    joins the title-attr detail.
3d. One eyebrow row above the headline, not two ("ANSWER · 2,811
    REGAINS · both teams · 7 matches" as a single line).
3e. Dead vertical space below the pitch on tall viewports: the pitch
    panel gets a max-height and the page a content max-width.

## Acceptance

Latency table (before/after, cold/warm) in the report; goldens
re-captured + director token audit; N8 walkthrough still passes on
the pressing tab (fixture names must not break clause keying);
full-suite table. The three findings map to the owner's words in the
review, per the taste protocol.
