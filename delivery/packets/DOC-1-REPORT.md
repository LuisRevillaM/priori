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
  "hero_relation": "cfd1acd732336d30",
  "path": "apps/workbench-alpha/public/case-study-part-two-replays.json"
}
```

## Exhibit Provenance

| Exhibit | Source | Provenance |
| --- | --- | --- |
| Honest UNKNOWN | Current controlled-pass runtime probe over `J03WOY` open-play passes | `J03WOY`, first half, away, event row `16`, pass episode `J03WOY:firstHalf:away:16:DFL-OBJ-J0196K:DFL-OBJ-J01KGY`, anchor frame `12362`, release-search frames `12337-12437`, current status `UNKNOWN`, reason `release_not_confirmed`, replay frames `141`. |
| Corridor that was never 0.8s | Current `execute_default_plan()` rows plus `evaluate_geometric_progressive_corridors()` | Relation `d797bf377bf89939`, `J03WOY`, first half, open frame `13860`, close frame `13875`, `4` PASS states. Old state-count duration `0.8s`; honest elapsed span `0.6s`; replay frames `61`. |
| Twelfth hero moment | DOC-1 review set difference plus current N1 attested document executed through the live runtime, with relation evidence from per-period state | Round-1 review verified the added row by executing the archived F1-C-era engine at `d006780` and diffing it against the live F1-D result set. The added row is final result `854d129b6d14f7dd`, relation `cfd1acd732336d30`, `J03WOY`, first half, live result count `12`, destination point `{x_m: 43.09, y_m: 5.11}`, declared region `central_central`, bounds `-6.8m..6.8m`, replay frames `116`. |
| One pitch, one partition | Runtime `partition_metadata()` plus DOC-1 review-required y=8.0m contrast | Five equal lanes over a `68m` pitch width, tie policy `five_equal_lanes_abs_y_ties_toward_center`, y marker `8.0m`; old fractional destination model: `central` (`\|y\| < 11.22m`); old lane occupancy: `RIGHT_HALF_SPACE`; declared shared model: `right_half_space` (`6.8m..20.4m`). |

## Rendered Walkthrough

- Part two starts after the existing part-one conclusion.
- Exhibit one shows the pass-event search window as a replay and labels the
  result as insufficient release evidence, not failure.
- Exhibit two draws the corridor at its open/close evidence and shows the
  old `0.8s` count beside the honest `0.6s` elapsed span.
- Exhibit three draws the reviewed set-difference hero row under the unified
  lane model, with the result count `12` shown in the facts strip.
- Exhibit four renders the declared five-lane pitch partition, the `y = 8.0m`
  marker, and the three classifications from the old fractional destination
  model, old lane occupancy model, and declared shared model.
- The hero genealogy is rendered as a simple three-step strip:
  `14` June attestation -> `11` elapsed duration -> `12` unified lanes.

The page has no sources section.

## Verification

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python scripts/workbench_alpha/generate_case_study_part_two_replays.py` | PASS | Generated the public part-two replay packet from runtime/canonical data. |
| `npm --prefix apps/workbench-alpha run test:unit` | PASS | `api`, `geometry`, `playback`, `presentation`, `workbenchState`, `overlay`, and `momentZero` tests passed. |
| `npm --prefix apps/workbench-alpha run build` | PASS | Contract generation, TypeScript, and Vite production build passed. Vite emitted the existing large chunk warning only. |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests` | PASS | Round-2 rerun after review fixes; `337` tests in `324.900s`; `OK`; attestation status `VERIFIED`. |

## Notes

- The honest UNKNOWN exhibit uses the packet-approved sparse/release-not-confirmed
  fallback because current `J03WOY` open-play controlled-pass records have no
  live `reception_window_truncated` UNKNOWN candidate.
- The M1.1 duration exhibit uses a current 0.6s/four-pass-state relation as
  the representative of the old 0.8s threshold-crossing class.
- The twelfth hero exhibit intentionally selects the review-verified
  set-difference result id `854d129b6d14f7dd`. The round-1 heuristic selection
  was rejected because it displayed a row already present in the 11-result
  F1-C set.
