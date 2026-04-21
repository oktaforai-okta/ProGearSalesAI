# Integrating Auth0 FGA into courtedge-ai-demo

## Context

The ProGear Sales AI demo currently uses **Okta group-based RBAC** to control which agents (Sales, Inventory, Customer, Pricing) a user can invoke. Group membership is evaluated during ID-JAG token exchange — if a user isn't in the right Okta group, the exchange returns `access_denied`.

This works, but it's coarse-grained. **Auth0 FGA (Fine-Grained Authorization)** adds a second authorization layer that can gate agent access with more granularity — per-user, per-system, with conditional relations like `manager` (with vacation checks) and derived permissions like `can_increase_inventory`.

The `openfga-sdk==0.9.7` package is already in `backend/requirements.txt` but has **zero integration code**. The `.env.example` has FGA env vars stubbed out but commented. This plan wires it all up.

**FGA Store (already created):**
- Store Name: `ProGear`
- API URL: `https://api.us1.fga.dev`
- Store ID: `01KNSR7472HW2PAYFR224NAPCY`
- Model ID: `01KNSR8FRB0CMMN79ZT1M2E9S5`

---

## Architecture: FGA as a Runtime Gatekeeper for AI Agents

FGA acts as a **runtime gatekeeper** — every time an agent is about to be invoked, FGA is checked first. This is not a one-time setup; it's evaluated on every single request with live context (like vacation status). If conditions change mid-day (manager goes on vacation), the next agent invocation is immediately blocked.

Current flow (orchestrator.py):
```
router → exchange_tokens → process_agents → generate_response
```

New flow with FGA as runtime gatekeeper:
```
router → fga_check → exchange_tokens → process_agents → generate_response
         ^^^^^^^^
         RUNTIME GATEKEEPER: checks FGA on every request before token exchange
```

**Why this matters:**
- **Okta RBAC** = static group membership (Sales/Warehouse/Finance). Changes require admin action.
- **FGA gatekeeper** = dynamic, contextual checks evaluated at runtime. A user can be a manager but still be blocked if `is_on_vacation == true` — no admin action needed, the condition evaluates automatically.
- FGA runs **before** token exchange. If FGA denies, we skip the Okta token exchange entirely (no wasted API calls) and the UI immediately shows the agent as denied with the reason.

---

## Step 1: Uncomment and Set FGA Environment Variables

**File:** `.env` (and `.env.example` for documentation)

Uncomment lines 46-51 in `.env.example` and add your real values to `.env`:

```bash
# Auth0 FGA (Fine-Grained Authorization)
FGA_STORE_ID=01KNSR7472HW2PAYFR224NAPCY
FGA_CLIENT_ID=<your-fga-client-id>        # from dashboard.fga.dev → Settings → API Keys
FGA_CLIENT_SECRET=<your-fga-client-secret> # from dashboard.fga.dev → Settings → API Keys
FGA_API_URL=https://api.us1.fga.dev
FGA_API_TOKEN_ISSUER=fga.us.auth0.com     # US region issuer
FGA_API_AUDIENCE=https://api.us1.fga.dev/  # US region audience
FGA_MODEL_ID=01KNSR8FRB0CMMN79ZT1M2E9S5  # optional, locks to a specific model version
```

**Also add to Render** (backend environment variables) when deploying.

---

## Step 2: The FGA Authorization Model (Already in Store)

This model is **already saved** in the ProGear FGA store (Model ID: `01KNSR8FRB0CMMN79ZT1M2E9S5`). It's visible at `dashboard.fga.dev` → Model Explorer.

```
model
  schema 1.1

type user

type inventory_system
  relations
    define can_increase_inventory: manager
    define manager: [user with check_vacation]

condition check_vacation(is_on_vacation: bool) {
  is_on_vacation == false
}
```

**What this gives you:**
- `inventory_system` — represents the Inventory MCP agent
- `manager` — only users assigned as manager AND passing the `check_vacation` condition can act
- `can_increase_inventory` — derived from `manager`, gates write operations (inventory:write scope)
- `check_vacation` — **contextual condition**: the check passes only when `is_on_vacation == false`. This means a manager on vacation is blocked from increasing inventory even though they're assigned the relation.

