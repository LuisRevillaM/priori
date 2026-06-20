# M1 Specification - Verified Ball-Side Block-Shift Evidence Spine

## Product Outcome

From real IDSSE tracking data, produce auditable moments where the ball enters a wide area, the defending block shifts toward it, and the attack subsequently switches, retains without switching, or loses possession.

## Boundary Decision

M1 is a verified vertical slice, not a generic backend milestone. It must prove that real source frames produce tactical measurements, those measurements satisfy one frozen query-specific model, and generated replay bundles visibly support the classification.

The milestone deliberately avoids wording that implies a switch necessarily follows the block shift. M1 proves a ball-side defensive shift and classifies the subsequent outcome. It does not prove that a switch was always available, that retaining was a mistake, that the attacking team intentionally caused the shift, or that the sequence was an opportunity without an opportunity model.

## Scope

M1 includes:

- source-locking and provisioning IDSSE/DFL raw data;
- an isolated IDSSE reader port with Floodlight as the primary adapter;
- canonical 25 Hz match, frame, position, event, team, player, and orientation stores;
- raw XML parity checks against canonical rows;
- 5 Hz analysis stream linked back to source 25 Hz frames;
- quality and orientation checks;
- the minimum tactical primitives needed by the ball-side block-shift detector;
- one query-specific Pydantic model and frozen configuration;
- deterministic detector and outcome classifier;
- evidence bundles for accepted moments and selected near misses;
- minimal static TypeScript replay app for verification;
- end-to-end verifier and proof pack;
- independent review protocol at Gate A, Gate B, and Gate C.

## Non-Goals

M1 excludes:

- Hermes or any other agent runtime inside the product;
- natural-language query compilation;
- a generic tactical query language;
- abstract scene/condition/dynamics/outcome/counterfactual/value frameworks;
- production API, Python server, database server, queues, auth, cloud deployment, or jobs;
- licensed match video;
- polished analyst dashboard;
- multiple query families;
- ML training;
- player-intent, causation, optimality, or "missed opportunity" claims;
- spatial-control acceptance requirements;
- synthetic or manually authored accepted match evidence;
- Go, unless a measured failure produces an ADR proving it is needed.

Coding agents may help deliver M1. An agent is not yet part of the M1 product.

## Technology Decision

M1 uses a Python analytical spine and a TypeScript replay proof.

Python is used for:

- IDSSE ingestion;
- canonicalization;
- quality checks;
- coordinate normalization;
- possession segmentation;
- primitive calculation;
- deterministic detection;
- evidence-bundle generation;
- independent verification.

Recommended analytical stack:

```text
Floodlight       provider parsing
Polars/PyArrow  canonical tables and transformations
NumPy           numerical geometry
Pydantic        authoritative contracts
Pytest          unit and integration tests
Hypothesis      geometric/property invariants
Pyright strict  static type checking
Ruff            linting and formatting
```

Python constraints:

- no untyped public functions;
- no notebooks as production implementations;
- no full-corpus row-by-row Python loops;
- no implicit coordinate units;
- no mutable global query settings;
- no remote loading after provisioning;
- no dictionaries crossing contract boundaries without validation.

TypeScript is used for:

- pitch playback;
- result selection;
- evidence presentation;
- frame navigation;
- provenance display;
- browser verification.

Recommended replay stack:

```text
React + Vite
TypeScript strict mode
Canvas pitch renderer
Generated contract types
Runtime JSON Schema validation
Vitest for components/utilities
Playwright for end-to-end replay proof
```

TypeScript constraints:

- no `any` in application code;
- no hardcoded tactical moments;
- no duplicate manually maintained contract interfaces;
- no silent bundle-validation failures;
- no analytics recomputation in the browser.

No Python server is needed in M1. Python writes static evidence artifacts; the replay app reads those artifacts.

