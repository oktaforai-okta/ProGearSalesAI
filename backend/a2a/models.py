"""Typed, fail-closed contracts for the ProGear A2A workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Literal

SCHEMA_VERSION = "1.0.0"


class A2AContractError(ValueError):
    """A task or specialist result violated the frozen business contract."""


class A2AAccessDenied(RuntimeError):
    """Okta or a protected resource denied one delegated operation."""

    def __init__(self, stage: str, message: str = "Delegated operation denied") -> None:
        super().__init__(message)
        self.stage = stage


class A2AInvocationError(RuntimeError):
    """A specialist or coordinator could not produce a verified result."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def _exact(payload: dict[str, Any], expected: set[str], label: str) -> None:
    if set(payload) != expected:
        raise A2AContractError(f"{label} fields do not match contract")


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise A2AContractError(f"{key} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class CustomerContext:
    customer_id: str
    name: str
    tier: Literal["Platinum", "Gold", "Silver", "Bronze"]
    notification_consent: bool
    preferred_channel: Literal["email", "sms"]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CustomerContext":
        _exact(
            payload,
            {
                "schema_version",
                "customer_id",
                "name",
                "tier",
                "preferred_channel",
                "notification_consent",
            },
            "Customer context",
        )
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise A2AContractError("Unsupported customer context schema")
        if payload.get("tier") not in {"Platinum", "Gold", "Silver", "Bronze"}:
            raise A2AContractError("Customer context has an invalid tier")
        if payload.get("preferred_channel") not in {"email", "sms"}:
            raise A2AContractError("Customer context has no approved channel")
        if not isinstance(payload.get("notification_consent"), bool):
            raise A2AContractError("Customer context has no consent decision")
        return cls(
            customer_id=_text(payload, "customer_id"),
            name=_text(payload, "name"),
            tier=payload["tier"],
            notification_consent=payload["notification_consent"],
            preferred_channel=payload["preferred_channel"],
        )


@dataclass(frozen=True, slots=True)
class InventoryReceipt:
    receipt_id: str
    correlation_id: str
    idempotency_key: str
    idempotent_replay: bool
    warehouse_id: str
    sku: str
    product_name: str
    customer_id: str
    customer_name: str
    previous_quantity: int
    received_quantity: int
    new_quantity: int
    base_unit_price: float
    tier_discount_percent: float
    volume_discount_percent: float
    total_discount_percent: float
    refreshed_unit_price: float

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        correlation_id: str,
        idempotency_key: str,
        warehouse_id: str,
        sku: str,
        customer_id: str,
        quantity: int,
    ) -> "InventoryReceipt":
        expected = {
            "schema_version",
            "receipt_id",
            "correlation_id",
            "idempotency_key",
            "idempotent_replay",
            "warehouse_id",
            "sku",
            "product_name",
            "customer_id",
            "customer_name",
            "previous_quantity",
            "received_quantity",
            "new_quantity",
            "base_unit_price",
            "tier_discount_percent",
            "volume_discount_percent",
            "total_discount_percent",
            "refreshed_unit_price",
        }
        _exact(payload, expected, "Inventory receipt")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise A2AContractError("Unsupported inventory receipt schema")
        integer_fields = ("previous_quantity", "received_quantity", "new_quantity")
        if any(isinstance(payload.get(k), bool) or not isinstance(payload.get(k), int) for k in integer_fields):
            raise A2AContractError("Inventory receipt has invalid quantities")
        number_fields = (
            "base_unit_price",
            "tier_discount_percent",
            "volume_discount_percent",
            "total_discount_percent",
            "refreshed_unit_price",
        )
        if any(
            isinstance(payload.get(k), bool)
            or not isinstance(payload.get(k), (int, float))
            or not math.isfinite(float(payload[k]))
            for k in number_fields
        ):
            raise A2AContractError("Inventory receipt has invalid pricing")
        receipt = cls(
            receipt_id=_text(payload, "receipt_id"),
            correlation_id=_text(payload, "correlation_id"),
            idempotency_key=_text(payload, "idempotency_key"),
            idempotent_replay=payload.get("idempotent_replay") is True,
            warehouse_id=_text(payload, "warehouse_id"),
            sku=_text(payload, "sku"),
            product_name=_text(payload, "product_name"),
            customer_id=_text(payload, "customer_id"),
            customer_name=_text(payload, "customer_name"),
            previous_quantity=payload["previous_quantity"],
            received_quantity=payload["received_quantity"],
            new_quantity=payload["new_quantity"],
            base_unit_price=float(payload["base_unit_price"]),
            tier_discount_percent=float(payload["tier_discount_percent"]),
            volume_discount_percent=float(payload["volume_discount_percent"]),
            total_discount_percent=float(payload["total_discount_percent"]),
            refreshed_unit_price=float(payload["refreshed_unit_price"]),
        )
        if (
            receipt.correlation_id != correlation_id
            or receipt.idempotency_key != idempotency_key
            or receipt.warehouse_id != warehouse_id
            or receipt.sku != sku
            or receipt.customer_id != customer_id
            or receipt.received_quantity != quantity
            or receipt.new_quantity != receipt.previous_quantity + quantity
            or receipt.previous_quantity < 0
            or receipt.refreshed_unit_price < 0
        ):
            raise A2AContractError("Inventory receipt is not bound to the authorized task")
        return receipt


@dataclass(frozen=True, slots=True)
class NotificationReceipt:
    receipt_id: str
    correlation_id: str
    idempotency_key: str
    idempotent_replay: bool
    inventory_receipt_id: str
    customer_id: str
    channel: Literal["email", "sms"]
    purpose: Literal["stock_available"]
    status: Literal["accepted"]

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
        inventory: InventoryReceipt,
        customer: CustomerContext,
    ) -> "NotificationReceipt":
        _exact(
            payload,
            {
                "schema_version",
                "receipt_id",
                "correlation_id",
                "idempotency_key",
                "idempotent_replay",
                "inventory_receipt_id",
                "customer_id",
                "channel",
                "purpose",
                "status",
            },
            "Notification receipt",
        )
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise A2AContractError("Unsupported notification receipt schema")
        receipt = cls(
            receipt_id=_text(payload, "receipt_id"),
            correlation_id=_text(payload, "correlation_id"),
            idempotency_key=_text(payload, "idempotency_key"),
            idempotent_replay=payload.get("idempotent_replay") is True,
            inventory_receipt_id=_text(payload, "inventory_receipt_id"),
            customer_id=_text(payload, "customer_id"),
            channel=payload.get("channel"),
            purpose=payload.get("purpose"),
            status=payload.get("status"),
        )
        if (
            receipt.correlation_id != inventory.correlation_id
            or receipt.idempotency_key != idempotency_key
            or receipt.inventory_receipt_id != inventory.receipt_id
            or receipt.customer_id != customer.customer_id
            or receipt.channel != customer.preferred_channel
            or receipt.purpose != "stock_available"
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

