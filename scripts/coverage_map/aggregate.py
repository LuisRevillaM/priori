#!/usr/bin/env python3
"""Regenerate the coverage-map report + CSV from the classification ledger.

The ledger (generated/coverage-map.json) is the judgment layer — 741 rows, each a
proof-carrying classification of an atlas concept against the current catalog. This
script is the DETERMINISTIC layer: it recomputes coverage %, the two backlogs
(missing primitives, composition constraints), family coverage, and a calibration
spot-check. Re-run after editing the ledger as new capabilities land:

    make coverage-map      # or: python scripts/coverage_map/aggregate.py

It changes no runtime semantics and reads only the ledger.
"""
from __future__ import annotations

import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "generated" / "coverage-map.json"
CSV_OUT = ROOT / "generated" / "coverage-map.csv"
REPORT = ROOT / "artifacts" / "autonomous" / "coverage-map-report.json"

CLAIM_STATUS = "internal_steering_only_v0_estimated_not_external_claim"
AUDIT_NOTE = (
    "30-row stratified audit corrected aggregation/extremum operator inflation; "
    "additional audits are required before external coverage claims."
)
ROADMAP_IMPLICATIONS = [
    "Q5 landed transition_anchor / structured_zone / outcome_window and redistributed the prior transition-anchor backlog.",
    "time_to_arrival landed as a static-point reachability primitive; the prior reachability backlog has redistributed into supported rows or narrower next blockers.",
    "carry_episode landed as a conservative movement-under-control primitive; the prior carry backlog has redistributed into supported rows or precise next blockers.",
    "Q2 now composes through generic binary episode joins; carry_out_of_pressure is generically_composable, not yet compiler_reachable.",
    "set_piece_structure and off_ball_run are now the top missing primitives by atlas unlock count.",
    "Remaining reachability gaps are mostly not this primitive: moving-target interception, pass-line interception, cover shadow, reachability-field/region generation, graph construction, or margin/rate operators.",
    "Remaining carry-family gaps are mostly not base carrying: defender-bypass-by-carry, space generation, profile aggregation, contact/touch, body orientation, or learned value.",
    "Regenerate the coverage map after every substrate package so supported/partial/gap counts remain a living metric.",
    "Treat composition constraints as compiler-alignment backlog, not hidden plan-wiring knowledge.",
]

# Merge near-duplicate capability strings the classifiers emitted into canonical names.
PRIMITIVE_ALIASES = {
    "set_piece_structure (+ role_or_reference_gap)": "set_piece_structure",
    "off_ball_run (run typing)": "off_ball_run",
    "off_ball_run + marking": "off_ball_run",
    "time_to_intercept": "time_to_arrival",
    "reachability": "time_to_arrival",
    "possession_phase": "transition_anchor",
    "transition / possession-phase": "transition_anchor",
}

def canon(cap: str) -> str:
    cap = (cap or "").strip()
    return PRIMITIVE_ALIASES.get(cap, cap)

def main() -> None:
    rows = json.loads(LEDGER.read_text())
    total = len(rows)
    cls = collections.Counter(r["classification"] for r in rows)
    pct = lambda n: round(100 * n / total, 1)

    prim = collections.Counter()
    for r in rows:
        if r["classification"] in ("missing_primitive", "partial_with_typed_gap"):
            cap = canon(r.get("required_missing_capability"))
            if cap:
                prim[cap] += 1

    ccn = [r for r in rows if r.get("composition_constraint_needed")]
    fam = collections.defaultdict(collections.Counter)
    for r in rows:
        fam[r["family"]][r["classification"]] += 1

    def chk(label, subs, expect):
        hits = [r for r in rows if any(s in r["concept"].lower() for s in subs)]
        ok = [h for h in hits if h["classification"] in expect]
        return {"check": label, "matched": len(hits), "in_expected_class": len(ok),
                "examples": [(h["concept"], h["classification"]) for h in hits[:4]]}

    calibration = [
        chk("carrying->supported_or_precise_next_gap", ["carry", "dribble"], {"supported", "missing_primitive", "partial_with_typed_gap", "missing_modality"}),
        chk("possession->supported", ["possession_dur", "circulation", "retention"], {"supported", "partial_with_typed_gap"}),
        chk("learned/xg->missing_modality", ["expected_goal", "_xg", "value_model", "pitch_control", "completion_prob"], {"missing_modality"}),
        chk("cover/reach->supported_or_precise_next_gap", ["cover_shadow", "time_to_inter", "reachab", "interception_margin"], {"supported", "missing_primitive", "partial_with_typed_gap"}),
        chk("roles->role_gap", ["tactical_role", "fullback", "_role_"], {"role_or_reference_gap", "ambiguous_or_needs_definition", "supported"}),
    ]

    report = {
        "schema_version": "coverage-map.v0",
        "claim_status": CLAIM_STATUS,
        "catalog_basis": "codex/afl08-passport-loop substrate after Q5, time_to_arrival static-point reachability, carry_episode movement-under-control, and Q2 generic binary episode joins",
        "denominator_note": "Coverage of Priori's authored 741-concept atlas inventory — NOT coverage of all questions users may ask. True denominator is the held-out NL eval.",
        "audit_note": AUDIT_NOTE,
        "roadmap_implications": ROADMAP_IMPLICATIONS,
        "total_concepts": total,
        "coverage_counts": dict(cls),
        "coverage_pct": {k: pct(v) for k, v in cls.items()},
        "reachable_now_or_one_gap_pct": pct(cls.get("supported", 0) + cls.get("partial_with_typed_gap", 0)),
        "top_missing_primitives_by_unlock": prim.most_common(15),
        "composition_constraint_count": len(ccn),
        "family_coverage": {k: dict(v) for k, v in sorted(fam.items())},
        "calibration_spotcheck": calibration,
        "audit_sample": {
            "rows_reviewed": 30,
            "approx_solid_rows": 26,
            "systematic_correction": "aggregation/extremum operator rows were downgraded from supported to partial_with_typed_gap because no generic argmax/argmin/local extremum operator exists.",
            "initial_supported_pct_after_correction": 43.9,
            "initial_reachable_now_or_one_gap_pct_after_correction": 64.8,
            "current_supported_pct_after_q2_redistribution": pct(cls.get("supported", 0)),
            "current_reachable_now_or_one_gap_pct_after_q2_redistribution": pct(cls.get("supported", 0) + cls.get("partial_with_typed_gap", 0)),
        },
    }
    REPORT.write_text(json.dumps(report, indent=1) + "\n")

    keys = ["concept", "family", "classification", "justification", "required_missing_capability",
            "closest_supported_substitute", "composition_constraint_needed", "composition_constraint_note",
            "compiler_reachability_status", "priority_unlock"]
    with CSV_OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})

    print(f"coverage-map v0 | {total} concepts")
    for k, v in cls.most_common():
        print(f"  {pct(v):>5}%  {v:>3}  {k}")
    print(f"reachable now or with one gap: {report['reachable_now_or_one_gap_pct']}%")
    print("top missing primitives:", prim.most_common(8))
    print("composition constraints needed:", len(ccn))
    for c in calibration:
        print(f"  calib {c['in_expected_class']}/{c['matched']}  {c['check']}")

if __name__ == "__main__":
    main()
