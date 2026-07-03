# ProGear Sales AI — Okta AI Agent Governance + Auth0 FGA Demo

> A sales-demo app for **CourtEdge ProGear**, a basketball-equipment retailer. An AI shopping/sales assistant is secured end-to-end with **Okta AI Agent Governance** (Workload Principal identity, ID-JAG token exchange), **Auth0 Fine-Grained Authorization (FGA)** for relationship- and context-aware inventory checks, and **Okta Identity Governance (OIG)** for human-in-the-loop approval on large orders.

![Okta AI Agent Governance](https://img.shields.io/badge/Okta-AI%20Agent%20Governance-blue)
![Auth0 FGA](https://img.shields.io/badge/Auth0-FGA-orange)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-purple)

## Live Demo

| | |
|---|---|
| **Frontend** | [progear-sales-aiagent.vercel.app](https://progear-sales-aiagent.vercel.app) |
| **Backend API** | [progearsalesai-p2wm.onrender.com](https://progearsalesai-p2wm.onrender.com) |

Both are deployed from this single repo and auto-deploy on every push to `main` (Vercel builds `packages/progear-sales-agent`; Render builds the `backend/` service).

Pages in the running app:

| Route | What it shows |
|---|---|
| `/` | The chat UI ("CourtEdge ProGear") — talk to the sales assistant |
| `/tokens` | Raw token exchanges, FGA checks, and pending approvals as they happen |
| `/architecture` | Interactive D3.js diagrams — a relationship graph (with the four business domains — Inventory, Customer, Pricing, Sales — as separate boxes) and a UML-style sequence walkthrough of 4 scenarios (happy path, access denied, blocked on vacation, needs approval) |

## What This Demo Shows

An AI sales agent needs to read and write real business data (inventory, pricing, customer records) on a user's behalf. This demo answers the questions that matter for enterprise AI agent security:

- **WHO** requested this access, and **WHAT** agent acted on their behalf?
- **WHICH** scopes were actually granted, per agent, per user?
- **CAN** a second, contextual check (relationship, clearance, vacation status) still block an otherwise-authorized action?
- **WHEN** does a human need to approve before an action executes?
- **CAN** access be revoked instantly?

| Layer | Technology | What it does |
|---|---|---|
| Identity for the agent | Okta AI Agent Governance | The AI has its own Workload Principal (`wlp`) identity, distinct from any human user |
| Token exchange | ID-JAG (Identity Assertion JWT Authorization Grant) | Two-step exchange: ID token → ID-JAG assertion (Org Authorization Server) → scoped access token (per-domain Custom Authorization Server). RSA keypair auth, no shared secret. No down-scoping — an ungrantable scope fails the whole exchange. |
| Fine-grained authorization | Auth0 FGA | Second layer for inventory actions — relationship checks (active manager), clearance-level checks, and a live vacation-flag check, on top of Okta's coarse-grained RBAC |
| Human-in-the-loop | Okta Identity Governance (OIG) | Large inventory writes (≥500 units by default) route to an approval workflow instead of executing immediately |
| Orchestration | LangGraph | Routes each user query to the right domain agent(s) and coordinates multi-agent responses |
| LLM calls | Anthropic Claude, via the raw Anthropic SDK | Each domain agent calls Claude directly (not through LangChain's LLM wrapper) for routing/response generation |

For the full technical walkthrough — sequence diagrams, token shapes, FGA model, approval flow — see **[docs/architecture.md](docs/architecture.md)**.

## The 4 Domain Agents

Each agent has its own Okta Custom Authorization Server and its own scopes — a user's group membership determines which agents (and which scopes within each agent) they can actually invoke.

| Agent | Scopes |
|---|---|
| Sales | `sales:read`, `sales:quote`, `sales:order` |
| Inventory | `inventory:read`, `inventory:write`, `inventory:alert` |
| Customer | `customer:read`, `customer:lookup`, `customer:history` |
| Pricing | `pricing:read`, `pricing:margin`, `pricing:discount` |

## Demo Data

90 inventory SKUs across 8 categories (Basketballs, Hoops & Backboards, Nets & Accessories, Uniforms & Apparel, Training Equipment, Footwear, Court & Game Equipment, Bags & Storage) and 34 customers, defined in `backend/data/initial_data.json` and served through `backend/data/demo_store.py`. On boot, the backend regenerates a runtime snapshot at `backend/data/live_data.json` (gitignored — it's derived state, never commit it and never hand-edit it).

## Tech Stack

| Area | Stack |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, NextAuth.js (Okta OIDC), D3.js (architecture visualizations) |
| Backend | Python, FastAPI (`backend/api/main.py`) |
| Orchestration | LangGraph (`langgraph>=0.2.0` — a real dependency, not just a label) — `backend/orchestrator/orchestrator.py` |
| LLM integration | Anthropic Python SDK, called directly per agent (no LangChain LLM wrapper) |
| AuthN/AuthZ | Okta AI Agent Governance (ID-JAG), Auth0 FGA (`openfga-sdk`), Okta Identity Governance |
| Deployment | Vercel (frontend), Render (backend) |

### A known, honest limitation

There's a real, working MCP server in this repo (`packages/progear-sales-mcp-server` — a JWT-validating Express server that verifies tokens against Okta's JWKS endpoint), deployed separately. **It is not currently in the live request path.** The backend's domain agents call `demo_store` in-process rather than calling out to that MCP server over HTTP. The MCP server exists and works, but wiring it into the chat flow is future work, not something already happening in production today.

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

Copy `.env.example` to `.env` and fill in real values before running anything — see it for every variable name used across the frontend, backend, and MCP server (Okta org/app/agent config, Anthropic key, Auth0 FGA store, etc.).

For a full walkthrough — Okta org setup (AI Agent, Custom Authorization Servers, groups), Auth0 FGA store setup, and deploying to Vercel + Render — see **[docs/implementation-guide.md](docs/implementation-guide.md)**.

## Documentation

| Document | Audience | Description |
|---|---|---|
| **[docs/architecture.md](docs/architecture.md)** | Anyone who wants to understand how it works | Full system walkthrough: token exchange sequence, FGA model, approval flow, MCP notes |
| **[docs/implementation-guide.md](docs/implementation-guide.md)** | Developers, DevOps | Complete deployment walkthrough — Okta configuration, Vercel + Render setup |
| **[docs/okta-security-value.md](docs/okta-security-value.md)** | Security teams, architects | The broader security framing and scenario catalog this demo draws on, including the *why* behind each design decision (why 4 auth servers, why FGA as a second layer, why human approval) |
| **[docs/okta-ai-security-essentials.md](docs/okta-ai-security-essentials.md)** | Marketers, executives, non-technical readers | The same value story as above, in plain English — no JWT/scope/issuer jargon |
| **[/architecture](https://progear-sales-aiagent.vercel.app/architecture)** (live) | Everyone | Interactive D3.js diagrams of the token exchange and access-control flows |

## Project Structure

```
ProGearSalesAI/
├── backend/
│   ├── api/main.py                 # FastAPI app and endpoints
│   ├── agents/                     # Sales, Inventory, Customer, Pricing agents
│   ├── auth/
│   │   ├── agent_config.py         # Per-agent Okta config (IDs, keys, scopes)
│   │   ├── multi_agent_auth.py     # ID-JAG token exchange
│   │   └── fga_client.py           # Auth0 FGA checks (relationship, clearance, vacation)
│   ├── orchestrator/
│   │   └── orchestrator.py         # LangGraph workflow + direct Anthropic SDK calls
│   ├── services/                   # OIG approval client and other services
│   └── data/                       # demo_store.py, initial_data.json (seed data)
├── packages/
│   ├── progear-sales-agent/        # Next.js frontend (chat, /tokens, /architecture)
│   └── progear-sales-mcp-server/   # Standalone JWT-validating MCP server (not yet wired into the chat flow)
├── docs/                           # architecture.md, implementation-guide.md, etc.
├── .env.example                    # Environment variable template (names only, no real secrets)
└── README.md                       # This file
```

## License

MIT (see `package.json`).
