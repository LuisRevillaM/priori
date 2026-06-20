# ADR 0003 - Controller Uses ChatGPT at Significant Milestone Gates

Date: 2026-06-19

Status: Accepted for planning

## Context

The user wants a durable loop where the controller packages significant milestone state for the context-rich ChatGPT conversation, asks for review or next-step guidance, and then integrates the feedback into local source-of-truth files.

## Decision

The controller must consult ChatGPT at the gates defined in `delivery/CONTROLLER_PROTOCOL.md`:

- `G0_SPEC_FREEZE`
- `G1_DATA_SOURCE_LOCK`
- `G2_QUERY_FREEZE`
- `G3_PROOF_PACK_REVIEW`
- `G4_NEXT_MILESTONE_SELECTION`

Each consultation must use a self-contained, evidence-indexed packet. `G1_DATA_SOURCE_LOCK` is tied to Gate A proof artifacts, not to the full seven-match corpus. The controller remains accountable for final judgment and must write accepted feedback into repo docs before agents rely on it.

## Alternatives Considered

- Consult after every small implementation step.
- Consult only after M1 is complete.
- Treat ChatGPT approval as milestone acceptance.

## Consequences

- The advisor loop is useful without becoming a bottleneck.
- Significant decisions get external context review.
- ChatGPT feedback does not replace automated verification, independent review, or owner acceptance.
