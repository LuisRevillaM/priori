# Work Packet F2-4 — Lines Family Extraction

Issued: 2026-07-03 by the project director. Third family relocation of ADR
0012 §3, following the accepted F2-2/F2-3 template exactly (read both
REVIEW/REPORT files for the pattern; all their rules apply verbatim:
zero-drift pure relocation, registry-only wiring for executor.py, fences,
full-suite table, the eight pinned gates, clean shared tree with the branch
ref as sole output).

Branch `packet/f2-4` off the frontier (tip `81b7580` or later).

## Scope

Move the lines-family node functions from `executor.py` to
`src/tqe/runtime/capabilities/lines_family.py`:

- the `defensive_line_model` / multi-line-model node functions
- `relative_position_to_observed_line` node function(s)
- `controlled_pass_crosses_observed_line` (controlled line break) node
  function(s)
- line-related helpers used ONLY by this family (per-family helper rule as
  before; shared ones stay and get listed)

Direct importers outside executor.py (verification modules, tests) may
update their import paths — the F2-3 precedent — but executor.py itself
remains registry-only.

## Deliverables

Branch `packet/f2-4`; executor.py line count before/after; shared-helpers
list; improvement-candidates list (NOT implemented); full-suite table;
pinned-gate proof; `delivery/packets/F2-4-REPORT.md`.
