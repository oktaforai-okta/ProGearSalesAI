"""Resolve live ProGear authorization context from an Okta user profile."""

from __future__ import annotations

import asyncio
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
    is_a_manager: bool
    is_on_vacation: bool


def _profile_bool(value: object) -> bool:
    """Normalize Okta Boolean values without treating arbitrary strings as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return value == 1


class OktaRoleResolver:
    def __init__(self, base_url: str, api_token: str):
        self._base_url = _normalize_base_url(base_url)
        self._api_token = api_token

    async def resolve_identity(self, identifier: str) -> ResolvedOktaUser:
        """Return the user's immutable ID and current authorization context.

        This lookup intentionally uses the live Okta profile instead of a
        browser-provided value.  It is used both for approver verification and
        for the pre-exchange clearance guard on inventory writes.
        """
        if not identifier:
            return ResolvedOktaUser(
                user_id="",
                clearance_level=-1,
                is_a_manager=False,
                is_on_vacation=False,
            )
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=3.0),
        ) as client:
            for attempt in range(3):
                try:
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
                    break
                except httpx.HTTPError as exc:
                    status = (
                        exc.response.status_code
                        if isinstance(exc, httpx.HTTPStatusError)
                        else None
                    )
                    retryable = (
                        isinstance(exc, httpx.TransportError)
                        or status == 429
                        or (status is not None and status >= 500)
                    )
                    if not retryable or attempt == 2:
                        raise

                    retry_after = None
                    if isinstance(exc, httpx.HTTPStatusError):
                        retry_after = exc.response.headers.get("Retry-After")
                    try:
                        delay = min(float(retry_after), 2.0) if retry_after else 0.25 * (2 ** attempt)
                    except ValueError:
                        delay = 0.25 * (2 ** attempt)
                    await asyncio.sleep(delay)
        clearance_level = normalize_role_level(profile.get("clearance_level"))
        return ResolvedOktaUser(
            user_id=str(user.get("id") or ""),
            clearance_level=clearance_level,
            # Clearance remains authoritative. The stored manager attribute is
            # a synchronized, human-readable profile fact used in tokens and
            # demos; deriving it here prevents stale profile data from creating
            # a second authorization source.
            is_a_manager=clearance_level in (1, 2),
            is_on_vacation=_profile_bool(profile.get("is_on_vacation")),
        )

    async def resolve(self, identifier: str) -> int:
        """Return the user's current Okta clearance level."""
        return (await self.resolve_identity(identifier)).clearance_level

    async def __call__(self, approver: dict) -> int:
        identifier = approver.get("id") or approver.get("email")
        return await self.resolve(identifier or "")

    async def is_group_member(self, approver: dict, group_name: str) -> bool:
        """Return whether the live Okta approver belongs to ``group_name``."""
        identifier = approver.get("id") or approver.get("email")
        if not identifier or not group_name:
            return False
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=3.0),
        ) as client:
            response = await client.get(
                f"{self._base_url}/api/v1/users/{identifier}/groups",
                headers={
                    "Authorization": f"SSWS {self._api_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
        expected = group_name.casefold()
        return any(
            str((group.get("profile") or {}).get("name") or "").casefold() == expected
            for group in response.json()
        )
