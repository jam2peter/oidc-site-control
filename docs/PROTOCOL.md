# Protocol

Default bundle format:

```text
OIDC_SITE_CONTROL_BUNDLE_V1
```

Each file carries:

- relative path;
- SHA-256;
- `gzip+base64` body.

The canonical manifest is SHA-256 over sorted records:

```text
path NUL sha256 LF
```

The idempotency key is derived from:

```text
target NUL source_commit NUL manifest_sha256
```

Expected API actions:

```text
GET  ?action=health
POST ?action=deploy.stage
GET  ?action=deploy.inspect&target=<root>/<slug>
POST ?action=deploy.apply&job_id=<id>
POST ?action=deploy.rollback&deployment_id=<id>
```

Successful responses use JSON and HTTP 200 or 201.