**How it maps to the demo:**
| FGA Check | ProGear Agent | Scope Gated |
|-----------|--------------|-------------|
| `user:X manager inventory_system:main_db` | Inventory MCP | `inventory:read`, `inventory:alert` |
| `user:X can_increase_inventory inventory_system:main_db` | Inventory MCP | `inventory:write` |

**To extend to other agents**, add more types to this model later:
```
type sales_system
  relations
    define can_access: [user]
    define can_create_orders: [user] or can_access

type customer_system
  relations
    define can_access: [user]
    define can_view_history: [user] or can_access
```

For now, **the model focuses on Inventory** with the vacation condition as the key demo scenario.

---

## Step 3: Seed Relationship Tuples

Add tuples that assign your demo users as `manager` of `inventory_system`. The `check_vacation` condition is evaluated at check time — the tuple just establishes the relationship.

**Create file:** `backend/auth/fga_seed.py`

```python
"""
Seed FGA store with initial relationship tuples for the ProGear demo.

Run once: python -m auth.fga_seed

Assigns users as managers of the inventory_system.
The check_vacation condition is evaluated at check time (not seed time).
"""

import asyncio
import os
from dotenv import load_dotenv
from openfga_sdk import ClientConfiguration, OpenFgaClient, RelationshipCondition
from openfga_sdk.credentials import Credentials, CredentialConfiguration
from openfga_sdk.client.models import ClientTuple, ClientWriteRequest

load_dotenv()


async def seed():
    configuration = ClientConfiguration(
        api_url=os.getenv("FGA_API_URL"),
        store_id=os.getenv("FGA_STORE_ID"),
        authorization_model_id=os.getenv("FGA_MODEL_ID"),
        credentials=Credentials(
            method='client_credentials',
            configuration=CredentialConfiguration(
                api_issuer=os.getenv("FGA_API_TOKEN_ISSUER"),
                api_audience=os.getenv("FGA_API_AUDIENCE"),
                client_id=os.getenv("FGA_CLIENT_ID"),
                client_secret=os.getenv("FGA_CLIENT_SECRET"),
            )
        )
    )

    async with OpenFgaClient(configuration) as fga:
        # Replace these user IDs with actual Okta sub claims
        # Find them in Okta Admin → Directory → People → user ID
        tuples = [
            # Warehouse manager — has manager relation on inventory_system
            # NOTE: User IDs use email format (matching your FGA store convention)
            # The check_vacation condition context is stored ON the tuple
            ClientTuple(
                user="user:mike.manager@atko.email",
                relation="manager",
                object="inventory_system:main_db",
                condition=RelationshipCondition(
                    name="check_vacation",
                    context=dict(is_on_vacation=True),  # Stored on tuple — mike is on vacation
                ),
            ),

            # Add more users as needed:
            # ClientTuple(
            #     user="user:jane.warehouse@atko.email",
            #     relation="manager",
            #     object="inventory_system:main_db",
            #     condition=RelationshipCondition(
            #         name="check_vacation",
            #         context=dict(is_on_vacation=False),  # Jane is NOT on vacation
            #     ),
            # ),
        ]

        body = ClientWriteRequest(writes=tuples)
        await fga.write(body)
        print(f"Seeded {len(tuples)} FGA tuples")


if __name__ == "__main__":
    asyncio.run(seed())
```

**User ID note:** FGA uses email format (`user:mike.manager@atko.email`), matching your existing tuple. The Okta internal ID for mike is `00uushw94qlX4GcTG1d7` (from the profile URL) — but FGA tuples reference the email, not the Okta sub.

**Okta custom attributes already configured for mike.manager:**
- `is_on_vacation` = `true`
- `is_a_manager` = `true`

These exist in the Okta user profile (Directory → People → mike.manager). See Step 4 for how these flow into the FGA check at runtime.

---

## Step 4: Create the FGA Client Module

**Create file:** `backend/auth/fga_client.py`

