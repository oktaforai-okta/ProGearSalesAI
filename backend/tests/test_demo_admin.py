import unittest

from auth.demo_admin import _reset_level


class DemoAdminResetTests(unittest.TestCase):
    def test_named_personas_have_deterministic_reset_levels(self):
        self.assertEqual(_reset_level({"login": "sarah.sales@atko.email", "clearance_level": 2}), 0)
        self.assertEqual(_reset_level({"login": "mike.manager@atko.email", "clearance_level": 2}), 1)
        self.assertEqual(_reset_level({"login": "joe.vp@atko.email", "clearance_level": 0}), 2)

    def test_other_users_reset_to_their_starting_value(self):
        self.assertEqual(_reset_level({"login": "demo@example.com", "clearance_level": 1}), 1)


if __name__ == "__main__":
    unittest.main()
