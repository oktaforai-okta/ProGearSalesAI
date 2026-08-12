import unittest
from unittest.mock import AsyncMock, patch

from auth.fga_client import FGACheckResult
from auth.inventory_policy import decide_inventory_policy, simple_authorization_message
from auth.multi_agent_auth import AGENT_INVENTORY
from orchestrator.orchestrator import Orchestrator


def make_workflow_state(
    role_level: int,
    message: str,
    scope: str,
    *,
    is_on_vacation: bool = False,
) -> tuple[Orchestrator, dict]:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.user_info = {
        "email": "persona@atko.email",
        "clearance_level": role_level,
        "is_a_manager": role_level in (1, 2),
        "is_on_vacation": is_on_vacation,
    }
    state = {
        "user_message": message,
        "agents_to_invoke": [AGENT_INVENTORY],
        "agent_scopes": {AGENT_INVENTORY: [scope]},
        "agent_results": {
            AGENT_INVENTORY: {
                "success": True,
                "access_denied": False,
                "requested_scopes": [scope],
                "agent_info": {"name": "Inventory", "color": "#000"},
            }
        },
        "agent_flow": [],
        "token_exchanges": [],
        "authorization_decisions": [],
        "fga_checks": [{"should": "be cleared"}],
        "simulate_fga": False,
        "delegation_denial_reason": None,
    }
    return orchestrator, state


class SimpleAuthorizationTests(unittest.TestCase):
    def decide(self, role_level: int, message: str, scope: str):
        return decide_inventory_policy([scope], message, role_level)

    def test_sales_read_is_direct(self):
        decision = self.decide(0, "How many basketballs are in stock?", "inventory:read")
        self.assertTrue(decision.direct_allowed)
        self.assertIsNone(simple_authorization_message(decision))

    def test_sales_write_is_denied_without_approval(self):
        decision = self.decide(0, "Add 50 basketballs to inventory", "inventory:write")
        self.assertFalse(decision.direct_allowed)
        self.assertIn("contact your manager", simple_authorization_message(decision) or "")

    def test_manager_standard_write_is_direct(self):
        decision = self.decide(1, "Add 600 basketballs to inventory", "inventory:write")
        self.assertTrue(decision.direct_allowed)
        self.assertIsNone(simple_authorization_message(decision))

    def test_manager_large_write_is_denied_not_bypassed(self):
        decision = self.decide(1, "Add 601 basketballs to inventory", "inventory:write")
        self.assertFalse(decision.direct_allowed)
        self.assertIn("requires VP permission", simple_authorization_message(decision) or "")

    def test_vp_large_write_is_direct(self):
        decision = self.decide(2, "Add 601 basketballs to inventory", "inventory:write")
        self.assertTrue(decision.direct_allowed)
        self.assertIsNone(simple_authorization_message(decision))


class SimpleAuthorizationWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_vacation_stops_inventory_read_before_exchange(self):
        orchestrator, state = make_workflow_state(
            1,
            "How many basketballs are in stock?",
            "inventory:read",
            is_on_vacation=True,
        )
        state["agent_results"] = {}
        state = await orchestrator._pre_exchange_guard_node(state)

        self.assertEqual(state["agents_to_invoke"], [])
        self.assertEqual(state["token_exchanges"], [])
        self.assertEqual(
            state["agent_results"][AGENT_INVENTORY]["error_code"],
            "delegation_suspended",
        )
        self.assertFalse(state["authorization_decisions"][0]["token_issued"])
        self.assertIn("on vacation", state["delegation_denial_reason"])

    async def test_vacation_stops_write_even_with_fga_enabled(self):
        orchestrator, state = make_workflow_state(
            1,
            "Add 601 basketballs to inventory",
            "inventory:write",
            is_on_vacation=True,
        )
        state["agent_results"] = {}
        state["fga_checks"] = []
        state["simulate_fga"] = True
        state = await orchestrator._pre_exchange_guard_node(state)
        state = await orchestrator._generate_response_node(state)

        self.assertEqual(state["agents_to_invoke"], [])
        self.assertEqual(state["fga_checks"], [])
        self.assertIn("No delegated token was requested", state["final_response"])

    async def test_vacation_is_global_not_inventory_only(self):
        orchestrator, state = make_workflow_state(
            2,
            "Show recent orders",
            "sales:read",
            is_on_vacation=True,
        )
        state["agents_to_invoke"] = ["sales"]
        state["agent_scopes"] = {"sales": ["sales:read"]}
        state["agent_results"] = {}
        state = await orchestrator._pre_exchange_guard_node(state)

        self.assertEqual(state["agents_to_invoke"], [])
        self.assertEqual(state["agent_results"]["sales"]["error_code"], "delegation_suspended")

    async def test_sales_write_stops_before_exchange_in_simple_mode(self):
        orchestrator, state = make_workflow_state(
            0,
            "Can you add 50 basketballs to the inventory?",
            "inventory:write",
        )
        state["agent_results"] = {}
        state = await orchestrator._pre_exchange_guard_node(state)

        self.assertEqual(state["agents_to_invoke"], [])
        self.assertEqual(state["token_exchanges"], [])
        self.assertFalse(state["authorization_decisions"][0]["token_issued"])
        self.assertIn("contact your manager", state["authorization_decisions"][0]["reason"])

    async def test_sales_write_stops_before_exchange_with_fga_enabled(self):
        orchestrator, state = make_workflow_state(
            0,
            "Can you add 50 basketballs to the inventory?",
            "inventory:write",
        )
        state["agent_results"] = {}
        state["simulate_fga"] = True
        state = await orchestrator._pre_exchange_guard_node(state)

        self.assertEqual(state["agents_to_invoke"], [])
        self.assertEqual(state["token_exchanges"], [])
        self.assertIn(
            "contact your manager",
            state["agent_results"][AGENT_INVENTORY]["authorization_reason"],
        )

    async def test_sales_write_response_explains_clearance_and_manager(self):
        orchestrator, state = make_workflow_state(
            0,
            "Can you add 50 basketballs to the inventory?",
            "inventory:write",
        )
        state["agent_results"] = {}
        state["pending_approval"] = None
        state = await orchestrator._pre_exchange_guard_node(state)
        state = await orchestrator._generate_response_node(state)

        self.assertEqual(
            state["final_response"],
            "I didn’t change the inventory. Sales can read inventory but cannot change it. "
            "Please contact your manager to make the change.",
        )

    async def test_manager_large_write_stops_before_exchange_in_simple_mode(self):
        orchestrator, state = make_workflow_state(
            1,
            "Add 605 basketballs to inventory",
            "inventory:write",
        )
        state["agent_results"] = {}
        state = await orchestrator._pre_exchange_guard_node(state)

        self.assertEqual(state["agents_to_invoke"], [])
        self.assertEqual(state["token_exchanges"], [])
        self.assertIn("requires VP permission", state["authorization_decisions"][0]["reason"])

    async def test_manager_large_write_continues_to_fga_approval_path(self):
        orchestrator, state = make_workflow_state(
            1,
            "Add 605 basketballs to inventory",
            "inventory:write",
        )
        state["agent_results"] = {}
        state["simulate_fga"] = True
        state = await orchestrator._pre_exchange_guard_node(state)

        self.assertEqual(state["agents_to_invoke"], [AGENT_INVENTORY])
        self.assertEqual(state["authorization_decisions"], [])

    async def test_sales_read_continues_to_exchange(self):
        orchestrator, state = make_workflow_state(
            0,
            "How many basketballs are in stock?",
            "inventory:read",
        )
        state["agent_results"] = {}
        state = await orchestrator._pre_exchange_guard_node(state)

        self.assertEqual(state["agents_to_invoke"], [AGENT_INVENTORY])

    async def test_sales_write_is_blocked_without_fga_or_approval(self):
        orchestrator, state = make_workflow_state(
            0,
            "Add 50 basketballs to inventory",
            "inventory:write",
        )
        state = await orchestrator._simple_authorization_node(state)
        state = await orchestrator._approval_gate_node(state)
        self.assertEqual(state["agents_to_invoke"], [])
        self.assertEqual(state["fga_checks"], [])
        self.assertTrue(state["agent_results"][AGENT_INVENTORY]["access_denied"])
        self.assertEqual(state["agent_flow"][-1]["status"], "skipped")
        self.assertIsNone(state.get("pending_approval"))

    async def test_manager_standard_write_continues_directly(self):
        orchestrator, state = make_workflow_state(
            1,
            "Add 600 basketballs to inventory",
            "inventory:write",
        )
        state = await orchestrator._simple_authorization_node(state)
        self.assertEqual(state["agents_to_invoke"], [AGENT_INVENTORY])
        self.assertFalse(state["agent_results"][AGENT_INVENTORY]["access_denied"])

    async def test_manager_large_write_cannot_bypass_vp_boundary(self):
        orchestrator, state = make_workflow_state(
            1,
            "Add 601 basketballs to inventory",
            "inventory:write",
        )
        state = await orchestrator._simple_authorization_node(state)
        self.assertEqual(state["agents_to_invoke"], [])
        self.assertIn(
            "requires VP permission",
            state["agent_results"][AGENT_INVENTORY]["authorization_reason"],
        )

    async def test_fga_demo_uses_isolated_context_after_token_validation(self):
        orchestrator, state = make_workflow_state(
            2,
            "Add 601 basketballs to inventory",
            "inventory:write",
        )
        state["simulate_fga"] = True
        state["agent_results"][AGENT_INVENTORY].update({
            "resource_token_validated": True,
            "access_token": "signed-resource-token",
            # Mike's real token can remain Manager while this browser session
            # demonstrates the VP FGA decision.
            "token_claims": {"Clearance": 1},
        })
        state["token_exchanges"] = [{
            "agent": AGENT_INVENTORY,
            "access_token": "signed-resource-token",
            "resource_token_validated": True,
        }]
        allowed = FGACheckResult(
            allowed=True,
            relation="can_update_large",
            object="inventory_system:warehouse",
            user="user:persona@atko.email",
            context={"role_level": 2},
            reason="VP may update 601+ units",
            contextual_tuples=[],
        )

        with patch(
            "orchestrator.orchestrator.check_agent_access",
            new=AsyncMock(return_value=allowed),
        ) as mock_check:
            state = await orchestrator._fga_check_node(state)

        self.assertEqual(mock_check.await_args.kwargs["role_level"], 2)
        self.assertEqual(state["authorization_decisions"][0]["role_level"], 2)
        self.assertEqual(state["authorization_decisions"][0]["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
