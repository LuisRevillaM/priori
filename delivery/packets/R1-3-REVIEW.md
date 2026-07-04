# R1-3 Acceptance Review — Round 1: ACCEPT-WITH-FIXES (the 10 earned; flip gated on F1+F2)

Reviewed 2026-07-04 at 21c5acf. The era's cleanest round 1: provider
legitimate (full candidate set, claim contract prohibits selection claims,
kernel untouched, full registry citizenship), operator genuinely selects
(20-seed shuffle-proof), all 20 booked selections re-derived from raw
parquet both teams to sub-mm, T2 probed live, acting-team keying clean at
composition level, document hash reproduces exactly, 9->10 on a copy
through the correspondence-gated path. Findings are omissions and one
off-path defect — no misrepresentations.

F1 (blocking): could-change-answer coverage decides against rank-1's value
even when top_k>1 — a missing candidate could displace rank k. Decide
against ranked[top_k-1]; add the test.
F2 (blocking, governance): source_provider/source_output pinning keys +
an inert provider-name score bonus grew into the "generic" extremum rule —
the third provider-name channel in three packets, evading the concept-hint
guard and the T1 ratchet. Verified inert (unpinned run: identical hashes)
— remove the keys or demote to post-hoc correspondence assertion; extend
the hint guard to provider names; delete the bonus; republish the
discovery count measured unpinned. THE ROOT FIX: the T1 ratchet extends
structurally to constraint-key channels, not just score literals.
F3: rule-12 audit table must walk ALL booked rows (one of twenty walked).
F4: republish reproducible hashes (strip absolute temp paths from hashed
artifacts — fix the relative_path fallback; publish the stable runtime
trace hash 638e4de5).

Non-blocking noted for R1-C: rule-id vocabulary registration;
UNKNOWN-record input-order sensitivity; T4 real-data variant; flip
evidence paths.
