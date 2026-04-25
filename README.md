# ProGear Sales AI - Okta AI Agent Governance Demo

> **Enterprise AI Agent security demonstration** showcasing Okta AI Agent Governance with Cross App Access (XAA), ID-JAG token exchange, and role-based access control.

![Okta AI Agent](https://img.shields.io/badge/Okta-AI%20Agent%20Governance-blue)
![Cross App Access](https://img.shields.io/badge/XAA-ID--JAG-green)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-purple)

## What This Demo Shows

This application demonstrates **Okta AI Agent Governance** using **Cross App Access (XAA)** - the emerging standard for enterprise AI agent authentication that MCP (Model Context Protocol) has officially adopted.

### The Security Problem

When AI agents access enterprise data on behalf of users, you need to answer:
- **WHO** requested this access? (Which user?)
- **WHAT** AI system performed the action? (Which agent?)
- **WHEN** did it happen?
- **CAN** we revoke access immediately?

### What This Demo Proves

This demo implements **Scenario 2** from our [four scenarios framework](docs/okta-security-value.md#the-four-scenarios-how-ai-agents-access-your-data):

| Feature | Description |
|---------|-------------|
| **Cross App Access (XAA)** | Industry-standard pattern adopted by MCP for enterprise AI authentication |
| **ID-JAG Token Exchange** | Identity Assertion JWT Authorization Grant - every token contains user + agent identity |
| **Workload Principal (`wlp`)** | First-class AI agent identity in Okta Universal Directory |
| **Role-Based Access Control** | User group membership determines which scopes are granted |
| **Complete Audit Trail** | Every token exchange logged with who, what, when, why |
| **Instant Revocation** | One-click deactivation of any AI agent |

### Live Demo

- **Frontend**: [progear-sales-agent.vercel.app](https://progear-sales-agent.vercel.app)
- **Backend API**: [courtedge-progear-backend.onrender.com](https://courtedge-progear-backend.onrender.com)

### 📚 Documentation

| | |
|---|---|
| **[Security & Governance Guide](docs/okta-security-value.md)** | Understand the four scenarios, XAA/ID-JAG concepts, and why this matters |
| **[Implementation Guide](docs/implementation-guide.md)** | Deploy your own instance with step-by-step Okta configuration |

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────┐
│                         User Browser                          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  ProGear Sales Agent (Next.js 14 + React)               │  │
│  │  - Chat interface with AI agent                         │  │
│  │  - Real-time token exchange visualization               │  │
│  │  - Agent flow tracking                                  │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTPS
                                ▼
┌───────────────────────────────────────────────────────────────┐
│            FastAPI Backend (LangGraph Orchestrator)           │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Multi-Agent Workflow (LangGraph)                       │  │
│  │                                                         │  │
│  │  router → exchange_tokens → process_agents → response   │  │
│  │                                                         │  │
│  │  - Intent-based scope detection                         │  │
│  │  - ID-JAG token exchange per MCP                        │  │
│  │  - Graceful access denial handling                      │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬───────────────────────────────┘
                                │
      ┌───────────┬─────────────┼─────────────┬───────────┐
      │           │             │             │           │
      ▼           ▼             ▼             ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Sales   │ │ Inventory│ │ Customer │ │ Pricing  │ │   Okta   │
│   MCP    │ │   MCP    │ │   MCP    │ │   MCP    │ │   IdP    │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## Key Components

### 1. Frontend (Next.js 14)
- **Location**: `packages/progear-sales-agent/`
- **Auth**: NextAuth.js with Okta OIDC provider
- **Features**: Chat interface, token exchange visualization, architecture overview

### 2. Backend (FastAPI + LangGraph)
- **Location**: `backend/`
- **Orchestrator**: LangGraph workflow for multi-agent coordination
- **Auth**: Okta AI SDK for ID-JAG token exchange
- **LLM**: Anthropic Claude for routing and response generation

### 3. MCP Servers (4 Protected APIs)
Each MCP server has its own Okta Authorization Server:

| MCP Server | Audience | Scopes |
|------------|----------|--------|
| Sales | `api://progear-sales` | `sales:read`, `sales:quote`, `sales:order` |
| Inventory | `api://progear-inventory` | `inventory:read`, `inventory:write`, `inventory:alert` |
| Customer | `api://progear-customer` | `customer:read`, `customer:lookup`, `customer:history` |
| Pricing | `api://progear-pricing` | `pricing:read`, `pricing:margin`, `pricing:discount` |

### 4. Okta AI Agent Governance
- **Workload Principal (`wlp`)**: AI agent identity in Okta Universal Directory - first-class identity like users
- **Authentication**: JWT Bearer with RS256 private key (no shared secrets)
- **Token Exchange**: ID-JAG (Identity Assertion JWT Authorization Grant) - user + agent in every token
- **RBAC**: Group-based access policies - same model as human access
- **Governance**: Mandatory owner, instant revocation, complete audit trail

## Role-Based Access Control

Three user groups with different access levels:

| Group | Sales MCP | Inventory MCP | Customer MCP | Pricing MCP |
|-------|-----------|---------------|--------------|-------------|
| **ProGear-Sales** | Full access | Read only | Full access | Full access |
| **ProGear-Warehouse** | No access | Full access | No access | No access |
| **ProGear-Finance** | No access | No access | No access | Full access |

## Token Exchange Flow

```
1. User Login → Okta OIDC → ID Token
2. Chat Query → LangGraph Router → Determine agents + scopes needed
3. For each MCP:
   a. ID Token → Okta (ID-JAG Exchange) → ID-JAG Token
   b. ID-JAG Token → Auth Server → MCP Access Token (or DENIED)
4. Process with authorized agents
5. Generate unified response
```

## Deploy Your Own

Want to deploy this demo with your own Okta org? Follow the **[Implementation Guide](docs/implementation-guide.md)** for complete instructions on:

1. Configuring Okta (AI Agent, Authorization Servers, Users, Groups)
2. Deploying the frontend to **Vercel**
3. Deploying the backend to **Render**
4. Connecting everything together

## Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| **[Security & Governance Guide](docs/okta-security-value.md)** | Security teams, architects | The four scenarios framework, XAA/ID-JAG concepts, MCP adoption, governance model |
| **[Implementation Guide](docs/implementation-guide.md)** | Developers, DevOps | Complete deployment walkthrough for Vercel + Render with Okta configuration |
| **[Live Architecture Page](https://progear-sales-agent.vercel.app/architecture)** | Everyone | Interactive visualization of the token exchange flow in the running demo |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 14, React 18, Tailwind CSS, NextAuth.js |
| Backend | FastAPI, LangGraph, LangChain, Python 3.9+ |
| LLM | Anthropic Claude (claude-sonnet-4-20250514) |
| Auth | Okta OIDC, Cross App Access (XAA), ID-JAG Token Exchange |
| Deployment | Vercel (frontend), Render (backend) |

## Environment Variables

See `.env.example` for the complete list. Key variables:

```bash
# Okta
OKTA_DOMAIN=https://your-org.okta.com
OKTA_AI_AGENT_ID=wlp...
OKTA_AI_AGENT_PRIVATE_KEY={"kty":"RSA",...}

# Authorization Servers (one per MCP)
OKTA_SALES_AUTH_SERVER_ID=aus...
OKTA_INVENTORY_AUTH_SERVER_ID=aus...
OKTA_CUSTOMER_AUTH_SERVER_ID=aus...
OKTA_PRICING_AUTH_SERVER_ID=aus...

# LLM
ANTHROPIC_API_KEY=sk-ant-...
```

## Project Structure

```
courtedge-ai-demo/
├── backend/
│   ├── api/main.py              # FastAPI endpoints
│   ├── auth/
│   │   ├── agent_config.py      # Agent configuration
│   │   ├── multi_agent_auth.py  # ID-JAG token exchange
│   │   └── okta_auth.py         # Okta authentication
│   └── orchestrator/
│       └── orchestrator.py      # LangGraph workflow
├── packages/
│   └── progear-sales-agent/     # Next.js frontend
│       ├── src/app/
│       │   ├── page.tsx         # Chat interface
│       │   └── architecture/    # Architecture page
│       ├── src/components/      # React components
│       └── src/lib/auth.ts      # NextAuth config
├── .env.example                 # Environment template
└── README.md                    # This file
```

## License

MIT License - See LICENSE file for details.

---

**Built to demonstrate Okta AI Agent Governance with Cross App Access (XAA)** - the same pattern MCP has adopted for enterprise AI authentication.
