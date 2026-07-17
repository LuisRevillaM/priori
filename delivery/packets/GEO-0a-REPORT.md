# GEO-0a — observation-manifest enforcement report

Branch: `packet/geo-0a`

Requested frontier: `ccfcefa3`

Packet commit brought onto the frontier: `d9800654` (packet text only; its
parent is `ccfcefa3`)

Status: **IMPLEMENTED; CERTIFIED-RESULT STOP AUDIT IN PROGRESS; NOT PUSHED**

## Outcome

The runtime now has one fail-closed observation-coverage interface for
`(modality, match, period, window)`. An absence-derived negative result is
licensed only when every required modality covers the complete requested
window with `CERTIFIED` rows. An absent, invalid, partial, missing, or explicitly
`UNCERTIFIED` manifest forces the result to `UNKNOWN` and preserves the
would-have-been reason in evidence.

The demo corpus ships a manifest with 56 rows: seven matches, two periods, and
four modalities (`event`, `ball`, `possession`, `player_track`). The rows use
the observed period frame bounds. Canonical frame IDs are contiguous; every
frame has one ball row; player-track certification is over the provider's
active-player population, not a claim that every match has 22 active players
at every frame. The manifest is integrity-locked in `data/manifest.json` and
required by the deploy manifest.

The canonical vision adapter writes the same schema. Event, ball, and
possession rows are explicitly `UNCERTIFIED`. Player tracks certify only when
every declared entity is known at every frame; the SHADOW-1 gated fixture is
therefore also `UNCERTIFIED`. Its vacuous possession/ball behavior now follows
the common law rather than an adapter-specific exception.

Synthetic `PeriodState` fixtures default to an absent manifest, hence
fail-closed. A fixture that asserts an absence-derived FAIL must explicitly
declare certified coverage. Existing typed-join, sequence-pattern, and
destination-entry fixtures were updated on that basis.

## Absence-to-negative inventory

This is the complete runtime inventory found before wiring. “Direct” means the
site itself turns an empty/not-found observation into a negative status.
“Propagated” means it carries a negative from an upstream site and therefore
must inherit the upstream gate rather than add a second independent coverage
claim.

| Runtime site | Existing negative conversion | Coverage gate |
| --- | --- | --- |
| `executor.py`, declared temporal predicate trace | no episode at the anchor → FAIL | event + ball + possession + player-track |
| `operators/sequence_pattern.py` | fully observed empty successor window → FAIL | event + possession + player-track |
| `operators/typed_join.py` | required counterpart absent under `no_match_policy=FAIL` → FAIL | event + ball + possession + player-track |
| `one_touch.py`, relay-touch detection | no relay touch in an otherwise observed window → FAIL | ball + player-track |
| `corridor_family.py`, destination entry | ball never enters the destination region → FAIL | ball |
| `lines_family.py`, observed line selection | no observed line / target rank absent → FAIL | player-track |
| `defensive_line.py` through `lines_family.py` | no qualifying defensive line → FAIL | player-track at the wrapper boundary |
| `offball_family.py`, marking | no marker inside the threshold → `unmarked_status=PASS` / `marking_status=FAIL` | player-track; the absence-derived PASS is gated explicitly |
| `offball_family.py`, off-ball run | no evaluable run candidate or no qualifying candidate → FAIL | ball + player-track |
| `offball_family.py`, time to arrival | no arrival within threshold → FAIL | player-track |
| `support_arrival.py` through `offball_family.py` | no qualifying supporter / support arrival not observed → FAIL | player-track over the complete support window |
| `teamshape_family.py`, cover shadow | no screening defender on the ball-target lane → FAIL | player-track |
| `teamshape_family.py`, pressure on carrier | no observed defender satisfies the pressure threshold/duration → FAIL | player-track over the lookback window |
| `teamshape_family.py`, team press | too few qualifying pressure actors / spread absent → FAIL | player-track over the comparison window |
| `local_number_relation.py` through `teamshape_family.py` | local-number requirement not met → FAIL | player-track at the wrapper boundary |
| `lane_occupancy.py` through `kinematics_family.py` | required lane occupancy absent → FAIL | player-track at the wrapper boundary |
| `kinematics_family.py`, legacy keyed join | right join key not found → FAIL | event + ball + possession + player-track over the left record window |
| `sequence_family.py`, terminal pass | no terminal pass in the successor window → FAIL | event + player-track |
| `possession_family.py`, open space | insufficient qualifying open-space points → FAIL | player-track |
| `possession_family.py`, settled outcome | no settled outcome threshold within the window → FAIL | ball + possession + player-track |

Adversarial grep also found names that sound absence-like but are not new
absence-to-evidence conversions:

- `delta_across_anchor.py` emits `rising_edge_not_observed` and
  `falling_edge_not_observed` only after both scalar endpoints are observed;
  missing endpoints already produce UNKNOWN.
