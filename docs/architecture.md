# ProGear AI Agent Architecture

ProGear is a custom AI sales agent for a fictional basketball-equipment retailer. The hosted application combines four controls:

1. **Okta AI Agent Governance** gives the agent its own Workload Principal identity.
2. **Native MCP resources** publish OAuth Protected Resource Metadata and expose standard Streamable HTTP tools.
3. **FGA** adds the optional role-and-quantity decision for Inventory.
4. **Okta Identity Governance (OIG)** supplies the one human approval path.

For deployment steps, see [implementation-guide.md](./implementation-guide.md).

## System at a glance

```text
Employee
   │ signs in
   ▼
ProGear custom agent ───────► MCP /.well-known metadata
   │                             │ resource + Okta AS + scopes
   │ ID token + agent proof      ▼
   └──────────────────────────► Okta
                                 │ ID-JAG, then scoped token
                                 ▼
                    local token validation
                                 │
                   ┌─────────────┴─────────────┐
                   │ FGA off                   │ FGA on
                   │ coarse Okta scope         │ role + quantity
                   └─────────────┬─────────────┘
                                 │
                                 ▼
              Bearer token + native MCP tools/call
                                 │
             Inventory · Sales · Customer · Pricing
```

The browser is a Next.js app on Vercel. FastAPI and LangGraph run on Render. The protected MCP service is a separate Render deployment. The FastAPI backend does not read or mutate the repository's local `demo_store` for live actions.

## 1. The agent is a first-class identity

Okta registers the **ProGear Sales Agent** as a Workload Principal (`wlp…`). The employee and agent do not collapse into one identity:

- the employee remains the delegated subject;
- the agent authenticates with its own key;
- resource access names both parties;
- deactivating the Workload Principal prevents new exchanges;
- Okta can audit the user, agent, target resource, scope, and outcome.

Employee sign-in uses a separate OIDC web client linked to the governed agent. The OIDC client and Workload Principal have independent keys. See [agent-client-binding-compatibility.md](./agent-client-binding-compatibility.md).

## 2. The MCP resource tells the agent how it is protected

`backend/mcp/client.py` performs [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728) discovery before token exchange.

For example:

```text
MCP resource:
https://progear-mcp-servers-m2f3.onrender.com/inventory/mcp

Protected-resource metadata:
https://progear-mcp-servers-m2f3.onrender.com/
  .well-known/oauth-protected-resource/inventory/mcp
```

The metadata must:

- identify the exact MCP resource requested;
- advertise every requested scope;
- identify exactly one authorization server in the configured Okta org.

The backend fails closed if any check fails. It does not require four copied authorization-server IDs in its environment.

| MCP resource | Resource path | Scopes |
|---|---|---|
| ProGear Inventory MCP | `/inventory/mcp` | `inventory:read`, `inventory:write`, `inventory:alert` |
| ProGear Sales MCP | `/sales/mcp` | `sales:read`, `sales:quote`, `sales:order` |
| ProGear Customer MCP | `/customer/mcp` | `customer:read`, `customer:lookup`, `customer:history` |
| ProGear Pricing MCP | `/pricing/mcp` | `pricing:read`, `pricing:margin`, `pricing:discount` |

The MCP Bridge and its write-only authorization server belong to a separate integration. They are not in this hosted native Cross App Access path.

Each domain therefore has two complementary Okta control-plane records: a registered MCP server for standards-based discovery and inventory, and an `IDENTITY_ASSERTION_CUSTOM_AS` agent resource connection for native XAA/ID-JAG. The current MCP-server agent connection type is STS-based; replacing the authorization-server connection with it would change the security flow rather than merely rename the resource.

## 3. Native Cross App Access and ID-JAG

`backend/auth/multi_agent_auth.py` performs the two-step exchange:

1. **ID token → ID-JAG.** The Okta Org Authorization Server creates a signed delegation grant that preserves the employee subject and identifies the ProGear Workload Principal.
2. **ID-JAG → scoped access token.** The authorization server discovered from the MCP resource evaluates the employee, agent, and requested scope.

There is no partial success. If the requested scope is not grantable, the exchange fails rather than silently returning a weaker token.

`backend/auth/resource_token.py` independently verifies the access token before use:

- signature and signing key;
- issuer discovered from MCP metadata;
- expected resource audience;
- expiry;
- requested scopes;
- governed agent identity;
- delegated employee.

The real signed token is then presented directly to the MCP endpoint:

```http
POST /inventory/mcp
Authorization: Bearer <scoped access token>
Content-Type: application/json
Accept: application/json, text/event-stream

{
  "jsonrpc": "2.0",
  "id": "...",
  "method": "tools/call",
  "params": {
    "name": "update_inventory_quantity",
    "arguments": {
      "sku": "basketball",
      "quantity": 50,
      "operation": "increase"
    }
  }
}
```

The MCP server validates the Bearer token again and enforces the scope associated with the selected tool.

## 4. Request orchestration

