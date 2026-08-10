"""
Demo-only Okta profile mutation for live FGA demos.

Lets the signed-in user toggle their OWN is_on_vacation / is_a_manager /
clearance_level custom attributes for real, via the Okta Users API, so the
FGA "manager on vacation" / "insufficient clearance" scenarios can be shown
live without an Okta Admin Console detour mid-demo.

Scoped deliberately tight:
- Only the caller's own Okta user (resolved from their validated ID token,
  never from the request body) can be mutated.
- Only a fixed allow-list of demo attributes can be touched.
- Persona-specific values are captured once per user/attribute. Reset restores
  those values and always returns vacation status to the demo default (False).
"""

import os
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

ALLOWED_ATTRIBUTES = {"is_on_vacation", "is_a_manager", "clearance_level"}

# A demo reset always returns vacation status to the normal working state.
# Manager and clearance remain persona-specific and are restored to the values
# captured before they were first changed.
DEMO_DEFAULT_VALUES: Dict[str, Any] = {"is_on_vacation": False}

# In-memory only - fine for a single-process demo backend. Keyed by Okta
# login/email, then attribute name, holding the value seen before the first
# toggle for that (user, attribute) pair.
_original_values: Dict[str, Dict[str, Any]] = {}


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

    domain, api_token = _require_config()

    if user_id not in _original_values:
        _original_values[user_id] = {}
    if attribute not in _original_values[user_id]:
        if attribute in DEMO_DEFAULT_VALUES:
            _original_values[user_id][attribute] = DEMO_DEFAULT_VALUES[attribute]
        else:
            current_profile = await _get_profile(user_id, domain, api_token)
            _original_values[user_id][attribute] = current_profile.get(attribute)

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
    """Restore persona attributes and enforce the safe demo defaults."""
    originals = _original_values.get(user_id, {})
    reset_values = {**originals, **DEMO_DEFAULT_VALUES}

    domain, api_token = _require_config()

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
