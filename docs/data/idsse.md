# IDSSE / Sportec Open DFL Data

## M1 Role

IDSSE / Sportec Open DFL Tracking and Event Data is the primary and only accepted M1 match-evidence source.

M1 uses it because it provides a small but complete open corpus of elite soccer tracking and event data suitable for deterministic tactical replay:

- seven complete matches;
- all players and ball;
- tracking at 25 Hz;
- synchronized event data;
- German Bundesliga / 2. Bundesliga context;
- open license reported by the source release.

## Match Roles

| Match ID | Home | Away | M1 Role |
| --- | --- | --- | --- |
| `J03WOH` | Fortuna Dusseldorf | SSV Jahn Regensburg | Gate A and calibration |
| `J03WOY` | Fortuna Dusseldorf | Hansa Rostock | Evaluation |
| `J03WPY` | Fortuna Dusseldorf | Nurnberg | Evaluation |
| `J03WQQ` | Fortuna Dusseldorf | St. Pauli | Evaluation |
| `J03WR9` | Fortuna Dusseldorf | Kaiserslautern | Evaluation |
| `J03WMX` | Koln | Bayern Munchen | Portability holdout |
| `J03WN1` | Bochum | Leverkusen | Portability holdout |

## Source Lock Requirements

## Official Source Snapshot

The active source lock uses the official Figshare article API, not mirror metadata:

- Figshare article ID: `28196177`
- Figshare API URL: `https://api.figshare.com/v2/articles/28196177`
- Article DOI: `10.6084/m9.figshare.28196177.v1`
- Dataset DOI family: `10.6084/m9.figshare.28196177`
- Paper DOI: `10.1038/s41597-025-04505-y`
- Article version: `1`
- Published date: `2025-02-02T08:01:37Z`
- License: CC BY 4.0

Gate A has source-locked the official `J03WOH` files locally under:

```text
data/raw/idsse/figshare-28196177-v1/J03WOH/
  metadata.xml
  events.xml
  tracking.xml
```

Locked Gate A source files:

| Kind | Figshare file ID | Official file name | Size | MD5 |
| --- | ---: | --- | ---: | --- |
| metadata | `51643478` | `DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WOH.xml` | `11745` | `b9710781d400dd812f62b0a6e3d7bce8` |
| events | `51643499` | `DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WOH.xml` | `635747` | `ab66e51512f39d06f49f27dd3b4c2f40` |
| tracking | `51643520` | `DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WOH.xml` | `348945715` | `3efff25a86a61768e7d253b4bba137a3` |

The local SHA-256 values are recorded in:

```text
artifacts/m1/gate-a/source-manifest.json
```

The source lock must record:

- dataset DOI;
- article/version identifier;
- source URL;
- retrieval timestamp;
- file names;
- file sizes;
- source checksums if available;
- local SHA-256 for every raw file;
- license;
- paper DOI;
- whether the source was official or an approved mirror.

Official source is preferred. A mirror may be used only if files are shown to match the official manifest and the substitution is documented.

Gate A source-locks only `J03WOH`. The remaining six matches are not provisioned until Gate A is accepted.

## Raw Layout

```text
data/raw/idsse/<source-version>/<match-id>/
  metadata.xml
  tracking.xml
  events.xml
```

Raw files are immutable. Derived outputs must be regenerated rather than editing raw source.

## Canonical Layout

```text
data/canonical/v1/
  matches.parquet
  teams.parquet
  players.parquet
  orientation.parquet
  frames/match_id=<id>/period=<period>.parquet
  positions/match_id=<id>/period=<period>.parquet
  events/match_id=<id>.parquet
```

## Known Risks To Verify

- Event timestamps may have meaningful alignment error relative to tracking.
- Attack direction and halftime orientation must be proven, not assumed.
- Fortuna is home in all tactical-corpus matches, so code must not equate perspective team with home team.
- Goalkeepers must be excluded from defensive-block centroid and width calculations.
- Portability holdouts must validate away-team perspective.
- Floodlight is the production ingestion adapter for M1, but raw XML spot checks and official totals remain the primary truth.

## Gate A Canonical Snapshot

The first canonical build for `J03WOH` produced:

- `137214` authoritative 25 Hz frame rows across two halves;
- `3155922` position observations from Floodlight arrays;
- `1457` Floodlight event rows;
- `39` rostered players;
- exact raw XML parity on `18` deterministic sampled player/ball observations;
- a 30-second replay bundle with `750` frames and `17250` entity observations.

Coordinates are centered metres. The data-quality report records some observations outside the strict pitch rectangle, with maximum bounds of `x=[-55.5, 55.5]` and `y=[-37.69, 37.62]`, but zero observations outside pitch dimensions plus a 5m tolerance. This tolerance is recorded evidence, not permission to ignore future coordinate issues.

## Gate B Corpus Snapshot

The Gate B corpus build source-locks and canonicalizes all seven planned matches:

- `J03WOH`
- `J03WOY`
- `J03WPY`
- `J03WQQ`
- `J03WR9`
- `J03WMX`
- `J03WN1`

Gate B generated:

- `22,876,878` canonical position observations;
- `126` deterministic raw parity samples with zero failures;
- aggregate metadata for `7` matches, `14` teams, `279` players, and `28` orientation rows;
- passing perspective checks for Bayern as away in `J03WMX` and Leverkusen as away in `J03WN1`;
- sequential processing evidence with max RSS about `1.67 GB`.

Raw `J03WMX` and `J03WN1` include referee tracking frame sets. The M1 canonical corpus excludes referee entities and keeps player/ball as the accepted tactical entity boundary.
