# F1-D Acceptance Review — Round 1: REVISE (merge blocked on 3 items)

Reviewed 2026-07-02, branch `packet/f1-d` commit `2836955`, independent
adversarial pass plus director verification. Verdict ACCEPT-WITH-FIXES: the
director rulings are implemented and survived every empirical probe —
mirror-exact classification across the full grid including all edges, the
audit's y=8.0 cross-consumer disagreement resolved, the G2 false-PASS dead
with declared aggregation semantics, all five ride-alongs landed
(`tests/test_m2a_bypass.py` byte-identical to its pre-F1-C original), and
the ripple delta table's numbers reproduced exactly by independent count.
Merge blocked until R1–R3 land on the same branch.

## Required for round 2 (same branch, append commits)

**R1 — apply the declared epsilon in lane_occupancy's classifier.**
`src/tqe/runtime/lane_occupancy.py:596-605` (`_lane_id_for_y`) classifies by
exact band bounds and ignores `tie_epsilon_m`, while the shared
`classify_lane_y` applies it — so y = 6.8+5e-10 diverges between the two
consumers we just unified, and the evidence payload declares an epsilon its
own classifier doesn't use. Route `_lane_id_for_y` through
`classify_lane_y` (or apply ε in band matching), and add the packet's
required edge±ε tests comparing `evaluate_lane_occupancy` assignments
against `destination_lane` directly (the current equivalence test probes
exact edges only and its relations-side is tautological).

**R2 — complete the ripple survey.** Missing from the report's gate table
and stale-list: `afl-line-break-support-response-verify` (composes
lane_occupancy; FAILs on expected-class frozen drift at
`delivery/autonomous/afl09a/frozen-expectations/line_break_support_response.json`
— bound_plan_hash, result_ids 89ffbeed→972b6bb4, signature) and
`afl-passport-verify` (pins lane_occupancy; FAILs on projection/lock
drift). Amend the report; the re-freeze/regeneration remains the
director's at acceptance.

**R3 — regenerate the full-suite table on the committed tree.** The
delivered table was produced pre-commit (its "dirty-runtime guard" row
passes on `2836955`); the true committed-tree count is 6 failures. The
standing bar means the table on the delivered commit. Note the corrected
hero row: 11→12 is a REAL lane ripple (destination-region bounds moved
under the unified geometry; one additional possession qualifies) —
correctly flagged for director re-pin, keep the attribution.

## Non-blocking notes (backlog)

`min_frame_ratio: 0` is trivially satisfied — exclude or document;
`destination_lane_partition()`/`partition_metadata()` currently have no
consumers (wire into contracts at regeneration or drop); the two J03WR9
historical episodes now classifying INVALID
`destination_outside_declared_lane_geometry` instead of coerced-"wide" are
the fail-honest direction and handled at acceptance.

---

# F1-D Acceptance Review — Round 2: ACCEPTED

Reviewed 2026-07-02, commits `5e896bc` + `54b36d5`, merged as `9d77b69`.
R1 verified (occupancy classifier routes through the shared model; edge±ε
regression coverage added); R2 report amended with both missed gates and
the frozen-expectation entry; R3 suite table regenerated on the committed
tree (337 tests, the expected 6 failures, hero row 11 != 12 correctly
attributed as a real lane ripple).

Director acceptance actions: contracts regenerated (parity PASS, 0
findings); attested-hero contract re-pinned 11 -> 12 with the full
genealogy (14 -> 11 duration honesty, 11 -> 12 unified destination
geometry) documented at the assertion; line-break-support-response
expectation re-frozen (hash-class drift, content verified). Phase F1 is
complete with this merge: every reproduced truth defect from the
2026-07-01 foundation audit is closed.
