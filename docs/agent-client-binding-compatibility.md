# Okta AI Agent Client Binding Compatibility

## Why this document exists

This repository was recovered during a temporary Okta compatibility period. Okta introduced a newer way to bind a user-facing OIDC client to an AI Agent, then temporarily reverted that behavior to give customers time to adapt. The newer binding model is expected to return.

The implementation on `main` must therefore be understood as the stable, currently compatible implementation, not as a permanent statement that the newer model will never exist.

## Current production-compatible model

The deployed ProGear application uses one governed **ProGear Sales Agent** and a fresh OIDC web application for interactive user sign-in.

The recovery sequence was:

1. Register the replacement AI Agent without relying on the temporarily unavailable native `signOnProvider` field.
2. Create a fresh OIDC web application through the Apps API.
3. Create an ID-token delegation link from the OIDC application to the replacement AI Agent.
4. Register separate public keys for the AI Agent workload and the OIDC web client.
5. Add the replacement agent to the existing Custom Authorization Server policies.
6. Create the four managed resource connections and activate the replacement agent.
7. Rewire Vercel and Render to the replacement identities and private keys.

The two keys remain independent:

- The **AI Agent workload key** signs backend ID-JAG and resource-token exchange requests.
- The **OIDC web-client key** authenticates authorization-code and refresh-token requests with `private_key_jwt`.

Only public JWK material is registered in Okta. Private JWK material remains in deployment secret storage.

## Why the older sign-on application was not reused

The original AI Agent was deleted accidentally. A surviving OIDC application is not proof that it is eligible for, or safely reusable with, a replacement agent. The recovery deliberately created a fresh OIDC application rather than inheriting potentially stale assignments, redirects, credentials, or binding state.

Do not delete or replace independent systems when changing the binding implementation. The following survive a client-to-agent binding migration:

- The four Custom Authorization Servers, scopes, access-policy rules, and audiences.
- FGA stores, models, and tuples.
- Okta Identity Governance workflows.
- Demo users and groups.
- Vercel and Render projects.
- Application behavior unrelated to sign-in and delegation.

## Future migration when the newer binding model returns

Do not restore an old repository snapshot wholesale. Start from the current stable `main` branch so the application retains its recovery, ID-token validation, observability, token-flow, FGA, CORS, and documentation fixes.

Create a feature branch, suggested name:

```text
future/native-agent-client-binding
```

Then change only the binding and provisioning boundary:

1. Confirm the exact API and Admin Console behavior enabled in the target Okta org.
2. Re-read the current Okta AI Agent API documentation. Do not assume an earlier preview schema is still exact.
3. Determine whether the supported flow uses `NEW_OIDC_APP`, `EXISTING_APP`, an agent-native client identity, or another released contract.
4. Verify the returned client ID, grant types, client-authentication method, assignments, redirect URIs, and token issuer/JWKS metadata.
5. Keep the AI Agent workload key separate from any web-client runtime key unless the released contract explicitly changes that responsibility.
6. Test in preview before changing production: sign-in, refresh, ID token to ID-JAG, ID-JAG to each domain token, Sarah denial, Mike authorization, FGA denial, and OIG approval.
7. Update the implementation guide and customer notebook in the same pull request.
8. Treat deletion of the compatibility OIDC app or delegation link as a separate cleanup change after production verification.

## Application-specific Org Authorization Server keys

The production OIDC application can use an application-specific Org Authorization Server signing key. The frontend therefore uses client-qualified discovery and verifies ID tokens against the client-qualified JWKS endpoint. Preserve this behavior unless testing proves the future binding model publishes a different supported discovery contract.

Relevant implementation:

- `packages/progear-sales-agent/src/lib/auth.ts`

## Historical restore points

Repository tags preserve both sides of the recovery:

- `pre-agent-binding-recovery-2026-08-10`: the previous `main` before the recovery pull request.
- `stable-delegation-link-binding-2026-08-10`: the working production-compatible state after the recovery pull request was merged.

Tags are historical evidence and rollback aids. They are not the recommended starting point for the future migration. The recommended starting point is the then-current `main` branch plus this document.

## Decision record

The compatibility implementation was chosen because it matched the behavior actually enabled in the tenant during the rollback period. The design isolates the binding mechanism so Okta's future update can be adopted without rebuilding authorization servers, FGA, OIG, domain policy, or the rest of the application.
