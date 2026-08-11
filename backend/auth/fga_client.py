"""Auth0 FGA client for ProGear's three-level inventory policy.

Okta's ``Clearance`` access-token claim is the role source of truth:
1 = Sales, 2 = Manager, 3 = VP.  The claim is translated into exactly one
contextual FGA role tuple on every check.  Vacation is also contextual, so a
profile change takes effect on the next request without stale stored roles.

FGA evaluates these application relations on ``inventory_system:warehouse``:

* ``can_read``: Sales, Manager, or VP
* ``can_request_change``: any non-vacation role
* ``can_update_standard``: non-vacation Manager or VP (1-600 units)
* ``can_update_large``: non-vacation VP (601+ units)

The older tuple-management helpers remain below for compatibility with old
demo data, but the current orchestrator uses contextual role tuples only.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from openfga_sdk import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import (
    ClientCheckRequest,
    ClientListObjectsRequest,
    ClientTuple,
    ClientWriteRequest,
)
from openfga_sdk.credentials import Credentials, CredentialConfiguration

from auth.inventory_policy import ROLE_RELATIONS, normalize_role_level, role_name

logger = logging.getLogger(__name__)


def _is_missing_tuple_error(e: Exception) -> bool:
    """
    Detect FGA "tuple does not exist" errors on delete.

    The openfga-sdk ApiException's str() only exposes status/reason; the
    descriptive message ("cannot delete a tuple which does not exist") is
    in e.body. Check both so harmless "already gone" deletes don't log ERROR.
    """
    text = str(e).lower()
    body = getattr(e, "body", None)
    if body:
        text += " " + str(body).lower()
    return (
        "does not exist" in text
        or "not found" in text
        or "cannot delete" in text
        or "write_failed_due_to_invalid_input" in text
    )


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
# Dynamic Tuple Management Functions
# ============================================================================

async def check_manager_tuple_exists(
    user_email: str,
    system_id: str = "warehouse"
) -> bool:
    """
    Check if manager tuple exists in FGA store for a user.

    Args:
        user_email: User's email/login from Okta
        system_id: The inventory system ID (default: warehouse)

    Returns:
        True if tuple exists, False otherwise
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot check manager tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{system_id}"

    try:
        # Use check API to verify if the manager relation exists
        check_request = ClientCheckRequest(
            user=fga_user,
            relation="manager",
            object=fga_object
        )
        response = await fga_client.check(check_request)

        exists = response.allowed
        logger.info(f"FGA manager tuple check: {fga_user} -> manager -> {fga_object} exists={exists}")
        return exists

    except Exception as e:
        logger.error(f"FGA manager tuple check failed: {e}")
        return False


