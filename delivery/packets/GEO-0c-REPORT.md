# GEO-0c — `multi_line_model` coverage correction report

Branch: `packet/geo-0c`

Frontier: `38fe8bbd08f8a1f380a9d2acaee88fcd72fc1bbf`

Executor clone: `/private/tmp/priori-geo0c-executor.Wt4y0h` (outside the
repository tree)

Status: **IMPLEMENTED — CERTIFIED VALUE-LEVEL STOP AUDIT CLEAR; FULL SUITE PASS**

## Design brief (authored before implementation)

### Existing semantic defect

`multi_line_anchor_record` currently turns both `no_observed_lines` and
`target_line_rank_not_observed` into `FAIL` whenever GEO-0a's single-frame
`player_track` manifest lookup is certified. That gate proves that the
producer covered its declared active-player population; it does not, on its
own, prove that enough defending outfield players have identifiable
coordinates to negate the requested geometric line rank. The current loop
also silently drops observed defender rows whose X or Y coordinate is absent.
Consequently a thin or ambiguous snapshot can be reported as a negative
tactical fact.

The affected path is deliberately narrow:

- `src/tqe/runtime/capabilities/lines_family.py::primitive_multi_line_model`
  resolves the declared thresholds and the known outfield roster.
- `multi_line_anchor_record` reads the ball and defending outfield rows,
  constructs disjoint observed bands, and presently assigns `FAIL` before
  consulting only the manifest gate.
- `multi_line_payload_from_anchor` emits the selected rank and line witnesses,
  but no explicit defender-identifiability evidence.
- `src/tqe/runtime/catalog.py` already declares every tactical quantity used
  here as a parameter: `goal_side_buffer_m`, `line_band_width_m`,
  `minimum_line_defenders`, and `target_line_rank`.

`defensive_line_model` is not widened into this packet. Its pure kernel already
forces `UNKNOWN` for an uncertain goalkeeper, unknown active-defender
denominator, invalid positions, and too few defenders. GEO-0c corrects the
separate ranked `multi_line_model` implementation named by ADR 0018 §3.3.

### Declared identifiability criteria

For evaluation frame `F`, declared rank `R`, and declared minimum members per
line `M`, defender observation is **adequate** exactly when all of the following
hold:

1. GEO-0a's observation-manifest interface certifies `player_track` coverage
   for `(match, period, [F,F])`.
2. The defending outfield population is classifiable from `players.parquet`,
   so goalkeeper exclusion is explicit rather than guessed.
3. Every observed defending-outfield row at `F` has finite X and Y
   coordinates. An observed row with an unusable coordinate is ambiguous; it
   is never silently discarded as evidence of absence.
4. At least `R × M` valid defending outfield players are observed at `F`.
   This is the structural witness floor: fewer players cannot populate `R`
   disjoint lines of at least `M` players each, so absence of rank `R` is not
   identifiable from that snapshot.

The floor contains no new football constant. Both factors are existing query
or saved-definition parameters and will be echoed, along with their derived
product, in every evaluated record. `goal_side_buffer_m` and
`line_band_width_m` remain the declared geometric tests. Exact coordinates and
those declared inequalities make band membership deterministic; GEO-0c does
not invent an uncalibrated measurement-error tolerance.

The resulting tri-state law is:

- adequate observation plus no qualifying line at all → `FAIL` with
  `no_observed_lines`;
- adequate observation plus fewer than `R` qualifying disjoint lines →
  `FAIL` with `target_line_rank_not_observed`;
- uncertified player-track coverage → `UNKNOWN`, retaining GEO-0a's typed
  coverage reason and row provenance;
- unknown outfield population, invalid observed defender coordinates, or
  fewer than `R × M` valid observed defenders → `UNKNOWN` with the exact
  identifiability reason;
- an observed rank under adequate observation → `PASS` as before.

