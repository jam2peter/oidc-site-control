# Architecture

OIDC Site Control separates identity from the operation being requested.

```text
GitHub Issue
  -> GitHub Actions
  -> GitHub OIDC token (ephemeral, audience-bound)
  -> configured HTTPS control endpoint
  -> server trust policy
  -> allowlisted deploy operation
```

For stage requests, the client creates a closed bundle inventory with SHA-256
per file, a canonical manifest and a deterministic idempotency key.

The server remains authoritative: it must independently validate OIDC,
authorization, targets and bundle integrity before changing runtime state.
