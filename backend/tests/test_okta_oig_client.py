import unittest

import httpx

from services.okta_oig_client import OIGRateLimited, OktaOIGClient


class OktaOIGClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_request_sends_true_requester_user_id(self):
        captured = {}

        async def handler(request):
            captured.update(__import__("json").loads(request.content))
            return httpx.Response(201, json={"id": "request-id"}, request=request)

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = OktaOIGClient("https://example.okta.com", "token", http=http)
        await client.create_request(
            request_type_id="request-type",
            subject="Inventory write",
            requester_user_id="00u12345678901234567",
            justification_field_id="justification-field",
            justification_value="because",
        )
        self.assertEqual(captured["requesterUserIds"], ["00u12345678901234567"])
        await http.aclose()

    async def test_rate_limit_exposes_retry_after(self):
        async def handler(request):
            return httpx.Response(429, headers={"Retry-After": "37"}, request=request)

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = OktaOIGClient("https://example.okta.com", "token", http=http)
        with self.assertRaises(OIGRateLimited) as raised:
            await client.get_request("request-id")
        self.assertEqual(raised.exception.retry_after, 37)
        await http.aclose()


if __name__ == "__main__":
    unittest.main()
