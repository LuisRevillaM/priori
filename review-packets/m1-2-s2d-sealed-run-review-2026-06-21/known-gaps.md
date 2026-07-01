# Known Gaps

## S3 Blocked

Class: `requires_human_decision`.

The sealed run found failures. S3 should remain blocked until a reviewer decides
whether to open a focused correction or accept/reclassify the failures.

## Independent Reproduction

Class: `requires_full_repo`.

This packet is inspection-only. It includes source, diffs, prompt set, reports,
and summaries, but not the full repo, data, virtualenv, credentials, or network
environment required to rerun the model calls.

## Compiler Not Tuned Post-Sealed-Set

Class: `not_in_scope`.

No post-sealed-run compiler tuning is included. That is intentional to preserve
the integrity of the sealed result.
