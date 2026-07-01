# Next Steps

If SCP-0 is approved:

1. Commit SCP-0 files and generated artifacts as a shadow registry foundation.
2. Keep the registry non-authoritative for runtime execution until a follow-up migration slice is reviewed.
3. Define the next SCP slice around controlled promotion of a small capability set, not the whole atlas.
4. Consider wiring registry projections into future product/AI catalog generation after proving no projection drift.
5. Continue to block product/AI exposure for `PROPOSED_ATLAS` items.

If SCP-0 is approved with required changes:

1. Keep the runtime unchanged.
2. Patch the registry schema/validation/projection issue only.
3. Rerun `make scp-0-verify` and the relevant unit tests.
4. Regenerate a narrow delta packet.

If SCP-0 is rejected:

1. Preserve the raw atlas import as source material only.
2. Do not migrate product/Hermes catalogs to registry-derived projections.
3. Identify whether rejection is about schema model, projection policy, runtime parity, or domain semantics before reopening implementation.
