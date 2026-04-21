# FGA Integration Prompts

This document captures the prompts and instructions used to implement Auth0 FGA integration in the ProGear Sales AI demo.

---

## Session Context

**Date**: April 2026
**Goal**: Integrate Auth0 FGA with Okta to demonstrate "Better Together" - fine-grained authorization using Okta token claims

---

## Prompt 1: Initial Understanding

```
Hey Claude, looking at this code and wait for my ask - please read the docs and understand
the demo's value to Okta for AI Agents and the Workload Principal.
```

**Action**: Read codebase, O4AA documentation, understand demo architecture.

---

## Prompt 2: Read FGA Integration Plan

```
in the docs folder can you read purrfect-mapping-hare.md our plan to install the FGA SDK.
Please be sure to ask clarifying questions to ensure I can build out the best demo with
the Auth0 FGA that I have full access to. Customers have been asking for us to show this
with demo and its value. Remember its all about showing Okta and FGA better together
```

**Action**: Read the FGA integration plan, ask clarifying questions about:
- FGA credentials (ready?)
- Agent scope (inventory only vs all agents)
- Vacation status source (Okta claim vs UI toggle)
- UI changes (FGA explanation panel)

---

## Prompt 3: Implement FGA Integration

```
yes (proceed with implementation)
```

**Action**: Implemented:
1. `backend/auth/fga_client.py` - FGA SDK client
2. `backend/auth/fga_seed.py` - Seed script
3. Modified `backend/orchestrator/orchestrator.py` - Added FGA check node
4. Updated `.env.example` - FGA env vars
5. Created `FGAExplanationCard.tsx` - Frontend component
6. Updated `page.tsx` - Wired FGA panel

---

## Prompt 4: Debug LLM Routing Error

```
why I am getting this WARNING:orchestrator.orchestrator:LLM routing failed,
using keyword fallback: Expecting value: line 1 column 1 (char 0)
```

**Action**: Diagnosed JSON parsing issue with LLM response.

---

## Prompt 5: Switch to Raw Anthropic SDK

```
CAN YOU change the code to use antropic key and comment out other method for llm interaction.
Please share the details before making changes
```

**Action**: Proposed switching from `langchain-anthropic` to raw `anthropic` SDK.

**Follow-up**: `A` (confirm Option A - raw SDK)

**Changes**:
- Replaced `ChatAnthropic` with `anthropic.Anthropic`
- Updated `_router_node` and `_generate_response_node`
- Removed unused `langchain-anthropic`, `langchain-openai`, `openai` dependencies

---

## Prompt 6: Remove Unused Code

```
is this the only file need change for antropic llm interaction?
```

**Action**: Checked for other LangChain usages.

```
can you remove the unused
```

**Action**: Removed `backend/agents/` folder (unused agent classes), cleaned `requirements.txt`.

---

## Prompt 7: Debug FGA Denying All Users

```
getting this INFO:auth.fga_client:FGA check: user:bob.manager@atko.email manager
inventory_system:main_db (vacation=False) -> False
```

**Diagnosis**: FGA tuples only contained `mike.manager@atko.email`, not `bob.manager@atko.email`.

---

## Prompt 8: Dynamic FGA Using Token Claims

```
I do not want you to hard code the user instead I want you to read the token of the
authenticated user and then check the tuple. can you share your plan before you make changes
```

**Action**: Proposed claims-based FGA evaluation instead of tuple lookup.

**Plan**:
1. Read `is_a_manager` and `is_on_vacation` from Okta ID token claims
2. Evaluate FGA model logic locally using these claims
3. No FGA API calls needed, works for any authenticated user

```
yes (proceed)
```

**Changes**:
- Rewrote `backend/auth/fga_client.py` - Claims-based evaluation
- Updated `_fga_check_node` to read claims from `user_info`

---

## Prompt 9: Save Context

```
capture all the context and memory for next time if we need to restart the conversation.
Also create a file with all the prompts
```

**Action**: Created memory files and this prompts document.

