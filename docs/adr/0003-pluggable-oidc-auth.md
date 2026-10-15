# 0003. Pluggable OIDC authentication

Date: 2026-10-14
Status: accepted

## Context

We want a hosted identity provider (Auth0 or Clerk now, perhaps Microsoft Entra External ID later) so that we do not build password handling or MFA. The provider choice is still open.

## Decision

The API only verifies tokens. `JWKSVerifier` validates signature, issuer, audience and expiry against the provider's JWKS, caches keys, and refetches at most every 30 seconds when it sees an unknown key id, which handles rotation. Symmetric and unsigned algorithms are refused in this mode. Anything that speaks OIDC works with three settings: issuer, audience and JWKS URL.

Local development uses `AUTH_MODE=dev`, which accepts HS256 tokens signed with a local secret. Settings validation refuses this mode when `ENV` is staging or production.

Users are created on first sign-in, keyed by the token's `sub`. Admin rights come from a role claim in the token, named in settings.

## Consequences

Swapping provider changes configuration, not code. We store no credentials. We depend on the provider issuing a `kid` header and a role claim, which both Auth0 and Clerk can do but may need a small provider-side rule to add the role claim.
