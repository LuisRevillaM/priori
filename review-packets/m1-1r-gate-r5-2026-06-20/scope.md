# Scope

## Packet Assumptions

- The target is M1.1R Gate R5, not the whole product roadmap.
- The external reviewer does not have repo access.
- The packet should support an architecture review and downstream readiness decision, not rerun the whole system standalone.
- The desired decision is one of: `APPROVE`, `APPROVE_WITH_REQUIRED_CHANGES`, or `REJECT`.

## Commit And Branch

- Branch: `codex/m1-1-s1-ir-binder`
- Commit: `12eb91a8d6940cb057efdc2753a2e59f1e847e53`
- Commit title: `Implement M1.1R Gate R5 architecture proof`
- Worktree at packet creation: clean.

## Source Of Truth

- Corrective spec: `source-excerpts/delivery/m1.1/CORRECTIVE_SPEC.md`
- M1.1 state: `source-excerpts/delivery/m1.1/status.yaml`
- Project state: `source-excerpts/delivery/status.yaml`
- Ledger: `source-excerpts/delivery/ledger.jsonl`

## Acceptance Criteria Under Review

From Gate R5:

- renaming all node IDs while preserving references leaves results unchanged;
- removing a required dependency fails binding;
- every advertised capability executes successfully in a minimal valid plan;
- changing classification rules changes classification behavior;
- changing requested evidence changes result projection;
- unknown policy changes behavior;
- generic executor source contains none of the approved recipe's predicate IDs;
- a second simple plan with no block-shift fields executes successfully;
- deleting generated caches still reproduces results from canonical data;
- corrected runtime still reproduces M1 exactly.

## Out Of Scope

- M1.2 implementation.
- Hermes natural-language query drafting.
- Saved detectors and analyst feedback loops.
- Delightful analyst UI.
- Priori integration.
- Match video.
- Production deployment.
