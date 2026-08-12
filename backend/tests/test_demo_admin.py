import unittest
from unittest.mock import AsyncMock, patch

from auth.demo_admin import (
    _clear_demo_sessions_for_test,
    _manager_for_level,
    _reset_level,
    _reset_vacation,
    _status_values,
    get_demo_status,
    reset_demo_attributes,
    toggle_demo_attribute,
)


class DemoAdminResetTests(unittest.TestCase):
    def test_role_always_uses_the_live_okta_value(self):
        self.assertEqual(_reset_level({"login": "sarah.sales@atko.email", "clearance_level": 0}), 0)
        self.assertEqual(_reset_level({"login": "mike.manager@atko.email", "clearance_level": 1}), 1)
        self.assertEqual(_reset_level({"login": "joe.vp@atko.email", "clearance_level": 2}), 2)
        self.assertEqual(_reset_level({"login": "demo@example.com", "clearance_level": 1}), 1)

    def test_persona_vacation_default_is_domain_independent(self):
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


class DemoAdminSessionIsolationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _clear_demo_sessions_for_test()
        self.profile = {
            "login": "mike.manager@atko.email",
            "clearance_level": 1,
            "is_a_manager": True,
            "is_on_vacation": False,
        }
        self.config = patch.dict(
            "os.environ",
            {"OKTA_DOMAIN": "https://example.okta.test", "OKTA_API_TOKEN": "test-token"},
        )
        self.config.start()
        self.profile_lookup = patch(
            "auth.demo_admin._get_profile",
            new=AsyncMock(return_value=self.profile),
        )
        self.mock_get_profile = self.profile_lookup.start()

    def tearDown(self):
        self.profile_lookup.stop()
        self.config.stop()
        _clear_demo_sessions_for_test()

    async def test_same_okta_user_has_independent_browser_sessions(self):
        session_a = "11111111-1111-4111-8111-111111111111"
        session_b = "22222222-2222-4222-8222-222222222222"

        await toggle_demo_attribute("00u-mike", session_a, "is_on_vacation", True)

        status_a = await get_demo_status("00u-mike", session_a)
        status_b = await get_demo_status("00u-mike", session_b)

        self.assertEqual(status_a["clearance_level"], 1)
        self.assertTrue(status_a["is_a_manager"])
        self.assertTrue(status_a["is_on_vacation"])
        self.assertEqual(status_b["clearance_level"], 1)
        self.assertTrue(status_b["is_a_manager"])
        self.assertFalse(status_b["is_on_vacation"])
        self.assertTrue(status_a["session_isolated"])
        self.assertEqual(self.mock_get_profile.await_count, 2)

    async def test_reset_changes_only_the_selected_session(self):
        session_a = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        session_b = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

        await toggle_demo_attribute("00u-mike", session_a, "is_on_vacation", True)
        reset = await reset_demo_attributes("00u-mike", session_a)

        self.assertEqual(reset["values"]["clearance_level"], 1)
        self.assertFalse(reset["values"]["is_on_vacation"])
        self.assertFalse((await get_demo_status("00u-mike", session_b))["is_on_vacation"])

    async def test_missing_or_malformed_session_is_rejected(self):
        for session_id in ("", "short", "contains spaces", "x" * 129):
            with self.subTest(session_id=session_id):
                with self.assertRaisesRegex(ValueError, "valid FGA demo session"):
                    await get_demo_status("00u-mike", session_id)

    async def test_invalid_toggle_values_are_rejected(self):
        session_id = "33333333-3333-4333-8333-333333333333"
        with self.assertRaisesRegex(ValueError, "not toggleable"):
            await toggle_demo_attribute("00u-mike", session_id, "clearance_level", 2)
        with self.assertRaisesRegex(ValueError, "is_on_vacation"):
            await toggle_demo_attribute("00u-mike", session_id, "is_on_vacation", "false")


if __name__ == "__main__":
    unittest.main()
