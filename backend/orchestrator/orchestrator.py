"""
Orchestrator - Coordinates multiple agents using LangGraph.

This is the brain of the multi-agent system. It:
1. Receives user messages
2. Determines which agent(s) to invoke (LLM-powered routing)
3. Manages token exchange for each agent
4. Handles access denied scenarios gracefully
5. Coordinates multi-agent workflows
6. Returns unified responses with audit trail

Key feature for demo: Shows which agents are accessible based on user's
group membership, with clear success/denied visualization.
"""

import os
import re
from typing import Dict, Any, List, Optional, TypedDict
from langgraph.graph import StateGraph, END
import anthropic
import logging
import json

# Load environment variables for Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "claude-sonnet-4-20250514")  # Model name

from auth.multi_agent_auth import (
    get_multi_agent_exchange,
    AGENT_SALES, AGENT_INVENTORY, AGENT_CUSTOMER, AGENT_PRICING
)
from auth.agent_config import get_agent_config, DEMO_AGENTS
from auth.fga_client import check_agent_access, is_fga_configured, FGACheckResult, ensure_manager_relationship, ensure_clearance_tuple, ensure_viewer_relationship

# Import agent classes
from agents import SalesAgent, InventoryAgent, PricingAgent, CustomerAgent

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """State passed through the LangGraph workflow."""
    messages: List[Any]
    user_message: str
    user_info: Dict[str, Any]
    user_token: str

    # Routing decision
    agents_to_invoke: List[str]
    agent_scopes: Dict[str, List[str]]  # Maps agent_type to required scopes based on intent

    # Agent results (with access status)
    agent_results: Dict[str, Dict[str, Any]]

    # Tracking for demo visibility
    agent_flow: List[Dict[str, Any]]
    token_exchanges: List[Dict[str, Any]]

    # FGA (Fine-Grained Authorization) checks
    fga_checks: List[Dict[str, Any]]

    # Final response
    final_response: Optional[str]


# Agent type to keywords mapping for fallback routing
AGENT_KEYWORDS = {
    AGENT_SALES: ["order", "quote", "deal", "sale", "revenue", "pipeline", "opportunity"],
    AGENT_INVENTORY: ["stock", "inventory", "product", "warehouse", "supply", "available", "in stock"],
    AGENT_CUSTOMER: ["customer", "account", "client", "contact", "tier", "loyalty", "history"],
    AGENT_PRICING: ["price", "discount", "margin", "cost", "profit", "bulk", "wholesale", "retail"],
}

# Scope definitions for each MCP - maps operation type to required scope
# This enables intent-based scope detection to demonstrate Okta governance
SCOPE_DEFINITIONS = {
    AGENT_INVENTORY: {
        "read": {
            "scope": "inventory:read",
            "keywords": ["what", "show", "list", "check", "available", "in stock", "how many", "do we have", "stock level"],
            "description": "View inventory levels"
        },
        "write": {
            "scope": "inventory:write",
            "keywords": ["add", "update", "change", "modify", "increase", "decrease", "set", "put", "remove", "delete", "adjust"],
            "description": "Modify inventory"
        },
        "alert": {
            "scope": "inventory:alert",
            "keywords": ["alert", "notify", "reorder", "low stock", "warning"],
            "description": "Inventory alerts"
        },
    },
    AGENT_PRICING: {
        "read": {
            "scope": "pricing:read",
            "keywords": ["price", "cost", "how much", "what's the price", "pricing"],
            "description": "View prices"
        },
        "margin": {
            "scope": "pricing:margin",
            "keywords": ["margin", "profit", "markup", "profitability", "cost breakdown"],
            "description": "View profit margins"
        },
        "discount": {
            "scope": "pricing:discount",
            "keywords": ["discount", "bulk pricing", "wholesale", "deal", "special price", "volume"],
            "description": "View/apply discounts"
        },
    },
    AGENT_CUSTOMER: {
        "read": {
            "scope": "customer:read",
            "keywords": ["who", "customer", "account", "client", "contact"],
            "description": "View customer info"
        },
        "lookup": {
            "scope": "customer:lookup",
            "keywords": ["lookup", "find", "search", "look up"],
            "description": "Search customers"
        },
        "history": {
            "scope": "customer:history",
            "keywords": ["history", "orders", "purchased", "past", "previous", "transactions"],
            "description": "View purchase history"
        },
    },
    AGENT_SALES: {
        "read": {
            "scope": "sales:read",
            "keywords": ["orders", "sales", "revenue", "pipeline", "show orders"],
            "description": "View sales data"
        },
        "quote": {
            "scope": "sales:quote",
            "keywords": ["quote", "proposal", "estimate", "quotation"],
            "description": "Create quotes"
        },
        "order": {
            "scope": "sales:order",
            "keywords": ["create order", "place order", "new order", "fulfill", "submit order"],
            "description": "Create orders"
        },
    },
}


