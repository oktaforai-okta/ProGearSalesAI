# Implementation Guide: ProGear Sales AI with Okta AI Agent Governance

> Complete step-by-step guide to deploying this demo in your own environment

## Table of Contents

1. [Introduction](#introduction)
2. [Deployment Order Overview](#deployment-order-overview)
3. [Understanding the Architecture](#understanding-the-architecture)
4. [What is Vercel?](#what-is-vercel)
5. [What is Render?](#what-is-render)
6. [How Vercel and Render Work Together](#how-vercel-and-render-work-together)
7. [Prerequisites](#prerequisites)
8. [Okta Configuration](#okta-configuration)
9. [Recovering from an Accidentally Deleted AI Agent](#recovering-from-an-accidentally-deleted-ai-agent)
10. [Clone and Deploy to Vercel (Frontend)](#clone-and-deploy-to-vercel-frontend)
11. [Deploy to Render (Backend)](#deploy-to-render-backend)
12. [Connect Frontend to Backend](#connect-frontend-to-backend)
13. [Environment Variables Reference](#environment-variables-reference)
14. [Demo Scenarios](#demo-scenarios)
15. [Demo Script](#demo-script)
16. [Troubleshooting](#troubleshooting)
17. [Verification Checklist](#verification-checklist)

---

## Introduction

This guide is designed for two types of users:

### Who This Guide is For

**1. Learners Building Their Own Chatbot**
If you want to understand how to build an AI chatbot with enterprise-grade security using Okta AI Agent Governance, this guide walks through every configuration step. The application may use multiple internal workflow components, but Okta governs one ProGear Sales Agent identity. You'll learn:
- How the AI agent authenticates and acts on behalf of users
- How to implement Role-Based Access Control (RBAC) with Okta groups
- How per-domain Okta Custom Authorization Servers scope what the agent can do in each resource domain
- How token exchange preserves user identity through the AI pipeline

**2. Quick Deployers**
If you want to clone this repository, deploy it to Vercel and Render, and configure your own Okta instance to see the demo in action, follow the step-by-step deployment sections.

### What You'll Deploy

A basketball equipment sales AI assistant with:
- **1 governed AI Agent**: ProGear Sales Agent, with four internal domain components for Sales, Inventory, Customer, and Pricing
- **4 Demo Users**: Sarah Sales, Mike Manager, Joe VP, and Frank Finance
- **Role-Based Access Control**: Users only see data they're authorized to access
- **Visual Token Exchange**: See exactly which scopes are granted/denied in real-time
- **Sample Data Included**: The repository includes realistic demo data for customers, products, inventory, and pricing - no database setup required

---

## Deployment Order Overview

Before diving in, understand the order of operations. There's a circular dependency between services that we solve by deploying in stages:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      RECOMMENDED DEPLOYMENT ORDER                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 1: Initial Okta Setup                                            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ • Register AI Agent and enable direct User access                  │  │
│  │ • Create Demo Users and Groups                                    │  │
│  │ • Register AI Agent and download private key                      │  │
│  │ • Create 4 Authorization Servers with policies                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                   ▼                                     │
│  PHASE 2: Deploy Frontend to Vercel                                     │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ • Fork repo and import to Vercel                                  │  │
│  │ • Get your Vercel URL (e.g., my-app.vercel.app)                   │  │
│  │ • Configure environment variables                                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                   ▼                                     │
│  PHASE 3: Deploy Backend to Render                                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ • Create web service from your fork                               │  │
│  │ • Get your Render URL (e.g., my-backend.onrender.com)             │  │
│  │ • Configure environment variables (including CORS for Vercel)    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                   ▼                                     │
│  PHASE 4: Connect Everything                                            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ • Update Vercel with Render URL                                   │  │
│  │ • Update Okta redirect URIs with real Vercel URL                  │  │
│  │ • Test the complete flow                                          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

> **Why this order?** You need the Vercel URL to configure Okta redirects, and you need the Render URL to configure the frontend. By using placeholder values initially, you can complete each phase and then circle back to connect them.

---

## Understanding the Architecture

Before diving into deployment, understand how the pieces fit together:

```
┌───────────────────────────────────────────────────────────────────┐
│                             USER                                  │
│                   (Browser on any device)                         │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  │ HTTPS
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                        VERCEL (Frontend)                          │
│                                                                   │
│   ┌───────────────────────────────────────────────────────────┐   │
│   │                   Next.js Application                     │   │
│   │                                                           │   │
│   │  • Chat interface (full-width, at /)                      │   │
│   │  • Token/FGA/approval inspection (at /tokens)              │   │
│   │  • User authentication (NextAuth.js + Okta)               │   │
│   │  • Architecture page (D3 diagrams)                         │   │
│   └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│   URL: https://your-app.vercel.app                                │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  │ API calls with ID token
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                        RENDER (Backend)                           │
│                                                                   │
│   ┌───────────────────────────────────────────────────────────┐   │
│   │                   FastAPI Application                     │   │
│   │                                                           │   │
│   │  • LangGraph orchestrator (routes by resource domain)      │   │
│   │  • Okta token exchange (ID -> ID-JAG -> scoped token)      │   │
│   │  • 4 in-process domain components (Sales, Inventory,      │   │
│   │    Customer, Pricing) with separate Custom AS boundaries   │   │
│   │  • FGA + Okta Identity Governance checks                  │   │
│   │  • Claude via the raw Anthropic SDK                       │   │
│   └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│   URL: https://your-backend.onrender.com                          │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  │ Token exchange requests
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                             OKTA                                  │
│                                                                   │
│   • User authentication (OIDC)                                    │
│   • AI Agent identity (wlp...)                                    │
│   • Org AS (step 1) + 4 per-domain Custom AS (step 2)              │
│   • Group-based access policies                                   │
│   • Audit logging (System Log)                                    │
│                                                                   │
│   URL: https://your-org.okta.com                                  │
└───────────────────────────────────────────────────────────────────┘
```

### The Token Exchange Flow

When a user sends a message:

```
1. User authenticates via Okta → Frontend receives ID token
2. Frontend sends message + ID token to Backend
3. Backend exchanges ID token → ID-JAG assertion at the Org AS (AI Agent acting for user)
4. Backend exchanges the ID-JAG → a scoped access token for each required resource domain, at that domain's Custom Authorization Server
5. If the user's group doesn't match policy → token denied (access control!)
6. Backend invokes each authorized internal domain component in-process with its granted scope (see docs/architecture.md for the current, honest MCP-server status)
7. Response flows back to user with visualization of what was granted/denied
```

---

## What is Vercel?

### Overview

**Vercel** is a cloud platform optimized for frontend frameworks, especially Next.js (which was created by Vercel). It handles deployment, hosting, and scaling of web applications.

### Why We Use Vercel for the Frontend

| Feature | Benefit for This Demo |
|---------|----------------------|
| **Zero-config deployment** | Push to GitHub → automatically deployed |
| **Global CDN** | Fast load times worldwide |
| **Serverless functions** | API routes run as serverless functions |
| **Environment variables** | Secure storage for Okta credentials |
| **Preview deployments** | Every PR gets its own URL for testing |
| **HTTPS by default** | Required for Okta OAuth callbacks |

### How Vercel Works

1. **Connect your GitHub repo** - Vercel watches for changes
2. **Automatic builds** - Every push triggers a new deployment
3. **Instant rollbacks** - Previous versions always available
4. **Custom domains** - Use your own domain or Vercel's subdomain

### What Vercel Hosts in This Demo

```
packages/progear-sales-agent/src/
├── app/
│   ├── api/auth/           # NextAuth.js Okta integration
│   ├── page.tsx            # Main chat UI (/)
│   ├── tokens/page.tsx     # Token/FGA/approval inspection (/tokens)
│   └── architecture/page.tsx    # Interactive D3 diagrams (/architecture)
├── components/             # RawTokensCard, FGAExplanationCard, FGAControlsPanel,
│                           # ApprovalStatusCard, D3ArchitectureDiagram,
│                           # SequenceDiagram, UserIdentityCard
└── lib/                    # NextAuth config, shared helpers
```

### Vercel Pricing

- Vercel's Hobby plan is sufficient for this frontend demo.
- Team and production needs may require a paid plan. Check [current Vercel pricing](https://vercel.com/pricing) rather than relying on a hard-coded amount.

---

## What is Render?

### Overview

**Render** is a cloud platform for hosting backends, databases, and services. It's an alternative to Heroku, AWS, or Google Cloud, but simpler to use.

### Why We Use Render for the Backend

| Feature | Benefit for This Demo |
|---------|----------------------|
| **Native Python support** | Runs FastAPI directly |
| **Long-running web service** | Supports the FastAPI process and approval poller |
| **Environment groups** | Share env vars across services |
| **Private networking** | Secure service-to-service communication |
| **Automatic HTTPS** | Required for API calls from Vercel |
| **Built-in monitoring** | Logs, metrics, and alerts |

### How Render Works

1. **Connect your GitHub repo** - Render watches the `backend` directory
2. **Auto-detect runtime** - Sees `requirements.txt`, knows it's Python
3. **Build and deploy** - Installs dependencies, starts uvicorn
4. **Assign URL** - Your backend gets `https://your-app.onrender.com`

### What Render Hosts in This Demo

```
backend/
├── api/
│   └── main.py              # FastAPI app, CORS, routes, approval poller
├── agents/                  # Internal Sales, Inventory, Customer, Pricing components
│                             # (each calls demo_store in-process + the
│                             #  raw Anthropic SDK -- not separate MCP
│                             #  servers; see docs/architecture.md §7)
├── orchestrator/
│   └── orchestrator.py      # LangGraph workflow (router -> token
│                             # exchange -> FGA check -> approval gate ->
│                             # process agents -> generate response)
├── auth/
│   ├── multi_agent_auth.py  # The real ID-JAG token exchange
│   └── fga_client.py        # FGA checks
├── services/                # OIG approval client, intent parsing
├── data/                    # demo_store.py, initial_data.json (seed)
└── requirements.txt         # Python dependencies
```

There's also a separately deployable MCP sample (`packages/progear-sales-mcp-server`), but the backend components above don't call it over the network today and its local-demo authentication bypasses must be removed before production use. See [architecture.md](./architecture.md#7-known-honest-limitation-the-mcp-server-isnt-in-the-live-path-yet) for the full explanation.

### Render Pricing

- **Free web service**: Suitable for initial testing, but it spins down after inactivity and cannot attach a persistent disk.
- **Paid web service**: Always on and required for the persistent approval ledger.
- Check [current Render pricing](https://render.com/pricing) before choosing an instance type.

---

## How Vercel and Render Work Together

### The Split Architecture

| Component | Platform | Why |
|-----------|----------|-----|
| **Frontend** (Next.js) | Vercel | Optimized for React/Next.js, great DX |
| **Backend** (FastAPI) | Render | Python support, persistent processes |

### Communication Flow

```
┌──────────────┐       HTTPS API calls        ┌──────────────┐
│    Vercel    │ ──────────────────────────▶  │    Render    │
│  (Frontend)  │                              │   (Backend)  │
│              │ ◀──────────────────────────  │              │
└──────────────┘       JSON responses         └──────────────┘
       │                                             │
       │                                             │
       │ Okta OAuth login                            │ Okta token exchange
       │ (browser redirect)                          │ (server-to-server)
       ▼                                             ▼
┌───────────────────────────────────────────────────────────┐
│                          OKTA                             │
│                                                           │
│  • Authenticates users (issues ID tokens to frontend)     │
│  • Validates AI Agent identity (backend JWT assertion)    │
│  • Issues scoped access tokens based on user's group      │
│    membership + policy evaluation                          │
└───────────────────────────────────────────────────────────┘
```

### Key Configuration Points

For Vercel and Render to communicate:

1. **CORS**: Render must allow requests from your Vercel URL
   ```
   CORS_ORIGINS=https://your-app.vercel.app
   ```

2. **API URL**: Vercel must know where to send API requests
   ```
   NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
   ```

3. **Okta callbacks**: Both URLs must be in Okta's redirect URIs
   ```
   Sign-in: https://your-app.vercel.app/api/auth/callback/okta
   ```

### Why This Architecture?

| Consideration | Why Split? |
|--------------|-----------|
| **Language optimization** | Next.js (JavaScript) + FastAPI (Python) |
| **Scaling** | Frontend and backend scale independently |
| **Cost efficiency** | Use best-fit platform for each workload |
| **Developer experience** | Vercel's Next.js tooling is unmatched |
| **AI libraries** | Python has better AI/ML ecosystem (LangChain, etc.) |

---

## Prerequisites

### Required Accounts

| Service | Purpose | Sign Up |
|---------|---------|---------|
| **Okta** | Identity & AI Agent Governance | [developer.okta.com](https://developer.okta.com) |
| **Anthropic** | Claude AI for LLM | [console.anthropic.com](https://console.anthropic.com) |
| **FGA** | Hosted fine-grained authorization | [dashboard.fga.dev](https://dashboard.fga.dev) |
| **Vercel** | Frontend hosting | [vercel.com](https://vercel.com) |
| **Render** | Backend hosting | [render.com](https://render.com) |
| **GitHub** | Repository hosting | [github.com](https://github.com) |

> **Important Account Setup Notes:**
> - **Sign up for Vercel and Render using your GitHub account** - this makes connecting your repository seamless
> - Your **Okta org must have the features listed below**; an Integrator Free Plan org alone does not guarantee AI Agent Governance or OIG access
> - Anthropic API usage is billed according to your account and selected model; check the provider's current pricing before running a public demo

### Okta Requirements

Your Okta org must have:
- **AI Agent feature enabled** (contact Okta support if not visible in admin console)
- **Custom Authorization Servers** enabled
- **[Okta Identity Governance subscription](https://developer.okta.com/docs/api/iga)** for the OIG Access Requests API and 601+ approval flow
- Admin access to create applications and authorization servers

### Render Tier Consideration

> **⚠️ Render Free Tier Limitation**
>
> The free tier works but has a significant limitation: **services spin down after 15 minutes of inactivity**. When you visit the demo after inactivity, the first request takes 30-60 seconds while Render "wakes up" the backend.
>
> | Tier | Cost | Behavior |
> |------|------|----------|
> | **Free** | $0/month | Cold starts after 15 min inactivity |
> | **Paid** | See current pricing | Always on; supports the persistent approval disk |
>
> You can start with Free for the base chat and upgrade later. The 601+ approval flow needs a Render persistent disk for its private intent and idempotency ledger. Persistent disks require a paid service; see [Render's persistent disk documentation](https://render.com/docs/disks).

---

## Okta Configuration

This is the most critical section. Follow each step carefully using your own Okta organization.

### Step 1: Create Demo Users

Create four demo users to showcase resource access and the Inventory role levels:

1. Navigate to **Directory** → **People** → **Add Person**
2. Create these users:

   | Username | First Name | Last Name | Email | Password |
   |----------|------------|-----------|-------|----------|
   | `sarah.sales` | Sarah | Sales | sarah.sales@`<your-domain>` | `<your-secure-password>` |
   | `mike.manager` | Mike | Manager | mike.manager@`<your-domain>` | `<your-secure-password>` |
   | `joe.vp` | Joe | VP | joe.vp@`<your-domain>` | `<your-secure-password>` |
   | `frank.finance` | Frank | Finance | frank.finance@`<your-domain>` | `<your-secure-password>` |

3. **Important**: Uncheck "User must change password on first login" for demo purposes

> **Note**: Use any email domain you control, or use your Okta organization's default domain. The passwords should be secure - these are demo users but treat them like any other credential.

### Step 2: Create User Groups

Create four groups to demonstrate RBAC and the fixed Inventory roles:

1. Navigate to **Directory** → **Groups**
2. Click **Add Group** and create:

   | Group Name | Description |
   |------------|-------------|
   | `ProGear-Sales` | Sales team - full agent access |
   | `ProGear-Managers` | Managers - Inventory read/write and routine changes |
   | `ProGear-VPs` | VPs - Inventory read/write and high-impact approval |
   | `ProGear-Finance` | Finance team - pricing only |

3. **Assign users to groups:**

   For each group, click the group name → **Assign People** button → search for and add the user:

   | User | Group | Access Level |
   |------|-------|--------------|
   | Sarah Sales | `ProGear-Sales` | Agent access across all four resource domains |
   | Mike Manager | `ProGear-Managers` | Inventory read/write; Level 1 controls the routine-write decision |
   | Joe VP | `ProGear-VPs` and `ProGear-Managers` | Inventory read/write; Level 2 controls the VP decision |
   | Frank Finance | `ProGear-Finance` | Agent access to the Pricing domain only |

   > **Verification:** Click on each user in **Directory** → **People** and check the **Groups** tab to confirm they're in the correct group.

#### Configure the Inventory role and delegation context

For Inventory, `clearance_level` is the authoritative role source. `is_a_manager` is synchronized from it; `is_on_vacation` is a separate global delegation control:

| Value | Role | Manager | Write 1–600 units | Write 601+ units |
|---:|---|---|---|---|
| 0 | Sales | False | Deny; contact manager | Deny; contact manager |
| 1 | Manager | True | Direct | Direct with FGA off; VP approval with FGA enabled |
| 2 | VP | True | Direct | Direct |

1. Add a user-profile property named `clearance_level` and label it **Clearance level**. Its description should state `0 = Sales, 1 = Manager, 2 = VP`.
2. Add `is_a_manager` as a Boolean titled **Manager**. Map or synchronize it to False at Level 0 and True at Levels 1–2; do not let it drift as a second role source.
3. Add `is_on_vacation` as a Boolean titled **On vacation**, default False. When true, the backend stops all agent delegation before ID-JAG, including reads.
4. Set Sarah to Level 0 / Manager False, Mike to Level 1 / Manager True, and the VP demo persona (Joe) to Level 2 / Manager True. Set vacation False for all three starting personas.
5. Create `ProGear-Managers` with a group rule matching Level 1 or 2.
6. Create `ProGear-VPs` with a group rule matching Level 2.

The three named users are demo fixtures only. ProGear does not match Sarah's, Mike's, or Joe's email address in authorization code; it resolves every authenticated user by Okta subject and applies the current profile values. For repeatable onboarding, assign the role and synchronized Manager value through your Okta identity-lifecycle or profile-mapping process so any new Sales, Manager, or VP user automatically follows the same policy. Maintain vacation separately as live user context.

`clearance_level` remains authoritative for normal application authorization. The Manager Boolean exists to make role context explicit in Okta, tokens, and demos, and production identity-lifecycle mappings must keep it synchronized with the role.

The `/fga` page does not update Okta. Role and Manager are read-only reflections of the live profile; only the vacation demonstration uses a short-lived server-side overlay keyed by the validated employee subject and an opaque browser-tab id. This keeps simultaneous demos with shared Sarah/Mike credentials independent. In production, keep the real properties read-only to the employee and update them through an administrator, lifecycle workflow, or trusted profile mapping; otherwise stolen employee credentials could clear the vacation containment signal.

### Step 3: Register the AI Agent and Configure Access

This is where the AI Agent identity and user-facing sign-in app are connected. Do the sub-steps in order; the workload identity and web-client credentials remain separate even when Okta binds them natively.

1. Navigate to **Directory** → **AI Agents**
   - If you don't see this menu item, contact Okta support to enable AI Agent Governance for your org
2. Click **Register AI Agent** and provide the following details:

   ```
   Name: ProGear Sales Agent
   Description: AI sales assistant with four internal resource-domain components
   ```

   When prompted to assign Owners, select the currently logged in Okta admin or any other user you have as the owner, and save. Owners are admins responsible for the agent; they are not the end users the agent acts on behalf of (see the callout below).

3. **Add Credentials (Key #1: the agent's own workload key).** This key signs the JWTs the backend uses for its ID-JAG and JWT-bearer exchanges with your Custom Authorization Servers.
   - Select the registered agent and navigate to the **Credentials** tab
   - Click **Add Public Key** → **Generate new key pair**
   - Okta generates an RS256 public/private key pair
   - **Download and save the private key (JWK format)** - click the download button

   The downloaded file contains JSON like this:
   ```json
   {
     "kty": "RSA",
     "kid": "your-unique-key-id",
     "alg": "RS256",
     "n": "base64-encoded-modulus...",
     "e": "AQAB",
     "d": "base64-encoded-private-exponent...",
     "p": "base64-encoded-prime-p...",
     "q": "base64-encoded-prime-q...",
     "dp": "base64-encoded-dp...",
     "dq": "base64-encoded-dq...",
     "qi": "base64-encoded-qi..."
   }
   ```

   > **⚠️ CRITICAL: Converting JWK to Single-Line Format**
   >
   > Environment variables cannot contain line breaks. You MUST convert the multi-line JSON to a single line.
   >
   > **Method 1: Online Tool**
   > 1. Go to [jsonformatter.org/json-minify](https://jsonformatter.org/json-minify)
   > 2. Paste your JWK JSON
   > 3. Click "Minify"
   > 4. Copy the single-line result
   >
   > **Method 2: Command Line (Mac/Linux)**
   > ```bash
   > cat your-downloaded-key.json | tr -d '\n' | tr -s ' '
   > ```
   >
   > **Method 3: Manual**
   > 1. Open the JSON file in a text editor
   > 2. Remove all line breaks and extra spaces
   > 3. Result should look like: `{"kty":"RSA","kid":"xxx","alg":"RS256","n":"xxx",...}`
   >
   > **Store this single-line version** - you'll paste it into Render's environment variables as `OKTA_AI_AGENT_PRIVATE_KEY`.

4. **Configure employee User access.**
   - Prefer the AI Agent's supported **User access** flow when it is enabled in your tenant. During the compatibility period used by this production demo, create a fresh OIDC web app and add the supported ID-token delegation link to the Workload Principal. Do not assume the OIDC client ID and Workload Principal ID are identical.
   - Assign the ProGear access groups you created in Step 2 to the newly created app.
   - Configure the app with your callback URL, for example:

     ```text
     https://your-app.vercel.app/api/auth/callback/okta
     ```

   - Enable `authorization_code`, `refresh_token`, token exchange, and JWT bearer grants. Keep client authentication set to **Public key / Private key** (`private_key_jwt`).

5. **Add Credentials (Key #2: the dedicated web-runtime key).** This is a second, separate RSA key pair, distinct from the agent workload key in step 3. It authenticates the Vercel frontend's `authorization_code` and `refresh_token` requests to the direct User access app.
   - Generate the key pair, add only its public JWK under the app's client credentials, and store the private JWK in the server-only `OKTA_OIDC_PRIVATE_KEY` environment variable. Never use a `NEXT_PUBLIC_` prefix for private key material.

6. **Activate** the agent.
7. Copy both identifiers: the OIDC web-client ID used for sign-in (an `0oa...` ID in this deployment) and the Agent ID (starts with `wlp...`).

In this repository's current compatibility deployment, `OKTA_CLIENT_ID` is the OIDC web-client ID (`0oa...`) and `OKTA_AI_AGENT_ID` is the distinct Workload Principal ID (`wlp...`). Neither private key is a client secret, and the two keys are never interchangeable.

> **CRITICAL: AI Agent Owners vs User Assignments**
>
> These are two completely different concepts - don't confuse them!
>
> | Concept | What it is | Where configured | Who to add |
> |---------|------------|------------------|------------|
> | **Owners** | Admins responsible for the agent | AI Agent → Owners tab | Admin users (yourself, your team) |
> | **User Assignments** | Users the agent acts on behalf of | Direct User access app → Assignments tab | End users (Sarah, Mike, Joe, Frank) |
>
> Users are assigned to the agent-linked **direct User access OIDC app**, and the agent can then act on behalf of any user who:
> 1. Is assigned to the direct User access app
> 2. Passes the access policy rules (group membership)

> **Two distinct runtime keys, not one.** Steps 3 and 5 above create two unrelated key pairs with two unrelated jobs: the agent workload key (Step 3) signs backend ID-JAG and JWT-bearer requests, and the web-runtime key (Step 5) signs the frontend's `private_key_jwt` sign-in and refresh requests. Rotating or replacing one never requires touching the other.

> **Binding behavior is release-dependent.** Okta temporarily rolled back a newer client-to-agent binding model to give customers migration time. The production recovery described in this repository uses a fresh OIDC web app plus a delegation link because that was the compatible behavior enabled in the tenant at recovery time. Do not treat a preview schema or an earlier tenant behavior as a permanent platform contract. Before provisioning or migrating this boundary, verify the behavior currently enabled in the target org and read [Okta AI Agent Client Binding Compatibility](agent-client-binding-compatibility.md).

### Step 4: Create Authorization Servers (4 MCP APIs)

Create one authorization server per MCP API. Each represents a different domain of your business data.

> **Important: User Login via the Org Authorization Server**
>
> Users must log in through the **Org Authorization Server** (not a Custom Authorization Server).
>
> This is required because the Okta AI SDK always performs Step 1 of the token exchange (ID Token → ID-JAG) at the Org AS. If users log in via a Custom AS, their ID token's issuer won't match, and the token exchange will fail.
>
> When configuring the frontend, set `NEXT_PUBLIC_OKTA_ISSUER` to just your Okta org URL (without an auth server ID in the path).

#### 5.1 Sales MCP Authorization Server

1. Navigate to **Security** → **API** → **Authorization Servers**
2. Click **Add Authorization Server**
3. Configure:

   ```
   Name: ProGear Sales MCP
   Audience: api://progear-sales
   Description: Authorization for Sales MCP API
   ```

4. Click **Save**

5. **Extract the Authorization Server ID:**

   After saving, you'll see an **Issuer URI** that looks like this:
   ```
   https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXX
   ```

   The **Authorization Server ID** is the last segment after `/oauth2/`:
   ```
   ausXXXXXXXXXXXXXX  ← This is your Auth Server ID
   ```

   Copy this ID - you'll need it for:
   - `OKTA_SALES_AUTH_SERVER_ID` (Sales MCP access - Step 2 token exchange)

6. **Add Scopes:**
   - Go to **Scopes** tab → **Add Scope**
   - Add these scopes:

   | Name | Description | Default Scope |
   |------|-------------|---------------|
   | `sales:read`  | View sales data | No |
   | `sales:quote` | Create quotes   | No |
   | `sales:order` | Create/modify orders | No |

7. **Add Access Policy:**
   - Go to **Access Policies** tab → **Add Policy**

   ```
   Name: Sales Agent Policy
   Description: Controls access to Sales MCP
   Assign to: ProGear Sales Agent
   ```

8. **Add Policy Rule:**
   - Inside the policy, click **Add Rule**

   ```
   Rule Name: Sales Group Access
   IF Grant type is: Authorization Code, Token Exchange, JWT Bearer
   AND User is: Assigned the app and a member of: ProGear-Sales
   AND Scopes requested: sales:read, sales:quote, sales:order
   ```

#### 5.2 Inventory MCP Authorization Server

Repeat the process:

```
Name: ProGear Inventory MCP
Audience: api://progear-inventory
Description: Authorization for Sales Inventory API
```

**Scopes:**
- `inventory:read` - View inventory levels
- `inventory:write` - Modify inventory

**Access Policy:**
   ```
   Name: Inventory Agent Policy
   Description: Controls access to Inventory MCP
   Assign to: ProGear Sales Agent
   ```

**Policy Rules:**

Before adding the workflow-service rule, create one OIDC **API Services** app named
`ProGear Approval Executor`:

1. Enable only the `client_credentials` grant.
2. Set client authentication to **Public key / Private key** (`private_key_jwt`).
3. Register only its public JWK in Okta. Store the private JWK as
   `OKTA_APPROVAL_EXECUTOR_PRIVATE_KEY` on Render.
4. Add this service app, along with the ProGear Sales Agent, to the Inventory
   policy's assigned clients.

Do not add `client_credentials` to the AI Agent workload principal. Workload
principal OAuth metadata is governed by Okta and isn't an application setting
to repurpose for background execution.

**Rule 1: VP Inventory Access** (Priority 1)
```
IF Grant type is: Authorization Code, Token Exchange, JWT Bearer
AND User is member of: ProGear-VPs
AND Scopes: inventory:read, inventory:write
```

**Rule 2: Manager Inventory Access** (Priority 2)
```
IF Grant type is: Authorization Code, Token Exchange, JWT Bearer
AND User is member of: ProGear-Managers
AND Scopes: inventory:read, inventory:write
```

**Rule 3: Sales Inventory Read** (Priority 3)
```
IF Grant type is: Authorization Code, Token Exchange, JWT Bearer
AND User is member of: ProGear-Sales
AND Scopes: inventory:read
```

**Rule 4: Approved Workflow Service Execution** (Priority 4)
```
IF Grant type is: Client Credentials
AND Client is: ProGear Approval Executor
AND Scopes: inventory:write
```

This rule is used only after a VP approves a Manager's 601+ request. The
backend authenticates the dedicated executor with `private_key_jwt`, validates
the five-minute token at the Inventory boundary, and executes idempotently.
The OIG request presents the requester, action, threshold reason, required
approver role, and governed agent in a concise human summary. The backend's
file-backed approval ledger retains the exact scope, quantity, agent identity,
and FGA check needed for one idempotent execution after approval. In a hosted
deployment, that ledger is durable only when `APPROVALS_LEDGER_PATH` points to
persistent storage. Legacy open requests with embedded intent JSON remain
supported.

These rules are unchanged when FGA is switched on. Okta remains the coarse
gate: Sales cannot obtain `inventory:write`, while Managers and VPs can. FGA
then distinguishes routine Manager writes from 601+ writes that need a VP.

On the Inventory Authorization Server, add these access-token claims:

| Claim | Value |
|---|---|
| `Clearance` | `user.clearance_level` |
| `Manager` | `user.is_a_manager` |
| `Vacation` | `user.is_on_vacation` |

The backend enforces Vacation before requesting ID-JAG from any resource. The token claims preserve the same live context as evidence for exchanges that are allowed to continue.

#### 5.3 MCP Bridge Inventory Write Authorization Server

The MCP Bridge protects its write tool with a separate, write-only boundary so
customers can immediately distinguish it from the hosted application's
Inventory server:

```
Name: MCP Bridge - ProGear Inventory Write MCP
Audience: api://progear-inv-write
Description: Write-only ProGear Inventory authorization server for MCP Bridge
```

Define only `inventory:write`, assign the Bridge agent clients to its policy,
and create these user rules:

1. **VP Inventory Write**: `ProGear-VPs`, `inventory:write`
2. **Manager Inventory Write**: `ProGear-Managers`, `inventory:write`

Do not create a Sales rule. Sarah can discover and use the read resource, but
the Bridge cannot obtain or expose the protected write capability for her.

#### 5.4 Customer MCP Authorization Server

```
Name: ProGear Customer MCP
Audience: api://progear-customer
Description: Authorization for Sales Customer API
```

**Scopes:**
- `customer:read` - View customer info
- `customer:lookup` - Search customers
- `customer:history` - View purchase history

**Access Policy:**
   ```
   Name: Customer Agent Policy
   Description: Controls access to Customer MCP
   Assign to: ProGear Sales Agent
   ```

**Policy Rule:**
```
Rule Name: Customer Group Access
IF Grant type is: Authorization Code, Token Exchange, JWT Bearer
AND User is member of: ProGear-Sales
AND Scopes: customer:read, customer:lookup, customer:history
```

#### 5.5 Pricing MCP Authorization Server

```
Name: ProGear Pricing MCP
Audience: api://progear-pricing
Description: Authorization for Sales Pricing API
```

**Scopes:**
- `pricing:read` - View prices
- `pricing:margin` - View profit margins
- `pricing:discount` - View/apply discounts

**Access Policy:**
   ```
   Name: Pricing Agent Policy
   Description: Controls access to Pricing MCP
   Assign to: ProGear Sales Agent
   ```

**Policy Rules (add TWO rules):**

**Rule 1: Finance Full Access** (Priority 1)
```
IF Grant type is: Authorization Code, Token Exchange, JWT Bearer
AND User is member of: ProGear-Finance
AND Scopes: pricing:read, pricing:margin, pricing:discount
```

**Rule 2: Sales Read Access** (Priority 2)
```
IF Grant type is: Authorization Code, Token Exchange, JWT Bearer
AND User is member of: ProGear-Sales
AND Scopes: pricing:read
```

### Step 5: Verify Policy Assigned Clients (CRITICAL!)

> **This step is the #1 cause of "no_matching_policy" errors.** Don't skip it!

For each Authorization Server, you must add the AI Agent to the policy's "Assigned clients":

1. Go to **Security** → **API** → **[Your Auth Server]** → **Access Policies** → **[Your Policy]**
2. Click **Edit** on the policy
3. In **Assigned clients**, add the following **Clients** (`ProGear Sales Agent`)

Repeat for all 4 authorization servers.

### Step 6: Update Agent managed connections
Once you have create authorization servers per MCP API, Use managed connections to add connections to all auth servers with scopes listed for data access while maintaining centralized control through Okta.
**Manage Connection:**
   - Select the ***Registered Agent** and navigate to ***Managed Connections** tab
   - Click **Add Connection**
     
     | Name | Details  |  Allowed Scopes |
     |------|----------|-----------------|
     | `ProGear Customer MCP` | Only allow | customer:history customer:lookup customer:read |
     | `ProGear Pricing MCP` | Only allow | pricing:discount pricing:margin pricing:read |
     | `ProGear Inventory MCP` | Only allow | inventory:write inventory:read |
     | `ProGear Sales MCP` | Only allow | sales:order sales:read sales:quote |

### Step 7: Configure FGA and OIG approval

1. Create an FGA store and publish [`backend/auth/fga_role_model.json`](../backend/auth/fga_role_model.json).
2. Record the store ID and the returned authorization model ID. Configure a client allowed to call that store.
3. Configure every backend serving the app with the same `FGA_STORE_ID` and `FGA_MODEL_ID`.
4. In Okta Identity Governance, create or select the Inventory access-request type and required justification field.
5. Assign the **Okta Access Requests** app to `ProGear-Managers` and `ProGear-VPs`. This provisions current and future group members into the approval experience.
6. In the Okta Access Requests app's **Push Groups** configuration, push `ProGear-VPs`, then confirm the mapping is active under **Access Requests Console → Settings → Pushed Groups**.
7. Edit the Inventory request type and set its approval task assignee to the pushed `ProGear-VPs` group. Publish the request type. Writing `ProGear-VPs` in the justification does not route a task; the request-type step owns routing.
8. Route only Manager changes above 600 units to that request type. Sales changes never create access requests. The backend sends the authenticated Manager's Okta subject in `requesterUserIds`. The OIG card shows a concise summary of the requester, action, threshold reason, required VP level, and governed agent; the machine-readable intent stays in the backend approval ledger. The backend verifies the approver's live Okta profile before execution, and legacy open requests with embedded intent remain supported.
9. On the Inventory Authorization Server, allow only the dedicated `ProGear Approval Executor` service client's `client_credentials` grant for `inventory:write`, with a five-minute access-token lifetime. The backend mints and validates this token before creating an OIG request and again before executing an approval.

The VP opens **Okta Access Requests → Inbox → Open** from the End-User Dashboard. A request that appears as `Task ... was not assigned` in the System Log indicates that step 7 is incomplete, even if the requester and VP group memberships are correct.

The model provides four application permissions:

```text
can_read            = Sales or Manager or VP
can_request_change  = Manager
can_update_standard = Manager or VP       # 1–600
can_update_large    = VP                   # 601+
```

The role is a contextual tuple derived from the validated Inventory token for each request. Do not seed or maintain a second persistent role copy in FGA. Vacation stays outside the FGA model because it decides whether user-to-agent delegation may start at all. See [Inventory role levels and approval routing](./inventory-role-levels.md) for the exact business matrix and demo prompts.

### Step 8: Record All Your IDs

**Before proceeding, verify you have collected all these values.** You'll need them for Vercel and Render configuration.

Use this checklist to track what you've collected:

```
┌───────────────────────────────────────────────────────────────────────┐
│                       OKTA VALUES CHECKLIST                           │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  □ OKTA_DOMAIN                                                        │
│    Your Okta org URL                                                  │
│    Example: https://dev-12345.okta.com                                │
│    Where: Browser URL bar when logged into Okta Admin                 │
│    Your value: ___________________________________________            │
│                                                                       │
│  □ OKTA_CLIENT_ID                                                     │
│    Employee sign-in OIDC client ID                                    │
│    Example: 0oaXXXXXXXXXXXXXX                                         │
│    Where: Applications → Applications → ProGear User Access           │
│    Your value: ___________________________________________            │
│                                                                       │
│  □ OKTA_OIDC_PRIVATE_KEY                                              │
│    Server-only private JWK for private_key_jwt                        │
│    Where: Generate locally; upload only the public JWK to Okta        │
│    Your value: ___________________________________________            │
│                                                                       │
│  □ OKTA_AI_AGENT_ID                                                   │
│    AI Agent Entity ID                                                 │
│    Example: wlpXXXXXXXXXXXXXX                                         │
│    Where: Directory → AI Agents → ProGear Sales Agent                 │
│    Your value: ___________________________________________            │
│                                                                       │
│  □ OKTA_AI_AGENT_PRIVATE_KEY                                          │
│    JWK Private Key (SINGLE LINE - no line breaks!)                    │
│    Where: Downloaded when you created credentials in Step 3           │
│    Status: □ Downloaded  □ Converted to single line                   │
│                                                                       │
│  □ OKTA_SALES_AUTH_SERVER_ID                                          │
│    Example: ausXXXXXXXXXXXXXX                                         │
│    Where: Security → API → ProGear Sales MCP → Issuer URI             │
│    Your value: ___________________________________________            │
│                                                                       │
│  □ OKTA_INVENTORY_AUTH_SERVER_ID                                      │
│    Where: Security → API → ProGear Inventory MCP → Issuer URI         │
│    Your value: ___________________________________________            │
│                                                                       │
│  □ OKTA_CUSTOMER_AUTH_SERVER_ID                                       │
│    Where: Security → API → ProGear Customer MCP → Issuer URI          │
│    Your value: ___________________________________________            │
│                                                                       │
│  □ OKTA_PRICING_AUTH_SERVER_ID                                        │
│    Where: Security → API → ProGear Pricing MCP → Issuer URI           │
│    Your value: ___________________________________________            │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

> **Tip:** Copy this checklist to a text file and fill it in as you go. You'll reference these values multiple times during deployment.

---

## Recovering from an Accidentally Deleted AI Agent

Sometimes an AI Agent registration gets deleted by accident, for example during a cleanup pass in the Admin Console. This section covers what breaks, what survives, and how to recover without deleting useful evidence or rebuilding independent authorization systems.

### What breaks

- The AI Agent identity itself, the `wlp...` workload principal, is gone.
- Its credentials, owners, lifecycle state, and resource connections no longer provide a usable agent configuration.
- Any authorization-server policy or deployment value that references the deleted agent must be updated to the replacement.

A previously associated OIDC app may still exist as a separate application. Treat its presence, status, assignments, redirect URIs, and client-authentication settings as facts to verify. Do not assume that the app is reusable, and do not assume that it must be deleted.

### What does not break

The replacement does not require rebuilding these independent resources:

- The four Custom Authorization Servers (Sales, Inventory, Customer, Pricing), their scopes, and their access policy rules.
- Your demo users and groups.
- Your FGA store, model, and relationship tuples for the Inventory domain.
- Your Okta Identity Governance approval workflow for large inventory writes.
- Your Vercel and Render projects. Their Okta identity values need to change, but the deployments themselves remain.

FGA and OIG key off users, groups, claims, relationships, and workflow configuration rather than the deleted agent's internal Okta entity ID.

### Choose a sign-on app strategy

The available client-to-agent binding contract depends on the Okta release enabled in the target org. A newer API schema can advertise `NEW_OIDC_APP` and `EXISTING_APP` while a tenant in the temporary compatibility period rejects the native `signOnProvider` field. That happened during this recovery.

For a clean recovery, prefer a fresh OIDC application. A fresh app avoids inheriting stale status, assignments, redirect URIs, or a client-authentication method that the application no longer uses. Reuse a surviving app only after a read-only review confirms that the currently enabled API explicitly supports it and that the app matches the intended web sign-on design.

The production-compatible fallback used by this repository is:

1. Register the AI Agent without `signOnProvider`.
2. Create a fresh OIDC web app through the Apps API.
3. Create an ID-token delegation link from that app to the agent.

When Okta restores the newer native binding model, migrate this boundary from the then-current `main` branch rather than restoring an older repository snapshot. See [Okta AI Agent Client Binding Compatibility](agent-client-binding-compatibility.md) for the decision record and verification checklist.

### Recovery steps

1. Inventory the surviving AI Agent, OIDC app, authorization servers, policies, user or group assignments, resource connections, and deployment configuration. Do not delete or deactivate anything during discovery.
2. Register one replacement **ProGear Sales Agent** in `STAGED`. Use the native fresh-app binding supported by the target org when available. During the temporary compatibility period, register without `signOnProvider`, create a fresh OIDC web app separately, and connect it with an ID-token delegation link.
3. Assign owners to the new agent. Okta supports up to five individual owner principals, or an eligible owner group according to your governance policy.
4. Generate the agent workload key pair with your approved internal key-management process. Add only its public JWK to the agent and keep the private JWK in server-side secret storage.
5. Configure the sign-on app's callback URL, logout URL, user or group assignments, grant types, and `private_key_jwt` client authentication. If the app uses `private_key_jwt`, use a separate web-runtime key pair and register only that public JWK on the app.
6. On each existing Custom Authorization Server access policy, replace or supplement references to the deleted agent with the replacement client. Preserve scopes and rule logic unless verification finds an unrelated defect.
7. Add one `IDENTITY_ASSERTION_CUSTOM_AS` resource connection for each existing authorization server. Use `INCLUDE_ONLY` and the exact scopes for that domain, then activate each connection.
8. Activate the replacement agent only after owners and agent credentials are present.
9. Rewire the backend first, validate health and token exchange, then rewire the frontend and validate sign-in.

### API versus Admin Console boundaries during recovery

The current APIs can perform most of the replacement lifecycle:

- Register the agent with `POST /workload-principals/api/v1/ai-agents` and poll the asynchronous operation returned by the `202` response.
- Configure owners with `POST /governance/api/v1/resource-owners` using user or group principal ORNs and the AI Agent resource ORN.
- Add the agent's public JWK with `POST /workload-principals/api/v1/ai-agents/{agentId}/credentials/jwks`.
- Create, inspect, update, activate, and deactivate resource connections under `/workload-principals/api/v1/ai-agents/{agentId}/connections`.
- Activate the agent with `POST /workload-principals/api/v1/ai-agents/{agentId}/lifecycle/activate`.
- Use the standard Apps and Authorization Server APIs for app settings, assignments, policies, and rules where your administrative token or service app has the required scopes.

The API accepts a public key that you generated, but production key generation should remain in your approved internal key-management process. Use the Admin Console when your organization requires interactive review, when your API principal lacks a required scope, or when a product-specific setting is not exposed in the API version enabled for your org.

### Secret-free validation before cutover

Before updating live Vercel or Render secrets:

- Confirm the new agent has the intended owners, an active public JWK, four active resource connections, and the expected sign-on app.
- Confirm each authorization-server policy references the replacement client and still enables the JWT Bearer grant for the intended users, groups, and scopes.
- Confirm the sign-on app's assignments, callback URLs, logout URLs, and `private_key_jwt` public key.
- Test sign-in and both token exchanges against a preview or staging deployment first.
- Prove all inventory paths before changing production traffic: read at Levels 0/1/2; Sales writes denied without requests; Manager direct write through 600; Manager write of 601+ to VP approval; and VP direct write.

### Cleanup is a separate change

After the replacement works end to end, prepare a separate cleanup list for stale applications, deleted-client policy references, old keys, and retired deployment artifacts. Do not delete those resources as part of the recovery itself. Review each target immediately before deletion and obtain explicit approval for that cleanup pass.

---

## Clone and Deploy to Vercel (Frontend)

### Step 1: Fork the Repository

1. Go to this repository on GitHub
2. Click **Fork** to create your own copy
3. This allows Vercel to deploy from your GitHub account

### Step 2: Import to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click **Add New** → **Project**
3. Click **Import** next to your forked repository
4. Configure the project:

   | Setting | Value |
   |---------|-------|
   | **Framework Preset** | Next.js |
   | **Root Directory** | `packages/progear-sales-agent` |
   | **Build Command** | `npm run build` |
   | **Output Directory** | `.next` |

5. Click **Deploy** (it will fail initially - that's OK, we need to add environment variables)

### Step 3: Configure Environment Variables

1. In Vercel, go to your project → **Settings** → **Environment Variables**

2. **Generate a NEXTAUTH_SECRET first:**

   This is a random string used to encrypt session tokens. Generate it using one of these methods:

   **Mac/Linux:**
   ```bash
   openssl rand -base64 32
   ```

   **Windows (PowerShell):**
   ```powershell
   [Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Max 256) }))
   ```

   **Online Generator:**
   Visit [generate-secret.vercel.app](https://generate-secret.vercel.app/) and copy the generated secret

   Copy the output - it will look like `K7gNU3sdo+OL0wNhqoVWhr3g6s1xYv72ol/pe/Unols=`

3. **Add these environment variables:**

   | Variable | Value | Notes |
   |----------|-------|-------|
   | `NEXTAUTH_URL` | `https://your-project-name.vercel.app` | Use your actual Vercel URL from dashboard |
   | `NEXTAUTH_SECRET` | (the value you generated above) | Required for session encryption |
   | `NEXT_PUBLIC_API_URL` | Leave empty for now | We'll add this after Render deployment |
   | `NEXT_PUBLIC_OKTA_CLIENT_ID` | Employee sign-in OIDC client ID | `0oa...` in the compatibility deployment |
   | `NEXT_PUBLIC_OKTA_DOMAIN` | `https://your-org.okta.com` | Your Okta org URL |
   | `NEXT_PUBLIC_OKTA_ISSUER` | `https://your-org.okta.com` | Your Okta org URL (NO auth server ID - use Org AS) |
   | `OKTA_CLIENT_ID` | Employee sign-in OIDC client ID | Same as NEXT_PUBLIC version; distinct from `OKTA_AI_AGENT_ID` |
   | `OKTA_OIDC_PRIVATE_KEY` | Your server-only private JWK | Generate locally; register only its public JWK in Okta |

5. Click **Save** for each variable, then go to **Deployments** and click **Redeploy** on the latest deployment

### Step 4: Update Okta Redirect URIs

Now that you have your real Vercel URL, go back to Okta and replace the placeholder URLs:

1. Go to Okta Admin Console → **Applications** → **ProGear Sales Agent direct User access app**
2. Click the **General** tab → **Edit**
3. **Replace the placeholder redirect URIs with your actual Vercel URL:**

   **Sign-in redirect URIs:**
   - Remove: `https://placeholder.vercel.app/api/auth/callback/okta`
   - Add: `https://your-actual-project.vercel.app/api/auth/callback/okta`

   **Sign-out redirect URIs:**
   - Remove: `https://placeholder.vercel.app`
   - Add: `https://your-actual-project.vercel.app/auth/signin`

4. Click **Save**

> **Example:** If your Vercel project URL is `https://progear-demo-abc123.vercel.app`, your redirect URI would be `https://progear-demo-abc123.vercel.app/api/auth/callback/okta`

### Step 5: Verify Frontend

1. Visit your Vercel URL
2. You should see the ProGear Sales AI interface
3. The chat won't work yet (backend not deployed)
4. You should be able to click "Sign in with Okta" and authenticate

---

## Deploy to Render (Backend)

### Step 1: Create a Render Account

1. Go to [render.com](https://render.com) and sign up
2. Connect your GitHub account when prompted

### Step 2: Create a New Web Service

1. Click **New** → **Web Service**
2. Connect your forked repository
3. Configure the service:

   | Setting | Value |
   |---------|-------|
   | **Name** | `progear-backend` (or your preferred name) |
   | **Language** | Python 3 |
   | **Branch** | `main` |
   | **Region** | Oregon (US West) or closest to you |
   | **Root Directory** | `backend` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |

5. Choose your plan:
   - **Free**: Works but has cold starts (service sleeps after 15 min inactivity)
   - **Paid**: Recommended for demos; always on and supports a persistent disk
6. If you will demo OIG approvals, attach a persistent disk at `/var/data`.
   This keeps pending approval intent and idempotency state across deploys and
   restarts. Render persistent disks require a paid service.

### Step 3: Configure Environment Variables

In Render, go to **Environment** and add these variables:

| Variable | Value |
|----------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `LLM_MODEL_NAME` | `claude-sonnet-4-6` (optional override) |
| `OKTA_DOMAIN` | `https://your-org.okta.com` |
| `OKTA_CLIENT_ID` | Employee sign-in OIDC client ID (`0oa...` in this deployment) |
| `OKTA_AI_AGENT_ID` | Your AI Agent ID (`wlp...`) |
| `OKTA_AI_AGENT_PRIVATE_KEY` | Your JWK private key (entire JSON on one line) |
| `OKTA_APPROVAL_EXECUTOR_CLIENT_ID` | Dedicated approval executor service-app client ID (`0oa...`) |
| `OKTA_APPROVAL_EXECUTOR_PRIVATE_KEY` | Executor private JWK (entire JSON on one line; never reuse the agent key) |
| `OKTA_MAIN_AUTH_SERVER_ID` | (Optional) Used for Step 1. Defaults to `"default"` (Okta's alias for the Org Authorization Server) if unset -- leave it out unless you specifically need Step 1 to hit a non-default server |
| `OKTA_SALES_AUTH_SERVER_ID` | Your Sales auth server ID |
| `OKTA_SALES_AUDIENCE` | `api://progear-sales` |
| `OKTA_INVENTORY_AUTH_SERVER_ID` | Your Inventory auth server ID |
| `OKTA_INVENTORY_AUDIENCE` | `api://progear-inventory` |
| `OKTA_CUSTOMER_AUTH_SERVER_ID` | Your Customer auth server ID |
| `OKTA_CUSTOMER_AUDIENCE` | `api://progear-customer` |
| `OKTA_PRICING_AUTH_SERVER_ID` | Your Pricing auth server ID |
| `OKTA_PRICING_AUDIENCE` | `api://progear-pricing` |
| `OKTA_API_TOKEN` | Admin API token used for live role/vacation lookup and approver-role verification |
| `FGA_API_URL` | Your FGA API URL |
| `FGA_STORE_ID` | Your FGA store ID |
| `FGA_MODEL_ID` | The published role-model ID |
| `FGA_CLIENT_ID` | FGA client ID |
| `FGA_CLIENT_SECRET` | FGA client secret |
| `OKTA_OIG_BASE_URL` | Your Okta org URL |
| `OKTA_OIG_API_TOKEN` | API token used for OIG access requests |
| `OKTA_OIG_INVENTORY_REQUEST_TYPE_ID` | Inventory request type ID |
| `OKTA_OIG_JUSTIFICATION_FIELD_ID` | Required justification field ID |
| `APPROVAL_QUANTITY_THRESHOLD` | `601` |
| `APPROVALS_LEDGER_PATH` | `/var/data/approvals_ledger.json` (requires the persistent disk above) |
| `APPROVAL_POLL_INTERVAL_SECONDS` | `120` |
| `OKTA_VP_APPROVER_GROUP_NAME` | `ProGear-VPs` |
| `APPROVAL_STATUS_CACHE_TTL_SECONDS` | `8` (collapses duplicate browser polls) |
| `CORS_ORIGINS` | Your Vercel URL: `https://your-project-name.vercel.app` |

### Step 4: Deploy

1. Click **Create Web Service**
2. Render will build and deploy your backend
3. Wait for deployment to complete (usually 2-5 minutes)
4. Note your Render URL: `https://your-service-name.onrender.com`

### Step 5: Verify Backend

Test that your backend is running:

```bash
curl https://your-service-name.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "progear-ai-api",
  "version": "0.2.0",
  "agents": ["sales", "inventory", "customer", "pricing"]
}
```

---

## Connect Frontend to Backend

### Step 1: Update Vercel Environment Variable

1. Go to Vercel → Your Project → **Settings** → **Environment Variables**
2. Add/update:
   ```
   NEXT_PUBLIC_API_URL=https://your-service-name.onrender.com
   ```

### Step 2: Redeploy Frontend

1. In Vercel, go to **Deployments**
2. Click the **...** menu on the latest deployment
3. Click **Redeploy**

### Step 3: Test the Complete System

1. Visit your Vercel URL
2. Click **Sign in with Okta**
3. Log in as one of your demo users
4. Try a test query: "What basketballs do we have in stock?"
5. Verify:
   - You get a response from the AI
   - Token exchanges are shown on the **Token Flow** page
   - Scopes are granted based on user's group membership

---

## Environment Variables Reference

### Complete List

| Variable | Platform | Required | Description |
|----------|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Render | Yes | Anthropic Claude API key |
| `LLM_MODEL_NAME` | Render | No | Anthropic model; defaults to `claude-sonnet-4-6` |
| `OKTA_DOMAIN` | Both | Yes | Your Okta org URL |
| `OKTA_CLIENT_ID` | Both | Yes | Employee sign-in OIDC client ID; distinct from the Workload Principal in this deployment |
| `OKTA_OIDC_PRIVATE_KEY` | Vercel | Yes | Server-only private JWK for private_key_jwt |
| `OKTA_AI_AGENT_ID` | Render | Yes | AI Agent entity ID (`wlp...`) |
| `OKTA_AI_AGENT_PRIVATE_KEY` | Render | Yes | JWK private key (JSON string) |
| `OKTA_APPROVAL_EXECUTOR_CLIENT_ID` | Render | Yes | Dedicated post-approval service client (`0oa...`) |
| `OKTA_APPROVAL_EXECUTOR_PRIVATE_KEY` | Render | Yes | Private JWK for the post-approval service client |
| `OKTA_MAIN_AUTH_SERVER_ID` | Render | No | Defaults to `"default"` (Org AS) for Step 1 -- only set if you need a non-default server |
| `OKTA_SALES_AUTH_SERVER_ID` | Render | Yes | Sales domain's Custom Authorization Server ID |
| `OKTA_SALES_AUDIENCE` | Render | Yes | `api://progear-sales` |
| `OKTA_INVENTORY_AUTH_SERVER_ID` | Render | Yes | Inventory domain's Custom Authorization Server ID |
| `OKTA_INVENTORY_AUDIENCE` | Render | Yes | `api://progear-inventory` |
| `OKTA_CUSTOMER_AUTH_SERVER_ID` | Render | Yes | Customer domain's Custom Authorization Server ID |
| `OKTA_CUSTOMER_AUDIENCE` | Render | Yes | `api://progear-customer` |
| `OKTA_PRICING_AUTH_SERVER_ID` | Render | Yes | Pricing domain's Custom Authorization Server ID |
| `OKTA_PRICING_AUDIENCE` | Render | Yes | `api://progear-pricing` |
| `OKTA_API_TOKEN` | Render | Yes | Scoped demo profile updates, live role/vacation lookup, and OIG approver-role verification |
| `FGA_API_URL` | Render | Yes | FGA API base URL |
| `FGA_STORE_ID` | Render | Yes | FGA store ID |
| `FGA_MODEL_ID` | Render | Yes | Published three-tier role model ID |
| `FGA_CLIENT_ID` | Render | Yes | FGA client ID |
| `FGA_CLIENT_SECRET` | Render | Yes | FGA client secret |
| `OKTA_OIG_BASE_URL` | Render | Yes | Okta org URL used by the OIG client |
| `OKTA_OIG_API_TOKEN` | Render | Yes | OIG API token |
| `OKTA_OIG_INVENTORY_REQUEST_TYPE_ID` | Render | Yes | Inventory request type ID |
| `OKTA_OIG_JUSTIFICATION_FIELD_ID` | Render | Yes | OIG justification field ID |
| `APPROVAL_QUANTITY_THRESHOLD` | Render | Yes | `601` (kept aligned with the fixed 600/601 policy boundary) |
| `APPROVALS_LEDGER_PATH` | Render | Yes for hosted OIG demo | Path on durable storage; use `/var/data/approvals_ledger.json` with a Render persistent disk |
| `APPROVAL_POLL_INTERVAL_SECONDS` | Render | No | OIG background polling interval; defaults to 120 seconds |
| `APPROVAL_STATUS_CACHE_TTL_SECONDS` | Render | No | Per-request status cache; defaults to 8 seconds |
| `OKTA_VP_APPROVER_GROUP_NAME` | Render | Yes | `ProGear-VPs` |
| `NEXTAUTH_URL` | Vercel | Yes | Your Vercel URL |
| `NEXTAUTH_SECRET` | Vercel | Yes | Generate: `openssl rand -base64 32` |
| `NEXT_PUBLIC_API_URL` | Vercel | Yes | Your Render URL |
| `NEXT_PUBLIC_OKTA_CLIENT_ID` | Vercel | Yes | Employee sign-in OIDC client ID (for frontend) |
| `NEXT_PUBLIC_OKTA_DOMAIN` | Vercel | Yes | Your Okta org URL |
| `NEXT_PUBLIC_OKTA_ISSUER` | Vercel | Yes | `https://your-org.okta.com` (NO auth server ID - use Org AS) |
| `CORS_ORIGINS` | Render | Yes | Your Vercel URL |

> **Three distinct runtime keys.** `OKTA_OIDC_PRIVATE_KEY`, `OKTA_AI_AGENT_PRIVATE_KEY`, and `OKTA_APPROVAL_EXECUTOR_PRIVATE_KEY` are unrelated key pairs. The first authenticates the Vercel sign-in client, the second authenticates the AI Agent's ID-JAG and JWT-bearer exchanges, and the third authenticates only the post-VP-approval service client. Rotating one never requires touching the others.

---

## Demo Scenarios

Four key scenarios demonstrate resource RBAC and the three-tier Inventory story:

### Scenario 1: Access across all resource domains (Sarah Sales)

**Login as**: Your sarah.sales user

**Question**: "Can we fulfill an order of 1500 basketballs for State University at a bulk discount?"

**What Happens**:
1. The single ProGear Sales Agent routes across its Customer, Inventory, Pricing, and Sales domain components
2. **Customer component** → Looks up State University (Platinum tier)
3. **Inventory component** → Checks basketball stock (available)
4. **Pricing component** → Calculates bulk discount
5. **Sales component** → Generates quote

**Expected Result**:
- Successful scoped token exchanges for the required resource domains
- Full combined answer with customer, inventory, pricing, and quote
- All required scopes granted on the **Token Flow** page

### Scenario 2: Limited resource access (Mike Manager)

**Login as**: Your mike.manager user

**Question**: Same as above

**What Happens**:
1. The ProGear Sales Agent identifies the Customer, Inventory, Pricing, and Sales resource needs
2. **Customer domain** → ACCESS DENIED (Mike is not in `ProGear-Sales`)
3. **Inventory domain** → SUCCESS: "Stock available"
4. **Pricing domain** → ACCESS DENIED (Mike is not in `ProGear-Finance`)
5. **Sales domain** → ACCESS DENIED

**Expected Result**:
- One resource decision granted and three denied
- Partial answer with the information the agent is allowed to retrieve
- Demonstrates governance working without introducing additional user-facing agents

### Scenario 3: Inventory authorization and approval tiers

The chat page starts with two everyday examples: Sarah's inventory read and Mike's 50-unit inventory write. Open `/fga` and select **Simulate FGA** to reveal the advanced controls and replace those examples with the three-tier FGA prompt set. Then use the prompts in this order:

1. `How many basketballs are in stock?`
2. `Add 50 basketballs to inventory`
3. `Add 601 basketballs to inventory`

Sarah's read succeeds, while both writes are denied without creating access requests. Mike's 50-unit write executes directly, while 601 creates a VP request. Change the signed-in user to Level 2 and 601 executes directly.

### Scenario 4: One resource domain (Frank Finance)

**Login as**: Your frank.finance user

**Question**: "What's our profit margin on professional basketballs?"

**What Happens**:
1. The agent routes to its Pricing domain component only
2. **Pricing component** → SUCCESS: Shows cost, wholesale, retail, and margin percentage

**Expected Result**:
- Single token exchange for the Pricing resource domain
- Complete pricing/margin information
- No unnecessary access to other systems

---

## Demo Script

Use these talking points when presenting:

### Opening
> "Let me show you how Okta AI Agent Governance secures AI access to enterprise data. ProGear has one governed Sales Agent that works across four protected resource domains: Sales, Inventory, Customer, and Pricing."

### Demo 1: Access across all domains (Sarah)
> "Sarah is a sales rep. Watch what happens when she asks the ProGear Sales Agent about fulfilling an order..."
> [Show the four internal domain steps, scoped resource token exchanges, and the combined answer]
> "Notice that the same agent obtained only the scopes needed for Sarah's request in each resource domain. The audit trail shows who accessed what."

### Demo 2: Limited resource access (Mike)
> "Now let's see what happens when Mike, a warehouse manager, asks the same agent the same question..."
> [Show three resource decisions denied and Inventory allowed]
> "Same agent, same question, different user permissions. Mike can see inventory, but not customer or pricing data."

### Demo 3: FGA and human approval
> "Sarah can read inventory, but every write is blocked and she contacts her manager. Mike can execute through 600 units; at 601, FGA creates a VP request. The same `clearance_level` in Okta drives every outcome."
> [Show Mike's fixed live role on `/fga`, the D3 decision diagram, and the pending OIG request]

### Demo 4: Vacation containment
> "Now set On vacation to True. The employee remains signed in, but the agent stops before ID-JAG for every resource. This is user-context containment if the employee is away or their credentials may have been exposed."
> [Show the chat denial and token page: ID token present, no ID-JAG or resource token]

### Demo 5: Governance evidence
> "Notice that the token exchanges and FGA decisions identify the user, agent, requested scope, role level, quantity, and outcome. OIG records the required human decision before a pending write executes."

### Closing
> "With Okta AI Agent Governance, you know which governed agent is accessing each resource, for which user, and with which permissions. Full visibility, full control."

---

## Troubleshooting

### "Token exchange failed" error

**Cause**: Misconfigured authorization server or missing policy rule

**Solution**:
1. Verify the user is in the correct group
2. Check the authorization server policy rules include the requested scopes
3. Ensure Token Exchange grant type is enabled on the OIDC app
4. Verify direct User access is enabled on the AI Agent

### "Invalid client assertion" error

**Cause**: Private key mismatch or malformed JWK

**Solution**:
1. Re-download the private key from Okta AI Agent settings
2. Ensure the entire JWK is on a single line in environment variables (no line breaks!)
3. Verify the `kid` in the JWK matches the public key in Okta

### "Access denied" for all requests

**Cause**: User not in any group with access policies

**Solution**:
1. Add the test user to the appropriate group in Okta
2. Verify the policy rules reference the correct group names
3. Check that policy rules are Active (not Inactive)

### CORS errors

**Cause**: `CORS_ORIGINS` doesn't include frontend URL

**Solution**:
1. Update `CORS_ORIGINS` in Render to include your exact Vercel URL
2. For multiple origins: `CORS_ORIGINS=https://app1.vercel.app,https://app2.vercel.app`
3. Redeploy the backend after changing

### "Unauthorized" on backend health check

**Cause**: Backend not receiving valid tokens

**Solution**:
1. Check that `NEXT_PUBLIC_API_URL` points to the correct Render URL
2. Verify the backend is running (check Render dashboard)
3. Check browser console for network errors

### `invalid_subject_token` error

**Cause**: The user ID token wasn't issued to the configured employee sign-in OIDC client, or the backend is validating it against the Workload Principal ID instead of the OIDC client ID.

**Solution**:
1. Verify the OIDC web app is linked to the AI Agent using the binding mechanism supported by your tenant.
2. Verify `NEXT_PUBLIC_OKTA_CLIENT_ID` and backend `OKTA_CLIENT_ID` use the OIDC web-client ID, while `OKTA_AI_AGENT_ID` uses the separate `wlp...` Workload Principal ID.
3. Sign out and sign in again to obtain a new ID token for the direct User access client.

### `user_not_assigned` error

**Cause**: User not assigned to the direct User access app

**Solution**:
1. Go to your OIDC App → Assignments tab
2. Add the user or a group containing the user
3. Users must be assigned to the app to authenticate

### `no_matching_policy` error

**Cause**: AI Agent not added to authorization server policy's "Assigned clients"

**Solution**:
1. Go to each Authorization Server → Access Policies → Your Policy
2. Edit the policy
3. Add the AI Agent entity (`wlp...`) to "Assigned clients"
4. **This is the #1 cause of token exchange failures!**

### Backend cold start (Free Render tier)

**Cause**: Render free tier spins down inactive services

**Solution**:
1. Wait 15-30 seconds for the service to wake up
2. Upgrade to a paid instance type for an always-on service
3. First request after sleep will be slow, subsequent requests fast

### Issuer mismatch / ID-JAG exchange failed

**Cause**: Users logged in via a Custom Authorization Server, but the Okta AI SDK always performs Step 1 (ID Token → ID-JAG) at the Org Authorization Server.

**Solution**:
1. `NEXT_PUBLIC_OKTA_ISSUER` must be your Org AS URL WITHOUT an auth server ID: `https://your-org.okta.com`
2. Do NOT include `/oauth2/{auth_server_id}` in the issuer - that causes users to log in via a Custom AS
3. The ID token's issuer must match where the SDK performs the exchange (Org AS)
4. Step 2 (ID-JAG → Access Token) correctly goes to each Custom AS - that's configured separately

### AI Agent registration disappeared / was deleted

**Cause**: The AI Agent registration was deleted from the Admin Console, intentionally or by accident. A previously associated OIDC app may still exist, but the workload principal, credentials, owners, and resource connections must be replaced.

**Solution**: See [Recovering from an Accidentally Deleted AI Agent](#recovering-from-an-accidentally-deleted-ai-agent). Your four Custom Authorization Servers, groups, FGA store, and OIG workflow are unaffected. Prefer a fresh `NEW_OIDC_APP` for a clean rebuild, or use `EXISTING_APP` only after confirming the surviving app is eligible and correctly configured.

---

## Verification Checklist

Use this checklist to verify your deployment is complete:

### Okta Configuration
- [ ] A supported direct User access app or delegation-link sign-on app is configured and Token Exchange is enabled
- [ ] 4 demo users created and can log in
- [ ] 4 resource-access groups created with correct user assignments
- [ ] `clearance_level` configured as 0 Sales, 1 Manager, or 2 VP
- [ ] `is_a_manager` configured and synchronized: False for Level 0, True for Levels 1–2
- [ ] `is_on_vacation` configured as a Boolean and False for the default personas
- [ ] `ProGear-Managers` rule includes Levels 1 and 2
- [ ] `ProGear-VPs` rule includes Level 2
- [ ] Inventory rules grant Sales only `inventory:read`, and grant Managers/VPs `inventory:read inventory:write`
- [ ] Okta Access Requests app assigned to `ProGear-Managers` and `ProGear-VPs`
- [ ] `ProGear-VPs` group push mapping is active in Access Requests
- [ ] Inventory request type approval task is assigned to `ProGear-VPs` and published
- [ ] AI Agent registered with JWK credentials
- [ ] AI Agent configured with the target org's supported user sign-on binding
- [ ] 4 authorization servers with scopes configured
- [ ] Inventory token carries `Clearance`, `Manager`, and `Vacation` claims
- [ ] **Access policies include the ProGear Sales Agent client**
- [ ] All demo users assigned to the direct User access app
- [ ] **`NEXT_PUBLIC_OKTA_ISSUER` set to Org AS URL (no auth server ID)**

### Vercel Deployment
- [ ] Project imported from GitHub
- [ ] Root directory set to `packages/progear-sales-agent`
- [ ] All environment variables configured
- [ ] Okta redirect URIs updated with Vercel URL
- [ ] Frontend loads without errors

### Render Deployment
- [ ] Web service created from `backend` directory
- [ ] All environment variables configured
- [ ] `CORS_ORIGINS` includes Vercel URL
- [ ] `/health` endpoint returns 200
- [ ] FGA store/model and OIG request variables are configured
- [ ] Persistent disk mounted at `/var/data` and `APPROVALS_LEDGER_PATH` points to it for the OIG approval demo

### Integration
- [ ] `NEXT_PUBLIC_API_URL` in Vercel points to Render
- [ ] Okta login works from frontend
- [ ] Chat messages get responses
- [ ] Token exchanges visible on the **Token Flow** page
- [ ] A Mike 601+ request lists Mike as requester and appears in Joe's **Access Requests → Inbox → Open**

### Demo Verification
- [ ] The same ProGear Sales Agent is shown for Sarah, Mike, Joe, and Frank
- [ ] Sarah can obtain Inventory read but cannot obtain Inventory write
- [ ] Mike's request can obtain Inventory scopes only
- [ ] Frank's request can obtain Pricing scopes only
- [ ] Sarah read succeeds; every write is denied without creating a request
- [ ] With FGA off, Mike writes any positive quantity; with FGA on, he writes through 600 directly and 601+ requests VP
- [ ] VP writes any quantity directly
- [ ] Okta System Log shows the single agent identity, user, resource, scope, and outcome for token exchange events

---

## Quick Reference: What to Change When Cloning

If you're cloning this repository to deploy your own instance, here's everything you need:

### 1. Okta Configuration (Create New in Your Org)
- [ ] AI Agent User access → get Client ID and configure a private JWK
- [ ] AI Agent → get Agent ID & download Private Key
- [ ] 4 Authorization Servers → get Auth Server IDs
- [ ] 4 User Groups → configure access policies

### 2. Vercel Environment Variables
- [ ] `NEXTAUTH_URL` - Your Vercel URL
- [ ] `NEXTAUTH_SECRET` - Generate new
- [ ] `NEXT_PUBLIC_API_URL` - Your Render URL
- [ ] `NEXT_PUBLIC_OKTA_*` - Your Okta values
- [ ] `OKTA_CLIENT_*` - Your Okta credentials

### 3. Render Environment Variables
- [ ] `ANTHROPIC_API_KEY` - Your key
- [ ] All `OKTA_*` variables - Your Okta values
- [ ] `CORS_ORIGINS` - Your Vercel URL

### 4. Okta Redirect URIs
- [ ] Add your Vercel callback and logout URLs to the direct User access app

### That's It!
The code is designed to work with any Okta org - just update the configuration values.

---

**Questions?** Check the [README](../README.md)
