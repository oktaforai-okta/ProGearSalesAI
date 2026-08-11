"""Resolve an OIG approver's live ProGear role level from Okta."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from auth.inventory_policy import normalize_role_level


def _normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if value and not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


@dataclass(frozen=True)
class ResolvedOktaUser:
    user_id: str
    clearance_level: int


class OktaRoleResolver:
    def __init__(self, base_url: str, api_token: str):
        self._base_url = _normalize_base_url(base_url)
        self._api_token = api_token

    async def resolve_identity(self, identifier: str) -> ResolvedOktaUser:
        """Return the user's immutable Okta ID and current clearance level.

        This lookup intentionally uses the live Okta profile instead of a
        browser-provided value.  It is used both for approver verification and
        for the pre-exchange clearance guard on inventory writes.
        """
        if not identifier:
            return ResolvedOktaUser(user_id="", clearance_level=-1)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._base_url}/api/v1/users/{identifier}",
                headers={
                    "Authorization": f"SSWS {self._api_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            user = response.json()
            profile = user.get("profile") or {}
        return ResolvedOktaUser(
            user_id=str(user.get("id") or ""),
            clearance_level=normalize_role_level(profile.get("clearance_level")),
        )

    async def resolve(self, identifier: str) -> int:
        """Return the user's current Okta clearance level."""
        return (await self.resolve_identity(identifier)).clearance_level

    async def __call__(self, approver: dict) -> int:
        identifier = approver.get("id") or approver.get("email")
        return await self.resolve(identifier or "")
