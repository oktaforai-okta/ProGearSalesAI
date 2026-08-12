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

    async def test_transient_timeout_is_retried(self):
        request = httpx.Request("GET", "https://example.okta.com/api/v1/users/00u-retry")
        response = httpx.Response(
            200,
            request=request,
            json={"id": "00u-retry", "profile": {"clearance_level": 1}},
        )
        mocked_get = AsyncMock(
            side_effect=[
                httpx.ReadTimeout("temporary timeout", request=request),
                response,
            ]
        )

        with (
            patch("httpx.AsyncClient.get", mocked_get),
            patch("services.okta_role_resolver.asyncio.sleep", AsyncMock()) as mocked_sleep,
        ):
            identity = await OktaRoleResolver(
                "https://example.okta.com",
                "secret-token",
            ).resolve_identity("00u-retry")

        self.assertEqual(identity.clearance_level, 1)
        self.assertEqual(mocked_get.await_count, 2)
        mocked_sleep.assert_awaited_once_with(0.25)

    async def test_rate_limit_is_retried_using_retry_after(self):
        request = httpx.Request("GET", "https://example.okta.com/api/v1/users/00u-rate")
        rate_limited = httpx.Response(
            429,
            request=request,
            headers={"Retry-After": "0.1"},
        )
        response = httpx.Response(
            200,
            request=request,
            json={"id": "00u-rate", "profile": {"clearance_level": 0}},
        )

        with (
            patch("httpx.AsyncClient.get", AsyncMock(side_effect=[rate_limited, response])) as mocked_get,
            patch("services.okta_role_resolver.asyncio.sleep", AsyncMock()) as mocked_sleep,
        ):
            identity = await OktaRoleResolver(
                "https://example.okta.com",
                "secret-token",
            ).resolve_identity("00u-rate")

        self.assertEqual(identity.clearance_level, 0)
        self.assertEqual(mocked_get.await_count, 2)
        mocked_sleep.assert_awaited_once_with(0.1)

    async def test_non_retryable_profile_error_fails_closed_immediately(self):
        request = httpx.Request("GET", "https://example.okta.com/api/v1/users/00u-forbidden")
        forbidden = httpx.Response(403, request=request)
        mocked_get = AsyncMock(return_value=forbidden)

        with (
            patch("httpx.AsyncClient.get", mocked_get),
            patch("services.okta_role_resolver.asyncio.sleep", AsyncMock()) as mocked_sleep,
        ):
            with self.assertRaises(httpx.HTTPStatusError):
                await OktaRoleResolver(
                    "https://example.okta.com",
                    "secret-token",
                ).resolve_identity("00u-forbidden")

        mocked_get.assert_awaited_once()
        mocked_sleep.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
