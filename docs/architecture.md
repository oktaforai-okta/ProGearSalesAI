# ProGear AI Agent Architecture

This document explains how the ProGear Sales AI demo actually works, end to end, based on the live code in this repo. It's written for someone who has never seen this codebase but is technically comfortable with OAuth, authorization, and multi-agent systems.

ProGear ("CourtEdge ProGear") is a fictional basketball-equipment retailer. The demo is an AI sales/shopping assistant secured by three cooperating systems:

1. **Okta AI Agent Governance**: gives the AI its own identity and exchanges the user's login for narrowly-scoped, short-lived access tokens (ID-JAG).
2. **Auth0 FGA**: a second, finer-grained authorization layer that checks live relationships, clearance, and context (e.g., "is this person on vacation right now?") that Okta's role-based check doesn't know about.
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
   Okta Org AS + 4 Custom      Auth0 FGA                Okta Identity
   Authorization Servers       (ReBAC + ABAC             Governance (OIG)
   (ID-JAG token exchange,     check on inventory)        (Access Requests for
   RSA/JWT-Bearer auth)                                    large writes)
```

The backend never talks to a database: it reads/writes a JSON file (`backend/data/demo_store.py` over `initial_data.json` / `live_data.json`) that simulates ProGear's business data.

---

## 1. Identity: the AI agent has its own Okta identity

The AI is not "the user with extra code around it." It is registered in Okta as a **Workload Principal**, a distinct machine identity whose entity ID starts with `wlp...`. The same `wlp...` identifier is the client ID of the OIDC app Okta permanently binds when **direct User access** is enabled. The Vercel web runtime authenticates its authorization-code and refresh-token requests with a dedicated `private_key_jwt` key (`OKTA_OIDC_PRIVATE_KEY`), while the backend uses its workload key for ID-JAG exchanges. Neither path uses a shared client secret. The production deployment uses one shared `OKTA_AI_AGENT_ID` / `OKTA_AI_AGENT_PRIVATE_KEY` identity across its internal domain configurations; the per-domain environment variables are optional code-level overrides, not four required Okta AI Agent registrations.

Because the agent's identity is separate from the human user's identity, every access decision downstream can be phrased as "is the ProGear Sales Agent, acting on behalf of User Y, allowed to do Z?" This is the shape Okta's AI Agent Governance and the audit trail in the Okta System Log are built around.

The application has four internal business-domain components and four Custom Authorization Server boundaries, but Okta governs one ProGear Sales Agent identity.

Deleting the Workload Principal invalidates the agent identity even if a previously associated OIDC app still exists as a separate application. Current registration APIs support both a fresh `NEW_OIDC_APP` binding and an eligible `EXISTING_APP` binding. The recommended clean recovery uses a fresh app, while preserving the surviving app for comparison until the replacement works end to end. See [Recovering from an Accidentally Deleted AI Agent](./implementation-guide.md#recovering-from-an-accidentally-deleted-ai-agent) in the Implementation Guide for the full procedure.

---

## 2. Token exchange: two-step ID-JAG

The core mechanism is the **Identity Assertion JWT Authorization Grant (ID-JAG)**, implemented in `backend/auth/multi_agent_auth.py`. It is a two-step exchange, and both steps run for each resource domain required by the request:

**Step 1: ID token → ID-JAG (at the Org Authorization Server)**
The user's Okta ID token (from their NextAuth login) is exchanged for an ID-JAG assertion. This assertion names *both* the user and the agent: "Agent X is acting on behalf of User Y." This happens at Okta's Org AS (configured via `OKTA_MAIN_AUTH_SERVER_ID`), using the agent's RSA keypair, not the user's credentials.

**Step 2: ID-JAG → scoped access token (at a per-domain Custom Authorization Server)**
The ID-JAG assertion is then exchanged for an actual access token at the Custom Authorization Server for the specific business domain the request needs (Sales, Inventory, Customer, or Pricing). This is where Okta's access policies evaluate whether this user and agent may receive the requested resource scope. The resulting access token is scoped, short-lived, and, for Inventory, carries `Vacation` and `Clearance` claims that feed the FGA layer described below. A compatibility `Manager` claim may still exist in Okta, but application authorization does not read it.

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

If the Okta AI SDK or the agent credentials aren't configured, `multi_agent_auth.py` falls back to a demo mode that fabricates a plausible-looking token result, useful for running the UI without a live Okta org, but worth knowing it exists so you don't mistake demo-mode output for a real exchange.

---

## 3. Orchestration: LangGraph + raw Anthropic SDK

`backend/orchestrator/orchestrator.py` uses the real `langgraph` package (`from langgraph.graph import StateGraph, END`; `langgraph>=0.2.0` is a genuine dependency in `backend/requirements.txt`, not just a label) to define the request pipeline as an explicit graph:

```
router → exchange_tokens → fga_check → approval_gate → process_agents → generate_response
```

- **router**: an LLM call (Claude, via the raw Anthropic SDK) decides which internal domain components are relevant to the user's message and, critically, which *specific scope* is needed. For example, "what's our basketball stock?" needs `inventory:read`, while "add 500 basketballs" needs `inventory:write`. If the LLM call or its JSON parsing fails, a keyword-matching fallback (`AGENT_KEYWORDS` / `SCOPE_DEFINITIONS`) selects the domain and scope instead.
- **exchange_tokens**: runs the two-step ID-JAG exchange described above for every resource domain the router selected, using the *specific* scopes it determined rather than requesting every available scope.
- **fga_check**: the Auth0 FGA layer, described in detail below. It runs *after* token exchange because the Inventory Custom Authorization Server's access token carries the `Manager`/`Vacation`/`Clearance` claims that FGA needs, and the Org AS used in Step 1 doesn't support these custom claims.
- **approval_gate**: the OIG human-in-the-loop check, described below.
- **process_agents**: invokes the internal domain components that survived both authorization layers.
- **generate_response**: synthesizes a final answer, explicitly distinguishing "access denied" (policy said no) from "system error" (Okta/infra failure) from "no response" (nothing was needed/available), so the UI and the user never conflate a security decision with a bug.

The internal domain classes (`backend/agents/sales_agent.py`, `inventory_agent.py`, `customer_agent.py`, `pricing_agent.py`) subclass `BaseAgent` (`backend/agents/base_agent.py`). These are orchestration components behind the one governed ProGear Sales Agent, not four separate user-facing or Okta-registered agent identities. Each component calls the **raw Anthropic SDK directly** (`anthropic.Anthropic(...).messages.create(...)`), not LangChain's LLM wrapper. `langchain` is present in `requirements.txt` only because `langgraph` needs it as a transitive dependency.

The model name comes from `LLM_MODEL_NAME` (default `claude-sonnet-4-6`); the key from `ANTHROPIC_API_KEY`.

---

## 4. Auth0 FGA: the second authorization layer

Okta authenticates the human and agent, grants a coarse inventory scope, and signs the user's live `Clearance` and `Vacation` values into the inventory access token. Auth0 FGA, implemented in `backend/auth/fga_client.py`, answers the next question: "given this role, quantity, and current context, may this request execute directly?" It is a separate authorization call against the hosted FGA store.

The presentation UI makes this advanced path opt-in. With **Simulate FGA** off, `POST /api/chat` uses the same signed role/context and the same direct-execution boundary, but denies any request that needs a higher role instead of calling FGA or creating an OIG request. With it on, the request includes `simulate_fga: true`, enabling the hosted decision and approval route. Because simple mode is deny-only for upward routing, this browser preference cannot weaken authorization.

### The model

`clearance_level` now means role, not item sensitivity: 1 = Sales, 2 = Manager, 3 = VP. The version-controlled FGA model is `backend/auth/fga_role_model.json`:

```
type user

