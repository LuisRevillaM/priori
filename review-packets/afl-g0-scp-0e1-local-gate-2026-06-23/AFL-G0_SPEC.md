# AFL-G0 - Protected Gate Bootstrap

## Outcome

AFL-G0 establishes the minimum viable root of trust for autonomous Priori
delivery. It does not build the football language. It proves that future
builders cannot promote broken work by editing success criteria, denominators,
hidden suites, gate code, or promotion records.

## Scope

AFL-G0 covers:

- namespaced autonomous milestones using `AFL-*`;
- a machine-readable milestone contract;
- schemas for milestone contracts, gate results, and review-packet manifests;
- local semantic validation of the operational contract;
- a concrete plan for moving from repo-local self-verification to a genuinely
  protected CI boundary;
- canaries showing that good candidates pass and bad candidates fail.

## Non-Goals

AFL-G0 must not:

- implement SCP-1 semantic expressions;
- implement football-library capabilities;
- deploy product changes;
- claim independent verification while the gate remains in the same writable
  workspace;
- let a builder-authored `status: PROMOTED` field carry authority.

## Protection Levels

```text
SELF_VERIFIED
The contract and gate live in the repo. Useful for engineering discipline, but
not independent proof.

PROTECTED_CI
The builder can submit commits, but cannot edit the gate runner, hidden suite,
denominators, signing key, or promotion policy.

SIGNED_PROMOTION
The protected gate emits signed certificates or protected Git tags that identify
candidate commit, contract hash, suite hash, denominators, and artifact lock.
```

AFL-G0 starts in `SELF_VERIFIED` and is not fully promoted until it reaches at
least `PROTECTED_CI`.

## Required Canaries

AFL-G0 must eventually prove:

1. Known-good candidate passes.
2. Deliberately broken candidate fails.
3. Contract tampering fails.
4. Denominator reduction fails.
5. Deleted hidden cases fail.
6. Failed gate cannot publish or promote.
7. Builder cannot mint a valid promotion certificate.

The local repo can implement public canaries first. Protected canaries require
the external gate boundary.

The repo-local gate currently implements these public canaries:

- known-good operational contract passes;
- legacy milestone IDs fail;
- hard-gate tampering fails;
- denominator reduction fails;
- builder-owned protected authority fails;
- missing hidden suite blocks promotion.

## Promotion Certificate

A promoted milestone must be represented by a gate-issued certificate:

```yaml
program: priori-autonomous-football-language
milestone: AFL-01
candidate_commit: ...
contract_hash: ...
contract_schema_hash: ...
gate_runner_hash: ...
protected_suite_id: ...
protected_suite_hash: ...
denominators_hash: ...
registry_lock: ...
source_tree_hash: ...
result: PROMOTED
promoted_at: ...
promotion_signature: ...
```

A builder-authored status file may record progress, but it is not a promotion
authority.

## Minimum Acceptance Criteria

AFL-G0 is accepted only when:

1. Autonomous milestone IDs are namespaced as `AFL-G0`, `AFL-01`, ..., `AFL-12`.
2. The operational contract validates against schema and semantic checks.
3. Milestone dependencies are unique, valid, and acyclic.
4. Every numeric threshold declares stage/target class, numerator, denominator,
   and evaluation split.
5. Zero-tolerance global hard gates are not waivable.
6. Promotion rules and review-packet requirements exist.
7. The gate result schema distinguishes `PROMOTED`, `REJECTED`, `BLOCKED`, and
   `ERROR`.
8. The review packet schema requires provenance, denominators, reports, waivers,
   limitations, and artifact hashes.
9. The local verifier explicitly labels itself `SELF_VERIFIED`, not protected.
10. A plan exists to move the gate runner and protected suite outside builder
    authority.
11. A candidate packet generator exists for SCP-0E.1.
12. A local gate result and promotion-certificate generator exists.
13. The local gate blocks protected promotion when protected CI metadata, hidden
    suite hash, or signing key are absent.
