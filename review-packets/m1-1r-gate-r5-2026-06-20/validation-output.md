# Validation Output

Packet created on 2026-06-20 from `/Users/luisrevilla/Documents/priori`.

## State Inspection

Command: `git rev-parse HEAD`

Status: pass

Output:

```text
12eb91a8d6940cb057efdc2753a2e59f1e847e53
```

Command: `git branch --show-current`

Status: pass

Output:

```text
codex/m1-1-s1-ir-binder
```

Command: `git status --short`

Status: pass

Output:

```text
```

Command: `git show --stat --oneline HEAD`

Status: pass

Output summary:

```text
12eb91a Implement M1.1R Gate R5 architecture proof
14 files changed, 768 insertions(+), 173 deletions(-)
```

Full commit patch: `diffs/commit-12eb91a.patch`.

## Gate And Test Validation

Command: `make m1-1-gate-r5-verify`

Status: pass

Output summary:

```text
Wrote artifacts/m1.1/gate-r5-verification-report.json
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 10}}
```

Report copy: `artifacts/m1.1/gate-r5-verification-report.json`.

Command: `make m1-1-gate-r4-verify`

Status: pass

```text
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 8}}
```

Command: `make m1-1-gate-r3-verify`

Status: pass

```text
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 9}}
```

Command: `make m1-1-gate-r2-verify`

Status: pass

```text
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 4}}
```

Command: `make m1-1-gate-r1-verify`

Status: pass

```text
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 19}}
```

Command: `make m1-1-gate-c-verify`

Status: pass

```text
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 10}}
```

Command: `make m1-1-gate-b-verify`

Status: pass

```text
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 14}}
```

Command: `make m1-1-gate-e-verify`

Status: pass

```text
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 21}}
```

Command: `make m1-1-gate-f-verify`

Status: pass

```text
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 13}}
```

Command: `make test`

Status: pass

```text
Ran 26 tests in 133.586s
OK
```

Command: `git diff --check`

Status: pass

Output: no whitespace errors.

## Reproducibility Note

The packet includes generated report JSONs, source snapshots, and diffs. Rerunning the commands requires the full repo, local Python environment, and canonical IDSSE data. This packet is inspection-only.
