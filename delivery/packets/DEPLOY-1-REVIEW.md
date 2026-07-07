# DEPLOY-1 Review: ACCEPT-WITH-FIXES (fixes executed at review)

Reviewed 2026-07-07 at e595ef8. Oracle green in BOTH modes against
the local public-mode service, run by the director: bind-before-warm
verified (page serves in ~6s where the old service blocked for
minutes), bootstrap honest through warming→ready with the interval
law and provenance intact, real replay frames served, the token gate
issuing typed refusals, and a live ask completing through the public
path with a typed outcome. Director's full suite green.

Fixes executed by the director's hand (all in director-owned
artifacts): the oracle corrected three times to the API's true shapes
(frame_id not frame_index; real frame ids from replay.frames[]) — the
payload-contract ergonomics debt (EXAM-1 F-F) biting its third
victim, now its last on this path since the oracle encodes the truth;
RB-001 updated to document WORKBENCH_HERMES_ENABLED, the executor's
deliberate-enable switch for live asks on public boxes — RATIFIED as
sound defense-in-depth, with the note that blueprint-only env vars
are documentation defects (the runbook is the owner's interface).

Carried (ledgered): 16 legacy Playwright expectations against the old
default route — retirement/rescope packet pending; not a DEPLOY-1
regression.
