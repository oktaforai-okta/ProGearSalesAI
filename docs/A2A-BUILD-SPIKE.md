# A2A Build Spike (Do Not Merge)

This branch preserves exploratory implementation work created before the project scope was clarified.
The current phase is **planning only**. This branch is not the approved architecture, is not deployed,
and must not be merged as the implementation source of truth.

Reusable findings:

- ProGear can keep its current UI while feature-gating a typed Google → AWS → Google workflow.
- A coordinator response needs explicit `outputs[target]` objects; answer prose is not mutation evidence.
- The coordinator-bound Custom Authorization Server access token must be resource-bound at both the
  authorization and token requests.
- The browser can display a token-free registry and execution trace without receiving ID-JAGs, target
  tokens, workload keys, or secrets.
- A receipt mismatch or Inventory denial must prevent Customer notification.

The approved build sequence, contracts, access questions, and acceptance criteria belong in the
`oktaforai-okta/progear-a2a` planning repository.
