"""
Sales Agent - The orchestrator for ProGear sales operations.

This is a VISIBLE agent class - customers can see this code.
The agent is registered as a first-class identity in Okta's AI Agent Directory.

Security Model:
- Agent ID: wlp8x5q7mvH86KvFJ0g7
- App Client ID: 0oa8x5nsjp8aDUpB70g7
- Scopes: mcp:read, mcp:inventory, mcp:pricing, mcp:customers (full orchestrator access)
- Authentication: JWT Bearer with JWK private key
"""

import os
from typing import Dict, Any, Optional, List
# from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import logging

# Load environment variables for OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_GATEWAY_SECRET = os.getenv("X_GATEWAY_SECRET")

from ..auth.okta_auth import OktaAuth, get_okta_auth, MCP_SCOPES

logger = logging.getLogger(__name__)


class SalesAgent:
    """
    Sales Agent - The primary orchestrator for ProGear.

    Capabilities:
    - Create and manage quotes
    - Process orders
    - Track deals and pipeline
    - Access inventory, pricing, and customer data via MCP

    Security:
    - Registered in Okta AI Agent Directory
    - Uses ID-JAG (Cross App Access) for MCP token exchange
    - Full MCP scopes as orchestrator: mcp:read, mcp:inventory, mcp:pricing, mcp:customers
    """

    # Agent identity (from Okta AI Agent Directory)
    AGENT_ID = "wlp8x5q7mvH86KvFJ0g7"
    AGENT_NAME = "ProGear Sales Agent"

    # OAuth/OIDC app (linked to agent)
    CLIENT_ID = "0oa8x5nsjp8aDUpB70g7"

    # MCP scopes this agent can request (configured in Managed Connections)
    SCOPES = MCP_SCOPES  # ["mcp:read", "mcp:inventory", "mcp:pricing", "mcp:customers"]

    def __init__(self, user_token: str, okta_auth: Optional[OktaAuth] = None):
        """
        Initialize the Sales Agent.

        Args:
            user_token: The user's ID token (will be exchanged for MCP token)
            okta_auth: OktaAuth instance for token exchange (uses singleton if not provided)
        """
        self.user_token = user_token
        self.okta_auth = okta_auth or get_okta_auth()

        # Token state
        self._mcp_token: Optional[str] = None
        self._token_info: Optional[Dict] = None

        # Initialize LLM (Claude)
        # self.llm = ChatAnthropic(
        #     model="claude-sonnet-4-20250514",
        #     temperature=0.7,
        # )
        self.llm = ChatOpenAI(
            model="claude-sonnet-4-20250514",
            api_key=OPENAI_API_KEY,

            # Custom headers are passed here
            default_headers={
                "x-gateway-secret": X_GATEWAY_SECRET
            }
        )

    async def get_mcp_token(self, resource_type: str = "all") -> str:
        """
        Exchange user token for MCP access token.

        This is the ID-JAG (Cross App Access) flow:
        1. User's ID token is presented
        2. Agent authenticates with its JWK private key
        3. Okta returns MCP-scoped access token

        Args:
            resource_type: "inventory", "pricing", "customers", or "all"

        Returns:
            MCP access token
        """
        token = await self.okta_auth.get_mcp_token(self.user_token, resource_type)
        self._mcp_token = token
        return token

    async def get_token_exchange_info(self) -> Dict[str, Any]:
        """
        Get detailed info about the token exchange for demo visualization.

        Returns:
            Dict with user info, agent info, and token exchange details
        """
        if self._token_info is None:
            self._token_info = await self.okta_auth.get_token_info(self.user_token)

        return {
            **self._token_info,
            "token_exchange": {
                "flow": "ID-JAG (Cross App Access)",
                "from": "user_id_token",
                "to": "mcp_access_token",
                "audience": self.okta_auth.mcp_audience,
                "scopes_requested": self.SCOPES,
                "agent_authentication": "JWT Bearer with JWK private key",
            }
        }

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a sales-related task.

        Args:
            task: The task description from the user
            context: Additional context (user info, conversation history, etc.)

        Returns:
            Dict with result, agent info, and token exchange details
        """
        context = context or {}

        # Get MCP token for accessing resources
        try:
            mcp_token = await self.get_mcp_token("all")
            token_exchange_success = True
            token_exchange_error = None
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            mcp_token = None
            token_exchange_success = False
            token_exchange_error = str(e)

        # Prepare messages for Claude
        messages = [
            SystemMessage(content=self.get_system_prompt()),
            HumanMessage(content=task)
        ]

        # Call Claude
        try:
            response = await self.llm.ainvoke(messages)
            llm_response = response.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            llm_response = f"I apologize, but I encountered an error processing your request: {e}"

        # Get token exchange info for visualization
        token_info = await self.get_token_exchange_info()

        return {
            "agent": {
                "name": self.AGENT_NAME,
                "id": self.AGENT_ID,
                "client_id": self.CLIENT_ID,
            },
            "result": llm_response,
            "token_exchange": {
                "success": token_exchange_success,
                "error": token_exchange_error,
                "flow": "User ID Token → JWT Bearer Assertion → MCP Access Token",
                "audience": self.okta_auth.mcp_audience,
                "scopes": self.SCOPES,
                "has_mcp_token": mcp_token is not None,
            },
            "security": {
                "user": token_info.get("user", {}),
                "agent_authenticated": token_info.get("agent", {}).get("has_private_key", False),
                "demo_mode": token_info.get("demo_mode", True),
            },
            "tools_called": [],  # Will be populated when MCP tools are connected
        }

    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return """You are the ProGear Sales Agent, an AI assistant specialized in sales operations for ProGear Sporting Goods.

Your capabilities:
- Create and manage sales quotes for sporting goods equipment
- Process customer orders
- Track deals in the sales pipeline
- Provide sales analytics and insights
- Access inventory data to check product availability
- Access pricing data for quotes and discounts
- Access customer data for personalized service

You work for ProGear, a B2B sporting goods company serving retailers and sports teams.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- You authenticate using a JWK private key (JWT Bearer)
- Your access to data is controlled by MCP scopes
- All your actions are audited through Okta
- You are acting ON BEHALF OF the logged-in user - their permissions apply

When you need data, you'll use MCP tools to access the sales, inventory, pricing, and customer databases.
Always be helpful, professional, and accurate. If you don't have access to certain data, explain why."""

    async def call_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool with the exchanged token.

        Args:
            tool_name: The MCP tool to call
            params: Parameters for the tool

        Returns:
            Tool result
        """
        # Ensure we have an MCP token
        if not self._mcp_token:
            self._mcp_token = await self.get_mcp_token("all")

        # TODO: Implement actual MCP tool call with the token
        # This will connect to the MCP server on Render
        logger.info(f"Calling MCP tool: {tool_name} with token")

        return {
            "tool": tool_name,
            "params": params,
            "result": f"[MCP] Tool {tool_name} called (implementation pending)",
            "token_used": self._mcp_token is not None,
        }
