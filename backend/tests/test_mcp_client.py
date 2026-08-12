import json
import unittest
from unittest.mock import patch

import httpx

from mcp.client import (
    MCPClient,
    MCPDiscoveryError,
    MCPToolError,
    authorization_server_id,
    protected_resource_metadata_url,
)


class _Response:
    def __init__(self, payload, *, status=200, content_type="application/json"):
        self._payload = payload
        self.status_code = status
        self.headers = {"content-type": content_type}
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://mcp.example.com/metadata")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("failure", request=request, response=response)


class _Client:
    response = None
    last_url = None
    last_json = None
    last_headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url, *, headers, timeout):
        type(self).last_url = url
        type(self).last_headers = headers
        return type(self).response

    async def post(self, url, *, json, headers, timeout):
        type(self).last_url = url
        type(self).last_json = json
        type(self).last_headers = headers
        response = type(self).response
        if callable(response):
            return response(json)
        return response


class MCPClientTests(unittest.IsolatedAsyncioTestCase):
    resource = "https://mcp.example.com/inventory/mcp"

    async def test_discovers_resource_authorization_server_and_scopes(self):
        _Client.response = _Response(
            {
                "resource": self.resource,
                "authorization_servers": ["https://tenant.okta.com/oauth2/aus123"],
                "scopes_supported": ["inventory:read", "inventory:write"],
                "resource_name": "ProGear Inventory MCP",
            }
        )
        with patch("mcp.client.httpx.AsyncClient", _Client):
            metadata = await MCPClient().discover(
                self.resource,
                required_scopes=["inventory:write"],
            )

        self.assertEqual(
            _Client.last_url,
            "https://mcp.example.com/.well-known/oauth-protected-resource/inventory/mcp",
        )
        issuer = metadata.authorization_server_for("https://tenant.okta.com")
        self.assertEqual(issuer, "https://tenant.okta.com/oauth2/aus123")
        self.assertEqual(
            authorization_server_id(issuer, "https://tenant.okta.com"),
            "aus123",
        )

    async def test_rejects_metadata_for_a_different_resource(self):
        _Client.response = _Response(
            {
                "resource": "https://mcp.example.com/other/mcp",
                "authorization_servers": ["https://tenant.okta.com/oauth2/aus123"],
                "scopes_supported": ["inventory:read"],
            }
        )
        with patch("mcp.client.httpx.AsyncClient", _Client):
            with self.assertRaisesRegex(MCPDiscoveryError, "different resource"):
                await MCPClient().discover(self.resource)

    async def test_rejects_scope_not_advertised_by_resource(self):
        _Client.response = _Response(
            {
                "resource": self.resource,
                "authorization_servers": ["https://tenant.okta.com/oauth2/aus123"],
                "scopes_supported": ["inventory:read"],
            }
        )
        with patch("mcp.client.httpx.AsyncClient", _Client):
            with self.assertRaisesRegex(MCPDiscoveryError, "inventory:write"):
                await MCPClient().discover(
                    self.resource,
                    required_scopes=["inventory:write"],
                )

    async def test_calls_tool_with_bearer_token_and_parses_sse(self):
        def response_for(request):
            payload = {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {
                    "content": [{"type": "text", "text": '{"new_quantity":150}'}]
                },
            }
            return _Response(
                f"event: message\ndata: {json.dumps(payload)}\n\n",
                content_type="text/event-stream",
            )

        _Client.response = response_for
        with patch("mcp.client.httpx.AsyncClient", _Client):
            result = await MCPClient().call_tool(
                resource_url=self.resource,
                access_token="signed-token",
                tool_name="update_inventory_quantity",
                arguments={"sku": "basketball", "quantity": 50, "operation": "increase"},
            )

        self.assertEqual(result["new_quantity"], 150)
        self.assertEqual(_Client.last_json["method"], "tools/call")
        self.assertEqual(_Client.last_headers["Authorization"], "Bearer signed-token")

    async def test_surfaces_mcp_tool_errors(self):
        def response_for(request):
            return _Response(
                {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": "scope denied"}],
                    },
                }
            )

        _Client.response = response_for
        with patch("mcp.client.httpx.AsyncClient", _Client):
            with self.assertRaisesRegex(MCPToolError, "scope denied"):
                await MCPClient().call_tool(
                    resource_url=self.resource,
                    access_token="signed-token",
                    tool_name="update_inventory_quantity",
                )

    def test_well_known_path_preserves_resource_path(self):
        self.assertEqual(
            protected_resource_metadata_url(self.resource),
            "https://mcp.example.com/.well-known/oauth-protected-resource/inventory/mcp",
        )


if __name__ == "__main__":
    unittest.main()
