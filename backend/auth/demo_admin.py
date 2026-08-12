"""Session-isolated controls for the hosted FGA demo.

Role authorization always comes from the employee's live Okta profile. The
FGA page can simulate only the vacation delegation gate. Shared Sarah/Mike
credentials are used by several demo engineers, so live profile mutation
would make one browser's simulation affect everyone.

Each authenticated browser tab receives an opaque demo-session id.  Values are
kept server-side and keyed by both the validated Okta subject and that id.  A
browser can therefore alter only its own short-lived simulation overlay.
"""

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import httpx

logger = logging.getLogger(__name__)

ALLOWED_ATTRIBUTES = {"is_on_vacation"}

_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_SESSION_TTL_SECONDS = max(300, int(os.getenv("DEMO_SESSION_TTL_SECONDS", "14400")))


@dataclass
class _DemoSession:
    original_values: Dict[str, Any]
    values: Dict[str, Any]
    last_seen: float


_sessions: Dict[Tuple[str, str], _DemoSession] = {}


def _reset_level(profile: Dict[str, Any]) -> Any:
    """Return the live role; demo sessions never replace it."""
    return profile.get("clearance_level")


def _reset_vacation(profile: Dict[str, Any]) -> bool:
    login = str(profile.get("login") or profile.get("email") or "").lower()
    local_part = login.split("@", 1)[0]
    if local_part in {"sarah.sales", "mike.manager", "joe.vp"}:
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


def _validate_session_id(demo_session_id: str) -> str:
    session_id = str(demo_session_id or "").strip()
    if not _SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError("A valid FGA demo session is required")
    return session_id


def _clear_expired_sessions(now: float) -> None:
    expired = [
        key for key, session in _sessions.items()
        if now - session.last_seen > _SESSION_TTL_SECONDS
    ]
    for key in expired:
        _sessions.pop(key, None)


async def _get_profile(user_id: str, domain: str, api_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{domain}/api/v1/users/{user_id}",
            headers={"Authorization": f"SSWS {api_token}", "Accept": "application/json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["profile"]


async def _get_session(user_id: str, demo_session_id: str) -> _DemoSession:
    session_id = _validate_session_id(demo_session_id)
    now = time.monotonic()
    _clear_expired_sessions(now)
    key = (user_id, session_id)
    existing = _sessions.get(key)
    if existing:
        existing.last_seen = now
        return existing

    domain, api_token = _require_config()
    profile = await _get_profile(user_id, domain, api_token)
    level = _reset_level(profile)
    baseline = {
        "clearance_level": level,
        "is_a_manager": _manager_for_level(level),
        "is_on_vacation": _reset_vacation(profile),
    }
    session = _DemoSession(
        original_values=dict(baseline),
        values=dict(baseline),
        last_seen=now,
    )
    _sessions[key] = session
    return session


def _response_values(session: _DemoSession) -> Dict[str, Any]:
    return {
        **session.values,
        "context_source": "isolated_demo_session",
        "session_isolated": True,
    }


async def get_demo_status(user_id: str, demo_session_id: str) -> Dict[str, Any]:
    """Return this authenticated browser session's FGA simulation values."""
    return _response_values(await _get_session(user_id, demo_session_id))


async def toggle_demo_attribute(
    user_id: str,
    demo_session_id: str,
    attribute: str,
    value: Any,
) -> Dict[str, Any]:
    """Change the vacation demo value without modifying Okta."""
    if attribute not in ALLOWED_ATTRIBUTES:
        raise ValueError(f"Attribute '{attribute}' is not toggleable")
    if attribute == "is_on_vacation" and not isinstance(value, bool):
        raise ValueError("is_on_vacation must be true or false")

    session = await _get_session(user_id, demo_session_id)
    session.values[attribute] = value

    logger.info("Updated isolated FGA demo context for authenticated user")
    return {
        "attribute": attribute,
        "value": session.values[attribute],
        "values": _response_values(session),
        "note": "This browser session will use the value on its next FGA prompt.",
    }


async def reset_demo_attributes(user_id: str, demo_session_id: str) -> Dict[str, Any]:
    """Restore only this browser session's starting simulation values."""
    session = await _get_session(user_id, demo_session_id)
    session.values = dict(session.original_values)
    session.last_seen = time.monotonic()
    logger.info("Reset isolated FGA demo context for authenticated user")
    return {
        "reset": list(session.values.keys()),
        "values": _response_values(session),
    }


def _clear_demo_sessions_for_test() -> None:
    _sessions.clear()
