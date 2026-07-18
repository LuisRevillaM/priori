# CAR-0a Review: ACCEPTED (2026-07-18)

Reviewed at 2df54e9c (+ ratchet acknowledgment). Design sealed before
implementation; fences held; pressure machinery consumed strictly
through the certified primitives per the charter's §3 mapping (the
64-test STOP suite proves no parallel thresholds); ambiguity
propagates (no unique carrier → UNKNOWN attribution, row retained);
the frame-farming and flicker attacks from the Goodhart table have
named failing-then-passing tests. The director's full suite: one
failure — the GEO-0b typed-reference census ratchet (110→116),
which is the ratchet WORKING (six new episode references acknowledged
by name in the census commit); suite otherwise green (634 tests).
The executor's own discovery-run kill (ask-timeout reaper interaction
inside the test harness) did not reproduce in the director's run —
recorded as watch-item, not defect.
