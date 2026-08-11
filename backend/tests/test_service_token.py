import base64
import json
import os
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from services.service_token import mint_service_token


def _b64(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _private_jwk() -> dict:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.private_numbers()
    public = numbers.public_numbers
    return {
        "kty": "RSA",
        "kid": "approval-executor-test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _b64(public.n),
        "e": _b64(public.e),
        "d": _b64(numbers.d),
        "p": _b64(numbers.p),
        "q": _b64(numbers.q),
        "dp": _b64(numbers.dmp1),
        "dq": _b64(numbers.dmq1),
        "qi": _b64(numbers.iqmp),
    }


class _Response:
    status_code = 200

    @staticmethod
    def json():
        return {"access_token": "signed-resource-token"}


class _Client:
    request_data = None
    request_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, *, data, headers, timeout):
        _ = (headers, timeout)
        type(self).request_url = url
        type(self).request_data = data
        return _Response()


class ServiceTokenTests(unittest.IsolatedAsyncioTestCase):
    async def test_does_not_fall_back_to_agent_credentials(self):
        private_jwk = _private_jwk()
        agent_only_env = {
            "OKTA_DOMAIN": "https://example.okta.com",
            "OKTA_AI_AGENT_ID": "wlp-agent",
            "OKTA_AI_AGENT_PRIVATE_KEY": json.dumps(private_jwk),
            "OKTA_INVENTORY_AUTH_SERVER_ID": "aus-inventory",
        }
        with patch.dict(os.environ, agent_only_env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "not fully configured"):
                await mint_service_token("inventory:write")

    async def test_uses_dedicated_executor_not_agent_identity(self):
        private_jwk = _private_jwk()
        env = {
            "OKTA_DOMAIN": "https://example.okta.com",
            "OKTA_AI_AGENT_ID": "wlp-agent",
            "OKTA_INVENTORY_AUTH_SERVER_ID": "aus-inventory",
            "OKTA_APPROVAL_EXECUTOR_CLIENT_ID": "0oa-approval-executor",
            "OKTA_APPROVAL_EXECUTOR_PRIVATE_KEY": json.dumps(private_jwk),
        }
        with patch.dict(os.environ, env, clear=False), patch(
            "services.service_token.httpx.AsyncClient", _Client
        ):
            token = await mint_service_token("inventory:write")

        self.assertEqual(token, "signed-resource-token")
        self.assertEqual(
            _Client.request_url,
            "https://example.okta.com/oauth2/aus-inventory/v1/token",
        )
        self.assertEqual(_Client.request_data["client_id"], "0oa-approval-executor")
        self.assertEqual(_Client.request_data["grant_type"], "client_credentials")
        claims = jwt.decode(
            _Client.request_data["client_assertion"],
            {key: private_jwk[key] for key in ("kty", "kid", "use", "alg", "n", "e")},
            algorithms=["RS256"],
            audience=_Client.request_url,
        )
        self.assertEqual(claims["iss"], "0oa-approval-executor")
        self.assertEqual(claims["sub"], "0oa-approval-executor")
        self.assertNotEqual(claims["sub"], "wlp-agent")


if __name__ == "__main__":
    unittest.main()
