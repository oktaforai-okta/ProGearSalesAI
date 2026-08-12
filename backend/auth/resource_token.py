"""Resource-server validation for tokens presented to ProGear domains.

Token exchange answers whether Okta will issue a coarse, scoped token.  It
does not by itself authorize a business action.  Before a domain reads or
mutates data, this module verifies the resource token's signature, issuer,
audience, expiry, scopes, governed-agent identity, and delegated user.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

import httpx
from jose import JWTError, jwt

from .agent_config import get_agent_config
from mcp.client import MCPDiscoveryError, get_mcp_client

logger = logging.getLogger(__name__)


class ResourceTokenError(ValueError):
    """Raised when a resource token cannot be trusted for the requested call."""


@dataclass(frozen=True)
class ValidatedResourceToken:
    claims: dict[str, Any]
    issuer: str
    audience: str
    scopes: tuple[str, ...]
    agent_id: str
    key_id: str


def _scope_set(claims: dict[str, Any]) -> set[str]:
    value = claims.get("scp", claims.get("scope", []))
    if isinstance(value, str):
        return {item for item in value.split() if item}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()


def _normalize_domain(value: str) -> str:
    value = value.strip().rstrip("/")
    if value and not value.startswith("http"):
        value = f"https://{value}"
    return value


class ResourceTokenValidator:
    """Validate Custom Authorization Server tokens with cached Okta JWKS."""

    def __init__(self, *, cache_ttl_seconds: int = 900):
        self._cache_ttl = cache_ttl_seconds
        self._jwks_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def _get_keys(self, issuer: str, *, refresh: bool = False) -> list[dict[str, Any]]:
        now = time.monotonic()
        cached = self._jwks_cache.get(issuer)
        if not refresh and cached and now - cached[0] < self._cache_ttl:
            return cached[1]

        async with self._lock:
            cached = self._jwks_cache.get(issuer)
            if not refresh and cached and now - cached[0] < self._cache_ttl:
                return cached[1]
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{issuer}/v1/keys", timeout=10.0)
                response.raise_for_status()
            keys = response.json().get("keys") or []
            if not keys:
                raise ResourceTokenError("The authorization server returned no signing keys.")
            self._jwks_cache[issuer] = (time.monotonic(), keys)
            return keys

    @staticmethod
    def _select_key(keys: list[dict[str, Any]], kid: str) -> dict[str, Any] | None:
        return next((key for key in keys if key.get("kid") == kid), None)

    async def validate(
        self,
        token: str,
        *,
        agent_type: str,
        required_scopes: Iterable[str],
        expected_subjects: Iterable[str] = (),
        expected_client_ids: Iterable[str] | None = None,
    ) -> ValidatedResourceToken:
        config = get_agent_config(agent_type)
        domain = _normalize_domain(os.getenv("OKTA_DOMAIN", ""))
        if not config or not domain or not config.mcp_url or not config.agent_id:
            raise ResourceTokenError(f"{agent_type} resource validation is not configured.")
        if not token or token.startswith("demo-") or token.startswith("service-token-placeholder"):
            raise ResourceTokenError("A real signed resource token is required.")

        try:
            metadata = await get_mcp_client().discover(
                config.mcp_url,
                required_scopes=required_scopes,
            )
            issuer = metadata.authorization_server_for(domain)
        except MCPDiscoveryError as exc:
            raise ResourceTokenError(
                f"The {agent_type} MCP authorization metadata could not be trusted: {exc}"
            ) from exc
        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise ResourceTokenError("The resource token header is invalid.") from exc
        kid = str(header.get("kid") or "")
        if not kid:
            raise ResourceTokenError("The resource token has no signing key id.")

        keys = await self._get_keys(issuer)
        key = self._select_key(keys, kid)
        if key is None:
            keys = await self._get_keys(issuer, refresh=True)
            key = self._select_key(keys, kid)
        if key is None:
            raise ResourceTokenError("The resource token signing key is unknown.")

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=issuer,
                audience=config.audience,
                options={"verify_at_hash": False},
            )
        except JWTError as exc:
            raise ResourceTokenError(f"Resource token verification failed: {exc}") from exc

        granted_scopes = _scope_set(claims)
        missing_scopes = set(required_scopes) - granted_scopes
        if missing_scopes:
            raise ResourceTokenError(
                f"Resource token is missing scope(s): {', '.join(sorted(missing_scopes))}."
            )

        actor = claims.get("act") if isinstance(claims.get("act"), dict) else {}
        represented_client_ids = {
            str(value)
            for value in (claims.get("cid"), claims.get("sub"), actor.get("sub"))
            if value
        }
        trusted_client_ids = (
            {str(value) for value in expected_client_ids if value}
            if expected_client_ids is not None
            else {config.agent_id}
        )
        if not trusted_client_ids or trusted_client_ids.isdisjoint(represented_client_ids):
            raise ResourceTokenError("The token was not issued to a trusted ProGear client.")

        expected = {str(value).lower() for value in expected_subjects if value}
        if expected:
            represented_users = {
                str(value).lower()
                for value in (claims.get("sub"), claims.get("uid"))
                if value
            }
            if expected.isdisjoint(represented_users):
                raise ResourceTokenError("The delegated user in the token does not match the request.")

        logger.info(
            "Validated %s resource token: kid=%s jti=%s scopes=%s",
            agent_type,
            kid,
            claims.get("jti"),
            sorted(granted_scopes),
        )
        return ValidatedResourceToken(
            claims=claims,
            issuer=issuer,
            audience=config.audience,
            scopes=tuple(sorted(granted_scopes)),
            agent_id=next(iter(trusted_client_ids & represented_client_ids)),
            key_id=kid,
        )


_validator: ResourceTokenValidator | None = None


def get_resource_token_validator() -> ResourceTokenValidator:
    global _validator
    if _validator is None:
        _validator = ResourceTokenValidator()
    return _validator