---

## Key Implementation Decisions

### 1. Claims-Based FGA (Not Tuple Lookup)

**Problem**: FGA tuples require pre-seeding every user email.

**Solution**: Evaluate FGA model logic using Okta token claims:
```python
is_a_manager = user_info.get("is_a_manager", user_info.get("Manager", False))
is_on_vacation = user_info.get("is_on_vacation", user_info.get("Vacation", False))

# FGA logic: manager AND NOT on_vacation
if not is_a_manager:
    denied
elif is_on_vacation:
    denied
else:
    allowed
```

### 2. Raw Anthropic SDK (Not LangChain)

**Problem**: LangChain wrapper obscured errors.

**Solution**: Direct `anthropic` SDK:
```python
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
response = client.messages.create(
    model=LLM_MODEL_NAME,
    max_tokens=500,
    messages=[{"role": "user", "content": prompt}]
)
result = response.content[0].text
```

### 3. Required Okta Claims

On **Org Authorization Server** (ID Token):

| Claim Name | Value | Purpose |
|------------|-------|---------|
| `Manager` | `user.is_a_manager` | User has manager role |
| `Vacation` | `user.is_on_vacation` | User on vacation |

**Path**: Okta Admin → Security → API → Authorization Servers → Claims → Add Claim

---

## Files Modified

| File | Change |
|------|--------|
| `backend/auth/fga_client.py` | Rewritten for claims-based FGA |
| `backend/auth/fga_seed.py` | Created (reference only) |
| `backend/orchestrator/orchestrator.py` | Raw Anthropic SDK, FGA check node |
| `backend/requirements.txt` | Removed unused LangChain deps |
| `backend/agents/` | Deleted (unused) |
| `.env.example` | Added FGA env vars |
| `packages/.../FGAExplanationCard.tsx` | Created FGA UI panel |
| `packages/.../page.tsx` | Added FGA card to dashboard |

---

## Testing Checklist

1. [ ] Ensure `ANTHROPIC_API_KEY` is set
2. [ ] Ensure Okta claims (`Manager`, `Vacation`) are on Org Auth Server
3. [ ] Set user's `is_a_manager` attribute in Okta user profile
4. [ ] Test: Manager not on vacation → Inventory access ALLOWED
5. [ ] Test: Manager on vacation → Inventory access DENIED
6. [ ] Test: Non-manager → Inventory access DENIED
7. [ ] Verify FGA panel shows decision reason in UI

---

# Session 2: FGA API with Contextual Tuples (April 15, 2026)

## Goal

Switch from claims-based local FGA evaluation to real FGA API calls with contextual tuples.

---

## Prompt 10: Update FGA to Use Contextual Tuples

```
Hey can you update the FGA implementation we did yesterday to check the token in this format:
const { sub: userId, is_on_vacation } = req.user; 
const resourceId = "main_db";

const contextualTuples = [];
if (is_on_vacation === true) {
  contextualTuples.push({
    user: `user:${userId}`,
    relation: 'on_vacation',
    object: `inventory_system:${resourceId}`
  });
}

const { allowed } = await fgaClient.check({
  tuple_key: {
    user: `user:${userId}`,
    relation: 'can_increase_inventory',
    object: `inventory_system:${resourceId}`
  },
  contextual_tuples: contextualTuples 
});
```

**Action**: Analyzed current implementation and proposed changes.

**Question**: Does FGA model have pre-seeded manager tuples (Option A) or need both claims as contextual tuples (Option B)?

```
use option A and make the changes and wait for my instruction to commit to github
```

---

## Prompt 11: Implementation

**Changes Made**:

### `backend/auth/fga_client.py` (Rewritten)
- Added FGA SDK client initialization with OAuth2 credentials
- New `_get_fga_client()` singleton function
- New `check_inventory_access_via_fga()` - calls FGA API with contextual tuples
- Updated `check_agent_access()` to use `user_id` (sub) instead of `user_email`
- Removed `is_a_manager` parameter - now relies on pre-seeded FGA tuples

