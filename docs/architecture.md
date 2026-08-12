# ProGear AI Agent Architecture

This document explains how the ProGear Sales AI demo actually works, end to end, based on the live code in this repo. It's written for someone who has never seen this codebase but is technically comfortable with OAuth, authorization, and agent systems.

ProGear ("CourtEdge ProGear") is a fictional basketball-equipment retailer. The demo is an AI sales/shopping assistant secured by three cooperating systems:

1. **Okta AI Agent Governance**: gives the AI its own identity and exchanges the user's login for narrowly-scoped, short-lived access tokens (ID-JAG).
2. **FGA**: a second, finer-grained authorization layer that combines the signed clearance role with the requested inventory quantity.
3. **Okta Identity Governance (OIG)**: routes high-impact actions (large inventory writes) to a human approver instead of letting the agent execute them immediately.

For deployment instructions, see [implementation-guide.md](./implementation-guide.md).

---

## System overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser: Next.js frontend (Vercel)                                 │
│  User signs in via Okta (NextAuth.js). Chat UI posts to backend.    │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ Authorization: Bearer <user ID token>
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Backend: FastAPI (Render): backend/api/main.py                     │
│                                                                       │
│  Orchestrator (LangGraph, backend/orchestrator/orchestrator.py)     │
│  router → exchange_tokens → fga_check → approval_gate →             │
│           process_agents → generate_response                       │
│                                                                       │
│   Sales domain  Inventory domain  Customer domain  Pricing domain  │
│   (internal components; each uses the raw Anthropic SDK)           │
└───────────┬───────────────────────┬──────────────────────┬──────────┘
            │                       │                      │
            ▼                       ▼                      ▼
   Okta Org AS + 4 Custom      FGA                      Okta Identity
   Authorization Servers       (ReBAC + ABAC             Governance (OIG)
   (ID-JAG token exchange,     check on inventory)        (Access Requests for
   RSA/JWT-Bearer auth)                                    large writes)
