# Controller Protocol

This file codifies how the controller agent should run this project without relying on chat memory.

## Governing Rule

Do not treat `planned`, `implemented`, `verified`, `reviewed`, `deployed`, and `accepted` as the same state. Advance state only when a ledger entry points to evidence.

## Milestone Loop

For each milestone:

1. Confirm the source-of-truth spec, success criteria, non-goals, side effects, and stop conditions.
2. Assign bounded implementation slices with their own acceptance criteria.
3. Require each implementing agent to produce evidence, not just a completion claim.
4. Self-verify by rerunning checks or inspecting artifacts directly.
5. Use independent review for meaningful architecture, data, query, replay, or product-boundary changes.
6. Integrate accepted feedback and record rejected feedback with reasons.
7. Update `delivery/ledger.jsonl`, milestone status, learnings, and known issues.
8. Ask the owner for acceptance only after proof and review are complete.

## ChatGPT Consultation Loop

The context-rich ChatGPT conversation is an external advisor, not the source of truth and not an acceptance authority. The controller should consult it at significant boundary points where its broader background can improve the plan, catch weak assumptions, or help choose the next slice.

Consultation is required at these gates:

- `G0_SPEC_FREEZE`: before an implementation team treats a milestone spec as executable.
- `G1_DATA_SOURCE_LOCK`: after Gate A source-lock, raw/canonical parity, data-quality, orientation, resource, and replay proof artifacts exist, before remaining-corpus work depends on them.
- `G2_QUERY_FREEZE`: after calibration on the allowed calibration match, before any evaluation-set replay inspection.
- `G3_PROOF_PACK_REVIEW`: after automated proof artifacts exist, before final independent-review adjudication.
- `G4_NEXT_MILESTONE_SELECTION`: after M1 acceptance or rejection, before detailed M2 spec authoring.

Consultation is optional for small implementation fixes, test repairs, formatting, or issues that do not change milestone semantics.

## Consultation Packet Format

Every packet pasted into ChatGPT must be self-contained:

```text
Milestone/gate:
Decision requested:
Current claim:
Explicit non-claims:
Spec paths:
Implementation paths:
Evidence paths:
Ledger status:
Known issues:
What changed since the previous consultation:
Questions for advisor:
What would count as blocking feedback:
```

The packet must not require chat memory. It should include enough detail for the advisor to review the current state, but it must not include secrets, credentials, private tokens, or unrelated logs.

## Feedback Handling

After each consultation:

- summarize the advisor's concrete recommendations in `docs/learnings/`;
- update the spec only when the recommendation improves correctness, verification, scope control, or product clarity;
- record rejected recommendations with a short reason;
- do not advance a milestone state solely because the advisor agreed.

## Anti-Reward-Hacking Duties

The controller must block acceptance when:

- proof depends on fake, fixture, synthetic, or manually edited accepted moments;
- primitive or detector work begins before Gate A acceptance;
- query thresholds changed after evaluation started;
- only clean-looking examples were selected for review;
- screenshots are presented without machine-traceable data;
- replay data cannot be traced to raw source hashes;
- the UI hardcodes moments rather than reading generated bundles;
- claims exceed implemented evidence.
