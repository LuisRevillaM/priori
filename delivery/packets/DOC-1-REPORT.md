# DOC-1 Report — Case Study Part Two, Interactive

Packet: `delivery/packets/DOC-1-case-study-part-two.md`  
Branch: `packet/doc-1`

## Summary

Extended the `/case-study` route with the part-two section from
`docs/CASE_STUDY.md`: compiler self-audit, honest UNKNOWNs, corridor duration
honesty, lane unification, and the 14 -> 11 -> 12 hero-result genealogy.

Part one content was left intact. The new section uses the same
`Look for / Proves / Does not claim` pattern and the existing pitch visual
language.

No runtime semantics were changed. No files under `src/tqe/runtime/`,
`semantic-registry/`, `generated/`, `frozen-expectations/`, or
`delivery/n1d/` were edited.

## Generated Payload

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/workbench_alpha/generate_case_study_part_two_replays.py
```

Output:

```json
{
  "controlled_unknown": "J03WOY:firstHalf:away:16:DFL-OBJ-J0196K:DFL-OBJ-J01KGY",
  "corridor_relation": "d797bf377bf89939",
  "hero_live_count": 12,
  "hero_relation": "d9344cc7b12728bf",
  "path": "apps/workbench-alpha/public/case-study-part-two-replays.json"
}
```

## Exhibit Provenance

| Exhibit | Source | Provenance |
| --- | --- | --- |
| Honest UNKNOWN | Current controlled-pass runtime probe over `J03WOY` open-play passes | `J03WOY`, first half, away, event row `16`, pass episode `J03WOY:firstHalf:away:16:DFL-OBJ-J0196K:DFL-OBJ-J01KGY`, anchor frame `12362`, release-search frames `12337-12437`, current status `UNKNOWN`, reason `release_not_confirmed`, replay frames `141`. |
| Corridor that was never 0.8s | Current `execute_default_plan()` rows plus `evaluate_geometric_progressive_corridors()` | Relation `d797bf377bf89939`, `J03WOY`, first half, open frame `13860`, close frame `13875`, `4` PASS states. Old state-count duration `0.8s`; honest elapsed span `0.6s`; replay frames `61`. |
| Twelfth hero moment | Current N1 attested document executed through the live runtime, with relation evidence from per-period state | Final result `139dec21797fc297`, relation `d9344cc7b12728bf`, `J03WOY`, first half, live result count `12`, destination point `{x_m: 42.55, y_m: 7.59}`, declared region `right_half_space`, bounds `6.8m..20.4m`, replay frames `161`. |
| One pitch, one partition | Runtime `partition_metadata()` | Five equal lanes over a `68m` pitch width, tie policy `five_equal_lanes_abs_y_ties_toward_center`, y marker `8.0m`. |

## Rendered Walkthrough

- Part two starts after the existing part-one conclusion.
- Exhibit one shows the pass-event search window as a replay and labels the
  result as insufficient release evidence, not failure.
- Exhibit two draws the corridor at its open/close evidence and shows the
  old `0.8s` count beside the honest `0.6s` elapsed span.
- Exhibit three draws the live hero corridor and destination band under the
  unified lane model, with the result count `12` shown in the facts strip.
- Exhibit four renders the declared five-lane pitch partition and the
  `y = 8.0m` marker.
- The hero genealogy is rendered as a simple three-step strip:
  `14` June attestation -> `11` elapsed duration -> `12` unified lanes.

The page has no sources section.

## Verification

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python scripts/workbench_alpha/generate_case_study_part_two_replays.py` | PASS | Generated the public part-two replay packet from runtime/canonical data. |
| `npm --prefix apps/workbench-alpha run test:unit` | PASS | `api`, `geometry`, `playback`, `presentation`, `workbenchState`, `overlay`, and `momentZero` tests passed. |
| `npm --prefix apps/workbench-alpha run build` | PASS | Contract generation, TypeScript, and Vite production build passed. Vite emitted the existing large chunk warning only. |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests` | PASS | Ran on committed tree; `337` tests in `342.022s`; `OK`; attestation status `VERIFIED`. |

## Notes

- The honest UNKNOWN exhibit uses the packet-approved sparse/release-not-confirmed
  fallback because current `J03WOY` open-play controlled-pass records have no
  live `reception_window_truncated` UNKNOWN candidate.
- The M1.1 duration exhibit uses a current 0.6s/four-pass-state relation as
  the representative of the old 0.8s threshold-crossing class.
- The twelfth hero exhibit selects the live lane-boundary half-space result
  whose destination point is closest to the y=8m disagreement area.
