"""
Customer Agent - Handles accounts, contacts, and customer data.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
Calls the protected ProGear Customer MCP for customer data.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from auth.agent_config import AGENT_CUSTOMER, get_agent_config
from mcp.client import MCPToolError, get_mcp_client


class CustomerAgent(BaseAgent):
    """
    Customer Agent handles all customer-related operations.

    Capabilities:
    - Look up customer accounts (customer:read)
    - Search/find customers (customer:lookup)
    - View purchase history (customer:history)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: customer:read, customer:lookup, customer:history
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Customer Agent",
            agent_type="customer",
            scopes=["customer:read", "customer:lookup", "customer:history"],
            user_token=user_token,
            color="#8b5cf6",  # Purple
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Customer Agent, an AI assistant specialized in customer management.

Your capabilities:
- Look up customer accounts and profiles
- Search for customers by name, email, or account number
- View purchase and order history
- Check customer tier, loyalty status, and preferences

You work for ProGear, a sporting goods company. Protect customer privacy and only share relevant info.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- Your access is controlled by scopes: customer:read, customer:lookup, customer:history
- All your actions are audited through Okta

Be helpful while respecting customer data privacy."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a customer-related task with real data."""
        context = context or {}

        try:
            data = await self._get_data(task, context)
        except MCPToolError as exc:
            return {
                "agent": self.agent_type,
                "agent_name": self.agent_name,
                "color": self.color,
                "result": f"Customer MCP operation failed: {exc}",
                "success": False,
                "error": str(exc),
                "scopes": context.get("scopes", self.scopes),
            }

        # Augment the task with data
        augmented_task = f"""{task}

Available customer data:
{data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    async def _get_data(self, task: str, context: Dict[str, Any]) -> Any:
        """Select and invoke one Customer MCP tool."""
        if not context.get("resource_token_validated") or not context.get("mcp_access_token"):
            raise MCPToolError("The Customer MCP requires a validated access token.")
        config = get_agent_config(AGENT_CUSTOMER)
        if config is None:
            raise MCPToolError("The Customer MCP resource is not configured.")
        task_lower = task.lower()
        scopes = context.get("scopes", [])
        if "customer:history" in scopes:
            tool_name, arguments = "get_customer_summary", {}
        elif "customer:lookup" in scopes:
            tier = next(
                (value for value in ("Platinum", "Gold", "Silver", "Bronze") if value.lower() in task_lower),
                None,
            )
            if tier:
                tool_name, arguments = "get_customers_by_tier", {"tier": tier}
            else:
                query = next(
                    (value for value in ("state university", "metro", "chicago", "los angeles", "atlanta", "boston", "dallas") if value in task_lower),
                    task.strip(),
                )
                tool_name, arguments = "search_customers", {"query": query}
        else:
            import re

            match = re.search(r"\bCUST-\d{3}\b", task, re.IGNORECASE)
            if not match:
                raise MCPToolError("Ask for a customer by ID or use a customer search prompt.")
            tool_name, arguments = "get_customer", {"customerId": match.group(0).upper()}
        return await get_mcp_client().call_tool(
            resource_url=config.mcp_url,
            access_token=str(context["mcp_access_token"]),
            tool_name=tool_name,
            arguments=arguments,
        )
