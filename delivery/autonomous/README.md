# Autonomous Delivery Governance

This directory contains two kinds of artifacts.

## Imported References

These files were supplied as external planning artifacts and are preserved
verbatim:

- `priori_autonomous_delivery_charter.md`
- `priori_autonomous_milestone_contract.yaml`

They are useful strategic references, but they are not the operational gate
contract.

## Operational Draft

These files are the current repo-local operational draft:

- `afl_milestone_contract.yaml`
- `AFL-G0_SPEC.md`
- `schemas/afl_milestone_contract.schema.json`
- `schemas/gate_result.schema.json`
- `schemas/review_packet_manifest.schema.json`

The `AFL-*` namespace avoids collision with existing Priori milestones. The
current local verifier is intentionally classified as interim self-verification.
It can validate structure and drift, but it is not a protected boundary because
it lives in the same repository and workspace as the implementation.

True autonomous promotion requires a separate gate identity: a separate
repository, protected CI environment, signing key, or equivalent boundary that
the builder cannot modify.
