import unittest

from services.intent import parse_inventory_intent


class InventoryIntentTests(unittest.TestCase):
    def test_copied_inventory_row_uses_requested_delta_and_exact_product(self):
        parsed = parse_inventory_intent(
            "Youth Adjustable Hoop – 823 units - Lets increase this by 50"
        )
        self.assertEqual(
            parsed,
            {"quantity_delta": 50, "product_name": "Youth Adjustable Hoop"},
        )

    def test_add_quantity_before_generic_product(self):
        self.assertEqual(
            parse_inventory_intent("Can you add 50 basketballs to the inventory?"),
            {"quantity_delta": 50, "product_name": "basketball"},
        )

    def test_comma_separated_delta(self):
        self.assertEqual(
            parse_inventory_intent("Increase the inventory by 1,200"),
            {"quantity_delta": 1200, "product_name": "basketball"},
        )

    def test_non_positive_quantity_is_rejected(self):
        self.assertIsNone(parse_inventory_intent("Increase inventory by 0"))


if __name__ == "__main__":
    unittest.main()