The payload will expose the observation disposition, valid/invalid observed
counts and IDs, the derived minimum identifiable count, and manifest coverage
reason/row IDs. Downstream consumers therefore receive both the tri-state
answer and the evidence that licensed it. No tactical role, formation, legal
offside, intent, or quality label is introduced.

### Compatibility and migration

No primitive, recipe, registry identifier, field-reference kind, serving
contract, or tactical threshold is added. Existing parameter spelling and
defaults stay byte-identical. The catalog's `multi_line_model` evidence
contract will be extended to advertise the new coverage witnesses; existing
plans remain readable. Runtime node-cache invalidation follows the existing
code-epoch machinery.

The canonical SkillCorner-derived manifest certifies the provider's declared
active-player population. Under that producer contract, an absent roster
player is not automatically a missing active track; the runtime judges the
actual observed outfield population at `F` against the parameter-derived
structural floor. Vision-adapter rows that do not certify complete declared
entity coverage remain `UNKNOWN` through the same GEO-0a mechanism.

### Tests and mutation standard

Named tests will exercise both directions through the committed runtime path:

- certified coverage + at least `R × M` valid defenders + no declared pair
  permits `FAIL`;
- the same geometric non-result with uncertified coverage forces `UNKNOWN`;
- certified coverage with fewer than `R × M` defenders forces `UNKNOWN`;
- certified coverage with an invalid observed defender coordinate forces
  `UNKNOWN` rather than silently dropping that defender;
- an adequately observed declared pair remains `PASS`.

For the mutation proof, the structural adequacy guard will be temporarily
bypassed. The named insufficient-observation oracle must fail, the guard will
be restored, and the same oracle must pass. A source/status check will prove no
mutation remains.

### Certified-result STOP law

Leg zero freezes ADR 0018, GEO-0a's observation law, certified inputs/tables,
oracles, dev sets, and frozen expectations. The certified runtime inventory
that directly executes `multi_line_model` is Q3 and Q6, via:

- `config/query-plans/q3_receiver_second_line_no_underneath_support.experimental.v1.json`
- `config/query-plans/q6_throw_in_first_action_under_pressure.experimental.v1.json`
- their frozen AFL-09A expectations and verification reports.

The implementation tree and an untouched `38fe8bbd` control will execute the
same committed producers against identical canonical/raw roots. Status
distributions, results, evidence populations, classifications, and semantic
hashes will be compared. The broader certified R2/GALLERY surfaces do not bind
`multi_line_model`; their standing suite checks remain required, but they are
not falsely presented as direct GEO-0c witnesses.

If any existing certified tactical value changes, execution stops and the
exact before/after delta is reported. No frozen expectation, certified table,
or result is rewritten or re-certified on this branch.

## Implementation record

The design was sealed first in `035cb02c`. Runtime implementation and the six
direction tests landed in `f3319c97`. The semantic contract and committed
generated artifacts landed in `6bcb999f`.

`multi_line_anchor_record` now evaluates the GEO-0a player-track coverage row,
the known outfield population, coordinate validity, and the
`target_line_rank × minimum_line_defenders` witness floor before any missing
rank can become `FAIL`. All disposition and coverage evidence is emitted on
the anchor record. `selected_line` is withheld unless the overall result is
`PASS`, so partial bands from an insufficient snapshot cannot leak downstream
as a certified selected line.

The catalog and semantic evidence contract advertise the new witnesses. The
committed producers regenerated the capability catalog, SCP-0 projections,
passport, registry lock, capability context, and tactical knowledge pack.
SCP-0 initially and correctly rejected the unregenerated contract. A temporary
AI-parity bridge was used only to order the generation dependency, then
removed after the model-visible knowledge pack was rebuilt. The final registry
contains no waiver for GEO-0c and SCP-0 passes with zero unapproved drift.

The capability-context producer also normalized inherited GEO-0b typed-field
references that were stale on the frontier. Those generated diffs are
producer output, not a GEO-0c runtime expansion; they are disclosed rather
than hand-edited away.

