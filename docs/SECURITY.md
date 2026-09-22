# Security

## No long-lived server credential

The normal workflow uses GitHub Actions OIDC and requires
`permissions.id-token=write`. There is no server password/API token input.

## Client boundary

The CLI supports only health, stage, inspect, apply and rollback. Targets must
match an allowlisted logical root plus slug. Stage bundles reject symlinks,
traversal, absolute paths and a reserved release marker.

## Server responsibility

A compatible server must independently validate:

- GitHub OIDC issuer and signature;
- exact audience;
- repository/owner/ref/workflow/event trust;
- token time bounds and replay policy;
- target authorization;
- bundle hashes and manifest;
- promotion/checkpoint/rollback rules.

Client-side checks are not the security boundary.
