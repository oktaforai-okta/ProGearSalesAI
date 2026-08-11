import base64
import os
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from agents.inventory_agent import InventoryAgent
from auth.resource_token import ResourceTokenError, ResourceTokenValidator


def _b64(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class ResourceTokenValidationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = key.public_key().public_numbers()
        self.private_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        self.public_jwk = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "alg": "RS256",
            "n": _b64(public.n),
            "e": _b64(public.e),
        }
        self.env = patch.dict(
            os.environ,
            {
                "OKTA_DOMAIN": "https://example.okta.com",
                "OKTA_INVENTORY_AUTH_SERVER_ID": "aus-inventory",
                "OKTA_INVENTORY_AUDIENCE": "api://progear-inventory",
                "OKTA_AI_AGENT_ID": "wlp-agent",
            },
        )
        self.env.start()
        self.validator = ResourceTokenValidator()
        self.issuer = "https://example.okta.com/oauth2/aus-inventory"
        self.validator._jwks_cache[self.issuer] = (time.monotonic(), [self.public_jwk])

    def tearDown(self):
        self.env.stop()

    def token(self, *, scopes=None, actor="wlp-agent"):
        now = int(time.time())
        return jwt.encode(
            {
                "iss": self.issuer,
                "aud": "api://progear-inventory",
                "sub": "sarah.sales@atko.email",
                "uid": "00u-sarah",
                "cid": actor,
                "act": {"sub": actor},
                "scp": scopes or ["inventory:write"],
                "iat": now,
                "exp": now + 300,
                "jti": "resource-token-test",
            },
            self.private_pem,
            algorithm="RS256",
            headers={"kid": "test-kid"},
        )

    async def test_validates_signature_scope_agent_and_user(self):
        result = await self.validator.validate(
            self.token(),
            agent_type="inventory",
            required_scopes=["inventory:write"],
            expected_subjects=["sarah.sales@atko.email", "00u-sarah"],
        )
        self.assertEqual(result.claims["jti"], "resource-token-test")
        self.assertIn("inventory:write", result.scopes)

    async def test_rejects_missing_scope(self):
        with self.assertRaises(ResourceTokenError):
            await self.validator.validate(
                self.token(scopes=["inventory:read"]),
                agent_type="inventory",
                required_scopes=["inventory:write"],
            )

    async def test_rejects_wrong_agent(self):
        with self.assertRaises(ResourceTokenError):
            await self.validator.validate(
                self.token(actor="wlp-other"),
                agent_type="inventory",
                required_scopes=["inventory:write"],
            )

    async def test_accepts_explicit_approval_executor(self):
        result = await self.validator.validate(
            self.token(actor="0oa-approval-executor"),
            agent_type="inventory",
            required_scopes=["inventory:write"],
            expected_client_ids=["0oa-approval-executor"],
        )
        self.assertEqual(result.agent_id, "0oa-approval-executor")

    async def test_rejects_agent_token_when_executor_is_required(self):
        with self.assertRaises(ResourceTokenError):
            await self.validator.validate(
                self.token(actor="wlp-agent"),
                agent_type="inventory",
                required_scopes=["inventory:write"],
                expected_client_ids=["0oa-approval-executor"],
            )


class _Store:
    def __init__(self):
        self.calls = 0

    def get_inventory_by_name(self, _name):
        return {"sku": "BALL-001"}

    def update_inventory_quantity(self, sku, quantity_change, operation):
        self.calls += 1
        return {
            "sku": sku,
            "name": "Pro Game Basketball",
            "previous_quantity": 100,
            "new_quantity": 100 + quantity_change,
            "change": quantity_change,
            "status": "good",
        }


class InventoryWriteEnforcementTests(unittest.IsolatedAsyncioTestCase):
    def agent(self):
        agent = InventoryAgent.__new__(InventoryAgent)
        agent.agent_type = "inventory"
        agent.agent_name = "Inventory Agent"
        agent.color = "#10b981"
        agent.scopes = ["inventory:read", "inventory:write"]
        return agent

    async def test_write_without_validated_token_does_not_touch_store(self):
        store = _Store()
        with patch("agents.inventory_agent.demo_store", store):
            result = await self.agent().process(
                "Add 50 basketballs to inventory",
                context={
                    "scopes": ["inventory:write"],
                    "resource_token_validated": False,
                    "authorization_decision": {"decision": "allow"},
                },
            )
        self.assertFalse(result["success"])
        self.assertEqual(store.calls, 0)

    async def test_write_without_allow_decision_does_not_touch_store(self):
        store = _Store()
        with patch("agents.inventory_agent.demo_store", store):
            result = await self.agent().process(
                "Add 50 basketballs to inventory",
                context={
                    "scopes": ["inventory:write"],
                    "resource_token_validated": True,
                    "authorization_decision": {"decision": "deny"},
                },
            )
        self.assertFalse(result["success"])
        self.assertEqual(store.calls, 0)

    async def test_validated_allowed_write_changes_store_once(self):
        store = _Store()
        with patch("agents.inventory_agent.demo_store", store):
            result = await self.agent().process(
                "Add 50 basketballs to inventory",
                context={
                    "scopes": ["inventory:write"],
                    "resource_token_validated": True,
                    "authorization_decision": {"decision": "allow"},
                },
            )
        self.assertTrue(result["success"])
        self.assertEqual(store.calls, 1)


if __name__ == "__main__":
    unittest.main()
