"""
Base Agent - Common functionality for all ProGear agents.

Uses raw Anthropic SDK (not LangChain wrappers) per project preference.
"""

import os
import logging
from typing import Dict, Any, Optional
import anthropic

logger = logging.getLogger(__name__)

# Anthropic configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "claude-sonnet-4-20250514")


class BaseAgent:
    """
    Base class for all ProGear agents.

    Provides:
    - Raw Anthropic SDK client
    - Common process() interface
    - System prompt handling
    """

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        scopes: list,
        user_token: str,
        color: str = "#888888",
    ):
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.scopes = scopes
        self.user_token = user_token
        self.color = color

        # Initialize Anthropic client (raw SDK)
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = LLM_MODEL_NAME

    def get_system_prompt(self) -> str:
        """Override in subclass to provide agent-specific system prompt."""
        raise NotImplementedError

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a task using the agent's LLM.

        Args:
            task: The user's request
            context: Additional context (scopes, token info, etc.)

        Returns:
            Dict with agent response and metadata
        """
        context = context or {}

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.get_system_prompt(),
                messages=[{"role": "user", "content": task}]
            )
            result = response.content[0].text
            success = True
            error = None
        except Exception as e:
            logger.error(f"[{self.agent_name}] LLM call failed: {e}")
            result = f"I encountered an error processing your request: {e}"
            success = False
            error = str(e)

        return {
            "agent": self.agent_type,
            "agent_name": self.agent_name,
            "color": self.color,
            "result": result,
            "success": success,
            "error": error,
            "scopes": context.get("scopes", self.scopes),
        }
