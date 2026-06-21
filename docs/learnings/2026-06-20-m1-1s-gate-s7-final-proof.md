# Learning: Final Proof Should Separate Generic Runtime From Legacy Compatibility

S7 should not pretend every M1-specific string has disappeared from the repository. Some strings remain in M1 primitive implementations and legacy compatibility trace rewriting because exact M1 parity is still required.

The useful final proof is narrower and more honest:

- generic result emission and generic declared-output tracing contain no plan predicate IDs;
- M1 parity uses the explicit `legacy_m1_parity` path;
- S4 and S6 generic plans reproduce from canonical data without generated/artifact caches;
- external review receives the distinction clearly instead of a blanket no-M1-string claim.
