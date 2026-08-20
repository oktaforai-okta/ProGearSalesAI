import unittest

from a2a.models import A2AAccessDenied
from a2a.workflow import ProGearA2AWorkflow


class FakeMesh:
    def __init__(self, *, deny_inventory=False, tamper_receipt=False):
        self.calls = []
        self.deny_inventory = deny_inventory
        self.tamper_receipt = tamper_receipt

    async def lookup_customer(self, **kwargs):
        self.calls.append(("lookup_customer", kwargs))
        return {
            "schema_version": "1.0.0",
            "customer_id": "CUST-METRO-001",
            "name": "Metro Youth League",
            "tier": "Gold",
            "notification_consent": True,
            "preferred_channel": "email",
        }, ["wlp-google-customer", "wlp-progear-coordinator"]

    async def receive_inventory(self, **kwargs):
        self.calls.append(("receive_inventory", kwargs))
        if self.deny_inventory:
            raise A2AAccessDenied("inventory_write")
        return {
            "schema_version": "1.0.0",
            "receipt_id": "INV-000001",
            "correlation_id": kwargs["correlation_id"],
            "idempotency_key": kwargs["idempotency_key"],
            "idempotent_replay": False,
            "warehouse_id": "main_db",
            "sku": "BB-TAMPERED" if self.tamper_receipt else kwargs["sku"],
            "product_name": "Elite Basketball",
            "customer_id": kwargs["customer_id"],
            "customer_name": "Metro Youth League",
            "previous_quantity": 18,
            "received_quantity": kwargs["quantity"],
            "new_quantity": 18 + kwargs["quantity"],
            "base_unit_price": 64.99,
            "tier_discount_percent": 3,
            "volume_discount_percent": 10,
            "total_discount_percent": 13,
            "refreshed_unit_price": 56.54,
        }, ["wlp-aws-inventory", "wlp-progear-coordinator"]

    async def notify_customer(self, **kwargs):
        self.calls.append(("notify_customer", kwargs))
        return {
            "schema_version": "1.0.0",
            "receipt_id": "NTF-000001",
            "correlation_id": kwargs["correlation_id"],
            "idempotency_key": kwargs["idempotency_key"],
            "idempotent_replay": False,
            "inventory_receipt_id": kwargs["inventory_receipt_id"],
            "customer_id": kwargs["customer_id"],
            "channel": "email",
            "purpose": "stock_available",
            "status": "accepted",
        }, ["wlp-google-customer", "wlp-progear-coordinator"]


class ProGearA2AWorkflowTests(unittest.IsolatedAsyncioTestCase):
    prompt = (
        "We received 50 Elite basketballs. Add them to inventory, refresh "
        "Metro Youth League's price, and notify their buyer."
    )

    def test_matches_only_the_cross_platform_story(self):
        self.assertTrue(ProGearA2AWorkflow.matches(self.prompt))
        self.assertFalse(ProGearA2AWorkflow.matches("How many basketballs are in stock?"))

    async def test_success_runs_google_then_aws_then_google_notification(self):
        mesh = FakeMesh()
        result = await ProGearA2AWorkflow(mesh).execute(
            self.prompt,
            user_access_token="user-access-token",
        )

        self.assertTrue(result.ok)
        self.assertEqual([name for name, _ in mesh.calls], [
            "lookup_customer",
            "receive_inventory",
            "notify_customer",
        ])
        self.assertEqual(result.inventory_receipt.previous_quantity, 18)
        self.assertEqual(result.inventory_receipt.new_quantity, 68)
        self.assertEqual(result.inventory_receipt.refreshed_unit_price, 56.54)
        self.assertEqual(result.notification_receipt.status, "accepted")
        self.assertEqual([event.platform for event in result.events], [
            "ProGear",
            "Google Cloud",
            "AWS Bedrock AgentCore",
            "Google Cloud",
        ])

    async def test_inventory_denial_never_calls_notification(self):
        mesh = FakeMesh(deny_inventory=True)
        result = await ProGearA2AWorkflow(mesh).execute(
            self.prompt,
            user_access_token="user-access-token",
        )

        self.assertFalse(result.ok)
        self.assertEqual([name for name, _ in mesh.calls], [
            "lookup_customer",
            "receive_inventory",
        ])
        self.assertIsNone(result.notification_receipt)
        self.assertEqual(result.events[-1].status, "denied")

    async def test_tampered_inventory_receipt_stops_before_notification(self):
        mesh = FakeMesh(tamper_receipt=True)
        result = await ProGearA2AWorkflow(mesh).execute(
            self.prompt,
            user_access_token="user-access-token",
        )

        self.assertFalse(result.ok)
        self.assertEqual([name for name, _ in mesh.calls], [
            "lookup_customer",
            "receive_inventory",
        ])
        self.assertIn("stopped", result.content)


if __name__ == "__main__":
    unittest.main()
