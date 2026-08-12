# Inventory roles, delegation context, and AI Agent Owner approval

`clearance_level` is the authoritative source for the ProGear inventory role. It is a role—not item sensitivity. `is_a_manager` is a synchronized profile fact derived from that role, not an independent authorization switch. `is_on_vacation` answers a different question: whether the agent may act for the employee at all.

| Okta value | Role | Manager | Read inventory | Write 1–600 units | Write 601+ units |
|---:|---|---|---|---|---|
| 0 | Sales | False | Execute | Deny; contact manager | Deny; contact manager |
| 1 | Manager | True | Execute | Execute | Execute with FGA off; AI Agent Owner approval with FGA on |
| 2 | VP | True | Execute | Execute | Execute |

The table assumes **On vacation = False**. When **On vacation = True**, the agent stops before ID-JAG for every role, resource, read, and write. This contains delegated access when an employee is away or their credentials may have been exposed. It does not change the employee's job role.

Sarah never creates an access request. She asks her manager to make the change. The only OIG escalation in this demo is Mike, as a Manager, requesting more than 600 units from the owners of the governed AI agent.

Those names are demo personas, not application rules. The backend looks up the authenticated user's live Okta profile by immutable subject (`sub`), never by email or name. Any newly onboarded employee with `clearance_level` 0 behaves as Sales, Level 1 behaves as Manager, and Level 2 behaves as VP. A genuinely missing or invalid value is denied as an unassigned role; a failed Okta profile lookup is reported separately and fails closed.

## End-to-end decision

1. Okta authenticates the employee; the backend reads `clearance_level`, `is_a_manager`, and `is_on_vacation` from the live Okta profile.
2. If vacation is true, delegation stops globally. The verified sign-in remains visible, but no ID-JAG or resource token is requested.
3. Otherwise, a known-ineligible inventory write stops immediately. Sarah is told to contact her manager, and no ID-JAG is requested for that stopped domain. Eligible Manager and VP writes continue regardless of quantity when FGA is off.
4. For a request allowed to continue, ID-JAG carries the employee + agent delegation to the Inventory Authorization Server.
5. The server issues a coarse, scoped Inventory token and signs the live `Clearance`, `Manager`, and `Vacation` profile claims into it.
6. Inventory independently validates the token signature, issuer, audience, expiry, agent identity, delegated employee, and required scope.
7. Simple mode executes a valid positive-quantity write when the resource token contains `inventory:write`; it does not apply the 600/601 boundary. Production FGA maps the validated `Clearance` value to one contextual relationship—`role_sales`, `role_manager`, or `role_vp`—and combines it with the requested quantity. The hosted presentation keeps Sarah fixed as Sales. A live Manager may preview Manager or VP outcomes through a server-side overlay isolated to that browser tab; the overlay cannot manufacture an Okta scope.
8. The resource mutates inventory only when the final decision is `allow`. Before creating an owner request, the backend proves that it can mint and validate the real execution token; a broken execution path cannot create a theatrical approval card.
9. A Manager request above 600 is left unchanged while the OIG request is pending. The approver sees only the requester, requested change, 600-unit threshold reason, required AI Agent Owner authority, and governed-agent label; internal execution JSON is not shown in the request card. After approval, the backend loads the exact intent from its ledger, verifies that the approver is currently in `AIAgentOwners`, mints and validates a fresh scoped Okta service token for the approval executor, and guards against duplicate execution in the application ledger. The current MCP tool doesn't accept an idempotency key, so production exactly-once delivery requires a downstream transaction key. Older open VP-routed requests remain compatible.

Token issuance is necessary, not sufficient—but a token is not requested when the answer is already known. Sarah's live Level 0 profile stops an inventory write before ID-JAG exchange, and her `ProGear-Sales` authorization-server rule cannot issue `inventory:write` in any case. Eligible Manager and VP requests continue to delegated token exchange; the resource and FGA layers can still deny or route the action after a scoped token is issued.

## Live Okta configuration

