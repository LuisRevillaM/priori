# Validation Output

## Fresh Local Validation During Packet Assembly

| Command | cwd | Result | Evidence |
| --- | --- | --- | --- |
| `make n1d1-verify` | `/Users/luisrevilla/Documents/priori` | pass: `attestation_status=VERIFIED`, `blocking_reasons=[]` | `commands/make-n1d1-verify.txt` |
| `make n1i-verify` | `/Users/luisrevilla/Documents/priori` | pass: `summary.fail=0`, `summary.pass=10` | `commands/make-n1i-verify.txt` |
| `.venv/bin/python -m unittest tests.test_n1d1_attestation tests.test_workbench_beta0_contract` | `/Users/luisrevilla/Documents/priori` | pass: 14 tests | `commands/unittest-n1d1-workbench.txt` |

## Committed Report-Level Validation

`delivery/n1d/N1I_REPORT.md` records the broader N1I verification claims:

- `make n1d-verify`: pass `12/12`
- `make n1d1-verify`: `VERIFIED`
- `make n1c-verify`: pass `8/8`
- `make n1i-verify`: pass `10/10`
- backend unittest suite: 45 tests
- Render `/healthz`: 200
- runner disabled after export: `/api/n1f/status` returns 403

The Beta shell reports record their own Workbench acceptance and TypeScript verification. Those broader logs are included as reports, not rerun inside this packet.

## Blocked Or Not Rerun

- Live Render/Hermes origin rerun: not rerun during packet assembly; requires deploy credentials/environment and paid/model access.
- Full Workbench Playwright acceptance: not rerun during packet assembly; prior committed reports are included.
- Full repository test suite: not rerun during packet assembly; targeted backend tests were rerun.