Go is explicitly excluded from M1. Go may be introduced only to satisfy a measured operational requirement, such as a future multi-user API gateway, job coordinator, artifact streaming service, concurrent query orchestration layer, or production deployment boundary. None of those exists in M1.

## Parser Boundary

Floodlight is the primary IDSSE/DFL parser, but it must not become the project domain model.

Use a port-and-adapter boundary:

```text
src/tqe/ports/idsse_reader.py
src/tqe/adapters/floodlight_idsse_reader.py
src/tqe/adapters/kloppy_idsse_reader.py
```

`kloppy_idsse_reader.py` is optional and exists only for sampled parity checks if useful.

The interface should look like:

```python
class IDSSEReader(Protocol):
    def read_match_metadata(self, match_id: str) -> MatchMetadata: ...
    def iter_tracking_frames(
        self,
        match_id: str,
    ) -> Iterator[ProviderTrackingFrame]: ...
    def iter_events(
        self,
        match_id: str,
    ) -> Iterator[ProviderEvent]: ...
```

Immediately convert provider objects into canonical Arrow/Parquet records:

```text
Floodlight-specific objects
-> adapter
-> canonical records
```

No Floodlight object may cross into primitive derivation, query execution, evidence generation, replay, or contract models.

Verification hierarchy:

```text
Raw XML spot checks          primary truth
Official frame/event totals  primary invariants
Floodlight parse             production ingestion
Kloppy sampled comparison    optional secondary check
```

If Floodlight exceeds the resource limit, crashes, or loses required fields, write an ADR and implement a streaming canonicalizer. Do not preemptively write a full custom XML parser.

## Data Strategy

Primary dataset: IDSSE / Sportec Open DFL Tracking and Event Data.

M1 ultimately provisions and canonicalizes exactly seven source matches:

| Match ID | Home | Away | Role |
| --- | --- | --- | --- |
| `J03WOH` | Fortuna Dusseldorf | SSV Jahn Regensburg | Gate A and calibration |
| `J03WOY` | Fortuna Dusseldorf | Hansa Rostock | Evaluation |
| `J03WPY` | Fortuna Dusseldorf | Nurnberg | Evaluation |
| `J03WQQ` | Fortuna Dusseldorf | St. Pauli | Evaluation |
| `J03WR9` | Fortuna Dusseldorf | Kaiserslautern | Evaluation |
| `J03WMX` | Koln | Bayern Munchen | Portability holdout |
| `J03WN1` | Bochum | Leverkusen | Portability holdout |

Do not process all seven matches before proving the selected stack on `J03WOH`.

Source provisioning must record:

- dataset DOI;
- article/version identifier;
- retrieval timestamp;
- source file URL;
- file name and size;
- source checksum if available;
- local SHA-256;
- license;
- paper DOI;
- fallback/mirror status if any.

No silent mirror fallback is allowed.

## Local Data Shape

Raw immutable source:

```text
data/raw/idsse/<source-version>/<match-id>/
  metadata.xml
  tracking.xml
  events.xml
```

Canonical 25 Hz store:

```text
data/canonical/v1/
  matches.parquet
  teams.parquet
  players.parquet
  orientation.parquet
  frames/match_id=<id>/period=<period>.parquet
  positions/match_id=<id>/period=<period>.parquet
  events/match_id=<id>.parquet
```

5 Hz analysis stream:

```text
data/features/v1/
  possession_segments.parquet
  team_frame_features/
  block_shift_features/
```

Evidence output:

```text
artifacts/m1/evidence/<bundle-id>/
  bundle.json
  replay.json
```

Spatial-control artifacts are optional experiments and are not part of M1 acceptance.

The 25 Hz stream is authoritative for replay. The 5 Hz stream is only for tactical scanning and must retain source 25 Hz frame IDs.

## Canonical Coordinate Contract

Physical canonical coordinates remain centered in metres:

```text
x in [-pitch_length / 2, +pitch_length / 2]
y in [-pitch_width / 2, +pitch_width / 2]
```

For a query perspective:

