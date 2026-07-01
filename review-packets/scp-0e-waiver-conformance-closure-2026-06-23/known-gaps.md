# Known Gaps

## requires_full_repo

What is missing:

This packet does not include the full repository, dependency environment, canonical data, virtual environment, or all generated caches.

Why it matters:

An external reviewer can inspect evidence but cannot independently rerun `make scp-0-verify` or `make test` from only this zip.

Default boundary:

Treat the packet as inspection evidence, not a standalone reproducible package.

Next action:

If a standalone package is required, build a separate reproducible bundle with environment bootstrapping and dataset constraints.

## not_in_scope

What is missing:

SCP-1 algebra implementation is not included.

Why it matters:

SCP-0E can only unblock SCP-1; it cannot prove SCP-1 behavior.

Default boundary:

After external approval, SCP-1 should start as a narrow compiler-to-existing-runtime milestone.

Next action:

Use High-Bypass Completed Pass and Ball-Side Block Shift as dual pilots for SCP-1.

## not_in_scope

What is missing:

Generated artifact publication is not a fully atomic release transaction across every possible I/O failure.

Why it matters:

The previous validation-failure publish safety remains intact, but mid-move filesystem failures could still be hardened later.

Default boundary:

Do not treat SCP-0E as a complete artifact deployment-system redesign.

Next action:

Consider versioned generation directories plus atomic pointer/symlink replacement in a later infrastructure hardening slice.

## not_in_scope

What is missing:

Older semantic cleanup around measurement-versus-judgement naming, especially `ball_lateral_fraction`, is not solved here.

Why it matters:

SCP-0E focuses on governance mechanics, not capability ontology refinement.

Default boundary:

Do not hold SCP-0E on this issue; carry it into SCP-1 or later semantic cleanup.

