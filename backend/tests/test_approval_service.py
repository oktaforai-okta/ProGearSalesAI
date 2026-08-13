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


class ApprovalServiceTests(unittest.IsolatedAsyncioTestCase):
    def build_service(self, oig, ledger_path, threshold=500):
        return ApprovalService(
            oig=oig,
            demo_store=object(),
            mint_service_token=unused_token_minter,
            request_type_id="request-type",
            justification_field_id="justification-field",
            ledger_path=ledger_path,
            quantity_threshold=threshold,
            clock=lambda: dt.datetime(2026, 8, 13, tzinfo=dt.timezone.utc),
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


if __name__ == "__main__":
    unittest.main()
