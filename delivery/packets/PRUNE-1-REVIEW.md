# PRUNE-1 Review: ACCEPTED

Reviewed 2026-07-06 at 601ee90. Inventory-first discipline followed
exactly: 42 classified rows committed before any removal; quarantines
moved under docs/archive/prune-1/ with provenance headers; the stale
top-level state docs retired from the root; the pre-operator-era
architecture tome archived and the README rewritten to point at the
real sources of truth (registry, runtime, ADRs, packet evidence). CI
change verified comment-only. Untracked root files inventoried with
recommendations, untouched. Director's suite green; executor's 561
green. The old system no longer speaks for the new one.

Ops note for the record: the director's original accept-and-dispatch
chain hung for ~4 hours on the director's own malformed shell (a bare
`cat >>` reading stdin), caught during the owner's
what-would-you-fix-yourself check-in, killed, and redone in plain
steps. Ceremony must be simple enough to fail loudly.
