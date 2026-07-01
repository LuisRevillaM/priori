# Known Gaps

## requires_full_repo

What is missing:

This packet does not include the full repository, dependency environment, canonical data, virtual environment, or all generated caches.

Why it matters:

The reviewer can inspect evidence but cannot rerun `make scp-0-verify` or `make test` from this zip alone.

Default boundary:

Treat this as an inspection packet.

Next action:

Use the source repo if independent command execution is required.

## not_in_scope

What is missing:

A pinned product recipe baseline artifact.

Why it matters:

Product recipe comparison is not independent frozen product-recipe parity yet.

Default boundary:

The parity report now explicitly labels this as current-runtime alignment, which is the selected closure option from the external review.

Next action:

Create a pinned product recipe baseline only when product recipe parity needs to be independent of the current runtime manifest.

## not_in_scope

What is missing:

SCP-1 algebra/compiler behavior.

Why it matters:

This patch can only close SCP-0E. It does not prove a semantic expression compiler.

Default boundary:

SCP-1 remains pending external approval of this patch.

Next action:

If accepted, begin SCP-1 with SemanticExpression -> existing TacticalQueryDocument -> existing binder/runtime.

