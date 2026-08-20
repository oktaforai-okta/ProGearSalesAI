import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from a2a.api import A2AExecuteRequest, execute_request
from a2a.models import (
    InventoryReceipt,
    NotificationReceipt,
    TraceEvent,
    WorkflowResult,
)


class AcceptingVerifier:
    def verify(self, token):
        if token != "verified-user-token":
            raise AssertionError("unexpected token")
        return {"sub": "00u-mike"}


class SuccessfulWorkflow:
    @staticmethod
    def matches(message):
        return "basketballs" in message

    async def execute(self, message, *, user_access_token):
        if user_access_token != "verified-user-token":
            raise AssertionError("workflow did not receive the verified token")
        inventory = InventoryReceipt(
            receipt_id="INV-1",
            correlation_id="pg-test",
            idempotency_key="pg-test:inventory",
            idempotent_replay=False,
            warehouse_id="main_db",
            sku="BB-ELITE-001",
            product_name="Elite Basketball",
            customer_id="CUST-METRO-001",
            customer_name="Metro Youth League",
            previous_quantity=18,
            received_quantity=50,
            new_quantity=68,
            base_unit_price=64.99,
            tier_discount_percent=3,
            volume_discount_percent=10,
            total_discount_percent=13,
            refreshed_unit_price=56.54,
        )
        notification = NotificationReceipt(
            receipt_id="NTF-1",
            correlation_id="pg-test",
            idempotency_key="pg-test:notification",
            idempotent_replay=False,
            inventory_receipt_id="INV-1",
            customer_id="CUST-METRO-001",
            channel="email",
            purpose="stock_available",
            status="accepted",
        )
        return WorkflowResult(
            ok=True,
            content="Inventory and notification completed.",
            events=[TraceEvent(
                step="inventory_write",
                action="Committed 18 → 68",
                status="completed",
                platform="AWS Bedrock AgentCore",
                agent="AWS Inventory + Pricing Agent",
                scope="inventory:write",
                correlation_id="pg-test",
            )],
            inventory_receipt=inventory,
            notification_receipt=notification,
        )


class A2AApiTests(unittest.IsolatedAsyncioTestCase):
    env = {
        "PROGEAR_A2A_ENABLED": "true",
        "A2A_USER_ISSUER": "https://example.okta.com/oauth2/aus-test",
        "A2A_COORDINATOR_RESOURCE": "https://agents.progear.example/coordinator",
    }

    async def test_execute_returns_receipts_without_credentials(self):
        with patch.dict(os.environ, self.env, clear=False):
            payload = await execute_request(
                A2AExecuteRequest(message="Receive 50 basketballs and notify Metro"),
                "Bearer verified-user-token",
                verifier_factory=AcceptingVerifier,
                workflow_factory=SuccessfulWorkflow,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["inventory_receipt"]["new_quantity"], 68)
        self.assertEqual(payload["notification_receipt"]["status"], "accepted")
        rendered = str(payload).lower()
        self.assertNotIn("verified-user-token", rendered)
        self.assertNotIn("access_token", rendered)
        self.assertNotIn("id_jag", rendered)

    async def test_execute_requires_bearer_authentication(self):
        with patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(HTTPException) as caught:
                await execute_request(
                    A2AExecuteRequest(message="Receive 50 basketballs and notify Metro"),
                    None,
                    verifier_factory=AcceptingVerifier,
                    workflow_factory=SuccessfulWorkflow,
                )
        self.assertEqual(caught.exception.status_code, 401)

    async def test_execute_is_fail_closed_when_disabled(self):
        with patch.dict(os.environ, {"PROGEAR_A2A_ENABLED": "false"}, clear=False):
            with self.assertRaises(HTTPException) as caught:
                await execute_request(
                    A2AExecuteRequest(message="Receive 50 basketballs and notify Metro"),
                    "Bearer verified-user-token",
                    verifier_factory=AcceptingVerifier,
                    workflow_factory=SuccessfulWorkflow,
                )
        self.assertEqual(caught.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
