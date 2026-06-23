# M2A-S0C Contract Freeze

Decision: **PROCEED_TO_S1**

Contract SHA-256: `ffa4c63bd127eb9ba232e6666bafc8e96c7a371f347d8fe6cac05d7466119ef7`

## Accepted Scope

- Match IDs: `['J03WOY']`
- Periods: `['firstHalf', 'secondHalf']`
- Reason: J03WOY has successful event/tracking pass reconstruction and no active-set or unusable-denominator issues in the 593 provisional controlled pass windows.

## Gate Checks

- `s0a_schema`: **PASS** - m2a.s0a.event_preflight.v1
- `s0a_positive_controlled_passes`: **PASS** - 593 provisional controlled-pass PASS records
- `s0a_timestamp_alignment`: **PASS** - event-frame offset p95=18.0ms
- `s0a_event_is_not_release_frame`: **PASS** - physical release delta p50=1.08s; S1 must derive release from tracking
- `s0b_schema`: **PASS** - m2a.s0b.active_players.v1
- `s0b_j03woy_pass_window_count_matches_s0a`: **PASS** - S0B windows=593 S0A pass=593
- `s0b_no_active_change_in_accepted_scope`: **PASS** - 0 J03WOY pass windows cross active-set changes
- `s0b_no_unusable_denominator_in_accepted_scope`: **PASS** - 0 J03WOY pass windows have empty/unusable defending denominator
- `s0b_full_corpus_caution_recorded`: **PASS** - 183934 full-corpus frame/team count deviations require coverage policy
- `s0c_bypass_smoke`: **PASS** - {"attack_x_sign": 1, "bypassed_buffer_m": 1.0, "bypassed_player_ids": ["a", "b"], "candidate_goal_side_ids": ["a", "b"], "coverage_status": "COMPLETE", "evaluated_opponent_ids": ["a", "b", "c"], "evaluation_status": "PASS", "expected_active_opponent_ids": ["a", "b", "c"], "failure_reason": null, "goal_side_buffer_m": 1.0, "missing_active_opponent_ids": [], "opponents_bypassed_count": 2, "reception_ball_attack_x_m": 12.0, "release_ball_attack_x_m": 0.0}

## Evidence Summary

- Candidate completed pass events: 639
- Controlled pass status counts: `{'FAIL': 11, 'PASS': 593, 'UNKNOWN': 35}`
- Event-frame offset ms: `{'count': 637, 'max': 19.0, 'min': -20.0, 'p50': 0.0, 'p90': 16.0, 'p95': 18.0}`
- Release delta from event seconds: `{'count': 604, 'max': 3.0, 'min': -1.0, 'p50': 1.08, 'p90': 2.12, 'p95': 2.32}`
- Reception delta from release seconds: `{'count': 593, 'max': 5.16, 'min': 0.04, 'p50': 1.72, 'p90': 3.4, 'p95': 3.76}`
- J03WOY pass-window analysis: `{'pass_records_path': 'artifacts/m2a/s0a-event-preflight-J03WOY-records.csv', 'samples': [], 'status': 'PASS', 'window_count': 593, 'windows_with_active_set_change': 0, 'windows_with_unusable_defending_outfield_denominator': 0}`
- Full-corpus frame/team count deviations: 183934

## Frozen Policies

- Event timestamp is the action anchor, not physical release.
- Physical release must be derived from tracking around the event.
- Controlled reception must be derived from receiver control in tracking.
- Expected opposition denominator is active defending outfield players at release and reception.
- Active-set changes inside the pass window become `UNKNOWN`.
- Missing expected active opponents become `UNKNOWN`; counts are never silently reduced.
- Bypass measurement is threshold-free; the recipe owns `>= 5` and `forward_progression_m >= 8`.

## S1 Boundary

- S1 unlocked: `True`
- Allowed initial runtime scope: `['controlled_pass_episode for J03WOY accepted scope', 'opponents_bypassed_by_action using active defending outfield sets', 'high_bypass_completed_pass_v1 result emission']`
- Still blocked: `['all-corpus M2A execution without reduced-player/tracking-gap coverage classification', 'Hermes exposure', 'defensive-line or support-response semantics']`