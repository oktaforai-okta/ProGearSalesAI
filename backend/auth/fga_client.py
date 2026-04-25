"""
Auth0 FGA Client for Agent Permission Gating

Uses FGA API with contextual tuples for fine-grained authorization.
This demonstrates "Okta + FGA Better Together":
- Okta: Identity (ID-JAG), coarse-grained RBAC (group membership), Manager claim
- FGA: Fine-grained, contextual authorization (runtime conditions via API)

Key Logic - Scope-Based FGA Check:
- inventory:read  -> NO FGA check (read operations always allowed)
- inventory:write -> FGA check (can_increase_inventory = manager but not on_vacation)
- inventory:alert -> NO FGA check (alert operations always allowed)

This means:
- User on vacation can VIEW inventory (read scope) ✓
- User on vacation CANNOT MODIFY inventory (write scope) ✗

Dynamic Manager Tuple Management:
1. Read "Manager" claim from Okta ID token
2. If Manager=true, ensure manager tuple exists in FGA
3. If Manager=false, delete manager tuple from FGA (if exists)
4. Then run vacation check with contextual tuple

Approach:
1. Router determines scopes based on user intent (read vs write)
2. Token exchange retrieves Auth Server token with Vacation claim
3. ensure_manager_relationship() creates/deletes manager tuple based on Okta claim
4. FGA check runs for inventory:write scope with vacation contextual tuple
5. If FGA denies, user gets clear message about vacation status

FGA Model:
  type user
  type inventory_system
    relations
      define manager: [user]
      define on_vacation: [user]
      define can_increase_inventory: manager but not on_vacation

Okta Claims Used:
- Manager (user.is_a_manager): Determines if manager tuple should exist in FGA
- Vacation (user.is_on_vacation): Passed as contextual tuple at check time
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
FGA_API_TOKEN_ISSUER = os.getenv("FGA_API_TOKEN_ISSUER", "fga.us.auth0.com")
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
# Manager Tuple Management Functions
# ============================================================================

async def check_manager_tuple_exists(
    user_email: str,
    resource_id: str = "main_db"
) -> bool:
    """
    Check if manager tuple exists in FGA store for a user.

    Uses FGA check API to verify if the user has the manager relation.

    Args:
        user_email: User's email/login from Okta
        resource_id: The inventory resource ID (default: main_db)

    Returns:
        True if tuple exists, False otherwise
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot check manager tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{resource_id}"

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
    resource_id: str = "main_db"
) -> bool:
    """
    Write manager tuple to FGA store.

    Creates: user:{email} manager inventory_system:{resource_id}

    Args:
        user_email: User's email/login from Okta
        resource_id: The inventory resource ID (default: main_db)

    Returns:
        True if successful, False otherwise
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot write manager tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{resource_id}"

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
    resource_id: str = "main_db"
) -> bool:
    """
    Delete manager tuple from FGA store.

    Removes: user:{email} manager inventory_system:{resource_id}

    Args:
        user_email: User's email/login from Okta
        resource_id: The inventory resource ID (default: main_db)

    Returns:
        True if successful (or tuple didn't exist), False on error
    """
    fga_client = _get_fga_client()
    if not fga_client:
        logger.warning("FGA client not available - cannot delete manager tuple")
        return False

    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{resource_id}"

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
    resource_id: str = "main_db"
) -> dict:
    """
    Ensure manager relationship in FGA matches the Okta Manager claim.

    - If is_manager=True and tuple doesn't exist -> create it
    - If is_manager=False and tuple exists -> delete it
    - Otherwise, no action needed

    Args:
        user_email: User's email/login from Okta
        is_manager: Value of Manager claim from Okta ID token
        resource_id: The inventory resource ID (default: main_db)

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
    tuple_exists = await check_manager_tuple_exists(user_email, resource_id)
    result["tuple_existed"] = tuple_exists

    if is_manager and not tuple_exists:
        # Manager claim is true but tuple doesn't exist -> create it
        success = await write_manager_tuple(user_email, resource_id)
        result["action"] = "created"
        result["success"] = success
        logger.info(f"FGA ensure_manager: Created tuple for {user_email} (Manager claim=true)")

    elif not is_manager and tuple_exists:
        # Manager claim is false but tuple exists -> delete it
        success = await delete_manager_tuple(user_email, resource_id)
        result["action"] = "deleted"
        result["success"] = success
        logger.info(f"FGA ensure_manager: Deleted tuple for {user_email} (Manager claim=false)")

    else:
        # No action needed - state is already correct
        if is_manager and tuple_exists:
            logger.info(f"FGA ensure_manager: Tuple already exists for {user_email} (no action)")
        else:
            logger.info(f"FGA ensure_manager: No tuple and not a manager for {user_email} (no action)")

    return result


# ============================================================================
# FGA Check Functions
# ============================================================================

async def check_inventory_access_via_fga(
    user_email: str,
    is_on_vacation: bool,
    resource_id: str = "main_db",
    relation: str = "can_increase_inventory",
) -> FGACheckResult:
    """
    Check inventory access using FGA API with contextual tuples.

    Args:
        user_email: User's email/login from Okta (e.g., bob.manager@atko.email)
        is_on_vacation: From Okta 'Vacation' claim (user.is_on_vacation)
        resource_id: The inventory resource ID (default: main_db)
        relation: FGA relation to check (default: can_increase_inventory)

    Returns:
        FGACheckResult with allowed status and explanation
    """
    fga_user = f"user:{user_email}"
    fga_object = f"inventory_system:{resource_id}"

    # Build contextual tuples - only add on_vacation if user is on vacation
    contextual_tuples = []
    if is_on_vacation:
        contextual_tuples.append(
            ClientTuple(
                user=fga_user,
                relation="on_vacation",
                object=fga_object
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
                reason = f"Access denied: {user_email} is on vacation (on_vacation tuple blocked access)"
            else:
                reason = f"Access denied: {user_email} does not have {relation} on {fga_object} (not a manager in FGA)"

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
                {"user": fga_user, "relation": "on_vacation", "object": fga_object}
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
) -> FGACheckResult:
    """
    Check if a user can access a specific agent using FGA API.

    Currently only inventory_system has FGA checks.
    Other agents pass through (return allowed=True).

    For inventory:
    - Write scopes (inventory:write) -> checks "can_increase_inventory" (manager + not on vacation)
    - Read scopes (inventory:read, inventory:alert) -> pass through (no FGA check needed)

    Args:
        user_email: User's email/login from Okta (e.g., "bob.manager@atko.email")
        agent_type: Agent type (sales, inventory, customer, pricing)
        scopes: Requested scopes (used to determine if FGA check is needed)
        is_on_vacation: From Okta token claim (passed as contextual tuple)

    Returns:
        FGACheckResult with allowed status and explanation
    """
    scopes = scopes or []

    # Only inventory has FGA checks - others pass through
    if agent_type not in AGENT_TO_FGA_OBJECT:
        return FGACheckResult(
            allowed=True,
            relation="n/a",
            object=f"{agent_type}_system",
            user=f"user:{user_email}",
            context={"is_on_vacation": is_on_vacation},
            reason=f"No FGA model for {agent_type} - Okta RBAC only",
            contextual_tuples=[],
        )

    # FGA check only applies to WRITE operations on inventory
    # Read operations (inventory:read, inventory:alert) pass through - no FGA check
    if "inventory:write" not in scopes:
        return FGACheckResult(
            allowed=True,
            relation="n/a",
            object=AGENT_TO_FGA_OBJECT[agent_type],
            user=f"user:{user_email}",
            context={"is_on_vacation": is_on_vacation, "scopes": scopes},
            reason=f"Read-only operation - FGA check not required (scopes: {', '.join(scopes)})",
            contextual_tuples=[],
        )

    # Write operation - check can_increase_inventory (manager + not on vacation)
    return await check_inventory_access_via_fga(
        user_email=user_email,
        is_on_vacation=is_on_vacation,
        relation="can_increase_inventory",
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
        "mode": "contextual-tuples",
        "description": "FGA API check with contextual tuples from Okta claims",
        "api_url": FGA_API_URL,
        "store_id": FGA_STORE_ID,
        "model_description": {
            "type": "inventory_system",
            "relations": {
                "manager": "Pre-seeded tuple: user has manager role in FGA",
                "on_vacation": "Contextual tuple: passed dynamically from Okta claim",
                "can_increase_inventory": "manager but not on_vacation"
            },
            "scope_based_check": {
                "description": "FGA check only runs for write operations",
                "inventory:read": "No FGA check - read always allowed",
                "inventory:write": "FGA check - can_increase_inventory (manager + not on vacation)",
                "inventory:alert": "No FGA check - alerts always allowed",
            },
            "contextual_tuple_logic": {
                "description": "If is_on_vacation=true AND scope=inventory:write, pass on_vacation tuple to FGA",
                "tuple_format": {
                    "user": "user:{userId}",
                    "relation": "on_vacation",
                    "object": "inventory_system:main_db"
                }
            }
        },
        "claims_used": [
            {"name": "sub", "description": "User ID for FGA user identifier"},
            {"name": "Vacation", "okta_attribute": "user.is_on_vacation", "description": "Passed as contextual tuple for write ops"},
        ]
    }


async def close_fga_client():
    """Close the FGA client connection."""
    global _fga_client
    if _fga_client is not None:
        await _fga_client.close()
        _fga_client = None
        logger.info("FGA client closed")
