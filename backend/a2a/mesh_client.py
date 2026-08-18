"""Adapter for the architect team's O4AA coordinator service.

The service performs SDK-backed AI Token Exchange and platform-native invocation.
This adapter requires structured specialist outputs; it never treats answer prose
as proof that a state-changing MCP operation succeeded.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .models import A2AAccessDenied, A2AInvocationError


class MeshCoordinatorClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 60.0) -> None:
        self.base_url = (base_url or os.getenv("A2A_COORDINATOR_URL", "")).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.inventory_target = os.getenv("A2A_AWS_INVENTORY_TARGET", "aws_inventory")
        self.customer_target = os.getenv("A2A_GOOGLE_CUSTOMER_TARGET", "google_customer")

    async def lookup_customer(
        self,
        *,
        customer_name: str,
        correlation_id: str,
        user_access_token: str,
    ) -> tuple[dict[str, Any], list[str]]:
        return await self._invoke(
            target=self.customer_target,
            operation="lookup_customer",
            arguments={"customer_name": customer_name, "correlation_id": correlation_id},
            user_access_token=user_access_token,
        )

    async def receive_inventory(
        self,
        *,
        sku: str,
        quantity: int,
        customer_id: str,
        correlation_id: str,
        idempotency_key: str,
        user_access_token: str,
    ) -> tuple[dict[str, Any], list[str]]:
        return await self._invoke(
            target=self.inventory_target,
            operation="receive_inventory_and_refresh_price",
            arguments={
                "warehouse_id": "main_db",
                "sku": sku,
                "quantity": quantity,
                "customer_id": customer_id,
                "correlation_id": correlation_id,
                "idempotency_key": idempotency_key,
            },
            user_access_token=user_access_token,
        )

    async def notify_customer(
        self,
        *,
        customer_id: str,
        inventory_receipt_id: str,
        correlation_id: str,
        idempotency_key: str,
        user_access_token: str,
    ) -> tuple[dict[str, Any], list[str]]:
        return await self._invoke(
            target=self.customer_target,
            operation="notify_stock_available",
            arguments={
                "customer_id": customer_id,
                "inventory_receipt_id": inventory_receipt_id,
                "correlation_id": correlation_id,
                "idempotency_key": idempotency_key,
            },
            user_access_token=user_access_token,
        )

    async def _invoke(
        self,
        *,
        target: str,
        operation: str,
        arguments: dict[str, Any],
        user_access_token: str,
    ) -> tuple[dict[str, Any], list[str]]:
        if not self.base_url:
            raise A2AInvocationError(operation, "A2A coordinator URL is not configured")
        if not user_access_token:
            raise A2AAccessDenied(operation, "A delegated user access token is required")

        task = {"operation": operation, "arguments": arguments}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/ask",
                headers={"Authorization": f"Bearer {user_access_token}"},
                json={
                    "prompt": json.dumps(task, separators=(",", ":")),
                    "targets": [target],
                    "session_id": arguments.get("correlation_id"),
                },
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise A2AInvocationError(operation, "A2A coordinator returned a non-JSON response") from exc

        trace = body.get("trace") if isinstance(body, dict) else None
        hops = trace.get("hops", []) if isinstance(trace, dict) else []
        hop = hops[0] if len(hops) == 1 and isinstance(hops[0], dict) else {}
        if response.status_code in {401, 403} or hop.get("error_kind") in {
            "access_denied",
            "no_matching_policy",
            "invalid_scope",
        }:
            raise A2AAccessDenied(operation)
        if not response.is_success or hop.get("ok") is not True:
            raise A2AInvocationError(operation, "The delegated specialist did not complete successfully")

        # The ProGear specialist contract adds `outputs[target]` to the generic
        # architect trace. Do not fall back to `answer`: it is free-form text.
        outputs = body.get("outputs") if isinstance(body, dict) else None
        output = outputs.get(target) if isinstance(outputs, dict) else None
        if not isinstance(output, dict):
            raise A2AInvocationError(operation, "Specialist returned no structured operation result")
        act_chain = hop.get("act_chain") if isinstance(hop.get("act_chain"), list) else []
        return output, [str(actor) for actor in act_chain]