```text
attack_x = attack_sign_x * x
attack_y = y
```

Do not destructively rewrite physical coordinates. Store orientation separately.

## Query

Query ID: `ball_side_block_shift_v1`

Initial query file:

```text
config/queries/ball_side_block_shift.v1.yaml
```

M1 defines one query-specific model:

```python
class BallSideBlockShiftQueryV1(BaseModel):
    analysis_rate_hz: int
    minimum_possession_seconds: float

    wide_entry_fraction: float
    prior_central_fraction: float
    minimum_wide_dwell_seconds: float

    baseline_window_seconds: float
    shift_search_window_seconds: float
    minimum_shift_metres: float
    minimum_shift_persistence_seconds: float

    outcome_horizon_seconds: float
    opposite_side_fraction: float
    retained_after_switch_seconds: float
```

Initial parameters:

```yaml
schema_version: "1.0"
query_id: "ball_side_block_shift_v1"
query_version: "1.0.0"
analysis_rate_hz: 5
minimum_possession_seconds: 8.0
wide_entry_fraction: 0.60
prior_central_fraction: 0.45
minimum_wide_dwell_seconds: 1.20
baseline_window_seconds: 0.80
shift_search_window_seconds: 4.00
minimum_shift_metres: 5.00
minimum_shift_persistence_seconds: 0.60
outcome_horizon_seconds: 6.00
opposite_side_fraction: 0.35
retained_after_switch_seconds: 1.00
maximum_analysis_gap_ms: 250
minimum_outfield_players_per_team: 9
ranking_metric: "block_shift_score"
ranking_direction: "descending"
```

These are starting values, not soccer truth. They may be adjusted only during calibration on `J03WOH`. After query freeze, evaluation thresholds and semantics are immutable.

M1 must not define a generic tactical query language. A broader query intermediate representation can be considered in M2 after a second meaningfully different detector exists.

## Contract Authority

Use this contract flow:

```text
Pydantic model
-> generated JSON Schema
-> generated TypeScript types
-> runtime validation in replay app
```

CI must fail when generated files differ from checked-in files. Agents may not manually maintain parallel Python and TypeScript interfaces.

Use a small common result envelope:

```text
provenance
match
perspective
time window
classification
quality
replay reference
```

Use a query-specific evidence payload:

```text
wide-entry time
baseline centroid
anchor centroid
signed shift
persistence duration
ball trajectory
outcome timing
```

## Outcome Classes

- `SWITCHED`: ball enters the opposite side within the horizon and the attacking team retains possession afterward.
- `RETAINED_NO_SWITCH`: attacking team keeps possession through the horizon but the ball never enters the opposite-side region.
- `LOST_BEFORE_SWITCH`: possession changes before a qualifying switch.
- `STOPPAGE`: ball becomes inactive before classification. Excluded from accepted tactical results.

M1 must not call `RETAINED_NO_SWITCH` a missed opportunity.

## Promotion Gates Inside M1

M1 has three hard gates. They are not separate product milestones.

### Gate A - One-Match Viability Proof

Using `J03WOH` only:

```text
official source lock
-> Floodlight parse
-> canonical Parquet
-> raw XML parity checks
-> quality report
-> orientation validation
-> real 30-second replay
-> memory/runtime report
```

Required proof artifacts:

```text
artifacts/m1/gate-a/source-manifest.json
artifacts/m1/gate-a/canonical-summary.json
artifacts/m1/gate-a/raw-parity-report.json
artifacts/m1/gate-a/data-quality-report.json
artifacts/m1/gate-a/resource-report.json
artifacts/m1/gate-a/replay-bundle/
artifacts/m1/gate-a/replay-screenshot.png
artifacts/m1/gate-a/verification-report.json
```

Gate A passes only if:

- the official frame count matches;
- sampled raw XML coordinates match canonical rows;
- attacking orientation is correct in both halves;
- replay comes exclusively from canonical data;
- no hidden remote requests occur after provisioning;
- memory stays inside the agreed limit;
- a clean checkout can reproduce the proof.

