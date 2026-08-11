"""
Demo-only Okta profile mutation for live FGA demos.

Lets the signed-in user change their OWN role and vacation controls through the
Okta Users API so the authorization story can be shown live without an Okta
Admin Console detour mid-demo. ``is_a_manager`` is synchronized from the role
level and is never an independent authorization switch.

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

ALLOWED_ATTRIBUTES = {"clearance_level", "is_on_vacation"}
PERSONA_DEFAULT_LEVELS = {
    "sarah.sales": 0,
    "mike.manager": 1,
    "joe.vp": 2,
}

# The cache preserves the starting value for non-persona users during one
# process lifetime. Named personas also have deterministic reset levels, so a
# backend restart cannot strand Sarah, Mike, or Joe in a simulated role.
_original_values: Dict[str, Dict[str, Any]] = {}


def _reset_level(profile: Dict[str, Any]) -> Any:
    login = str(profile.get("login") or profile.get("email") or "").lower()
    local_part = login.split("@", 1)[0]
    return PERSONA_DEFAULT_LEVELS.get(local_part, profile.get("clearance_level"))


def _reset_vacation(profile: Dict[str, Any]) -> bool:
    login = str(profile.get("login") or profile.get("email") or "").lower()
    local_part = login.split("@", 1)[0]
    if local_part in PERSONA_DEFAULT_LEVELS:
        return False
    return profile.get("is_on_vacation") is True


def _manager_for_level(level: Any) -> bool:
    return level in (1, 2)


def _status_values(profile: Dict[str, Any]) -> Dict[str, Any]:
    level = profile.get("clearance_level")
    return {
        "clearance_level": level,
        "is_a_manager": _manager_for_level(level),
        "is_on_vacation": profile.get("is_on_vacation") is True,
    }


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
    return _status_values(profile)


async def toggle_demo_attribute(user_id: str, attribute: str, value: Any) -> Dict[str, Any]:
    """Set one allow-listed profile attribute on the caller's own Okta user."""
    if attribute not in ALLOWED_ATTRIBUTES:
        raise ValueError(f"Attribute '{attribute}' is not toggleable")
    if attribute == "clearance_level" and (
        isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1, 2)
    ):
        raise ValueError("clearance_level must be 0 (Sales), 1 (Manager), or 2 (VP)")
    if attribute == "is_on_vacation" and not isinstance(value, bool):
        raise ValueError("is_on_vacation must be true or false")

    domain, api_token = _require_config()

    if user_id not in _original_values:
        current_profile = await _get_profile(user_id, domain, api_token)
        original_level = _reset_level(current_profile)
        _original_values[user_id] = {
            "clearance_level": original_level,
            "is_a_manager": _manager_for_level(original_level),
            "is_on_vacation": _reset_vacation(current_profile),
        }

    updates = {attribute: value}
    if attribute == "clearance_level":
        updates["is_a_manager"] = _manager_for_level(value)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{domain}/api/v1/users/{user_id}",
            json={"profile": updates},
            headers={"Authorization": f"SSWS {api_token}", "Content-Type": "application/json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        updated = resp.json()

    logger.info(f"Demo toggle: {user_id} {attribute} -> {value}")
    return {
        "attribute": attribute,
        "value": updated["profile"].get(attribute),
        "values": _status_values(updated["profile"]),
        "note": "Takes effect on your next chat message - no re-login needed.",
    }


async def reset_demo_attributes(user_id: str) -> Dict[str, Any]:
    """Restore the persona's original role level."""
    domain, api_token = _require_config()
    reset_values = _original_values.get(user_id)
    if not reset_values:
        current_profile = await _get_profile(user_id, domain, api_token)
        level = _reset_level(current_profile)
        reset_values = {
            "clearance_level": level,
            "is_a_manager": _manager_for_level(level),
            "is_on_vacation": _reset_vacation(current_profile),
        }
    else:
        level = reset_values.get("clearance_level")
        reset_values = {
            **reset_values,
            "is_a_manager": _manager_for_level(level),
        }

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
