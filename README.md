# Priori Tactical Query Workbench

Priori is a tactical query engine for football tracking data. Hermes authors bounded tactical definitions, the deterministic runtime measures real match coordinates over time, and the Workbench replays evidence-backed moments for human inspection.

## Architecture Source Of Truth

Start here:

- [Tactical Query Architecture And Standard Library](docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md)

Core idea:

```text
We are not adding more canned queries first.
We are expanding the typed football vocabulary from which Hermes can construct queries.
```

That document defines the layer model, claim boundaries, runtime object model, Hermes/host authority split, current implemented capabilities, and the proposed tactical standard-library expansion.

## Current Product Claim

The deployed Workbench can execute reviewed recipes and one verified Hermes-authored experimental tactical composition over real canonical match data, with deterministic provenance, evidence aliases, predicate traces, cache behavior, and coordinate replay.

This does not claim arbitrary tactical authorship across the full football domain yet. The next expansion is the tactical standard library for line-break/support concepts.

## Key References

- [Current State](CURRENT_STATE.md)
- [Project Charter](PROJECT_CHARTER.md)
- [Milestones](MILESTONES.md)
- [Render Deployment Notes](docs/DEPLOY_RENDER.md)
- [Workbench Alpha App](apps/workbench-alpha/)

## Useful Commands

```bash
make n1d-verify
make n1d1-verify
make n1i-verify
npm --prefix apps/workbench-alpha run test:acceptance
```

Some verification targets require generated artifacts and canonical data already present in the workspace.