- `controlled_line_break.py`, one-touch receiver-line transition,
  off-ball-run type, and pass-chain records propagate an upstream FAIL. Their
  source primitives are gated above; they do not independently inspect an
  empty modality window.
- compactness, high-bypass, acceleration/deceleration, geometry relations,
  temporal constraints, and required-status checks are contradictions of
  observed values/thresholds. Their missing inputs already produce UNKNOWN.
- `bypass.py`, lane target selection, support candidate selection, and
  controlled-pass tracking gaps already return UNKNOWN for missing evidence.

## Certified-result STOP audit

The first audit appeared to change the R2-1 `period_records_hash`. A sealed
field-level control showed two confounds before any verdict was taken:

1. the committed producer already regenerates a different provenance hash on
   the current corpus in both the untouched frontier and GEO trees; and
2. an overbroad implementation assignment changed `coverage_status` to
   UNKNOWN whenever an upstream semantic status was already UNKNOWN, even when
   the new gate did not fire.

That assignment was corrected across pressure, team press, time-to-arrival,
support-arrival, local-number, and lane-occupancy wrappers. Coverage metadata
now changes only when the manifest gate itself changes a negative result to
UNKNOWN.

Fresh full R2-1 executions then matched byte-for-byte:

| Side | Table SHA-256 | `period_records_hash` | Totals |
| --- | --- | --- | --- |
| untouched frontier control in `/private/tmp/priori-geo0a-baseline.lxDvry` | `68d8100793a3cf907a177a7b25c5a7625b03691fb4855850ec40833702c47a30` | `15ddf8d7e1c998a35428993dbf020dc876fc148a9ef92f0a80c395597d301945` | PASS 145; FAIL 2,615; UNKNOWN 5,654; population 8,414 |
| GEO-0a tree | `68d8100793a3cf907a177a7b25c5a7625b03691fb4855850ec40833702c47a30` | `15ddf8d7e1c998a35428993dbf020dc876fc148a9ef92f0a80c395597d301945` | PASS 145; FAIL 2,615; UNKNOWN 5,654; population 8,414 |

The fenced committed R2-1 table was restored unchanged after the comparison.
No re-certification occurred. R2-2/R2-4 fresh-result controls remain to be
recorded below before final packet closure.

The GALLERY-2 committed check also reproduced 2,811 regain moments with
1,204 defensive-third, 1,054 middle-third, 500 final-third, and 53
location-UNKNOWN records; table semantic hash
`e40f1abc02d142eb96b644e12841e6ac5714b60c1f94817aecfbeda2d482e97e`.

## Oracle and mutation evidence

The named oracle tests are:

- `test_certified_ball_absence_can_remain_fail`
- `test_uncertified_ball_absence_is_forced_unknown`
- `test_absent_manifest_is_uncertified_fail_closed`
- `test_coverage_must_span_the_entire_requested_window`

Mutation probe: the gate's `all(item.certified ...)` condition was temporarily
bypassed. Both uncertified/absent-manifest tests failed (`expected UNKNOWN, got
FAIL`, exit 1). The original condition was restored, and all three direction
tests passed. No mutation remains in the worktree.

## Verification table

| Gate / command | Result |
| --- | --- |
| Focused manifest, adapter, typed-join, and sequence-pattern suite | PASS — 32 tests |
| Restored named law tests after mutation | PASS — 3 tests |
| `compileall` over evidence/runtime and `git diff --check` | PASS |
| Ruff | NOT RUN — `.venv/bin/ruff` is not installed |
| First canonical `make test` | FAIL — 613 tests in 586.093s: 1 failure, 11 errors |

The first broad run found three GEO fixture-constructor regressions, which are
fixed by the fail-closed `PeriodState` default and explicit destination-entry
fixture certification. Eight errors are sandbox `PermissionError` failures at
localhost `WorkbenchServer` bind in `test_deploy1_public_mode` and
`test_smoke1_honest_errors`. The validation-factory failure is its intentional
dirty-runtime freeze guard and must be rerun from the committed tree. A final
standing-suite result will replace this provisional disposition.

An earlier focused invocation omitted `PYTHONPATH=src` and produced four import
errors before executing tests. It is environment-invalid and not presented as
product evidence; the corrected 32-test invocation above passed.

## Deviations and repository state

- `git pull --ff-only` could not start because the repository contains a
  malformed ref named `refs/heads/packet/f2-0.lock.probe`. No pull mutation
  occurred. The requested frontier object was present locally and the branch
  was created directly from `ccfcefa3`.
- The packet file was not in `ccfcefa3`; the direct child packet-only commit was
  cherry-picked as `d9800654` so execution could follow the requested text.
- Executor controls live outside the repository at
  `/private/tmp/priori-geo0a-baseline.lxDvry` and
  `/private/tmp/priori-geo0a-proof.hPnEjY`.
- No push, deploy, registry mutation, or external-service mutation occurred.
- Pre-existing untracked files are not packet work and remain untouched.