type inventory_system
  relations
    define role_sales:          [user]
    define role_manager:        [user]
    define role_vp:             [user]
    define on_vacation:         [user]
    define active_sales:        role_sales but not on_vacation
    define active_manager:      role_manager but not on_vacation
    define active_vp:           role_vp but not on_vacation
    define can_read:            role_sales or role_manager or role_vp
    define can_request_change:  active_sales or active_manager or active_vp
    define can_update_standard: active_manager or active_vp
    define can_update_large:    active_vp
```

| Request | FGA relation | Direct execution | If requester is below the tier |
|---|---|---|---|
| Inventory read | `can_read` | Level 1+ | Deny if no valid role |
| Write 1–600 units | `can_update_standard` | Level 2+ | Manager approval |
| Write 601+ units | `can_update_large` | Level 3 | VP approval |

Sales, Customer, and Pricing agents have no FGA model today and always pass through. FGA currently only gates Inventory.

### Role and vacation are contextual

The backend maps the `Clearance` token claim to exactly one contextual tuple (`role_sales`, `role_manager`, or `role_vp`) and adds `on_vacation` when the claim is true. Neither fact is persisted as a mutable role copy in FGA. A role or vacation change in Okta therefore applies on the next token exchange. Reads remain available while on vacation; writes and approval submission are blocked.

### The check itself

`backend/auth/inventory_policy.py` parses quantity and selects the required FGA relation and approval tier. `check_inventory_access_via_fga()` checks `inventory_system:warehouse` with the contextual role and vacation tuples. The orchestrator records the decision, role, quantity, direct permission, and approval route in `state["fga_checks"]`; `ChatResponse.fga_checks` returns that evidence to the browser for `/fga` and `/tokens`.

**Fail-closed by design.** If the FGA client isn't configured or the API call fails, `check_inventory_access_via_fga()` denies access by default rather than allowing it. Authorization for inventory writes and reads depends on FGA actually answering.

---

## 5. Governance: human-in-the-loop approval for large writes

`backend/services/factory.py` builds an `ApprovalService` wired to a real **Okta Identity Governance (OIG) Access Request** flow. Approval is role-based: Level 1 needs Manager approval for 1–600, while any non-VP needs VP approval for 601+.

The orchestrator's **approval_gate** node fires only when all of the following are true:
1. The request needs `inventory:write`.
2. FGA confirms the active user may submit a change request.
3. The user's level is below the direct-execution level for the parsed quantity.

When triggered, it builds an `Intent` containing the required approver role and level and creates a real OIG request. The intent JSON is fenced inside the justification field so it can be recovered later without a separate database. After OIG approval, `OktaRoleResolver` retrieves the approver's current profile and the service fails closed unless the approver meets the required level.

**Resolution happens two ways:**
- **Foreground fast path**: `GET /api/approvals/{request_id}` (polled by the frontend) calls `ApprovalService.execute_if_approved()`, which checks OIG's current decision and executes the write immediately if approved.
- **Background poller**: `backend/api/main.py` starts an async loop on FastAPI startup (`_approval_poller_loop`) that polls OIG's open/resolved requests every `APPROVAL_POLL_INTERVAL_SECONDS` (default 120s, with exponential backoff on errors) and executes any newly-approved inventory requests even if nobody has the tab open.

Execution is idempotent: a JSON ledger file (`backend/data/approvals_ledger.json`) tracks which OIG request IDs have already been executed, with a bounded retry count (3 attempts) before a request is marked abandoned, so a flaky write doesn't retry forever and an already-executed request never double-applies.

**Honest limitation:** when the write finally executes, it's authorized via `mint_service_token()` (`backend/services/service_token.py`); this is currently a **placeholder string**, not a real Okta `client_credentials` exchange. The comment in that file says so directly: it exists because the original user's session may have long since expired by the time an approver acts, and a real service-identity token exchange is future work, not something wired up today.

---

## 6. The demo data layer

`backend/data/demo_store.py` is the only place business data lives; there's no database. It loads `backend/data/initial_data.json` (the seed dataset: 90 inventory SKUs across 8 categories, 34 customers) into `backend/data/live_data.json` on first boot if that file doesn't exist, and thereafter reads/writes `live_data.json` directly. `live_data.json` is **gitignored**: it's a runtime snapshot regenerated from the seed file, never something to commit or hand-edit. Resetting the demo means deleting `live_data.json` (or calling the store's reset method) so it re-derives from `initial_data.json`.

---

## 7. Known, honest limitation: the MCP server isn't in the live path yet

`packages/progear-sales-mcp-server` is a real, separately deployed Express server that validates JWTs against Okta's JWKS endpoint. It exists and works as a standalone component. **However, the internal domain components in this backend do not call it.** `_invoke_agent()` in the orchestrator instantiates the domain classes directly, and they read/write `demo_store` in-process. There is no network round-trip to the MCP server today. Describing every domain action as "a real MCP tool call" would be inaccurate. It is an in-process function call gated by the same Okta/FGA/OIG checks described above, with a real, working, JWT-validating MCP server that is not yet wired into this request path.

---

## 8. Audit trail

Every ID-JAG exchange, granted or denied, is a token-grant event in **Okta's System Log**, a queryable, tamper-evident stream that exists independently of this app's own logging. `GET /api/okta/logs` in `backend/api/main.py` queries the real Okta System Log API (`/api/v1/logs`, authenticated with `OKTA_API_TOKEN`) for `token.grant`/token-exchange events and reshapes them into a consistent shape: which agent (actor) acted, on behalf of which user (target), against which Custom Authorization Server, and which scopes were requested versus actually granted. This is Okta's own audit record, not a log table this app maintains.

**Honest limitation:** the endpoint above is real and callable, but the frontend page that rendered it (`OktaSystemLog`, on the now-removed `/how-it-works` page) is gone. There's currently no UI surfacing this data, only the API.

---

## 9. Cutting off access

Two independent mechanisms can stop new agent actions. The distinction between **stopping new token issuance** and **revoking a token already issued** matters operationally.

- **Deactivate the Workload Principal.** An admin can deactivate the AI agent's identity in Okta directly. The next ID-JAG exchange attempt for that agent fails outright, so the agent cannot obtain a new resource access token. A resource token issued before deactivation remains governed by its short expiry and the resource server's revocation policy; keep token lifetimes narrow and validation strict.
- **Change live FGA inputs.** Vacation status and the role derived from `clearance_level` are contextual tuples evaluated at check time, so the next exchanged token drives the next decision: no redeploy and no mutable role copy in FGA. This repo ships scoped demo endpoints for that purpose: `POST /api/admin/demo-toggle` lets the *signed-in* user change only their own `is_on_vacation` or `clearance_level` (validated as 1, 2, or 3), while `/api/admin/demo-reset` restores the persona's starting role and sets vacation to false. The user ID always comes from the validated token, never from the request body (`backend/auth/demo_admin.py`).

---

## 10. Deployment topology

Both halves deploy from this single repo with `main` as the single production source branch:

| Component | Platform | Detail |
|---|---|---|
| Frontend | Vercel | `packages/progear-sales-agent` (Next.js). Live at `https://progear-sales-aiagent.vercel.app`. |
| Backend | Render | Service name "ProGearSalesAI", `rootDir: backend`. Live at `https://progearsalesai-p2wm.onrender.com`. |

