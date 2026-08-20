import datetime as dt
import tempfile
import unittest

from services.approval_service import ApprovalService
from services.intent import Intent


class FakeOIG:
    def __init__(self):
        self.requests = {}
        self.created = []

    async def create_request(self, **kwargs):
        self.created.append(kwargs)
        request_id = f"request-{len(self.created)}"
        self.requests[request_id] = {
            "id": request_id,
            "requestTypeId": kwargs["request_type_id"],
            "requestStatus": "OPEN",
            "requesterUserIds": [kwargs["requester_user_id"]],
            "approvals": [{"status": "PENDING"}],
            "requesterFieldValues": [
                {"value": kwargs["justification_value"]}
            ],
        }
        return {"id": request_id}

    async def get_request(self, request_id):
        return self.requests[request_id]


async def unused_token_minter(scope):
    return f"token-for-{scope}"


class FakeStore:
    def __init__(self):
        self.quantity = 100
        self.calls = 0

    def update_inventory_quantity(self, **kwargs):
        self.calls += 1
        previous = self.quantity
        self.quantity += kwargs["quantity_change"]
        return {"previous_quantity": previous, "new_quantity": self.quantity}


class ApprovalServiceTests(unittest.IsolatedAsyncioTestCase):
    def build_service(self, oig, ledger_path, threshold=500, store=None, clock=None):
        return ApprovalService(
            oig=oig,
            demo_store=store or object(),
            mint_service_token=unused_token_minter,
            request_type_id="request-type",
            justification_field_id="justification-field",
            ledger_path=ledger_path,
            quantity_threshold=threshold,
            clock=clock or (lambda: dt.datetime(2026, 8, 13, tzinfo=dt.timezone.utc)),
        )

    async def test_fifty_unit_change_does_not_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self.build_service(FakeOIG(), f"{tmp}/ledger.json")
            self.assertFalse(
                service.should_gate(
                    "inventory:write",
                    {"quantity_delta": 50, "product_name": "Youth Adjustable Hoop"},
                )
            )

    async def test_equivalent_open_request_is_reused(self):
        intent = Intent(
            user_email="mike.manager@atko.email",
            agent="inventory",
            scope="inventory:write",
            product_name="Youth Adjustable Hoop",
            quantity_delta=600,
            original_task="Increase Youth Adjustable Hoop by 600",
            submitted_at="2026-08-13T00:00:00Z",
        )
        oig = FakeOIG()
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = f"{tmp}/ledger.json"
            service = self.build_service(oig, ledger_path)
            first_id, _ = await service.create_request(
                user_email=intent.user_email,
                requester_id="ignored",
                approver_group_name="AIAgentOwners",
                agent=intent.agent,
                scope=intent.scope,
                parsed_intent={
                    "quantity_delta": intent.quantity_delta,
                    "product_name": intent.product_name,
                },
                original_task=intent.original_task,
            )
            # Rebuild the service to prove deduplication survives a backend
            # restart through the persistent ledger.
            restarted_service = self.build_service(oig, ledger_path)
            request_id, reused_intent = await restarted_service.create_request(
                user_email=intent.user_email,
                requester_id="ignored",
                approver_group_name="AIAgentOwners",
                agent=intent.agent,
                scope=intent.scope,
                parsed_intent={
                    "quantity_delta": intent.quantity_delta,
                    "product_name": intent.product_name,
                },
                original_task="Please add another 600",
            )

        self.assertEqual(first_id, "request-1")
        self.assertEqual(request_id, first_id)
        self.assertEqual(reused_intent.quantity_delta, 600)
        self.assertEqual(len(oig.created), 1)
        self.assertEqual(oig.created[0]["requester_user_id"], "ignored")

    async def test_status_read_never_executes_approved_request(self):
        oig = FakeOIG()
        store = FakeStore()
        with tempfile.TemporaryDirectory() as tmp:
            service = self.build_service(oig, f"{tmp}/ledger.json", store=store)
            request_id, _ = await service.create_request(
                user_email="mike.manager@atko.email",
                requester_id="00u12345678901234567",
                approver_group_name="AIAgentOwners",
                agent="inventory",
                scope="inventory:write",
                parsed_intent={"quantity_delta": 600, "product_name": "basketball"},
                original_task="Add 600 basketballs",
            )
            oig.requests[request_id]["requestStatus"] = "RESOLVED"
            oig.requests[request_id]["approvals"] = [
                {"status": "COMPLETED", "decision": "APPROVED"}
            ]

            status = await service.get_status(request_id)

        self.assertEqual(status.status, "approved")
        self.assertEqual(store.calls, 0)
        self.assertEqual(store.quantity, 100)

    async def test_execution_requires_registered_request(self):
        oig = FakeOIG()
        oig.requests["unknown"] = {
            "id": "unknown",
            "requestTypeId": "request-type",
            "requestStatus": "RESOLVED",
            "approvals": [{"status": "COMPLETED", "decision": "APPROVED"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            service = self.build_service(oig, f"{tmp}/ledger.json", store=FakeStore())
            with self.assertRaises(ValueError):
                await service.execute_if_approved("unknown")

    async def test_registered_approved_request_executes_exactly_once(self):
        oig = FakeOIG()
        store = FakeStore()
        with tempfile.TemporaryDirectory() as tmp:
            service = self.build_service(oig, f"{tmp}/ledger.json", store=store)
            request_id, _ = await service.create_request(
                user_email="mike.manager@atko.email",
                requester_id="00u12345678901234567",
                approver_group_name="AIAgentOwners",
                agent="inventory",
                scope="inventory:write",
                parsed_intent={"quantity_delta": 600, "product_name": "basketball"},
                original_task="Add 600 basketballs",
            )
            oig.requests[request_id]["requestStatus"] = "RESOLVED"
            oig.requests[request_id]["approvals"] = [
                {"status": "COMPLETED", "decision": "APPROVED"}
            ]

            first = await service.execute_if_approved(request_id)
            second = await service.execute_if_approved(request_id)

        self.assertEqual(first.status, "executed")
        self.assertEqual(second.status, "executed")
        self.assertEqual(store.calls, 1)
        self.assertEqual(store.quantity, 700)

    async def test_requester_mismatch_blocks_execution(self):
        oig = FakeOIG()
        store = FakeStore()
        with tempfile.TemporaryDirectory() as tmp:
            service = self.build_service(oig, f"{tmp}/ledger.json", store=store)
            request_id, _ = await service.create_request(
                user_email="mike.manager@atko.email",
                requester_id="00u12345678901234567",
                approver_group_name="AIAgentOwners",
                agent="inventory",
                scope="inventory:write",
                parsed_intent={"quantity_delta": 600, "product_name": "basketball"},
                original_task="Add 600 basketballs",
            )
            oig.requests[request_id]["requestStatus"] = "RESOLVED"
            oig.requests[request_id]["requesterUserIds"] = ["00uSomeoneElse"]
            oig.requests[request_id]["approvals"] = [
                {"status": "COMPLETED", "decision": "APPROVED"}
            ]

            status = await service.execute_if_approved(request_id)

        self.assertEqual(status.status, "approved")
        self.assertIn("requester", status.denial_reason.lower())
        self.assertEqual(store.calls, 0)

    async def test_expired_open_request_is_not_reused(self):
        oig = FakeOIG()
        with tempfile.TemporaryDirectory() as tmp:
            now = dt.datetime(2026, 8, 13, tzinfo=dt.timezone.utc)
            service = self.build_service(oig, f"{tmp}/ledger.json", clock=lambda: now)
            first_id, _ = await service.create_request(
                user_email="mike.manager@atko.email",
                requester_id="00u12345678901234567",
                approver_group_name="AIAgentOwners",
                agent="inventory",
                scope="inventory:write",
                parsed_intent={"quantity_delta": 600, "product_name": "basketball"},
                original_task="Add 600 basketballs",
            )
            now = now + dt.timedelta(hours=2)
            second_id, _ = await service.create_request(
                user_email="mike.manager@atko.email",
                requester_id="00u12345678901234567",
                approver_group_name="AIAgentOwners",
                agent="inventory",
                scope="inventory:write",
                parsed_intent={"quantity_delta": 600, "product_name": "basketball"},
                original_task="Add 600 basketballs",
            )

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(oig.created), 2)


if __name__ == "__main__":
    unittest.main()
