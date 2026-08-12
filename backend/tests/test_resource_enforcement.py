import base64
import os
import time
import unittest
from unittest.mock import AsyncMock, patch

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
        metadata = type(
            "Metadata",
            (),
            {"authorization_server_for": lambda _self, _domain: self.issuer},
        )()
        discovery_client = type("DiscoveryClient", (), {})()
        discovery_client.discover = AsyncMock(return_value=metadata)
        self.discovery_patch = patch(
            "auth.resource_token.get_mcp_client",
            return_value=discovery_client,
        )
        self.discovery_patch.start()

    def tearDown(self):
        self.discovery_patch.stop()
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


class _MCPClient:
    def __init__(self):
        self.calls = 0
        self.last_call = None

    async def call_tool(self, **kwargs):
        self.calls += 1
        self.last_call = kwargs
        if kwargs["tool_name"] == "list_products":
            return {
                "count": 2,
                "products": [
                    {"sku": "BALL-001", "name": "Pro Game Basketball", "quantity": 100},
                    {"sku": "BALL-002", "name": "Youth Basketball", "quantity": 50},
                ],
            }
        return {
            "sku": "BALL-001",
            "name": "Pro Game Basketball",
            "previous_quantity": 100,
            "new_quantity": 150,
            "change": 50,
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
        mcp = _MCPClient()
        with patch("agents.inventory_agent.get_mcp_client", return_value=mcp):
            result = await self.agent().process(
                "Add 50 basketballs to inventory",
                context={
                    "scopes": ["inventory:write"],
                    "resource_token_validated": False,
                    "authorization_decision": {"decision": "allow"},
                },
            )
        self.assertFalse(result["success"])
        self.assertEqual(mcp.calls, 0)

    async def test_write_without_allow_decision_does_not_touch_store(self):
        mcp = _MCPClient()
        with patch("agents.inventory_agent.get_mcp_client", return_value=mcp):
            result = await self.agent().process(
                "Add 50 basketballs to inventory",
                context={
                    "scopes": ["inventory:write"],
                    "resource_token_validated": True,
                    "mcp_access_token": "signed-token",
                    "authorization_decision": {"decision": "deny"},
                },
            )
        self.assertFalse(result["success"])
        self.assertEqual(mcp.calls, 0)

    async def test_validated_allowed_write_changes_store_once(self):
        mcp = _MCPClient()
        with patch("agents.inventory_agent.get_mcp_client", return_value=mcp):
            result = await self.agent().process(
                "Add 50 basketballs to inventory",
                context={
                    "scopes": ["inventory:write"],
                    "resource_token_validated": True,
                    "mcp_access_token": "signed-token",
                    "authorization_decision": {"decision": "allow"},
                },
            )
        self.assertTrue(result["success"])
        self.assertEqual(mcp.calls, 1)
        self.assertEqual(mcp.last_call["tool_name"], "update_inventory_quantity")
        self.assertEqual(mcp.last_call["arguments"]["quantity"], 50)

    async def test_basketball_read_is_exact_and_does_not_call_an_llm(self):
        mcp = _MCPClient()
        with patch("agents.inventory_agent.get_mcp_client", return_value=mcp):
            result = await self.agent().process(
                "How many basketballs are in stock?",
                context={
                    "scopes": ["inventory:read"],
                    "resource_token_validated": True,
                    "mcp_access_token": "signed-token",
                },
            )

        self.assertTrue(result["success"])
        self.assertTrue(result["response_is_final"])
        self.assertIn("**150 basketballs in stock across 2 products**", result["result"])
        self.assertIn("| Pro Game Basketball | BALL-001 | 100 |", result["result"])
        self.assertIn("| Youth Basketball | BALL-002 | 50 |", result["result"])
        self.assertEqual(mcp.last_call["tool_name"], "list_products")


if __name__ == "__main__":
    unittest.main()
