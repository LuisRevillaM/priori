# The Own-Footage Track — Make the Film Queryable

Status: `TRACK_CHARTER_V0` — established 2026-07-02. Parallel research
track; does NOT alter the current spine (F2 executor extraction → operator
releases → General Compiler v1 → sealed evaluation). Source of truth for the
track's mission, staging, doctrine, and constraints.

## Mission

> Point the system at football film, ask it football questions in football
> language, and get back the exact moments that answer them — with the
> machine honest about what the camera never showed.

The owner's phrase for it, preserved verbatim as the product's north star:
**make the film queryable.**

## The thesis

Broadcast film is already scouting's working medium. Scouts live inside
footage platforms; coaches clip film for meetings. This track does not
introduce an exotic new data source — it decodes the medium the profession
already trusts, so that:

1. every machine claim pins to a moment a scout can verify with their own
   eyes (the trust loop scouts already use, made mechanical);
2. the same film that today can only be *watched* becomes *queryable* by
   the full typed vocabulary and, eventually, the general compiler;
3. the system's existing honesty machinery — PASS/FAIL/UNKNOWN, typed
   coverage, claim boundaries — handles broadcast data's defining weakness
   (the camera follows the ball; roughly half the players are out of frame
   at any moment) as a first-class, declared property rather than a secret
   papered over with extrapolation. Broadcast data's weakness is this
   engine's home turf.

## Doctrine (non-negotiable)

- **Imputed positions are never presented as observations.** If off-camera
  extrapolation is ever added, imputed data is a separate typed evidence
  tier, permanently distinguishable from camera-observed positions, never
  silently mixed, and never claim-bearing on its own.
- Per-frame, per-player coverage enters the canonical layer as typed
  evidence, not metadata garnish. UNKNOWN discipline applies end-to-end.
- All existing claim boundaries apply to vision-derived data with extra
  force: detection confidence, identity uncertainty, and calibration error
  are evidence properties, not footnotes.

## Staging

**V0 — ingest, don't build.** Adapter for the SkillCorner open-data format
(10 broadcast-tracked matches, partial tracking, 10 fps;
github.com/SkillCorner/opendata) behind the existing canonical port
(ADR 0004's port/adapter split pays off here). Forces per-frame coverage
into the canonical layer; proves the engine on genuinely gappy data. No
GPU; packet-sized; slot after F2-1 without breaking stride.
*Success: at least one existing verified query family executes over a
SkillCorner match with honest coverage-aware results and replay.*

**V1 — run the open pipeline ourselves.** Stand up the open-source
game-state-reconstruction stack (SoccerNet sn-gamestate / tracklab lineage:
detection + tracking + re-ID + jersey OCR + per-frame calibration) on
research clips; produce our own coordinates end-to-end; ingest through the
same adapter. Cloud GPUs (L4/A10-class, single-digit dollars per match,
batch not realtime). *Success: our own pixels-to-coordinates output passes
the same canonical quality gates as V0 data, evaluated against published
ground truth.*

**V2 — own footage.** One camera, one rights-cleared match (lower-league /
accessible football, where data providers don't go and the scouting
dossiers are most valuable), full loop: pixels → coordinates → typed
queries → replayable dossier. *Success: a dossier produced from footage we
captured, every claim decomposing to film moments.*

## Constraints and honest facts

- **Rights are the wall, not the tech.** Deriving commercial data from
  broadcast footage we don't own is contested legal territory (active
  player litigation over tracking data; derivative-data clauses in league
  licensing). Rule: research on open/licensed footage only; any commercial
  path runs through licensed footage or own capture. Legal review before
  any commercialization step.
- **Accuracy ceiling is real.** State of the art on broadcast game-state
  reconstruction is far from solved (2024 challenge winner ~64 GS-HOTA);
  the ball and cross-cut identity are the hard parts. The doctrine above is
  what makes shipping on imperfect vision honest.
- **The moat is not the vision model.** Incumbents' real assets are
  off-camera imputation and QA operations at scale. Our differentiation is
  the opposite bet: honesty about partiality, plus a compiler no one else
  has on top.
- The heavy constraint at scale is QA-hours, not GPU-hours.

## Relation to the rest of the program

CAR and the scouting question bank apply unchanged to broadcast-grade data —
with UNKNOWN accounting doing exactly the job it was designed for. The
sealed-set evaluation and this track are independent; neither blocks the
other. The charter's demo scope (public IDSSE data, pre-meeting demo)
remains in force until the owner explicitly re-scopes; this track is the
ambition running ahead of the charter, on purpose, in writing.