No primitive or detector work begins until Gate A is `ACCEPTED`.

### Gate B - Corpus Proof

After Gate A is accepted, fetch and canonicalize the remaining six matches and pass corpus-wide invariants.

Gate B passes only if:

- all seven expected match IDs are source-locked;
- raw hashes and canonical schemas pass verification;
- frame/event totals match official or locked expected counts;
- no duplicate match/period/frame keys exist;
- entity identity and coordinate bounds validate;
- orientation and perspective checks pass, including Bayern as away perspective in `J03WMX` and Leverkusen as away perspective in `J03WN1`;
- corpus processing does not require loading all seven full position tables at once.

### Gate C - Tactical Proof

After Gate B is accepted:

- implement only required tactical primitives;
- calibrate the query on `J03WOH`;
- freeze query semantics and query hash;
- execute the unchanged query on `J03WOY`, `J03WPY`, `J03WQQ`, and `J03WR9`;
- generate accepted results and boundary near misses;
- generate typed replay/evidence bundles;
- build the minimal TypeScript replay proof;
- pass independent numerical and visual review.

## Required Commands

Expose exactly these verification commands:

```bash
make gate-a-verify
make gate-b-verify
make gate-c-verify
make m1-verify
```

Each command must emit a machine-readable verification report and fail with a nonzero exit code when any condition is unmet.

`make m1-verify` must run all accepted-gate verification needed to prove M1.

## Acceptance Gates

M1 is accepted only when:

- Gate A is accepted;
- Gate B is accepted;
- Gate C is accepted;
- every accepted result recomputes from canonical data;
- every accepted result has exactly one valid evidence bundle;
- replay coordinates match canonical source data within tolerance;
- minimal replay app reads generated bundles, not hardcoded moments;
- deterministic proof pack is generated;
- independent reviewer passes the protocol;
- owner records final acceptance.

Tactical result hard floor:

- 8 or more accepted real moments;
- accepted moments span at least three of four Fortuna evaluation matches;
- at least two accepted moments are `SWITCHED`;
- at least two accepted moments are `RETAINED_NO_SWITCH` or `LOST_BEFORE_SWITCH`;
- no single match contributes more than 60 percent of accepted results;
- no accepted result has quality status `fail`.

Delivery target:

- 12 to 20 accepted moments.

The delivery target is not a gate and may not justify threshold relaxation.

## Stop Conditions

If Gate A fails, do not begin primitive or detector work.

If Gate B fails, do not begin query calibration.

If the frozen query produces fewer than eight qualifying evaluation moments, mark:

```text
M1 REJECTED - QUERY NOT SUBSTANTIATED
```

That result is not permission to lower thresholds, manually curate extra moments, substitute synthetic evidence, remove inconvenient evaluation matches, or redefine `SWITCHED` after seeing results.

If raw source identity, orientation, or replay-source correspondence fails, stop before tactical claims.

## Implementation Sequence

### S0 - Lock Charter, Query Semantics, Gates, and Non-Goals

Artifacts:

- `PROJECT_CHARTER.md`
- `MILESTONES.md`
- `delivery/CONTROLLER_PROTOCOL.md`
- `delivery/m1/SPEC.md`
- `delivery/m1/status.yaml`
- `delivery/ledger.jsonl`
- ADRs and initial data/query docs

Acceptance:

- source-of-truth files exist;
- M1 is explicitly `PLANNED`;
- Gate A/B/C promotion boundaries are defined;
- no implementation or verification is overclaimed.

### S1 - Provision `J03WOH` and Establish Source Provenance

Expected modules/artifacts:

```text
scripts/data/source_lock_idsse.py
data/raw/idsse/<source-version>/J03WOH/
artifacts/m1/gate-a/source-manifest.json
docs/data/idsse.md
```

Acceptance:

