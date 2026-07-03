# Work Packet F2-5 — Off-Ball Family Extraction

Issued: 2026-07-03 by the project director. Fourth family relocation of ADR
0012 §3, accepted F2-2/3/4 template applies verbatim (zero-drift pure
relocation, registry-only executor wiring, fences, full-suite table, eight
pinned gates, clean shared tree, branch ref as sole output).

Branch `packet/f2-5` off the frontier (tip `a9b4dcd` or later).

## Backfill obligation first

Your F2-4 run was externally interrupted after the code commit and before
the report: write `delivery/packets/F2-4-REPORT.md` retroactively (scope
outcome, relocated function list, the line counts 9,884 -> 9,183, and note
that the director ran the verification independently due to the
interruption) and commit it on THIS packet's branch.

## Scope

Move the off-ball family node functions from `executor.py` to
`src/tqe/runtime/capabilities/offball_family.py`:

- support-arrival node function(s)
- time-to-arrival node function(s)
- marking / marking-proximity node function(s)
- off-ball-run and run-type node function(s)
- family-only helpers move; shared helpers stay and get listed

## Deliverables

Branch `packet/f2-5`; F2-4 report backfill; executor.py line count
before/after; shared-helpers and improvement-candidates lists; full-suite
table; pinned-gate proof; `delivery/packets/F2-5-REPORT.md`.
