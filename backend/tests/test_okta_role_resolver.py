import unittest
from unittest.mock import AsyncMock, patch

import httpx

from services.okta_role_resolver import OktaRoleResolver


class OktaRoleResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_normalizes_domain_and_uses_live_profile(self):
        request = httpx.Request("GET", "https://example.okta.com/api/v1/users/00u-new-sales")
        response = httpx.Response(
            200,
            request=request,
            json={
                "id": "00u-new-sales",
                "profile": {
                    "clearance_level": 0,
                    "is_a_manager": False,
                    "is_on_vacation": False,
                },
            },
        )
        mocked_get = AsyncMock(return_value=response)

        with patch("httpx.AsyncClient.get", mocked_get):
            level = await OktaRoleResolver(
                "example.okta.com/",
                "secret-token",
            ).resolve("00u-new-sales")

        self.assertEqual(level, 0)
        mocked_get.assert_awaited_once()
        args, kwargs = mocked_get.await_args
        self.assertEqual(
            args[0],
            "https://example.okta.com/api/v1/users/00u-new-sales",
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "SSWS secret-token")

    async def test_resolve_identity_returns_immutable_okta_user_id(self):
        request = httpx.Request("GET", "https://example.okta.com/api/v1/users/mike@example.com")
        response = httpx.Response(
            200,
            request=request,
            json={
                "id": "00u-manager",
                "profile": {
                    "clearance_level": 1,
                    "is_a_manager": True,
                    "is_on_vacation": True,
                },
            },
        )

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=response)):
            identity = await OktaRoleResolver(
                "https://example.okta.com",
                "secret-token",
            ).resolve_identity("mike@example.com")

        self.assertEqual(identity.user_id, "00u-manager")
        self.assertEqual(identity.clearance_level, 1)
        self.assertTrue(identity.is_a_manager)
        self.assertTrue(identity.is_on_vacation)

    async def test_manager_flag_is_derived_from_authoritative_clearance(self):
        request = httpx.Request("GET", "https://example.okta.com/api/v1/users/00u-vp")
        response = httpx.Response(
            200,
            request=request,
            json={
                "id": "00u-vp",
                "profile": {
                    "clearance_level": 2,
                    "is_a_manager": False,
                    "is_on_vacation": "false",
                },
            },
        )

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=response)):
            identity = await OktaRoleResolver(
                "https://example.okta.com",
                "secret-token",
            ).resolve_identity("00u-vp")

        self.assertTrue(identity.is_a_manager)
        self.assertFalse(identity.is_on_vacation)

    async def test_any_manager_profile_resolves_to_level_one(self):
        request = httpx.Request("GET", "https://example.okta.com/api/v1/users/00u-new-manager")
        response = httpx.Response(
            200,
            request=request,
            json={"id": "00u-new-manager", "profile": {"clearance_level": 1}},
        )

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=response)):
            level = await OktaRoleResolver(
                "https://example.okta.com",
                "secret-token",
            ).resolve("00u-new-manager")

        self.assertEqual(level, 1)

    async def test_missing_identifier_fails_closed(self):
        resolver = OktaRoleResolver(
            "https://example.okta.com",
            "secret-token",
        )
        identity = await resolver.resolve_identity("")
        self.assertEqual(identity.clearance_level, -1)
        self.assertFalse(identity.is_a_manager)
        self.assertFalse(identity.is_on_vacation)


if __name__ == "__main__":
    unittest.main()
