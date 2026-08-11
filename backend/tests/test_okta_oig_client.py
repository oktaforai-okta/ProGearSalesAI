import json
import unittest

import httpx

from services.okta_oig_client import OktaOIGClient, OIGUnavailable


class OktaOIGClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_request_sends_explicit_requester_user_id(self):
        captured = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={"id": "request-1"})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = OktaOIGClient("https://example.okta.com", "secret", http=http)
        try:
            response = await client.create_request(
                request_type_id="request-type",
                subject="Inventory write: +601 basketball",
                requester_id="00u-manager",
                justification_field_id="justification",
                justification_value="Please approve",
            )
        finally:
            await http.aclose()

        self.assertEqual(response["id"], "request-1")
        self.assertEqual(captured["requesterUserIds"], ["00u-manager"])

    async def test_rate_limit_is_treated_as_temporary_unavailability(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "12"}, json={})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = OktaOIGClient("https://example.okta.com", "secret", http=http)
        try:
            with self.assertRaisesRegex(OIGUnavailable, "retry after 12s"):
                await client.get_request("request-1")
        finally:
            await http.aclose()


if __name__ == "__main__":
    unittest.main()
