# Beta 1C Live Attested Workbench Review Packet

Packet type: `inspection_packet_only`

This packet is for external review of Beta 1C: exposing the verified N1I Hermes-authored experimental composition in Workbench without letting arbitrary or drifting model drafts claim `HERMES_NOVEL_COMPOSITION`.

## Review Scope

Commits under review:

- `3caa4b6` Expose attested Hermes novel composition
- `fd09735` Route attested Hermes hero through scoped product path
- `5ca720b` Expose verified attested Hermes hero plan
- `b4e1028` Include N1D attestation artifacts in runtime image

Live service tested:

- `https://priori-integrated-alpha.onrender.com`
- Render deploy commit expected: `b4e102857de462673704bfb2f46735f4fba05c55`

## What Is Real

- The Workbench can expose the exact N1I-attested Hermes-origin plan as `HERMES_NOVEL_COMPOSITION`.
- The host verifies committed N1D.1 attestation artifacts before returning that provenance.
- The attested plan is locked to `match_ids=["J03WOY"]`, `periods=["firstHalf"]`, `perspective_team_role="home"`.
- Live API smoke proved: interpret -> validate -> confirm -> execute -> inspect/replay.
- The live path returned 14 real results and a 101-frame replay for the first result.

## What Is Not Claimed

- This does not claim every fresh Hermes draft is novel or executable.
- This does not claim arbitrary scope changes are supported for the attested plan.
- This does not claim a fresh model call will reproduce the byte-identical N1I AST every time.
- This does not prove first-run cache miss in the current deploy; the same deterministic plan was already executed by N1I, so the live product smoke correctly showed cache `HIT`.

## Review Map

- `route-smokes/live-beta1c-smoke.json` - live deployed API evidence.
- `artifacts/n1d1-attestation.json` - committed verified N1D.1 attestation.
- `artifacts/n1f-origin-bundle.json` - Hermes-origin bundle containing the submitted draft and host-augmented plan.
- `diffs/beta1c-implementation.diff` - implementation diff for reviewed files.
- `source-excerpts/app_service.py` - provenance/attestation gate and product route.
- `source-excerpts/App.tsx` and `source-excerpts/workbenchState.ts` - UI flow, scope lock, and runnable-state behavior.
- `commands/n1-proof-gates.txt` - N1D/N1D.1/N1I verification output.
- `commands/backend-contract-tests.txt` - backend contract test output.
- `validation-output.md` - summarized validation.
- `known-gaps.md` - explicit limits and residual risk.

## Reviewer Questions

1. Is the distinction between committed attested Hermes origin and fresh unverified Hermes drafts honest enough for Beta 1C?
2. Is locking the exact attested plan to `J03WOY / firstHalf / home` acceptable for the preview?
3. Is the cache `HIT` explanation acceptable given the protected N1I runner already executed the same deterministic plan?
4. Are the Docker artifact copies sufficient to make the deployed attestation gate auditable?
