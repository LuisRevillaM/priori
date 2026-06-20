# M1 Baseline Freeze

## Fact
M1 is controller-verified, not final owner-accepted. The baseline freeze records the verified M1 detector behavior as an oracle for M1.1 parity without changing analytical behavior.

## Decision
M1.1 may proceed using tracked manifests in `delivery/m1/baseline/` as the compatibility boundary:

- `m1-baseline-manifest.json` for M1 verification state, query freeze, source hashes, and acceptance boundary.
- `legacy-result-manifest.json` for accepted result IDs, classifications, frame anchors, and near-miss keys.
- `evidence-bundle-manifest.json` for selected evidence bundle and replay JSON hashes.

## Learning
The baseline must distinguish three states that are easy to blur: M1 was verified by the controller, the owner explicitly allowed baseline freeze and M1.1 preparation to proceed, and final M1 owner acceptance remains pending.

## Evidence
- `make m1-verify`
- `make m1-baseline-freeze`
- `docs/queries/ball-side-block-shift/semantic-gold-set.v1.json`
- `delivery/m1/baseline/m1-baseline-manifest.json`
