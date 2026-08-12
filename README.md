# ProGear Sales AI: Okta AI Agent Governance + FGA Demo

> **AI agents are identities. Every delegated action stays attributable.** CourtEdge ProGear registers its customer-owned sales agent in Okta as a [Workload Principal](https://developer.okta.com/docs/api/secures-ai/ai-agents)—a first-class identity with its own owners, credentials, lifecycle, resource connections, and audit trail. When the agent acts for an employee, **Cross App Access (XAA)** uses the [IETF Identity Assertion JWT Authorization Grant (ID-JAG)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant) to carry the user's identity across trust domains while identifying the agent client acting on that user's behalf. The result is a traceable delegation chain: **user → agent → MCP resource → scope → tool call**. [Explore XAA.dev](https://xaa.dev/).

Before any delegation, ProGear reads the employee's live Okta profile. An **On vacation** value of `true` suspends agent work before ID-JAG, while the synchronized **Manager** value makes the employee's role easy to understand and audit. **FGA** then evaluates role plus requested quantity. [**Okta Identity Governance**](https://developer.okta.com/docs/api/iga) is used for one deliberate escalation: a Manager requesting more than 600 units needs approval from the people who own the governed AI agent.

![Okta AI Agent Governance](https://img.shields.io/badge/Okta-AI%20Agent%20Governance-blue)
![FGA](https://img.shields.io/badge/Fine--Grained-Authorization-orange)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-purple)

## Live Demo

**Production app:** [progear-sales-aiagent.vercel.app](https://progear-sales-aiagent.vercel.app)

Production deploys from `main`; feature branches may produce temporary previews, but they are not production sources.

### How Okta governs this custom agent

The ProGear Sales Agent is not a generic chatbot identity or a separate identity for each internal tool. Its Workload Principal (`wlp`) under **Directory → AI Agents** is the durable control point for the complete agent: administrators can assign owners, manage credentials and resource connections, activate or deactivate it, and use Okta's System Log to trace its delegation activity. The application remains customer-owned; Okta supplies the governed identity and preserves accountability when that agent acts for a user.

User sign-in uses a dedicated Okta OIDC web app linked to the registered ProGear Sales Agent. In the compatibility model active in this tenant, the sign-in client has its own `0oa...` ID while the governed agent keeps its separate `wlp...` identity. Both use independent `private_key_jwt` credentials; there is no shared client secret. See [Okta AI Agent Client Binding Compatibility](docs/agent-client-binding-compatibility.md).

[![CourtEdge ProGear custom agent sign-in page](docs/images/progear-sign-in.png)](https://progear-sales-aiagent.vercel.app/auth/signin)

*The application owns this sign-in experience and delegates authentication to Okta. No application password is collected by ProGear.*

Pages in the running app:

| Route | What it shows |
|---|---|
| `/` | The chat UI ("CourtEdge ProGear"), talk to the sales assistant |
| `/tokens` | RFC 9728 MCP discovery, the signed token chain, independent resource-token validation, final business decision, and pending approval status |
| `/architecture` | Identity-centered architecture and sequence diagrams for Workload Principal governance, native MCP discovery, ID-JAG delegation, `tools/call`, auditability, and the agent deactivation control; the advanced FGA layer appears only when its simulation is enabled |
| `/fga` | Opt-in FGA demo with browser-session-isolated Manager/VP comparison and vacation controls, plus a simple D3 decision view |

The application starts with **Simulate FGA** off and shows two everyday prompts: an inventory read and a normal 50-unit write. In this coarse mode, Sarah is read-only, while a validated `inventory:write` token lets Mike or a VP execute any positive quantity. Enabling the simulation on `/fga` exposes the On vacation control, replaces those examples with the Read, 1–600, and 601+ tiers, and opts chat requests into hosted FGA checks plus OIG approval routing. Sarah always remains Sales. Mike starts as Manager and may compare the Manager and VP policy outcomes inside only his current browser tab; this does not change his shared Okta profile or grant a scope Okta denied. As Manager, 601+ creates an approval for `AIAgentOwners`; as the VP preview, it executes directly. The tab stores a random session ID in `sessionStorage`; refreshes and sign-outs keep that tab's FGA choice, while closing the tab ends the browser session and a fresh tab starts with FGA off. Color preferences are independent: Light is the first-visit default, with Dark and System available from the persistent theme control.

### Demo personas at a glance

With **Simulate FGA** enabled, the three default Okta role levels tell one complete inventory story:

| Persona | Okta role level | Manager | Inventory behavior |
|---|---:|---|---|
| Sarah Sales | 0 — Sales | False | Reads directly; every inventory write stops before ID-JAG exchange, with guidance to contact her manager. No access request is created. |
| Mike Manager | 1 — Manager | True | Reads and writes 1–600 units directly; writes of 601+ units request AI Agent Owner approval when FGA is enabled. His isolated FGA control can preview Level 2 direct execution. |
| VP policy outcome | 2 — VP | True | Writes any quantity directly. The hosted demo previews this outcome through Mike's session rather than requiring a third login. |

Sarah and Mike are example personas, not hard-coded identities. The backend resolves the authenticated employee's current Okta profile by subject on every request, so any user assigned `clearance_level` 0, 1, or 2 follows the same Sales, Manager, or VP policy. `is_a_manager` is synchronized from that level (`false`, `true`, `true`) rather than acting as a second role switch. `is_on_vacation` is separate: setting it to `true` stops the agent before ID-JAG for every protected resource and every action. Use your Okta identity-lifecycle or profile-mapping process to maintain these values.

The hosted app calls the native **ProGear Inventory MCP** endpoint. It first reads the resource's [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728) well-known metadata, which identifies the resource, its protecting Okta authorization server, and its scopes. `ProGear-Sales` can receive only `inventory:read`; `ProGear-Managers` and `ProGear-VPs` can receive `inventory:read`, `inventory:write`, and `inventory:alert` as assigned by policy. After a successful native ID-JAG exchange, the same signed Bearer token is sent to the MCP endpoint in a standard `tools/call`. FGA is not a separate authorization server; when enabled, it evaluates role plus quantity after the coarse Okta gate and before the write tool call.

For the approval demo, assign the **Okta Access Requests** app to the relevant presenters, push `AIAgentOwners` into Access Requests, and assign the request type's approval task to that pushed group. The backend sends Mike's Okta user ID in `requesterUserIds`, so OIG shows the signed-in Manager as the requester and the service credential owner separately as the request creator. Any current member of `AIAgentOwners` can approve or deny the task in **Okta Access Requests → Inbox → Open**. The backend verifies that live group membership before execution. A presenter such as Johnathan can keep Access Requests open in a separate browser profile, so no third ProGear persona login is required. The approval card contains only a concise human summary; the exact machine-readable execution intent stays in the backend approval ledger.

## What This Demo Shows

An AI sales agent needs to read and write real business data (inventory, pricing, customer records) on a user's behalf. This demo answers the questions that matter for enterprise AI agent security:

- **WHO** requested this access, and **WHAT** agent acted on their behalf?
- **WHICH** scopes were actually granted, per resource domain, per user?
- **CAN** a second decision (clearance level + quantity) still block or route an otherwise-authenticated action?
- **WHEN** does a human need to approve before an action executes?
- **SHOULD** the agent be allowed to act for this employee right now, or should vacation status suspend delegation first?
- **CAN** access be revoked instantly?

| Layer | Technology | What it does |
|---|---|---|
| Identity for the agent | Okta AI Agent Governance | The AI has its own Workload Principal (`wlp`) identity, distinct from any human user |
| MCP discovery and token exchange | RFC 9728 + ID-JAG | The MCP resource advertises its Okta authorization server and scopes. ProGear then performs ID token → ID-JAG → scoped access token with RSA keypair authentication and presents that token to the real MCP endpoint. |
| Delegation context | Okta user profile | `is_on_vacation=true` stops before ID-JAG; `is_a_manager` remains synchronized with the authoritative role level |
| Fine-grained authorization | FGA | Maps role level (0 Sales, 1 Manager, 2 VP) and requested quantity to allow, block, or owner approval |
| Human-in-the-loop | Okta Identity Governance (OIG) | A Manager write of 601+ units routes to `AIAgentOwners`; Sales writes never create requests |
| Orchestration | LangGraph | Routes each user query to the correct protected MCP resource and coordinates the response |
| Protected tools | Model Context Protocol (Streamable HTTP) | Standard Bearer-authenticated `tools/call` requests reach the Inventory, Sales, Customer, or Pricing MCP server |
| LLM calls | Anthropic Claude, via the raw Anthropic SDK | Internal domain components call Claude directly (not through LangChain's LLM wrapper) for routing and response generation |

For the role matrix and live configuration, see **[docs/inventory-role-levels.md](docs/inventory-role-levels.md)**. For the broader technical walkthrough, see **[docs/architecture.md](docs/architecture.md)**.

## One governed agent, four protected MCP resources

Okta governs one **ProGear Sales Agent** workload identity. The application discovers and calls four native MCP endpoints. Each endpoint publishes its own protected-resource metadata and is protected by an Okta Custom Authorization Server. A user's group membership determines which scopes the single agent can obtain for that user.

| MCP resource | Endpoint | Scopes |
|---|---|---|
| Sales | `/sales/mcp` | `sales:read`, `sales:quote`, `sales:order` |
| Inventory | `/inventory/mcp` | `inventory:read`, `inventory:write`, `inventory:alert` |
| Customer | `/customer/mcp` | `customer:read`, `customer:lookup`, `customer:history` |
| Pricing | `/pricing/mcp` | `pricing:read`, `pricing:margin`, `pricing:discount` |

The deployed base URL is configured with `PROGEAR_MCP_BASE_URL`. For a resource such as `/inventory/mcp`, ProGear discovers metadata at `/.well-known/oauth-protected-resource/inventory/mcp`; authorization-server IDs are not copied into the application configuration.

Okta configuration intentionally has two complementary records for each domain: the registered **MCP server** provides standards-based discovery and inventory, while the agent's `IDENTITY_ASSERTION_CUSTOM_AS` resource connection preserves native XAA/ID-JAG. In the current resource-connection API, selecting **MCP server** as the agent connection type uses the STS access-token model, so it is not a drop-in replacement for this hosted XAA path.

## Demo Data

The deployed ProGear MCP service owns the demonstration dataset: 90 inventory SKUs across 8 categories and 34 customers. Its current store is intentionally in-memory, seeded when the MCP process starts, and resets on a service restart. The hosted FastAPI backend no longer reads or mutates `backend/data/demo_store.py` for live business actions.

## Tech Stack

| Area | Stack |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, NextAuth.js (Okta OIDC), D3.js (architecture visualizations) |
| Backend | Python, FastAPI (`backend/api/main.py`) |
| Orchestration | LangGraph (`langgraph>=0.2.0`, a real dependency, not just a label), `backend/orchestrator/orchestrator.py` |
| LLM integration | Anthropic Python SDK, called directly by internal domain components (no LangChain LLM wrapper) |
| AuthN/AuthZ | Okta AI Agent Governance (RFC 9728 discovery + ID-JAG), FGA (`openfga-sdk`), Okta Identity Governance |
| Protected resources | Native Streamable HTTP MCP endpoints on Render |
| Deployment | Vercel (frontend), Render (backend) |

### Runtime boundary and demo limitation

The live request path uses the separately deployed [ProGear MCP servers](https://github.com/oktaforai-okta/progear-mcp-servers), not the legacy `packages/progear-sales-mcp-server` sample in this repository. The backend validates every resource token locally and the MCP server validates it again before executing a tool. Inventory writes additionally require the final simple/FGA decision to be `allow`; there is no local simulated-success fallback. The MCP service is a demo system of record—its in-memory data resets when the service restarts and should be replaced by durable storage for production.

## Quickstart

This repo is an npm workspaces monorepo (`packages/progear-sales-agent`, `packages/progear-sales-mcp-server`) plus a standalone Python `backend/`.

```bash
# Frontend
npm install
npm run dev --workspace=packages/progear-sales-agent

# Backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Copy `.env.example` to `.env` and fill in real values before running anything. `PROGEAR_MCP_BASE_URL` selects the native MCP service; each resource's well-known document supplies the protecting authorization server.

For a full walkthrough of Okta org setup (AI Agent, Custom Authorization Servers, groups), FGA store setup, and deploying to Vercel + Render, see **[docs/implementation-guide.md](docs/implementation-guide.md)** (it also covers recovering from an accidentally deleted AI Agent).

> **Client-to-agent binding compatibility:** This repository currently implements the delegation-link flow that works during Okta's temporary rollback of the newer binding model. The newer model is expected to return. Before changing the binding flow, read **[docs/agent-client-binding-compatibility.md](docs/agent-client-binding-compatibility.md)**. It records the rationale, stable restore points, migration boundary, and verification checklist so the work can be resumed from GitHub in a new session.

## Customer Learning Notebook

<a href="https://colab.research.google.com/github/oktaforai-okta/ProGearSalesAI/blob/main/notebooks/progear-inventory-authorization-story.ipynb"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open Wire your custom AI agent to Okta in Colab"/></a>

**[Wire your custom AI agent to Okta](notebooks/progear-inventory-authorization-story.ipynb)** helps builders apply the ProGear pattern to an agent of their own. Five configuration cards walk through the one-time Okta setup—OIDC sign-in, custom-agent registration, one Custom Authorization Server, one least-privilege scope and policy, and one resource connection—with direct links to the supporting Okta documentation. The runnable half then follows user ID token → agent proof → ID-JAG → scoped resource token → protected API. A credential-free preview is included; Live Okta mode keeps private values in Colab Secrets. FGA and OIG remain optional extensions in the web application.

## Documentation

| Document | Audience | Description |
|---|---|---|
| **[docs/architecture.md](docs/architecture.md)** | Anyone who wants to understand how it works | Full system walkthrough: token exchange sequence, FGA model, approval flow, MCP notes |
| **[docs/implementation-guide.md](docs/implementation-guide.md)** | Developers, DevOps | Complete deployment walkthrough: Okta configuration, Vercel + Render setup, and recovering from an accidentally deleted AI Agent |
| **[docs/agent-client-binding-compatibility.md](docs/agent-client-binding-compatibility.md)** | Maintainers, architects | Why the current delegation-link compatibility path exists and how to migrate when Okta restores the newer client-to-agent binding model |
| **[docs/okta-security-value.md](docs/okta-security-value.md)** | Security teams, architects | The broader security framing and scenario catalog this demo draws on, including the *why* behind each design decision (why 4 auth servers, why FGA as a second layer, why human approval) |
| **[docs/okta-ai-security-essentials.md](docs/okta-ai-security-essentials.md)** | Marketers, executives, non-technical readers | The same value story as above, in plain English, no JWT/scope/issuer jargon |
| **[/architecture](https://progear-sales-aiagent.vercel.app/architecture)** (live) | Everyone | Interactive D3.js diagrams of the token exchange and access-control flows |

## Project Structure

```
ProGearSalesAI/
├── backend/
│   ├── api/main.py                 # FastAPI app and endpoints
│   ├── agents/                     # Internal Sales, Inventory, Customer, Pricing components
│   ├── auth/
│   │   ├── agent_config.py         # Native MCP resource URLs, scopes, audiences, identity overrides
│   │   ├── multi_agent_auth.py     # MCP discovery + ID-JAG token exchange
│   │   ├── fga_client.py           # FGA checks (clearance + quantity)
│   │   └── resource_token.py       # Resource JWT validation before data access
│   ├── orchestrator/
│   │   └── orchestrator.py         # LangGraph workflow + direct Anthropic SDK calls
│   ├── mcp/client.py               # RFC 9728 discovery + Streamable HTTP tools/call
│   └── services/                   # OIG approval client and post-approval MCP execution
├── packages/
│   ├── progear-sales-agent/        # Next.js frontend (chat, /tokens, /architecture)
│   └── progear-sales-mcp-server/   # Legacy standalone sample (not in the live path)
├── docs/                           # architecture.md, implementation-guide.md, etc.
├── notebooks/                      # Layered customer Colab integration guide
├── examples/                       # Platform-neutral token exchange reference
├── .env.example                    # Environment variable template (names only, no real secrets)
└── README.md                       # This file
```

## License

MIT (see `package.json`).
