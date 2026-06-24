# Reproduction

Run from repository root:

```bash
make scp-0-verify
make afl-g0-verify
make afl-g0-gate
```

Protected promotion additionally requires a non-builder CI identity,
a protected suite hash, and `AFL_GATE_SIGNING_KEY` supplied outside the repo.
