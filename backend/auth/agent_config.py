"""
Multi-Agent Configuration

Defines all 4 AI agents and their Okta credentials for the ProGear demo.
Each agent has its own:
- Agent ID (wlp...)
- Private JWK key
- Authorization server
- Scopes

Environment variables:
- OKTA_AI_AGENT_[TYPE]_ID - The agent entity ID
- OKTA_AI_AGENT_[TYPE]_PRIVATE_KEY - JWK private key JSON
- OKTA_[TYPE]_AUTH_SERVER_ID - Authorization server ID
- OKTA_[TYPE]_AUDIENCE - API audience
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for a single AI agent."""
    name: str  # MCP name for Token Exchange card (e.g., "Inventory MCP")
    display_name: str  # Agent name for Agent Flow card (e.g., "Inventory Agent")
    agent_type: str  # sales, inventory, customer, pricing
    agent_id: str  # wlp...
    private_key: Optional[Dict[str, Any]]  # JWK private key
    auth_server_id: str  # aus...
    audience: str  # api://progear-...
    scopes: List[str]  # All possible scopes for this MCP
    description: str
    color: str  # For UI display


# Agent type constants
AGENT_SALES = "sales"
AGENT_INVENTORY = "inventory"
AGENT_CUSTOMER = "customer"
AGENT_PRICING = "pricing"


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
    Get configuration for a specific agent type.

    Args:
        agent_type: One of sales, inventory, customer, pricing

    Returns:
        AgentConfig or None if not configured
    """
    configs = {
        AGENT_SALES: AgentConfig(
            name="Sales MCP",
            display_name="Sales Agent",
            agent_type=AGENT_SALES,
            agent_id=os.getenv("OKTA_AI_AGENT_SALES_ID", os.getenv("OKTA_AI_AGENT_ID", "")),
            private_key=_parse_private_key(
                os.getenv("OKTA_AI_AGENT_SALES_PRIVATE_KEY",
                         os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", ""))
            ),
            auth_server_id=os.getenv("OKTA_SALES_AUTH_SERVER_ID",
                                    os.getenv("OKTA_MCP_AUTH_SERVER_ID", "")),
            audience=os.getenv("OKTA_SALES_AUDIENCE", "api://progear-sales"),
            scopes=["sales:read", "sales:quote", "sales:order"],
            description="Orders, quotes, and sales pipeline",
            color="#3b82f6",  # Blue
        ),
        AGENT_INVENTORY: AgentConfig(
            name="Inventory MCP",
            display_name="Inventory Agent",
            agent_type=AGENT_INVENTORY,
            agent_id=os.getenv("OKTA_AI_AGENT_INVENTORY_ID", os.getenv("OKTA_AI_AGENT_ID", "")),
            private_key=_parse_private_key(
                os.getenv("OKTA_AI_AGENT_INVENTORY_PRIVATE_KEY",
                         os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", ""))
            ),
            auth_server_id=os.getenv("OKTA_INVENTORY_AUTH_SERVER_ID",
                                    os.getenv("OKTA_MCP_AUTH_SERVER_ID", "")),
            audience=os.getenv("OKTA_INVENTORY_AUDIENCE", "api://progear-inventory"),
            scopes=["inventory:read", "inventory:write", "inventory:alert"],
            description="Stock levels, products, and warehouse",
            color="#10b981",  # Green
        ),
        AGENT_CUSTOMER: AgentConfig(
            name="Customer MCP",
            display_name="Customer Agent",
            agent_type=AGENT_CUSTOMER,
            agent_id=os.getenv("OKTA_AI_AGENT_CUSTOMER_ID", os.getenv("OKTA_AI_AGENT_ID", "")),
            private_key=_parse_private_key(
                os.getenv("OKTA_AI_AGENT_CUSTOMER_PRIVATE_KEY",
                         os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", ""))
            ),
            auth_server_id=os.getenv("OKTA_CUSTOMER_AUTH_SERVER_ID",
                                    os.getenv("OKTA_MCP_AUTH_SERVER_ID", "")),
            audience=os.getenv("OKTA_CUSTOMER_AUDIENCE", "api://progear-customer"),
            scopes=["customer:read", "customer:lookup", "customer:history"],
            description="Accounts, contacts, and purchase history",
            color="#8b5cf6",  # Purple
        ),
        AGENT_PRICING: AgentConfig(
            name="Pricing MCP",
            display_name="Pricing Agent",
            agent_type=AGENT_PRICING,
            agent_id=os.getenv("OKTA_AI_AGENT_PRICING_ID", os.getenv("OKTA_AI_AGENT_ID", "")),
            private_key=_parse_private_key(
                os.getenv("OKTA_AI_AGENT_PRICING_PRIVATE_KEY",
                         os.getenv("OKTA_AI_AGENT_PRIVATE_KEY", ""))
            ),
            auth_server_id=os.getenv("OKTA_PRICING_AUTH_SERVER_ID",
                                    os.getenv("OKTA_MCP_AUTH_SERVER_ID", "")),
            audience=os.getenv("OKTA_PRICING_AUDIENCE", "api://progear-pricing"),
            scopes=["pricing:read", "pricing:margin", "pricing:discount"],
            description="Pricing, margins, and discounts",
            color="#f59e0b",  # Orange
        ),
    }

    return configs.get(agent_type)


def get_all_agent_configs() -> Dict[str, AgentConfig]:
    """Get all agent configurations."""
    return {
        agent_type: get_agent_config(agent_type)
        for agent_type in [AGENT_SALES, AGENT_INVENTORY, AGENT_CUSTOMER, AGENT_PRICING]
        if get_agent_config(agent_type) is not None
    }


def is_agent_configured(agent_type: str) -> bool:
    """Check if an agent has the minimum required configuration."""
    config = get_agent_config(agent_type)
    if not config:
        return False
    # At minimum, need agent_id and auth_server_id
    return bool(config.agent_id and config.auth_server_id)


def get_configured_agents() -> List[str]:
    """Get list of agent types that are properly configured."""
    return [
        agent_type for agent_type in [AGENT_SALES, AGENT_INVENTORY, AGENT_CUSTOMER, AGENT_PRICING]
        if is_agent_configured(agent_type)
    ]


# Demo mode configuration
# When real agents aren't configured, use these demo values
DEMO_AGENTS = {
    AGENT_SALES: {
        "name": "Sales MCP",
        "display_name": "Sales Agent",
        "scopes": ["sales:read", "sales:quote", "sales:order"],
        "color": "#3b82f6",
    },
    AGENT_INVENTORY: {
        "name": "Inventory MCP",
        "display_name": "Inventory Agent",
        "scopes": ["inventory:read", "inventory:write", "inventory:alert"],
        "color": "#10b981",
    },
    AGENT_CUSTOMER: {
        "name": "Customer MCP",
        "display_name": "Customer Agent",
        "scopes": ["customer:read", "customer:lookup", "customer:history"],
        "color": "#8b5cf6",
    },
    AGENT_PRICING: {
        "name": "Pricing MCP",
        "display_name": "Pricing Agent",
        "scopes": ["pricing:read", "pricing:margin", "pricing:discount"],
        "color": "#f59e0b",
    },
}
