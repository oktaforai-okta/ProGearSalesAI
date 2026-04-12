"""
Customer Agent - Handles accounts, contacts, and customer data.

Registered as a first-class identity in Okta.
"""

import os
from typing import Dict, Any, Optional
# from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Load environment variables for OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_GATEWAY_SECRET = os.getenv("X_GATEWAY_SECRET")


class CustomerAgent:
    """
    Customer Agent handles all customer-related operations.

    Capabilities:
    - Look up customer accounts
    - Get contact information
    - View purchase history
    - Check customer tier/status

    Security:
    - Registered as Okta AI Agent
    - Uses token exchange (ID-JAG) for MCP access
    - Scoped to customer:read, customer:write
    """

    def __init__(self, user_token: str, okta_auth: Optional[Any] = None):
        self.user_token = user_token
        self.okta_auth = okta_auth
        self.agent_name = "customer-agent"
        self.scopes = ["customer:read", "customer:write"]

        # self.llm = ChatAnthropic(
        #     model="claude-sonnet-4-20250514",
        #     temperature=0.5,
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
        """Exchange user token for customer agent token."""
        if not self.okta_auth:
            return "demo-token"
        return "demo-token"

    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a customer-related task."""
        agent_token = await self.get_agent_token()

        return {
            "agent": self.agent_name,
            "result": f"[Customer Agent] Processing: {task}",
            "token_exchange": {
                "from": "user",
                "to": "customer-agent",
                "audience": "customer-agent-audience",
                "scopes": self.scopes,
            },
            "tools_called": [],
        }

    def get_system_prompt(self) -> str:
        return """You are the ProGear Customer Agent, an AI assistant specialized in customer management.

Your capabilities:
- Look up customer accounts and profiles
- Get contact information
- View purchase and order history
- Check customer tier, loyalty status, and preferences

You work for ProGear, a sporting goods company. Protect customer privacy and only share relevant info.
Your access is scoped to customer data only, and all actions are audited."""
