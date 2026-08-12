"""Minimal native Streamable HTTP MCP client with RFC 9728 discovery.

The protected-resource URL is the source of truth.  Before Okta issues a
delegated token, ProGear reads that resource's well-known metadata to learn
which authorization server protects it and which scopes it supports.  The
resulting access token is then presented directly to the MCP server in a
standard JSON-RPC ``tools/call`` request.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import httpx


class MCPDiscoveryError(RuntimeError):
    """Raised when protected-resource metadata is unavailable or invalid."""


class MCPToolError(RuntimeError):
    """Raised when an MCP endpoint or tool returns an error."""


@dataclass(frozen=True)
class MCPProtectedResourceMetadata:
    resource: str
    authorization_servers: tuple[str, ...]
    scopes_supported: tuple[str, ...]
    resource_name: str | None = None

    def authorization_server_for(self, okta_domain: str) -> str:
        domain = okta_domain.rstrip("/")
        matches = [
            issuer.rstrip("/")
            for issuer in self.authorization_servers
            if issuer.rstrip("/").startswith(f"{domain}/oauth2/")
        ]
        if len(matches) != 1:
            raise MCPDiscoveryError(
                "The MCP resource must advertise exactly one authorization "
                "server in the configured Okta org."
            )
        return matches[0]


def protected_resource_metadata_url(resource_url: str) -> str:
    """Build the RFC 9728 path-form well-known URL for an MCP resource."""
    parsed = urlsplit(resource_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MCPDiscoveryError("The MCP resource URL must be an absolute HTTP URL.")
    resource_path = parsed.path.rstrip("/")
    well_known_path = f"/.well-known/oauth-protected-resource{resource_path}"
    return urlunsplit((parsed.scheme, parsed.netloc, well_known_path, "", ""))


def authorization_server_id(issuer: str, okta_domain: str) -> str:
    """Extract the Okta authorization-server id from a discovered issuer."""
    issuer_parts = urlsplit(issuer.rstrip("/"))
    domain_parts = urlsplit(okta_domain.rstrip("/"))
    if (issuer_parts.scheme, issuer_parts.netloc) != (
        domain_parts.scheme,
        domain_parts.netloc,
    ):
        raise MCPDiscoveryError("The MCP resource advertised a different Okta org.")
    segments = [segment for segment in issuer_parts.path.split("/") if segment]
    if len(segments) != 2 or segments[0] != "oauth2" or not segments[1]:
        raise MCPDiscoveryError(
            "The MCP resource advertised an unsupported authorization-server issuer."
        )
    return segments[1]


class MCPClient:
    """Small client for the subset of MCP used by this demo."""

    def __init__(self, *, timeout_seconds: float = 15.0, cache_ttl_seconds: int = 300):
        self._timeout = timeout_seconds
        self._cache_ttl = cache_ttl_seconds
        self._metadata_cache: dict[str, tuple[float, MCPProtectedResourceMetadata]] = {}
        self._lock = asyncio.Lock()

    async def discover(
        self,
        resource_url: str,
        *,
        required_scopes: Iterable[str] = (),
        refresh: bool = False,
    ) -> MCPProtectedResourceMetadata:
        now = time.monotonic()
        cached = self._metadata_cache.get(resource_url)
        if not refresh and cached and now - cached[0] < self._cache_ttl:
            metadata = cached[1]
        else:
            async with self._lock:
                cached = self._metadata_cache.get(resource_url)
                if not refresh and cached and now - cached[0] < self._cache_ttl:
                    metadata = cached[1]
                else:
                    url = protected_resource_metadata_url(resource_url)
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                url,
                                headers={"Accept": "application/json"},
                                timeout=self._timeout,
                            )
                            response.raise_for_status()
                    except httpx.HTTPError as exc:
                        raise MCPDiscoveryError(
                            f"MCP protected-resource discovery failed: {exc}"
                        ) from exc
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise MCPDiscoveryError(
                            "The MCP protected-resource metadata is not valid JSON."
                        ) from exc
                    if payload.get("resource", "").rstrip("/") != resource_url.rstrip("/"):
                        raise MCPDiscoveryError(
                            "The MCP protected-resource metadata identifies a different resource."
                        )
                    issuers = payload.get("authorization_servers") or []
                    scopes = payload.get("scopes_supported") or []
                    if not isinstance(issuers, list) or not issuers:
                        raise MCPDiscoveryError(
                            "The MCP resource did not advertise an authorization server."
                        )
                    if not isinstance(scopes, list):
                        raise MCPDiscoveryError(
                            "The MCP resource advertised an invalid scope list."
                        )
                    metadata = MCPProtectedResourceMetadata(
                        resource=str(payload["resource"]).rstrip("/"),
                        authorization_servers=tuple(str(value).rstrip("/") for value in issuers),
                        scopes_supported=tuple(str(value) for value in scopes),
                        resource_name=(
                            str(payload["resource_name"])
                            if payload.get("resource_name")
                            else None
                        ),
                    )
                    self._metadata_cache[resource_url] = (time.monotonic(), metadata)

        missing = set(required_scopes) - set(metadata.scopes_supported)
        if missing:
            raise MCPDiscoveryError(
                "The MCP resource does not advertise scope(s): "
                + ", ".join(sorted(missing))
            )
        return metadata

    async def call_tool(
        self,
        *,
        resource_url: str,
        access_token: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        if not access_token or access_token.startswith("demo-"):
            raise MCPToolError("A real MCP access token is required.")
        request_id = str(uuid.uuid4())
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    resource_url,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    },
                    timeout=self._timeout,
                )
        except httpx.HTTPError as exc:
            raise MCPToolError(f"The MCP resource could not be reached: {exc}") from exc

        raw = response.text
        if response.status_code >= 400:
            detail = raw[:500]
            try:
                parsed_error = response.json()
                detail = str(
                    parsed_error.get("error_description")
                    or parsed_error.get("error")
                    or parsed_error
                )
            except ValueError:
                pass
            raise MCPToolError(
                f"MCP resource returned HTTP {response.status_code}: {detail}"
            )

        try:
            if "text/event-stream" in response.headers.get("content-type", ""):
                data_lines = [
                    line[len("data:") :].strip()
                    for line in raw.splitlines()
                    if line.startswith("data:")
                ]
                if not data_lines:
                    raise ValueError("SSE response contains no data event")
                rpc = json.loads(data_lines[-1])
            else:
                rpc = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise MCPToolError("The MCP resource returned an invalid response.") from exc

        if rpc.get("id") != request_id:
            raise MCPToolError("The MCP response id does not match the request.")
        if rpc.get("error"):
            error = rpc["error"]
            raise MCPToolError(str(error.get("message") or error))
        result = rpc.get("result") or {}
        content = result.get("content") or []
        text_parts = [item.get("text") for item in content if item.get("type") == "text"]
        rendered = "\n".join(str(part) for part in text_parts if part is not None)
        if result.get("isError"):
            raise MCPToolError(rendered or f"MCP tool {tool_name} failed.")
        if not rendered:
            return result.get("structuredContent", result)
        try:
            return json.loads(rendered)
        except json.JSONDecodeError:
            return rendered


_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
