# MCP Bridge 0.16 runtime changes

The ProGear A2A environment runs MCP Bridge `0.16.2`. The deployed adapter is built from the local source snapshot at:

`/Users/johnathan.campos/okta-agent-mcp-adapter-main-0.16-AUG172026`

That directory is a source snapshot, not a Git checkout. Preserve it until these changes are incorporated into the upstream 0.16 line.

## ProGear compatibility changes

- Accept Custom Authorization Server access tokens as A2A subject tokens.
- Configure receiver-side token validation from the resource connection rather than the caller's defaults.
- Resolve same-organization Custom Authorization Server JWKS correctly.
- Route Okta workload-principal identifiers to their imported Bridge agent records.
- Bind callable-agent exchanges to the target resource audience.

The main implementation and regression-test files are:

- `okta_agent_proxy/auth/cross_app_access.py`
- `okta_agent_proxy/auth/okta_validator.py`
- `okta_agent_proxy/proxy/handler.py`
- `tests/test_cross_app_sdk.py`
- `tests/test_okta_auth.py`
- `tests/test_proxy_agent_binding.py`

## Deployment and rollback

- Adapter task definition revision `6` contains the ProGear compatibility build.
- Adapter revision `5` remains the rollback point.
- Admin UI remains on task definition revision `1`.
- Both ECS services reached `COMPLETED` with their desired tasks healthy.

## Verification

- The 77 authentication, exchange, validation, and routing tests directly covering these changes pass.
- Live Sarah Sales flow: customer context succeeds; inventory exchange is denied; no inventory or notification receipt is created.
- Live Mike Manager flow: customer context, inventory write, and receipt-bound notification complete in order.
- The live token trace reports a two-actor delegation chain at the specialist hop.

The broader legacy adapter suite is not a clean release gate in this snapshot because many unrelated tests require unavailable environment configuration or rely on unpinned dependency behavior. Use the focused tests plus the live end-to-end checks above as the evidence for this compatibility build.