- manifest records DOI, source URLs, license, sizes, hashes, and retrieval timestamp;
- only `J03WOH` is required for Gate A;
- raw files are immutable inputs;
- no remote access is required after provisioning.

### S2 - Parse `J03WOH` Through the Floodlight Adapter

Expected modules:

```text
src/tqe/ports/idsse_reader.py
src/tqe/adapters/floodlight_idsse_reader.py
src/tqe/data/provider_models.py
```

Acceptance:

- adapter emits provider-neutral records;
- no Floodlight object crosses the adapter boundary;
- resource usage is recorded;
- failures produce actionable diagnostics.

### S3 - Canonicalize and Independently Spot-Check Raw XML

Expected modules:

```text
src/tqe/data/canonical.py
src/tqe/data/schemas.py
src/tqe/data/write_parquet.py
src/tqe/verification/raw_parity.py
```

Acceptance:

- canonical tables match documented schemas;
- official frame count matches;
- deterministic raw XML samples match canonical rows;
- `artifacts/m1/gate-a/raw-parity-report.json` is emitted.

### S4 - Validate Quality and Both-Half Orientation

Expected modules:

```text
src/tqe/quality/checks.py
src/tqe/quality/orientation.py
src/tqe/quality/report.py
```

Acceptance:

- first-half and second-half attacking orientation are validated;
- quality report identifies gaps, inactive ball, player counts, and coordinate bounds;
- orientation is not inferred by assuming Fortuna is always home.

### S5 - Render a Real 30-Second Canonical-Data Replay

Expected modules:

```text
src/tqe/evidence/gate_a_replay.py
apps/replay/
```

Acceptance:

- replay bundle is generated only from canonical files;
- screenshot is generated;
- clean checkout can reproduce Gate A proof;
- `make gate-a-verify` passes.

### Gate A Independent Review

No primitive or detector work begins until this review accepts Gate A.

### S6 - Provision and Canonicalize Remaining Six Matches

Acceptance:

- all seven matches are source-locked and canonicalized;
- corpus-wide schemas and counts pass.

### S7 - Run Corpus-Wide Integrity and Portability Checks

Acceptance:

- orientation and perspective checks pass for both holdouts;
- corpus processing respects resource constraints;
- `make gate-b-verify` passes.

### Gate B Independent Review

No query calibration begins until this review accepts Gate B.

### S8 - Implement Only Required Tactical Primitives

Expected modules:

```text
src/tqe/primitives/ball_location.py
src/tqe/primitives/team_structure.py
src/tqe/primitives/block_shift.py
docs/primitives/registry.yaml
```

Acceptance:

- primitives are versioned and documented;
- goalkeeper is excluded from block centroid calculations;
- unit/property tests cover mirroring, player-order permutation, quantile width, signed shift, persistence, and gaps;
- no orphan primitive exists outside M1 needs.

### S9 - Calibrate Query on `J03WOH` and Freeze Query Hash

Expected modules:

```text
src/tqe/queries/ball_side_block_shift.py
config/queries/ball_side_block_shift.v1.yaml
docs/queries/ball-side-block-shift/calibration-log.md
```

Acceptance:

- every config revision is recorded;
- query freeze emits a stable query hash;
- evaluation matches have not been inspected before freeze.

### S10 - Execute Unchanged Query on Evaluation Corpus

Acceptance:

- frozen query runs on `J03WOY`, `J03WPY`, `J03WQQ`, and `J03WR9`;
- result-count and class-diversity hard floor passes, or M1 is rejected honestly;
- no threshold changes occur after freeze.

### S11 - Generate Accepted Results and Boundary Near Misses

Acceptance:

- accepted predicates recompute independently;
- near misses document boundary failures;
- no manual result curation occurs.

### S12 - Generate Typed Replay/Evidence Bundles

Expected modules:

```text
src/tqe/evidence/models.py
src/tqe/evidence/clip_export.py
src/tqe/evidence/bundle_export.py
schemas/contracts/tactical-result-bundle.schema.json
```

