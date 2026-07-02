# DOC-1 Acceptance Review — Round 1: REJECTED

Reviewed 2026-07-02, branch `packet/doc-1` commit `09b8120`. Everything
except one exhibit verified clean: fences exact, payload reproduces
byte-for-byte through the committed generator from canonical data, exhibit 1
(honest UNKNOWN, `release_not_confirmed`) and exhibit 2 (0.8→0.6s class
representative, disclosed as such) truthful and claim-bounded, part one
byte-untouched, genealogy figure correct, all builds/suites green.

## Blocking: Exhibit 3 is not the twelfth hero moment

Verified by executing the attested hero plan on the archived F1-C-era engine
(`d006780`) and diffing the result sets: the exhibited result
`139dec21797fc297` is ALREADY in the 11-row F1-C set. The row actually added
by F1-D lane unification is **`854d129b6d14f7dd`** (relation
`cfd1acd732336d30`, destination `central_central`, entry y = +5.11 m). The
caption "Once corridor destination logic and lane occupancy used the same
model, this possession qualified" is therefore false for the displayed
possession.

Root cause: `scripts/workbench_alpha/generate_case_study_part_two_replays.py`
(`twelfth_hero_payload`) selects heuristically (PASS half-space entry nearest
y=8 within 6.8 < |y| < 11.34 — also the wrong old bound; the fractional
model's was 34 × 0.33 = 11.22) instead of computing the set difference.

## Required for round 2 (same branch, append commits)

R1. Select exhibit 3 by set difference against the F1-C-era result set —
    hardcode the verified result id `854d129b6d14f7dd` with a comment citing
    this review, or compute the diff reproducibly. Regenerate the payload.
    Update the exhibit's "Look for" text: the true twelfth is a
    central-lane destination (not half-space) — adjust the narrative
    accordingly and keep the caption strictly to what the diff proves.
R2. Exhibit 4 caption must state the packet-required contrast explicitly:
    old fractional destination model → "central" (|y| < 11.22); old lane
    occupancy → RIGHT_HALF_SPACE; declared five-lane model →
    right_half_space (6.8–20.4 m, ties toward center). Render the three
    classifications, not just "the models disagreed."
R3. Report addendum: regenerate provenance section for exhibit 3 (the diff
    method and both engine versions), and correct the old-boundary constant
    wherever 11.34 appears.
