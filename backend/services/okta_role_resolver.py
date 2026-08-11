"""Resolve an OIG approver's live ProGear role level from Okta."""

from __future__ import annotations

import httpx

from auth.inventory_policy import normalize_role_level


def _normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if value and not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


class OktaRoleResolver:
    def __init__(self, base_url: str, api_token: str):
        self._base_url = _normalize_base_url(base_url)
        self._api_token = api_token

    async def resolve(self, identifier: str) -> int:
        """Return the user's current Okta clearance level.

        This lookup intentionally uses the live Okta profile instead of a
        browser-provided value.  It is used both for approver verification and
        for the pre-exchange clearance guard on inventory writes.
        """
        if not identifier:
            return -1
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

    async def __call__(self, approver: dict) -> int:
        identifier = approver.get("id") or approver.get("email")
        return await self.resolve(identifier or "")
