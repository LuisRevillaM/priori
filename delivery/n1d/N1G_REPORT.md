# N1G — Agent-Authorable Destination Entry Capability

Status: `pass`
Generated: `2026-06-23T04:29:13+00:00`

## Scope

N1G makes the generic destination-entry measurement path visible and valid for agent-authored possession-start corridor plans. It does not expose the trusted recipe wrapper.

## Reconciliation

`delivery/n1d/N1B_N1F_RECONCILIATION.md` is the controlling causal note. Its conclusion is explanation 3: the executable capability context already marked `relation_destination_entry` authorable, but generated/model-visible knowledge was inconsistent. N1F then copied `relation_destination_entry_classification` from a recipe authoring contract and validation correctly rejected it as trusted-recipe-only.

## Current Local Hashes

- Capability context file SHA-256: `c054f8ef97160c4786b32722f96816b310816fec9f846e957d9f88fa79ef08ed`
- Tactical Knowledge Pack file SHA-256: `fbe155e29760a66843391c0e2ee7629d669d3c7888b1c1fcfc5e826deb078b5b`
- Tactical Knowledge Pack semantic SHA-256: `10cdddbbe5639c4786b38c314676ac088778eae2b42dcd484aa045f87311efa5`
- Runtime executor SHA-256: `05680f7cc478f8d10f39c286be12fc66ac1c254d0d2ef6200166c5b6c5fbd9ad`
- Workshop capability service SHA-256: `c3c96cf32ac09d7737938d59926bc5b43aff6e708b5073968d02a60c79a6d0ef`
- Knowledge-pack generator SHA-256: `b0cebf5d59824f06553c55c0a1b96757fbc48f0340bdb8a84aac6f1466617a57`

## Local Proof

- Manual plan: `artifacts/n1g/n1g-manual-possession-destination-entry-plan.json`
- Manual plan hash: `a33032d73ffeef73eef9c3b5fe728e2d57627c19e407cb5c04ced5a711d997a5`
- Model-profile validation: `True`
- Execution status: `pass`
- Rows: `14`
- Bound plan hash: `6e2d3cc1b800444a975b95f187f0a14fb17f1b4e84b3fb34c8ef5eb6ce956e08`
- Entry modes: `ENTERED_AFTER_OPEN, PRESENT_AT_OPEN`

## N1F Failure Preservation

- Existing N1F bundle present: `True`
- Existing N1F status: `failed_compile`
- Existing N1F used trusted wrapper: `True`

## Checks

- `pass` n1g.generic_entry_agent_authorable: relation_destination_entry is visible as the generic agent-authorable path.
- `pass` n1g.trusted_wrapper_not_agent_authorable: relation_destination_entry_classification remains trusted-recipe-only and is omitted from recipe authoring contracts.
- `pass` n1g.safe_composition_path_advertised: Hermes-visible catalog describes the possession-corridor destination-entry path.
- `pass` n1g.manual_generic_plan_validates_for_model: A manually authored model-profile plan validates through the generic path.
- `pass` n1g.manual_generic_plan_executes: The generic possession-start destination-entry plan executes over canonical data.
- `pass` n1g.entry_evidence_projected: Result evidence includes destination_entry_mode and destination_time_to_entry_seconds.
- `pass` n1g.destination_evidence_scoped_to_same_relation: Destination-entry evidence remains tied to the same witness relation selected by the corridor evidence.
- `pass` n1g.eq_pass_preserves_unknown: entry_status eq PASS preserves UNKNOWN.
- `pass` n1g.wrapper_plan_rejected_for_model: The same path using the trusted wrapper is still rejected for model callers.
- `pass` n1g.knowledge_pack_safe_surface: Generated tactical knowledge pack exposes the safe generic path and omits the trusted wrapper from authorable recipe summaries.

## Verification

- `make n1g-verify`: pass, 10/10.
- `make m1-2-gate-s2i-verify`: pass, 23/23.
- `make n1c-verify`: pass, 8/8.
- `.venv/bin/python -m unittest tests.test_m1_1_runtime tests.test_m1_1_binder tests.test_n1d1_attestation`: pass, 34 tests.
- `.venv/bin/python -m unittest tests.test_workbench_beta0_contract`: pass, 6 tests.
- `npm --prefix apps/workbench-alpha run test:acceptance`: pass, 16 E2E plus contract/fixture/unit checks.

Expected blocked before live rerun:

- `make n1d-verify`: fails only on stale N1D pins because N1G intentionally changed the knowledge-pack hashes and runtime source hash.
- `make n1d1-verify`: remains `BLOCKED` on the old N1F augmentation diff until a fresh faithful Hermes origin bundle exists.

## Faithful Rerun

Status: `pending deploy-side rerun`.

The next step is to deploy this commit, run the existing N1F faithful scoped Hermes path once, and preserve the result without prompt, synonym, vocabulary, MCP auth, model-config, or hero-question changes.

## Next Required Step

Deploy this capability-contract fix, rerun the faithful scoped Hermes origin path, and preserve either a VERIFIED n1d1 attestation or the new blocker. Beta 1C remains blocked until n1d1-verify is VERIFIED.
