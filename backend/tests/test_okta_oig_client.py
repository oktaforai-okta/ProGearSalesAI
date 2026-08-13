import unittest

import httpx

from services.okta_oig_client import OIGRateLimited, OktaOIGClient


class OktaOIGClientTests(unittest.IsolatedAsyncioTestCase):
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
