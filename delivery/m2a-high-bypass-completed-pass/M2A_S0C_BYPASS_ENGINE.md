# M2A-S0C Pure Bypass Measurement Engine

Status: implemented as isolated synthetic logic, not wired into runtime registries.

Files:

```text
src/tqe/runtime/bypass.py
tests/test_m2a_bypass.py
```

## Scope

The evaluator measures which expected active opposition outfield players were bypassed between a controlled pass release endpoint and a controlled reception endpoint.

It consumes:

```text
release_ball_x_m
reception_ball_x_m
release_opponent_positions
reception_opponent_positions
expected_active_opponent_ids
attack_x_sign
excluded_opponent_ids
goal_side_buffer_m
bypassed_buffer_m
```

It returns:

```text
evaluation_status
coverage_status
missing_active_opponent_ids
candidate_goal_side_ids
bypassed_player_ids
opponents_bypassed_count
normalized ball x positions
buffer configuration
```

## Semantics

Coordinates are normalized internally:

```text
attack_x_m = x_m * attack_x_sign
```

An opponent is a candidate if:

```text
opponent_attack_x_at_release > release_ball_attack_x + goal_side_buffer_m
```

An opponent is bypassed if the same opponent is:

```text
candidate at release
AND opponent_attack_x_at_reception < reception_ball_attack_x - bypassed_buffer_m
```

The comparisons are strict. A player level with the buffer boundary is not counted.

## UNKNOWN Policy

Missing expected active opposition outfield players produce:

```text
evaluation_status = UNKNOWN
coverage_status = UNKNOWN
```

The evaluator still reports the measured bypassed ids among observed players, but the result is not complete and must not be treated as a definitive non-bypass or definitive count by downstream recipe predicates.

Goalkeepers are excluded by the caller through `excluded_opponent_ids`. Excluded players are not required for coverage and are not counted.

## Threshold Boundary

The evaluator is threshold-free. It does not know:

```text
opponents_bypassed_count >= 5
forward_progression_m >= 8
HIGH_BYPASS_COMPLETED_PASS
```

Those belong to the later recipe/predicate layer.

## Verification

Focused unit tests cover:

```text
attacking-direction mirroring
player-order determinism
strict buffer edges
missing expected active opponent -> UNKNOWN
goalkeeper exclusion
threshold-free count reporting
```

Command:

```text
./.venv/bin/python -m unittest tests.test_m2a_bypass
```

Result:

```text
Ran 6 tests
OK
```