---

## 11. See it live, interactively

One page in the running frontend exists specifically to make this architecture visible and explorable, beyond this document:

- **`/architecture`** presents two complementary views. The architecture diagram is a clean left-to-right trust chain: employee subject → ProGear Workload Principal → Okta ID-JAG → Resource Authorization Server → Inventory API. Selecting a node reveals an engineer-level explanation without crowding the executive view. A simulated deactivation severs the chain before ID-JAG and explicitly distinguishes new-token cutoff from already-issued token expiry. The sequence diagram then shows the same request in time order and exposes plain-language and protocol detail one step at a time. When the shared **Simulate FGA** preference is enabled, both diagrams add the role + quantity + vacation decision between scoped OAuth access and the protected inventory action; when it is off, the advanced layer disappears.

There's also a **`/tokens`** page showing the raw token exchanges, FGA checks, and pending approvals as they happen in real time for the current session, useful for watching the mechanisms above fire on an actual request instead of just reading about them.

---

## Further reading

- [Implementation Guide](./implementation-guide.md): step-by-step deployment instructions
- [Okta AI Agent Documentation](https://developer.okta.com/docs/guides/ai-agent-governance/): official Okta docs
- [IETF ID-JAG Specification](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant): Identity Assertion JWT Authorization Grant draft
- [Cross App Access](https://xaa.dev/): approachable overview of the cross-domain delegation pattern
