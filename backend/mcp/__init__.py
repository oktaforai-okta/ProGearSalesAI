"""Native MCP client helpers for ProGear protected resources."""

from .client import (
    MCPClient,
    MCPDiscoveryError,
    MCPProtectedResourceMetadata,
    MCPToolError,
    get_mcp_client,
)

__all__ = [
    "MCPClient",
    "MCPDiscoveryError",
    "MCPProtectedResourceMetadata",
    "MCPToolError",
    "get_mcp_client",
]
