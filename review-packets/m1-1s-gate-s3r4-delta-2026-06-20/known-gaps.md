# Known Gaps

## S4 Not Implemented

classification: `not_in_scope`

What is missing: S4 rule-driven result emission is not part of this packet.

Why it matters: S3R4 is a pre-S4 correctness gate, not the next milestone itself.

Default boundary: Treat S4 as blocked until S3R4 is externally reviewed or accepted by the controller.

Next action: Review this packet, then proceed to S4 only if no blocking S3R4 issues remain.

## Packet Is Not Standalone Reproducible

classification: `requires_full_repo`

What is missing: Full source tree, dependencies, virtual environment, datasets, and Makefile context.

Why it matters: External reviewers can inspect but cannot rerun validation from the archive alone.

Default boundary: Claims are supported by included diffs, source excerpts, and generated reports, not by standalone execution.

Next action: If standalone reproduction is required, create a separate reproducible package with dependency and fixture minimization.

## UI And Agent UX Are Not Proven

classification: `not_in_scope`

What is missing: No UI, visualization, animation, or natural-language query authoring proof is included.

Why it matters: The project’s final demo still depends on those later milestones.

Default boundary: This packet only claims runtime/temporal correctness for the S3R4 gate.

Next action: Address UI and agent UX in their own milestone packets.

## External Review Pending

classification: `requires_human_decision`

What is missing: Independent reviewer decision on S3R4.

Why it matters: Prior milestone practice requires external review before moving into the next high-risk implementation phase.

Default boundary: Controller accepted S3R4 locally, but S4 should wait for external review if following the established protocol strictly.

Next action: Send this packet to the external reviewer and request approve/reject with blocking findings.