## Mutation evidence

The guard
`len(valid_defenders) < required_observed_defender_count` was temporarily
bypassed. The named oracle
`test_insufficient_defender_observation_is_forced_unknown` failed exactly as
required: expected `UNKNOWN`, received `FAIL` (exit 1). After restoration, the
same oracle passed, all six direction tests passed, and a source grep proved
the mutation absent.

## Certified-result STOP audit

Control clone: `/private/tmp/priori-geo0c-control.nH9MPn`, detached at
`38fe8bbd08f8a1f380a9d2acaee88fcd72fc1bbf`. Both trees used regular-file
copies of the same 182 MB canonical corpus, the same absolute raw corpus and
data manifest, and one execution worker.

| Certified surface | Untouched frontier control | GEO-0c | Value verdict |
| --- | --- | --- | --- |
| Q3 execution | PASS; 13 results; 0 evidence failures | exact same | no delta |
| Q3 multi-line probe | PASS 142; FAIL 106; UNKNOWN 0; population 248 | exact same | no delta |
| Q3 downstream probes | support FAIL 184 / UNKNOWN 64; action chain PASS 146 / FAIL 64 | exact same | no delta |
| Q6 execution | PASS; honest zero; 0 results; 0 evidence failures | exact same | no delta |
| Q6 line transition | PASS 1; FAIL 13; UNKNOWN 3; population 17 | exact same | no delta |
| Q6 pressure / velocity | pressure PASS 5 / FAIL 7; velocity PASS 17 | exact same | no delta |

The coverage-witness contract changes plan identity, as it must under the
PERF-1 cache-key law. Q3 bound-plan hash moves from `f6f3776d...` to
`88970ddc...`; Q6 moves from `d3f23c56...` to `f1a264b2...`. Q3 result IDs
and its signature hash also move because their identity includes the changed
plan contract. Q6's empty-result signature remains exactly
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
No status, count, classification, population, requested-evidence result, or
tactical value changed. Therefore **the certified-value STOP condition does
not fire**.

The untouched Q3 control already fails its older frozen expectation on the
current frontier (its GEO-0b-era bound-plan hash and result IDs differ from the
frozen file). GEO-0c neither caused nor concealed that pre-existing mismatch.
Q6's control matches its frozen expectation; GEO-0c differs only on the new
bound-plan identity. Both frozen expectation files stayed byte-unchanged.

## Verification table

| Gate | Result |
| --- | --- |
| GEO-0c both-direction suite | PASS — 6 tests in 0.011 s |
| GEO-0a + GEO-0c + line kernel + executor boundary suite | PASS — 48 tests in 0.248 s |
| Structural-guard mutation | EXPECTED FAIL; restored oracle PASS; mutation absent |
| Q3 frontier-vs-GEO value comparison | PASS — exact values; disclosed identity-only hashes |
| Q6 frontier-vs-GEO value comparison | PASS — exact values; disclosed bound-plan hash only |
| Final SCP-0 generation/check | PASS — 58 tests; zero unapproved parity drift |
| `compileall` and `git diff --check` | PASS |
| Final canonical `make test` | PASS — 621 tests in 798.666 s; attestation `VERIFIED`; zero blockers |
| Leg zero | PASS — charter, GEO-0a law, oracles, dev sets, and frozen AFL-09A expectations unchanged |

## Deviations and repository state

- The executor clone is outside the repository tree as required.
- During setup, an initial branch command changed only the primary worktree's
  checked-out branch name before the isolated-clone route was established; no
  primary-worktree file was changed. Sandbox denial prevented restoring that
  branch pointer. All packet edits and commits are confined to the clone named
  above.
- The broad suite exceeded five minutes; its exact 798.666-second duration is
  reported rather than hidden.
- Packet commits before this report-close commit are `035cb02c`, `f3319c97`,
  and `6bcb999f`.
- No push or external-service mutation was attempted.
