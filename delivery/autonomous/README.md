# Autonomous Delivery Governance

## Read first (binding)

Before using the onboarding brief or planning AFL-08/AFL-09 work, read:

- **`ONBOARDING_RECONCILE_WITH_REALITY.md`**
- **`AGENT_EXECUTION_MODE.md`**

`ONBOARDING_RECONCILE_WITH_REALITY.md` is binding where it corrects informal brief language:
capability passports are **generated projections**, not hand-authored sources of truth;
standard-library/passport work runs under **AFL-08/AFL-09** unless the protected contract is formally
amended. `AGENT_EXECUTION_MODE.md` sets the operating posture: bias to end-to-end execution, use the
existing rails, add ceremony only when it prevents drift, false claims, or unreproducible work.

Read these before acting on the broader brief.

---

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
- `PROTECTED_GATE_SETUP.md`
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

## Local Gate Runner

`make afl-g0-gate` builds a local SCP-0E.1 candidate packet, runs public
verification and public canaries, writes a gate result and certificate, and
packages the evidence for review. By default it must produce a `BLOCKED` result,
because this workspace does not own a protected holdout suite or signing key.

The generated local artifacts are:

- `artifacts/autonomous/afl-g0-scp-0e1-candidate/`
- `artifacts/autonomous/afl-g0-scp-0e1-gate-result.json`
- `artifacts/autonomous/afl-g0-scp-0e1-promotion-certificate.json`
- `artifacts/autonomous/afl-g0-scp-0e1-canary-report.json`
- `review-packets/afl-g0-scp-0e1-local-gate-2026-06-23.zip`
- `review-packets/afl-g0-scp-0e1-local-gate-2026-06-23.zip.sha256`

See `PROTECTED_GATE_SETUP.md` for the environment required to turn the same
mechanics into a protected promotion gate.
