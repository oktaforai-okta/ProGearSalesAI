# ProGear AI Agent Architecture

This document explains how the ProGear Sales AI demo actually works, end to end, based on the live code in this repo. It's written for someone who has never seen this codebase but is technically comfortable with OAuth, authorization, and multi-agent systems.

ProGear ("CourtEdge ProGear") is a fictional basketball-equipment retailer. The demo is an AI sales/shopping assistant secured by three cooperating systems:

1. **Okta AI Agent Governance** — gives the AI its own identity and exchanges the user's login for narrowly-scoped, short-lived access tokens (ID-JAG).
2. **Auth0 FGA** — a second, finer-grained authorization layer that checks live relationships, clearance, and context (e.g., "is this person on vacation right now?") that Okta's role-based check doesn't know about.
3. **Okta Identity Governance (OIG)** — routes high-impact actions (large inventory writes) to a human approver instead of letting the agent execute them immediately.

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
│  Backend: FastAPI (Render) — backend/api/main.py                    │
│                                                                       │
│  Orchestrator (LangGraph, backend/orchestrator/orchestrator.py)     │
│  router → exchange_tokens → fga_check → approval_gate →             │
│           process_agents → generate_response                       │
│                                                                       │
│    Sales Agent   Inventory Agent   Customer Agent   Pricing Agent   │
│    (each: raw Anthropic SDK call, no LangChain LLM wrapper)         │
└───────────┬───────────────────────┬──────────────────────┬──────────┘
            │                       │                      │
            ▼                       ▼                      ▼
   Okta Org AS + 4 Custom      Auth0 FGA                Okta Identity
   Authorization Servers       (ReBAC + ABAC             Governance (OIG)
   (ID-JAG token exchange,     check on inventory)        (Access Requests for
   RSA/JWT-Bearer auth)                                    large writes)
