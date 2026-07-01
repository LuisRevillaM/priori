# Validation Output

## Repository State

Command:

```bash
date +%F && git rev-parse HEAD && git branch --show-current
```

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Result:

```text
2026-06-22
25f29a146e475ef573dbf59da1901bec4d9c8253
codex/integrated-alpha
```

## JSON Validation

Command:

```bash
python -m json.tool generated/audits/workbench-state-machine.json >/dev/null &&
python -m json.tool generated/audits/workbench-ui-inventory.json >/dev/null &&
python -m json.tool generated/audits/workbench-loading-audit.json >/dev/null &&
python -m json.tool generated/audits/tactical-overlay-audit.json >/dev/null &&
python -m json.tool generated/audits/novel-composition-audit.json >/dev/null &&
python -m json.tool generated/audits/email-sendability-scorecard.json >/dev/null &&
python -m json.tool generated/audits/workbench-prioritized-backlog.json >/dev/null &&
echo 'json validation passed'
```

Result:

```text
json validation passed
```

## Full App Verification

Not rerun for this packaging step. The packet is inspection-only and packages the audit deliverables, not a full reproducible app environment.

