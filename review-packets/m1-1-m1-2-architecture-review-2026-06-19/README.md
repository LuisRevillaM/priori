# External Review Packet - M1.1 / M1.2 Architecture Split

Packet type: `inspection_packet_only`

Date: 2026-06-19

## What This Packet Is

This packet is for an external planning/review agent that does not have access to the repository. It packages the proposed post-M1 architecture split into:

- M1.1 - Composable Tactical Query Runtime
- M1.2 - Grounded Tactical Query Workshop

The main artifact is a paste-ready mega prompt:

- `EXTERNAL_REVIEW_PROMPT.md`

## Review Scope

Ask the reviewer to assess whether this split is the right architecture and sequencing before implementation begins, with particular attention to downstream consequences for M2-M6.

## What Is Real

- M1 is controller-verified end to end in the local repo.
- The roadmap and delivery docs now include M1.1 and M1.2 as planned milestones.
- The M1.1/M1.2 specs are planning artifacts only.

## What Is Not Proven

- M1.1 implementation has not started.
- M1.2 implementation has not started.
- No independent reviewer has approved the split yet.
- This packet is not reproducible without the full repo and local data artifacts.

## Review Map

1. Start with `EXTERNAL_REVIEW_PROMPT.md`.
2. Use `source-excerpts/milestone-spec-excerpts.md` if the reviewer wants the exact spec text in compact form.
3. Use `known-gaps.md` to understand what remains unproven.
4. Use `next-steps.md` for the intended post-review action.

## Validation

See `validation-output.md`. Planning files were checked for YAML/JSONL parseability and whitespace issues. No implementation tests were run for this packet because this is a planning review packet.
