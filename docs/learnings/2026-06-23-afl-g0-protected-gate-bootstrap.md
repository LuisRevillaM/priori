# AFL-G0 Protected Gate Bootstrap

## Fact

The imported autonomous-delivery charter and milestone contract are useful
strategic references, but they are too broad to function directly as a trusted
promotion gate. The immediate system need is a small root-of-trust layer that
namespaces autonomous milestones, freezes the shape of gate artifacts, and makes
verification status harder to confuse with accepted promotion.

## Decision

Create `AFL-G0` as the operational protected-gate bootstrap. It introduces the
`AFL-*` namespace, target classes, contract schemas, gate-result schemas,
review-packet schemas, promotion-certificate structure, and canary requirements.

The current implementation is deliberately labeled `SELF_VERIFIED`. It validates
the repo-local contract and catches obvious tampering patterns, but it does not
claim the protected CI, hidden-suite, signing-key, or independent promotion
boundary required for true autonomous promotion.

## Learning

For autonomous agents, a builder-owned status file is not authority. Promotion
authority must come from a separate gate identity that records the candidate
commit, contract hash, schema hash, suite hash, denominator hash, artifact lock,
and promotion signature or protected tag.

The practical path is therefore staged:

1. Prove the contract is well shaped locally.
2. Move the gate runner and protected suite outside builder authority.
3. Add signed or protected promotion artifacts.
4. Only then allow future `AFL-*` milestones to advance based on promotion
   certificates rather than self-reported completion.

## Evidence

- `delivery/autonomous/AFL-G0_SPEC.md`
- `delivery/autonomous/afl_milestone_contract.yaml`
- `delivery/autonomous/schemas/afl_milestone_contract.schema.json`
- `delivery/autonomous/schemas/gate_result.schema.json`
- `delivery/autonomous/schemas/review_packet_manifest.schema.json`
- `src/tqe/verification/afl_g0.py`
- `tests/test_afl_g0_contract.py`
- `artifacts/autonomous/afl-g0-contract-verification-report.json`

## Follow-Up

Implement the real protected boundary: separate CI or equivalent non-builder
authority, hidden canaries, candidate-packet generation, and signed promotion
certificates. Until then, AFL-G0 is an engineering scaffold, not an accepted
protected gate.
