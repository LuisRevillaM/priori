# Work Packet R1-C: Era Checkpoint — one sweep, one tree, twelve claims

**Era**: R1 close-out (post R1-5 acceptance, ledger at 12)
**Branch**: `packet/r1-c` off the frontier
**Executor ground rules**: commit locally in stages, never push; report file
`delivery/packets/R1-C-REPORT.md` created WITH the first item commit and
updated per item; full-suite table on the committed tree in the report or
no review happens.

**Fences (do not touch)**:
- `generated/coverage-map.json` / `.csv` — the ledger flips by the
  director's hand only (ADR 0013, principle 17). R1-C changes HOW the
  counter is computed, never its value.
- `semantic-registry/atlas/` — Priori's raw atlas is never mutated.
- `artifacts/autonomous/` — frozen G0 candidate exhibit.
- `delivery/packets/r1-5-copy-proof/`, `delivery/packets/r1-5-population-audit/`
  — sealed evidence of the closed era.
- No freezes, no re-pins — those are governance (director's, at merge).

## Headline risk (the one argument this packet must win)

The era's twelve compiler_reachable claims were each proven by a live
search at their own acceptance moment, on five different trees. R1-C
proves they all hold **simultaneously, in one sweep, on one committed
tree** — and hardens the KPI counter so its number can never drift from
the semantics that earned it.

## Scope

### C1. The unified sweep
Run the compiler search across ALL era targets in a single invocation
(all five `config/compiler-reachability/r1-*-targets.v0.json` files plus
the pre-era `search-targets.v0.json`, both team perspectives where the
target declares them). Deliverable: one search run whose row ledger
carries every era row, committed as `delivery/packets/r1-c-sweep/`
(report + row-ledger + per-row certified plans), with a summary table in
the report: target, rows searched, rows compiler_reachable, correspondence
status. Expected: 12/12 with correspondence PASS; any deviation is a
finding to report, not to fix.

### C2. KPI semantic-correspondence hardening
`scripts/coverage_map/compiler_search_reachability.py:3866`
(`update_coverage_rows`): today the function trusts its caller's results
list. Harden so a row can only move to `compiler_reachable` when its
result row carries `correspondence == "PASS"` (or the field's actual
name — derive from the certified-plan schema, do not invent) AND a
certified plan reference. A result lacking either must raise, not skip —
tri-state discipline: a missing check is UNKNOWN and UNKNOWN cannot flip
a ledger row. Add unit tests proving both rejection paths (mutation
standard: break the guard, watch the named test fail).

### C3. Riders from the R1-5 closing round (both mechanical)
- `tests/test_r1_5_typed_join.py` both-teams suite test: add the
  `continuity_team_role == anchor_team_role` assertion line per row, so
  the R1-4 canon bug is caught at composition level, not just unit level.
- Commit the full-population audit generator as
  `scripts/audits/r1_5_population_audit.py` (the tool that produced
  `delivery/packets/r1-5-population-audit/audit.json`), with a smoke test
  that regenerates the committed audit.md summary numbers byte-identically
  from the committed audit.json.

### C4. Latency: stop hashing 182MB per gate run
Introduce `data/manifest.json` (or the project's naming) — file path,
size, sha256 for each raw data file, itself hash-pinned — and switch
gate-time integrity checks to verify the manifest's own hash plus file
sizes, with full re-hash behind an explicit `TQE_DEEP_VERIFY=1`. The
default gate path must not read hundreds of MB to prove nothing changed.
Measure and report before/after wall time for `make scp-0-verify`.

## Required tests
House standard: mutation-verified where a guard is claimed (C2, C3).
Full suite (`make test`) green on the committed tree, every failure
enumerated and attributed.

## Expected legitimate ripples
Gate wall-times change (C4) — report numbers. The sweep's search-run
directory replaces the last single-target run under
`generated/compiler-search-v0/` per the established per-run pattern —
the durable copy lives in `delivery/packets/r1-c-sweep/`.

## Explicitly OUT of scope (debt ledger, disposition at review)
- Fabricated-trace deletion + opposite-corridor plan retirement + gates
  E/S7 coupling — design-bearing, its own packet after R1-C.
- Stale R3/S2 gate pins (119/747) re-pin — governance, director at merge.
- FrameSignal sparse-signal trap; rule-id vocabulary registration —
  carried, visible, next era's entry work.
- Parallel gate execution in Makefile + persistent node cache (latency
  items 2/4) — carried unless C4 lands early with room.

## Deliverables
`delivery/packets/R1-C-REPORT.md` (stage-committed), the sweep evidence
directory, the hardened counter + tests, the two riders, the manifest +
timing table. Nothing pushed.
