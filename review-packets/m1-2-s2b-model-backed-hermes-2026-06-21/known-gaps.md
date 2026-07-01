# Known Gaps

## requires_full_repo

The packet is inspection-only. Reproducing the validation requires the full repo,
local canonical data, environment dependencies, and model API credentials.

## requires_credentials

S2B model-backed verification uses `OPENAI_API_KEY`. No secrets are included in
this packet.

## not_in_scope

S3 feedback-driven revisions, semantic diffs, result deltas, and immutable recipe
versioning are not implemented here.

## not_in_scope

No second tactical family, visual polish, or production infrastructure is added.
