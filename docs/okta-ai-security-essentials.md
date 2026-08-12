# Why AI Agent Security Matters: A Plain English Guide

> For marketers, executives, and anyone who wants to understand AI agent governance without the technical jargon

---

## Table of Contents

1. [The Big Picture](#the-big-picture)
2. [Think of It Like a Building Security System](#think-of-it-like-a-building-security-system)
3. [The Five Questions You Can Answer](#the-five-questions-you-can-answer)
4. [How It Works: A Day in the Life](#how-it-works-a-day-in-the-life)
5. [The Four Ways AI Can Access Your Data](#the-four-ways-ai-can-access-your-data)
6. [What Makes Okta Different](#what-makes-okta-different)
7. [Real-World Scenarios with Examples](#real-world-scenarios-with-examples)
8. [A Closer Look: Two More Safety Checks for High-Stakes Actions](#a-closer-look-two-more-safety-checks-for-high-stakes-actions)
9. [Why This Matters for Your Business](#why-this-matters-for-your-business)
10. [The Industry is Moving This Way](#the-industry-is-moving-this-way)
11. [Common Questions](#common-questions)
12. [The Bottom Line](#the-bottom-line)

---

## The Big Picture

Your company is using AI agents to help employees work faster. These AI assistants can look up customer information, check inventory, find pricing, and more.

**The question every executive asks:** "When an AI does something with our data, do we know what happened?"

Without proper governance, the honest answer is: "Not really."

With Okta AI Agent Governance, the answer is: **"Yes, completely."**

### A Simple Example

Imagine your marketing manager asks an AI assistant: "Show me our top 10 customers by revenue."

**Without governance:**
- The AI accesses customer data
- Somewhere, a log says "data was accessed"
- You don't know who asked, which AI did it, or if this should have been allowed

**With Okta governance:**
- The AI checks with Okta: "Jennifer from Marketing wants customer revenue data"
- Okta verifies: "Is Jennifer allowed to see this? Is this AI agent approved?"
- Access is granted (or denied), and everything is logged with full details
- You know exactly: Jennifer asked, ProGear AI answered, customer data was accessed, at 2:34 PM

---

## Think of It Like a Building Security System

The best way to understand AI agent governance is through an analogy everyone understands: building security.

### Your Company Data = A Secure Office Building

Imagine your company data is stored in a secure office building with multiple floors:

- **Floor 1 - Sales Data**: Customer lists, deals in progress, revenue numbers
- **Floor 2 - Inventory Data**: What's in stock, what's running low, warehouse locations
- **Floor 3 - Customer Data**: Contact information, purchase history, account details
- **Floor 4 - Pricing Data**: Profit margins, discount structures, cost information

Different employees have access to different floors based on their job.

### Without AI Agent Governance: The Masked Visitor Problem

When an AI agent accesses your data without governance, it's like someone walking into your building wearing a mask:

**What the security camera sees:**
- Someone entered the building at 2:34 PM
- They went to Floor 3 (Customer Data)
- They left at 2:35 PM

**What you DON'T know:**
- Who was behind the mask?
- Who sent them?
- Were they supposed to be there?
- What exactly did they look at?
- How do you stop them from coming back?

**Real-world impact:** If a data breach happens, you can't answer basic questions. Auditors ask "Who accessed this customer data?" and you say "Some AI... somewhere... we think."

### With Okta AI Agent Governance: The ID Badge System

With Okta, every AI agent has a visible ID badge, and there's a security guard (Okta) checking every entry:

**What the security system records:**
- **Visitor:** ProGear Sales AI Agent (Badge #WLP-8X5Q7)
- **Sent by:** Sarah Sales, Sales Representative
- **Destination:** Floor 2 (Inventory Data)
- **Purpose:** Check basketball stock levels
- **Authorization:** Approved - Sarah has inventory access
- **Time in:** 2:34:17 PM
- **Time out:** 2:34:19 PM

**What you CAN do:**
- See every AI agent that exists (like a visitor log)
- Know exactly who sent each AI agent
- Verify they were supposed to be there
- Review exactly what they accessed
- Revoke their badge instantly if needed

**Real-world impact:** When auditors ask "Who accessed customer data?", you pull up the log and show them: "Sarah from Sales asked our AI assistant about customer order history at 2:34 PM on Tuesday. Here's the complete record."

### Why Two Checks Instead of One?

Notice the badge system above actually does two things, not one: first the front desk confirms *who you are and who you're visiting on behalf of*, and only then does the checkpoint for the specific floor you're heading to decide *what you're allowed to do once you're there*.

Why not combine those into a single check? Because they're answering two different questions, and mixing them together would make the whole building less safe, not more convenient:

- The front-desk check just needs to confirm identity: "Yes, this is really the ProGear AI Agent, and yes, it's here on behalf of Sarah, who really did just badge in." It doesn't need to know anything about what Floor 2 vs. Floor 4's rules are.
- Each floor's checkpoint only needs to know its own rules: "Given that this really is Sarah, is she allowed on this specific floor?" It doesn't need to re-verify who Sarah is - that was already handled downstairs.

If you collapsed this into one check, that single checkpoint would either need to know every floor's rules at once (turning it into a single point of failure for the whole building), or it would need to hand out one all-purpose pass that works on every floor (which is just the master-key problem again, dressed up with a name on it). Keeping the two checks separate means the identity check and the "what can you do here" check can never be confused with each other.

### Why Four Separate Checkpoints Instead of One for the Whole Building?

Go back to the four-floor building: Sales, Inventory, Customer, Pricing. It would be simpler to install one shared badge reader for the whole building instead of a separate one per floor. It would also be much less safe, for a very concrete reason.

**With one shared badge reader for every floor:** every floor trusts the same reader and the same set of rules. If that shared reader is ever misconfigured - say, a setup mistake accidentally lets warehouse badges open the Pricing floor - there's nothing else standing in the way. The mistake is immediately live everywhere, because every floor was relying on the same system to get it right.

**With a separate checkpoint on each floor:** a badge that opens the Inventory floor is *physically the wrong shape* for the Pricing floor's reader - it's not that the Pricing floor's rules happen to reject it, it's that the badge itself doesn't fit that door. If the Inventory floor's checkpoint is ever misconfigured, the mistake is contained to the Inventory floor. It cannot spread to Sales, Customer, or Pricing, because those floors were never relying on the same checkpoint in the first place.

This is also why, when the AI asks for several permissions at once and even one of them isn't allowed, the whole request gets turned away rather than quietly handing over a smaller, "safer" set of the ones that were fine. The system doesn't guess at a partial compromise - it says no cleanly, and that clean "no" is only meaningful because each floor's checkpoint is a genuinely separate gate to begin with, not four labels on the same gate.

**Business translation:** if your AI's credentials ever leaked, or a setup mistake ever happened on one system, the exposure is contained to that one system - inventory operations, say - and does not automatically extend to customer records, pricing, or sales data. That containment is the entire point of having four separate checkpoints instead of one shared one.

---

## The Five Questions You Can Answer

When your compliance team, security officer, or board asks about AI security, you need clear answers to five questions:

### Question 1: WHO requested this access?

**The scenario:** Your AI agent accessed sensitive customer financial data at 3 AM.

| Without Governance | With Okta |
|-------------------|-----------|
| "An application accessed it" | "Tom Wilson from Finance requested it" |
| "We'd need to check multiple systems" | "Here's his user profile and the exact request" |
| "It might take days to figure out" | "I can tell you in 10 seconds" |

**Example from the demo:**
- Sarah Sales asks: "What's our revenue this quarter?"
- The log shows: `User: sarah.sales@atko.email requested sales:read access`
- You know exactly who made the request

### Question 2: WHAT AI system performed the action?

**The scenario:** Customer data was exported. Which of your five AI tools did it?

| Without Governance | With Okta |
|-------------------|-----------|
| "One of our AI systems" | "ProGear Sales Agent (ID: wlpuoor63yK6)" |
| "We have several, not sure which" | "This specific agent, owned by John Admin" |
| "Different AI systems share credentials" | "Each registered AI system has its own trackable identity" |

**Example from the demo:**
- The AI agent has a unique ID: `wlpuoor63yK6LYFEh1d7`
- It has a name: "ProGear Sales Agent"
- It has an owner: The person responsible for it
- Every delegated exchange is tied to this specific identity

### Question 3: WHEN did it happen?

**The scenario:** You discover unusual data access patterns and need to investigate.

| Without Governance | With Okta |
|-------------------|-----------|
| "Sometime last week" | "Tuesday, December 15, 2024, at 14:23:47.123 UTC" |
| "Our logs aren't that detailed" | "Exact timestamps on each delegated token event" |
| "We'd need to correlate multiple systems" | "One unified log with all the details" |

**Example from the demo:**
- Every token exchange is logged with exact timestamps
- You can search by date range, user, or AI agent
- Timeline reconstruction is straightforward

### Question 4: WHY was access granted or denied?

**The scenario:** An AI agent accessed pricing data. Should it have been allowed?

| Without Governance | With Okta |
|-------------------|-----------|
| "It had the right credentials" | "Policy 'Sales Team Pricing Access' allowed it" |
| "Not sure what rules apply" | "User was in ProGear-Sales group, which grants pricing:read" |
| "We'd need to review code" | "Here's the exact policy that matched" |

**Example from the demo:**
- Mike Manager asks about pricing margins
- Okta checks: "Is Mike in a group that allows pricing access?"
- Answer: No - ProGear-Managers doesn't have pricing permissions
- Log shows: `Access DENIED - Reason: User not in required group`
- You know exactly why it was blocked

### Question 5: Can we STOP it right now?

**The scenario:** You suspect an AI agent has been compromised or is misbehaving.

| Without Governance | With Okta |
|-------------------|-----------|
| "We need to rotate credentials" | "Click 'Deactivate' - done" |
| "IT needs to update multiple systems" | "Any admin can do it in seconds" |
| "It might take hours or days" | "New authentication and token exchanges stop at the identity control point" |

**Example from the demo:**
- Go to Okta Admin Console → Directory → AI Agents
- Find the agent
- Click "Deactivate"
- The agent can no longer authenticate or obtain new delegated tokens; any previously issued short-lived token follows resource policy

---

## How It Works: A Day in the Life

Let's follow a real scenario step by step to see how AI agent governance works in practice.

### Morning: Sarah Starts Her Day

**8:30 AM - Sarah logs in**

Sarah Sales is a sales representative at ProGear Sports. She opens her browser and goes to the company portal.

1. She clicks "Sign in with Okta"
2. She enters her email and password (or uses her phone for passwordless login)
3. Okta verifies: "Yes, this is Sarah Sales. She's in the Sales team."
4. Sarah is now logged in

**What happened behind the scenes:**
- Okta issued Sarah a digital "pass" (called a token) that proves who she is
- This pass is temporary - it expires in a few hours
- The pass contains her identity and what groups she belongs to

### Mid-Morning: Sarah Asks the AI for Help

**10:15 AM - A customer question**

Sarah is on a call with a big customer who asks: "Do you have Pro Game Basketballs in stock? We need 500 units."

Sarah types into the AI assistant: "Check stock levels for Pro Game Basketballs"

**What happens next (in about 2 seconds):**

**Step 1: The AI receives Sarah's question**
- The AI sees: "Sarah wants to know about basketball inventory"
- The AI has Sarah's digital pass that proves she's logged in

**Step 2: The AI asks Okta for permission**
- AI Agent: "Hey Okta, Sarah wants me to check inventory. Can I do this for her?"
- The AI presents:
  - Sarah's digital pass (proof of who she is)
  - The AI's own ID badge (proof of which AI agent this is)
  - What it needs: "inventory:read" permission

**Step 3: Okta checks the rules**
- Okta looks up Sarah: "She's in the ProGear-Sales group"
- Okta checks the policy: "ProGear-Sales members can read inventory"
- Okta verifies the AI agent: "This is the approved ProGear Sales Agent"
- Decision: **APPROVED**

**Step 4: Okta issues a temporary access pass**
- Okta creates a special pass just for this request
- The pass says: "Sarah Sales (via ProGear AI Agent) can read inventory data"
- The pass expires in minutes, not hours or days
- Everything is logged

**Step 5: The AI gets the inventory data**
- Using the temporary pass, the AI checks the inventory system
- It finds: "Pro Game Basketball - 8,500 units in stock"
- It responds to Sarah: "We have 8,500 Pro Game Basketballs in stock. Plenty to fulfill a 500-unit order!"

**Step 6: Sarah helps her customer**
- Total time elapsed: about 2 seconds
- Sarah didn't notice any of the security checks
- The customer is happy
- Everything is fully documented

### Afternoon: Mike Hits a Boundary

**2:30 PM - A different kind of request**

Mike is the warehouse manager. He's great at his job but doesn't need access to customer financial data.

Mike types into the AI assistant: "Show me the profit margins on our basketball products"

**What happens:**

**Step 1-2:** Same as before - the AI gets Mike's request and asks Okta for permission

**Step 3: Okta checks the rules**
- Okta looks up Mike: "He's in the ProGear-Managers group"
- Okta checks the policy: "ProGear-Managers members can access inventory, but NOT pricing"
- Decision: **DENIED**

**Step 4: The AI responds appropriately**
- The AI doesn't crash or show an error
- Instead, it politely says: "I'm sorry, but you don't have access to pricing information. I can help you with inventory questions. Would you like me to check stock levels instead?"

**Step 5: Everything is logged**
- The attempted access is recorded
- The denial reason is documented
- If Mike repeatedly tries to access things he shouldn't, security can see the pattern

**Why this matters:**
- Mike wasn't embarrassed by an error message
- The system enforced appropriate boundaries
- There's a complete audit trail
- Mike can still do his actual job

### End of Day: The Audit Trail

**5:00 PM - What the logs show**

At the end of the day, an administrator could pull up the logs and see:

```
Today's AI Agent Activity Summary:

Sarah Sales (ProGear-Sales)
├── 10:15 AM - Inventory access GRANTED - "Check basketball stock"
├── 11:42 AM - Customer access GRANTED - "Look up Acme Corp order history"
├── 2:15 PM - Pricing access GRANTED - "What's our margin on Pro Game Basketball?"
└── 4:30 PM - Sales access GRANTED - "Show my pipeline for this quarter"

Mike Manager (ProGear-Managers)
├── 9:00 AM - Inventory access GRANTED - "Low stock alerts"
├── 2:30 PM - Pricing access DENIED - "Show profit margins" (not in allowed group)
└── 3:45 PM - Inventory access GRANTED - "Update basketball count to 8,000"

Frank Finance (ProGear-Finance)
├── 10:00 AM - Pricing access GRANTED - "Q4 margin analysis"
└── 1:30 PM - Customer access DENIED - "Show customer list" (not in allowed group)
```

Everything is visible. Everything is traceable. Everything is explainable.

---

## The Key Concept: "On Behalf Of"

This is the most important security concept to understand, and it's surprisingly simple.

### The Problem with Traditional AI Access

Many AI systems work like this:
- The AI has its own credentials (like a service account)
- When anyone asks the AI to do something, it uses those credentials
- The AI can access everything its credentials allow
- There's no connection between "who asked" and "what the AI can do"

**The danger:** If the AI can access customer data, then *anyone* who can talk to the AI can access customer data - whether they should or not.

### How "On Behalf Of" Changes Everything

With Okta AI Agent Governance, the user and agent remain two distinct identities. The agent has its own governed Workload Principal, owners, credentials, lifecycle, and resource connections; it does not receive an unbounded service-account pass. For each delegated request:

- **Okta evaluates the user and the registered agent together**
- **Sarah asks a question → policy evaluates Sarah + ProGear Agent + resource + scope**
- **Mike asks the same question → the same agent is evaluated with Mike's identity instead**

Think of it like a credentialed representative:
- The representative has a badge of its own
- The badge shows which person the representative is acting for
- The destination still applies its policy to both identities and the requested permission
- The audit trail keeps the employee and agent visible instead of merging them

### What This Looks Like in Practice

**Sarah (Sales team) asks:** "Show me customer purchase history"
- The AI acts on behalf of Sarah
- Sarah has customer access → Request approved
- The AI retrieves the data

**Mike (Warehouse team) asks:** "Show me customer purchase history"
- The AI acts on behalf of Mike
- Mike does NOT have customer access → Request denied
- The AI politely declines

**Same governed agent. Same question. Different results.** The employee context changes while the agent identity remains attributable.

### The Technical Term (Optional)

In Okta and industry standards, this uses an **Identity Assertion**: the registered agent proves that it is acting on behalf of a specific user for a specific target. The formal name is **ID-JAG** (Identity Assertion JWT Authorization Grant). The important point is that the user's identity is delegated without erasing the agent's own identity.

### Why This Matters for Security

| Without "On Behalf Of" | With "On Behalf Of" |
|------------------------|---------------------|
| AI has broad shared access | Agent has a governed identity and explicit resource connections |
| Anyone can trigger that access | User, agent, resource, and scope policy are evaluated together |
| Logs show "AI did something" | Logs show "AI did something for Sarah" |
| Can't enforce per-user rules | Same rules as if Sarah did it herself |
| Revoking access is complex | Disable the user or the AI instantly |

### The Two Identities in Every Request

Every time the AI accesses data, the system records two identities:

1. **The User** (WHO asked): Sarah Sales
2. **The Agent** (WHAT acted): ProGear Sales AI

This is why the audit logs are so powerful. You're not just seeing "data was accessed" - you're seeing "Sarah asked the AI to access this data."

---

## The Four Ways AI Can Access Your Data

Not all AI implementations are created equal. There are four different approaches, and they offer very different levels of security and visibility.

### Approach 1: Basic Access (No Real Governance)

**What it is:** The AI has credentials (like a username and password) and uses them to access data directly.

**The analogy:** Giving someone a master key to your building. They can come and go as they please.

**Example scenario:**
- Your company sets up an AI assistant
- The AI is given database credentials
- Anyone who can talk to the AI can access whatever the AI can access
- Logs show "AI Service accessed customer database" but not who asked or why

**The problems:**
- You can't tell which employee triggered which access
- You can't enforce "Sarah can see this, but Mike can't"
- If something goes wrong, you can't trace it back
- Revoking access means changing shared credentials everywhere

**When this is used:** Unfortunately, many early AI implementations work this way.

### Approach 2: Okta-Managed Security (This Demo)

**What it is:** Okta manages both the AI agent identity and the access rules. This is what the ProGear demo shows.

**The analogy:** A professional security company manages your building. Every visitor is checked, logged, and tracked.

**Example scenario:**
- Your AI agent is registered with Okta as a "Workload Principal"
- When Sarah asks the AI something, the AI proves it's acting for Sarah
- Okta checks: "Is Sarah allowed to see this? Is this AI agent approved?"
- Temporary, limited access is granted and fully logged

**The benefits:**
- Complete visibility: You know exactly who, what, when, and why
- Fine-grained control: Different employees get different access
- New-token cutoff: One click disables the agent's authentication and delegated exchanges
- Unified management: Same system you use for employee access

**Status:** Works today. This demo proves it.

### Approach 3: Your Own Security + Okta Identity

**What it is:** You have your own internal systems that control access, but Okta provides the verified identity information.

**The analogy:** You run your own building security, but Okta provides verified ID cards that your guards can trust.

**Example scenario:**
- Sarah asks the AI about internal project data
- The AI gets identity proof from Okta
- Your internal system receives that proof and makes the access decision
- You control the rules, Okta provides the trusted identity

**The benefits:**
- Same identity verification as Approach 2
- Works with systems you already have
- You maintain full control over access rules
- Okta provides the audit trail for identity verification

**Status:** Works today if you build the integration.

### Approach 4: Third-Party Apps + Okta Identity

**What it is:** AI agents access third-party applications (Salesforce, ServiceNow, etc.) using Okta-verified identity.

**The analogy:** Your employee ID badge works at partner company buildings too, and everything is logged.

**Example scenario:**
- Sarah asks the AI to "Update my Salesforce opportunity"
- The AI gets identity proof from Okta
- Salesforce receives the proof and verifies Sarah's access
- The action is taken and logged in both systems

**The benefits:**
- Same governance model extends to external apps
- IT maintains central control through Okta
- No more employees creating their own AI-to-SaaS connections
- Unified visibility across internal and external systems

**Status:** Growing ecosystem. Anthropic's MCP (the system Claude uses) has adopted this approach.

### Comparison Summary

| Aspect | Approach 1 | Approach 2 | Approach 3 | Approach 4 |
|--------|-----------|-----------|-----------|-----------|
| **Who triggered it?** | Unknown | Known | Known | Known |
| **Which AI did it?** | Vague | Specific | Specific | Specific |
| **Access rules** | All or nothing | Per-user | Per-user | Per-user |
| **Audit trail** | Minimal | Complete | Complete | Complete |
| **Revoke access** | Complicated | One click | One click | One click |
| **Works today** | Yes | Yes | Yes (build needed) | Growing |

---

## What Makes Okta Different

### Every AI Agent Has a Real Identity

In Okta, AI agents aren't just applications with passwords. They're first-class identities, just like employees.

**What you see in the Okta dashboard:**

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Agent: ProGear Sales Agent                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Status:        ● Active                                        │
│  ID:            wlpuoor63yK6LYFEh1d7                             │
│  Owner:         john.admin@company.com                          │
│  Created:       December 1, 2024                                │
│  Last Active:   2 minutes ago                                   │
│                                                                 │
│  Can Access:                                                    │
│    ✓ Sales API      (read orders, quotes, pipeline)             │
│    ✓ Inventory API  (read stock levels)                         │
│    ✓ Customer API   (read customer info)                        │
│    ✓ Pricing API    (read prices, margins, discounts)           │
│                                                                 │
│  Recent Activity:                                               │
│    • 2 min ago: Sarah Sales - inventory:read - GRANTED          │
│    • 5 min ago: Mike Manager - pricing:read - DENIED            │
│    • 8 min ago: Sarah Sales - customer:lookup - GRANTED         │
│                                                                 │
│  [Deactivate]  [View Logs]  [Edit Permissions]                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key elements:**

1. **Unique ID**: Every AI agent has an identifier that never changes. The ID starts with "wlp" which stands for **Workload Principal** - Okta's term for a non-human identity like an AI agent. Just as employees have user IDs, AI agents have workload principal IDs. If you see `wlpuoor63yK6LYFEh1d7` in a log, you know exactly which agent it was.

2. **Mandatory Owner**: Someone must be responsible. When John leaves the company, the ownership transfer is part of offboarding.

3. **Clear Status**: Is it active? When was it last used? Dormant agents are visible and can be cleaned up.

4. **Explicit Permissions**: Not "this AI can access everything." It's "this AI can access these specific things."

5. **Activity History**: Recent actions are visible right on the agent's page.

### One-Click Control

**Scenario:** It's Friday at 4:55 PM. Your security team detects unusual behavior from an AI agent.

**Without Okta:**
- Call the on-call engineer
- Figure out which system the AI uses
- Find the credentials
- Rotate them in multiple places
- Hope you didn't break something
- It's now 8:00 PM

**With Okta:**
- Go to Directory → AI Agents
- Find the agent
- Click "Deactivate"
- New authentication and delegated token exchanges for that agent stop
- It's now 4:56 PM
- You can investigate calmly

**The "Deactivate" button is like a kill switch for new access.** It doesn't delete anything or cause data loss. The agent can no longer authenticate or obtain new delegated tokens. A short-lived resource token issued before deactivation remains governed by its expiry and the resource server's revocation policy. When you're ready, you can reactivate the agent.

### Complete Audit Trail

Every delegated token exchange is logged with both identities and its authorization context. A request denied before exchange is recorded by the application as a stopped business decision instead of pretending that a token event occurred. Here is what the exchange evidence looks like in plain English:

**Successful Access:**
```
What happened:     AI agent requested access and was approved
When:              December 15, 2024 at 2:23:47 PM
AI Agent:          ProGear Sales Agent (wlpuoor63yK6LYFEh1d7)
Acting for:        Sarah Sales (sarah.sales@atko.email)
Accessed:          Inventory API
Permission:        inventory:read
Result:            GRANTED
```

**Denied Access:**
```
What happened:     AI agent requested access and was denied
When:              December 15, 2024 at 2:30:12 PM
AI Agent:          ProGear Sales Agent (wlpuoor63yK6LYFEh1d7)
Acting for:        Mike Manager (mike.manager@atko.email)
Attempted:         Pricing API
Permission:        pricing:read
Result:            DENIED
Reason:            User not in required group (needs ProGear-Sales)
```

**What you can do with these logs:**
- Export them for compliance audits
- Set up alerts for unusual patterns
- Investigate incidents with complete information
- Prove to regulators that you have proper controls

---

## Real-World Scenarios with Examples

### Scenario 1: The Sales Representative (Full Access)

**Meet Sarah Sales**
- Job: Sales Representative
- Team: Sales Department
- Okta Group: ProGear-Sales

**What Sarah can do with the AI:**

| Sarah asks... | AI checks... | Result |
|--------------|--------------|--------|
| "What's in our sales pipeline?" | Sales access? Yes (Sales team) | Shows pipeline data |
| "How many basketballs in stock?" | Inventory access? Yes (Sales can read) | Shows 8,500 units |
| "Look up Acme Corp's purchase history" | Customer access? Yes (Sales team) | Shows order history |
| "What's our margin on Pro Game Basketball?" | Pricing access? Yes (Sales team) | Shows 42% margin |

**Sarah's experience:**
- She doesn't notice any security checks
- Everything just works
- She can help customers quickly
- Her access is appropriate for her job

**What the audit shows:**
- Four successful access requests
- All tied to Sarah's identity
- All within her authorized scope
- Complete timestamps and details

### Scenario 2: The Warehouse Manager (Limited Access)

**Meet Mike Manager**
- Job: Warehouse Manager
- Team: Warehouse Operations
- Okta Group: ProGear-Managers

**What Mike can do with the AI:**

| Mike asks... | AI checks... | Result |
|--------------|--------------|--------|
| "What products are low on stock?" | Inventory access? Yes (Warehouse team) | Shows low stock alerts |
| "Update basketball count to 9,000" | Inventory write? Yes (Warehouse team) | Updates the count |
| "Show me customer contact info" | Customer access? No (Warehouse doesn't need this) | Politely declined |
| "What's our profit margin on shoes?" | Pricing access? No (Warehouse doesn't need this) | Politely declined |

**Mike's experience:**
- He can do everything his job requires
- Requests outside his scope are politely declined
- No error messages or confusing failures
- The AI offers to help with what he CAN do

**When Mike asks about pricing, the AI responds:**
> "I'm not able to access pricing information for your account. I can help you with inventory management, stock alerts, and warehouse operations. Would you like me to check stock levels for any products?"

**What the audit shows:**
- Two successful inventory requests
- Two denied requests (customer, pricing)
- Clear reasons for each denial
- Pattern is visible if Mike repeatedly tries to access unauthorized data

**One more thing worth knowing about that "Update basketball count to 9,000" row:** Mike's job role clearing him to make inventory updates at all is only the first check. Before a change of that size happens, FGA compares his role with the requested quantity, and a change above 600 is sent to an AI Agent Owner for approval. See "A Closer Look" below for why those extra checks exist.

### Scenario 3: The Finance Analyst (Specialized Access)

**Meet Frank Finance**
- Job: Financial Analyst
- Team: Finance Department
- Okta Group: ProGear-Finance

**What Frank can do with the AI:**

| Frank asks... | AI checks... | Result |
|--------------|--------------|--------|
| "Show me margin analysis for Q4" | Pricing access? Yes (Finance team) | Shows margin data |
| "What discounts are we offering?" | Pricing access? Yes (Finance team) | Shows discount structure |
| "Look up Acme Corp's address" | Customer access? No (Finance doesn't need this) | Politely declined |
| "How many items sold this month?" | Sales access? No (Finance doesn't need this) | Politely declined |

**Frank's experience:**
- He has deep access to financial data
- He can analyze pricing, margins, and discounts
- He can't see individual customer details or sales rep performance
- This matches his actual job requirements

**What the audit shows:**
- Complete record of Frank's financial data access
- Boundaries are enforced appropriately
- Finance team access is isolated from customer PII

### Scenario 4: The Suspicious Pattern

**The situation:** Your security team notices something unusual in the logs.

**What they see:**
```
Friday, December 15

Mike Manager (ProGear-Managers):
  3:00 PM - pricing:read - DENIED - "Show profit margins"
  3:02 PM - pricing:read - DENIED - "What's our markup?"
  3:05 PM - customer:read - DENIED - "Show customer list"
  3:08 PM - pricing:margin - DENIED - "Display margin report"
  3:10 PM - pricing:discount - DENIED - "What discounts exist?"
```

**What this tells security:**
- Mike is repeatedly trying to access data outside his role
- This could be innocent (curiosity) or concerning (data gathering)
- Either way, the attempts were blocked
- The pattern is documented for investigation

**What security can do:**
- Talk to Mike or his manager
- Review if his role should change
- Verify this is actually Mike (not someone using his account)
- All without any data having been exposed

### Scenario 5: The Emergency Deactivation

**The situation:** It's 9 PM on Saturday. You get an alert that an AI agent is making unusual requests at high volume.

**The sequence of events:**

1. **9:00 PM - Alert received**
   - Monitoring system flags: "ProGear Sales Agent - 500 requests in last 5 minutes"
   - Normal average: 50 requests per hour

2. **9:02 PM - Security officer investigates**
   - Logs into Okta Admin Console from phone
   - Goes to Directory → AI Agents → ProGear Sales Agent
   - Sees the unusual activity

3. **9:03 PM - Agent deactivated**
   - Clicks "Deactivate"
   - Confirmation: the agent can no longer authenticate or obtain new delegated tokens
   - Clicks "Confirm"

4. **9:04 PM - Threat contained**
   - New delegated token exchanges from the agent are rejected
   - Previously issued short-lived tokens age out under resource policy
   - All legitimate users can still work (other systems unaffected)

5. **Monday morning - Investigation**
   - Complete logs available for analysis
   - Can determine: What was accessed? By which users? What data was returned?
   - Root cause identified and fixed
   - Agent reactivated with updated security

**Without this capability:**
- The attack could continue all weekend
- Finding the right credentials to revoke would take time
- Other systems might be affected
- Logs might not have enough detail to investigate

---

## A Closer Look: Two More Safety Checks for High-Stakes Actions

Everything above - the badge system, the "on behalf of" model, the four separate checkpoints - answers one question: **is this person's role allowed to do this kind of thing at all?** That's an important question, and it's a mostly stable one: it doesn't change hour to hour.

But for the highest-stakes actions - the ones with real business consequences if they go wrong - "the role is allowed to do this" isn't the whole story. Two more checks run underneath it, and they answer questions that a role-based badge system was never designed to answer.

### Check #2: Is this role enough for this quantity?

Think about it this way: Okta holds one role level for the inventory story: **0 = Sales, 1 = Manager, 2 = VP**. Mike's Level 1 role is real and current, and the final decision also depends on the quantity he asked to change.

So this demo adds a second, automatic check that combines the live Okta role with the requested quantity:
- Is the request a read, a standard write of 1–600, or a large write of 601 or more?
- Is the person's role high enough to execute it directly, should a Manager create an AI Agent Owner request, or must the write stop?

**Why use both Okta and FGA?** Okta remains the source of truth for identity and role level and issues the narrow Inventory token. The Inventory boundary validates that signed token. FGA is purpose-built to combine the role with the requested quantity for one action, without keeping a second mutable role copy that could drift from Okta.

**In plain terms:** Sarah (Level 0, Manager False) can read, but every write stops before delegated token exchange and she contacts her manager. With FGA enabled, Mike (Level 1, Manager True) can write through 600 units, but 601 needs an AI Agent Owner; with FGA off, his coarse `inventory:write` scope permits any positive quantity. A Level 2 VP (Manager True) can execute any quantity. The hosted demo previews that outcome through Mike's isolated session. If any employee is marked On vacation, the agent stops before ID-JAG for every action; the role remains unchanged, but delegated work is suspended.

### Check #3: Should a human still look at this one?

Even after both of the above say yes, one more question remains: is this action, at this size, something a computer should be allowed to finish on its own?

In this demo, Sales writes never become access requests. A Manager write of 601 or more becomes an `AIAgentOwners` request. Nothing changes in Inventory while that request is pending. The owner sees a short summary of who requested what and why approval is needed—not internal JSON. When OIG reports approval, the backend loads the exact action from its approval ledger, checks that the approver is still in `AIAgentOwners`, mints and validates a real service token, and executes once.

**Why require a person to sign off on something that's already fully authorized?** Because "is this allowed" and "is this a good idea right now" are genuinely different questions:

- "May this role execute this quantity?" is the FGA decision: Manager for normal changes, VP for 601+.
- "Did a current AI Agent Owner approve it?" is the governance decision. The request and decision are recorded in Okta Identity Governance, and the approver still has to belong to the required owner group when execution occurs.

Put the checks together and the picture is crisp: Okta establishes identity, checks whether delegation is currently appropriate, and supplies the role claim; FGA decides direct execution, Sales denial, or Manager-to-owner escalation using role and quantity; OIG records the required AI Agent Owner decision. None can be skipped by getting past another.

---

## Why This Matters for Your Business

### For Your Compliance Team

**Auditors ask tough questions. Okta gives you clear answers.**

| Auditor Question | Your Answer |
|-----------------|-------------|
| "How do you control AI access to customer data?" | "The same way we control employee access - through Okta policies. Here's the policy that governs it." |
| "Can you show me who accessed what?" | "Yes. Here's the complete log with user, AI agent, data accessed, and timestamp for any time period you want." |
| "What happens if an AI agent is compromised?" | "We deactivate its governed identity with one click. New delegated token exchanges stop, and short-lived tokens already issued age out under resource policy." |
| "How do you ensure AI agents only access appropriate data?" | "Each user's AI requests are governed by their group membership. Same rules as direct access." |

**Compliance frameworks this supports:**
- **SOC 2**: Demonstrates access controls and monitoring
- **GDPR**: Shows who accessed personal data and why
- **HIPAA**: Proves access is limited to authorized users
- **PCI-DSS**: Documents access to cardholder data
- **ISO 27001**: Supports access management requirements

### For Your Security Team

**Real security controls, not security theater.**

| Security Need | How Okta Delivers |
|--------------|-------------------|
| **Least Privilege** | AI agents get temporary, limited access - just enough to answer the user's question |
| **No Shared Secrets** | AI agents use cryptographic keys, not passwords that can be stolen or shared |
| **Complete Visibility** | Delegated exchanges keep user, agent, target, scopes, and outcome; the app records pre-exchange business denials |
| **Rapid Response** | One-click deactivation stops new authentication and token exchanges |
| **Pattern Detection** | Logs enable detection of unusual behavior |

**What your security team gains:**
- AI agents visible in the same console as everything else
- No shadow AI systems with unknown access
- Same security model for AI as for humans
- Ability to respond to incidents quickly

### For Your IT Operations Team

**Manageable at scale, not a special snowflake.**

| Operations Need | How Okta Delivers |
|----------------|-------------------|
| **Central Management** | All AI agents in one dashboard |
| **Consistent Policies** | Same access rules for AI and humans |
| **Clear Ownership** | Every AI agent has an assigned owner |
| **Lifecycle Management** | Onboard, modify, offboard like any other identity |
| **Integration** | Works with your existing Okta setup |

**What IT operations gains:**
- No separate system to manage
- AI governance is an extension of identity governance
- Familiar tools and workflows
- Scales with your AI adoption

### For Your Executive Team

**Answer board-level questions with confidence.**

| Executive Question | Your Answer |
|-------------------|-------------|
| "Are our AI systems secure?" | "They're governed by the same identity system as our employees, with attributable exchange evidence and business decisions." |
| "What's our risk exposure?" | "Each AI action is tied to a specific user and logged. We can deactivate an agent identity to stop new access, while short token lifetimes bound existing exposure." |
| "Are we compliant?" | "Yes. We can demonstrate who accessed what, when, and why for any time period." |
| "What if something goes wrong?" | "We have complete logs for investigation and can immediately stop an AI agent from obtaining new access." |

---

## The Industry is Moving This Way

### Anthropic and MCP

In May 2025, **Anthropic** (the company behind Claude) announced that their **Model Context Protocol (MCP)** would adopt this same approach for enterprise authentication.

**What is MCP?**
MCP is the system that allows AI assistants like Claude to connect to external tools and data sources. When an employee uses Claude to access company data, MCP handles that connection.

**Why this matters:**
- Anthropic is one of the leading AI companies
- MCP is becoming an industry standard
- Their adoption validates this security approach
- Companies implementing this now are ahead of the curve

### The Problem MCP Solves

**Before (how most AI-to-app connections work today):**
- Employee wants to connect Claude to Salesforce
- Claude asks the employee to log into Salesforce directly
- Employee approves the connection
- IT has no visibility or control
- Each employee manages their own connections
- No central audit trail

**After (with the XAA approach):**
- Employee logs into Claude through company SSO (Okta)
- Claude asks Okta: "Can this user access Salesforce?"
- Okta checks policies and grants or denies access
- IT maintains central control
- Attributable delegated-exchange trail in Okta

### What This Means for You

If you implement AI Agent Governance today:
- You're using the same approach that industry leaders have validated
- You're prepared for the direction the industry is moving
- Your governance model will extend to new AI tools as they adopt this standard
- You're building on a foundation, not a dead end

---

## Common Questions

### "Do our employees need to learn something new?"

**No.** From an employee's perspective, nothing changes. They:
- Log in the same way they always have
- Use the AI assistant normally
- Don't see any additional prompts or steps

All the security happens behind the scenes. The experience is seamless.

### "What if we have multiple AI agents?"

You manage them all in one place. Each AI agent:
- Has its own unique identity
- Has its own assigned owner
- Has its own access permissions
- Can be independently monitored and controlled

Whether you have 1 AI agent or 100, the management model is the same.

### "How is this different from just giving the AI a service account?"

A service account is like giving someone a master key to the building. Once they have it, they can come and go freely - and here's the problem: every time that key is used, the security log just says "someone used the master key." It doesn't say who they were let in for.

That's the real issue with a shared credential, not just that it's old-fashioned. If your AI has one set of credentials it uses for every employee's request, then:

- **Every action looks identical**, whether the AI is helping Sarah, helping Mike, or - if that credential is ever stolen - helping someone who has no business being there at all. Nothing in the log tells them apart.
- **If that one credential leaks, the damage isn't limited to one person's access - it's every floor the AI was ever allowed into**, for every employee it has ever worked with. There's no way to say "just cut off the bad part" because the credential never distinguished good usage from bad usage in the first place.
- **You can't say "Sarah can, but Mike can't"** through the credential itself. That rule would have to be coded into the AI application by hand, somewhere no security team or auditor can see it.

Okta AI Agent Governance is like having a security checkpoint that checks two badges on every single entry, not one: the AI's own badge, and the badge of the person it's currently working for. Every entry is:
- Verified: "Who are you, and who sent you?" (both identities, every time - never just one)
- Authorized: "Is this specific person allowed where they're going?"
- Logged: "Record of exactly what happened, and for whom"
- Controlled: "Your pass is temporary and limited"

Because the AI's badge always travels paired with a specific person's badge, a stolen or misused AI credential shows up immediately as unusual pairings in the log - not as an invisible blur of "the app did something." And revoking the AI's badge doesn't require touching anyone's actual account; the two identities were always separate.

### "What if an AI agent needs to work without a user?"

Some AI agents do batch processing or scheduled tasks without a user actively requesting something.

For these cases:
- The AI agent still has its own identity
- Access is still logged
- Policies still apply
- But the "acting for user" is the system or schedule

You still have visibility and control, just without a human in the loop.

### "How quickly can we implement this?"

If you already use Okta for identity management, the core infrastructure is in place. Implementation involves:
- Registering your AI agents in Okta
- Configuring access policies
- Updating your AI applications to use Okta for authentication

The demo you're looking at was built to show this working end-to-end.

### "What about AI agents from vendors?"

This is Approach 4 in our earlier breakdown. As vendors adopt this standard:
- Your existing Okta policies extend to their AI agents
- You maintain central visibility and control
- No need to manage credentials for each vendor's AI

The ecosystem is growing, and MCP's adoption of this approach is accelerating it.

### "Can we try this before committing?"

Yes! The ProGear demo lets you:
- Log in as different users (Sarah, Mike, and Frank); use Mike's isolated FGA control to preview VP
- Ask questions and see what's allowed or denied
- Watch the **Token Flow** page show issued tokens and business decisions in real time
- Use the Okta System Log for the delegated exchanges that were actually attempted

It's a working demonstration, not just slides.

---

## The Bottom Line

AI agents are powerful tools. They can access customer data, financial information, inventory systems, and more. That power requires proper governance.

**Without governance, you have:**
- AI agents accessing data with no way to know who triggered it
- No ability to enforce "this person can see this, but not that"
- Incomplete audit trails that won't satisfy regulators
- No quick way to shut down a misbehaving AI agent

**With Okta AI Agent Governance, you have:**
- Complete visibility into every AI agent and what it accesses
- The same access controls for AI as for human employees
- Delegated actions tied to both a specific user and a specific agent
- One-click ability to deactivate an AI agent and stop new delegated access
- A per-action check that combines the live Okta role with the requested quantity
- Human sign-off automatically required before the highest-stakes actions complete

No single one of these is enough on its own. Identity without the role-and-quantity check would treat every inventory change alike. The quantity check without identity would have no trustworthy role to evaluate. And none of it matters if the largest changes can still complete without qualified review. The combination—and each layer being unable to override the others—is what makes the whole system trustworthy.

**The simple principle:** Your AI agents should be as governed as your employees.

With Okta, they are.

---

## See It In Action

The ProGear demo shows this working in real-time:

1. **Log in as different users**
   - Sarah Sales: Full access to all four data domains
   - Mike Manager: Inventory only
   - Mike's VP preview: Inventory, including direct large writes
   - Frank Finance: Pricing only

2. **Ask questions and watch the results**
   - See what each user can access
   - See what gets denied and why
   - Watch the AI handle boundaries gracefully

3. **View the Token Flow page**
   - See the AI agent's identity
   - Watch token exchanges happen in real-time
   - See granted vs. denied access

4. **Check the Okta System Log**
   - Delegated exchange attempts are recorded independently of the app
   - User, agent, target authorization server, scopes, and outcome remain attributable
   - Pre-exchange role denials remain visible as application business decisions

Reading about security is one thing. Watching it work is another.

---

## Ready to Learn More?

- **For technical details:** See [okta-security-value.md](./okta-security-value.md)
- **For architecture overview:** See [architecture.md](./architecture.md)
- **For implementation guide:** See [implementation-guide.md](./implementation-guide.md)

---

*This guide accompanies the ProGear AI Agent demo showcasing Okta AI Agent Governance. The concepts apply to any organization implementing AI agents that access sensitive data.*