This is the core integration module. It checks the `inventory_system` model with the `check_vacation` contextual condition.

```python
"""
Auth0 FGA Client for Agent Permission Gating

Checks whether a user can access the inventory system before
attempting Okta token exchange. Uses the check_vacation condition
to block managers who are on vacation.

FGA Model:
  type inventory_system
    relations
      define can_increase_inventory: manager
      define manager: [user with check_vacation]

  condition check_vacation(is_on_vacation: bool) {
    is_on_vacation == false
  }
"""

import os
import logging
from typing import Optional
from openfga_sdk import ClientConfiguration, OpenFgaClient
from openfga_sdk.credentials import Credentials, CredentialConfiguration
from openfga_sdk.client.models import ClientCheckRequest

logger = logging.getLogger(__name__)

_fga_config: Optional[ClientConfiguration] = None

# Maps ProGear agent types → FGA object types
# Only inventory_system is modeled in FGA for now.
# Other agents pass through (no FGA check).
AGENT_TO_FGA_OBJECT = {
    "inventory": "inventory_system:main_db",
}


def _get_fga_config() -> Optional[ClientConfiguration]:
    """Build FGA configuration from environment variables."""
    global _fga_config
    if _fga_config is not None:
        return _fga_config

    api_url = os.getenv("FGA_API_URL", "")
    store_id = os.getenv("FGA_STORE_ID", "")
    client_id = os.getenv("FGA_CLIENT_ID", "")
    client_secret = os.getenv("FGA_CLIENT_SECRET", "")

    if not all([api_url, store_id, client_id, client_secret]):
        logger.info("FGA not configured — skipping fine-grained checks")
        return None

    _fga_config = ClientConfiguration(
        api_url=api_url,
        store_id=store_id,
        authorization_model_id=os.getenv("FGA_MODEL_ID", ""),
        credentials=Credentials(
            method='client_credentials',
            configuration=CredentialConfiguration(
                api_issuer=os.getenv("FGA_API_TOKEN_ISSUER", "fga.us.auth0.com"),
                api_audience=os.getenv("FGA_API_AUDIENCE", "https://api.us1.fga.dev/"),
                client_id=client_id,
                client_secret=client_secret,
            )
        )
    )
    return _fga_config


async def check_inventory_access(
    user_email: str,
    relation: str = "manager",
    is_on_vacation: bool = False,
) -> bool:
    """
    Check if a user has access to the inventory system via FGA.

    The check_vacation condition is passed as context — if the user
    is on vacation, FGA denies access even if they are a manager.

    Args:
        user_email: User's email (e.g., "mike.manager@atko.email") — FGA uses email format
        relation: FGA relation to check ("manager" or "can_increase_inventory")
        is_on_vacation: Whether the user is currently on vacation (from Okta profile)

    Returns:
        True if allowed, False if denied.
        Returns True if FGA is not configured (passthrough).
    """
    config = _get_fga_config()
    if config is None:
        return True  # FGA not configured — rely on Okta RBAC alone

    try:
        async with OpenFgaClient(config) as fga:
            response = await fga.check(ClientCheckRequest(
                user=f"user:{user_email}",
                relation=relation,
                object="inventory_system:main_db",
                context=dict(is_on_vacation=is_on_vacation),
            ))
            allowed = response.allowed
            logger.info(
                f"FGA check: user:{user_email} {relation} inventory_system:main_db "
                f"(vacation={is_on_vacation}) → {allowed}"
            )
            return allowed
    except Exception as e:
        logger.error(f"FGA check failed: {e} — allowing (fail-open)")
        return True


async def check_agent_access(
    user_id: str,
    agent_type: str,
    scopes: list[str] = None,
    is_on_vacation: bool = False,
) -> bool:
    """
    Check if a user can access a specific agent via FGA.

    Currently only inventory_system is modeled in FGA.
    Other agents pass through (return True).

    For inventory:
    - Write scopes (inventory:write) → checks "can_increase_inventory"
    - Read scopes → checks "manager"

    Args:
        user_id: Okta user sub claim
        agent_type: Agent type (sales, inventory, customer, pricing)
        scopes: Requested scopes (used to determine read vs write check)
        is_on_vacation: Whether the user is currently on vacation

    Returns:
        True if allowed, False if denied.
    """
    # Only inventory has an FGA model — others pass through
    if agent_type not in AGENT_TO_FGA_OBJECT:
        return True

    # Determine which relation to check based on requested scopes
    if scopes and "inventory:write" in scopes:
        relation = "can_increase_inventory"
    else:
        relation = "manager"

    return await check_inventory_access(user_id, relation, is_on_vacation)
```

