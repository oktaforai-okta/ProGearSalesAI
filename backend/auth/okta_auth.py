"""Validate the signed-in employee token at the ProGear API boundary."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from jose import JWTError, jwt

logger = logging.getLogger(__name__)


def _normalize_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if value and not value.startswith("http"):
        value = f"https://{value}"
    return value


class OktaAuth:
    """Validate the Okta ID token supplied by the frontend."""

    def __init__(self):
        domain = _normalize_url(os.getenv("OKTA_DOMAIN", ""))
        self.issuer = _normalize_url(os.getenv("OKTA_ISSUER", domain))
        self.audience = (
            os.getenv("OKTA_CLIENT_ID", "").strip()
            or os.getenv("OKTA_AI_AGENT_ID", "").strip()
        )
        # Okta's org authorization server exposes client-specific ID-token
        # keys. Custom authorization servers expose their keys below the
        # issuer. The browser uses the same distinction in lib/auth.ts.
        if "/oauth2/" in self.issuer:
            self.jwks_uri = f"{self.issuer}/v1/keys"
        else:
            self.jwks_uri = (
                f"{self.issuer}/oauth2/v1/keys?client_id={self.audience}"
            )
        self._keys: list[dict[str, Any]] | None = None

    async def _load_keys(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._keys is not None and not refresh:
            return self._keys
        async with httpx.AsyncClient() as client:
            response = await client.get(self.jwks_uri, timeout=10.0)
            response.raise_for_status()
        self._keys = response.json().get("keys") or []
        if not self._keys:
            raise ValueError("Okta returned no ID-token signing keys.")
        return self._keys

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Verify signature, issuer, audience, and lifetime; then return claims."""
        if token == "demo-token" or token.startswith("test-"):
            if os.getenv("ALLOW_DEMO_TOKENS", "").lower() != "true":
                raise ValueError("Demo tokens are disabled.")
            return {
                "sub": "demo-user",
                "email": "demo@progear.example",
                "name": "Demo User",
            }
        if not self.issuer or not self.audience:
            raise ValueError("Okta ID-token validation is not configured.")

        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise ValueError("Token is missing a signing key id.")
            keys = await self._load_keys()
            key = next((item for item in keys if item.get("kid") == kid), None)
            if key is None:
                keys = await self._load_keys(refresh=True)
                key = next((item for item in keys if item.get("kid") == kid), None)
            if key is None:
                raise ValueError("Token signing key is unknown.")
            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"verify_at_hash": False},
            )
        except (JWTError, httpx.HTTPError, ValueError) as exc:
            logger.warning("ID token validation failed: %s", exc)
            raise ValueError(f"Invalid token: {exc}") from exc


_okta_auth: OktaAuth | None = None


def get_okta_auth() -> OktaAuth:
    """Get or create the OktaAuth singleton."""
    global _okta_auth
    if _okta_auth is None:
        _okta_auth = OktaAuth()
    return _okta_auth
