import unittest
from unittest.mock import AsyncMock, patch

import httpx

from services.okta_role_resolver import OktaRoleResolver


class OktaRoleResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_uses_live_okta_profile_clearance(self):
        request = httpx.Request("GET", "https://example.okta.com/api/v1/users/00u123")
        response = httpx.Response(
            200,
            request=request,
            json={"profile": {"clearance_level": 0}},
        )
        mocked_get = AsyncMock(return_value=response)

        with patch("httpx.AsyncClient.get", mocked_get):
            level = await OktaRoleResolver(
                "https://example.okta.com",
                "secret-token",
            ).resolve("00u123")

        self.assertEqual(level, 0)
        mocked_get.assert_awaited_once()
        _, kwargs = mocked_get.await_args
        self.assertEqual(kwargs["headers"]["Authorization"], "SSWS secret-token")

    async def test_missing_identifier_fails_closed(self):
        level = await OktaRoleResolver(
            "https://example.okta.com",
            "secret-token",
        ).resolve("")
        self.assertEqual(level, -1)


if __name__ == "__main__":
    unittest.main()
