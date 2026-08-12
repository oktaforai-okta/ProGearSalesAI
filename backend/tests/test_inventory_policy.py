import unittest

from auth.inventory_policy import decide_inventory_policy


class InventoryPolicyTests(unittest.TestCase):
    def test_sales_can_read(self):
        decision = decide_inventory_policy(
            ["inventory:read"], "How many basketballs are in stock?", 0
        )
        self.assertEqual(decision.relation, "can_read")
        self.assertFalse(decision.approval_required)
        self.assertIsNone(decision.hard_denial_reason)
        self.assertTrue(decision.direct_allowed)

    def test_sales_standard_write_is_denied_without_request(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 50 basketballs to inventory", 0
        )
        self.assertEqual(decision.relation, "can_update_standard")
        self.assertIsNone(decision.approval_role)
        self.assertIsNone(decision.approval_level)
        self.assertIn("contact your manager", decision.hard_denial_reason or "")
        self.assertFalse(decision.direct_allowed)

    def test_sales_write_without_quantity_is_denied_for_role_not_quantity(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Hey can you increase the inventory?", 0
        )
        self.assertEqual(decision.operation, "write")
        self.assertIsNone(decision.quantity)
        self.assertIsNone(decision.approval_role)
        self.assertIn("Sales can read inventory", decision.hard_denial_reason or "")
        self.assertIn("contact your manager", decision.hard_denial_reason or "")
        self.assertNotIn("positive quantity", decision.hard_denial_reason or "")

    def test_manager_write_without_quantity_requests_quantity(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Hey can you increase the inventory?", 1
        )
        self.assertIn("positive quantity", decision.hard_denial_reason or "")

    def test_unassigned_write_without_quantity_is_denied_for_missing_role(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Hey can you increase the inventory?", -1
        )
        self.assertEqual(
            decision.hard_denial_reason,
            "No ProGear role is assigned in Okta.",
        )

    def test_manager_standard_write_is_direct(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 600 basketballs to inventory", 1
        )
        self.assertEqual(decision.relation, "can_update_standard")
        self.assertFalse(decision.approval_required)
        self.assertTrue(decision.direct_allowed)

    def test_manager_601_write_routes_to_vp(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 601 basketballs to inventory", 1
        )
        self.assertEqual(decision.relation, "can_update_large")
        self.assertEqual(decision.approval_role, "VP")
        self.assertEqual(decision.approval_level, 2)
        self.assertFalse(decision.direct_allowed)

    def test_sales_large_write_is_denied_without_request(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 1000 basketballs to inventory", 0
        )
        self.assertIsNone(decision.approval_role)
        self.assertIn("contact your manager", decision.hard_denial_reason or "")

    def test_vp_large_write_is_direct(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 601 basketballs to inventory", 2
        )
        self.assertFalse(decision.approval_required)
        self.assertIsNone(decision.hard_denial_reason)
        self.assertTrue(decision.direct_allowed)

if __name__ == "__main__":
    unittest.main()
