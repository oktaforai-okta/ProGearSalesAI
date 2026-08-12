import tempfile
import unittest
from pathlib import Path

from services.approval_service import ApprovalService
from services.intent import Intent, encode_justification
from services.okta_oig_client import OIGUnavailable


class _OIG:
    def __init__(self, raw):
        self.raw = raw
        self.create_calls = 0
        self.create_kwargs = None
        self.get_calls = 0
        self.unavailable = False

    async def get_request(self, request_id):
        self.get_calls += 1
        if self.unavailable:
            raise OIGUnavailable("rate limited")
        return self.raw

    async def create_request(self, **kwargs):
        self.create_calls += 1
        self.create_kwargs = kwargs
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


def _approved_raw(
    required_level: int | None,
    required_role: str,
    required_group: str | None = None,
):
    intent = Intent(
        user_email="mike.manager@example.com",
        agent="inventory",
        scope="inventory:write",
        product_name="basketball",
        quantity_delta=601,
        original_task="Add 601 basketballs to inventory",
        submitted_at="2026-08-10T00:00:00Z",
        agent_id="wlp-agent",
        required_approver_role=required_role,
        required_approver_level=required_level,
        required_approver_group=required_group,
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
    def _service(
        self,
        raw,
        store,
        ledger_path,
        resolved_level,
        group_member: bool | None = None,
    ):
        async def resolve_level(approver):
            self.assertEqual(approver["id"], "00u-approver")
            return resolved_level

        async def verify_group(approver, group_name):
            self.assertEqual(approver["id"], "00u-approver")
            self.assertEqual(group_name, "AIAgentOwners")
            return bool(group_member)

        return ApprovalService(
            oig=_OIG(raw),
            demo_store=store,
            mint_service_token=_mint_token,
            validate_service_token=_validate_token,
            request_type_id="request-type",
            justification_field_id="justification-field",
            ledger_path=ledger_path,
            resolve_approver_level=resolve_level,
            verify_approver_group=verify_group if group_member is not None else None,
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

    async def test_ai_agent_owner_can_satisfy_owner_group_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _Store()
            service = self._service(
                _approved_raw(None, "AI Agent Owner", "AIAgentOwners"),
                store,
                Path(tmp) / "ledger.json",
                resolved_level=-1,
                group_member=True,
            )
            status = await service.execute_if_approved("request-owner")
            self.assertEqual(status.status, "executed")
            self.assertEqual(store.calls, 1)

    async def test_non_owner_cannot_satisfy_owner_group_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _Store()
            service = self._service(
                _approved_raw(None, "AI Agent Owner", "AIAgentOwners"),
                store,
                Path(tmp) / "ledger.json",
                resolved_level=2,
                group_member=False,
            )
            status = await service.execute_if_approved("request-owner")
            self.assertEqual(status.status, "denied")
            self.assertIn("AIAgentOwners", status.denial_reason or "")
            self.assertEqual(store.calls, 0)

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
                    approver_group_name="AIAgentOwners",
                    agent="inventory",
                    scope="inventory:write",
                    parsed_intent={"quantity_delta": 601, "product_name": "basketball"},
                    original_task="Add 601 basketballs to inventory",
                    required_approver_role="AI Agent Owner",
                    required_approver_level=None,
                )
            self.assertEqual(oig.create_calls, 0)

    async def test_request_preserves_signed_in_employee_as_oig_requester(self):
        with tempfile.TemporaryDirectory() as tmp:
            oig = _OIG({})
            service = ApprovalService(
                oig=oig,
                demo_store=_Store(),
                mint_service_token=_mint_token,
                validate_service_token=_validate_token,
                request_type_id="request-type",
                justification_field_id="justification-field",
                ledger_path=Path(tmp) / "ledger.json",
            )
            request_id, _ = await service.create_request(
                user_email="mike.manager@example.com",
                requester_id="00u-manager",
                approver_group_name="AIAgentOwners",
                agent="inventory",
                scope="inventory:write",
                parsed_intent={"quantity_delta": 601, "product_name": "basketball"},
                original_task="Add 601 basketballs to inventory",
                required_approver_role="AI Agent Owner",
                required_approver_level=None,
            )
            self.assertEqual(request_id, "request-created")
            self.assertEqual(oig.create_kwargs["requester_id"], "00u-manager")
            justification = oig.create_kwargs["justification_value"]
            self.assertNotIn("[INTENT_JSON]", justification)
            self.assertIn("Requested for: mike.manager@example.com", justification)
            self.assertIn("Action: Add 601 basketballs to inventory", justification)
            self.assertIn("Reason: Exceeds the Manager limit of 600 units", justification)
            self.assertIn("Required approval: AI Agent Owner (AIAgentOwners)", justification)
            self.assertEqual(service.pending_request_ids(), ["request-created"])

            created_intent = service._ledger.get("request-created").intent
            self.assertEqual(created_intent["required_approver_group"], "AIAgentOwners")

            # New requests recover the action from the private ledger; OIG no
            # longer needs to expose machine-readable JSON to the approver.
            oig.raw = {
                "requestStatus": "OPEN",
                "requesterFieldValues": [{"value": justification}],
                "approvals": [{"status": "PENDING"}],
            }
            restarted_service = ApprovalService(
                oig=oig,
                demo_store=_Store(),
                mint_service_token=_mint_token,
                validate_service_token=_validate_token,
                request_type_id="request-type",
                justification_field_id="justification-field",
                ledger_path=Path(tmp) / "ledger.json",
            )
            status = await restarted_service.get_status(request_id)
            self.assertIsNotNone(status.intent)
            self.assertEqual(status.intent.quantity_delta, 601)

    async def test_legacy_request_intent_still_decodes_from_justification(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = _approved_raw(2, "VP")
            service = self._service(raw, _Store(), Path(tmp) / "ledger.json", 2)
            status = await service.get_status("legacy-request")
            self.assertIsNotNone(status.intent)
            self.assertEqual(status.intent.required_approver_role, "VP")
            self.assertEqual(status.intent.quantity_delta, 601)

    async def test_status_cache_collapses_duplicate_oig_polls_and_serves_stale_on_429(self):
        with tempfile.TemporaryDirectory() as tmp:
            oig = _OIG({"requestStatus": "OPEN", "approvals": [{"status": "PENDING"}]})
            service = ApprovalService(
                oig=oig,
                demo_store=_Store(),
                mint_service_token=_mint_token,
                validate_service_token=_validate_token,
                request_type_id="request-type",
                justification_field_id="justification-field",
                ledger_path=Path(tmp) / "ledger.json",
                status_cache_ttl_seconds=60,
            )
            first = await service.execute_if_approved("request-pending")
            second = await service.execute_if_approved("request-pending")
            self.assertEqual(first.status, "pending")
            self.assertEqual(second.status, "pending")
            self.assertEqual(oig.get_calls, 1)

            service._status_cache_ttl = 0
            oig.unavailable = True
            stale = await service.execute_if_approved("request-pending")
            self.assertEqual(stale.status, "pending")
            self.assertTrue(stale.poll_error)
            self.assertEqual(oig.get_calls, 2)


if __name__ == "__main__":
    unittest.main()
