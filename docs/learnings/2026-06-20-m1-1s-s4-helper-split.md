# Learning: Generic-Sounding Helpers Must Not Force Legacy Profiles

S3R4 external review approved S4 but identified one opening cleanup: `execute_plan_from_path()` sounded generic while forcing `legacy_m1_parity`.

The helper is now split:

- `execute_plan_from_path(...)` uses the executor default, which is generic.
- `execute_legacy_m1_plan_from_path(...)` explicitly preserves old M1.1 parity behavior.

The old experimental M1.1 proof currently returns rows only through the explicit legacy helper. Under the generic helper it executes but emits zero rows. That is an S4 signal, not a reason to reopen S3R: S4 must complete generic result production instead of relying on legacy result emission.
