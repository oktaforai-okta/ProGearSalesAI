"""
Pricing Agent - Handles pricing, discounts, and margins.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
Calls the protected ProGear Pricing MCP for pricing data.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from auth.agent_config import AGENT_PRICING, get_agent_config
from mcp.client import MCPToolError, get_mcp_client


class PricingAgent(BaseAgent):
    """
    Pricing Agent handles all pricing-related operations.

    Capabilities:
    - Get product pricing (pricing:read)
    - View profit margins (pricing:margin)
    - Apply/view discounts (pricing:discount)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: pricing:read, pricing:margin, pricing:discount
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Pricing Agent",
            agent_type="pricing",
            scopes=["pricing:read", "pricing:margin", "pricing:discount"],
            user_token=user_token,
            color="#f59e0b",  # Orange
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Pricing Agent, an AI assistant specialized in pricing operations.

Your capabilities:
- Look up product pricing
- Apply volume and promotional discounts
- Calculate profit margins
- Enforce pricing rules and approval thresholds

You work for ProGear, a sporting goods company. Be precise with all pricing calculations.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- Your access is controlled by scopes: pricing:read, pricing:margin, pricing:discount
- All your actions are audited through Okta

Always show pricing calculations clearly."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a pricing-related task with real data."""
        context = context or {}

        try:
            data = await self._get_data(task, context)
        except MCPToolError as exc:
            return {
                "agent": self.agent_type,
                "agent_name": self.agent_name,
                "color": self.color,
                "result": f"Pricing MCP operation failed: {exc}",
                "success": False,
                "error": str(exc),
                "scopes": context.get("scopes", self.scopes),
            }

        # Augment the task with data
        augmented_task = f"""{task}

Available pricing data:
{data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    async def _get_data(self, task: str, context: Dict[str, Any]) -> Any:
        """Select and invoke one Pricing MCP tool."""
        if not context.get("resource_token_validated") or not context.get("mcp_access_token"):
            raise MCPToolError("The Pricing MCP requires a validated access token.")
        config = get_agent_config(AGENT_PRICING)
        if config is None:
            raise MCPToolError("The Pricing MCP resource is not configured.")
        task_lower = task.lower()
        scopes = context.get("scopes", [])
        if "pricing:discount" in scopes:
            tool_name, arguments = "get_discount_structure", {}
        elif "pricing:margin" in scopes or "margin" in task_lower:
            category = "Hoops & Backboards" if "hoop" in task_lower else "Basketballs"
            tool_name, arguments = "get_category_pricing", {"category": category}
        else:
            import re

            sku_match = re.search(r"\b[A-Z]{2,5}-[A-Z0-9-]+\b", task.upper())
            sku = sku_match.group(0) if sku_match else "BB-PRO-001"
            tool_name, arguments = "get_price", {"sku": sku}
        return await get_mcp_client().call_tool(
            resource_url=config.mcp_url,
            access_token=str(context["mcp_access_token"]),
            tool_name=tool_name,
            arguments=arguments,
        )