**Key design decisions:**
- **Contextual condition**: The `check_vacation` condition is passed as `context` at check time, not stored in tuples. This means you can toggle vacation status dynamically without rewriting tuples.
- **Scope-aware**: Write scopes check `can_increase_inventory`, read scopes check `manager`.
- **Fail-open**: If FGA is not configured or errors out, access is allowed. Okta RBAC still protects.
- **Only inventory modeled**: Other agents (sales, customer, pricing) pass through for now. Extend by adding more types to the model and entries to `AGENT_TO_FGA_OBJECT`.
- **Vacation status from Okta**: The `is_on_vacation` custom attribute is already on the Okta user profile (e.g., mike.manager has `is_on_vacation: true`). To get this into the backend at runtime, add `is_on_vacation` as a custom claim in your Okta authorization server (Security → API → Authorization Servers → Claims → Add Claim). Then the ID token will include it, and the backend reads it from `user_info`. See Step 5b for how this flows into the FGA check.

---

## Step 5: Integrate FGA into the Orchestrator

**File:** `backend/orchestrator/orchestrator.py`

### 5a. Add import at top of file (after existing imports):

```python
from auth.fga_client import check_agent_access
```

### 5b. Add a new `_fga_check_node` to the workflow:

Add this method to the `Orchestrator` class (after `_router_node`):

```python
async def _fga_check_node(self, state: WorkflowState) -> WorkflowState:
    """
    Check FGA permissions before token exchange.
    Filters out agents the user cannot invoke.

    Currently checks:
    - inventory agent → FGA inventory_system with check_vacation condition
    - all other agents → pass through (no FGA model yet)
    """
    agents = state["agents_to_invoke"]
    user_id = self.user_info.get("sub", "")

    if not user_id or not agents:
        return state

    state["agent_flow"].append({
        "step": "fga_check",
        "action": "Checking fine-grained permissions (FGA)",
        "status": "processing"
    })

    # Determine vacation status for the current user.
    # Option A: Read from Okta user profile custom attribute
    # Option B: Hardcode for demo (toggle to show denied vs allowed)
    # Option C: Pass as query param from frontend for demo flexibility
    is_on_vacation = self.user_info.get("is_on_vacation", False)

    # Check each agent against FGA
    allowed_agents = []
    for agent_type in agents:
        scopes = state["agent_scopes"].get(agent_type, [])
        allowed = await check_agent_access(
            user_id=user_id,
            agent_type=agent_type,
            scopes=scopes,
            is_on_vacation=is_on_vacation,
        )

        if allowed:
            allowed_agents.append(agent_type)
        else:
            # Record as denied in token_exchanges for UI visibility
            from auth.agent_config import get_agent_config, DEMO_AGENTS
            config = get_agent_config(agent_type)
            demo = DEMO_AGENTS.get(agent_type, {})
            requested_scopes = state["agent_scopes"].get(agent_type, [])

            reason = "FGA: manager on vacation — inventory access blocked"
            if "inventory:write" in requested_scopes:
                reason = "FGA: can_increase_inventory denied (manager on vacation)"

            state["token_exchanges"].append({
                "agent": agent_type,
                "agent_name": config.name if config else demo.get("name", ""),
                "color": config.color if config else demo.get("color", "#888"),
                "success": False,
                "access_denied": True,
                "status": "denied",
                "scopes": [],
                "requested_scopes": requested_scopes,
                "error": reason,
                "demo_mode": False,
            })

    state["agents_to_invoke"] = allowed_agents

    denied_count = len(agents) - len(allowed_agents)
    state["agent_flow"].append({
        "step": "fga_check",
        "action": f"FGA: {len(allowed_agents)} allowed, {denied_count} denied",
        "status": "completed"
    })

    return state
```

