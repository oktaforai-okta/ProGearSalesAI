import tempfile
import unittest
from pathlib import Path

from services.approval_service import ApprovalService
from services.intent import Intent, encode_justification


class _OIG:
    def __init__(self, raw):
        self.raw = raw
        self.create_calls = 0

    async def get_request(self, request_id):
        return self.raw

    async def create_request(self, **kwargs):
        self.create_calls += 1
        return {"id": "request-created"}


class _Store:
    def __init__(self):
        self.calls = 0

    def update_inventory_quantity(self, **kwargs):
        self.calls += 1
        return {"previous_quantity": 100, "new_quantity": 150}


async def _mint_token(scope):
    return f"token-for-{scope}"


async def _validate_token(token, scope):
    if token != f"token-for-{scope}":
        raise ValueError("token mismatch")


def _approved_raw(required_level: int, required_role: str):
    intent = Intent(
        user_email="mike.manager@example.com",
        agent="inventory",
        scope="inventory:write",
        product_name="basketball",
        quantity_delta=601,
        original_task="Add 601 basketballs to inventory",
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
            validate_service_token=_validate_token,
            request_type_id="request-type",
            justification_field_id="justification-field",
            ledger_path=ledger_path,
            resolve_approver_level=resolve_level,
        )

    async def test_manager_cannot_satisfy_vp_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _Store()
            service = self._service(
                _approved_raw(2, "VP"), store, Path(tmp) / "ledger.json", 1
            )
            status = await service.execute_if_approved("request-vp")
            self.assertEqual(status.status, "denied")
            self.assertIn("level 2", status.denial_reason or "")
            self.assertEqual(store.calls, 0)

    async def test_vp_can_satisfy_vp_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _Store()
            service = self._service(
                _approved_raw(2, "VP"), store, Path(tmp) / "ledger.json", 2
            )
            status = await service.execute_if_approved("request-vp")
            self.assertEqual(status.status, "executed")
            self.assertEqual(store.calls, 1)

    async def test_request_is_not_created_when_execution_token_preflight_fails(self):
        async def reject_token(token, scope):
            raise ValueError("resource token rejected")

        with tempfile.TemporaryDirectory() as tmp:
            oig = _OIG({})
            service = ApprovalService(
                oig=oig,
                demo_store=_Store(),
                mint_service_token=_mint_token,
                validate_service_token=reject_token,
                request_type_id="request-type",
                justification_field_id="justification-field",
                ledger_path=Path(tmp) / "ledger.json",
            )
            with self.assertRaisesRegex(ValueError, "resource token rejected"):
                await service.create_request(
                    user_email="mike.manager@example.com",
                    requester_id="00u-manager",
                    approver_group_name="ProGear-VPs",
                    agent="inventory",
                    scope="inventory:write",
                    parsed_intent={"quantity_delta": 601, "product_name": "basketball"},
                    original_task="Add 601 basketballs to inventory",
                    required_approver_role="VP",
                    required_approver_level=2,
                )
            self.assertEqual(oig.create_calls, 0)


if __name__ == "__main__":
    unittest.main()