- Custom profile property: `clearance_level`, titled **Clearance level**.
- Custom profile property: `is_a_manager`, titled **Manager**, synchronized to False for Level 0 and True for Levels 1–2.
- Custom profile property: `is_on_vacation`, titled **On vacation**, default False.
- Access-token claims: `Clearance = user.clearance_level`, `Manager = user.is_a_manager`, and `Vacation = user.is_on_vacation`.
- Core personas: Sarah Sales = Level 0 and Mike Manager = Level 1. Mike's isolated FGA control can preview Level 2 without changing the shared profile.
- `ProGear-Managers` contains Managers and VPs as appropriate for ordinary administration.
- `AIAgentOwners` contains the people authorized to approve Manager requests above 600.
- Assign the Okta Access Requests app to the presenters, push `AIAgentOwners` into Access Requests, and assign the request type's approval task to that pushed group. Any current owner can receive the task; the requester is still Mike.
- Inventory authorization-server rules are fixed by role: `ProGear-Sales` receives only `inventory:read`; `ProGear-Managers` and `ProGear-VPs` receive `inventory:read` and `inventory:write`.
- A separate five-minute `client_credentials` rule permits only the dedicated ProGear Approval Executor service client to execute an already-approved inventory write. The application preflights and validates that token before it creates the OIG request; the AI Agent workload principal continues to handle delegated user exchanges.
- A separate MCP Bridge demonstration, when used, has its own authorization server named **MCP Bridge - ProGear Inventory Write MCP**. It is not part of the hosted Vercel/FastAPI native MCP path.

The demo starts with **Simulate FGA** off. That browser-tab preference shows two everyday examples and hides the advanced controls. A random ID in `sessionStorage` isolates the preference, role preview, and vacation demonstration to that tab. Refreshing or signing out preserves the choice; closing the tab ends the browser session, and a fresh tab starts in simple mode. In simple mode, Sales writes are denied, while Manager and VP writes with a validated `inventory:write` token may execute any positive quantity; no OIG request is created. Enabling FGA reveals the Read, 1–600, and 601+ prompt tiers. Sarah cannot elevate. Mike starts as Manager and can compare Manager and VP outcomes; Manager 601+ routes to `AIAgentOwners`, while the VP preview executes directly. The On vacation True/False control demonstrates the global delegation stop, and Reset restores that session's starting role and vacation value.

The role and vacation controls are intentionally demo-only and never mutate the live Okta profile. The backend keys them by authenticated employee plus browser tab, so two engineers using the same persona do not share state. Only a live Manager can compare Manager and VP; Sales cannot elevate. In production, keep role, Manager, and vacation attributes administrator- or lifecycle-managed so an employee session—and therefore stolen employee credentials—cannot clear the containment signal.

## FGA model

The version-controlled model is [`backend/auth/fga_role_model.json`](../backend/auth/fga_role_model.json).

```text
can_read            = Sales or Manager or VP
can_request_change  = Manager
can_update_standard = Manager or VP
can_update_large    = VP
```

The role tuple is contextual: it is derived from the validated Okta Inventory token for the current check and is not persisted as a second mutable role copy in FGA. Vacation is intentionally enforced before FGA because it controls whether delegation may begin, not which inventory relation a role satisfies.

## Deterministic demo prompts

These prompts replace the two everyday examples after **Simulate FGA** is enabled on `/fga`:

1. `How many basketballs are in stock?`
2. `Add 50 basketballs to inventory`
3. `Add 601 basketballs to inventory`

- Sarah (Level 0): prompt 1 executes; prompts 2 and 3 are blocked without creating requests.
- Mike as Manager (Level 1): prompts 1 and 2 execute; prompt 3 creates one `AIAgentOwners` request and does not change inventory while pending.
- Mike's VP preview (Level 2): all three execute directly. The approval authority remains the separate `AIAgentOwners` group.

## Deployment values

Every backend serving this frontend must use the same `FGA_STORE_ID` and active `FGA_MODEL_ID`. The approval backend also needs the live OIG request type and justification field IDs, plus:

```text
APPROVAL_QUANTITY_THRESHOLD=601
OKTA_APPROVER_GROUP_NAME=AIAgentOwners
APPROVAL_STATUS_CACHE_TTL_SECONDS=8
```

The fixed 600/601 boundary is implemented in `backend/auth/inventory_policy.py` and covered by the backend policy test suite.
