# Inventory role levels and approval routing

`clearance_level` is the single source of truth for the ProGear inventory role. It is no longer an item-sensitivity score and it is not combined with a separate Manager switch.

| Okta value | Role | Read inventory | Write 1–600 units | Write 601+ units |
|---:|---|---|---|---|
| 1 | Sales | Execute | Manager approval | VP approval |
| 2 | Manager | Execute | Execute | VP approval |
| 3 | VP | Execute | Execute | Execute |

`is_on_vacation=true` blocks every inventory write. It does not block reads and it does not create an approval request.

## End-to-end decision

1. Okta authenticates the user and the Inventory Custom Authorization Server signs `Clearance` (`user.clearance_level`) and `Vacation` (`user.is_on_vacation`) into the access token.
2. The backend maps the live `Clearance` value to one contextual FGA relationship: `role_sales`, `role_manager`, or `role_vp`.
3. Quantity selects the FGA permission: `can_update_standard` for 1–600, or `can_update_large` for 601+.
4. If the user's level can execute, the write proceeds. If a higher level is required, the backend creates an Okta Identity Governance request for that level. Vacation is a hard denial.
5. After OIG approval, the backend looks up the approver in Okta and verifies their current `clearance_level` before executing. A Level 2 approver can satisfy a Manager request; only Level 3 can satisfy a VP request.

## Live Okta configuration

- Custom profile property: `clearance_level`, titled **ProGear role level**.
- Access-token claim: `Clearance = user.clearance_level`.
- Compatibility claim: `Manager = clearance_level is 2 or 3`; application authorization does not depend on this claim.
- `ProGear-Managers` membership rule: level 2 or 3.
- `ProGear-VPs` membership rule: level 3.
- Demo personas: Sarah Sales = Level 1, Mike Manager = Level 2, and Joe VP = Level 3; vacation defaults to false. Joe also belongs to `ProGear-Warehouse` so the Inventory authorization server can issue the coarse inventory scopes before FGA evaluates his VP level.
- The Sales inventory authorization-server rule grants `inventory:read` and `inventory:write`. The write scope only lets the request reach the FGA layer; it does not itself authorize direct execution.

The demo starts with **Simulate FGA** off. That browser-local preference shows only two everyday examples—Sarah's read and Mike's normal write—and hides the role/vacation controls. Enabling it replaces those examples with the three FGA tiers and reveals the advanced controls; changing the preference does not itself mutate Okta. In simple mode, the backend still applies the Okta-signed role and vacation context, but a request that needs a higher role is denied instead of being sent to FGA/OIG. This makes the switch safe: turning simulation off can never bypass the Manager/VP execution boundary. Once enabled, the controls may only change the signed-in user's `clearance_level` and `is_on_vacation`. They validate the role as 1, 2, or 3. Reset restores that persona's starting role and always sets vacation to false.

## Auth0 FGA model

The version-controlled model is [`backend/auth/fga_role_model.json`](../backend/auth/fga_role_model.json).

```text
can_read            = Sales or Manager or VP
can_request_change  = active Sales or active Manager or active VP
can_update_standard = active Manager or active VP
can_update_large    = active VP

active role = role but not on_vacation
```

Role and vacation tuples are contextual: they are derived from the signed Okta token for that check and are not left behind as mutable role copies in the FGA store.

## Deterministic demo prompts

These prompts replace the two everyday examples after **Simulate FGA** is enabled on `/fga`:

1. `How many basketballs are in stock?`
2. `Add 50 basketballs to inventory`
3. `Add 601 basketballs to inventory`

For Sarah's default Level 1, prompt 1 reads successfully, prompt 2 creates a Manager request, and prompt 3 creates a VP request. For Mike's default Level 2, prompt 2 executes while prompt 3 creates a VP request. At Level 3, all three execute unless vacation is true.

## Deployment values

All backends that serve this frontend must use the same `FGA_STORE_ID` and the current `FGA_MODEL_ID`. The approval backends also need the live OIG request type and justification field IDs, plus:

```text
APPROVAL_QUANTITY_THRESHOLD=601
OKTA_MANAGER_APPROVER_GROUP_NAME=ProGear-Managers
OKTA_VP_APPROVER_GROUP_NAME=ProGear-VPs
```

The policy decision itself uses the fixed 600/601 boundary in `backend/auth/inventory_policy.py`; the threshold environment value remains aligned for compatibility with older approval-service callers.