The LangGraph path is:

```text
router
  → pre_exchange_guard
  → exchange_tokens
  → fga_check
  → approval_gate
  → process_agents
  → generate_response
```

- **router** selects the MCP resource and least-privilege scope.
- **pre_exchange_guard** stops vacation delegation and known Sales writes before ID-JAG.
- **exchange_tokens** discovers MCP metadata, performs ID-JAG, and validates the resource token.
- **fga_check** applies the advanced Inventory decision only when enabled.
- **approval_gate** creates the one Manager-to-`AIAgentOwners` OIG request.
- **process_agents** calls the actual protected MCP tool.
- **generate_response** distinguishes policy denial from infrastructure failure.

There is no local success fallback. If discovery, Okta, token validation, FGA, or the MCP resource fails, the action fails visibly.

## 5. Simple mode and FGA mode

FGA never grants a scope that Okta denied.

### FGA off: coarse-grained Okta policy

- Sales may read Inventory.
- Sales cannot obtain `inventory:write` and is told to contact a manager.
- A Manager or VP with a validated `inventory:write` token may submit any positive quantity.
- No OIG request is created.

### FGA on: role plus quantity

Production uses the authoritative `Clearance` value from the live Okta profile and signed Inventory token. The hosted demo also lets a live Manager compare Manager and VP outcomes in an isolated browser session:

| Level | Role | Read | Write 1–600 | Write 601+ |
|---:|---|---|---|---|
| 0 | Sales | Execute | Block | Block |
| 1 | Manager | Execute | Execute | Request AI Agent Owner approval |
| 2 | VP | Execute | Execute | Execute |

The version-controlled model is `backend/auth/fga_role_model.json`:

```text
can_read            = Sales or Manager or VP
can_request_change  = Manager
can_update_standard = Manager or VP
can_update_large    = VP
```

The backend supplies exactly one contextual role tuple for each check. It does not persist role membership in FGA. Production derives that tuple from live Okta. The hosted Manager/VP comparison is a clearly labeled, session-only overlay and cannot create a scope that Okta did not issue.

The `is_on_vacation` control is intentionally earlier than FGA because it answers whether delegation may begin at all. In the hosted demo its value and Mike's role preview are isolated by an opaque browser-tab ID in `sessionStorage`. Sarah cannot elevate.

## 6. Human approval

There is one approval path: a Level 1 Manager requests an Inventory increase of 601 or more while FGA is enabled.

1. FGA confirms the Manager may request the change but may not execute it.
2. The backend proves that its dedicated approval executor can obtain and validate `inventory:write` before creating a request.
3. OIG records the Manager as requester and assigns the task to `AIAgentOwners`.
4. A current AI Agent Owner approves or denies it from Access Requests.
5. The backend verifies the approver's live `AIAgentOwners` membership.
6. After approval, the dedicated executor mints a fresh token and calls the real Inventory MCP `update_inventory_quantity` tool.

Sales never creates an access request. The requester and approver remain separate: Mike requests as Manager, while a current `AIAgentOwners` member—such as Johnathan in a separate browser profile—approves. No dedicated Joe/VP login is required.

The OIG request ID and exact execution intent are retained in a file-backed ledger. Hosted deployments need a persistent disk for `APPROVALS_LEDGER_PATH`. The MCP tool currently has no idempotency-key argument, so durable end-to-end exactly-once execution requires a future tool contract or durable system-of-record transaction key.

## 7. Data and deployment boundary

The live MCP service owns the demo data. Its current store is in memory and resets on process restart. That is acceptable for this demo, but production needs durable storage.

| Component | Platform |
|---|---|
| Next.js frontend | Vercel |
| FastAPI orchestration backend | Render |
| ProGear protected MCP resources | Render |
| Employee and agent identity, token exchange | Okta |
| Fine-grained Inventory decision | FGA |
| Human approval | Okta Identity Governance |

The old `packages/progear-sales-mcp-server` directory is a legacy standalone sample and is not the live protected resource.

## 8. What the UI proves

- **`/architecture`** shows MCP discovery, ID-JAG, scoped tokens, native `tools/call`, the agent kill switch, and optional FGA.
- **`/tokens`** shows the well-known URL, MCP resource, discovered authorization server, signed token chain, resource validation, and final business decision.
- **`/fga`** shows the opt-in role-and-quantity policy and human-in-the-loop route.

A scoped token is necessary, not sufficient. A write executes only after every applicable control passes and the native MCP tool succeeds.

## Further reading

- [Okta: Secure MCP servers](https://developer.okta.com/docs/api/secures-ai/mcp-servers)
- [Okta: AI Agent token exchange](https://developer.okta.com/docs/guides/ai-agent-token-exchange/authserver/main/)
- [RFC 9728: OAuth 2.0 Protected Resource Metadata](https://www.rfc-editor.org/rfc/rfc9728)
- [IETF ID-JAG](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant)
- [Cross App Access](https://xaa.dev/)
