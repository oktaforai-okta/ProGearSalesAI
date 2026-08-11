import unittest

from auth.demo_admin import _manager_for_level, _reset_level, _reset_vacation, _status_values


class DemoAdminResetTests(unittest.TestCase):
    def test_named_personas_have_deterministic_reset_levels(self):
        self.assertEqual(_reset_level({"login": "sarah.sales@atko.email", "clearance_level": 2}), 0)
        self.assertEqual(_reset_level({"login": "mike.manager@atko.email", "clearance_level": 2}), 1)
        self.assertEqual(_reset_level({"login": "joe.vp@atko.email", "clearance_level": 0}), 2)

    def test_other_users_reset_to_their_starting_value(self):
        self.assertEqual(_reset_level({"login": "demo@example.com", "clearance_level": 1}), 1)

    def test_persona_defaults_are_domain_independent(self):
        self.assertEqual(_reset_level({"login": "mike.manager@customer.example", "clearance_level": 0}), 1)
        self.assertFalse(_reset_vacation({"login": "mike.manager@customer.example", "is_on_vacation": True}))

    def test_other_users_keep_their_original_vacation_value_on_reset(self):
        self.assertTrue(_reset_vacation({"login": "demo@example.com", "is_on_vacation": True}))

    def test_manager_attribute_is_derived_from_role(self):
        self.assertFalse(_manager_for_level(0))
        self.assertTrue(_manager_for_level(1))
        self.assertTrue(_manager_for_level(2))

    def test_demo_status_normalizes_manager_and_vacation(self):
        self.assertEqual(
            _status_values({
                "clearance_level": 2,
                "is_a_manager": False,
                "is_on_vacation": True,
            }),
            {"clearance_level": 2, "is_a_manager": True, "is_on_vacation": True},
        )


if __name__ == "__main__":
    unittest.main()
