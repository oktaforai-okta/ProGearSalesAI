"""Pure policy helpers for the ProGear inventory authorization story.

Okta's ``Clearance`` claim is the single role source of truth:

* 0 = Sales
* 1 = Manager
* 2 = VP

The helpers in this module deliberately contain no network calls.  The
orchestrator uses the returned FGA relation for the live FGA check and
uses ``approval_role`` to decide whether an OIG request should be created.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.intent import parse_inventory_intent


ROLE_NAMES = {0: "Sales", 1: "Manager", 2: "VP"}
ROLE_RELATIONS = {0: "role_sales", 1: "role_manager", 2: "role_vp"}
STANDARD_WRITE_LIMIT = 600


def normalize_role_level(value: object) -> int:
    """Return a supported role level, or -1 for missing/invalid values."""
    try:
        level = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return -1
    return level if level in ROLE_NAMES else -1


def role_name(level: int) -> str:
    return ROLE_NAMES.get(normalize_role_level(level), "Unassigned")


@dataclass(frozen=True)
class InventoryPolicyDecision:
    operation: str
    relation: str
    role_level: int
    role_name: str
    quantity: int | None
    required_level: int
    required_role: str
    approval_level: int | None = None
    approval_role: str | None = None
    hard_denial_reason: str | None = None

    @property
    def approval_required(self) -> bool:
        return self.approval_level is not None

    @property
    def direct_allowed(self) -> bool:
        """Whether FGA can execute directly without OIG approval routing."""
        return self.hard_denial_reason is None and not self.approval_required

    @property
    def coarse_allowed(self) -> bool:
        """Whether the request may execute when only coarse Okta access is active."""
        return self.hard_denial_reason is None


def simple_authorization_message(decision: InventoryPolicyDecision) -> str | None:
    """Return a coarse-mode denial, or None when the scoped request may run."""
    if decision.coarse_allowed:
        return None
    return f"I didn’t change the inventory. {decision.hard_denial_reason}"


def decide_inventory_policy(
    scopes: list[str],
    task: str,
    role_level: int,
) -> InventoryPolicyDecision:
    """Translate a request into the exact FGA relation and approval tier.

    FGA remains authoritative for the allow/deny result.  This policy object
    selects which relation FGA must evaluate and identifies the human approval
    tier when the user's role is intentionally below the direct-execution tier.
    """
    level = normalize_role_level(role_level)
    name = role_name(level)
    is_write = "inventory:write" in scopes

    if not is_write:
        return InventoryPolicyDecision(
            operation="read",
            relation="can_read",
            role_level=level,
            role_name=name,
            quantity=None,
            required_level=0,
            required_role="Sales",
            hard_denial_reason=None if level >= 0 else "No ProGear role is assigned in Okta.",
        )

    # Role eligibility is the coarse-grained gate and must be evaluated before
    # request details such as quantity. Sales is read-only for every inventory
    # write, so asking Sarah to supply a quantity is both misleading and an
    # unnecessary disclosure of the downstream Manager/VP policy. Likewise, a
    # user with no ProGear role must be rejected before request validation.
    if level < 0:
        return InventoryPolicyDecision(
            operation="write",
            relation="can_update_standard",
            role_level=level,
            role_name=name,
            quantity=None,
            required_level=1,
            required_role="Manager",
            hard_denial_reason="No ProGear role is assigned in Okta.",
        )

    if level == 0:
        return InventoryPolicyDecision(
            operation="write",
            relation="can_update_standard",
            role_level=level,
            role_name=name,
            quantity=None,
            required_level=1,
            required_role="Manager",
            hard_denial_reason=(
                "Sales can read inventory but cannot change it. "
                "Please contact your manager to make the change."
            ),
        )

    parsed = parse_inventory_intent(task)
    quantity = parsed.get("quantity_delta") if parsed else None
    if not isinstance(quantity, int) or quantity <= 0:
        return InventoryPolicyDecision(
            operation="write",
            relation="can_update_standard",
            role_level=level,
            role_name=name,
            quantity=None,
            required_level=1,
            required_role="Manager",
            hard_denial_reason="Include a positive quantity so the correct approval tier can be selected.",
        )

    is_large = quantity > STANDARD_WRITE_LIMIT
    required_level = 2 if is_large else 1
    required_role = ROLE_NAMES[required_level]
    relation = "can_update_large" if is_large else "can_update_standard"

    approval_level = None
    approval_role = None
    # Only a Manager crossing the 600-unit boundary may request approval.
    # Sales never creates an OIG request; a manager performs the ordinary
    # change on Sarah's behalf.
    if level == 1 and required_level == 2:
        approval_level = required_level
        approval_role = required_role

    return InventoryPolicyDecision(
        operation="write",
        relation=relation,
        role_level=level,
        role_name=name,
        quantity=quantity,
        required_level=required_level,
        required_role=required_role,
        approval_level=approval_level,
        approval_role=approval_role,
        hard_denial_reason=None,
    )
