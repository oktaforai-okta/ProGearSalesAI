"""
Sales Agent - The orchestrator for ProGear sales operations.

Registered as a first-class identity in Okta's AI Agent Directory.
Uses raw Anthropic SDK for LLM calls.
Calls the protected ProGear Sales MCP for business data.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from auth.agent_config import AGENT_SALES, get_agent_config
from mcp.client import MCPToolError, get_mcp_client


class SalesAgent(BaseAgent):
    """
    Sales Agent - The primary agent for ProGear sales.

    Capabilities:
    - Create and manage sales quotes
    - Process customer orders
    - Track deals and pipeline
    - Provide sales analytics

    Security:
    - Registered in Okta AI Agent Directory
    - Uses ID-JAG (Cross App Access) for token exchange
    - Scopes: sales:read, sales:quote, sales:order
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Sales Agent",
            agent_type="sales",
            scopes=["sales:read", "sales:quote", "sales:order"],
            user_token=user_token,
            color="#3b82f6",  # Blue
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Sales Agent, an AI assistant specialized in sales operations for ProGear Sporting Goods.

Your capabilities:
- Create and manage sales quotes for sporting goods equipment
- Process customer orders
- Track deals in the sales pipeline
- Provide sales analytics and insights

You work for ProGear, a B2B sporting goods company serving retailers and sports teams.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- You authenticate using a JWK private key (JWT Bearer)
- Your access to data is controlled by scopes: sales:read, sales:quote, sales:order
- All your actions are audited through Okta
- You are acting ON BEHALF OF the logged-in user - their permissions apply

When responding, be helpful, professional, and accurate. Focus on sales-related information."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a sales task with data from the native Sales MCP."""
        context = context or {}
        try:
            data = await self._get_data(task, context)
        except MCPToolError as exc:
            return {
                "agent": self.agent_type,
                "agent_name": self.agent_name,
                "color": self.color,
                "result": f"Sales MCP operation failed: {exc}",
                "success": False,
                "error": str(exc),
                "scopes": context.get("scopes", self.scopes),
            }

        # Augment the task with data
        augmented_task = f"""{task}

Available data to reference:
{data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    async def _get_data(self, task: str, context: Dict[str, Any]) -> Any:
        """Select and invoke one Sales MCP tool."""
        if not context.get("resource_token_validated") or not context.get("mcp_access_token"):
            raise MCPToolError("The Sales MCP requires a validated access token.")
        config = get_agent_config(AGENT_SALES)
        if config is None:
            raise MCPToolError("The Sales MCP resource is not configured.")
        task_lower = task.lower()
        scopes = context.get("scopes", [])
        if any(scope in scopes for scope in ("sales:quote", "sales:order")):
            raise MCPToolError(
                "Creating a quote or order requires a customer ID and product line items."
            )
        tool_name = "get_pipeline" if any(
            word in task_lower for word in ("pipeline", "revenue", "summary", "total")
        ) else "list_orders"
        return await get_mcp_client().call_tool(
            resource_url=config.mcp_url,
            access_token=str(context["mcp_access_token"]),
            tool_name=tool_name,
            arguments={},
        )