### `backend/orchestrator/orchestrator.py` (Updated)
- Extract `user_id` from token's `sub` claim
- Only read `is_on_vacation` claim (removed `is_a_manager`)
- Pass `is_on_vacation` as contextual tuple to FGA

---

## Prompt 12: Commit

```
commit
```

**Commit**: `04a59a1 FGA API with contextual tuples`

---

## Key Implementation Decision

### Contextual Tuples Approach

**Previous (Claims-Based)**:
- Read `is_a_manager` and `is_on_vacation` from Okta token
- Evaluate FGA logic locally in Python
- No FGA API calls

**New (FGA API + Contextual Tuples)**:
- Manager status: Pre-seeded in FGA store (`user:{userId} manager inventory_system:main_db`)
- Vacation status: Read from Okta claim, passed as contextual tuple
- Real FGA API check with contextual tuples

### FGA Check Format

```json
{
  "tuple_key": {
    "user": "user:{userId}",
    "relation": "can_increase_inventory",
    "object": "inventory_system:main_db"
  },
  "contextual_tuples": {
    "tuple_keys": [
      {
        "user": "user:{userId}",
        "relation": "on_vacation", 
        "object": "inventory_system:main_db"
      }
    ]
  }
}
```

### FGA Model Required

```
type user
type inventory_system
  relations
    define manager: [user]
    define on_vacation: [user]
    define can_increase_inventory: manager but not on_vacation
```

---

## Updated Testing Checklist

1. [ ] Ensure FGA credentials are set (`FGA_CLIENT_ID`, `FGA_CLIENT_SECRET`, `FGA_STORE_ID`)
2. [ ] Pre-seed manager tuple in FGA: `user:{sub} manager inventory_system:main_db`
3. [ ] Ensure Okta claim `Vacation` (`user.is_on_vacation`) is on Org Auth Server
4. [ ] Test: Manager not on vacation → Inventory access ALLOWED
5. [ ] Test: Manager on vacation → Inventory access DENIED (contextual tuple blocks)
6. [ ] Test: Non-manager (no FGA tuple) → Inventory access DENIED
7. [ ] Verify FGA panel shows contextual tuples in UI

---

## Prompt 13: Fix Render Deployment Error

**Error on Render.com deployment:**
```
ImportError: cannot import name 'ClientTupleKey' from 'openfga_sdk.client.models'
```

**Root Cause**: Wrong class name for contextual tuples in OpenFGA SDK 0.9.7.

**Fix**:
```python
# Wrong:
from openfga_sdk.client.models import ClientCheckRequest, ClientTupleKey

# Correct:
from openfga_sdk.client.models import ClientCheckRequest, ClientTuple
```

**Commit**: `4fe9b54 fix: use ClientTuple instead of ClientTupleKey for OpenFGA SDK`

---

## OpenFGA SDK Quick Reference (openfga-sdk 0.9.7)

```python
from openfga_sdk import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import ClientCheckRequest, ClientTuple

# Initialize client
configuration = ClientConfiguration(
    api_url=FGA_API_URL,
    store_id=FGA_STORE_ID,
    authorization_model_id=FGA_MODEL_ID,
    credentials={
        "method": "client_credentials",
        "config": {
            "client_id": FGA_CLIENT_ID,
            "client_secret": FGA_CLIENT_SECRET,
            "api_issuer": FGA_API_TOKEN_ISSUER,
            "api_audience": FGA_API_AUDIENCE,
        }
    }
)
fga_client = OpenFgaClient(configuration)

# Build contextual tuples
contextual_tuples = [
    ClientTuple(
        user="user:123",
        relation="on_vacation",
        object="inventory_system:main_db"
    )
]

# Check request
check_request = ClientCheckRequest(
    user="user:123",
    relation="can_increase_inventory",
    object="inventory_system:main_db",
    contextual_tuples=contextual_tuples,
)
response = await fga_client.check(check_request)
allowed = response.allowed
```
