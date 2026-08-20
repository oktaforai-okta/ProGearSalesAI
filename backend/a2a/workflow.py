"""Deterministic, success-only ProGear workflow across AWS and Google agents."""

from __future__ import annotations

import re
import uuid
from typing import Protocol

from .mesh_client import MeshCoordinatorClient
from .models import (
    A2AAccessDenied,
    A2AContractError,
    A2AInvocationError,
    CustomerContext,
    InventoryReceipt,
    NotificationReceipt,
    TraceEvent,
    WorkflowResult,
)


class MeshPort(Protocol):
    async def lookup_customer(self, **kwargs): ...
    async def receive_inventory(self, **kwargs): ...
    async def notify_customer(self, **kwargs): ...


class ProGearA2AWorkflow:
    SKU = "BB-ELITE-001"
    WAREHOUSE_ID = "main_db"
    CUSTOMER_ID = "CUST-METRO-001"
    CUSTOMER_NAME = "Metro Youth League"

    def __init__(self, mesh: MeshPort | None = None) -> None:
        self.mesh = mesh or MeshCoordinatorClient()

    @staticmethod
    def matches(prompt: str) -> bool:
        text = prompt.lower()
        return (
            any(word in text for word in ("receive", "received", "add", "increase"))
            and "basketball" in text
            and "metro" in text
            and any(word in text for word in ("notify", "notification", "buyer"))
        )

    async def execute(self, prompt: str, *, user_access_token: str) -> WorkflowResult:
        quantity_match = re.search(r"\b(\d{1,5})\b", prompt.replace(",", ""))
        if not quantity_match or int(quantity_match.group(1)) <= 0:
            raise A2AContractError("The A2A inventory request needs a positive quantity")
        quantity = int(quantity_match.group(1))
        correlation_id = f"pg-{uuid.uuid4().hex[:16]}"
        inventory_key = f"{correlation_id}:inventory"
        notification_key = f"{correlation_id}:notification"
        events = [
            TraceEvent(
                step="route",
                action="Route typed work to Google Customer and AWS Inventory agents",
                status="completed",
                platform="ProGear",
                agent="ProGear Coordinator",
                scope="agent.invoke",
                correlation_id=correlation_id,
            )
        ]

        try:
            customer_payload, customer_chain = await self.mesh.lookup_customer(
                customer_id=self.CUSTOMER_ID,
                correlation_id=correlation_id,
                user_access_token=user_access_token,
            )
            customer = CustomerContext.from_payload(customer_payload)
            if not customer.notification_consent:
                raise A2AAccessDenied("customer_lookup", "Customer has no notification consent")
            events.append(TraceEvent(
                step="customer_context",
                action=f"Verified {customer.name} profile, tier, channel, and consent",
                status="completed",
                platform="Google Cloud",
                agent="Google Customer Agent",
                scope="customer:read",
                correlation_id=correlation_id,
                act_chain=customer_chain,
            ))

            inventory_payload, inventory_chain = await self.mesh.receive_inventory(
                sku=self.SKU,
                quantity=quantity,
                customer_id=customer.customer_id,
                customer_tier=customer.tier,
                correlation_id=correlation_id,
                idempotency_key=inventory_key,
                user_access_token=user_access_token,
            )
            inventory = InventoryReceipt.from_payload(
                inventory_payload,
                correlation_id=correlation_id,
                idempotency_key=inventory_key,
                warehouse_id=self.WAREHOUSE_ID,
                sku=self.SKU,
                customer_id=customer.customer_id,
                quantity=quantity,
            )
            events.append(TraceEvent(
                step="inventory_write",
                action=f"Committed {inventory.previous_quantity} → {inventory.new_quantity} and refreshed price",
                status="completed",
                platform="AWS Bedrock AgentCore",
                agent="AWS Inventory + Pricing Agent",
                scope="inventory:write",
                correlation_id=correlation_id,
                detail=f"Inventory receipt {inventory.receipt_id}; Okta write scope and AWS actor verified",
                act_chain=inventory_chain,
            ))

            notification_payload, notification_chain = await self.mesh.notify_customer(
                customer_id=customer.customer_id,
                inventory_receipt_id=inventory.receipt_id,
                correlation_id=correlation_id,
                idempotency_key=notification_key,
                user_access_token=user_access_token,
            )
            notification = NotificationReceipt.from_payload(
                notification_payload,
                idempotency_key=notification_key,
                inventory=inventory,
                customer=customer,
            )
            events.append(TraceEvent(
                step="customer_notify",
                action=f"Accepted stock-available notification via {notification.channel}",
                status="completed",
                platform="Google Cloud",
                agent="Google Customer Agent",
                scope="customer:notify",
                correlation_id=correlation_id,
                detail=f"Notification receipt {notification.receipt_id}",
                act_chain=notification_chain,
            ))

            return WorkflowResult(
                ok=True,
                content=(
                    f"Received **{inventory.received_quantity} {inventory.product_name}s** and updated "
                    f"inventory from **{inventory.previous_quantity} to {inventory.new_quantity}**. "
                    f"{customer.name}'s refreshed unit price is **${inventory.refreshed_unit_price:.2f}**. "
                    f"Their consented {notification.channel} notification was accepted "
                    f"(receipt `{notification.receipt_id}`)."
                ),
                events=events,
                inventory_receipt=inventory,
                notification_receipt=notification,
            )
        except A2AAccessDenied as exc:
            events.append(TraceEvent(
                step=exc.stage,
                action="Delegated operation denied; no downstream side effect was accepted",
                status="denied",
                platform="Okta / protected resource",
                agent="Policy enforcement",
                scope="least privilege",
                correlation_id=correlation_id,
            ))
            return WorkflowResult(
                ok=False,
                content=(
                    "Okta policy did not grant the required delegated capability. Inventory was not "
                    "changed, pricing was not refreshed, and no customer notification was sent."
                ),
                events=events,
            )
        except (A2AContractError, A2AInvocationError) as exc:
            events.append(TraceEvent(
                step=getattr(exc, "stage", "contract_validation"),
                action="Workflow failed closed before the next side effect",
                status="error",
                platform="ProGear",
                agent="ProGear Coordinator",
                scope="typed result validation",
                correlation_id=correlation_id,
                detail=str(exc),
            ))
            return WorkflowResult(
                ok=False,
                content=(
                    "The cross-platform workflow could not verify an authoritative agent result, so it "
                    "stopped before any dependent notification. Please review the execution trace."
                ),
                events=events,
            )