```

The backend never talks to a database — it reads/writes a JSON file (`backend/data/demo_store.py` over `initial_data.json` / `live_data.json`) that simulates ProGear's business data.

---

## 1. Identity: the AI agent has its own Okta identity

The AI is not "the user with extra code around it." It is registered in Okta as a **Workload Principal** — a distinct machine identity (Okta entity IDs for these start with `wlp...`). The same `wlp...` identifier is now the client ID of the OIDC app Okta permanently binds when **direct User access** is enabled. The Vercel web runtime authenticates its authorization-code and refresh-token requests with a dedicated `private_key_jwt` key (`OKTA_OIDC_PRIVATE_KEY`), while the backend uses its workload key for ID-JAG exchanges. Neither path uses a shared client secret. The backend workload key is supplied per agent as a JWK via environment variables (`OKTA_AI_AGENT_[TYPE]_PRIVATE_KEY`, falling back to a shared `OKTA_AI_AGENT_PRIVATE_KEY`) and consumed in `backend/auth/multi_agent_auth.py` and `backend/auth/agent_config.py`.

Because the agent's identity is separate from the human user's identity, every access decision downstream can be phrased as "is Agent X, acting on behalf of User Y, allowed to do Z" — which is exactly the shape Okta's AI Agent Governance and the audit trail (Okta System Log) are built around.

There are actually **4 separate agent identities/configurations** in this demo — one per business domain — described below.

---

## 2. Token exchange: two-step ID-JAG

The core mechanism is the **Identity Assertion JWT Authorization Grant (ID-JAG)**, implemented in `backend/auth/multi_agent_auth.py`. It's a two-step exchange, and both steps happen on every chat request, per agent needed for that request:

**Step 1 — ID token → ID-JAG (at the Org Authorization Server)**
The user's Okta ID token (from their NextAuth login) is exchanged for an ID-JAG assertion. This assertion names *both* the user and the agent — "Agent X is acting on behalf of User Y." This happens at Okta's Org AS (configured via `OKTA_MAIN_AUTH_SERVER_ID`), using the agent's RSA keypair, not the user's credentials.

**Step 2 — ID-JAG → scoped access token (at a per-domain Custom Authorization Server)**
The ID-JAG assertion is then exchanged for an actual access token at the Custom Authorization Server for the specific business domain the request needs (Sales, Inventory, Customer, or Pricing). This is where Okta's access policies actually evaluate: is this user, in this group, allowed to receive these scopes? The resulting access token is scoped, short-lived, and — for the Inventory domain — carries custom claims (`Manager`, `Vacation`, `Clearance`) that feed the FGA layer described below.

**No down-scoping.** If any one of the requested scopes isn't grantable to this user under this agent's policy, Okta doesn't silently drop that scope and grant the rest — the *entire* exchange fails with `access_denied`. `multi_agent_auth.py` treats `no_matching_policy`, `access_denied`, and Okta's generic "Policy evaluation failed" 401 as the same outcome and returns a clean `access_denied` result rather than a partial grant or a raw error.

### The 4 domain agents and their Custom Authorization Servers

Each domain has its own agent configuration, its own Custom Authorization Server, and its own scope set, all defined in `backend/auth/agent_config.py`:

| Domain | Scopes | Authorization server environment variable |
|---|---|---|
| Sales | `sales:read`, `sales:quote`, `sales:order` | `OKTA_SALES_AUTH_SERVER_ID` |
| Inventory | `inventory:read`, `inventory:write` | `OKTA_INVENTORY_AUTH_SERVER_ID` |
| Customer | `customer:read`, `customer:lookup`, `customer:history` | `OKTA_CUSTOMER_AUTH_SERVER_ID` |
| Pricing | `pricing:read`, `pricing:margin`, `pricing:discount` | `OKTA_PRICING_AUTH_SERVER_ID` |

Each also has its own agent ID / private key env vars (`OKTA_AI_AGENT_[TYPE]_ID`, `OKTA_AI_AGENT_[TYPE]_PRIVATE_KEY`), with a shared fallback (`OKTA_AI_AGENT_ID`, `OKTA_AI_AGENT_PRIVATE_KEY`) if a per-domain agent isn't separately provisioned.

If the Okta AI SDK or the agent credentials aren't configured, `multi_agent_auth.py` falls back to a demo mode that fabricates a plausible-looking token result — useful for running the UI without a live Okta org, but worth knowing it exists so you don't mistake demo-mode output for a real exchange.

---

## 3. Orchestration: LangGraph + raw Anthropic SDK

`backend/orchestrator/orchestrator.py` uses the real `langgraph` package (`from langgraph.graph import StateGraph, END`; `langgraph>=0.2.0` is a genuine dependency in `backend/requirements.txt`, not just a label) to define the request pipeline as an explicit graph:

```
router → exchange_tokens → fga_check → approval_gate → process_agents → generate_response
```

- **router** — an LLM call (Claude, via the raw Anthropic SDK) decides which of the 4 domain agents are relevant to the user's message and, critically, which *specific scope* is needed (e.g., a "what's our basketball stock?" question needs `inventory:read`; "add 500 basketballs" needs `inventory:write`). If the LLM call or its JSON parsing fails, a keyword-matching fallback (`AGENT_KEYWORDS` / `SCOPE_DEFINITIONS`) picks agents and scopes instead.
- **exchange_tokens** — runs the two-step ID-JAG exchange described above for every agent the router selected, using the *specific* scopes it determined (not a blanket "all scopes for this agent" request).
- **fga_check** — the Auth0 FGA layer, described in detail below. Runs *after* token exchange specifically because the Inventory Custom Authorization Server's access token carries the `Manager`/`Vacation`/`Clearance` claims that FGA needs, and the Org AS (used in Step 1) doesn't support custom claims.
- **approval_gate** — the OIG human-in-the-loop check, described below.
- **process_agents** — actually invokes the domain agent(s) that survived both authorization layers.
- **generate_response** — synthesizes a final answer, explicitly distinguishing "access denied" (policy said no) from "system error" (Okta/infra failure) from "no response" (nothing was needed/available) so the UI and the user never conflate a security decision with a bug.

Each domain agent (`backend/agents/sales_agent.py`, `inventory_agent.py`, `customer_agent.py`, `pricing_agent.py`) subclasses `BaseAgent` (`backend/agents/base_agent.py`), which calls the **raw Anthropic SDK directly** (`anthropic.Anthropic(...).messages.create(...)`) — not LangChain's LLM wrapper. The code comment in `base_agent.py` is explicit about this: "Uses raw Anthropic SDK (not LangChain wrappers) per project preference." `langchain` is present in `requirements.txt` only because `langgraph` needs it as a transitive dependency, not because agents use it to talk to the model.

The model name comes from `LLM_MODEL_NAME` (default `claude-sonnet-4-6`); the key from `ANTHROPIC_API_KEY`.

---

## 4. Auth0 FGA: the second authorization layer

Okta's ID-JAG check answers "is this role allowed to do this *kind* of thing at all" (coarse: group membership → scope). Auth0 FGA, implemented in `backend/auth/fga_client.py`, answers a different question: "does *this specific person* have the right *live* relationship, clearance, and context for *this specific object*, right now?" It's a genuinely separate authorization system, called via the OpenFGA SDK against a hosted FGA store, not a re-implementation of Okta's logic.

### The model

The FGA store defines these types and relations (see the full docstring at the top of `fga_client.py` for the authoritative version):

```
type user

