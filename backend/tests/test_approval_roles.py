import tempfile
import unittest
from pathlib import Path

from services.approval_service import ApprovalService
from services.intent import Intent, encode_justification


class _OIG:
    def __init__(self, raw):
        self.raw = raw

    async def get_request(self, request_id):
        return self.raw


class _Store:
    def __init__(self):
        self.calls = 0

    def update_inventory_quantity(self, **kwargs):
        self.calls += 1
        return {"previous_quantity": 100, "new_quantity": 150}


async def _mint_token(scope):
    return f"token-for-{scope}"


def _approved_raw(required_level: int, required_role: str):
    intent = Intent(
        user_email="sarah.sales@example.com",
        agent="inventory",
        scope="inventory:write",
        product_name="basketball",
        quantity_delta=50,
        original_task="Add 50 basketballs to inventory",
        submitted_at="2026-08-10T00:00:00Z",
        required_approver_role=required_role,
        required_approver_level=required_level,
    )
    return {
        "requestStatus": "RESOLVED",
        "requesterFieldValues": [
            {"value": encode_justification("Approval test", intent)}
        ],
        "approvals": [
            {
                "decision": "APPROVED",
                "approverId": "00u-approver",
                "updatedAt": "2026-08-10T00:01:00Z",
            }
        ],
    }


class ApprovalRoleTests(unittest.IsolatedAsyncioTestCase):
    def _service(self, raw, store, ledger_path, resolved_level):
        async def resolve_level(approver):
            self.assertEqual(approver["id"], "00u-approver")
            return resolved_level

        return ApprovalService(
            oig=_OIG(raw),
            demo_store=store,
            mint_service_token=_mint_token,
            request_type_id="request-type",
            justification_field_id="justification-field",
            ledger_path=ledger_path,
            resolve_approver_level=resolve_level,
        )

    async def test_manager_can_satisfy_manager_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _Store()
            service = self._service(
                _approved_raw(2, "Manager"), store, Path(tmp) / "ledger.json", 2
            )
            status = await service.execute_if_approved("request-manager")
            self.assertEqual(status.status, "executed")
            self.assertEqual(store.calls, 1)

    async def test_manager_cannot_satisfy_vp_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _Store()
            service = self._service(
                _approved_raw(3, "VP"), store, Path(tmp) / "ledger.json", 2
            )
            status = await service.execute_if_approved("request-vp")
            self.assertEqual(status.status, "denied")
            self.assertIn("level 3", status.denial_reason or "")
            self.assertEqual(store.calls, 0)

    async def test_vp_can_satisfy_vp_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _Store()
            service = self._service(
                _approved_raw(3, "VP"), store, Path(tmp) / "ledger.json", 3
            )
            status = await service.execute_if_approved("request-vp")
            self.assertEqual(status.status, "executed")
            self.assertEqual(store.calls, 1)


if __name__ == "__main__":
    unittest.main()
