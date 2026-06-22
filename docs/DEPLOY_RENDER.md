# Render Deployment: Manual Tactical Workbench Alpha

This deploys C0 as a single private Render Docker web service:

```text
React Workbench
Python host service
deterministic tactical runtime
host-owned handles/cache
canonical replay payloads
```

Hermes is disabled for C0:

```text
WORKBENCH_HERMES_ENABLED=0
```

Do not present manual interpretation as Hermes output.

## Data Bundle

The Docker image intentionally excludes `data/`. Runtime data is provisioned to
the persistent disk at `/var/data/dataset`.

Required layout after provisioning:

```text
/var/data/dataset/canonical/v1/...
/var/data/dataset/raw/idsse/figshare-28196177-v1/J03WOY/tracking.xml
/var/data/dataset/raw/idsse/figshare-28196177-v1/J03WPY/tracking.xml
/var/data/dataset/raw/idsse/figshare-28196177-v1/J03WQQ/tracking.xml
/var/data/dataset/raw/idsse/figshare-28196177-v1/J03WR9/tracking.xml
```

The manifest is `config/deploy/demo-data-manifest.json`.

Create and upload a bundle shaped like this:

```text
dataset/
  canonical/v1/...
  raw/idsse/figshare-28196177-v1/...
```

Then configure Render secrets:

```text
TQE_DATA_BUNDLE_URL=<private tar.gz URL>
TQE_DATA_BUNDLE_SHA256=<sha256 of tar.gz>
DEMO_ACCESS_TOKEN=<private alpha token>
```

The startup script verifies the bundle hash before unpacking and refuses to
serve if required files are missing.

## Render Service

Use `render.yaml` to create one Docker web service with:

```text
healthCheckPath: /healthz
disk mount: /var/data
```

Required environment:

```text
WORKBENCH_HERMES_ENABLED=0
TQE_DATA_ROOT=/var/data/dataset/canonical/v1
TQE_RAW_ROOT=/var/data/dataset/raw/idsse/figshare-28196177-v1
TQE_RUNTIME_ROOT=/var/data/runtime
TQE_CACHE_ROOT=/var/data/cache
TQE_DATA_MANIFEST_PATH=/app/config/deploy/demo-data-manifest.json
TQE_KNOWLEDGE_PACK_PATH=/app/generated/tactical-knowledge-pack.json
TQE_EXPECTED_KNOWLEDGE_PACK_SHA256=<generated pack sha>
```

`PORT` is supplied by Render.

## Access

Set `DEMO_ACCESS_TOKEN`. The service accepts:

```text
Authorization: Basic base64(any-user:token)
Authorization: Bearer token
https://service.onrender.com/?access_token=token
```

The query-token path sets an HTTP-only cookie and redirects to `/`.

## Readiness

```text
GET /healthz
GET /readyz
```

`/readyz` checks:

- frontend build exists;
- runtime/cache roots are writable;
- canonical demo data exists;
- required raw tracking XML exists;
- knowledge pack exists and matches the expected SHA when configured;
- approved and experimental recipes are loadable.

## Smoke Test

After deploy:

```bash
python scripts/cloud-smoke.py \
  --base-url https://<render-service>.onrender.com \
  --token "$DEMO_ACCESS_TOKEN"
```

Required proof:

- `/healthz` and `/readyz` pass;
- approved and experimental recipes validate;
- host confirmation is required;
- both recipes execute against real data;
- first result opens coordinate replay;
- second execution returns `CACHE HIT`.

## C1 Later

Only after the frontier gate passes:

```text
WORKBENCH_HERMES_ENABLED=1
```

The same deployment can then run the Hermes path behind the existing feature
flag. Keep manual mode available as fallback.
