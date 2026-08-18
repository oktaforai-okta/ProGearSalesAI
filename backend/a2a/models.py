"""Typed business contracts shared by the ProGear A2A coordinator adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Literal


class A2AContractError(ValueError):
    """A specialist returned data that is unsafe to use for the next side effect."""


class A2AAccessDenied(RuntimeError):
    """Okta or the protected resource denied one delegated operation."""

    def __init__(self, stage: str, message: str = "Delegated operation denied") -> None:
        super().__init__(message)
        self.stage = stage


class A2AInvocationError(RuntimeError):
    """A specialist or coordinator could not produce a verified result."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True, slots=True)
class CustomerContext:
    customer_id: str
    name: str
    tier: str
    notification_consent: bool
    preferred_channel: Literal["email", "sms"]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CustomerContext":
        channel = payload.get("preferred_channel")
        if channel not in {"email", "sms"}:
            raise A2AContractError("Customer result has no approved notification channel")
        required = ("customer_id", "name", "tier")
        if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
            raise A2AContractError("Customer result is missing authoritative identity or tier data")
        return cls(
            customer_id=payload["customer_id"],
            name=payload["name"],
            tier=payload["tier"],
            notification_consent=payload.get("notification_consent") is True,
            preferred_channel=channel,
        )


@dataclass(frozen=True, slots=True)
class InventoryReceipt:
    receipt_id: str
    correlation_id: str
    sku: str
    product_name: str
    customer_id: str
    previous_quantity: int
    received_quantity: int
    new_quantity: int
    refreshed_unit_price: float

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        correlation_id: str,
        sku: str,
        customer_id: str,
        quantity: int,
    ) -> "InventoryReceipt":
        try:
            receipt = cls(
                receipt_id=str(payload["receipt_id"]),
                correlation_id=str(payload["correlation_id"]),
                sku=str(payload["sku"]),
                product_name=str(payload["product_name"]),
                customer_id=str(payload["customer_id"]),
                previous_quantity=int(payload["previous_quantity"]),
                received_quantity=int(payload["received_quantity"]),
                new_quantity=int(payload["new_quantity"]),
                refreshed_unit_price=float(payload["refreshed_unit_price"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise A2AContractError("Inventory agent returned no authoritative receipt") from exc

        if (
            not receipt.receipt_id.strip()
            or not receipt.product_name.strip()
            or receipt.correlation_id != correlation_id
            or receipt.sku != sku
            or receipt.customer_id != customer_id
            or receipt.received_quantity != quantity
            or receipt.new_quantity != receipt.previous_quantity + quantity
            or receipt.previous_quantity < 0
            or receipt.received_quantity <= 0
            or not math.isfinite(receipt.refreshed_unit_price)
            or receipt.refreshed_unit_price < 0
        ):
            raise A2AContractError("Inventory receipt does not match the authorized request")
        return receipt


@dataclass(frozen=True, slots=True)
class NotificationReceipt:
    receipt_id: str
    correlation_id: str
    inventory_receipt_id: str
    customer_id: str
    channel: Literal["email", "sms"]
    status: Literal["accepted"]

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        inventory: InventoryReceipt,
        customer: CustomerContext,
    ) -> "NotificationReceipt":
        try:
            receipt = cls(
                receipt_id=str(payload["receipt_id"]),
                correlation_id=str(payload["correlation_id"]),
                inventory_receipt_id=str(payload["inventory_receipt_id"]),
                customer_id=str(payload["customer_id"]),
                channel=payload["channel"],
                status=payload["status"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise A2AContractError("Customer agent returned no notification receipt") from exc

        if (
            receipt.correlation_id != inventory.correlation_id
            or receipt.inventory_receipt_id != inventory.receipt_id
            or receipt.customer_id != customer.customer_id
            or receipt.channel != customer.preferred_channel
            or receipt.status != "accepted"
        ):
            raise A2AContractError("Notification receipt is not bound to the inventory result")
        return receipt


@dataclass(slots=True)
class TraceEvent:
    step: str
    action: str
    status: Literal["processing", "completed", "denied", "error"]
    platform: str
    agent: str
    scope: str
    correlation_id: str
    detail: str | None = None
    act_chain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkflowResult:
    content: str
    events: list[TraceEvent]
    ok: bool
    inventory_receipt: InventoryReceipt | None = None
    notification_receipt: NotificationReceipt | None = None

    def trace(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]
