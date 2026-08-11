"""Resolve an OIG approver's live ProGear role level from Okta."""

from __future__ import annotations

import httpx

from auth.inventory_policy import normalize_role_level


class OktaRoleResolver:
    def __init__(self, base_url: str, api_token: str):
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token

    async def __call__(self, approver: dict) -> int:
        identifier = approver.get("id") or approver.get("email")
        if not identifier:
            return 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._base_url}/api/v1/users/{identifier}",
                headers={
                    "Authorization": f"SSWS {self._api_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            profile = response.json().get("profile") or {}
        return normalize_role_level(profile.get("clearance_level"))
