"""
Per-Resource-Domain Agent Configuration

Okta governs a single AI Agent workload identity for this demo: the
ProGear Sales Agent. This module defines the per-resource-domain settings
that agent uses when performing ID-JAG token exchanges for each of the
four resource domains (sales, inventory, customer, pricing):
- Native MCP protected-resource URL (the RFC 9728 document supplies the
  protecting Custom Authorization Server)
- API audience
- Scopes
- Display metadata (name, color) for the UI

Environment variables:
- OKTA_AI_AGENT_ID - The governed agent's entity ID (wlp...), shared by
  every resource domain unless a per-domain override below is set.
- OKTA_AI_AGENT_PRIVATE_KEY - The governed agent's JWK private key JSON,
  shared by every resource domain unless a per-domain override is set.
- OKTA_AI_AGENT_[TYPE]_ID / OKTA_AI_AGENT_[TYPE]_PRIVATE_KEY - Optional
  per-domain overrides. Only needed if a deployment provisions a separate
  Okta AI Agent identity per resource domain instead of the one-agent
  model above; unset by default.
- PROGEAR_MCP_BASE_URL - Base URL for the four native ProGear MCP resources.
- PROGEAR_[TYPE]_MCP_URL - Optional full URL override for one MCP resource.
- OKTA_[TYPE]_AUDIENCE - API audience for this resource domain.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Per-resource-domain configuration used by the governed ProGear Sales Agent.

    `agent_id` / `private_key` normally resolve to the one shared Okta AI
    Agent identity (see module docstring); they are per-domain fields here
    only to support the optional per-domain override env vars.
    """
    name: str  # MCP name for Token Exchange card (e.g., "Inventory MCP")
    display_name: str  # Display label for Agent Flow card (e.g., "Inventory Agent")
    agent_type: str  # resource domain: sales, inventory, customer, pricing
    agent_id: str  # Governed agent entity ID (wlp...), shared unless overridden
    private_key: Optional[Dict[str, Any]]  # JWK private key, shared unless overridden
    mcp_url: str  # Native MCP protected-resource URL; its metadata supplies the AS
    audience: str  # api://progear-...
    scopes: List[str]  # All possible scopes for this resource domain
    description: str
    color: str  # For UI display


# Resource domain constants
AGENT_SALES = "sales"
AGENT_INVENTORY = "inventory"
AGENT_CUSTOMER = "customer"
AGENT_PRICING = "pricing"

DEFAULT_MCP_BASE_URL = "https://progear-mcp-servers-m2f3.onrender.com"


def _mcp_url(agent_type: str) -> str:
    override = os.getenv(f"PROGEAR_{agent_type.upper()}_MCP_URL", "").strip()
    if override:
        return override.rstrip("/")
    base = os.getenv("PROGEAR_MCP_BASE_URL", DEFAULT_MCP_BASE_URL).strip().rstrip("/")
    return f"{base}/{agent_type}/mcp"


def _parse_private_key(key_str: str) -> Optional[Dict[str, Any]]:
    """Parse private key from environment variable."""
    if not key_str:
        return None
    try:
        return json.loads(key_str)
    except json.JSONDecodeError:
        logger.error("Failed to parse private key JSON")
        return None