```

The backend never talks to a database: it reads/writes a JSON file (`backend/data/demo_store.py` over `initial_data.json` / `live_data.json`) that simulates ProGear's business data.

---

## 1. Identity: the AI agent has its own Okta identity

The AI is not "the user with extra code around it." It is registered in Okta as a **Workload Principal**, a distinct machine identity whose entity ID starts with `wlp...`. The compatibility model active in this tenant uses a separate `0oa...` OIDC web app for employee sign-in and links its ID tokens to the governed agent for delegation. The Vercel web runtime authenticates authorization-code and refresh-token requests with a dedicated `private_key_jwt` key (`OKTA_OIDC_PRIVATE_KEY`), while the backend uses the agent's workload key for ID-JAG exchanges. Neither path uses a shared client secret. The production deployment uses one shared `OKTA_AI_AGENT_ID` / `OKTA_AI_AGENT_PRIVATE_KEY` identity across its internal domain configurations; the per-domain environment variables are optional code-level overrides, not four required Okta AI Agent registrations. See [Okta AI Agent Client Binding Compatibility](./agent-client-binding-compatibility.md).

Because the agent's identity is separate from the human user's identity, every access decision downstream can be phrased as "is the ProGear Sales Agent, acting on behalf of User Y, allowed to do Z?" This is the shape Okta's AI Agent Governance and the audit trail in the Okta System Log are built around.

The application has four internal business-domain components and four Custom Authorization Server boundaries, but Okta governs one ProGear Sales Agent identity.

Deleting the Workload Principal invalidates the agent identity even if a previously associated OIDC app still exists as a separate application. Current registration APIs support both a fresh `NEW_OIDC_APP` binding and an eligible `EXISTING_APP` binding. The recommended clean recovery uses a fresh app, while preserving the surviving app for comparison until the replacement works end to end. See [Recovering from an Accidentally Deleted AI Agent](./implementation-guide.md#recovering-from-an-accidentally-deleted-ai-agent) in the Implementation Guide for the full procedure.

---

## 2. Token exchange: two-step ID-JAG

The core mechanism is the **Identity Assertion JWT Authorization Grant (ID-JAG)**, implemented in `backend/auth/multi_agent_auth.py`. It is a two-step exchange, and both steps run for each resource domain required by the request:

Before Step 1, the backend verifies the employee's OIDC ID token and reads the employee's live `clearance_level`, derived Manager status, and vacation status from Okta. Vacation True stops all delegated work here, regardless of resource or action. Otherwise, a known-ineligible inventory write also stops here: Sarah is told to contact her manager, and no delegated token is requested. In simple mode, Mike's 601+ write likewise stops with VP guidance. Reads and eligible writes continue.

**Step 1: ID token → ID-JAG (at the Org Authorization Server)**
The user's Okta ID token (from their NextAuth login) is exchanged for an ID-JAG assertion. This assertion names *both* the user and the agent: "Agent X is acting on behalf of User Y." This happens at Okta's Org AS (configured via `OKTA_MAIN_AUTH_SERVER_ID`), using the agent's RSA keypair, not the user's credentials.

**Step 2: ID-JAG → scoped access token (at a per-domain Custom Authorization Server)**
The ID-JAG assertion is then exchanged for an actual access token at the Custom Authorization Server for the specific business domain the request needs (Sales, Inventory, Customer, or Pricing). This is where Okta's access policies evaluate whether this user and agent may receive the requested resource scope. The resulting access token is scoped, short-lived, and, for Inventory, carries the live `Clearance`, `Manager`, and `Vacation` claims. `Clearance` feeds FGA; `Manager` is the synchronized human-readable role fact; vacation has already been enforced before delegation.

**No down-scoping.** If any one of the requested scopes isn't grantable to this user under this agent's policy, Okta doesn't silently drop that scope and grant the rest: the *entire* exchange fails with `access_denied`. `multi_agent_auth.py` treats `no_matching_policy`, `access_denied`, and Okta's generic "Policy evaluation failed" 401 as the same outcome and returns a clean `access_denied` result rather than a partial grant or a raw error.

### The four resource domains and their Custom Authorization Servers

Each internal domain configuration selects its own Custom Authorization Server and scope set, all defined in `backend/auth/agent_config.py`. In the production deployment, these configurations use the same ProGear Sales Agent workload identity:

| Domain | Scopes | Authorization server environment variable |
|---|---|---|
| Sales | `sales:read`, `sales:quote`, `sales:order` | `OKTA_SALES_AUTH_SERVER_ID` |
| Inventory | `inventory:read`, `inventory:write` | `OKTA_INVENTORY_AUTH_SERVER_ID` |
| Customer | `customer:read`, `customer:lookup`, `customer:history` | `OKTA_CUSTOMER_AUTH_SERVER_ID` |
| Pricing | `pricing:read`, `pricing:margin`, `pricing:discount` | `OKTA_PRICING_AUTH_SERVER_ID` |

The code supports optional per-domain agent ID / private key overrides (`OKTA_AI_AGENT_[TYPE]_ID`, `OKTA_AI_AGENT_[TYPE]_PRIVATE_KEY`) for other deployment patterns. When those variables are absent, every domain uses the shared `OKTA_AI_AGENT_ID` and `OKTA_AI_AGENT_PRIVATE_KEY`, which is the one-agent production model used here.

If the Okta AI SDK or agent credentials aren't configured, `multi_agent_auth.py` can return a clearly marked demo-mode result for local read-only UI work. Demo tokens are never accepted for inventory writes; a write requires a real signed resource token.

---

## 3. Orchestration: LangGraph + raw Anthropic SDK

`backend/orchestrator/orchestrator.py` uses the real `langgraph` package (`from langgraph.graph import StateGraph, END`; `langgraph>=0.2.0` is a genuine dependency in `backend/requirements.txt`, not just a label) to define the request pipeline as an explicit graph:

```
router → pre_exchange_guard → exchange_tokens → fga_check → approval_gate → process_agents → generate_response
```

- **router**: an LLM call (Claude, via the raw Anthropic SDK) decides which internal domain components are relevant to the user's message and, critically, which *specific scope* is needed. For example, "what's our basketball stock?" needs `inventory:read`, while "add 500 basketballs" needs `inventory:write`. If the LLM call or its JSON parsing fails, a keyword-matching fallback (`AGENT_KEYWORDS` / `SCOPE_DEFINITIONS`) selects the domain and scope instead.
- **pre_exchange_guard**: first applies the employee's live vacation status globally. Vacation True stops every selected resource before ID-JAG. When vacation is False, the same node applies the Okta clearance to known inventory-write boundaries: Sales writes stop with manager guidance in both modes; a Manager 601+ write stops in simple mode but continues to the FGA/OIG path when FGA is enabled.
- **exchange_tokens**: runs the two-step ID-JAG exchange for every selected resource domain, then independently verifies the resource token's signature, issuer, audience, expiry, governed-agent identity, delegated user, and requested scopes in `backend/auth/resource_token.py`.
- **fga_check**: the FGA layer described below. It runs after validation because the Inventory Custom Authorization Server's access token carries the authoritative `Clearance` claim.
- **approval_gate**: the OIG human-in-the-loop check, described below.
- **process_agents**: invokes the internal domain components that survived both authorization layers.
- **generate_response**: synthesizes a final answer, explicitly distinguishing "access denied" (policy said no) from "system error" (Okta/infra failure) from "no response" (nothing was needed/available), so the UI and the user never conflate a security decision with a bug.

The internal domain classes (`backend/agents/sales_agent.py`, `inventory_agent.py`, `customer_agent.py`, `pricing_agent.py`) subclass `BaseAgent` (`backend/agents/base_agent.py`). These are orchestration components behind the one governed ProGear Sales Agent, not four separate user-facing or Okta-registered agent identities. Components that need model reasoning call the **raw asynchronous Anthropic SDK directly** (`anthropic.AsyncAnthropic(...).messages.create(...)`), not LangChain's LLM wrapper. Inventory reads and writes return exact resource results without an LLM paraphrase. `langchain` is present in `requirements.txt` only because `langgraph` needs it as a transitive dependency.

The model name comes from `LLM_MODEL_NAME` (default `claude-sonnet-4-6`); the key from `ANTHROPIC_API_KEY`.

---

## 4. FGA: the second authorization layer

Okta authenticates the human and agent, grants a coarse inventory scope, and signs the user's live `Clearance` value into the inventory access token. FGA, implemented in `backend/auth/fga_client.py`, answers the next question: "given this role and quantity, may this request execute directly?" It is a separate authorization call against the hosted FGA store. In production the FGA contextual tuple comes from that trusted live context. The hosted demo can apply a short-lived server-side overlay at the role and delegation policy gates so a presenter can demonstrate each outcome without changing the shared Okta users or their signed token claims.

The presentation UI makes this advanced path opt-in. With **Simulate FGA** off, `POST /api/chat` applies the live Okta role matrix and denies any request that needs a higher role instead of creating an OIG request. With it on, the request includes `simulate_fga: true` plus an opaque demo-session id, enabling the hosted decision and the one approval route. The ID is a random UUID in the tab's `sessionStorage`, not a cookie: navigation, refresh, and sign-out preserve it, while closing the tab ends the client session. The backend keys the overlay by the validated Okta subject and that browser-tab id and expires inactive records after `DEMO_SESSION_TTL_SECONDS` (four hours by default). One engineer's controls therefore cannot change another engineer's session, even when they share Sarah or Mike credentials. The overlay also cannot manufacture a denied Okta scope because token exchange and independent resource validation still occur first.

### The model

`clearance_level` means role, not item sensitivity: 0 = Sales, 1 = Manager, 2 = VP. `is_a_manager` is synchronized from that role; `is_on_vacation` is the earlier delegation gate and is not duplicated as an FGA relation. The version-controlled FGA model is `backend/auth/fga_role_model.json`:

```
type user

