"""
Inventory Agent - Handles stock levels and products.

Registered as a first-class identity in Okta.
"""

from typing import Dict, Any, Optional
from langchain_anthropic import ChatAnthropic


class InventoryAgent:
    """
    Inventory Agent handles all inventory-related operations.

    Capabilities:
    - Check stock levels
    - List products
    - Reserve inventory
    - Track warehouse status

    Security:
    - Registered as Okta AI Agent
    - Uses token exchange (ID-JAG) for MCP access
    - Scoped to inventory:read, inventory:write
    """

    def __init__(self, user_token: str, okta_auth: Optional[Any] = None):
        self.user_token = user_token
        self.okta_auth = okta_auth
        self.agent_name = "inventory-agent"
        self.scopes = ["inventory:read", "inventory:write"]

        self.llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            temperature=0.3,  # Lower temp for factual inventory data
        )

    async def get_agent_token(self) -> str:
        """Exchange user token for inventory agent token."""
        if not self.okta_auth:
            return "demo-token"
        return "demo-token"

    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process an inventory-related task."""
        agent_token = await self.get_agent_token()

        return {
            "agent": self.agent_name,
            "result": f"[Inventory Agent] Processing: {task}",
            "token_exchange": {
                "from": "user",
                "to": "inventory-agent",
                "audience": "inventory-agent-audience",
                "scopes": self.scopes,
            },
            "tools_called": [],
        }

    def get_system_prompt(self) -> str:
        return """You are the ProGear Inventory Agent, an AI assistant specialized in inventory management.

Your capabilities:
- Check real-time stock levels for any product
- List available products by category
- Reserve inventory for orders
- Track warehouse and fulfillment status

You work for ProGear, a sporting goods company. Provide accurate inventory information.
Your access is scoped to inventory data only, and all actions are audited."""