**Vacation status — how to get it at runtime:**

The `check_vacation` condition needs `is_on_vacation: bool` at check time. The Okta user profile already has this attribute (`is_on_vacation`) — mike.manager is set to `true`.

**Claims already configured on Inventory MCP auth server:**

The ProGear Inventory MCP authorization server already has custom claims:

| Claim Name | Value | Type | Included |
|------------|-------|------|----------|
| `sub` | `(appuser != null) ? appuser.userName : app.clientId` | access | Always |
| `Vacation` | `user.is_on_vacation` | access | Always |
| `Manager` | `user.is_a_manager` | access | Always |

These appear in the **access token after token exchange** — but the FGA check runs BEFORE token exchange. So you need vacation status from the user's **initial ID token** too.

**To get vacation status before token exchange:**

1. Add the same claim to your **Org Authorization Server** (or whichever auth server issues the user's initial ID token):
   - Okta Admin → Security → API → Org Authorization Server → Claims → **Add Claim**
   - Name: `is_on_vacation`, Value: `user.is_on_vacation`, Include in: ID Token (Always)
2. The backend already decodes the ID token in `main.py` (line 165) — add it to `user_info`:
   ```python
   "is_on_vacation": user_claims.get("is_on_vacation", False),
   ```
3. The `_fga_check_node` reads it from `self.user_info.get("is_on_vacation", False)` — already wired above

**Alternative for quick testing:** Hardcode `is_on_vacation = True` in the node to skip the claim setup.

**Defense in depth:** After FGA allows and token exchange succeeds, the Inventory MCP access token ALSO carries the `Vacation` and `Manager` claims. So authorization is enforced at two layers:
1. **FGA gatekeeper** (pre-exchange): blocks the agent invocation entirely
2. **Access token claims** (post-exchange): the MCP server can also verify these claims on its side

### 5c. Wire the new node into `_build_workflow`:

Change the workflow from:
```python
workflow.set_entry_point("router")
workflow.add_edge("router", "exchange_tokens")
```

To:
```python
workflow.add_node("fga_check", self._fga_check_node)

workflow.set_entry_point("router")
workflow.add_edge("router", "fga_check")
workflow.add_edge("fga_check", "exchange_tokens")
```

---

## Step 6: Pass `user_info["sub"]` Through the Flow

The orchestrator already receives `user_info` in `__init__`, and `user_info` contains `sub` from the token claims (set in `main.py` line 167). No changes needed here — the `_fga_check_node` accesses it via `self.user_info.get("sub")`.

---

## Verification

### Local testing:

1. Set FGA env vars in `.env`
2. Run the seed script: `cd backend && python -m auth.fga_seed`
3. Start the backend: `cd backend && uvicorn api.main:app --reload`
4. Log in as a Warehouse manager user → ask "check inventory" → should work (manager, not on vacation)
5. Set `is_on_vacation = True` in the `_fga_check_node` (or via your chosen method) → ask "add 500 basketballs" → should be **denied** by FGA
6. Check the UI's Token Exchange card — FGA-denied agents should show "denied" with the vacation reason

### Demo scenario to show:

1. **Warehouse manager (not on vacation)**: "What's our basketball inventory?" → Inventory MCP granted, data returned
2. **Warehouse manager (on vacation)**: "Increase basketball stock by 500" → FGA denies `can_increase_inventory` because `check_vacation` fails → UI shows denied with reason
3. **Sales user**: Any query → inventory passes through FGA (no model for sales agents yet), Okta RBAC still applies

### Verify FGA is working:

- In backend logs, look for: `FGA check: user:xxx manager inventory_system:main_db (vacation=False) → True`
- If FGA env vars are missing, logs will show: `FGA not configured — skipping fine-grained checks`
- The Okta RBAC layer still runs after FGA, so both layers must allow access

### Dashboard verification:

- Go to `dashboard.fga.dev` → your ProGear store → Tuple Explorer
- Verify your relationship tuples are present (user → manager → inventory_system:main_db)
- Use the "Check" tab to test: `user:xxx manager inventory_system:main_db` with context `{"is_on_vacation": false}` → should return allowed
- Same check with `{"is_on_vacation": true}` → should return denied

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `.env` / `.env.example` | Edit | Uncomment and fill FGA env vars |
| `backend/auth/fga_client.py` | **New** | FGA client singleton + check functions |
| `backend/auth/fga_seed.py` | **New** | Script to seed relationship tuples |
| `backend/orchestrator/orchestrator.py` | Edit | Add `fga_check` node between router and token exchange |

No frontend changes needed — the existing Token Exchange UI card already renders denied agents correctly.

---

## Before You Start: Clarifying Questions

Answer these before implementing. You can get most of this from the Auth0 FGA dashboard and Okta admin console.

### FGA Credentials (from dashboard.fga.dev)
1. **Do you have FGA API credentials?** Go to `dashboard.fga.dev` → your ProGear store → Settings → API Keys. You need:
   - `FGA_CLIENT_ID` — the client ID for programmatic access
   - `FGA_CLIENT_SECRET` — the client secret
   - If you don't have API keys yet, create one under Settings → API Keys → "Create API Key"

2. **Which FGA API region are you using?** The store above is US (`api.us1.fga.dev`). If you created a different store in EU, use `api.eu1.fga.dev` instead. The token issuer also changes: `fga.us.auth0.com` (US) vs `fga.eu.auth0.com` (EU).

3. **Do you want to use the existing Model ID (`01KNSR8FRB0CMMN79ZT1M2E9S5`) or write a new model?** If the existing model already has the right types/relations, just use it. If not, you'll write the model from Step 2 and get a new Model ID.

### User-to-Agent Mapping (from Okta admin console)
4. **FGA user IDs use email format** (e.g., `user:mike.manager@atko.email`). If you add more users, make sure the FGA tuple user matches this format. The Okta internal ID (`00uushw94qlX4GcTG1d7`) is NOT what FGA uses.

5. **Is `is_on_vacation` a claim on your Org Authorization Server's ID token?** It's already on the Inventory MCP auth server (access token), but FGA needs it BEFORE token exchange. Check if the **Org Auth Server** also includes `is_on_vacation` in the ID token. If not, add it:
   - Security → API → Org Authorization Server → Claims → Add Claim
   - Name: `is_on_vacation`, Value: `user.is_on_vacation`, Include in: ID Token (Always)

6. **Do you plan to extend the FGA model to other agents?** The current model only covers `inventory_system`. If you want FGA gating on Sales/Customer/Pricing agents too, you'll need to add types to the model and update `AGENT_TO_FGA_OBJECT` in `fga_client.py`.

### Deployment
6. **Have you added FGA env vars to Render?** The backend runs on Render. Go to Render dashboard → your service → Environment → add all `FGA_*` variables. The frontend (Vercel) does NOT need FGA vars — all FGA checks happen server-side.

---

## Notes for the Person Forking

- The `openfga-sdk==0.9.7` is already in `requirements.txt` — no pip install needed
- FGA is a **runtime gatekeeper** — it doesn't replace Okta RBAC, it layers on top. Both must allow access. FGA runs first (cheaper), Okta token exchange runs second.
- The integration is **fail-open** by design. If FGA is down or misconfigured, Okta RBAC still protects. The demo won't break.
- User IDs in FGA tuples must match the Okta `sub` claim exactly. Find these in your Okta admin console under Directory → People → select user → look at `sub` or the user ID.
- The `check_vacation` condition is evaluated at **check time**, not when tuples are written. This is the power of FGA conditions — the tuple says "this user is a manager", the condition says "but only if they're not on vacation right now."
- This app is live on Vercel (frontend) and Render (backend). Add FGA env vars to Render before deploying.
- The model currently only covers `inventory_system`. To extend to other agents, add types to the FGA model and update `AGENT_TO_FGA_OBJECT` in `fga_client.py`.