type inventory_system
  relations
    define role_sales:          [user]
    define role_manager:        [user]
    define role_vp:             [user]
    define can_read:            role_sales or role_manager or role_vp
    define can_request_change:  role_manager
    define can_update_standard: role_manager or role_vp
    define can_update_large:    role_vp
```

| Request | FGA relation | Direct execution | If requester is below the tier |
|---|---|---|---|
| Inventory read | `can_read` | Level 0+ | Deny if no valid role |
| Write 1–600 units | `can_update_standard` | Level 1+ | Sales is denied; no request |
| Write 601+ units | `can_update_large` | Level 2 | Manager may request VP approval; Sales is denied |

Sales, Customer, and Pricing agents have no FGA model today and always pass through. FGA currently only gates Inventory.

### The role is contextual

The backend maps the validated `Clearance` token claim to exactly one contextual tuple (`role_sales`, `role_manager`, or `role_vp`). The role is not persisted as a mutable copy in FGA, so an Okta role change applies on the next token exchange.

### The check itself

`backend/auth/inventory_policy.py` parses quantity and selects the required FGA relation. `check_inventory_access_via_fga()` checks `inventory_system:warehouse` with the contextual role tuple. The orchestrator records both `fga_checks` and a separate `authorization_decisions` record. `/tokens` therefore shows the truthful sequence: token issued, token validated, business action allowed/blocked/pending, and finally executed or not executed.

**Fail-closed by design.** If the FGA client isn't configured or the API call fails, `check_inventory_access_via_fga()` denies access by default rather than allowing it. Authorization for inventory writes and reads depends on FGA actually answering.

---

## 5. Governance: human-in-the-loop approval for large writes

`backend/services/factory.py` builds an `ApprovalService` wired to a real **Okta Identity Governance (OIG) Access Request** flow. There is one approval path: a Level 1 Manager requesting 601+ units needs a Level 2 VP. Level 0 Sales writes are denied without creating a request.

The orchestrator's **approval_gate** node fires only when all of the following are true:
1. The request needs `inventory:write`.
2. The requester is a Manager.
3. The parsed quantity is greater than 600 and FGA confirms `can_request_change`.

When triggered, it first mints and validates a short-lived execution token using the same path needed after approval. If that preflight fails, no OIG request is created. It then builds an `Intent` containing the required approver role and level and creates a real OIG request. The signed-in Manager's Okta subject is sent as `requesterUserIds`; the API-token owner remains the request creator, preserving both identities in OIG. The approver sees a concise summary—requester, action, threshold reason, required role, and governed agent—while the machine-readable execution intent stays in the backend's file-backed ledger. Existing requests that used the older fenced-JSON justification remain readable for compatibility. After OIG approval, `OktaRoleResolver` retrieves the approver's current profile and the service fails closed unless the approver meets the required level.

**Resolution happens two ways:**
- **Foreground fast path**: `GET /api/approvals/{request_id}` (polled by the frontend) calls `ApprovalService.execute_if_approved()`, which checks OIG's current decision and executes the write immediately if approved. An eight-second per-request cache collapses duplicate polls from multiple tabs, and OIG 429 responses become a retrying status rather than a customer-facing 502.
- **Background poller**: `backend/api/main.py` discovers open demo requests once at startup, then polls only request IDs registered in its file-backed ledger every `APPROVAL_POLL_INTERVAL_SECONDS` (default 120s, with exponential backoff on errors). It no longer lists and rechecks every historical resolved tenant request on each cycle.

Execution is idempotent while the ledger is retained: a JSON ledger stores each request's machine-readable intent and tracks which OIG request IDs have already been executed. It also enforces a bounded retry count (3 attempts), so a flaky write doesn't retry forever and an already-executed request never double-applies. Local development defaults to `backend/data/approvals_ledger.json`. A hosted deployment must point `APPROVALS_LEDGER_PATH` at durable storage; on Render, attach a persistent disk at `/var/data` and use `/var/data/approvals_ledger.json`. Without that mount, deploys and restarts can discard pending intent and idempotency state.

When approval completes, `backend/services/service_token.py` performs a real
Okta `client_credentials` exchange authenticated by the dedicated ProGear
Approval Executor's `private_key_jwt`. The executor has only
`inventory:write`, and its token lasts five minutes. The Inventory boundary
validates that signed token before the idempotent store mutation. The AI Agent
workload principal remains the identity for delegated user requests. OIG
preserves the requester, human-readable action, governed-agent label, and
approval decision; the backend ledger preserves the exact FGA check and
execution intent. Together they retain the full approval chain without putting
internal JSON in the approver's request card. A placeholder token is never
accepted.

---

## 6. The demo data layer

`backend/data/demo_store.py` is the only place business data lives; there's no database. It loads `backend/data/initial_data.json` (the seed dataset: 90 inventory SKUs across 8 categories, 34 customers) into `backend/data/live_data.json` on first boot if that file doesn't exist, and thereafter reads/writes `live_data.json` directly. `live_data.json` is **gitignored**: it's a runtime snapshot regenerated from the seed file, never something to commit or hand-edit. Resetting the demo means deleting `live_data.json` (or calling the store's reset method) so it re-derives from `initial_data.json`.

---

## 7. Known, honest limitation: the MCP server isn't in the live path yet

`packages/progear-sales-mcp-server` is a separately deployable Express sample. **The internal domain components in this backend do not call it.** `_invoke_agent()` instantiates the domain classes directly, and they read/write `demo_store` in-process. There is no network round-trip to the MCP server today. The sample also contains explicit local-demo authentication bypasses, so it must be hardened before protecting real data. The live in-process resource boundary is the customer-demo security boundary: it fails closed, validates the Okta JWT cryptographically, and requires the final business decision before data access. Describing the current call as a live MCP round-trip—or the standalone sample as production-ready—would be inaccurate.

---

## 8. Audit trail

Every ID-JAG exchange that is actually attempted, whether granted or denied, produces evidence in **Okta's System Log**, a queryable, tamper-evident stream that exists independently of this app's own logging. A pre-exchange clearance denial correctly has no ID-JAG event; the app records that stopped decision after the employee's verified sign-in step. `GET /api/okta/logs` in `backend/api/main.py` queries the real Okta System Log API (`/api/v1/logs`, authenticated with `OKTA_API_TOKEN`) for `token.grant`/token-exchange events and reshapes them into a consistent shape: which agent (actor) acted, on behalf of which user (target), against which Custom Authorization Server, and which scopes were requested versus actually granted. This is Okta's own audit record, not a log table this app maintains.

**Honest limitation:** the endpoint above is real and callable, but the frontend page that rendered it (`OktaSystemLog`, on the now-removed `/how-it-works` page) is gone. There's currently no UI surfacing this data, only the API.

---

## 9. Cutting off access

Three independent mechanisms can stop or constrain new agent actions. The distinction between **stopping new token issuance** and **revoking a token already issued** matters operationally.

- **Deactivate the Workload Principal.** An admin can deactivate the AI agent's identity in Okta directly. The next ID-JAG exchange attempt for that agent fails outright, so the agent cannot obtain a new resource access token. A resource token issued before deactivation remains governed by its short expiry and the resource server's revocation policy; keep token lifetimes narrow and validation strict.
- **Mark the employee on vacation.** `is_on_vacation=true` stops the agent before it requests an ID-JAG for any resource. This is a user-context containment control, useful when the employee is away or their sign-in credentials may have been exposed. It does not deactivate the agent for everyone.
- **Change the production role.** The role derived from live `clearance_level` is evaluated at request time, so an administrator or lifecycle change in Okta drives the next production decision without a redeploy or mutable role copy in FGA.
- **Simulate role or vacation safely.** `POST /api/admin/demo-toggle` changes only the signed-in browser tab's short-lived demo context; a role change synchronizes its derived `is_a_manager` value. `/api/admin/demo-reset` restores that session's starting values. The backend keys the context by a cryptographically validated Okta subject plus an opaque browser-session id, and never writes these controls to the shared Okta profile (`backend/auth/demo_admin.py`).

---

## 10. Deployment topology

Both halves deploy from this single repo with `main` as the single production source branch:

| Component | Platform | Detail |
|---|---|---|
| Frontend | Vercel | `packages/progear-sales-agent` (Next.js). Live at `https://progear-sales-aiagent.vercel.app`. |
| Backend | Render | Service name "ProGearSalesAI", `rootDir: backend`. The backend URL is intentionally not published. |

---

## 11. See it live, interactively

One page in the running frontend exists specifically to make this architecture visible and explorable, beyond this document:

- **`/architecture`** presents two compact technical views. The topology graph connects the employee, ProGear Workload Principal, Okta ID-JAG exchange, Resource Authorization Server, audit trail, and four protected business resources. Its paths are deliberately routed to avoid collisions; the simulated kill switch visibly cuts the agent-to-Okta exchange. The sequence diagram shows the same exchange in time order with short protocol labels and a single detail line. When the shared **Simulate FGA** preference is enabled, the Inventory path and sequence add the role + quantity decision; when it is off, that advanced node and lane disappear.

There's also a **`/tokens`** page showing each signed artifact, resource validation, final business decision, and pending approval status. It explicitly teaches that a scoped token being issued is not the same as a write being authorized or executed.

---

## Further reading

- [Implementation Guide](./implementation-guide.md): step-by-step deployment instructions
- [Okta AI Agent Documentation](https://developer.okta.com/docs/guides/ai-agent-governance/): official Okta docs
- [IETF ID-JAG Specification](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant): Identity Assertion JWT Authorization Grant draft
- [Cross App Access](https://xaa.dev/): approachable overview of the cross-domain delegation pattern
