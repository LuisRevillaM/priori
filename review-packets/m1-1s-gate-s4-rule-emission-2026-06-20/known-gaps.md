# Known Gaps

## Second Tactical Family Not Proven

classification: `not_in_scope`

What is missing: A second dissimilar tactical pattern executing without special cases.

Why it matters: This is the next architecture proof that determines whether the system generalizes beyond the M1/corridor family.

Default boundary: S4 proves generic result emission for the experimental corridor plan only.

Next action: Proceed to the second tactical family only after S4 review.

## UI And Hermes Not Proven

classification: `not_in_scope`

What is missing: Natural-language query drafting, Hermes behavior, replay UI, visual polish, and final demo UX.

Why it matters: The project’s demo still needs these later layers.

Default boundary: Treat this packet as backend runtime proof only.

Next action: Review and accept/reject S4 before starting UI/Hermes work.

## Packet Is Not Standalone Reproducible

classification: `requires_full_repo`

What is missing: Full repo, dependencies, canonical data, raw IDSSE data, and virtual environment.

Why it matters: The external reviewer can inspect source and reports but cannot rerun the proof from the packet alone.

Default boundary: Claims are backed by included source, patch, reports, and command output.

Next action: If independent execution is required, create a separate reproducible bundle.

## Experimental Plan Is Still Experimental

classification: `not_in_scope`

What is missing: Product approval, semantic gold-set validation, and analyst acceptance for the corridor detector.

Why it matters: S4 proves architecture, not detector-product correctness.

Default boundary: Do not present the corridor plan as an approved tactical product claim.

Next action: Keep product semantics review for later milestones.
