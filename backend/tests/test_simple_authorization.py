import unittest

from auth.inventory_policy import decide_inventory_policy, simple_authorization_message
from auth.multi_agent_auth import AGENT_INVENTORY
from orchestrator.orchestrator import Orchestrator


def make_workflow_state(role_level: int, message: str, scope: str) -> tuple[Orchestrator, dict]:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.user_info = {
        "email": "persona@atko.email",
        "clearance_level": role_level,
        "is_on_vacation": False,
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
        "fga_checks": [{"should": "be cleared"}],
        "simulate_fga": False,
    }
    return orchestrator, state


class SimpleAuthorizationTests(unittest.TestCase):
    def decide(self, role_level: int, message: str, scope: str, vacation: bool = False):
        return decide_inventory_policy([scope], message, role_level, vacation)

    def test_sales_read_is_direct(self):
        decision = self.decide(1, "How many basketballs are in stock?", "inventory:read")
        self.assertTrue(decision.direct_allowed)
        self.assertIsNone(simple_authorization_message(decision))

    def test_sales_write_is_denied_without_approval(self):
        decision = self.decide(1, "Add 50 basketballs to inventory", "inventory:write")
        self.assertFalse(decision.direct_allowed)
        self.assertIn("contact your manager", simple_authorization_message(decision) or "")

    def test_manager_standard_write_is_direct(self):
        decision = self.decide(2, "Add 600 basketballs to inventory", "inventory:write")
        self.assertTrue(decision.direct_allowed)
        self.assertIsNone(simple_authorization_message(decision))

    def test_manager_large_write_is_denied_not_bypassed(self):
        decision = self.decide(2, "Add 601 basketballs to inventory", "inventory:write")
        self.assertFalse(decision.direct_allowed)
        self.assertIn("requires VP permission", simple_authorization_message(decision) or "")

    def test_vp_large_write_is_direct(self):
        decision = self.decide(3, "Add 601 basketballs to inventory", "inventory:write")
        self.assertTrue(decision.direct_allowed)
        self.assertIsNone(simple_authorization_message(decision))


class SimpleAuthorizationWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_sales_write_is_blocked_without_fga_or_approval(self):
        orchestrator, state = make_workflow_state(
            1,
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
            2,
            "Add 600 basketballs to inventory",
            "inventory:write",
        )
        state = await orchestrator._simple_authorization_node(state)
        self.assertEqual(state["agents_to_invoke"], [AGENT_INVENTORY])
        self.assertFalse(state["agent_results"][AGENT_INVENTORY]["access_denied"])

    async def test_manager_large_write_cannot_bypass_vp_boundary(self):
        orchestrator, state = make_workflow_state(
            2,
            "Add 601 basketballs to inventory",
            "inventory:write",
        )
        state = await orchestrator._simple_authorization_node(state)
        self.assertEqual(state["agents_to_invoke"], [])
        self.assertIn(
            "requires VP permission",
            state["agent_results"][AGENT_INVENTORY]["authorization_reason"],
        )


if __name__ == "__main__":
    unittest.main()