def get_agent_config(agent_type: str) -> Optional[AgentConfig]:
    """
    Get the governed ProGear Sales Agent's configuration for one resource domain.

    Args:
        agent_type: One resource domain - sales, inventory, customer, pricing

    Returns:
        AgentConfig or None if not configured
    """
    configs = {
        AGENT_SALES: AgentConfig(
            name="ProGear Sales MCP",
            display_name="Sales Agent",
            agent_type=AGENT_SALES,
            agent_id=os.getenv("OKTA_AI_AGENT_SALES_ID", os.getenv("OKTA_AI_AGENT_ID", "")),
            private_key=_parse_private_key(
                os.getenv("OKTA_AI_AGENT_SALES_PRIVATE_KEY",
                         os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", ""))
            ),
            mcp_url=_mcp_url(AGENT_SALES),
            audience=os.getenv("OKTA_SALES_AUDIENCE", "api://progear-sales"),
            scopes=["sales:read", "sales:quote", "sales:order"],
            description="Orders, quotes, and sales pipeline",
            color="#3b82f6",  # Blue
        ),
        AGENT_INVENTORY: AgentConfig(
            name="ProGear Inventory MCP",
            display_name="Inventory Agent",
            agent_type=AGENT_INVENTORY,
            agent_id=os.getenv("OKTA_AI_AGENT_INVENTORY_ID", os.getenv("OKTA_AI_AGENT_ID", "")),
            private_key=_parse_private_key(
                os.getenv("OKTA_AI_AGENT_INVENTORY_PRIVATE_KEY",
                         os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", ""))
            ),
            mcp_url=_mcp_url(AGENT_INVENTORY),
            audience=os.getenv("OKTA_INVENTORY_AUDIENCE", "api://progear-inventory"),
            scopes=["inventory:read", "inventory:write", "inventory:alert"],
            description="Stock levels, products, and warehouse",
            color="#10b981",  # Green
        ),
        AGENT_CUSTOMER: AgentConfig(
            name="ProGear Customer MCP",
            display_name="Customer Agent",
            agent_type=AGENT_CUSTOMER,
            agent_id=os.getenv("OKTA_AI_AGENT_CUSTOMER_ID", os.getenv("OKTA_AI_AGENT_ID", "")),
            private_key=_parse_private_key(
                os.getenv("OKTA_AI_AGENT_CUSTOMER_PRIVATE_KEY",
                         os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", ""))
            ),
            mcp_url=_mcp_url(AGENT_CUSTOMER),
            audience=os.getenv("OKTA_CUSTOMER_AUDIENCE", "api://progear-customer"),
            scopes=["customer:read", "customer:lookup", "customer:history"],
            description="Accounts, contacts, and purchase history",
            color="#8b5cf6",  # Purple
        ),
        AGENT_PRICING: AgentConfig(
            name="ProGear Pricing MCP",
            display_name="Pricing Agent",
            agent_type=AGENT_PRICING,
            agent_id=os.getenv("OKTA_AI_AGENT_PRICING_ID", os.getenv("OKTA_AI_AGENT_ID", "")),
            private_key=_parse_private_key(
                os.getenv("OKTA_AI_AGENT_PRICING_PRIVATE_KEY",
                         os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", ""))
            ),
            mcp_url=_mcp_url(AGENT_PRICING),
            audience=os.getenv("OKTA_PRICING_AUDIENCE", "api://progear-pricing"),
            scopes=["pricing:read", "pricing:margin", "pricing:discount"],
            description="Pricing, margins, and discounts",
            color="#f59e0b",  # Orange
        ),
    }

    return configs.get(agent_type)


def get_all_agent_configs() -> Dict[str, AgentConfig]:
    """Get the governed agent's per-resource-domain configuration for all four domains."""
    return {
        agent_type: get_agent_config(agent_type)
        for agent_type in [AGENT_SALES, AGENT_INVENTORY, AGENT_CUSTOMER, AGENT_PRICING]
        if get_agent_config(agent_type) is not None
    }


def is_agent_configured(agent_type: str) -> bool:
    """Check if the governed agent has the minimum required configuration for this resource domain."""
    config = get_agent_config(agent_type)
    if not config:
        return False
    # The resource's RFC 9728 metadata supplies the authorization server.
    return bool(config.agent_id and config.mcp_url)


def get_configured_agents() -> List[str]:
    """Get the list of resource domains the governed agent is properly configured for."""
    return [
        agent_type for agent_type in [AGENT_SALES, AGENT_INVENTORY, AGENT_CUSTOMER, AGENT_PRICING]
        if is_agent_configured(agent_type)
    ]


# Demo mode configuration
# When the governed agent's real credentials aren't configured, use these
# demo values (one entry per resource domain).
DEMO_AGENTS = {
    AGENT_SALES: {
        "name": "ProGear Sales MCP",
        "display_name": "Sales Agent",
        "scopes": ["sales:read", "sales:quote", "sales:order"],
        "color": "#3b82f6",
    },
    AGENT_INVENTORY: {
        "name": "ProGear Inventory MCP",
        "display_name": "Inventory Agent",
        "scopes": ["inventory:read", "inventory:write", "inventory:alert"],
        "color": "#10b981",
    },
    AGENT_CUSTOMER: {
        "name": "ProGear Customer MCP",
        "display_name": "Customer Agent",
        "scopes": ["customer:read", "customer:lookup", "customer:history"],
        "color": "#8b5cf6",
    },
    AGENT_PRICING: {
        "name": "ProGear Pricing MCP",
        "display_name": "Pricing Agent",
        "scopes": ["pricing:read", "pricing:margin", "pricing:discount"],
        "color": "#f59e0b",
    },
}
