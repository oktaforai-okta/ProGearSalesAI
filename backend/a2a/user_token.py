"""Verification for the coordinator-bound user access token."""

from __future__ import annotations

import os
from typing import Any, Sequence

import jwt

from .models import A2AAccessDenied


class A2AUserTokenVerifier:
    """Verify the browser's Custom-AS token before forwarding it to the mesh."""

    def __init__(
        self,
        *,
        issuer: str | None = None,
        audience: str | None = None,
        required_scopes: Sequence[str] = ("agent.invoke",),
        jwks_client: Any | None = None,
    ) -> None:
        self.issuer = (issuer or os.getenv("A2A_USER_ISSUER", "")).rstrip("/")
        self.audience = audience or os.getenv("A2A_COORDINATOR_RESOURCE", "")
        self.required_scopes = tuple(required_scopes)
        if not self.issuer or not self.audience:
            raise A2AAccessDenied(
                "session_auth",
                "A2A user issuer and coordinator audience must be configured",
            )
        self._jwks = jwks_client or jwt.PyJWKClient(f"{self.issuer}/v1/keys")

    def verify(self, token: str) -> dict[str, Any]:
        if not token:
            raise A2AAccessDenied("session_auth", "A delegated user access token is required")
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.PyJWTError as exc:
            raise A2AAccessDenied("session_auth", "A2A user access token was rejected") from exc

        held = _scopes(claims)
        missing = sorted(set(self.required_scopes) - set(held))
        if missing:
            raise A2AAccessDenied(
                "session_auth",
                f"A2A user access token is missing required scopes: {missing}",
            )
        return claims


def _scopes(claims: dict[str, Any]) -> tuple[str, ...]:
    value = claims.get("scp", claims.get("scope", ()))
    if isinstance(value, str):
        return tuple(value.split())
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


