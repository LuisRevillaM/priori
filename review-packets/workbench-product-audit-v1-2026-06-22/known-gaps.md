# Known Gaps

## requires_full_repo

- The reviewer cannot rerun Workbench tests from this packet alone.
- The reviewer cannot inspect every source line referenced by the audit without repository access.

## requires_credentials

- Hermes/ChatGPT/Codex subscription login and provider details are not included.
- Render deployment credentials and logs are not included.

## requires_network

- Live app behavior requires access to https://priori-integrated-alpha.onrender.com.

## not_in_scope

- This packet does not include raw DFL/IDSSE tracking data.
- This packet does not include product screenshots; the audit references existing repo artifact paths.
- This packet does not implement P0/P1 fixes.

## unknown

- Live app state may change after the packet is created if Render is redeployed.