Acceptance:

- every accepted result has exactly one bundle;
- bundle IDs are deterministic;
- replay frames come from canonical 25 Hz data;
- no interpolation or fabricated missing frames are presented as source tracking;
- schema validation passes;
- edits change proof hashes.

### S13 - Build Minimal TypeScript Replay Proof

Expected modules:

```text
apps/replay/src/App.tsx
apps/replay/src/PitchCanvas.tsx
apps/replay/src/PlaybackControls.tsx
apps/replay/src/ResultList.tsx
apps/replay/src/EvidencePanel.tsx
apps/replay/src/Timeline.tsx
```

Acceptance:

- app reads generated evidence manifest;
- app has no hardcoded accepted moments;
- play, pause, scrub, and frame jump work;
- pitch renders ball, teams, possession, baseline/anchor centroids, displacement arrow, ball trail, wide-entry zone, opposite-side zone, and outcome marker;
- displayed values match `bundle.json`;
- malformed bundles show an obvious failure state;
- Playwright loads every accepted bundle without console errors;
- app states that no match video is available.

### S14 - Run Independent Numerical and Visual Review

Expected modules:

```text
src/tqe/verification/milestone_1.py
src/tqe/verification/proof_manifest.py
```

Acceptance:

- `make gate-c-verify` passes;
- `make m1-verify` passes;
- deterministic proof pack is sufficient for independent review.

## Verification Plan

Automated verification must cover:

- source identity, license, raw checksums, and match set;
- canonical frame uniqueness, time order, cadence, coordinates, entity identity, ball state, schema, and numeric validity;
- raw XML parity checks against canonical rows;
- orientation, including halftime reversal and away-team perspective;
- primitive invariants and property tests;
- query predicate recomputation separate from detector code;
- near-miss export for boundary failures;
- replay-source correspondence;
- determinism across repeated feature/query/evidence runs;
- memory/resource behavior;
- anti-reward-hacking checks.

## Deterministic Review Sample

When there are at least 12 accepted moments, the review sample contains:

- four highest-scoring accepted results;
- four closest to the passing threshold;
- four selected by deterministic seed derived from the query hash.

When there are 8 to 11 accepted moments, review every accepted moment plus enough near misses to reach 12 reviewed cases.

This prevents the team from showing only clean examples.

## Independent Review Protocol

Reviewer must not be the primary implementing agent for canonicalization, primitive derivation, detector logic, or evidence export.

Reviewer must:

- run from a fresh checkout;
- regenerate derived outputs from pinned raw data;
- inspect provenance and source lock;
- manually compare raw XML to canonical rows for sampled frames;
- inspect orientation in `J03WOH` and an away-team holdout after Gate B;
- manually recompute selected primitive values after Gate C;
- inspect the deterministic review sample;
- inspect at least five near misses when available;
- confirm replay app reads generated bundles and has no hardcoded moments.

Blocking feedback includes checksum mismatch, wrong match/team identity, incorrect orientation, replay mismatch, goalkeeper in block centroid, post-freeze threshold changes, insufficient result diversity, wrong outcome classification, synthetic evidence, hardcoded UI moments, manual result deletion, or inability to regenerate proof.

## Controller Consultation Gates

The controller must use `delivery/CONTROLLER_PROTOCOL.md` and consult the context-rich ChatGPT conversation at:

- `G0_SPEC_FREEZE`;
- `G1_DATA_SOURCE_LOCK`;
- `G2_QUERY_FREEZE`;
- `G3_PROOF_PACK_REVIEW`;
- `G4_NEXT_MILESTONE_SELECTION`.

Each consultation packet must be self-contained and evidence-indexed. ChatGPT advice is advisory; accepted changes must be written into this spec or a follow-up ADR before implementation agents rely on them.

The G0 spec-freeze consultation has been integrated into this version. M1 remains `PLANNED`; no implementation, verification, review, or owner acceptance has started.
