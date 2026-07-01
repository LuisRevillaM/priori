# Validation Output

Working directory:

`/Users/luisrevilla/Documents/priori`

Command:

```bash
make m1-2-gate-s2-verify
```

Status:

```text
pass
```

Output:

```text
{"status": "pass", "summary": {"fail": 0, "pass": 21}}
```

Important note:

The structural S2 gate passed because it records the sealed run. The sealed
evaluation report itself failed acceptance-level scores:

```json
{
  "supported_accuracy": 1.0,
  "ambiguous_accuracy": 0.75,
  "unsupported_accuracy": 0.75,
  "schema_valid_or_refusal_rate": 0.9375
}
```

Full row details:

`artifacts/agent-sealed-evaluation-report.json`
