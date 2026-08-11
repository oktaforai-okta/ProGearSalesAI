# Inventory role levels and VP approval routing

`clearance_level` is the single source of truth for the ProGear inventory role. It is a role—not item sensitivity—and it is not combined with a Manager Boolean.

| Okta value | Role | Read inventory | Write 1–600 units | Write 601+ units |
|---:|---|---|---|---|
| 0 | Sales | Execute | Deny; contact manager | Deny; contact manager |
| 1 | Manager | Execute | Execute | VP approval with FGA on; deny in simple mode |
| 2 | VP | Execute | Execute | Execute |

Sarah never creates an access request. She asks her manager to make the change. The only OIG escalation in this demo is Mike, as a Manager, requesting more than 600 units from a VP.

Those names are demo personas, not application rules. The backend looks up the authenticated user's live Okta profile by immutable subject (`sub`), never by email or name. Any newly onboarded employee with `clearance_level` 0 behaves as Sales, Level 1 behaves as Manager, and Level 2 behaves as VP. A genuinely missing or invalid value is denied as an unassigned role; a failed Okta profile lookup is reported separately and fails closed.

## End-to-end decision

1. Okta authenticates the employee; the backend reads that employee's current `clearance_level` from the live Okta profile.
2. A known-ineligible inventory write stops immediately. Sarah is told to contact her manager; in simple mode Mike is told to contact a VP for 601+ units. No ID-JAG is requested for that stopped domain.
3. For a request allowed to continue, ID-JAG carries the employee + agent delegation to the Inventory Authorization Server.
4. The server issues a coarse, scoped Inventory token and signs `Clearance = user.clearance_level` into it.
5. Inventory independently validates the token signature, issuer, audience, expiry, agent identity, delegated employee, and required scope.
6. Simple mode executes only a direct allow. FGA mode maps the validated `Clearance` value to one contextual relationship—`role_sales`, `role_manager`, or `role_vp`—and combines it with the requested quantity.
7. The resource mutates inventory only when the final decision is `allow`. Before creating a VP request, the backend proves that it can mint and validate the real execution token; a broken execution path cannot create a theatrical approval card.
8. A Manager request above 600 is left unchanged while the VP OIG request is pending. The approver sees only the requester, requested change, 600-unit threshold reason, required VP level, and governed-agent label; internal execution JSON is not shown in the request card. After approval, the backend loads the exact intent from its ledger, verifies that the approver currently has Level 2 in Okta, mints and validates a fresh scoped Okta service token for the approval executor, and performs the write once using the request ID as an idempotency key. Older open requests with embedded intent remain compatible.

Token issuance is necessary, not sufficient—but a token is not requested when the answer is already known. Sarah's live Level 0 profile stops an inventory write before ID-JAG exchange and the token page explains that she must contact her manager. Eligible requests continue to delegated token exchange; the resource and FGA layers can still deny or route the action after a scoped token is issued.

## Live Okta configuration

- Custom profile property: `clearance_level`, titled **Clearance level**.
- Access-token claim: `Clearance = user.clearance_level`.
- Demo personas: Sarah Sales = Level 0, Mike Manager = Level 1, Joe VP = Level 2.
- `ProGear-Managers` contains Managers and VPs as appropriate for ordinary administration.
- `ProGear-VPs` contains the eligible approvers for Manager requests above 600.
- Assign the Okta Access Requests app to `ProGear-Managers` and `ProGear-VPs`, push `ProGear-VPs` into Access Requests, and assign the request type's approval task to that pushed group. This makes the route dynamic: any current Level 2 member can receive the task.
- The Inventory authorization-server rule may issue `inventory:read` and `inventory:write` to the demo personas. The write scope is a coarse resource capability, not direct permission to change inventory.
- A separate five-minute `client_credentials` rule permits only the dedicated ProGear Approval Executor service client to execute an already-approved inventory write. The application preflights and validates that token before it creates the OIG request; the AI Agent workload principal continues to handle delegated user exchanges.

The demo starts with **Simulate FGA** off. That browser-local preference shows two everyday examples and hides the advanced role control. In simple mode, Sales writes and Manager writes above 600 are denied; no OIG request is created. Enabling FGA reveals the Read, 1–600, and 601+ prompt tiers and allows the one escalation path from Manager to VP. The control may change only the signed-in user's `clearance_level` to 0, 1, or 2. Reset restores that persona's starting role.

## FGA model

The version-controlled model is [`backend/auth/fga_role_model.json`](../backend/auth/fga_role_model.json).

```text
can_read            = Sales or Manager or VP
can_request_change  = Manager
can_update_standard = Manager or VP
can_update_large    = VP
```

The role tuple is contextual: it is derived from the validated Okta Inventory token for the current check and is not persisted as a second mutable role copy in FGA.

## Deterministic demo prompts

These prompts replace the two everyday examples after **Simulate FGA** is enabled on `/fga`:

1. `How many basketballs are in stock?`
2. `Add 50 basketballs to inventory`
3. `Add 601 basketballs to inventory`

- Sarah (Level 0): prompt 1 executes; prompts 2 and 3 are blocked without creating requests.
- Mike (Level 1): prompts 1 and 2 execute; prompt 3 creates one VP request and does not change inventory while pending.
- Joe (Level 2): all three execute directly.

## Deployment values

Every backend serving this frontend must use the same `FGA_STORE_ID` and active `FGA_MODEL_ID`. The approval backend also needs the live OIG request type and justification field IDs, plus:

```text
APPROVAL_QUANTITY_THRESHOLD=601
OKTA_VP_APPROVER_GROUP_NAME=ProGear-VPs
APPROVAL_STATUS_CACHE_TTL_SECONDS=8
```

The fixed 600/601 boundary is implemented in `backend/auth/inventory_policy.py` and covered by the backend policy test suite.
