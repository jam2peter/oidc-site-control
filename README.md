# OIDC Site Control

A narrow GitHub Actions control client for web deployment APIs authenticated
with **ephemeral GitHub OIDC** instead of a long-lived server credential.

> Status: `v0.1-beta`

OIDC Site Control mirrors a proven operational pattern:

```text
GitHub Issue command
  -> GitHub Actions
  -> ephemeral OIDC token
  -> allowlisted site-control API
  -> stage / apply / inspect / rollback
```

The product is a client/protocol package. Your hosting endpoint implements the
server side and decides which repositories, refs, workflows and targets it
trusts.

## Commands

The included Issue workflow exposes:

```text
/site health
/site deploy.inspect <root>/<slug>
/site deploy.stage <package> <root>/<slug>
/site deploy.apply <job_id>
/site deploy.rollback <deployment_id>
```

`deploy.stage` packages a versioned directory, rejects symlinks and unsafe
paths, computes SHA-256 for every file and a canonical manifest, then sends the
bundle with an audience-bound GitHub Actions OIDC identity.

## Quick start

1. Copy `site-control.example.json` to `site-control.json`.
2. Set repository variable `SITE_CONTROL_CONFIG` only if you use a different path.
3. Copy `templates/site-control.yml` to `.github/workflows/`.
4. Copy `scripts/site_control.py`.
5. Configure the server trust policy for your repository/workflow/ref.

No server API password is required in the normal workflow.

## Endpoint contract

The beta expects an HTTPS endpoint supporting query actions:

- `health`
- `deploy.stage`
- `deploy.apply&job_id=N`
- `deploy.inspect&target=...`
- `deploy.rollback&deployment_id=N`

The OIDC token is sent in the configured header (default
`X-Site-Control-GitHub-OIDC`).

See [Protocol](docs/PROTOCOL.md), [Architecture](docs/ARCHITECTURE.md) and
[Security](docs/SECURITY.md).

## Development

```bash
python3 -m py_compile scripts/site_control.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## License

MIT
