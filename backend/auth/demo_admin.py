"""
Demo-only Okta profile mutation for live FGA demos.

Lets the signed-in user change their OWN ``clearance_level`` custom attribute
through the Okta Users API so the three role tiers can be shown live without
an Okta Admin Console detour mid-demo.

Scoped deliberately tight:
- Only the caller's own Okta user (resolved from their validated ID token,
  never from the request body) can be mutated.
- Only a fixed allow-list of demo attributes can be touched.
- Persona-specific values are captured once per user. Reset restores that role.
"""

import os
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

ALLOWED_ATTRIBUTES = {"clearance_level"}
PERSONA_DEFAULT_LEVELS = {
    "sarah.sales@atko.email": 0,
    "mike.manager@atko.email": 1,
    "joe.vp@atko.email": 2,
}

# The cache preserves the starting value for non-persona users during one
# process lifetime. Named personas also have deterministic reset levels, so a
# backend restart cannot strand Sarah, Mike, or Joe in a simulated role.
_original_values: Dict[str, Dict[str, Any]] = {}


def _reset_level(profile: Dict[str, Any]) -> Any:
    login = str(profile.get("login") or profile.get("email") or "").lower()
    return PERSONA_DEFAULT_LEVELS.get(login, profile.get("clearance_level"))


def _okta_domain() -> str:
    domain = os.getenv("OKTA_DOMAIN", "").strip()
    if domain and not domain.startswith("http"):
        domain = f"https://{domain}"
    return domain


def _require_config() -> tuple[str, str]:
    api_token = os.getenv("OKTA_API_TOKEN", "").strip()
    domain = _okta_domain()
    if not api_token or not domain:
        raise RuntimeError("Okta admin API not configured (OKTA_DOMAIN/OKTA_API_TOKEN)")
    return domain, api_token


async def _get_profile(user_id: str, domain: str, api_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{domain}/api/v1/users/{user_id}",
            headers={"Authorization": f"SSWS {api_token}", "Accept": "application/json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["profile"]


async def get_demo_status(user_id: str) -> Dict[str, Any]:
    """Read-only: the caller's current values for the toggleable attributes,
    so the UI can highlight which state is actually active instead of
    guessing."""
    domain, api_token = _require_config()
    profile = await _get_profile(user_id, domain, api_token)
    return {attr: profile.get(attr) for attr in ALLOWED_ATTRIBUTES}


async def toggle_demo_attribute(user_id: str, attribute: str, value: Any) -> Dict[str, Any]:
    """Set one allow-listed profile attribute on the caller's own Okta user."""
    if attribute not in ALLOWED_ATTRIBUTES:
        raise ValueError(f"Attribute '{attribute}' is not toggleable")
    if attribute == "clearance_level" and (
        isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1, 2)
    ):
        raise ValueError("clearance_level must be 0 (Sales), 1 (Manager), or 2 (VP)")

    domain, api_token = _require_config()

    if user_id not in _original_values:
        _original_values[user_id] = {}
    if attribute not in _original_values[user_id]:
        current_profile = await _get_profile(user_id, domain, api_token)
        _original_values[user_id][attribute] = _reset_level(current_profile)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{domain}/api/v1/users/{user_id}",
            json={"profile": {attribute: value}},
            headers={"Authorization": f"SSWS {api_token}", "Content-Type": "application/json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        updated = resp.json()

    logger.info(f"Demo toggle: {user_id} {attribute} -> {value}")
    return {
        "attribute": attribute,
        "value": updated["profile"].get(attribute),
        "note": "Takes effect on your next chat message - no re-login needed.",
    }


async def reset_demo_attributes(user_id: str) -> Dict[str, Any]:
    """Restore the persona's original role level."""
    domain, api_token = _require_config()
    reset_values = _original_values.get(user_id)
    if not reset_values:
        current_profile = await _get_profile(user_id, domain, api_token)
        reset_values = {"clearance_level": _reset_level(current_profile)}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{domain}/api/v1/users/{user_id}",
            json={"profile": reset_values},
            headers={"Authorization": f"SSWS {api_token}", "Content-Type": "application/json"},
            timeout=10.0,
        )
        resp.raise_for_status()

    _original_values.pop(user_id, None)
    logger.info(f"Demo reset: {user_id} -> {reset_values}")
    return {"reset": list(reset_values.keys()), "values": reset_values}
