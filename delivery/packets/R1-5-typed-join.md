# Work Packet R1-5 — Operator: typed_join (the keystone)

Issued: 2026-07-04 by the project director. Fifth and final operator of the
R1 era. Governing: ADR 0013 with all addenda; case law R1-1..R1-4 complete.
This packet carries the era's accumulated purpose: the composition
constraints that every prior ghost pointed at, and the acceptance
composition the project's flagship metric rests on.

## Ground rules (standing; clone route sanctioned; patch ranges will be
cut against your clone's own SHAs)

Branch `packet/r1-5` off the frontier (tip 08450a2 or later). Report
stage-committed from commit one; no push.

## Opening obligations (from R1-4 acceptance — do these FIRST, commits 2-3)

O1: the named both-teams composition-level test (rule 13; third round open
— non-negotiable this packet).
O2: window's data-boundary false FAIL (coverage judged on requested window
before period clipping) — fix in the retrofit.
O3: latest_start overlap-policy misnomer — rename or implement.
O4: DELETE same_team_control (director ruling R-I(c)).
O5: ledger/report hygiene — reconcile clone-hash citations, disclose
booking scope, audit artifacts into the tree.

## The operator

`typed_join@0.1.0`: join two capability/operator output channels on
DECLARED identity under DECLARED composition constraints, emitting a
joined record channel whose every row carries both sides' witnesses.

Join keys (declared enum): same_anchor (anchor_id-exact — V8 law),
same_frame_window (declared tolerance), same_entity (player id),
episode_overlap (declared overlap semantics).

Composition constraints — THE POINT OF THE ERA — as bind-time-enforced
elements (not conventions): `same_team_perspective` (both sides' team
keys resolve to the same acting team — the R1-1/R1-2/R1-4 ghost caged),
`entity_identity_preserved` (an entity referenced by both sides is the
same player), `frame_alignment` (declared max skew between sides'
evaluation frames). A join node declaring none of these FAILS to bind
unless it declares `unconstrained: true` with a rationale string — the
constraint is opt-out-with-disclosure, never silent.

Tri-state law: a join row is UNKNOWN if either side is UNKNOWN where it
could change the row (could-change-answer); missing counterpart under a
required constraint -> declared policy (no_match_policy enum: FAIL vs
UNKNOWN vs drop-with-count — counted drops recorded in evidence).

RETROFIT (R-L): window's continuity binding re-expresses over the join's
same_team_perspective machinery (one team-keying implementation, not two).

## Acceptance composition — CAR-0

`fragile_possession_state` per docs/CAR_NORTH_STAR.md: a possession anchor
joined (same_anchor / same_team_perspective enforced) with pressure
evidence (opponents near carrier) AND support evidence (time-to-arrival /
lane occupancy class), producing typed fragile-moment records over real
matches — both teams, full audit table, correspondence declared against
the CAR-0 concept (promote fragile_possession_state into the working
taxonomy per the atlas-review proposal 22 if no row exists — a declared
NEW row with its correspondence is honest; do not shoehorn into a wrong
row). Discovery honest; proof on committed tree; before=11/after on a
copy; real flip mine.

## Required tests

House standard + full case law: each join key; each constraint enforced at
bind AND runtime (probe violations); unconstrained-with-rationale path;
no_match policies incl. drop counts; UNKNOWN propagation both sides;
both-teams composition-level (O1 — the named test); executor-path chains
(join over window output — the two-operator chain the era promised);
frozen-plan hash invariance.

## Deliverables

Branch/clone `packet/r1-5`; obligations; the operator; the retrofit; the
CAR-0 composition executing with evidence; earned delta on a copy; full
audit table; declaration enumeration; full-suite table; pinned-gate proof;
`delivery/packets/R1-5-REPORT.md`.
