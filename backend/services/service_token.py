"""Service-token minter for the OIG approval flow.

When an OIG Access Request is resolved long after the original user
session has expired, the ApprovalService executes the inventory write
under a service identity rather than the (now-gone) user token. In
production this would be an Okta client_credentials exchange signed
with OKTA_AI_AGENT_PRIVATE_KEY. For the current demo the token value
is only ever logged for audit — it is never presented to a live API —
so we return a self-describing placeholder. Replace this implementation
with a real token-minting function once the production flow is wired.
"""
from __future__ import annotations

import os


async def mint_service_token(scope: str) -> str:
    """Return a placeholder service-token string that identifies the agent + scope.

    Intentionally synchronous-friendly: returns an awaitable string so
    ApprovalService can `await self._mint_token(scope)` unchanged. The
    string includes the agent id so audit logs show *who* the service
    identity belongs to.
    """
    agent_id = os.getenv("OKTA_AI_AGENT_ID", "ai-agent")
    return f"service-token-placeholder:agent={agent_id}:scope={scope}"
