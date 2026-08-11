"""Mint a real Okta service token for an approved inventory write.

An OIG approval can complete after the requester's browser session expires.
The approved action therefore executes through a dedicated, least-privilege
OAuth service client using client credentials authenticated with
``private_key_jwt``. The governed AI Agent remains the actor for delegated user
requests; the service client is only the post-approval executor.
"""

from __future__ import annotations

import json
import os
import time
import uuid

import httpx
from jose import jwt

from auth.agent_config import AGENT_INVENTORY, get_agent_config


def _private_key() -> dict:
    raw = os.getenv("OKTA_APPROVAL_EXECUTOR_PRIVATE_KEY", "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("OKTA_APPROVAL_EXECUTOR_PRIVATE_KEY must be valid JWK JSON.") from exc
    if not isinstance(value, dict):
        raise RuntimeError("OKTA_APPROVAL_EXECUTOR_PRIVATE_KEY must be a JWK object.")
    return value


def _okta_domain() -> str:
    value = os.getenv("OKTA_DOMAIN", "").strip().rstrip("/")
    if value and not value.startswith("http"):
        value = f"https://{value}"
    return value


async def mint_service_token(scope: str) -> str:
    """Mint a signed, scoped Inventory token for the approval executor."""
    config = get_agent_config(AGENT_INVENTORY)
    domain = _okta_domain()
    client_id = os.getenv("OKTA_APPROVAL_EXECUTOR_CLIENT_ID", "").strip()
    private_key = _private_key()
    if not config or not domain or not client_id or not private_key or not config.auth_server_id:
        raise RuntimeError("Inventory service-token exchange is not fully configured.")

    token_endpoint = f"{domain}/oauth2/{config.auth_server_id}/v1/token"
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": client_id,
            "sub": client_id,
            "aud": token_endpoint,
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": private_key.get("kid")},
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_endpoint,
            data={
                "grant_type": "client_credentials",
                "scope": scope,
                "client_id": client_id,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": assertion,
            },
            headers={"Accept": "application/json"},
            timeout=15.0,
        )
    if response.status_code >= 400:
        try:
            detail = response.json().get("error_description") or response.json().get("error")
        except ValueError:
            detail = response.text[:300]
        raise RuntimeError(f"Okta service-token exchange failed ({response.status_code}): {detail}")

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Okta service-token response did not include an access token.")
    return str(token)
