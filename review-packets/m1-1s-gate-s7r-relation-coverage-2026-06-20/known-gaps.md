# Known Gaps

## requires_full_repo: Make Target Reproduction

What is missing: canonical data, Python environment, full package layout, and Make target context.

Why it matters: reviewers cannot rerun `make m1-1-gate-s7r-verify` from this packet alone.

Default boundary: treat this packet as inspection evidence, not independent reproduction.

Next action: rerun commands inside the full repo if direct reproduction is required.

## not_in_scope: M1.2 Hermes

What is missing: Hermes natural-language drafting, query authoring loop, feedback loop, and agent-facing capability catalog UX.

Why it matters: S7R only unblocks the runtime semantics needed before Hermes; it does not implement Hermes.

Default boundary: M1.2 remains blocked pending external S7R approval.

Next action: after approval, begin the Hermes draft-execute-inspect-revise loop.

## not_in_scope: Frontend And Visualization

What is missing: analyst UI, animation, replay visualization, and delightful demo surface.

Why it matters: the project demo still needs a frontend milestone after backend/runtime semantics are stable.

Default boundary: no UI claim is made by this packet.

Next action: schedule UI work after Hermes/runtime milestones are accepted.

## not_in_scope: Priori Or Video Integration

What is missing: Priori SDK/API access and any video playback integration.

Why it matters: the demo is intentionally independent and dataset-driven.

Default boundary: no Priori or video integration claim is made.

Next action: none for S7R.

## unknown: External Reviewer Acceptance

What is missing: independent external approval of S7R.

Why it matters: M1.2 should not start until this focused corrective gate is accepted or further required changes are integrated.

Default boundary: `delivery/m1.1/status.yaml` keeps M1.2 blocked pending external review.

Next action: send this packet to the external reviewer.
