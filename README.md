# ProGear Sales AI: Okta AI Agent Governance + FGA Demo

> **AI agents are identities. Every delegated action stays attributable.** CourtEdge ProGear registers its customer-owned sales agent in Okta as a [Workload Principal](https://developer.okta.com/docs/api/secures-ai/ai-agents)—a first-class identity with its own owners, credentials, lifecycle, resource connections, and audit trail. When the agent acts for Sarah, Mike, or Joe, **Cross App Access (XAA)** uses the [IETF Identity Assertion JWT Authorization Grant (ID-JAG)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant) to carry the user's identity across trust domains while identifying the agent client acting on that user's behalf. The result is a traceable delegation chain: **user → agent → resource → scope → action**. [Explore XAA.dev](https://xaa.dev/).

**FGA** then evaluates the signed clearance level and requested quantity. **Okta Identity Governance** is used for one deliberate escalation: a Manager requesting more than 600 units needs VP approval.

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

User sign-in uses Okta **direct User access** on the registered ProGear Sales Agent. The agent-bound OIDC app shares the agent's `wlp...` client ID and authenticates token requests with `private_key_jwt`; there is no separate sign-on client secret.

[![CourtEdge ProGear custom agent sign-in page](docs/images/progear-sign-in.png)](https://progear-sales-aiagent.vercel.app/auth/signin)

*The application owns this sign-in experience and delegates authentication to Okta. No application password is collected by ProGear.*

Pages in the running app:

| Route | What it shows |
|---|---|
| `/` | The chat UI ("CourtEdge ProGear"), talk to the sales assistant |
| `/tokens` | The signed token chain, independent resource-token validation, final business decision, and pending approval status |
| `/architecture` | Identity-centered architecture and sequence diagrams for Workload Principal governance, ID-JAG delegation, scoped access, auditability, and the agent deactivation control; the advanced FGA layer appears only when its simulation is enabled |
| `/fga` | Opt-in live Okta role controls and a simple D3 view of the FGA decision |

The application starts with **Simulate FGA** off and shows two everyday prompts: an inventory read and a normal 50-unit write. Enabling the simulation on `/fga` reveals the live role control, replaces those examples with the Read, 1–600, and 601+ VP prompt tiers, and opts chat requests into hosted FGA checks plus OIG approval routing. Simple mode still enforces the validated Okta-signed role, but denies requests that need a higher role instead of creating approval requests. It is never a bypass. Color preferences are independent: Light is the first-visit default, with Dark and System available from the persistent theme control.

### Demo personas at a glance

With **Simulate FGA** enabled, the three default Okta role levels tell one complete inventory story:

| Persona | Okta role level | Inventory behavior |
|---|---:|---|
| Sarah Sales | 0 — Sales | Reads directly; every inventory write is denied, with guidance to contact her manager. No access request is created. |
| Mike Manager | 1 — Manager | Reads and writes 1–600 units directly; writes of 601+ units request VP approval when FGA is enabled. |
| Joe VP | 2 — VP | Reads and writes any quantity directly. |

## What This Demo Shows

An AI sales agent needs to read and write real business data (inventory, pricing, customer records) on a user's behalf. This demo answers the questions that matter for enterprise AI agent security:

- **WHO** requested this access, and **WHAT** agent acted on their behalf?
- **WHICH** scopes were actually granted, per resource domain, per user?
- **CAN** a second decision (clearance level + quantity) still block or route an otherwise-authenticated action?
- **WHEN** does a human need to approve before an action executes?
- **CAN** access be revoked instantly?

| Layer | Technology | What it does |
|---|---|---|
| Identity for the agent | Okta AI Agent Governance | The AI has its own Workload Principal (`wlp`) identity, distinct from any human user |
| Token exchange | ID-JAG (Identity Assertion JWT Authorization Grant) | Two-step exchange: ID token → ID-JAG assertion (Org Authorization Server) → scoped access token (per-domain Custom Authorization Server). RSA keypair auth, no shared secret. No down-scoping: an ungrantable scope fails the whole exchange. |
| Fine-grained authorization | FGA | Maps Okta's role level (0 Sales, 1 Manager, 2 VP) and requested quantity to allow, block, or VP approval |
| Human-in-the-loop | Okta Identity Governance (OIG) | A Manager write of 601+ units routes to VP approval; Sales writes never create requests |
| Orchestration | LangGraph | Routes each user query to the right internal domain component and coordinates the response |
| LLM calls | Anthropic Claude, via the raw Anthropic SDK | Internal domain components call Claude directly (not through LangChain's LLM wrapper) for routing and response generation |

For the role matrix and live configuration, see **[docs/inventory-role-levels.md](docs/inventory-role-levels.md)**. For the broader technical walkthrough, see **[docs/architecture.md](docs/architecture.md)**.

## One governed agent, four resource domains

Okta governs one **ProGear Sales Agent** workload identity. The application contains four internal domain components, and each resource domain has its own Custom Authorization Server and scope boundary. A user's group membership determines which scopes the single agent can obtain for that user in each domain.

| Resource domain | Scopes |
|---|---|
| Sales | `sales:read`, `sales:quote`, `sales:order` |
| Inventory | `inventory:read`, `inventory:write` |
| Customer | `customer:read`, `customer:lookup`, `customer:history` |
| Pricing | `pricing:read`, `pricing:margin`, `pricing:discount` |

## Demo Data

90 inventory SKUs across 8 categories (Basketballs, Hoops & Backboards, Nets & Accessories, Uniforms & Apparel, Training Equipment, Footwear, Court & Game Equipment, Bags & Storage) and 34 customers, defined in `backend/data/initial_data.json` and served through `backend/data/demo_store.py`. On boot, the backend regenerates a runtime snapshot at `backend/data/live_data.json` (gitignored: it's derived state, never commit it and never hand-edit it).

## Tech Stack

| Area | Stack |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, NextAuth.js (Okta OIDC), D3.js (architecture visualizations) |
| Backend | Python, FastAPI (`backend/api/main.py`) |
| Orchestration | LangGraph (`langgraph>=0.2.0`, a real dependency, not just a label), `backend/orchestrator/orchestrator.py` |
| LLM integration | Anthropic Python SDK, called directly by internal domain components (no LangChain LLM wrapper) |
| AuthN/AuthZ | Okta AI Agent Governance (ID-JAG), FGA (`openfga-sdk`), Okta Identity Governance |
| Deployment | Vercel (frontend), Render (backend) |

### A known, honest limitation

There's a real, working MCP server in this repo (`packages/progear-sales-mcp-server`), a JWT-validating Express server that is deployed separately. **It is not currently in the live request path.** The backend's internal resource boundary independently validates every Okta token's signature, issuer, audience, expiry, agent identity, delegated user, and required scope before data access. Inventory writes additionally require the final simple/FGA decision to be `allow`; the old simulated-success fallback has been removed. The internal domain component then calls `demo_store` in-process rather than calling the standalone MCP server over HTTP.

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

Copy `.env.example` to `.env` and fill in real values before running anything. See it for every variable name used across the frontend, backend, and MCP server (Okta org/app/agent config, Anthropic key, FGA store, etc.).

For a full walkthrough of Okta org setup (AI Agent, Custom Authorization Servers, groups), FGA store setup, and deploying to Vercel + Render, see **[docs/implementation-guide.md](docs/implementation-guide.md)** (it also covers recovering from an accidentally deleted AI Agent).

> **Client-to-agent binding compatibility:** This repository currently implements the delegation-link flow that works during Okta's temporary rollback of the newer binding model. The newer model is expected to return. Before changing the binding flow, read **[docs/agent-client-binding-compatibility.md](docs/agent-client-binding-compatibility.md)**. It records the rationale, stable restore points, migration boundary, and verification checklist so the work can be resumed from GitHub in a new session.

## Customer Learning Notebook

<a href="https://colab.research.google.com/github/oktaforai-okta/ProGearSalesAI/blob/main/notebooks/progear-inventory-authorization-story.ipynb"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open ProGear Inventory Authorization Story in Colab"/></a>

**[Secure your custom AI agent with Okta](notebooks/progear-inventory-authorization-story.ipynb)** is a layered business-to-implementation guide. New readers can follow the Sarah-versus-Mike story without code; architects and developers can map the pattern to a customer-owned agent, configure Okta for AI Agents, inspect the two-step ID-JAG exchange, use the platform-neutral Python reference module, validate resource tokens, and work through production and troubleshooting checklists. Default labs use only local examples or read-only checks and contain no credentials.

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
│   │   ├── agent_config.py         # Per-domain auth server, scope, and optional identity overrides
│   │   ├── multi_agent_auth.py     # ID-JAG token exchange
│   │   ├── fga_client.py           # FGA checks (clearance + quantity)
│   │   └── resource_token.py       # Resource JWT validation before data access
│   ├── orchestrator/
│   │   └── orchestrator.py         # LangGraph workflow + direct Anthropic SDK calls
│   ├── services/                   # OIG approval client and other services
│   └── data/                       # demo_store.py, initial_data.json (seed data)
├── packages/
│   ├── progear-sales-agent/        # Next.js frontend (chat, /tokens, /architecture)
│   └── progear-sales-mcp-server/   # Standalone JWT-validating MCP server (not yet wired into the chat flow)
├── docs/                           # architecture.md, implementation-guide.md, etc.
├── notebooks/                      # Layered customer Colab integration guide
├── examples/                       # Platform-neutral token exchange reference
├── .env.example                    # Environment variable template (names only, no real secrets)
└── README.md                       # This file
```

## License

MIT (see `package.json`).