type clearance_level
  relations
    define next_higher: [clearance_level]
    define granted_to:  [user]
    define holder:      granted_to or holder from next_higher

type inventory_system
  relations
    define manager:        [user]
    define viewer:         [user]
    define on_vacation:    [user]
    define active_manager: manager but not on_vacation
    define active_viewer:  viewer but not on_vacation
    define can_manage:     active_manager
    define can_read:       active_manager or active_viewer

type inventory_item
  relations
    define parent:             [inventory_system]
    define required_clearance: [clearance_level]
    define has_clearance:      holder from required_clearance
    define can_view:            can_read from parent
    define can_update:          has_clearance and can_manage from parent
```

Two things worth calling out about this model:

- **Clearance is hierarchical.** `clearance_level` forms a chain via `next_higher`: holding level *N* also makes you a holder of every level below it (`holder: granted_to or holder from next_higher`). A user with clearance 7 satisfies an item that requires clearance 3.
- **Read access is broader than write access.** Both managers and plain viewers get `can_view` (via `can_read: active_manager or active_viewer`), but only managers with sufficient clearance get `can_update` (`has_clearance and can_manage from parent`, and `can_manage` is manager-only). Non-managers who request the Inventory agent are automatically given a `viewer` tuple (see "dynamic tuples" below) so they can read but never write.

### How scopes map to FGA checks

| Requested scope | FGA check | What it actually requires |
|---|---|---|
| `inventory:read` | `can_view` on the relevant `inventory_item` | active manager OR active viewer (i.e., not on vacation) |
| `inventory:write` | `can_update` on the relevant `inventory_item` | active manager AND sufficient clearance for that item |

Sales, Customer, and Pricing agents have no FGA model today and always pass through — FGA currently only gates Inventory.

### Vacation is contextual, not stored

`is_on_vacation` is **not** written into the FGA store as a persistent fact. It's read from the `Vacation` claim on the Inventory Custom Authorization Server's access token (or, as a fallback, the ID token) and passed as a **contextual tuple** at check time: `user:X on_vacation inventory_system:warehouse`, added to the request only when true. Because it's evaluated per-request rather than stored, flipping someone's vacation status takes effect on their very next check — no redeploy, no tuple cleanup.

### Manager, viewer, and clearance tuples are kept in sync dynamically

Unlike vacation, manager/viewer/clearance relationships *are* stored as FGA tuples — but the backend keeps them in sync with the live Okta claims on every request rather than requiring a one-time seed:

- `ensure_manager_relationship()` writes or deletes the `manager` tuple to match the `Manager` claim.
- `ensure_viewer_relationship()` writes or deletes a `viewer` tuple for non-managers who are requesting the Inventory agent, so they get read-only access without ever being a manager.
- `ensure_clearance_tuple()` enforces a single active clearance tuple per user — it deletes any stale level and writes the current one, so clearance changes on the Okta side (the `Clearance` claim) propagate into FGA on the next request.

### The check itself

`check_agent_access()` picks `can_view` or `can_update` based on the requested scope, then `check_inventory_access_via_fga()` calls the FGA API with the user, relation, the target `inventory_item` (the demo uses `widget-a`, which requires clearance 3, or `classified-part` if the message mentions "classified," which requires clearance 7), and the contextual vacation tuple if applicable. The orchestrator's `fga_check` node records the full result — allowed/denied, the relation checked, the object, the contextual tuples used, and a human-readable reason — into `state["fga_checks"]`, which the frontend's `/tokens` page and Token Exchange UI render directly.

**Fail-closed by design.** If the FGA client isn't configured or the API call fails, `check_inventory_access_via_fga()` denies access by default rather than allowing it. Authorization for inventory writes and reads depends on FGA actually answering.

---

## 5. Governance: human-in-the-loop approval for large writes

Not every authorized write executes immediately. `backend/services/factory.py` builds an `ApprovalService` (`backend/services/approval_service.py`) wired to a real **Okta Identity Governance (OIG) Access Request** flow via `backend/services/okta_oig_client.py`. The threshold is configurable (`APPROVAL_QUANTITY_THRESHOLD`, default `500`).

The orchestrator's **approval_gate** node fires only when all of the following are true:
1. The request needs `inventory:write`.
2. FGA didn't already deny the Inventory agent (an unauthorized action never reaches the approval gate — it's just denied).
3. `backend/services/intent.py` parses a quantity from the message (`parse_inventory_intent`) that is `>= APPROVAL_QUANTITY_THRESHOLD`.

When triggered, it builds an `Intent` (user, product, quantity, original request text) and calls the OIG API (`POST /governance/api/v1/requests`) to create a real Access Request, with the intent JSON fenced inside the request's justification field (`[INTENT_JSON]{...}[/INTENT_JSON]`) so it can be recovered later without a separate database. The chat response tells the user their request is pending and which approver group (`OKTA_APPROVER_GROUP_NAME`, default `InventoryApprovers`) it went to.

**Resolution happens two ways:**
- **Foreground fast path**: `GET /api/approvals/{request_id}` (polled by the frontend) calls `ApprovalService.execute_if_approved()`, which checks OIG's current decision and executes the write immediately if approved.
- **Background poller**: `backend/api/main.py` starts an async loop on FastAPI startup (`_approval_poller_loop`) that polls OIG's open/resolved requests every `APPROVAL_POLL_INTERVAL_SECONDS` (default 120s, with exponential backoff on errors) and executes any newly-approved inventory requests even if nobody has the tab open.

Execution is idempotent: a JSON ledger file (`backend/data/approvals_ledger.json`) tracks which OIG request IDs have already been executed, with a bounded retry count (3 attempts) before a request is marked abandoned, so a flaky write doesn't retry forever and an already-executed request never double-applies.

**Honest limitation:** when the write finally executes, it's authorized via `mint_service_token()` (`backend/services/service_token.py`) — this is currently a **placeholder string**, not a real Okta `client_credentials` exchange. The comment in that file says so directly: it exists because the original user's session may have long since expired by the time an approver acts, and a real service-identity token exchange is future work, not something wired up today.

---

## 6. The demo data layer

`backend/data/demo_store.py` is the only place business data lives — there's no database. It loads `backend/data/initial_data.json` (the seed dataset: 90 inventory SKUs across 8 categories, 34 customers) into `backend/data/live_data.json` on first boot if that file doesn't exist, and thereafter reads/writes `live_data.json` directly. `live_data.json` is **gitignored** — it's a runtime snapshot regenerated from the seed file, never something to commit or hand-edit. Resetting the demo means deleting `live_data.json` (or calling the store's reset method) so it re-derives from `initial_data.json`.

---

## 7. Known, honest limitation: the MCP server isn't in the live path yet

`packages/progear-sales-mcp-server` is a real, separately-deployed Express server that validates JWTs against Okta's JWKS endpoint. It exists and works as a standalone component. **However, the domain agents in this backend do not call it.** `_invoke_agent()` in the orchestrator instantiates the agent classes directly and they read/write `demo_store` in-process. There is no network round-trip to the MCP server today. Describing every agent action as "a real MCP tool call" would be inaccurate — it's an in-process function call gated by the same Okta/FGA/OIG checks described above, with a real, working, JWT-validating MCP server sitting nearby as a component that isn't yet wired into this request path.

---

## 8. Audit trail

Every ID-JAG exchange — granted or denied — is a token-grant event in **Okta's System Log**, a queryable, tamper-evident stream that exists independently of this app's own logging. `GET /api/okta/logs` in `backend/api/main.py` queries the real Okta System Log API (`/api/v1/logs`, authenticated with `OKTA_API_TOKEN`) for `token.grant`/token-exchange events and reshapes them into a consistent shape: which agent (actor) acted, on behalf of which user (target), against which Custom Authorization Server, and which scopes were requested versus actually granted. This is Okta's own audit record, not a log table this app maintains.

**Honest limitation:** the endpoint above is real and callable, but the frontend page that rendered it (`OktaSystemLog`, on the now-removed `/how-it-works` page) is gone — there's currently no UI surfacing this data, only the API.

---

## 9. Cutting off access

Two independent mechanisms can stop the agent from acting, and both take effect almost immediately because every credential in this system is short-lived and re-derived per request — there's no long-lived session to revoke:

- **Deactivate the Workload Principal.** An admin can deactivate the AI agent's identity in Okta directly. The next ID-JAG exchange attempt for that agent fails outright.
- **Flip a context flag FGA reads.** Because vacation status is a contextual tuple evaluated at check time (not a stored fact), setting `is_on_vacation` denies the very next inventory check for that user — no redeploy, no cache to bust. This repo ships a scoped demo endpoint for this exact purpose: `POST /api/admin/demo-toggle` (and `/api/admin/demo-reset`) let the *signed-in* user flip their own `is_on_vacation` / `is_a_manager` / `clearance_level` Okta profile attributes via the Okta Users API, specifically so the FGA "manager on vacation" and "insufficient clearance" scenarios can be demonstrated live without an Admin Console detour. It only ever mutates the caller's own profile — the user ID always comes from their validated token, never from the request body (`backend/auth/demo_admin.py`).

---

## 10. Deployment topology

Both halves deploy from this single repo and auto-deploy on every push to `main`:

| Component | Platform | Detail |
|---|---|---|
| Frontend | Vercel | `packages/progear-sales-agent` (Next.js). Live at `https://progear-sales-aiagent.vercel.app`. |
| Backend | Render | Service name "ProGearSalesAI", `rootDir: backend`. Live at `https://progearsalesai-p2wm.onrender.com`. |

---

## 11. See it live, interactively

One page in the running frontend exists specifically to make this architecture visible and explorable, beyond this document:

- **`/architecture`** — interactive D3.js diagrams (`D3ArchitectureDiagram` component): a hub-and-spoke relationship graph you can hover/click to trace connections — the resource tier is four separate boxes (Inventory, Customer, Pricing, Sales) rather than one bundled node, so each domain's own access rules are traceable — and a UML-style sequence-diagram walkthrough of 4 real scenarios (happy path, access denied, blocked on vacation, needs human approval). Steps stay lit as playback advances, so the whole path taken so far is always visible, not just the current step.

There's also a **`/tokens`** page showing the raw token exchanges, FGA checks, and pending approvals as they happen in real time for the current session — useful for watching the mechanisms above fire on an actual request instead of just reading about them.

---

## Further reading

- [Implementation Guide](./implementation-guide.md) — step-by-step deployment instructions
- [Okta AI Agent Documentation](https://developer.okta.com/docs/guides/ai-agent-governance/) — official Okta docs
- [IETF ID-JAG Specification](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/) — Identity Assertion JWT Authorization Grant draft
