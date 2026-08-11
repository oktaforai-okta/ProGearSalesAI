# Why Okta AI Agent Governance Matters

> A practical guide to understanding the security value for CISOs, security teams, and compliance officers

---

## Table of Contents

1. [The Challenge in Plain Terms](#the-challenge-in-plain-terms)
2. [The Four Scenarios: How AI Agents Access Your Data](#the-four-scenarios-how-ai-agents-access-your-data)
3. [Scenario 1: Standard Token Exchange (No Governance)](#scenario-1-standard-token-exchange-no-governance)
4. [Scenario 2: ID-JAG with Okta Authorization Servers (This Demo)](#scenario-2-id-jag-with-okta-authorization-servers-this-demo)
5. [Scenario 3: ID-JAG/XAA with Customer-Controlled External Auth Server](#scenario-3-id-jagxaa-with-customer-controlled-external-auth-server)
6. [Scenario 4: ID-JAG/XAA with ISV Authorization Servers](#scenario-4-id-jagxaa-with-isv-authorization-servers)
7. [Industry Validation: MCP Adopts Cross App Access](#industry-validation-mcp-adopts-cross-app-access)
8. [The Workload Principal: Your AI Agent's Identity](#the-workload-principal-your-ai-agents-identity)
9. [Proof: What You See in Audit Logs](#proof-what-you-see-in-audit-logs)
10. [The Governance Model](#the-governance-model)
11. [Layer Two: Fine-Grained Authorization](#layer-two-fine-grained-authorization)
12. [Layer Three: Human Approval for High-Risk Actions](#layer-three-human-approval-for-high-risk-actions-okta-identity-governance)
13. [Real Demo Scenarios with Evidence](#real-demo-scenarios-with-evidence)
14. [Security and Governance FAQ](#security-and-governance-faq)

---

## The Challenge in Plain Terms

Your organization is building AI agents. These agents need to access company data - customer records, inventory systems, pricing engines, sales pipelines.

**The security question is simple:** When an AI agent accesses your data, can you answer these questions?

1. **WHO** requested this access? (Which user?)
2. **WHAT** AI system performed the action? (Which agent?)
3. **WHEN** did it happen? (Timestamp?)
4. **WHY** was access granted or denied? (Which policy?)
5. **CAN** we shut it down immediately if needed? (Kill switch?)

Your ability to answer these questions depends on *how* your AI agents authenticate and access resources. There are four distinct scenarios, each with different governance capabilities.

---

## The Four Scenarios: How AI Agents Access Your Data

Before diving into technical details, understand that there are four ways an AI agent can access your data. The governance capabilities differ dramatically between them.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   THE FOUR AI AGENT ACCESS SCENARIOS                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SCENARIO 1: Standard Token Exchange                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  App ──▶ Okta ──▶ API                                                  │ │
│  │  • No workload principal                                               │ │
│  │  • No user attribution in tokens                                       │ │
│  │  • Audit shows "app got token" - nothing more                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  SCENARIO 2: ID-JAG with Okta Auth Servers (THIS DEMO)                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  AI Agent (wlp) ──▶ Okta ID-JAG ──▶ Okta Auth Server                   │ │
│  │  • Workload principal with full visibility                             │ │
│  │  • User + agent identity in every token                                │ │
│  │  • Complete audit trail: who, what, when, why                          │ │
│  │  • Works TODAY - no external dependencies                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  SCENARIO 3: ID-JAG/XAA with Customer External Auth Server                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  AI Agent (wlp) ──▶ Okta ID-JAG ──▶ Customer's Auth Server             │ │
│  │  • Same workload principal visibility                                  │ │
│  │  • Customer builds resource server to validate ID-JAG                  │ │
│  │  • Full governance - customer controls both sides                      │ │
│  │  • Works TODAY - requires customer engineering effort                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  SCENARIO 4: ID-JAG/XAA with ISV Auth Servers                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  AI Agent (wlp) ──▶ Okta ID-JAG ──▶ Salesforce/ServiceNow/etc.         │ │
│  │  • Same workload principal visibility                                  │ │
│  │  • ISV builds resource server to validate ID-JAG                       │ │
│  │  • Same governance model extends to external SaaS                      │ │
│  │  • Growing ecosystem - MCP has adopted this pattern                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Quick Comparison

| Scenario | Workload Principal | User Attribution | Who Implements Resource Server | Status |
|----------|-------------------|------------------|-------------------------------|--------|
| 1. Standard Token Exchange | No | No | N/A | Works, no governance |
| 2. ID-JAG + Okta Auth Servers | **Yes** | **Yes** | Okta (config only) | **Works today** |
| 3. ID-JAG/XAA + Customer Auth Server | **Yes** | **Yes** | Customer builds it | Works today (effort required) |
| 4. ID-JAG/XAA + ISV Auth Server | **Yes** | **Yes** | ISV builds it | Ecosystem growing |

**Key Insight:** Scenarios 2, 3, and 4 are technically identical - they all use Cross App Access (XAA) with the ID-JAG grant type. The only difference is who implements the resource server side.

---

## Scenario 1: Standard Token Exchange (No Governance)

### What It Is

Traditional OAuth 2.0 token exchange (RFC 8693) between applications. This is what most organizations use today for app-to-app communication.

### How It Works

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│   Your App     │ ───▶ │     OKTA       │ ───▶ │   Your API     │
│   (0oa...)     │      │ Token Exchange │      │                │
└────────────────┘      └────────────────┘      └────────────────┘
```

### The Token

```json
{
  "sub": "0oaEXAMPLEAPPCLIENT",
  "scp": ["inventory:read"],
  "aud": "api://progear-inventory"
}
```

**Problem:** Who is `0oaEXAMPLEAPPCLIENT`? Is this a user? A service? An AI agent? Who authorized this access?

### The Audit Log

```json
{
  "eventType": "app.oauth2.as.token.grant",
  "actor": {
    "id": "0oaEXAMPLEAPPCLIENT",
    "type": "PublicClientApp",
    "displayName": "AI-Sales-Service"
  },
  "target": [
    {
      "type": "AuthorizationServer",
      "displayName": "Inventory API"
    }
  ]
}
```

**What You Know:** An app called "AI-Sales-Service" got a token.
**What You Don't Know:** Which user triggered this? Was it Sarah in Sales or Mike in Warehouse?

### The Governance Gap

| Capability | Available? |
|------------|-----------|
| Identify which AI agents exist | No - mixed with other apps |
| Know who owns each AI agent | No - optional field |
| See which user the agent acted for | No - not in token |
| Revoke AI agent access instantly | Partially - credential rotation required |
| Audit AI actions by user | No - requires custom implementation |

### When This Is Acceptable

- Internal services with no user context
- Batch jobs that don't act on behalf of users
- Legacy integrations where governance isn't required

### When This Is NOT Acceptable

- AI agents that access user data on behalf of users
- Systems that require compliance auditing
- Environments where you need to answer "who did this?"

---

## Scenario 2: ID-JAG with Okta Authorization Servers (This Demo)

### What It Is

Cross App Access (XAA) using the Identity Assertion JWT Authorization Grant (ID-JAG) with Okta-managed authorization servers. This is what this demo implements.

### How It Works

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│   AI Agent     │ ───▶ │     OKTA       │ ───▶ │ Okta Auth      │
│   (wlp...)     │      │    ID-JAG      │      │ Server         │
└────────────────┘      └────────────────┘      └────────────────┘
        │                       │                       │
        │ Workload Principal    │ act claim             │ Scoped token
        │ in Universal Dir      │ with user+agent       │ for your API
        ▼                       ▼                       ▼
```

### Why Two Steps, Not One Hop?

Look closely at the arrows above: there are two separate exchanges, not one.

1. **Step 1 - ID token → ID-JAG, at Okta's Org Authorization Server.** The agent proves, once, "I am really the ProGear Sales Agent, and I am acting on behalf of Sarah Sales, who just authenticated." Okta issues an ID-JAG assertion binding those two identities together.
2. **Step 2 - ID-JAG → scoped access token, at a per-domain Custom Authorization Server.** The agent presents that assertion to *one specific domain's* Custom Authorization Server (Sales, Inventory, Customer, or Pricing), and that server - and only that server - decides what the (agent, user) pair is allowed to do *there*.

Collapsing this into a single hop would force one of two bad outcomes. Either the Org AS would need to own every domain's authorization policy up front (which defeats the purpose of having separate domains at all), or a single token minted once would need to carry every domain's scopes simultaneously - reintroducing the "master key" problem from Scenario 1, just with better attribution attached to it.

The two-step design keeps those concerns cleanly separated: **identity proof** (step 1, who is this agent, who is it acting for) never has to know anything about Sales vs. Inventory vs. Pricing policy, and **the domain-specific authorization decision** (step 2) never has to re-verify who the agent and user are - it just decides what that already-verified pair may do here. The result is that the same agent, acting for the same user, ends up holding four different, independently-scoped, independently-revocable credentials - one per domain - instead of a single credential that spans all of them. Deactivating or narrowing access to one domain's Custom Authorization Server has zero effect on the other three.

### The Token

```json
{
  "sub": "sarah.sales@atko.email",
  "act": {
    "sub": "wlpuoor63yK6LYFEh1d7"
  },
  "scp": ["inventory:read"],
  "aud": "api://progear-inventory"
}
```

**Clear Answer:** Sarah Sales (`sub`) is the user. The AI agent `wlpuoor63yK6LYFEh1d7` (`act.sub`) is acting on her behalf.

### The Audit Log

```json
{
  "eventType": "app.oauth2.token.grant.id_jag",
  "actor": {
    "id": "wlpuoor63yK6LYFEh1d7",
    "type": "AI Agent",
    "displayName": "ProGear Sales Agent"
  },
  "target": [
    {
      "id": "00u8x5nsjp8aDUpB70g7",
      "type": "User",
      "displayName": "Sarah Sales",
      "alternateId": "sarah.sales@atko.email"
    },
    {
      "type": "AuthorizationServer",
      "displayName": "ProGear Inventory MCP"
    }
  ]
}
```

**What You Know:** Everything.
- **WHO:** Sarah Sales
- **WHAT:** ProGear Sales Agent accessed Inventory API
- **WHEN:** Timestamp in log
- **WHY:** Policy allowed it (or denied it with reason)

### The Governance Capability

| Capability | Available? |
|------------|-----------|
| Identify which AI agents exist | **Yes** - dedicated AI Agents section |
| Know who owns each AI agent | **Yes** - mandatory owner field |
| See which user the agent acted for | **Yes** - in token and logs |
| Stop new AI agent access | **Yes** - one-click deactivation blocks new token exchanges |
| Audit AI actions by user | **Yes** - query by user or agent |

### What This Demo Proves

This demo implements Scenario 2 with four internal authorization servers:
- ProGear Sales API (`api://progear-sales`)
- ProGear Inventory API (`api://progear-inventory`)
- ProGear Customer API (`api://progear-customer`)
- ProGear Pricing API (`api://progear-pricing`)

**This works today. No external dependencies. No waiting for anyone.**

### Why Four Separate Authorization Servers Instead of One Shared One?

This is the design decision that matters most for blast-radius reasoning, so it's worth spelling out the alternative that was rejected.

**The alternative:** one shared Custom Authorization Server, with all twelve scopes defined on it - `sales:read`, `sales:quote`, `sales:order`, `inventory:read`, `inventory:write`, `customer:read`, `customer:lookup`, `customer:history`, `pricing:read`, `pricing:margin`, `pricing:discount` - and a single policy engine deciding who gets which. It looks simpler to stand up. It is structurally weaker:

- **Same issuer, same audience, one trust boundary for everything.** Every token that server mints carries the same `aud` claim. A policy misconfiguration that grants `pricing:discount` to the warehouse group by mistake produces a token that is *structurally valid* for the Pricing API - the only thing standing between that mistake and a real exposure is application code correctly reading the `scp` claim, on every code path, every time, forever.
- **A compromised or over-broad token is replayable across domains.** If Inventory and Pricing shared an authorization server, a token minted for one carries that server's issuer and audience - identical to a token meant for the other. A resource server that's even slightly too permissive about which scopes it enforces (a common implementation bug, not a hypothetical one) will accept it, because nothing about the token itself says "this belongs to Inventory, not Pricing."

**What four separate Custom Authorization Servers actually buy you:** each domain has its own issuer/audience pair (`api://progear-sales`, `api://progear-inventory`, `api://progear-customer`, `api://progear-pricing`). A token minted for Inventory does not pass `aud` validation against the Pricing API - not because a scope check caught it, but because the token's own shape is wrong for that audience. The isolation is enforced by the token itself, not by application-layer logic that has to get it right every single time. If Pricing's Custom Authorization Server is ever misconfigured, the blast radius is Pricing. It structurally cannot leak into Sales, Inventory, or Customer, because those live behind entirely different issuers.

This is also why the "no down-scoping" behavior you saw in the denied audit log above matters. When the ProGear Sales Agent requests `customer:read customer:lookup` on behalf of Mike Manager (in `ProGear-Warehouse`, not `ProGear-Sales`), the exchange doesn't quietly grant a smaller, safer subset of those scopes and drop the rest - the *entire* token exchange fails (`no_matching_policy`). Okta refuses to partially satisfy a request rather than silently narrowing it. That all-or-nothing behavior is only meaningful *because* each domain's Custom Authorization Server is a genuinely separate trust boundary to begin with. Fail-closed on a shared server still leaves you trusting that scope-checking logic downstream gets every call right, on every domain, forever; fail-closed on four separate servers means the failure is contained to one domain by construction.

### Admin Console Visibility

```
┌─────────────────────────────────────────────────────────────────────┐
│  Directory → AI Agents                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ProGear Sales Agent                                                │
│  ID: wlpuoor63yK6LYFEh1d7                                           │
│  Owner: john.admin@company.com                                      │
│  Status: ● Active                                                   │
│  Managed Connections: 4 APIs                                        │
│                                                                     │
│  Every AI agent visible. Every owner identified. One click to stop. │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Scenario 3: ID-JAG/XAA with Customer-Controlled External Auth Server

### What It Is

Cross App Access (XAA) using ID-JAG where the resource server is an authorization server you own and control, but is external to Okta.

### When This Applies

- You have a custom authorization server (not Okta-managed)
- Your internal applications use this auth server for API access
- You want the same governance and visibility as Scenario 2
- You can modify your auth server to validate Okta's ID-JAG tokens

### How It Works

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│   AI Agent     │ ───▶ │     OKTA       │ ───▶ │ Your Custom    │
│   (wlp...)     │      │    ID-JAG      │      │ Auth Server    │
└────────────────┘      └────────────────┘      └────────────────┘
        │                       │                       │
        │ Workload Principal    │ ID-JAG token          │ Validates JWT
        │ still in Okta         │ with act claim        │ trusts Okta
        ▼                       ▼                       ▼
```

### What You Get From Okta

- **Workload Principal (`wlp`)** - the AI agent identity
- **ID-JAG token** - contains `sub` (user) and `act.sub` (agent)
- **Okta audit logs** - `app.oauth2.token.grant.id_jag` events

### What You Build

Your external authorization server must:

1. **Accept ID-JAG tokens** via RFC 8693 token exchange
2. **Validate against Okta's JWKS** (`https://your-org.okta.com/oauth2/v1/keys`)
3. **Read the `sub` and `act.sub` claims** for user and agent identity
4. **Issue your own access tokens** for your protected resources

### Pseudocode for Your Auth Server

```python
def token_exchange(subject_token):
    # 1. Validate the ID-JAG from Okta
    claims = validate_jwt(
        token=subject_token,
        jwks_url="https://your-org.okta.com/oauth2/v1/keys"
    )

    # 2. Extract identities
    user_id = claims["sub"]           # "sarah.sales@company.com"
    agent_id = claims["act"]["sub"]   # "wlpuoor63yK6LYFEh1d7"

    # 3. Make policy decision
    scopes = determine_scopes(user_id, agent_id)

    # 4. Issue your own token
    return issue_token(
        sub=user_id,
        act={"sub": agent_id},  # Preserve the delegation chain
        scopes=scopes
    )
```

### The Value

| Capability | Available? |
|------------|-----------|
| Workload principal visibility | **Yes** - in Okta |
| User attribution in tokens | **Yes** - you read the `act` claim |
| Audit in Okta | **Yes** - ID-JAG issuance logged |
| Audit in your system | **Yes** - you log with both identities |
| New-token cutoff | **Yes** - deactivate the agent in Okta; existing short-lived tokens follow resource policy |

### Status

**Works today** - requires engineering effort to implement the resource server side, but you control both ends.

---

## Scenario 4: ID-JAG/XAA with ISV Authorization Servers

### What It Is

Cross App Access (XAA) using ID-JAG where the resource server is a third-party SaaS application (Salesforce, ServiceNow, Box, etc.) that you don't control.

### How It Works

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│   AI Agent     │ ───▶ │     OKTA       │ ───▶ │  Salesforce /  │
│   (wlp...)     │      │    ID-JAG      │      │  ServiceNow /  │
└────────────────┘      └────────────────┘      │  Box, etc.     │
        │                       │               └────────────────┘
        │                       │                       │
        │ Workload Principal    │ ID-JAG token          │ ISV validates
        │ still in Okta         │ with act claim        │ and issues token
        ▼                       ▼                       ▼
```

### The Difference from Scenario 3

| Aspect | Scenario 3 (Customer Auth Server) | Scenario 4 (ISV Auth Server) |
|--------|-----------------------------------|------------------------------|
| Who builds resource server | You | The ISV |
| When it's available | Now (you build it) | When ISV adopts XAA |
| Your control | Complete | Limited to Okta config |

### What the ISV Must Implement

The same thing you would build in Scenario 3:
1. Accept ID-JAG tokens via token exchange
2. Validate against Okta's JWKS
3. Read `sub` and `act.sub` claims
4. Issue scoped access tokens

### The Value When ISVs Adopt

- **Same governance model** extends to external SaaS
- **No reconfiguration needed** - just add managed connections in Okta
- **User identity preserved** across all AI interactions, internal and external
- **Centralized audit** - Okta logs every ID-JAG issuance

### Status

**Ecosystem growing.** The pattern is standardized (IETF ID-JAG specification). ISV adoption is accelerating.

---

## Industry Validation: MCP Adopts Cross App Access

### The Significance

In May 2025, the **Model Context Protocol (MCP)** - Anthropic's open standard for connecting AI agents to external tools - officially adopted Cross App Access as the enterprise authentication pattern.

### What MCP Is

MCP is how AI agents like Claude connect to external resources (databases, APIs, SaaS tools). When an employee uses Claude to access company data, MCP handles the connection.

### The Problem MCP Solves with XAA

**Before XAA (current state):**
- Employee connects Claude to Salesforce
- Claude prompts user for OAuth consent
- User approves, Claude gets a token
- **Enterprise admin has no visibility or control**
- Each employee manages their own connections
- No centralized governance, no audit trail

**With XAA:**
- Employee logs into Claude via SSO (Okta)
- Claude requests ID-JAG from Okta
- Okta checks: Is this user allowed to use Claude to access Salesforce?
- If yes, issues ID-JAG with user + agent identity
- Salesforce validates the ID-JAG, issues scoped token
- **Enterprise admin controls everything through Okta**

### Why This Matters

1. **Validation of the pattern** - MCP choosing XAA confirms this is the right approach for enterprise AI
2. **Ecosystem acceleration** - MCP servers will implement XAA, driving ISV adoption
3. **Centralized control** - IT admins manage AI agent access through existing identity infrastructure
4. **Standards-based** - IETF specification, not proprietary

### The Quote

> "Enterprise admin has no visibility or control over individual OAuth connections. Cross-App Access shifts control to IT administrators who can enforce policies centrally."
>
> - Aaron Parecki, on MCP enterprise authentication

### What This Means for You

If you implement AI Agent Governance today (Scenarios 2 or 3), you're building on the same pattern that MCP has adopted. When MCP servers implement XAA, your governance model extends automatically.

---

## The Workload Principal: Your AI Agent's Identity

### What is a Workload Principal?

A **Workload Principal** (ID starts with `wlp`) is Okta's identity type for AI agents and automated workloads. It's not a service account. It's not an API key. It's a first-class identity designed for AI systems.

### Why Not Just Give the App an API Key?

The simpler alternative is Scenario 1: give the AI application a single API key or client credential, and let it call your APIs directly. It fails for one structural reason: **a shared app credential has no way to carry per-user identity.**

Every call the AI makes with that key looks identical in your logs - "AI-Sales-Service called the Inventory API" - whether the AI is:

- Acting for Sarah Sales, looking up her own accounts,
- Acting for Mike Manager, checking warehouse stock,
- Or someone who stole the key and is making calls that look exactly like every other call the app has ever made.

There is no way to tell these apart after the fact, because the credential authenticates the *app*, not the *request*. Concretely, that means:

- **The blast radius of a stolen credential is every user the AI has ever acted for**, not one user. Rotating the key doesn't surgically cut off an attacker - it cuts off the AI entirely, including its next thousand legitimate requests, because there's no way to revoke "just the bad usage" of a credential that never distinguished usage in the first place.
- **You cannot answer "who did this?"** for any single action - the exact question an incident responder or auditor asks first.
- **You cannot apply different policy to different users** through the credential itself. Any per-user restriction has to be reimplemented in application code, invisible to Okta and absent from your audit trail - which means it's also invisible to whoever is supposed to be reviewing access.

A Workload Principal fixes this by giving the AI its own identity that travels *alongside*, but never replaces, the user's identity. The ID-JAG preserves the user in `sub` and the acting client in `client_id`; this demo's final resource token also uses `act.sub` for the agent actor. That separation is the foundation for the audit trail, per-user policy enforcement, and a centralized cutoff for new agent access.

### Key Properties

| Property | What It Means | Why It Matters |
|----------|---------------|----------------|
| **Unique ID** | `wlpuoor63yK6LYFEh1d7` | Every agent has a trackable identity |
| **Mandatory Owner** | A real person is responsible | Governance and accountability |
| **Cryptographic Credentials** | RS256 key pair (no passwords) | Secure, rotatable authentication |
| **Direct User access** | Which assigned users can sign in to the agent-bound OIDC app | Controlled entry points |
| **Managed Connections** | Which APIs this agent can access | Explicit scope boundaries |
| **Enable/Disable Toggle** | One click to activate or deactivate | Stops new authentication and delegated token exchanges |

### Where It Lives

```
┌───────────────────────────────────────────────────────────────────┐
│                     OKTA UNIVERSAL DIRECTORY                      │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│   USERS (People)                GROUPS                            │
│   ┌────────────────┐            ┌─────────────────────┐           │
│   │ sarah.sales    │            │ ProGear-Sales       │           │
│   │ mike.manager   │            │ ProGear-Warehouse   │           │
│   │ frank.finance  │            │ ProGear-Finance     │           │
│   └────────────────┘            └─────────────────────┘           │
│                                                                   │
│   AI AGENTS (Workload Principals)       ← First-class identity    │
│   ┌─────────────────────────────────────────────────────┐         │
│   │ ProGear Sales Agent (wlpuoor63yK6LYFEh1d7)          │         │
│   │   • Owner: admin@company.com                        │         │
│   │   • Credentials: RS256 key pair                     │         │
│   │   • Direct User access: ProGear Sales Agent         │         │
│   │   • Status: ACTIVE                                  │         │
│   └─────────────────────────────────────────────────────┘         │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Why This Matters for Security

**Before (Service Account - Scenario 1):**
- Service account created, credentials shared
- No clear owner after employee leaves
- Scattered across different systems
- Hard to audit, hard to revoke

**With Workload Principal (Scenarios 2-4):**
- Centralized in Universal Directory
- Owner is required and visible
- All access policies in one place
- Disable with one click, audit with one query

---

## Proof: What You See in Audit Logs

### Sample Log: Successful Token Exchange

When Sarah Sales asks the AI agent to check inventory:

```json
{
  "eventType": "app.oauth2.token.grant.id_jag",
  "displayMessage": "OAuth 2.0 Identity Assertion Authorization Grant is granted",
  "outcome": {
    "result": "SUCCESS"
  },
  "published": "2024-12-15T14:23:47.123Z",
  "actor": {
    "id": "wlpuoor63yK6LYFEh1d7",
    "type": "AI Agent",
    "displayName": "ProGear Sales Agent"
  },
  "target": [
    {
      "id": "00u8x5nsjp8aDUpB70g7",
      "type": "User",
      "displayName": "Sarah Sales",
      "alternateId": "sarah.sales@atko.email"
    },
    {
      "id": "ausuoodihgxiDhdJH1d7",
      "type": "AuthorizationServer",
      "displayName": "ProGear Inventory MCP"
    }
  ],
  "debugContext": {
    "grantedScopes": "inventory:read",
    "requestedScopes": "inventory:read"
  }
}
```

### What This Log Tells You

| Field | Value | Security Insight |
|-------|-------|------------------|
| `actor.displayName` | "ProGear Sales Agent" | **WHICH AI** performed this action |
| `actor.id` | `wlpuoor63yK6LYFEh1d7` | Unique, trackable agent ID |
| `target[0].displayName` | "Sarah Sales" | **WHICH USER** the agent acted for |
| `target[1].displayName` | "ProGear Inventory MCP" | **WHICH API** was accessed |
| `grantedScopes` | "inventory:read" | **WHAT PERMISSIONS** were granted |
| `outcome.result` | "SUCCESS" | Access was allowed |
| `published` | Timestamp | **WHEN** this happened |

### Sample Log: Access Denied

When Mike Manager (warehouse team) tries to access customer data:

```json
{
  "eventType": "app.oauth2.token.grant.id_jag",
  "displayMessage": "OAuth 2.0 Identity Assertion Authorization Grant failed",
  "outcome": {
    "result": "FAILURE",
    "reason": "no_matching_policy"
  },
  "published": "2024-12-15T14:25:12.456Z",
  "actor": {
    "id": "wlpuoor63yK6LYFEh1d7",
    "type": "AI Agent",
    "displayName": "ProGear Sales Agent"
  },
  "target": [
    {
      "id": "00u8x5abc123def456",
      "type": "User",
      "displayName": "Mike Manager",
      "alternateId": "mike.manager@atko.email"
    },
    {
      "id": "ausuop8bitEQYw3mc1d7",
      "type": "AuthorizationServer",
      "displayName": "ProGear Customer MCP"
    }
  ],
  "debugContext": {
    "requestedScopes": "customer:read customer:lookup",
    "denialReason": "User not in required group: ProGear-Sales"
  }
}
```

**This is the audit trail your compliance team needs.**

---

## The Governance Model

### Five Pillars of AI Agent Governance

```
┌─────────────────────────────────────────────────────────────────┐
│                  AI AGENT GOVERNANCE MODEL                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. IDENTITY          Every agent has a Workload Principal      │
│     ────────────────  (wlp...) in Universal Directory           │
│                                                                 │
│  2. OWNERSHIP         Every agent MUST have an owner            │
│     ────────────────  (required field, not optional)            │
│                                                                 │
│  3. DELEGATION        Agent acts ON BEHALF OF users             │
│     ────────────────  (user identity preserved in tokens)       │
│                                                                 │
│  4. POLICY            Access controlled by group membership     │
│     ────────────────  (same policies that govern human access)  │
│                                                                 │
│  5. AUDITABILITY      Exchanges show user + agent               │
│     ────────────────  (target, scopes, policy, outcome)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Stop New Delegated Access

If an AI agent is compromised or behaving unexpectedly:

1. Go to **Directory** → **AI Agents**
2. Find the agent
3. Click **Deactivate**

**Result:** New token exchanges fail without credential rotation or a deployment change. A token issued before deactivation remains subject to its short expiry and the resource server's revocation policy.

---

## Layer Two: Fine-Grained Authorization

Everything above - Workload Principals, ID-JAG, four Custom Authorization Servers - answers one question well: **may this governed agent obtain a token for this resource and scope while acting for this user?** For Inventory, both read and write scopes let the request reach the resource. A write scope is not permission to bypass the next decision.

That question is necessary, but it is not sufficient for every access decision. Before requesting ID-JAG, ProGear also evaluates the employee's live delegation context: `is_on_vacation=true` stops every agent action, while `is_a_manager` remains synchronized with the authoritative role for clear profile and audit context. Known Sales writes then stop at the live Okta clearance guard. For eligible requests, this demo adds a second layer—**FGA** (Fine-Grained Authorization)—after token exchange to answer: **given this live Okta role and this quantity, may the request execute, stop, or require VP approval?**

### Why not just make Okta's policy more granular?

The user's authoritative inventory role is `clearance_level`, with three intentional meanings: **0 = Sales, 1 = Manager, 2 = VP**. It is a role level, not an item-sensitivity score. `is_a_manager` is synchronized from that level for profile clarity and audit context; it is not a second authorization switch. `is_on_vacation` is separate and stops delegated agent work before ID-JAG when true.

Okta remains the source of truth for that role. The Inventory access token carries `Clearance`, `Manager`, and `Vacation`; the backend has already enforced vacation before exchange. It validates the token and converts `Clearance` into one contextual FGA tuple for the current check, rather than persisting a second mutable role copy in FGA.

### What FGA actually checks (the real model behind this demo)

FGA runs on top of the Okta scope check, for the Inventory domain, only after Okta has already granted `inventory:read` or `inventory:write`:

| Okta establishes | FGA decides next |
|---|---|
| Signed-in user and governed agent identity | Read: all valid role levels may execute |
| Narrow `inventory:read` or `inventory:write` token | Write 1–600 units: Level 1+ executes; Level 0 is blocked |
| Validated `Clearance` role claim | Write 601+ units: Level 2 executes; Level 1 may request VP approval; Level 0 is blocked |

`inventory:read` maps to `can_read`. Quantity selects `can_update_standard` for 1–600 or `can_update_large` for 601+. `can_request_change` is intentionally Manager-only, so Sales can never manufacture an access request. Low-stock alerts remain reads.

**Concretely:** Sarah (Level 0) may read, but every write is blocked and no request is created. Mike (Level 1) may add 50 directly, but adding 601 creates a VP request. A Level 2 VP may perform either write directly.

### Why this is a second layer, not duplicated work

Okta and FGA are not answering the same question twice. Okta authenticates the employee, governs the agent, and supplies the live clearance used to stop known-ineligible writes before delegation. For requests that continue, Okta issues the resource token, the resource validates it, and FGA combines role with quantity for the per-action decision. OIG records the one human escalation when a Manager crosses 600 units.

---

## Layer Three: Human Approval for High-Risk Actions (Okta Identity Governance)

An action can have a valid token but still require a higher role before it executes. That is where Okta Identity Governance supplies the human-in-the-loop step.

In this demo, **Sales writes are denied without creating an access request**. **A Manager write of 601 or more requires VP approval**. The backend creates an **Okta Identity Governance (OIG)** request with a concise human summary, keeps the exact execution intent in its approval ledger, makes no inventory change while the request is pending, and verifies the approver's current Level 2 Okta role before executing an approved change.

### Why add a third gate when the first two already said yes?

Because "is this action within policy" and "is this action a good idea right now" are different questions, answered by different mechanisms:

- **Authorization (Okta + FGA) asks:** may this role execute this exact quantity now, or may it submit a request to the next role?
- **Governance (the approval gate) asks:** did a currently qualified VP approve the queued Manager change?

The 600/601 boundary makes the story deterministic. A Manager is trusted to execute normal inventory adjustments through 600 units. A VP must authorize a Manager's change at 601 or above. Sales cannot execute either class of write and cannot create an approval request.

Routing this through Okta Identity Governance, rather than a bespoke approval box bolted onto the app, matters for the same reason the rest of this document does: the request, the justification, and the approval decision all land in the same governance system that already owns your access-review and audit story, instead of creating a second, disconnected place your auditors have to go find.

---

## Real Demo Scenarios with Evidence

### Scenario: Full Access User (Sarah Sales)

**User Profile:**
- Name: Sarah Sales
- Group: `ProGear-Sales`
- Role: Sales Representative

**What She Can Access:**

| Agent/API | Access Level | Scopes Granted |
|-----------|--------------|----------------|
| Sales MCP | Full | `sales:read`, `sales:quote`, `sales:order` |
| Inventory MCP | Read Only | `inventory:read` |
| Customer MCP | Full | `customer:read`, `customer:lookup`, `customer:history` |
| Pricing MCP | Full | `pricing:read`, `pricing:margin`, `pricing:discount` |

**Audit Trail:** 4 successful token exchanges, all tied to Sarah Sales, each with specific scopes.

### Scenario: Limited Access User (Mike Manager)

**User Profile:**
- Name: Mike Manager
- Group: `ProGear-Warehouse`
- Role: Warehouse Manager

**What He Can Access:**

| Agent/API | Access Level | Scopes Granted |
|-----------|--------------|----------------|
| Sales MCP | **DENIED** | - |
| Inventory MCP | Full | `inventory:read`, `inventory:write` |
| Customer MCP | **DENIED** | - |
| Pricing MCP | **DENIED** | - |

**Audit Trail:** 1 success, 3 denials - all logged with Mike Manager as the user.

**Note on the `inventory:write` grant above:** token issuance is necessary, not sufficient. Inventory validates the token and FGA still applies Mike's Level 1 role plus the requested quantity. He can execute 1–600; 601+ creates a Level 2 VP request. See [Layer Two](#layer-two-fine-grained-authorization) and [Layer Three](#layer-three-human-approval-for-high-risk-actions-okta-identity-governance) above.

---

## Security and Governance FAQ

### "Which AI systems can access our data?"

**Answer:** Go to **Directory** → **AI Agents** in Okta Admin Console. You'll see every registered AI agent, its owner, its status, and what it can access.

### "Who is responsible for this AI agent?"

**Answer:** The **Owner** field is mandatory. Click on any AI agent to see who owns it.

### "What can this AI agent access?"

**Answer:** Click the agent → **Managed Connections** tab. You'll see exactly which authorization servers (APIs) this agent can request tokens from.

### "Who did this AI act for?"

**Answer:** The delegation chain keeps both identities visible. In the ID-JAG, `sub` identifies the end user and `client_id` identifies the client acting for that user at the Resource Authorization Server. In this demo's final resource token, `sub` remains the user and `act.sub` identifies the agent actor.

### "Can we shut it down NOW?"

**Answer:** Yes. The **Deactivate** button on the AI Agent page stops new authentication and delegated token exchanges at one control point. Previously issued short-lived resource tokens continue to follow resource policy.

### "How do we prove compliance to auditors?"

**Answer:** Export System Log with filter: `eventType eq "app.oauth2.token.grant.id_jag"`

---

## Summary: The Security Value

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   OKTA AI AGENT GOVERNANCE                                      │
│                                                                 │
│   ✓ Centralized visibility of all AI agents                     │
│   ✓ Mandatory ownership for accountability                      │
│   ✓ User identity preserved in every AI action                  │
│   ✓ Policy-based access control (same as humans)                │
│   ✓ Complete audit trail for compliance                         │
│   ✓ Stop new delegated access with one click                   │
│                                                                 │
│   ✓ Works today for internal APIs (Scenarios 2 & 3)             │
│   ✓ Same pattern extends to external SaaS (Scenario 4)          │
│   ✓ Validated by MCP adoption of Cross App Access               │
│                                                                 │
│   ✓ Layer 2: FGA for role-and-quantity decisions                │
│   ✓ Layer 3: Human approval for high-magnitude actions          │
│                                                                 │
│   Your AI agents should be as governed as your employees.       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

No single layer above is sufficient by itself. Identity establishes the user, agent, role, and resource boundary. FGA combines role and quantity for each action. OIG records the qualified VP decision when escalation is required. The value is the enforced chain, not any one control in isolation.

---

## Next Steps

1. **Run the Demo** - See Scenario 2 in action with real token exchanges
2. **Check the Logs** - Verify the audit trail in your Okta System Log
3. **Try Different Users** - Log in as Sarah, Mike, Joe, and Frank to see different access levels
4. **Plan for Scenarios 3 & 4** - Same infrastructure, expanding scope

---

*This document accompanies the ProGear Sales AI demo showcasing Okta AI Agent Governance with Cross App Access (XAA).*
