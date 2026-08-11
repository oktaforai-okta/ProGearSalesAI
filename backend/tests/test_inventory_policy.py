import unittest

from auth.inventory_policy import decide_inventory_policy


class InventoryPolicyTests(unittest.TestCase):
    def test_sales_can_read(self):
        decision = decide_inventory_policy(
            ["inventory:read"], "How many basketballs are in stock?", 1, False
        )
        self.assertEqual(decision.relation, "can_read")
        self.assertFalse(decision.approval_required)
        self.assertIsNone(decision.hard_denial_reason)

    def test_sales_standard_write_routes_to_manager(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 50 basketballs to inventory", 1, False
        )
        self.assertEqual(decision.relation, "can_update_standard")
        self.assertEqual(decision.approval_role, "Manager")
        self.assertEqual(decision.approval_level, 2)

    def test_manager_standard_write_is_direct(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 600 basketballs to inventory", 2, False
        )
        self.assertEqual(decision.relation, "can_update_standard")
        self.assertFalse(decision.approval_required)

    def test_manager_601_write_routes_to_vp(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 601 basketballs to inventory", 2, False
        )
        self.assertEqual(decision.relation, "can_update_large")
        self.assertEqual(decision.approval_role, "VP")
        self.assertEqual(decision.approval_level, 3)

    def test_sales_large_write_routes_directly_to_vp(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 1000 basketballs to inventory", 1, False
        )
        self.assertEqual(decision.approval_role, "VP")

    def test_vp_large_write_is_direct(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 601 basketballs to inventory", 3, False
        )
        self.assertFalse(decision.approval_required)
        self.assertIsNone(decision.hard_denial_reason)

    def test_vacation_is_hard_denial_not_approval(self):
        decision = decide_inventory_policy(
            ["inventory:write"], "Add 50 basketballs to inventory", 2, True
        )
        self.assertFalse(decision.approval_required)
        self.assertIn("vacation", decision.hard_denial_reason or "")


if __name__ == "__main__":
    unittest.main()
