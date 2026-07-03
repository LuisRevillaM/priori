# Work Packet F2-2 — Pass-Family Extraction

Issued: 2026-07-03 by the project director. First family extraction of ADR
0012 §3. Pattern-setter: this packet's shape is the template for every
family that follows, so cleanliness here compounds.

## Ground rules

- Branch `packet/f2-2` off `codex/afl08-passport-loop` (tip `630dcfa` or
  later). Commit locally, do NOT push. Standing bar: full-suite table on
  the committed tree.
- Fences: `semantic-registry/`, `generated/`, `frozen-expectations/`,
  `delivery/n1d/`, `artifacts/`, `src/tqe/runtime/catalog.py` (NO contract
  changes of any kind in this packet).
- **Zero-drift bar (defining constraint): pure code relocation.** No
  behavior change, no hash movement, no contract change. The F2-0 precedent
  applies: pinned gates passing IS the drift proof.

## Scope

Move the pass-family node functions out of `executor.py` into
`src/tqe/runtime/capabilities/pass_family.py`:

- `primitive_controlled_pass_episode`
- `primitive_one_touch_relay_episode`
- the bypass/pass-bypass/high-bypass node functions
  (`opponents_bypassed_by_action`, `pass_bypass`, `high_bypass_completed_pass`
  — identify their exact function names by reading the dispatch registry)
- `primitive_action_event_anchor` IF AND ONLY IF it is pass-family-coupled
  (it parses pass events); if it serves non-pass capabilities too, leave it
  and note the coupling in the report for the director's F2-3 sequencing.

Rules of the move:

1. Functions keep their exact signatures `(state, node)` and exact bodies —
   relocation, not refactoring. Resist every temptation to improve; note
   improvement candidates in the report instead.
2. Shared helpers used ONLY by pass-family functions move with them.
   Helpers used by other families too STAY in executor.py — list each such
   shared helper in the report (this list is director input for the shared-
   kernel design in later packets).
3. The dispatch registry (`capabilities/__init__.py`) points at the new
   locations; no other executor.py code changes.
4. The boundary-freeze test's allowlist entries for relocated code must
   MOVE OR SHRINK, never grow. Imports of capability modules from
   executor.py shared sections count as leaks — the registry, not
   executor.py, is the only place that may know the family module exists.
5. Update the F2-0 conformance shadow report path expectations if module
   paths are recorded anywhere.

## Required tests

Existing suites are the safety net (that's the point of a pure move). Add
only: an import-boundary test asserting `executor.py` does not import
`pass_family` (registry-only wiring), and that every relocated function is
reachable through the registry.

## Deliverables

Branch `packet/f2-2`; the relocation; executor.py line-count before/after in
the report; the shared-helpers list (director input); the
improvement-candidates list (NOT implemented); full-suite table; pinned-gate
drift proof (`n1d1`, `afl-substrate-q4`, `afl-substrate-q6`,
`afl-line-break-support-response`, `afl-lane-occupancy`, `afl-09a`,
`scp-0`, `afl-passport` — all must PASS untouched);
`delivery/packets/F2-2-REPORT.md`.
