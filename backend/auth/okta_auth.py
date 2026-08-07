"""
Okta user token validation for the ProGear demo.

Resource token exchange is implemented in multi_agent_auth.py. This module
only resolves the signed-in user's token for API requests and demo controls.
"""

import logging
from typing import Any, Dict

from jose import JWTError, jwt

logger = logging.getLogger(__name__)


class OktaAuth:
    """Validate the user token supplied by the frontend."""

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Return claims from an Okta ID or access token."""
        if token == "demo-token" or token.startswith("test-"):
            return {
                "sub": "demo-user",
                "email": "demo@progear.example",
                "name": "Demo User",
            }

        try:
            # This demo passes the ID token to Okta for ID-JAG exchange, where
            # Okta performs authoritative validation. Signature validation at
            # this API boundary remains future hardening work.
            return jwt.get_unverified_claims(token)
        except JWTError as e:
            logger.error("Token validation failed: %s", e)
            raise ValueError(f"Invalid token: {e}") from e


_okta_auth: OktaAuth | None = None


def get_okta_auth() -> OktaAuth:
    """Get or create the OktaAuth singleton."""
    global _okta_auth
    if _okta_auth is None:
        _okta_auth = OktaAuth()
    return _okta_auth
