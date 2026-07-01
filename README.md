# Priori

Priori is a research prototype for evidence-backed football tactical queries over
tracking and event data. The core idea is simple:

```text
A tactical claim should be compiled into explicit, typed conditions,
measured over real match coordinates, and shown with enough evidence that a
human can inspect whether the claim actually holds.
```

The current repo is not a polished general-purpose product or SDK. It is a
working research/codebase history containing:

- a deterministic Python runtime for tactical measurements;
- a React/Vite workbench and coach-facing preview surface;
- generated contracts, semantic-registry artifacts, and replay payloads;
- verification scripts and review packets from several proof phases;
- deployment plumbing for the current Render alpha;
- historical artifacts kept deliberately so claims can be audited.

## Current Status

Current active branch for the public alpha work:

```text
codex/afl08-passport-loop
```

Live alpha surfaces:

- Coach preview: `https://priori-integrated-alpha.onrender.com/`
- Case study: `https://priori-integrated-alpha.onrender.com/case-study`
- Research workbench: `https://priori-integrated-alpha.onrender.com/workbench`

The case study is the most readable current entry point. It explains the main
product lesson from the latest work: a primitive existing in the catalog is not
the same as a coach-facing meaning being proven. Coach-facing claims require a
compound of geometric, relational, control, possession, and context conditions,
and the surface must not say more than that compound proves.

## What Is Real Today

The repository currently supports these bounded claims:

- It canonicalizes a small public football tracking/event corpus.
- It runs deterministic tactical measurements over real coordinates.
- It emits typed PASS / FAIL / UNKNOWN outcomes instead of silently collapsing
  missing or insufficient evidence into false.
- It contains a growing primitive library: defensive lines, relative position,
  controlled line breaks, support arrival, local number, lane occupancy, carry
  episodes, acceleration, set-piece structure, off-ball runs, marking, generated
  space regions, cover shadows, team pressure, and high-bypass pass checks.
- It can render evidence-backed replay clips in the Workbench and coach preview.
- It has a bounded natural-language to meaning to contract path for the current
  preview scope.
- It has verification targets for the main gates and primitive expansions.

The current product surface is intentionally narrow. It is strongest where the
query is specific and evidence-backed. It is not an arbitrary football analyst.

## What This Does Not Claim

The repo does not currently prove or provide:

- player intent;
- tactical causation;
- coaching quality or optimality judgments;
- expected goals, pass-completion probability, or learned value models;
- video understanding;
- body orientation, scanning, or gaze;
- complete football ontology coverage;
- reliable interpretation of arbitrary free-form tactical language.

When the system says a player was under observed pressure, it means geometric
pressure conditions were met. It does not mean a coordinated pressing trap was
intended. When it says a pass bypassed opponents, it means the measured bypass
geometry held. It does not by itself mean the pass was valuable, successful, or
coach-approved. Those stronger meanings require additional checks.

## Data Boundary

The accepted match evidence source is the public IDSSE / Sportec Open DFL
Tracking and Event Data corpus.

See [docs/data/idsse.md](docs/data/idsse.md) for source locks and match details.

Important details:

- 7 complete matches;
- all players and ball;
- 25 Hz tracking;
- synchronized event data;
- German Bundesliga / 2. Bundesliga context;
- Figshare article `28196177`;
- article DOI `10.6084/m9.figshare.28196177.v1`;
- license reported as CC BY 4.0.

This repo uses coordinate and event data only. It does not contain or process
match video. Raw and canonical data can be large, and a fresh clone should not
be assumed to have every local `data/` artifact available.

## Repository Map

```text
apps/workbench-alpha/        React/Vite alpha UI, coach preview, case study, workbench
apps/replay-proof/           Older replay proof app
src/tqe/                     Python tactical query/evidence package
src/tqe/runtime/             Runtime IR, binder, executor, catalog, primitives
src/tqe/semantic_compiler/   Meaning-to-contract lowering and gap types
src/tqe/semantic_registry/   Semantic registry generation/runtime manifest code
src/tqe/verification/        Gate and primitive verification modules
scripts/                     Data, compiler, coverage, and workbench scripts
config/                      Query plans, deployment config, evaluation config
docs/                        Architecture, data, audits, reviews, primitive notes
delivery/                    Phase ledgers and handoff artifacts
generated/                   Generated contracts, semantic outputs, replay payloads
artifacts/                   Verification outputs and historical evidence
review-packets/              External/internal review bundles from proof phases
semantic-registry/           Atlas and semantic schemas
tests/                       Python and frontend-oriented tests
```

The generated, artifact, delivery, and review-packet directories are noisy on
purpose. They are part of the audit trail for how the system reached its current
claim boundaries.

## How The System Is Layered

The architecture source of truth is:

- [docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md](docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md)

The short version:

```text
raw source data
  -> canonical match state
  -> typed runtime values
  -> measurements and relations
  -> predicates and temporal operators
  -> evidence-backed result emission
  -> replay/workbench/product surface
```

The important invariant is that the product surface should be the last mile of
the same evidence discipline, not a place where stronger claims are invented.
Pixels and prose are treated as claims too.

## History And Context

The project has gone through several proof phases. The names below reflect the
local milestone/gate language preserved in this repo.

### M1: Real-data evidence spine

The first milestone locked the IDSSE/DFL data source, canonicalized match state,
validated raw/canonical parity, and built deterministic replay evidence over
real tracking coordinates.

### M1.1: Typed deterministic runtime

The next phase added a typed IR, binder, executor, runtime artifacts, predicate
traces, caching behavior, and verification gates. This moved the project from
replay proof toward executable tactical query plans.

### M1.2: Workbench and host boundary

The Workbench/Hermes path established a bounded host-controlled execution model:
the host owns tools, scope, confirmation, provenance, cache, and replay. Current
cloud alpha deployment keeps the Hermes path disabled by flag for the C0 surface.

### SCP/SCL: Meaning, contracts, and answer-leak prevention

The semantic compiler work separated football meaning from downstream search.
The design goal was to prevent answer leakage: natural-language or meaning
layers should describe football meaning, while lower layers independently map
that meaning to contracts, executable plans, or typed gaps.

The current preview scope is deliberately small, but the important architectural
pattern is present: vocabulary-blind interpretation, generated contracts, blind
search, and honest outcomes when the system cannot express or find something.

### AFL/passport/substrate expansion

The primitive library grew through repeated verifier-backed additions: defensive
line geometry, relative position, controlled line breaks, support arrival, lane
occupancy, acceleration, set-piece structure, off-ball runs, marking, space
generation, cover-shadow, team-press, carry, and high-bypass pass checks.

The key lesson was that each primitive must have a narrow claim boundary. For
example, observed convergence around a carrier is not the same as a coordinated
pressing scheme.

### Product case study: high-bypass and claim backing

The latest product work exposed a harder layer: even if a primitive is truthful,
coach-facing language can still overclaim. A pass can geometrically bypass
opponents while control never settles, or while the event came from a restart
rather than open play.

That led to product-layer gates for clean control, open-play context, possession
retention, and claim-backing. The case study is now the clearest explanation of
that history.

## Current Product Surfaces

`apps/workbench-alpha` contains the active UI.

Routes:

```text
/             Coach-facing preview
/case-study   Narrative case study with replay examples
/moment-zero  Earlier single-moment design prototype
/workbench    Dense research workbench
```

The case study currently contrasts:

- geometric/kinematic primitives such as team pressure, cover shadow, and carry;
- the compounded high-bypass case, where coach-facing meaning requires multiple
  layers to all hold at once.

## Running Locally

Python setup:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
```

Frontend setup:

```bash
npm --prefix apps/workbench-alpha install
npm --prefix apps/workbench-alpha run dev
```

The dev server defaults to:

```text
http://127.0.0.1:5174
```

Build the frontend:

```bash
PYTHON=.venv/bin/python npm --prefix apps/workbench-alpha run build
```

Run frontend checks:

```bash
npm --prefix apps/workbench-alpha run test:unit
npm --prefix apps/workbench-alpha run test:acceptance
```

Many Python verification targets require local canonical data and generated
artifacts. Examples:

```bash
make m1-verify
make m1-1-verify
make m1-2-verify
make afl-passport-verify
make afl-team-press-verify
make scl0-verify
make scl1-verify
make scl-nl0-verify
```

If a target fails because `data/` is missing, provision the public IDSSE/DFL
corpus first or use an environment where the canonical data bundle is mounted.

## Deployment

Render deployment notes:

- [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md)

The current Render alpha is a single Docker web service with:

- React Workbench build;
- Python host service;
- deterministic runtime;
- persistent disk for canonical/raw data bundle;
- readiness endpoints at `/healthz` and `/readyz`.

The cloud image intentionally excludes the large local `data/` directory.
Runtime data is provisioned separately to Render storage.

## How To Read This Repo

Recommended path for a new reader:

1. Read this README.
2. Read the case study — canonical text at [docs/CASE_STUDY.md](docs/CASE_STUDY.md),
   live interactive version at `/case-study`.
3. Read [docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md](docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md).
4. Read [docs/data/idsse.md](docs/data/idsse.md).
5. Inspect `src/tqe/runtime/` for the executable primitive/runtime layer.
6. Inspect `src/tqe/verification/` for the gates that make the claims testable.
7. Inspect `apps/workbench-alpha/src/` for the coach/workbench surfaces.

The repo is intentionally transparent about partial work and prior mistakes.
Some artifacts are historical rather than current product code. The safest way
to evaluate any claim is to find the verification target or replay evidence that
backs it.
