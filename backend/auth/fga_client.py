"""FGA client for ProGear's three-level inventory policy.

Okta's ``Clearance`` access-token claim is the role source of truth:
0 = Sales, 1 = Manager, 2 = VP.  The claim is translated into exactly one
contextual FGA role tuple on every check, so profile changes take effect on
the next request without stale stored roles.

FGA evaluates these application relations on ``inventory_system:warehouse``:

* ``can_read``: Sales, Manager, or VP
* ``can_request_change``: Manager only, for a 601+ VP request
* ``can_update_standard``: Manager or VP (1-600 units)
* ``can_update_large``: VP (601+ units)

No role tuples are persisted. The current Okta claim is supplied as one
contextual relationship for each check.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from openfga_sdk import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import (
    ClientCheckRequest,
    ClientTuple,
)
from openfga_sdk.credentials import Credentials, CredentialConfiguration

from auth.inventory_policy import ROLE_RELATIONS, normalize_role_level, role_name

logger = logging.getLogger(__name__)

# FGA Configuration from environment
FGA_API_URL = os.getenv("FGA_API_URL", "https://api.us1.fga.dev")
FGA_STORE_ID = os.getenv("FGA_STORE_ID")
FGA_MODEL_ID = os.getenv("FGA_MODEL_ID")
FGA_CLIENT_ID = os.getenv("FGA_CLIENT_ID")
FGA_CLIENT_SECRET = os.getenv("FGA_CLIENT_SECRET")
FGA_API_TOKEN_ISSUER = os.getenv("FGA_API_TOKEN_ISSUER", "auth.fga.dev")
FGA_API_AUDIENCE = os.getenv("FGA_API_AUDIENCE", "https://api.us1.fga.dev/")


@dataclass
class FGACheckResult:
    """Result of an FGA permission check."""
    allowed: bool
    relation: str
    object: str
    user: str
    context: Dict[str, Any]
    reason: str  # Human-readable explanation
    contextual_tuples: list = None  # Tuples passed to FGA


# Maps ProGear agent types -> FGA object types
# Only inventory_system is modeled for now.
# Other agents pass through (no FGA check).
AGENT_TO_FGA_OBJECT = {
    "inventory": "inventory_system:main_db",
}

# Singleton FGA client
_fga_client: Optional[OpenFgaClient] = None


def _get_fga_client() -> Optional[OpenFgaClient]:
    """Get or create FGA client singleton."""
    global _fga_client

    if _fga_client is not None:
        return _fga_client

    if not FGA_STORE_ID or not FGA_CLIENT_ID or not FGA_CLIENT_SECRET:
        logger.warning("FGA credentials not configured - FGA checks will be skipped")
        return None

    try:
        credentials = Credentials(
            method="client_credentials",
            configuration=CredentialConfiguration(
                client_id=FGA_CLIENT_ID,
                client_secret=FGA_CLIENT_SECRET,
                api_issuer=FGA_API_TOKEN_ISSUER,
                api_audience=FGA_API_AUDIENCE,
            )
        )
        configuration = ClientConfiguration(
            api_url=FGA_API_URL,
            store_id=FGA_STORE_ID,
            authorization_model_id=FGA_MODEL_ID,
            credentials=credentials,
        )
        _fga_client = OpenFgaClient(configuration)
        logger.info(f"FGA client initialized: store={FGA_STORE_ID}")
        return _fga_client
    except Exception as e:
        logger.error(f"Failed to initialize FGA client: {e}")
        return None


# ============================================================================
# FGA Check Functions
# ============================================================================

async def check_inventory_access_via_fga(
    user_email: str,
    role_level: int = -1,
    relation: str = "can_read",
    system_id: str = "warehouse",
) -> FGACheckResult:
    """Check one inventory permission with a live contextual role tuple."""
    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{system_id}"
    level = normalize_role_level(role_level)
    role_relation = ROLE_RELATIONS.get(level)

    contextual_tuples = []
    if role_relation:
        contextual_tuples.append(
            ClientTuple(user=fga_user, relation=role_relation, object=fga_object)
        )
    context = {
        "role_level": level,
        "role_name": role_name(level),
        "role_relation": role_relation,
        "contextual_tuples_count": len(contextual_tuples),
    }

    # Get FGA client
    fga_client = _get_fga_client()

    if fga_client is None:
        # FGA not configured - deny by default for safety
        logger.warning("FGA client not available - denying access by default")
        return FGACheckResult(
            allowed=False,
            relation=relation,
            object=fga_object,
            user=fga_user,
            context=context,
            reason="FGA not configured - access denied by default",
            contextual_tuples=[],
        )

    try:
        check_request = ClientCheckRequest(
            user=fga_user,
            relation=relation,
            object=fga_object,
            contextual_tuples=contextual_tuples if contextual_tuples else None,
        )

        response = await fga_client.check(check_request)
        allowed = response.allowed

        if allowed:
            reason = (
                f"Allowed: {role_name(level)} (level {level}) satisfies {relation}."
            )
        elif not role_relation:
            reason = "Denied: no valid ProGear role level was supplied by Okta."
        else:
            reason = (
                f"Denied: {role_name(level)} (level {level}) does not satisfy {relation}."
            )

        logger.info(
            f"FGA API check: {fga_user} {relation} {fga_object} "
            f"(role={level}, "
            f"contextual_tuples={len(contextual_tuples)}) -> {allowed}"
        )

        return FGACheckResult(
            allowed=allowed,
            relation=relation,
            object=fga_object,
            user=fga_user,
            context=context,
            reason=reason,
            contextual_tuples=[
                {"user": item.user, "relation": item.relation, "object": item.object}
                for item in contextual_tuples
            ],
        )

    except Exception as e:
        logger.error(f"FGA check failed: {e}")
        return FGACheckResult(
            allowed=False,
            relation=relation,
            object=fga_object,
            user=fga_user,
            context={**context, "error": str(e)},
            reason=f"FGA check failed: {e}",
            contextual_tuples=[],
        )


async def check_agent_access(
    user_email: str,
    agent_type: str,
    scopes: list = None,
    role_level: int = -1,
    relation: str | None = None,
) -> FGACheckResult:
    """Check an agent permission; only inventory currently has an FGA model."""
    scopes = scopes or []

    # Only inventory has FGA checks - others pass through
    if agent_type != "inventory":
        return FGACheckResult(
            allowed=True,
            relation="n/a",
            object=f"{agent_type}_system",
            user=f"user:{user_email}",
            context={"role_level": role_level},
            reason=f"No FGA model for {agent_type} - Okta RBAC only",
            contextual_tuples=[],
        )

    if relation is None:
        relation = "can_update_standard" if "inventory:write" in scopes else "can_read"

    return await check_inventory_access_via_fga(
        user_email=user_email,
        role_level=role_level,
        relation=relation,
        system_id="warehouse",
    )


def is_fga_configured() -> bool:
    """
    Check if FGA API is configured.

    Returns True if FGA credentials are set.
    """
    return bool(FGA_STORE_ID and FGA_CLIENT_ID and FGA_CLIENT_SECRET)


def get_fga_model_info() -> Dict[str, Any]:
    """Get FGA model information for UI display."""
    return {
        "mode": "role-context",
        "description": "Three ProGear role levels with a quantity-aware decision",
        "store_name": "ProGear",
        "api_url": FGA_API_URL,
        "store_id": FGA_STORE_ID,
        "model_id": FGA_MODEL_ID,
        "model_types": {
            "user": "Human principal from Okta",
            "inventory_system": "Warehouse with Sales, Manager, and VP permissions",
        },
        "key_relations": {
            "can_read": "Sales or Manager or VP",
            "can_request_change": "Manager only, for VP approval above 600",
            "can_update_standard": "Manager or VP (1-600)",
            "can_update_large": "VP (601+)",
        },
        "scope_to_permission": {
            "inventory:read": {
                "fga_permission": "can_read",
                "requirements": "level 0+"
            },
            "inventory:write": {
                "fga_permission": "can_update_standard or can_update_large",
                "requirements": "level 1 through 600; level 2 at 601+"
            }
        },
        "contextual_tuples": {
            "role": "Mapped from the live Okta Clearance claim on each request",
        },
        "claims_used": [
            {"name": "Clearance", "okta_attribute": "user.clearance_level", "description": "0=Sales, 1=Manager, 2=VP"},
            {"name": "Manager", "okta_attribute": "user.is_a_manager", "description": "Derived from the role level"},
            {"name": "Vacation", "okta_attribute": "user.is_on_vacation", "description": "Enforced before ID-JAG"},
        ],
    }


async def close_fga_client():
    """Close the FGA client connection."""
    global _fga_client
    if _fga_client is not None:
        await _fga_client.close()
        _fga_client = None
        logger.info("FGA client closed")
