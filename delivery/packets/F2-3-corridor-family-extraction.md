# Work Packet F2-3 — Corridor/Destination Family Extraction

Issued: 2026-07-03 by the project director. Second family relocation of ADR
0012 §3, following the accepted F2-2 template exactly.

## Ground rules

Identical to F2-2 (read delivery/packets/F2-2-pass-family-extraction.md and
its REVIEW/REPORT for the accepted pattern): branch `packet/f2-3` off the
frontier (tip `e16b8a2` or later); commit locally, do NOT push; zero-drift
bar (pure relocation, no improvements — list them instead); catalog and all
evidence directories fenced; full-suite table plus the same eight pinned
gates as drift proof.

NEW channel rule (from F2-2's operational friction): leave the shared
working tree exactly as you found it — clean on the frontier branch. Your
packet branch REF is your only output; if index locks prevent normal
checkout, build the ref with plumbing but do not leave loose working-tree
copies behind.

## Scope

Move the corridor/destination node functions from `executor.py` to
`src/tqe/runtime/capabilities/corridor_family.py`:

- the `geometric_progressive_corridor` and
  `geometric_progressive_corridor_from_anchor_set` node functions
- `relation_destination_entry` and `relation_destination_entry_classification`
  node functions
- ball-entry/destination evaluation helpers used ONLY by this family
  (helpers shared with other families stay; list them in the report)

Same rules as F2-2: exact signatures and bodies, registry-only wiring,
boundary allowlist moves-or-shrinks, import-boundary test extended to the
new module.

## Deliverables

Branch `packet/f2-3`; executor.py line count before/after; shared-helpers
list; improvement-candidates list (NOT implemented); full-suite table;
pinned-gate proof; `delivery/packets/F2-3-REPORT.md`.
