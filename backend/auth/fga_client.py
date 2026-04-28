"""
Auth0 FGA Client for Agent Permission Gating

Uses FGA API with full o4aa-fga-example model combining ReBAC + ABAC.
This demonstrates "Okta + FGA Better Together":
- Okta: Identity (ID-JAG), coarse-grained RBAC (group membership), claims (Manager, Vacation, Clearance)
- FGA: Fine-grained ReBAC + ABAC (relationships, hierarchies, contextual conditions)

Key Logic - Scope-Based FGA Check:
- inventory:read  -> FGA check: can_view (active_manager)
- inventory:write -> FGA check: can_update (active_manager + has_clearance)
- inventory:alert -> NO FGA check (alert operations always allowed)

This means:
- User on vacation CANNOT VIEW or UPDATE inventory (active_manager blocks both)
- User with insufficient clearance can VIEW but CANNOT UPDATE high-sensitivity items
- Users need both manager status AND adequate clearance to update items

FGA Model (Store: ProGear New - 01KQ391VCMRKCD0G5XE92HVTQY):
  type user
  type clearance_level
    relations
      define next_higher: [clearance_level]
      define granted_to: [user]
      define holder: granted_to or holder from next_higher
  type inventory_system
    relations
      define manager: [user]
      define on_vacation: [user]
      define active_manager: manager but not on_vacation
      define can_manage: active_manager
  type inventory_item
    relations
      define parent: [inventory_system]
      define required_clearance: [clearance_level]
      define has_clearance: holder from required_clearance
      define can_view: can_manage from parent
      define can_update: has_clearance and can_manage from parent

Tuples:
- Manager roles: Pre-seeded in FGA store (user:{email} -> manager -> inventory_system:warehouse)
- Clearance grants: Pre-seeded (user:{email} -> granted_to -> clearance_level:N)
- Vacation status: Passed as contextual tuple per request (NOT stored in FGA)

Okta Claims Used (from Inventory Auth Server Access Token):
- Manager (user.is_a_manager): User is a manager (tuple must be pre-seeded in FGA)
- Vacation (user.is_on_vacation): Passed as contextual tuple at check time
- Clearance (user.clearance_level): User's clearance level (tuple must be pre-seeded in FGA)

Approach:
1. Router determines scopes based on user intent (read vs write)
2. Token exchange retrieves Auth Server token with Manager, Vacation, Clearance claims
3. FGA check runs with:
   - can_view for inventory:read
   - can_update for inventory:write (checks clearance + active_manager)
   - Vacation passed as contextual tuple if user is on vacation
4. If FGA denies, user gets clear message about vacation or clearance
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from openfga_sdk import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import ClientCheckRequest, ClientTuple, ClientWriteRequest
from openfga_sdk.credentials import Credentials, CredentialConfiguration

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
        error_str = str(e).lower()
        if "does not exist" in error_str or "not found" in error_str:
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

    # Check current state in FGA
    tuple_exists = await check_manager_tuple_exists(user_email, system_id)
    result["tuple_existed"] = tuple_exists

    if is_manager and not tuple_exists:
        # Manager claim is true but tuple doesn't exist -> create it
        success = await write_manager_tuple(user_email, system_id)
        result["action"] = "created"
        result["success"] = success
        logger.info(f"FGA: Manager tuple created for {user_email} (Manager claim=true)")

    elif not is_manager and tuple_exists:
        # Manager claim is false but tuple exists -> delete it
        success = await delete_manager_tuple(user_email, system_id)
        result["action"] = "deleted"
        result["success"] = success
        logger.info(f"FGA: Manager tuple deleted for {user_email} (Manager claim=false)")

    else:
        # No action needed - state is already correct
        logger.info(f"FGA: Manager tuple state correct for {user_email} (no action)")

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
        error_str = str(e).lower()
        if "does not exist" in error_str or "not found" in error_str or "cannot delete" in error_str:
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

    # Check current state in FGA
    tuple_exists = await check_viewer_tuple_exists(user_email, system_id)
    result["tuple_existed"] = tuple_exists

    if is_viewer and not tuple_exists:
        # Should be viewer but tuple doesn't exist -> create it
        success = await write_viewer_tuple(user_email, system_id)
        result["action"] = "created"
        result["success"] = success
        logger.info(f"FGA: Viewer tuple created for {user_email}")

    elif not is_viewer and tuple_exists:
        # Should not be viewer but tuple exists -> delete it
        success = await delete_viewer_tuple(user_email, system_id)
        result["action"] = "deleted"
        result["success"] = success
        logger.info(f"FGA: Viewer tuple deleted for {user_email}")

    else:
        # No action needed - state is already correct
        logger.info(f"FGA: Viewer tuple state correct for {user_email} (no action)")

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
        error_str = str(e).lower()
        if "does not exist" in error_str or "not found" in error_str:
            logger.info(f"FGA: Clearance tuple didn't exist for {user_email} at level {clearance_level}")
            return True
        logger.error(f"FGA delete clearance tuple failed: {e}")
        return False


async def ensure_clearance_tuple(
    user_email: str,
    clearance_level: int
) -> dict:
    """
    Ensure ONLY the current clearance tuple exists in FGA for the user.

    IMPORTANT: This function enforces single-clearance-per-user by:
    1. Deleting ALL clearance tuples (levels 1-10) except the current level
    2. Creating the current level tuple if it doesn't exist

    This prevents tuple accumulation where a user could have multiple
    clearance levels (e.g., 2, 5, 7) simultaneously in FGA.

    Args:
        user_email: User's email/login from Okta
        clearance_level: Value of Clearance claim from Okta token (1-10)

    Returns:
        Dict with action taken and success status
    """
    result = {
        "user": user_email,
        "clearance_level": clearance_level,
        "action": "none",
        "success": True,
        "deleted_levels": [],
    }

    # If no clearance, delete all clearance tuples for this user
    if clearance_level <= 0:
        logger.info(f"FGA: No clearance level for {user_email} - removing all clearance tuples")
        for level in range(1, 11):
            deleted = await delete_clearance_tuple(user_email, level)
            if deleted:
                result["deleted_levels"].append(level)
        result["action"] = "cleared_all"
        return result

    # Delete all OTHER clearance levels (1-10 except current)
    # This ensures only ONE clearance tuple exists per user
    for level in range(1, 11):
        if level != clearance_level:
            # Try to delete - will succeed if exists or already doesn't exist
            deleted = await delete_clearance_tuple(user_email, level)
            # Note: delete_clearance_tuple returns True even if tuple didn't exist

    logger.info(f"FGA: Cleaned up other clearance levels for {user_email} (keeping only level {clearance_level})")

    # Check if tuple exists at the current level
    tuple_exists = await check_clearance_tuple_exists(user_email, clearance_level)
    result["tuple_existed"] = tuple_exists

    if not tuple_exists:
        # Clearance tuple doesn't exist -> create it
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
    item_id: str = "widget-a",
    relation: str = "can_view",
    system_id: str = "warehouse",
) -> FGACheckResult:
    """
    Check inventory access using FGA API with new o4aa-fga-example model.

    Args:
        user_email: User's email/login from Okta (e.g., bob.manager@atko.email)
        is_on_vacation: From Okta 'Vacation' claim (user.is_on_vacation)
        item_id: The inventory item ID (default: widget-a)
        relation: FGA relation to check (can_view or can_update)
        system_id: The inventory system ID (default: warehouse)

    Returns:
        FGACheckResult with allowed status and explanation
    """
    fga_user = f"user:{user_email}"
    fga_object = f"inventory_item:{item_id}"
    fga_system = f"inventory_system:{system_id}"

    # Build contextual tuples - only add on_vacation if user is on vacation
    # Vacation is checked at inventory_system level (not item level)
    contextual_tuples = []
    if is_on_vacation:
        contextual_tuples.append(
            ClientTuple(
                user=fga_user,
                relation="on_vacation",
                object=fga_system  # vacation applies to system, not item
            )
        )

    context = {
        "is_on_vacation": is_on_vacation,
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
        # Build the check request
        check_request = ClientCheckRequest(
            user=fga_user,
            relation=relation,
            object=fga_object,
            contextual_tuples=contextual_tuples if contextual_tuples else None,
        )

        # Call FGA API
        response = await fga_client.check(check_request)
        allowed = response.allowed

        # Build human-readable reason
        if allowed:
            reason = f"Access granted: {user_email} has {relation} on {fga_object}"
        else:
            if is_on_vacation:
                reason = f"Access denied: {user_email} is on vacation (active_manager exclusion)"
            elif relation == "can_update":
                reason = f"Access denied: {user_email} lacks clearance or manager status for {fga_object}"
            else:
                reason = f"Access denied: {user_email} does not have {relation} on {fga_object}"

        logger.info(
            f"FGA API check: {fga_user} {relation} {fga_object} "
            f"(vacation={is_on_vacation}, contextual_tuples={len(contextual_tuples)}) -> {allowed}"
        )

        return FGACheckResult(
            allowed=allowed,
            relation=relation,
            object=fga_object,
            user=fga_user,
            context=context,
            reason=reason,
            contextual_tuples=[
                {"user": fga_user, "relation": "on_vacation", "object": fga_system}
            ] if is_on_vacation else [],
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
    item_id: str = "widget-a",
) -> FGACheckResult:
    """
    Check if a user can access a specific agent using FGA API with new model.

    Currently only inventory has FGA checks.
    Other agents pass through (return allowed=True).

    For inventory with new model:
    - inventory:read -> checks "can_view" on inventory_item (active_manager)
    - inventory:write -> checks "can_update" on inventory_item (active_manager + has_clearance)
    - inventory:alert -> pass through (no FGA check)

    Args:
        user_email: User's email/login from Okta (e.g., "bob.manager@atko.email")
        agent_type: Agent type (sales, inventory, customer, pricing)
        scopes: Requested scopes (used to determine which permission to check)
        is_on_vacation: From Okta token claim (passed as contextual tuple)
        item_id: The inventory item to check (default: widget-a)

    Returns:
        FGACheckResult with allowed status and explanation
    """
    scopes = scopes or []

    # Only inventory has FGA checks - others pass through
    if agent_type != "inventory":
        return FGACheckResult(
            allowed=True,
            relation="n/a",
            object=f"{agent_type}_system",
            user=f"user:{user_email}",
            context={"is_on_vacation": is_on_vacation},
            reason=f"No FGA model for {agent_type} - Okta RBAC only",
            contextual_tuples=[],
        )

    # Alert operations pass through - no FGA check
    if "inventory:alert" in scopes and "inventory:read" not in scopes and "inventory:write" not in scopes:
        return FGACheckResult(
            allowed=True,
            relation="n/a",
            object=f"inventory_system:warehouse",
            user=f"user:{user_email}",
            context={"is_on_vacation": is_on_vacation, "scopes": scopes},
            reason=f"Alert operation - no FGA check required",
            contextual_tuples=[],
        )

    # Determine FGA permission based on scope
    # inventory:write -> can_update (requires active_manager + has_clearance)
    # inventory:read -> can_view (requires active_manager only)
    if "inventory:write" in scopes:
        relation = "can_update"
    else:
        relation = "can_view"

    # Perform FGA check on inventory_item
    return await check_inventory_access_via_fga(
        user_email=user_email,
        is_on_vacation=is_on_vacation,
        item_id=item_id,
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
        "mode": "rebac-abac",
        "description": "Full o4aa-fga-example model with clearance hierarchy, viewer role, and delegation",
        "store_name": "ProGear New",
        "api_url": FGA_API_URL,
        "store_id": FGA_STORE_ID,
        "model_id": FGA_MODEL_ID,
        "model_types": {
            "user": "Human principals (managers, viewers)",
            "clearance_level": "Hierarchical clearance tiers (1-10)",
            "inventory_system": "Top-level resource (warehouse) with manager and viewer roles",
            "inventory_item": "Items with parent system and required clearance"
        },
        "key_relations": {
            "active_manager": "manager but not on_vacation",
            "active_viewer": "viewer but not on_vacation",
            "can_read": "active_manager or active_viewer",
            "has_clearance": "holder from required_clearance (hierarchy walk)",
            "can_view": "can_read from parent (manager OR viewer, not on vacation)",
            "can_update": "has_clearance and can_manage from parent (manager only)"
        },
        "scope_to_permission": {
            "inventory:read": {
                "fga_permission": "can_view",
                "requirements": "active_manager OR active_viewer (not on vacation)"
            },
            "inventory:write": {
                "fga_permission": "can_update",
                "requirements": "active_manager + has_clearance"
            },
            "inventory:alert": {
                "fga_permission": "n/a",
                "requirements": "No FGA check"
            }
        },
        "tuples_seeded": {
            "manager": "Dynamic based on Okta Manager claim",
            "viewer": "Dynamic for non-managers with inventory access",
            "clearance_grants": "Dynamic based on Okta Clearance claim",
            "clearance_hierarchy": "Pre-seeded (level chains)",
            "inventory_hierarchy": "Pre-seeded (system -> parent -> item)",
            "vacation": "Contextual tuple per request (NOT stored)"
        },
        "claims_used": [
            {"name": "Manager", "okta_attribute": "user.is_a_manager", "description": "Creates manager tuple if true"},
            {"name": "Vacation", "okta_attribute": "user.is_on_vacation", "description": "Passed as contextual tuple"},
            {"name": "Clearance", "okta_attribute": "user.clearance_level", "description": "Creates clearance grant tuple"}
        ],
        "viewer_role": {
            "description": "Non-managers who need read access get viewer role automatically",
            "logic": "If Manager=false and user requests inventory agent, viewer tuple is created",
            "permissions": "can_view only (cannot update even with clearance)"
        }
    }


async def close_fga_client():
    """Close the FGA client connection."""
    global _fga_client
    if _fga_client is not None:
        await _fga_client.close()
        _fga_client = None
        logger.info("FGA client closed")
