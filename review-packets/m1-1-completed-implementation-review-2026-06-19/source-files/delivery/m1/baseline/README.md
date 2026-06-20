# M1 Baseline Freeze

This directory contains tracked baseline manifests used by M1.1 before the legacy M1 detector can act as an oracle.

The manifests are generated from local verified artifacts with:

```bash
make m1-baseline-freeze
```

## Files

- `m1-baseline-manifest.json`: top-level M1 verification, query freeze, source hashes, and baseline state.
- `legacy-result-manifest.json`: selected M1 tactical result IDs, classifications, frame anchors, and near-miss keys.
- `evidence-bundle-manifest.json`: hashes for each selected evidence bundle and replay JSON.

## Boundary

These manifests do not include raw tracking data, canonical Parquet tables, or large generated replay files. They record hashes and IDs so a later M1.1 parity check can detect drift against the accepted M1 behavior.
