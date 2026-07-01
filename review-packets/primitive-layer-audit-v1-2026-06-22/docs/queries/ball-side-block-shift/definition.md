# Query Definition - Ball-Side Block Shift

## Query ID

`ball_side_block_shift_v1`

## What This Query Proves

The ball entered a wide area, the defending outfield block shifted toward that ball side, and the attack subsequently switched, retained without switching, or lost possession within the configured horizon.

## What This Query Does Not Prove

It does not prove:

- the attack intentionally caused the movement;
- a switch was always available;
- an opposite-side option was optimal;
- not switching was a mistake;
- the sequence was a tactical opportunity;
- a receiver was open;
- a pass lane was available;
- the result generalizes beyond the implemented predicates.

## Query-Specific Model

M1 defines one query-specific model:

```python
class BallSideBlockShiftQueryV1(BaseModel):
    analysis_rate_hz: int
    minimum_possession_seconds: float

    wide_entry_fraction: float
    prior_central_fraction: float
    minimum_wide_dwell_seconds: float

    baseline_window_seconds: float
    shift_search_window_seconds: float
    minimum_shift_metres: float
    minimum_shift_persistence_seconds: float

    outcome_horizon_seconds: float
    opposite_side_fraction: float
    retained_after_switch_seconds: float
```

Do not define a generic tactical query language in M1.

## Detector Sequence

1. Build a 5 Hz analysis stream from the canonical 25 Hz source frames while retaining the original source frame IDs.
2. Identify eligible possessions where the query perspective team has active-ball possession for at least the configured duration.
3. Detect wide entry: the ball enters a wide channel, dwells there, and was previously central.
4. Calculate the defensive baseline from the defending outfield centroid before wide entry.
5. Find the anchor frame with maximum signed defensive lateral displacement toward the ball side during the eligible possession segment.
6. Enforce shift magnitude and persistence.
7. Classify outcome over the configured horizon after the anchor as `SWITCHED`, `RETAINED_NO_SWITCH`, `LOST_BEFORE_SWITCH`, or excluded `STOPPAGE`.
8. Deduplicate overlapping moments.
9. Generate replay windows around baseline, anchor, and outcome.

## Initial Parameters

See `delivery/m1/SPEC.md` for the current normative initial configuration.

## Calibration Rule

Only `J03WOH` may be used for calibration. Evaluation matches must not be inspected before the query is frozen and hashed.

Changing thresholds or semantics after evaluation starts creates a new query version and invalidates earlier evaluation.

## Review Rule

Accepted result predicates must be recomputed by verification code that does not merely trust detector-stored booleans.
