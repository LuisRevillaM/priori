# Work Packet F2-7 — Final Sweep Extraction

Issued: 2026-07-03 by the project director. Sixth and final family
relocation of ADR 0012 §3, per the F2-6 report's remaining-inline census.
Accepted F2-2..6 template applies verbatim (zero-drift pure relocation,
registry-only executor wiring, fences, stage commits, clean shared tree,
full-suite table, eight pinned gates).

Branch `packet/f2-7` off the frontier (tip `bf4cde1` or later).

## Scope — three modules, per the census grouping

1. `capabilities/possession_family.py`: possession_segment,
   transition_anchor, structured_zone, space_region_generation,
   outcome_window, set_piece_structure, outcome_classification.
2. `capabilities/sequence_family.py`: action_chain, switch_of_play,
   carry_episode, pass_chain_episode.
3. `capabilities/kinematics_family.py`: tracking_quality,
   pairwise_distance, and every remaining registered inline capability node
   function from the census (velocity/acceleration/join etc. — sweep them
   ALL; after this packet, executor.py contains ZERO registered capability
   implementations other than the four LEGACY_NOOP registrations, which
   stay for F2-X).

Family-only helpers move; the shared runtime-kernel utilities from the
census (PeriodState, caching, node_parameter_*, anchor helpers, etc.) STAY —
they are the kernel that remains after the sweep.

ALSO deliver (census, no action): every remaining capability-name leak in
shared executor code per the boundary-freeze allowlist — the F2-X kill-list
input.

## Deliverables

Branch `packet/f2-7`; the three modules; executor.py line count
before/after; the post-sweep verification that zero registered inline
implementations remain (a test, not a claim); the F2-X leak census;
full-suite table; pinned-gate proof; `delivery/packets/F2-7-REPORT.md`.