class Orchestrator:
    """
    Multi-agent orchestrator using LangGraph.

    Routes requests to appropriate agents and coordinates
    complex multi-agent workflows with proper access control.
    """

    def __init__(self, user_token: str, user_info: Optional[Dict[str, Any]] = None):
        """
        Initialize the orchestrator with user context.

        Args:
            user_token: User's ID token (for token exchange)
            user_info: Optional user info from token validation
        """
        self.user_token = user_token
        self.user_info = user_info or {}

        # Get multi-agent token exchange manager
        self.token_exchange = get_multi_agent_exchange()

        # Initialize Anthropic client (raw SDK for better control)
        self.anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info(f"Anthropic client initialized with model: {LLM_MODEL_NAME}")

        # Build the workflow
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("exchange_tokens", self._exchange_tokens_node)
        workflow.add_node("fga_check", self._fga_check_node)  # FGA gatekeeper
        workflow.add_node("process_agents", self._process_agents_node)
        workflow.add_node("generate_response", self._generate_response_node)

        # Linear flow: router -> exchange -> fga_check -> process -> response
        # Token exchange runs FIRST so we can extract Vacation claim from Auth Server token
        # (Org Auth Server doesn't support custom claims, but custom Auth Servers do)
        # FGA check uses Vacation claim from Auth Server token to build contextual tuples
        workflow.set_entry_point("router")
        workflow.add_edge("router", "exchange_tokens")
        workflow.add_edge("exchange_tokens", "fga_check")
        workflow.add_edge("fga_check", "process_agents")
        workflow.add_edge("process_agents", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    async def _router_node(self, state: WorkflowState) -> WorkflowState:
        """
        Determine which agents to invoke and what scopes are needed.

        Uses LLM-powered routing with keyword fallback.
        CRITICAL: Detects intent to determine specific scopes needed.
        """
        message = state["user_message"]
        state["agent_flow"].append({
            "step": "router",
            "action": "Analyzing request to determine relevant agents and required scopes",
            "status": "processing"
        })

        # Use LLM to determine which agents are relevant AND what operations are needed
        try:
            routing_prompt = f"""Analyze this user request and determine:
1. Which AI agents should handle it
2. What specific operations/scopes are needed for each agent

Available agents and their scopes:
1. SALES:
   - sales:read - View orders, sales data, revenue (read-only queries)
   - sales:quote - Create quotes/proposals
   - sales:order - Create/modify orders

2. INVENTORY:
   - inventory:read - View stock levels, product availability (read-only queries like "what do we have", "check stock")
   - inventory:write - Add/update/modify inventory (write operations like "add 5000 basketballs", "update stock")
   - inventory:alert - Manage inventory alerts

3. CUSTOMER:
   - customer:read - View customer information
   - customer:lookup - Search/find customers
   - customer:history - View purchase history

4. PRICING:
   - pricing:read - View prices (basic price queries)
   - pricing:margin - View profit margins (margin/profit queries)
   - pricing:discount - View/apply discounts (bulk/discount queries)

User request: "{message}"

Return a JSON object with agents and their required scopes:
{{
  "sales": {{"needed": true/false, "scopes": ["sales:read"]}},
  "inventory": {{"needed": true/false, "scopes": ["inventory:read"]}},
  "customer": {{"needed": true/false, "scopes": ["customer:read"]}},
  "pricing": {{"needed": true/false, "scopes": ["pricing:read"]}}
}}

IMPORTANT: Choose scopes based on the operation type:
- READ operations (view, show, list, check, what, how many) -> use :read scopes
- WRITE operations (add, update, modify, change, set, put) -> use :write scopes
- For margin/profit queries -> use pricing:margin
- For discount/bulk queries -> use pricing:discount

Return ONLY the JSON object, no other text."""

            # Use raw Anthropic SDK for routing
            response = self.anthropic_client.messages.create(
                model=LLM_MODEL_NAME,
                max_tokens=500,
                messages=[{"role": "user", "content": routing_prompt}]
            )
            response_text = response.content[0].text
            logger.info(f"Router LLM raw response: {response_text[:500]}")

            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text.strip()
            if json_text.startswith("```"):
                # Remove markdown code block
                lines = json_text.split("\n")
                json_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            routing_json = json.loads(json_text)

            agents = []
            agent_scopes = {}

            for agent_type, config in [
                (AGENT_SALES, routing_json.get("sales", {})),
                (AGENT_INVENTORY, routing_json.get("inventory", {})),
                (AGENT_CUSTOMER, routing_json.get("customer", {})),
                (AGENT_PRICING, routing_json.get("pricing", {}))
            ]:
                if config.get("needed"):
                    agents.append(agent_type)
                    agent_scopes[agent_type] = config.get("scopes", [f"{agent_type}:read"])

            logger.info(f"LLM routing decision: agents={agents}, scopes={agent_scopes}")

        except Exception as e:
            logger.warning(f"LLM routing failed, using keyword fallback: {e}")
            agents = self._keyword_routing(message)
            agent_scopes = self._detect_scopes_from_keywords(message, agents)

        # Default to at least one agent
        if not agents:
            agents = [AGENT_SALES]
            agent_scopes = {AGENT_SALES: ["sales:read"]}

        state["agents_to_invoke"] = agents
        state["agent_scopes"] = agent_scopes

        # Build scope summary for display
        scope_summary = ", ".join([f"{a}: {agent_scopes.get(a, [])}" for a in agents])
        state["agent_flow"].append({
            "step": "router",
            "action": f"Selected agents: {', '.join(agents)}",
            "status": "completed",
            "agents": agents,
            "scopes": agent_scopes
        })

        return state

    async def _fga_check_node(self, state: WorkflowState) -> WorkflowState:
        """
        Check FGA permissions AFTER token exchange.
        Filters out agents the user cannot invoke based on fine-grained rules.

        This is the "Okta + FGA Better Together" integration point:
        1. Reads Manager claim from ID token -> creates/deletes manager tuple in FGA
        2. Extracts Vacation claim from Auth Server token
        3. Passes is_on_vacation as contextual tuple to FGA API
        4. FGA checks: can_increase_inventory = manager but not on_vacation
        5. If FGA denies, marks the token exchange result as denied

        Currently checks:
        - inventory agent -> FGA inventory_system with can_increase_inventory relation
        - all other agents -> pass through (no FGA model yet)
        """
        agents = state["agents_to_invoke"]
        agent_results = state.get("agent_results", {})

        # Extract user email for FGA checks (more human-readable than sub)
        user_email = self.user_info.get("email", "")

        if not user_email or not agents:
            return state

        state["agent_flow"].append({
            "step": "fga_check",
            "action": "Checking fine-grained permissions (Auth0 FGA API)",
            "status": "processing"
        })

        # Extract Manager, Vacation, and Clearance claims from Auth Server token
        # (Org Auth Server doesn't support custom claims, so we use Custom Auth Server token)
        is_manager = False
        is_on_vacation = False
        clearance_level = 0

        inventory_result = agent_results.get(AGENT_INVENTORY, {})
        if inventory_result.get("success") and inventory_result.get("access_token"):
            try:
                from jose import jwt as jose_jwt
                auth_token_claims = jose_jwt.get_unverified_claims(inventory_result["access_token"])

                # Extract Manager claim from Auth Server token
                manager_claim = auth_token_claims.get("Manager", auth_token_claims.get("is_a_manager"))
                if manager_claim is not None:
                    is_manager = bool(manager_claim)
                    logger.info(f"Extracted Manager claim from Auth Server token: {manager_claim}")

                # Extract Vacation claim from Auth Server token
                vacation_claim = auth_token_claims.get("Vacation", auth_token_claims.get("is_on_vacation"))
                if vacation_claim is not None:
                    is_on_vacation = bool(vacation_claim)
                    logger.info(f"Extracted Vacation claim from Auth Server token: {vacation_claim}")

                # Extract Clearance claim from Auth Server token
                clearance_claim = auth_token_claims.get("Clearance", auth_token_claims.get("clearance_level"))
                if clearance_claim is not None:
                    try:
                        clearance_level = int(clearance_claim)
                        logger.info(f"Extracted Clearance claim from Auth Server token: {clearance_claim}")
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid Clearance claim value: {clearance_claim}")

                logger.info(f"Auth Server token claims for FGA: {list(auth_token_claims.keys())}")
            except Exception as e:
                logger.warning(f"Could not extract claims from Auth Server token: {e}")

        # Fallback to ID token claims (in case Custom Auth Server not configured)
        if not is_manager:
            is_manager = self.user_info.get("is_manager", self.user_info.get("Manager", False))
        if not is_on_vacation:
            is_on_vacation = self.user_info.get("is_on_vacation", self.user_info.get("Vacation", False))
        if clearance_level == 0:
            clearance_level = int(self.user_info.get("clearance_level", self.user_info.get("Clearance", 0)))

        logger.info(f"FGA check for {user_email}: is_manager={is_manager}, is_on_vacation={is_on_vacation}, clearance={clearance_level}")

        # Step 1: Ensure manager tuple in FGA matches Manager claim
        manager_result = await ensure_manager_relationship(user_email, is_manager, system_id="warehouse")
        logger.info(f"FGA: Manager tuple management result: {manager_result}")

        # Step 2: Ensure viewer tuple for non-managers who need inventory read access
        # Viewer = non-manager who has inventory agent access (can read but not manage)
        is_viewer = not is_manager and AGENT_INVENTORY in agents
        viewer_result = await ensure_viewer_relationship(user_email, is_viewer, system_id="warehouse")
        logger.info(f"FGA: Viewer tuple management result: {viewer_result}")

        # Step 3: Ensure clearance tuple in FGA matches Clearance claim
        if clearance_level > 0:
            clearance_result = await ensure_clearance_tuple(user_email, clearance_level)
            logger.info(f"FGA: Clearance tuple management result: {clearance_result}")

        # Step 4: Check each agent against FGA with vacation as contextual tuple
        allowed_agents = []
        fga_checks = []

        for agent_type in agents:
            scopes = state["agent_scopes"].get(agent_type, [])

            # Run FGA check using FGA API with new model
            # - user_email: from token's email claim
            # - is_on_vacation: passed as contextual tuple if true
            # - item_id: default to "widget-a" (general inventory item)
            # Note: In a real app, you'd map the user's request to specific items
            result: FGACheckResult = await check_agent_access(
                user_email=user_email,
                agent_type=agent_type,
                scopes=scopes,
                is_on_vacation=is_on_vacation,
                item_id="widget-a",  # Default item for demo
            )

            # Determine required clearance for the item (for UI display)
            item_id = "widget-a"  # Default item
            item_required_clearance = 3  # widget-a requires clearance 3
            if "classified" in state["user_message"].lower():
                item_id = "classified-part"
                item_required_clearance = 7  # classified-part requires clearance 7

            # Record the FGA check for UI visibility with real values
            fga_check_record = {
                "agent": agent_type,
                "allowed": result.allowed,
                "relation": result.relation,
                "object": result.object,
                "user": result.user,
                "context": result.context,
                "reason": result.reason,
                "requested_scopes": scopes,
                "contextual_tuples": result.contextual_tuples or [],
                # Real values from Okta claims
                "user_claims": {
                    "is_manager": is_manager,
                    "is_on_vacation": is_on_vacation,
                    "clearance_level": clearance_level,
                },
                # Item info for clearance comparison
                "item_info": {
                    "item_id": item_id,
                    "required_clearance": item_required_clearance,
                },
                # Tuple summary for display
                "stored_tuples": {
                    "manager": f"inventory_system:warehouse" if is_manager else None,
                    "clearance": f"clearance_level:{clearance_level}" if clearance_level > 0 else None,
                },
            }
            fga_checks.append(fga_check_record)

            if result.allowed:
                allowed_agents.append(agent_type)
            else:
                # FGA denied - update the existing token_exchange record to show denial
                # Token was already exchanged, but FGA blocks the action
                for tx in state["token_exchanges"]:
                    if tx.get("agent") == agent_type:
                        tx["success"] = False
                        tx["access_denied"] = True
                        tx["status"] = "denied"
                        tx["error"] = f"FGA: {result.reason}"
                        tx["fga_denied"] = True  # Flag for UI to show FGA-specific styling
                        break
                else:
                    # Fallback: add new record if not found (shouldn't happen)
                    config = get_agent_config(agent_type)
                    demo = DEMO_AGENTS.get(agent_type, {})
                    state["token_exchanges"].append({
                        "agent": agent_type,
                        "agent_name": config.name if config else demo.get("name", ""),
                        "color": config.color if config else demo.get("color", "#888"),
                        "success": False,
                        "access_denied": True,
                        "status": "denied",
                        "scopes": [],
                        "requested_scopes": scopes,
                        "error": f"FGA: {result.reason}",
                        "demo_mode": False,
                        "fga_denied": True,
                    })

                # Mark agent result as denied so process_agents skips it
                if agent_type in agent_results:
                    agent_results[agent_type]["access_denied"] = True
                    agent_results[agent_type]["success"] = False

        state["agents_to_invoke"] = allowed_agents
        state["fga_checks"] = fga_checks

        denied_count = len(agents) - len(allowed_agents)
        fga_status = "API" if is_fga_configured() else "not configured"

        state["agent_flow"].append({
            "step": "fga_check",
            "action": f"FGA ({fga_status}): {len(allowed_agents)} allowed, {denied_count} denied",
            "status": "completed",
            "details": {
                "vacation_status": is_on_vacation,
                "user_email": user_email,
                "contextual_tuples_used": is_on_vacation,  # True if on_vacation tuple was passed
            }
        })

        return state

    def _detect_scopes_from_keywords(self, message: str, agents: List[str]) -> Dict[str, List[str]]:
        """Detect required scopes based on keywords in the message."""
        message_lower = message.lower()
        agent_scopes = {}

        for agent_type in agents:
            if agent_type in SCOPE_DEFINITIONS:
                scopes = []
                for op_type, op_config in SCOPE_DEFINITIONS[agent_type].items():
                    if any(kw in message_lower for kw in op_config["keywords"]):
                        scopes.append(op_config["scope"])

                # Default to read scope if no specific scope detected
                if not scopes:
                    scopes = [f"{agent_type}:read"]

                agent_scopes[agent_type] = scopes
            else:
                agent_scopes[agent_type] = [f"{agent_type}:read"]

        return agent_scopes

    def _keyword_routing(self, message: str) -> List[str]:
        """Fallback keyword-based routing."""
        message_lower = message.lower()
        agents = []

        for agent_type, keywords in AGENT_KEYWORDS.items():
            if any(keyword in message_lower for keyword in keywords):
                agents.append(agent_type)

        return agents if agents else [AGENT_SALES]

    async def _exchange_tokens_node(self, state: WorkflowState) -> WorkflowState:
        """
        Exchange tokens for all selected agents with the detected scopes.

        This is where access control happens - users may be denied
        access to certain scopes based on group membership.
        """
        agents_to_invoke = state["agents_to_invoke"]
        agent_scopes = state.get("agent_scopes", {})

        state["agent_flow"].append({
            "step": "token_exchange",
            "action": "Requesting access tokens with required scopes",
            "status": "processing"
        })

        # Exchange tokens for all selected agents with their specific scopes
        exchange_results = await self.token_exchange.exchange_for_all_agents(
            self.user_token,
            agents_to_invoke,
            agent_scopes  # Pass the intent-based scopes
        )

        # Record token exchanges - use "name" for Token Exchange card (MCP name)
        for agent_type, result in exchange_results.items():
            requested_scopes = result.get("requested_scopes", agent_scopes.get(agent_type, []))

            exchange_record = {
                "agent": agent_type,
                "agent_name": result["agent_info"]["name"],  # MCP name for Token Exchange card
                "color": result["agent_info"]["color"],
                "success": result["success"],
                "access_denied": result.get("access_denied", False),
                "scopes": result.get("scopes", []),
                "requested_scopes": requested_scopes,  # What was requested
                "demo_mode": result.get("demo_mode", False),
                "token_claims": result.get("token_claims"),  # Decoded access token claims
                "access_token": result.get("access_token"),  # Raw access token JWT
                "id_jag_token": result.get("id_jag_token"),  # Raw ID-JAG token (intermediate)
                "id_jag_claims": result.get("id_jag_claims"),  # Decoded ID-JAG claims
            }

            if result.get("access_denied"):
                exchange_record["error"] = result.get("error", f"Access denied for scope(s): {', '.join(requested_scopes)}")
                exchange_record["status"] = "denied"
            elif result["success"]:
                exchange_record["status"] = "granted"
                exchange_record["audience"] = result.get("audience")
            else:
                exchange_record["error"] = result.get("error", "Unknown error")
                exchange_record["status"] = "error"

            state["token_exchanges"].append(exchange_record)

        # Store results for next node
        state["agent_results"] = exchange_results

        # Summary for flow
        granted = sum(1 for r in exchange_results.values() if r["success"] and not r.get("access_denied"))
        denied = sum(1 for r in exchange_results.values() if r.get("access_denied"))

        state["agent_flow"].append({
            "step": "token_exchange",
            "action": f"Token exchange complete: {granted} granted, {denied} denied",
            "status": "completed",
            "summary": {
                "total": len(exchange_results),
                "granted": granted,
                "denied": denied
            }
        })

        return state

    async def _process_agents_node(self, state: WorkflowState) -> WorkflowState:
        """
        Process requests through agents that have access.

        Agents with denied access are skipped but noted in the response.
        """
        agent_results = state["agent_results"]

        state["agent_flow"].append({
            "step": "process_agents",
            "action": "Running authorized agents",
            "status": "processing"
        })

        # For each agent with access, simulate processing
        # In a full implementation, this would call MCP tools
        for agent_type, exchange_result in agent_results.items():
            # Use display_name for Agent Flow card
            display_name = exchange_result["agent_info"].get("display_name", exchange_result["agent_info"]["name"])
            requested_scopes = exchange_result.get("requested_scopes", [])

            if exchange_result["success"] and not exchange_result.get("access_denied"):
                # Agent has access - process the request
                agent_response = await self._invoke_agent(
                    agent_type,
                    state["user_message"],
                    exchange_result
                )
                agent_results[agent_type]["response"] = agent_response

                state["agent_flow"].append({
                    "step": f"{agent_type}_agent",
                    "action": f"{display_name}",
                    "detail": f"Via {exchange_result['agent_info']['name']}",
                    "status": "completed",
                    "color": exchange_result["agent_info"]["color"],
                    "scopes": exchange_result.get("scopes", [])
                })
            elif exchange_result.get("access_denied"):
                state["agent_flow"].append({
                    "step": f"{agent_type}_agent",
                    "action": f"{display_name}",
                    "detail": f"DENIED: {', '.join(requested_scopes)}",
                    "status": "denied",
                    "color": exchange_result["agent_info"]["color"],
                    "requested_scopes": requested_scopes
                })

        state["agent_results"] = agent_results
        return state

    async def _invoke_agent(
        self,
        agent_type: str,
        message: str,
        exchange_result: Dict[str, Any]
    ) -> str:
        """
        Invoke a specific agent to process the request.

        Uses the actual agent classes (SalesAgent, InventoryAgent, etc.)
        which use raw Anthropic SDK for LLM calls.
        """
        scopes = exchange_result.get("scopes", [])
        agent_name = exchange_result["agent_info"]["name"]

        # Map agent type to agent class
        agent_classes = {
            AGENT_SALES: SalesAgent,
            AGENT_INVENTORY: InventoryAgent,
            AGENT_CUSTOMER: CustomerAgent,
            AGENT_PRICING: PricingAgent,
        }

        agent_class = agent_classes.get(agent_type)
        if not agent_class:
            # Fallback to demo data if agent class not found
            data = self._get_demo_data(agent_type, message, scopes)
            return f"[{agent_name}]\n{data}\n(Scopes: {', '.join(scopes)})"

        try:
            # Instantiate and invoke the agent
            agent = agent_class(user_token=self.user_token)
            result = await agent.process(message, context={"scopes": scopes})

            if result.get("success"):
                return f"[{agent_name}]\n{result['result']}\n(Scopes: {', '.join(scopes)})"
            else:
                # Agent LLM call failed, use demo data as fallback
                logger.warning(f"Agent {agent_type} LLM call failed: {result.get('error')}")
                data = self._get_demo_data(agent_type, message, scopes)
                return f"[{agent_name}]\n{data}\n(Scopes: {', '.join(scopes)})"

        except Exception as e:
            logger.error(f"Error invoking agent {agent_type}: {e}")
            # Fallback to demo data
            data = self._get_demo_data(agent_type, message, scopes)
            return f"[{agent_name}]\n{data}\n(Scopes: {', '.join(scopes)})"

    def _get_demo_data(self, agent_type: str, message: str, scopes: List[str] = None) -> str:
        """Get demo data for an agent based on message context and scopes."""
        message_lower = message.lower()
        scopes = scopes or []

        if agent_type == AGENT_SALES:
            if "order" in message_lower or "recent" in message_lower:
                return (
                    "Recent Orders:\n"
                    "- ORD-2024-001: State University Athletics - $7,109.53 (shipped)\n"
                    "- ORD-2024-002: Metro High School District - $23,796.60 (processing)\n"
                    "- ORD-2024-003: Riverside Youth League - $3,608.95 (pending)\n"
                    "- ORD-2024-004: City Pro Basketball Academy - $5,669.69 (shipped)\n"
                    "Pipeline Value: $40,184.77 this week"
                )
            return (
                "Sales Summary:\n"
                "- Active orders: 5 orders totaling $40,184.77\n"
                "- Top customer: Metro High School District ($124,500 lifetime)\n"
                "- Quote ready for 1,500 basketballs @ 20% bulk discount"
            )

        elif agent_type == AGENT_INVENTORY:
            # Check if this is a WRITE operation (user has inventory:write scope)
            has_write_scope = "inventory:write" in scopes
            is_write_request = any(kw in message_lower for kw in ["add", "update", "increase", "set", "put", "remove", "decrease"])

            if has_write_scope and is_write_request:
                # Extract quantity from message (simple pattern matching)
                qty_match = re.search(r'(\d+)\s*(basket|ball|unit)', message_lower)
                quantity = qty_match.group(1) if qty_match else "30"

                return (
                    f"INVENTORY UPDATE SUCCESSFUL:\n"
                    f"- Action: Added {quantity} basketballs to inventory\n"
                    f"- Product: Pro Game Basketball (default SKU)\n"
                    f"- Previous count: 2,847 units\n"
                    f"- New count: {int(quantity) + 2847} units\n"
                    f"- Status: CONFIRMED\n"
                    f"- Transaction ID: INV-2026-{hash(message) % 10000:04d}\n"
                    f"Total basketballs now: {12219 + int(quantity)} units"
                )

            # Read-only inventory data
            if "basketball" in message_lower:
                return (
                    "Basketball Inventory:\n"
                    "- Pro Game Basketball: 2,847 units - GOOD\n"
                    "- Pro Composite: 1,523 units - GOOD\n"
                    "- Women's Official: 1,234 units - GOOD\n"
                    "- Youth Size 5: 3,567 units - GOOD\n"
                    "- Youth Size 4: 2,156 units - GOOD\n"
                    "Total basketballs: 12,219 units available"
                )
            return (
                "Inventory Summary:\n"
                "- Basketballs: 12,219 units (6 SKUs)\n"
                "- Hoops & Backboards: 769 units (4 SKUs)\n"
                "- Uniforms: 21,120 units (4 SKUs)\n"
                "- Training Equipment: 4,700 units (4 SKUs)\n"
                "Low stock alert: Pro Arena Hoop System (45 units)"
            )

        elif agent_type == AGENT_CUSTOMER:
            if "state" in message_lower or "university" in message_lower:
                return (
                    "Customer: State University Athletics\n"
                    "- Tier: Platinum\n"
                    "- Lifetime Value: $89,500 (156 orders)\n"
                    "- Contact: Coach Williams\n"
                    "- Territory: West | Payment: Net 45\n"
                    "Note: Preferred for bulk basketball orders"
                )
            if "platinum" in message_lower or "tier" in message_lower:
                return (
                    "Platinum Tier Customers:\n"
                    "1. Metro High School District - $124,500 lifetime\n"
                    "2. State University Athletics - $89,500 lifetime\n"
                    "3. City Pro Basketball Academy - $67,800 lifetime\n"
                    "Platinum benefits: 5% discount, Net 45-60 terms"
                )
            return (
                "Customer Overview:\n"
                "- Platinum: 3 accounts ($281,800 combined)\n"
                "- Gold: 3 accounts ($63,500 combined)\n"
                "- Silver: 2 accounts ($15,200 combined)\n"
                "Top: Metro High School District ($124,500)"
            )

        elif agent_type == AGENT_PRICING:
            if "basketball" in message_lower or "margin" in message_lower:
                return (
                    "Basketball Pricing:\n"
                    "- Pro Game: $149.99 (cost $62, margin 58.7%)\n"
                    "- Pro Composite: $89.99 (cost $38, margin 57.8%)\n"
                    "- Women's Official: $129.99 (cost $55, margin 57.7%)\n"
                    "- Youth Size 5: $34.99 (cost $14, margin 60.0%)\n"
                    "Average basketball margin: 58.8%"
                )
            if "bulk" in message_lower or "discount" in message_lower:
                return (
                    "Bulk Discounts:\n"
                    "- 10+ units: 5% | 50+ units: 10%\n"
                    "- 100+ units: 15% | 500+ units: 20%\n"
                    "Customer Tier Bonuses:\n"
                    "- Platinum: +5% | Gold: +3%\n"
                    "Example: 1,500 units @ Platinum = 25% total discount"
                )
            return (
                "Pricing Overview:\n"
                "- Average margin: 58.2% across all products\n"
                "- Highest: Youth basketballs (60%)\n"
                "- Volume discounts: 5-20% based on quantity\n"
                "- Tier discounts: 0-5% based on customer status"
            )

        return "Data not available for this query."

    async def _generate_response_node(self, state: WorkflowState) -> WorkflowState:
        """
        Generate a unified response combining all agent outputs.

        Clearly indicates which agents contributed and which were denied.
        """
        agent_results = state["agent_results"]

        # Collect successful responses and denied agents
        responses = []
        denied_agents = []

        for agent_type, result in agent_results.items():
            if result["success"] and "response" in result:
                responses.append(result["response"])
            elif result.get("access_denied"):
                denied_agents.append(result["agent_info"]["name"])

        # Generate combined response
        if responses:
            # Use LLM to create natural combined response
            combined_data = "\n\n".join(responses)
            synthesis_prompt = f"""Based on the following agent responses, provide a helpful, natural answer
to the user's question: "{state['user_message']}"

Agent responses:
{combined_data}

{"Note: The user was denied access to these agents: " + ", ".join(denied_agents) if denied_agents else ""}

Provide a concise, helpful response that combines the relevant information.
If some agents were denied, acknowledge what information is missing but focus on what IS available."""

            try:
                # Use raw Anthropic SDK for response synthesis
                response = self.anthropic_client.messages.create(
                    model=LLM_MODEL_NAME,
                    max_tokens=1024,
                    system="You are a helpful AI assistant for ProGear Sporting Goods.",
                    messages=[{"role": "user", "content": synthesis_prompt}]
                )
                final_response = response.content[0].text
            except Exception as e:
                logger.error(f"Response synthesis failed: {e}")
                final_response = combined_data

        elif denied_agents:
            final_response = (
                f"I apologize, but you don't have access to the agents needed for this request.\n\n"
                f"Access denied for: {', '.join(denied_agents)}\n\n"
                f"Please contact your administrator if you need access to this information."
            )
        else:
            final_response = (
                "I'm not sure how to help with that request. "
                "Try asking about orders, inventory, pricing, or customer information."
            )

        state["final_response"] = final_response

        # Add denied agents info if any
        if denied_agents:
            state["final_response"] += f"\n\n[Note: Limited access - denied agents: {', '.join(denied_agents)}]"

        state["agent_flow"].append({
            "step": "generate_response",
            "action": "Generated combined response",
            "status": "completed"
        })

        return state

    async def process(self, message: str) -> Dict[str, Any]:
        """
        Process a user message through the orchestrator.

        Args:
            message: User's message

        Returns:
            Dict with:
            - content: Final response
            - agent_flow: Steps taken
            - token_exchanges: Token exchange results per agent
        """
        # Initialize state
        initial_state: WorkflowState = {
            "messages": [],
            "user_message": message,
            "user_info": self.user_info,
            "user_token": self.user_token,
            "agents_to_invoke": [],
            "agent_scopes": {},  # Will be populated by router based on intent
            "agent_results": {},
            "agent_flow": [],
            "token_exchanges": [],
            "fga_checks": [],  # FGA fine-grained authorization checks
            "final_response": None,
        }

        # Run the workflow
        final_state = await self.workflow.ainvoke(initial_state)

        return {
            "content": final_state["final_response"],
            "agent_flow": final_state["agent_flow"],
            "token_exchanges": final_state["token_exchanges"],
            "fga_checks": final_state["fga_checks"],
        }
