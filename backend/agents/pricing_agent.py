"""
Pricing Agent - Handles pricing, discounts, and margins.

Registered as a first-class identity in Okta.
"""

import os
from typing import Dict, Any, Optional
# from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Load environment variables for OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_GATEWAY_SECRET = os.getenv("X_GATEWAY_SECRET")


class PricingAgent:
    """
    Pricing Agent handles all pricing-related operations.

    Capabilities:
    - Get product pricing
    - Apply discounts
    - Calculate margins
    - Check pricing rules

    Security:
    - Registered as Okta AI Agent
    - Uses token exchange (ID-JAG) for MCP access
    - Scoped to pricing:read, pricing:write
    """

    def __init__(self, user_token: str, okta_auth: Optional[Any] = None):
        self.user_token = user_token
        self.okta_auth = okta_auth
        self.agent_name = "pricing-agent"
        self.scopes = ["pricing:read", "pricing:write"]

        # self.llm = ChatAnthropic(
        #     model="claude-sonnet-4-20250514",
        #     temperature=0.2,  # Low temp for pricing accuracy
        # )
        self.llm = ChatOpenAI(
            model="claude-sonnet-4-20250514",
            api_key=OPENAI_API_KEY,

            # Custom headers are passed here
            default_headers={
                "x-gateway-secret": X_GATEWAY_SECRET
            }
        )

    async def get_agent_token(self) -> str:
        """Exchange user token for pricing agent token."""
        if not self.okta_auth:
            return "demo-token"
        return "demo-token"

    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a pricing-related task."""
        agent_token = await self.get_agent_token()

        return {
            "agent": self.agent_name,
            "result": f"[Pricing Agent] Processing: {task}",
            "token_exchange": {
                "from": "user",
                "to": "pricing-agent",
                "audience": "pricing-agent-audience",
                "scopes": self.scopes,
            },
            "tools_called": [],
        }

    def get_system_prompt(self) -> str:
        return """You are the ProGear Pricing Agent, an AI assistant specialized in pricing operations.

Your capabilities:
- Look up product pricing
- Apply volume and promotional discounts
- Calculate profit margins
- Enforce pricing rules and approval thresholds

You work for ProGear, a sporting goods company. Be precise with all pricing calculations.
Your access is scoped to pricing data only, and all actions are audited."""