async def write_manager_tuple(
    user_email: str,
    system_id: str = "warehouse"
) -> bool:
    """
    Write manager tuple to FGA store.

    Creates: user:{email} manager inventory_system:{system_id}

    Args:
        user_email: User's email/login from Okta
        system_id: The inventory system ID (default: warehouse)

    Returns:
        True if successful, False otherwise
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot write manager tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{system_id}"

    try:
        write_request = ClientWriteRequest(
            writes=[
                ClientTuple(
                    user=fga_user,
                    relation="manager",
                    object=fga_object
                )
            ]
        )
        await fga_client.write(write_request)
        logger.info(f"FGA: Created manager tuple: {fga_user} -> manager -> {fga_object}")
        return True

    except Exception as e:
        error_str = str(e).lower()
        if "already exists" in error_str:
            logger.info(f"FGA: Manager tuple already exists for {user_email}")
            return True
        logger.error(f"FGA write manager tuple failed: {e}")
        return False


async def delete_manager_tuple(
    user_email: str,
    system_id: str = "warehouse"
) -> bool:
    """
    Delete manager tuple from FGA store.

    Removes: user:{email} manager inventory_system:{system_id}

    Args:
        user_email: User's email/login from Okta
        system_id: The inventory system ID (default: warehouse)

    Returns:
        True if successful (or tuple didn't exist), False on error
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot delete manager tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{system_id}"

    try:
        write_request = ClientWriteRequest(
            deletes=[
                ClientTuple(
                    user=fga_user,
                    relation="manager",
                    object=fga_object
                )
            ]
        )
        await fga_client.write(write_request)
        logger.info(f"FGA: Deleted manager tuple: {fga_user} -> manager -> {fga_object}")
        return True

    except Exception as e:
        if _is_missing_tuple_error(e):
            logger.info(f"FGA: Manager tuple didn't exist for {user_email} (nothing to delete)")
            return True
        logger.error(f"FGA delete manager tuple failed: {e}")
        return False


async def ensure_manager_relationship(
    user_email: str,
    is_manager: bool,
    system_id: str = "warehouse"
) -> dict:
    """
    Ensure manager relationship in FGA matches the Okta Manager claim.

    - If is_manager=True and tuple doesn't exist -> create it
    - If is_manager=False and tuple exists -> delete it
    - Otherwise, no action needed

    Args:
        user_email: User's email/login from Okta
        is_manager: Value of Manager claim from Okta token
        system_id: The inventory system ID (default: warehouse)

    Returns:
        Dict with action taken and success status
    """
    result = {
        "user": user_email,
        "is_manager_claim": is_manager,
        "action": "none",
        "success": True,
    }

    # Always write/delete unconditionally. The write helpers tolerate the
    # "tuple already exists" / "does not exist" races, which lets us skip a
    # pre-check read that would otherwise return stale data under FGA's default
    # MINIMIZE_LATENCY consistency. This keeps the tuple state aligned with the
    # Okta claim without relying on fresh-read semantics we can't guarantee.
    if is_manager:
        success = await write_manager_tuple(user_email, system_id)
        result["action"] = "ensured_present"
        result["success"] = success
    else:
        success = await delete_manager_tuple(user_email, system_id)
        result["action"] = "ensured_absent"
        result["success"] = success

    return result


# ============================================================================
# Viewer Tuple Management Functions
# ============================================================================

async def check_viewer_tuple_exists(
    user_email: str,
    system_id: str = "warehouse"
) -> bool:
    """
    Check if viewer tuple exists in FGA store for a user.

    Args:
        user_email: User's email/login from Okta
        system_id: The inventory system ID (default: warehouse)

    Returns:
        True if tuple exists, False otherwise
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot check viewer tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{system_id}"

    try:
        check_request = ClientCheckRequest(
            user=fga_user,
            relation="viewer",
            object=fga_object
        )
        response = await fga_client.check(check_request)

        exists = response.allowed
        logger.info(f"FGA viewer tuple check: {fga_user} -> viewer -> {fga_object} exists={exists}")
        return exists

    except Exception as e:
        logger.error(f"FGA viewer tuple check failed: {e}")
        return False


async def write_viewer_tuple(
    user_email: str,
    system_id: str = "warehouse"
) -> bool:
    """
    Write viewer tuple to FGA store.

    Creates: user:{email} viewer inventory_system:{system_id}

    Args:
        user_email: User's email/login from Okta
        system_id: The inventory system ID (default: warehouse)

    Returns:
        True if successful, False otherwise
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot write viewer tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{system_id}"

    try:
        write_request = ClientWriteRequest(
            writes=[
                ClientTuple(
                    user=fga_user,
                    relation="viewer",
                    object=fga_object
                )
            ]
        )
        await fga_client.write(write_request)
        logger.info(f"FGA: Created viewer tuple: {fga_user} -> viewer -> {fga_object}")
        return True

    except Exception as e:
        error_str = str(e).lower()
        if "already exists" in error_str:
            logger.info(f"FGA: Viewer tuple already exists for {user_email}")
            return True
        logger.error(f"FGA write viewer tuple failed: {e}")
        return False


async def delete_viewer_tuple(
    user_email: str,
    system_id: str = "warehouse"
) -> bool:
    """
    Delete viewer tuple from FGA store.

    Removes: user:{email} viewer inventory_system:{system_id}

    Args:
        user_email: User's email/login from Okta
        system_id: The inventory system ID (default: warehouse)

    Returns:
        True if successful (or tuple didn't exist), False on error
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot delete viewer tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{system_id}"

    try:
        write_request = ClientWriteRequest(
            deletes=[
                ClientTuple(
                    user=fga_user,
                    relation="viewer",
                    object=fga_object
                )
            ]
        )
        await fga_client.write(write_request)
        logger.info(f"FGA: Deleted viewer tuple: {fga_user} -> viewer -> {fga_object}")
        return True

    except Exception as e:
        if _is_missing_tuple_error(e):
            logger.info(f"FGA: Viewer tuple didn't exist for {user_email} (nothing to delete)")
            return True
        logger.error(f"FGA delete viewer tuple failed: {e}")
        return False


async def ensure_viewer_relationship(
    user_email: str,
    is_viewer: bool,
    system_id: str = "warehouse"
) -> dict:
    """
    Ensure viewer relationship in FGA for non-manager users who need read access.

    - If is_viewer=True and tuple doesn't exist -> create it
    - If is_viewer=False and tuple exists -> delete it
    - Otherwise, no action needed

    Args:
        user_email: User's email/login from Okta
        is_viewer: Whether user should have viewer access
        system_id: The inventory system ID (default: warehouse)

    Returns:
        Dict with action taken and success status
    """
    result = {
        "user": user_email,
        "is_viewer": is_viewer,
        "action": "none",
        "success": True,
    }

    # Unconditional write/delete — see ensure_manager_relationship for rationale.
    if is_viewer:
        success = await write_viewer_tuple(user_email, system_id)
        result["action"] = "ensured_present"
        result["success"] = success
    else:
        success = await delete_viewer_tuple(user_email, system_id)
        result["action"] = "ensured_absent"
        result["success"] = success

    return result


async def check_clearance_tuple_exists(
    user_email: str,
    clearance_level: int
) -> bool:
    """
    Check if clearance tuple exists in FGA store for a user at specific level.

    Args:
        user_email: User's email/login from Okta
        clearance_level: The clearance level to check

    Returns:
        True if tuple exists, False otherwise
    """
    fga_client = _get_fga_client()
    if not fga_client:
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"clearance_level:{clearance_level}"

    try:
        check_request = ClientCheckRequest(
            user=fga_user,
            relation="granted_to",
            object=fga_object
        )
        response = await fga_client.check(check_request)
        exists = response.allowed
        logger.info(f"FGA clearance tuple check: {fga_user} -> granted_to -> {fga_object} exists={exists}")
        return exists

    except Exception as e:
        logger.error(f"FGA clearance tuple check failed: {e}")
        return False


async def write_clearance_tuple(
    user_email: str,
    clearance_level: int
) -> bool:
    """
    Write clearance tuple to FGA store.

    Creates: user:{email} granted_to clearance_level:{level}

    Args:
        user_email: User's email/login from Okta
        clearance_level: The clearance level to grant

    Returns:
        True if successful, False otherwise
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot write clearance tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"clearance_level:{clearance_level}"

    try:
        write_request = ClientWriteRequest(
            writes=[
                ClientTuple(
                    user=fga_user,
                    relation="granted_to",
                    object=fga_object
                )
            ]
        )
        await fga_client.write(write_request)
        logger.info(f"FGA: Created clearance tuple: {fga_user} -> granted_to -> {fga_object}")
        return True

    except Exception as e:
        error_str = str(e).lower()
        if "already exists" in error_str:
            logger.info(f"FGA: Clearance tuple already exists for {user_email} at level {clearance_level}")
            return True
        logger.error(f"FGA write clearance tuple failed: {e}")
        return False


async def delete_clearance_tuple(
    user_email: str,
    clearance_level: int
) -> bool:
    """
    Delete clearance tuple from FGA store.

    Removes: user:{email} granted_to clearance_level:{level}

    Args:
        user_email: User's email/login from Okta
        clearance_level: The clearance level to remove

    Returns:
        True if successful, False on error
    """
    fga_client = _get_fga_client()
    if not fga_client:
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"clearance_level:{clearance_level}"

    try:
        write_request = ClientWriteRequest(
            deletes=[
                ClientTuple(
                    user=fga_user,
                    relation="granted_to",
                    object=fga_object
                )
            ]
        )
        await fga_client.write(write_request)
        logger.info(f"FGA: Deleted clearance tuple: {fga_user} -> granted_to -> {fga_object}")
        return True

    except Exception as e:
        if _is_missing_tuple_error(e):
            logger.debug(f"FGA: Clearance tuple didn't exist for {user_email} at level {clearance_level}")
            return True
        logger.error(f"FGA delete clearance tuple failed: {e}")
        return False


async def list_existing_clearance_levels(user_email: str) -> Optional[list]:
    """
    Return the clearance levels the user currently has granted_to tuples for.

    Uses FGA list_objects in a single call instead of probing all 10 levels.
    Returns None if the FGA client is unavailable or the call fails.
    """
    fga_client = _get_fga_client()
    if not fga_client:
        return None

    try:
        response = await fga_client.list_objects(ClientListObjectsRequest(
            user=f"user:{user_email}",
            relation="granted_to",
            type="clearance_level",
        ))
        levels = []
        for obj in response.objects or []:
            # obj looks like "clearance_level:5"
            _, _, level_str = obj.partition(":")
            try:
                levels.append(int(level_str))
            except ValueError:
                continue
        return levels
    except Exception as e:
        logger.warning(f"FGA list_objects for clearance levels failed: {e}")
        return None


async def ensure_clearance_tuple(
    user_email: str,
    clearance_level: int
) -> dict:
    """
    Ensure ONLY the current clearance tuple exists in FGA for the user.

    Enforces single-clearance-per-user: deletes any level that isn't the
    current one, then creates the current level if it's missing. Uses
    list_objects to see what already exists, so we don't probe all 10 levels.
    """
    result = {
        "user": user_email,
        "clearance_level": clearance_level,
        "action": "none",
        "success": True,
        "deleted_levels": [],
    }

    existing = await list_existing_clearance_levels(user_email)
    # Fall back to the old behavior if list_objects failed, so FGA-down
    # doesn't silently skip cleanup.
    if existing is None:
        existing_to_delete = [lvl for lvl in range(1, 11) if lvl != max(clearance_level, 0)]
    else:
        existing_to_delete = [lvl for lvl in existing if lvl != clearance_level]

    for level in existing_to_delete:
        if await delete_clearance_tuple(user_email, level):
            result["deleted_levels"].append(level)

    if clearance_level <= 0:
        result["action"] = "cleared_all"
        if existing:
            logger.info(f"FGA: Removed clearance levels {result['deleted_levels']} for {user_email}")
        return result

    tuple_exists = existing is not None and clearance_level in existing
    result["tuple_existed"] = tuple_exists

    if not tuple_exists:
        success = await write_clearance_tuple(user_email, clearance_level)
        result["action"] = "created"
        result["success"] = success
        logger.info(f"FGA: Clearance tuple created for {user_email} at level {clearance_level}")
    else:
        result["action"] = "verified"
        logger.info(f"FGA: Clearance tuple already exists for {user_email} at level {clearance_level}")

    return result


# ============================================================================
# FGA Check Functions
# ============================================================================

async def check_inventory_access_via_fga(
    user_email: str,
    is_on_vacation: bool,
    role_level: int = 1,
    relation: str = "can_read",
    system_id: str = "warehouse",
) -> FGACheckResult:
    """Check one inventory permission with role/vacation contextual tuples."""
    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{system_id}"
    level = normalize_role_level(role_level)
    role_relation = ROLE_RELATIONS.get(level)

    contextual_tuples = []
    if role_relation:
        contextual_tuples.append(
            ClientTuple(user=fga_user, relation=role_relation, object=fga_object)
        )
    if is_on_vacation:
        contextual_tuples.append(
            ClientTuple(user=fga_user, relation="on_vacation", object=fga_object)
        )

    context = {
        "is_on_vacation": is_on_vacation,
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
            if is_on_vacation:
                reason = "Denied: inventory writes are blocked while the requester is on vacation."
            else:
                reason = (
                    f"Denied: {role_name(level)} (level {level}) does not satisfy {relation}."
                )

        logger.info(
            f"FGA API check: {fga_user} {relation} {fga_object} "
            f"(role={level}, vacation={is_on_vacation}, "
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
    is_on_vacation: bool = False,
    role_level: int = 1,
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
            context={"is_on_vacation": is_on_vacation, "role_level": role_level},
            reason=f"No FGA model for {agent_type} - Okta RBAC only",
            contextual_tuples=[],
        )

    if relation is None:
        relation = "can_update_standard" if "inventory:write" in scopes else "can_read"

    return await check_inventory_access_via_fga(
        user_email=user_email,
        is_on_vacation=is_on_vacation,
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
        "description": "Three ProGear role levels with a live vacation context check",
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
            "can_request_change": "Any assigned role, when not on vacation",
            "can_update_standard": "Manager or VP, when not on vacation (1-600)",
            "can_update_large": "VP, when not on vacation (601+)",
        },
        "scope_to_permission": {
            "inventory:read": {
                "fga_permission": "can_read",
                "requirements": "level 1+"
            },
            "inventory:write": {
                "fga_permission": "can_update_standard or can_update_large",
                "requirements": "level 2 through 600; level 3 at 601+"
            }
        },
        "contextual_tuples": {
            "role": "Mapped from the live Okta Clearance claim on each request",
            "vacation": "Mapped from the live Okta Vacation claim on each request",
        },
        "claims_used": [
            {"name": "Clearance", "okta_attribute": "user.clearance_level", "description": "1=Sales, 2=Manager, 3=VP"},
            {"name": "Vacation", "okta_attribute": "user.is_on_vacation", "description": "Passed as contextual tuple"},
        ],
    }


async def close_fga_client():
    """Close the FGA client connection."""
    global _fga_client
    if _fga_client is not None:
        await _fga_client.close()
        _fga_client = None
        logger.info("FGA client closed")
