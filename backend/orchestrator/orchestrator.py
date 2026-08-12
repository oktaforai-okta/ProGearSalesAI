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
import httpx
import logging
import json

# Load environment variables for Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "claude-sonnet-4-6")  # Model name - previous default (claude-sonnet-4-20250514) was retired

from auth.multi_agent_auth import (
    get_multi_agent_exchange,
    AGENT_SALES, AGENT_INVENTORY, AGENT_CUSTOMER, AGENT_PRICING
)
from auth.agent_config import get_agent_config, DEMO_AGENTS
from auth.fga_client import check_agent_access, is_fga_configured, FGACheckResult
from auth.inventory_policy import (
    decide_inventory_policy,
    normalize_role_level,
    role_name,
    simple_authorization_message,
)
from auth.resource_token import ResourceTokenError, get_resource_token_validator

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
    simulate_fga: bool

    # Final business decisions are separate from coarse token issuance.
    authorization_decisions: List[Dict[str, Any]]

    # Final response
    final_response: Optional[str]

    # Approval gate (populated by approval_gate node; None when gate is not triggered)
    pending_approval: Optional[Dict[str, Any]]
    parsed_intent: Optional[Dict[str, Any]]
    delegation_denial_reason: Optional[str]


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
            "scope": "inventory:read",
            "keywords": ["alert", "notify", "reorder", "low stock", "warning"],
            "description": "View inventory alerts"
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

    def __init__(
        self,
        user_token: str,
        user_info: Optional[Dict[str, Any]] = None,
        approval_service=None,
    ):
        """
        Initialize the orchestrator with user context.

        Args:
            user_token: User's ID token (for token exchange)
            user_info: Optional user info from token validation
            approval_service: Optional ApprovalService (inject from api/main.py)
        """
        self.user_token = user_token
        self.user_info = user_info or {}
        self.approval_service = approval_service

        # Get multi-agent token exchange manager
        self.token_exchange = get_multi_agent_exchange()

        # Keep all model I/O non-blocking. This orchestrator runs inside an
        # async web request, so the synchronous SDK can starve concurrent Okta
        # profile requests and cause false authorization-context timeouts.
        self.anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        logger.info(f"Anthropic client initialized with model: {LLM_MODEL_NAME}")

        # Build the workflow
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("pre_exchange_guard", self._pre_exchange_guard_node)
        workflow.add_node("exchange_tokens", self._exchange_tokens_node)
        workflow.add_node("fga_check", self._fga_check_node)
        workflow.add_node("approval_gate", self._approval_gate_node)
        workflow.add_node("process_agents", self._process_agents_node)
        workflow.add_node("generate_response", self._generate_response_node)

        # Known hard denials stop before delegated tokens are requested. Other
        # requests continue through token exchange, resource validation, and
        # (when enabled) the FGA/approval decision.
        workflow.set_entry_point("router")
        workflow.add_edge("router", "pre_exchange_guard")

        def _route_after_pre_exchange_guard(state: WorkflowState) -> str:
            return "exchange_tokens" if state.get("agents_to_invoke") else "generate_response"

        workflow.add_conditional_edges(
            "pre_exchange_guard",
            _route_after_pre_exchange_guard,
            {
                "exchange_tokens": "exchange_tokens",
                "generate_response": "generate_response",
            },
        )
        workflow.add_edge("exchange_tokens", "fga_check")
        workflow.add_edge("fga_check", "approval_gate")

        def _route_after_approval(state: WorkflowState) -> str:
            # Gate fired (pending or error) → skip process_agents, go straight to response.
            if state.get("pending_approval") is not None:
                return "generate_response"
            last_flow = state.get("agent_flow", [])
            if last_flow and last_flow[-1].get("step") == "approval_gate" and last_flow[-1].get("status") == "error":
                return "generate_response"
            return "process_agents"

        workflow.add_conditional_edges(
            "approval_gate",
            _route_after_approval,
            {
                "generate_response": "generate_response",
                "process_agents": "process_agents",
            },
        )

        workflow.add_edge("process_agents", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    async def _pre_exchange_guard_node(self, state: WorkflowState) -> WorkflowState:
        """Stop delegation or writes that live Okta context cannot initiate.

        Vacation is a global delegation stop: no selected domain may request
        an ID-JAG while the employee is marked away. Otherwise, Sales writes
        are always denied here. In simple mode, Manager writes
        above 600 units also stop here. In FGA mode those Manager requests are
        allowed to continue because the later FGA/OIG path can request VP
        approval. No ID-JAG or resource token is requested for a stopped
        domain.
        """
        agents = list(state.get("agents_to_invoke", []))
        if self.user_info.get("is_on_vacation") is True:
            message = (
                "I can’t act on your behalf while your Okta profile says you’re on vacation. "
                "No delegated token was requested. Set On vacation to False or contact your "
                "Okta administrator."
            )
            state["delegation_denial_reason"] = message
            for agent_type in agents:
                scopes = state.get("agent_scopes", {}).get(agent_type, [])
                config = get_agent_config(agent_type)
                demo = DEMO_AGENTS.get(agent_type, {})
                agent_info = {
                    "name": config.name if config else demo.get("name", agent_type.title()),
                    "display_name": config.display_name if config else demo.get("display_name", agent_type.title()),
                    "color": config.color if config else demo.get("color", "#888"),
                }
                state.setdefault("agent_results", {})[agent_type] = {
                    "success": False,
                    "access_denied": True,
                    "requested_scopes": scopes,
                    "authorization_reason": message,
                    "error": message,
                    "error_code": "delegation_suspended",
                    "token_issued": False,
                    "resource_token_validated": False,
                    "agent_info": agent_info,
                }
                state.setdefault("authorization_decisions", []).append({
                    "agent": agent_type,
                    "mode": "okta",
                    "engine": "Okta delegation policy",
                    "operation": "write" if any(scope.endswith(":write") for scope in scopes) else "read",
                    "quantity": None,
                    "role_level": normalize_role_level(self.user_info.get("clearance_level")),
                    "role_name": role_name(normalize_role_level(self.user_info.get("clearance_level"))),
                    "decision": "deny",
                    "outcome": "blocked",
                    "reason": message,
                    "token_issued": False,
                    "token_validated": False,
                })
            state["agents_to_invoke"] = []
            state.setdefault("agent_flow", []).append({
                "step": "pre_exchange_guard",
                "action": "Okta vacation policy stopped delegated access before token exchange",
                "detail": message,
                "status": "denied",
            })
            return state

        if AGENT_INVENTORY not in agents:
            return state

        scopes = state.get("agent_scopes", {}).get(AGENT_INVENTORY, [])
        if "inventory:write" not in scopes:
            return state

        clearance_level = normalize_role_level(
            self.user_info.get("clearance_level", self.user_info.get("Clearance"))
        )
        policy = decide_inventory_policy(scopes, state["user_message"], clearance_level)
        should_stop = bool(policy.hard_denial_reason) or (
            not state.get("simulate_fga", False) and not policy.direct_allowed
        )
        if not should_stop:
            return state

        message = simple_authorization_message(policy)
        if message is None:
            message = "I can’t complete that request with your current permissions."
        config = get_agent_config(AGENT_INVENTORY)
        demo = DEMO_AGENTS.get(AGENT_INVENTORY, {})
        agent_info = {
            "name": config.name if config else demo.get("name", "Inventory"),
            "display_name": (
                config.display_name if config else demo.get("display_name", "Inventory")
            ),
            "color": config.color if config else demo.get("color", "#888"),
        }

        state.setdefault("agent_results", {})[AGENT_INVENTORY] = {
            "success": False,
            "access_denied": True,
            "requested_scopes": scopes,
            "authorization_reason": message,
            "error": message,
            "error_code": "insufficient_clearance",
            "token_issued": False,
            "resource_token_validated": False,
            "agent_info": agent_info,
        }
        state.setdefault("authorization_decisions", []).append({
            "agent": AGENT_INVENTORY,
            "mode": "okta",
            "engine": "Okta clearance policy",
            "operation": policy.operation,
            "quantity": policy.quantity,
            "role_level": clearance_level,
            "role_name": role_name(clearance_level),
            "required_level": policy.required_level,
            "required_role": policy.required_role,
            "relation": policy.relation,
            "decision": "deny",
            "outcome": "blocked",
            "reason": message,
            "token_issued": False,
            "token_validated": False,
            "approval_role": policy.approval_role,
            "approval_level": policy.approval_level,
        })
        state["agents_to_invoke"] = [agent for agent in agents if agent != AGENT_INVENTORY]
        state.setdefault("agent_flow", []).append({
            "step": "pre_exchange_guard",
            "action": "Okta clearance stopped the inventory write before token exchange",
            "detail": message,
            "status": "denied",
            "requested_scopes": scopes,
        })
        return state

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
            response = await self.anthropic_client.messages.create(
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
        """Apply the request's trusted authorization context to FGA.

        The role context always comes from live Okta and its signed resource
        token. Hosted FGA simulation can overlay only vacation at the earlier
        delegation gate. It cannot change role or manufacture an Okta scope:
        token exchange and resource validation happen before this node.
        """
        agents = state["agents_to_invoke"]
        agent_results = state.get("agent_results", {})
        user_email = self.user_info.get("email", "")

        if not user_email or not agents:
            return state

        if not state.get("simulate_fga", False):
            return await self._simple_authorization_node(state)

        state["agent_flow"].append({
            "step": "fga_check",
            "action": "Checking fine-grained permissions (FGA API)",
            "status": "processing"
        })

        # The API always resolves this value from the authenticated employee's
        # live Okta profile. FGA simulation never replaces the role.
        clearance_level = normalize_role_level(
            self.user_info.get("clearance_level", self.user_info.get("Clearance"))
        )
        inventory_result = agent_results.get(AGENT_INVENTORY, {})

        logger.info(
            "FGA check for %s: role_level=%s (%s)",
            user_email,
            clearance_level,
            role_name(clearance_level),
        )

        allowed_agents = []
        fga_checks = []

        for agent_type in agents:
            scopes = state["agent_scopes"].get(agent_type, [])
            exchange_result = agent_results.get(agent_type, {})
            if not exchange_result.get("success") or exchange_result.get("access_denied"):
                state["authorization_decisions"].append({
                    "agent": agent_type,
                    "mode": "fga",
                    "engine": "Resource server",
                    "operation": "write" if any(scope.endswith(":write") for scope in scopes) else "read",
                    "quantity": None,
                    "role_level": clearance_level,
                    "role_name": role_name(clearance_level),
                    "decision": "deny",
                    "outcome": "blocked",
                    "reason": exchange_result.get("error", "The resource token was not accepted."),
                    "token_issued": bool(exchange_result.get("token_issued")),
                    "token_validated": bool(exchange_result.get("resource_token_validated")),
                })
                continue
            policy = decide_inventory_policy(
                scopes,
                state["user_message"],
                clearance_level,
            )
            result: FGACheckResult = await check_agent_access(
                user_email=user_email,
                agent_type=agent_type,
                scopes=scopes,
                role_level=clearance_level,
                relation=policy.relation if agent_type == AGENT_INVENTORY else None,
            )

            request_allowed = False
            request_check_reason = None
            if agent_type == AGENT_INVENTORY and policy.approval_required:
                request_result = await check_agent_access(
                    user_email=user_email,
                    agent_type=agent_type,
                    scopes=scopes,
                    role_level=clearance_level,
                    relation="can_request_change",
                )
                request_allowed = request_result.allowed
                request_check_reason = request_result.reason

            effective_allowed = result.allowed
            if agent_type == AGENT_INVENTORY:
                effective_allowed = (
                    result.allowed
                    and not policy.approval_required
                    and policy.hard_denial_reason is None
                )
            fga_check_record = {
                "agent": agent_type,
                "allowed": effective_allowed,
                "direct_allowed": result.allowed,
                "request_allowed": request_allowed,
                "request_check_reason": request_check_reason,
                "relation": result.relation,
                "object": result.object,
                "user": result.user,
                "context": result.context,
                "reason": result.reason,
                "requested_scopes": scopes,
                "contextual_tuples": result.contextual_tuples or [],
                "user_claims": {
                    "clearance_level": clearance_level,
                    "role_name": role_name(clearance_level),
                },
                "policy": {
                    "operation": policy.operation,
                    "quantity": policy.quantity,
                    "required_level": policy.required_level,
                    "required_role": policy.required_role,
                    "approval_required": policy.approval_required,
                    "approval_level": policy.approval_level,
                    "approval_role": policy.approval_role,
                    "hard_denial_reason": policy.hard_denial_reason,
                },
            }
            fga_checks.append(fga_check_record)

            approval_route = (
                agent_type == AGENT_INVENTORY
                and policy.approval_required
                and request_allowed
                and policy.hard_denial_reason is None
            )

            if effective_allowed:
                allowed_agents.append(agent_type)
            elif not approval_route:
                denial_reason = (
                    policy.hard_denial_reason
                    or result.reason
                )
                for tx in state["token_exchanges"]:
                    if tx.get("agent") == agent_type:
                        # The signed token was genuinely issued and validated.
                        # Preserve it as evidence; FGA is a later business-action
                        # decision, not a retroactive token-exchange failure.
                        tx["business_decision"] = "blocked"
                        tx["business_reason"] = denial_reason
                        break
                else:
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
                        "error": f"FGA: {denial_reason}",
                        "demo_mode": False,
                        "fga_denied": True,
                    })

                if agent_type in agent_results:
                    agent_results[agent_type]["access_denied"] = True
                    agent_results[agent_type]["success"] = False

            decision = "allow" if effective_allowed else "approval_required" if approval_route else "deny"
            state["authorization_decisions"].append({
                "agent": agent_type,
                "mode": "fga",
                "engine": "FGA",
                "operation": policy.operation,
                "quantity": policy.quantity,
                "role_level": clearance_level,
                "role_name": role_name(clearance_level),
                "required_level": policy.required_level,
                "required_role": policy.required_role,
                "relation": policy.relation,
                "decision": decision,
                "outcome": "authorized" if effective_allowed else "awaiting_approval" if approval_route else "blocked",
                "reason": result.reason if effective_allowed else (
                    f"{policy.approval_role} approval is required."
                    if approval_route
                    else denial_reason
                ),
                "token_issued": bool(inventory_result.get("access_token")) if agent_type == AGENT_INVENTORY else True,
                "token_validated": bool(inventory_result.get("resource_token_validated")) if agent_type == AGENT_INVENTORY else True,
                "approval_role": policy.approval_role,
                "approval_level": policy.approval_level,
            })

            # An approval route is not a failed Okta token exchange and not a
            # hard FGA denial. Keep the real tokens as evidence that the
            # coarse resource boundary passed; the approval gate below owns
            # the pending action and prevents direct Inventory execution.

        state["agents_to_invoke"] = allowed_agents
        state["fga_checks"] = fga_checks

        approval_count = sum(
            1
            for check in fga_checks
            if check.get("policy", {}).get("approval_required")
            and check.get("request_allowed")
            and not check.get("policy", {}).get("hard_denial_reason")
        )
        denied_count = len(agents) - len(allowed_agents) - approval_count
        fga_status = "API" if is_fga_configured() else "not configured"

        state["agent_flow"].append({
            "step": "fga_check",
            "action": (
                f"FGA ({fga_status}): {len(allowed_agents)} direct, "
                f"{approval_count} approval, {denied_count} denied"
            ),
            "status": "completed",
            "details": {
                "role_level": clearance_level,
                "role_name": role_name(clearance_level),
                "user_email": user_email,
                "contextual_tuples_used": True,
            }
        })

        return state

    async def _simple_authorization_node(self, state: WorkflowState) -> WorkflowState:
        """Apply the safe Sarah/Mike policy without calling FGA or OIG.

        Simple mode is intentionally at least as restrictive as FGA mode: a
        role that cannot execute directly is denied instead of being routed
        to approval. The decision comes from the validated Okta-signed role
        claim, so a browser flag can never grant extra write permission.
        """
        agents = state["agents_to_invoke"]
        agent_results = state.get("agent_results", {})
        clearance_level = -1

        inventory_result = agent_results.get(AGENT_INVENTORY, {})
        if inventory_result.get("resource_token_validated"):
            claims = inventory_result.get("token_claims") or {}
            clearance_level = normalize_role_level(
                claims.get("Clearance", claims.get("clearance_level"))
            )

        if clearance_level == -1:
            clearance_level = normalize_role_level(
                self.user_info.get("clearance_level", self.user_info.get("Clearance"))
            )

        state["agent_flow"].append({
            "step": "simple_authorization",
            "action": "Applying the simple Okta role policy (FGA simulation is off)",
            "status": "processing",
        })

        allowed_agents = []
        denied_count = 0
        for agent_type in agents:
            result = agent_results.get(agent_type, {})
            if not result.get("success") or result.get("access_denied"):
                continue
            if agent_type != AGENT_INVENTORY:
                allowed_agents.append(agent_type)
                continue

            scopes = state["agent_scopes"].get(agent_type, [])
            policy = decide_inventory_policy(
                scopes,
                state["user_message"],
                clearance_level,
            )
            if policy.direct_allowed:
                allowed_agents.append(agent_type)
                message = None
            else:
                denied_count += 1
                message = simple_authorization_message(policy)
                if message is None:
                    # direct_allowed above makes this unreachable; keep the guard
                    # so a future policy change cannot accidentally grant access.
                    message = "I can’t complete that request with your current permissions."
                result["success"] = False
                result["access_denied"] = True
                result["authorization_reason"] = message
                result["requested_scopes"] = scopes

            state["authorization_decisions"].append({
                "agent": agent_type,
                "mode": "simple",
                "engine": "Okta role policy",
                "operation": policy.operation,
                "quantity": policy.quantity,
                "role_level": clearance_level,
                "role_name": role_name(clearance_level),
                "required_level": policy.required_level,
                "required_role": policy.required_role,
                "relation": policy.relation,
                "decision": "allow" if policy.direct_allowed else "deny",
                "outcome": "authorized" if policy.direct_allowed else "blocked",
                "reason": (
                    f"{role_name(clearance_level)} satisfies the direct-execution rule."
                    if policy.direct_allowed
                    else message
                ),
                "token_issued": bool(inventory_result.get("access_token")),
                "token_validated": bool(inventory_result.get("resource_token_validated")),
                "approval_role": None,
                "approval_level": None,
            })

        state["agents_to_invoke"] = allowed_agents
        state["agent_results"] = agent_results
        state["fga_checks"] = []
        state["agent_flow"].append({
            "step": "simple_authorization",
            "action": (
                f"Simple role policy: {len(allowed_agents)} direct, "
                f"{denied_count} denied, no approval requests"
            ),
            "status": "completed",
            "details": {
                "role_level": clearance_level,
                "role_name": role_name(clearance_level),
            },
        })
        return state

    async def _approval_gate_node(self, state: WorkflowState) -> WorkflowState:
        """Create the VP OIG request selected by the FGA policy.

        Only a Manager write of 601+ routes to a VP. Sales and malformed
        requests are hard denials and never turn into approval requests.
        """
        from services.intent import parse_inventory_intent  # local import — same style as existing backend modules

        if not state.get("simulate_fga", False):
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": "FGA simulation is off; no approval request is created",
                "status": "skipped",
            })
            return state

        agent_scopes = state.get("agent_scopes", {}) or {}
        inv_scopes = agent_scopes.get(AGENT_INVENTORY, []) or []

        if "inventory:write" not in inv_scopes:
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": "No inventory:write scope in request; skipping approval check",
                "status": "skipped",
            })
            return state

        fga_record = next(
            (check for check in state.get("fga_checks", []) if check.get("agent") == AGENT_INVENTORY),
            None,
        )
        policy = (fga_record or {}).get("policy") or {}

        hard_denial = policy.get("hard_denial_reason")
        if hard_denial:
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": hard_denial,
                "status": "denied",
            })
            return state

        parsed = parse_inventory_intent(state["user_message"])
        state["parsed_intent"] = parsed

        if not policy.get("approval_required"):
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": "The user's role can execute this quantity directly",
                "status": "skipped",
            })
            return state

        if not (fga_record or {}).get("request_allowed"):
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": "FGA denied permission to submit an inventory change request",
                "status": "denied",
            })
            return state

        if self.approval_service is None:
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": "Approval is required, but the approval service is not configured",
                "status": "error",
            })
            return state

        approval_role = str(policy.get("approval_role") or "VP")
        approval_level = int(policy.get("approval_level") or 2)
        approver_group = os.getenv("OKTA_VP_APPROVER_GROUP_NAME", "ProGear-VPs")
        try:
            fga_check_id = None
            if state.get("fga_checks"):
                fga_check_id = state["fga_checks"][-1].get("id")
            inventory_config = get_agent_config(AGENT_INVENTORY)
            request_id, intent = await self.approval_service.create_request(
                user_email=self.user_info.get("email") or "",
                requester_id=(
                    self.user_info.get("okta_user_id")
                    or self.user_info.get("sub")
                    or self.user_info.get("id")
                    or ""
                ),
                approver_group_name=approver_group,
                agent=AGENT_INVENTORY,
                scope="inventory:write",
                parsed_intent=parsed,
                original_task=state["user_message"],
                agent_id=inventory_config.agent_id if inventory_config else None,
                fga_check_id=fga_check_id,
                required_approver_role=approval_role,
                required_approver_level=approval_level,
            )
        except Exception as exc:
            logger.error(f"approval_gate create_request failed: {exc}")
            state["agent_flow"].append({
                "step": "approval_gate",
                "action": f"Approval service error: {exc}",
                "status": "error",
            })
            # Clear results so process_agents does nothing; response node reports the error.
            state["agent_results"] = {}
            state["pending_approval"] = None
            return state

        state["agent_flow"].append({
            "step": "approval_gate",
            "action": f"Queued OIG Access Request {request_id} for {approver_group}",
            "status": "pending",
        })
        state["pending_approval"] = {
            "request_id": request_id,
            "status": "pending",
            "approver_group": approver_group,
            "approver_role": approval_role,
            "approver_level": approval_level,
            "submitted_at": intent.submitted_at,
            "intent": {
                "product_name": intent.product_name,
                "quantity_delta": intent.quantity_delta,
                "scope": intent.scope,
                "original_task": intent.original_task,
            },
        }
        for decision in reversed(state.get("authorization_decisions", [])):
            if decision.get("agent") == AGENT_INVENTORY:
                decision["outcome"] = "awaiting_approval"
                decision["request_id"] = request_id
                decision["approver_group"] = approver_group
                break
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

        # A successful exchange means Okta issued a coarse resource token. The
        # resource still validates that JWT independently before policy or data
        # access. This makes the write path enforceable rather than a UI-only
        # simulation.
        validator = get_resource_token_validator()
        expected_subjects = [
            self.user_info.get("email"),
            self.user_info.get("sub"),
        ]
        for agent_type, result in exchange_results.items():
            requested_scopes = result.get("requested_scopes", agent_scopes.get(agent_type, []))
            result["token_issued"] = bool(result.get("success") and result.get("access_token"))
            result["resource_token_validated"] = False
            if not result["token_issued"]:
                continue
            if result.get("demo_mode"):
                if any(scope.endswith(":write") for scope in requested_scopes):
                    result["success"] = False
                    result["error"] = "A real signed resource token is required for writes."
                    result["error_code"] = "resource_token_required"
                continue
            try:
                validated = await validator.validate(
                    result["access_token"],
                    agent_type=agent_type,
                    required_scopes=requested_scopes,
                    expected_subjects=expected_subjects,
                )
                result["resource_token_validated"] = True
                result["token_claims"] = validated.claims
                result["resource_token_kid"] = validated.key_id
            except (ResourceTokenError, httpx.HTTPError) as exc:
                logger.warning("[%s] Resource token rejected: %s", agent_type, exc)
                result["success"] = False
                result["access_denied"] = False
                result["error"] = str(exc)
                result["error_code"] = "invalid_resource_token"

        # Record token exchanges - use "name" for Token Exchange card (MCP name)
        for agent_type, result in exchange_results.items():
            requested_scopes = result.get("requested_scopes", agent_scopes.get(agent_type, []))

            exchange_record = {
                "agent": agent_type,
                "agent_name": result["agent_info"]["name"],  # MCP name for Token Exchange card
                "color": result["agent_info"]["color"],
                # Keep token issuance truthful even if the resource rejects the
                # token in the next stage.
                "success": result.get("token_issued", result["success"]),
                "access_denied": result.get("access_denied", False),
                "scopes": result.get("scopes", []),
                "requested_scopes": requested_scopes,  # What was requested
                "demo_mode": result.get("demo_mode", False),
                "token_claims": result.get("token_claims"),  # Decoded access token claims
                "access_token": result.get("access_token"),  # Raw access token JWT
                "id_jag_token": result.get("id_jag_token"),  # Raw ID-JAG token (intermediate)
                "id_jag_claims": result.get("id_jag_claims"),  # Decoded ID-JAG claims
                "resource_token_validated": result.get("resource_token_validated", False),
                "resource_token_kid": result.get("resource_token_kid"),
                "resource_validation_error": (
                    result.get("error")
                    if result.get("token_issued") and not result.get("resource_token_validated")
                    else None
                ),
            }

            if result.get("access_denied"):
                exchange_record["error"] = result.get("error", f"Access denied for scope(s): {', '.join(requested_scopes)}")
                exchange_record["status"] = "denied"
            elif result.get("token_issued"):
                exchange_record["status"] = "granted"
                exchange_record["audience"] = result.get("audience")
            else:
                exchange_record["error"] = result.get("error", "Unknown error")
                exchange_record["status"] = "error"

            state["token_exchanges"].append(exchange_record)

        # Preserve any domain stopped by the pre-exchange guard while adding
        # the exchange results for domains that were allowed to continue.
        state["agent_results"] = {
            **state.get("agent_results", {}),
            **exchange_results,
        }

        # Summary for flow
        granted = sum(1 for r in exchange_results.values() if r.get("token_issued") and not r.get("access_denied"))
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

            is_authorized = agent_type in state.get("agents_to_invoke", [])
            decision = next(
                (
                    item
                    for item in reversed(state.get("authorization_decisions", []))
                    if item.get("agent") == agent_type
                ),
                None,
            )

            if (
                exchange_result["success"]
                and not exchange_result.get("access_denied")
                and is_authorized
            ):
                if not exchange_result.get("resource_token_validated") and not exchange_result.get("demo_mode"):
                    exchange_result["success"] = False
                    exchange_result["error"] = "The resource token was not validated."
                    if decision:
                        decision["decision"] = "deny"
                        decision["outcome"] = "blocked"
                        decision["reason"] = exchange_result["error"]
                    continue

                # The token and final business decision have both passed.
                agent_outcome = await self._invoke_agent(
                    agent_type,
                    state["user_message"],
                    exchange_result,
                    decision,
                )
                if not agent_outcome["success"]:
                    exchange_result["success"] = False
                    exchange_result["error"] = agent_outcome.get("error") or "Resource operation failed"
                    if decision:
                        decision["decision"] = "deny"
                        decision["outcome"] = "blocked"
                        decision["reason"] = exchange_result["error"]
                    state["agent_flow"].append({
                        "step": f"{agent_type}_agent",
                        "action": f"{display_name}",
                        "detail": f"RESOURCE BLOCKED: {exchange_result['error']}",
                        "status": "error",
                        "color": exchange_result["agent_info"]["color"],
                        "requested_scopes": requested_scopes,
                    })
                    continue

                agent_results[agent_type]["response"] = agent_outcome["response"]
                agent_results[agent_type]["response_is_final"] = agent_outcome.get(
                    "response_is_final",
                    False,
                )
                if decision:
                    decision["outcome"] = "executed"

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
            else:
                # Real system/infrastructure error (expired token, Okta outage, SDK
                # failure, etc.) - distinct from access_denied. Without this branch
                # the agent silently vanishes from agent_flow (stuck "pending" in the
                # UI forever) and _generate_response_node has nothing to say about it,
                # degrading to the generic "I'm not sure how to help" message that
                # looks like a routing failure but is actually a masked backend error.
                error_detail = exchange_result.get("error", "Unknown error")
                state["agent_flow"].append({
                    "step": f"{agent_type}_agent",
                    "action": f"{display_name}",
                    "detail": f"SYSTEM ERROR: {error_detail}",
                    "status": "error",
                    "color": exchange_result["agent_info"]["color"],
                    "requested_scopes": requested_scopes
                })

        state["agent_results"] = agent_results
        return state

    async def _invoke_agent(
        self,
        agent_type: str,
        message: str,
        exchange_result: Dict[str, Any],
        authorization_decision: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            return {
                "success": True,
                "response": f"[{agent_name}]\n{data}\n(Scopes: {', '.join(scopes)})",
            }

        try:
            # Instantiate and invoke the agent
            agent = agent_class(user_token=self.user_token)
            result = await agent.process(
                message,
                context={
                    "scopes": scopes,
                    "resource_token_validated": exchange_result.get("resource_token_validated", False),
                    "authorization_decision": authorization_decision,
                },
            )

            if result.get("success"):
                response_is_final = bool(result.get("response_is_final"))
                return {
                    "success": True,
                    "response": (
                        result["result"]
                        if response_is_final
                        else f"[{agent_name}]\n{result['result']}\n(Scopes: {', '.join(scopes)})"
                    ),
                    "response_is_final": response_is_final,
                }
            else:
                if agent_type == AGENT_INVENTORY and "inventory:write" in scopes:
                    return {
                        "success": False,
                        "error": result.get("error") or result.get("result") or "Inventory write failed",
                    }
                # Agent LLM call failed, use demo data as fallback
                logger.warning(f"Agent {agent_type} LLM call failed: {result.get('error')}")
                data = self._get_demo_data(agent_type, message, scopes)
                return {
                    "success": True,
                    "response": f"[{agent_name}]\n{data}\n(Scopes: {', '.join(scopes)})",
                }

        except Exception as e:
            logger.error(f"Error invoking agent {agent_type}: {e}")
            if agent_type == AGENT_INVENTORY and "inventory:write" in scopes:
                return {"success": False, "error": str(e)}
            # Fallback to demo data
            data = self._get_demo_data(agent_type, message, scopes)
            return {
                "success": True,
                "response": f"[{agent_name}]\n{data}\n(Scopes: {', '.join(scopes)})",
            }

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
                return (
                    "Inventory writes are never simulated. A validated resource token "
                    "and an allow decision are required before the data store can change."
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

        Returns user-facing permission guidance without exposing internal agent names.
        """
        if state.get("delegation_denial_reason"):
            state["final_response"] = state["delegation_denial_reason"]
            state["agent_flow"].append({
                "step": "generate_response",
                "action": "Returned vacation delegation-denial message",
                "status": "denied",
            })
            return state

        # Short-circuit when the approval gate queued an OIG request.
        if state.get("pending_approval") is not None:
            pa = state["pending_approval"]
            intent = pa.get("intent") or {}
            approval_role = pa.get("approver_role") or "VP"
            state["final_response"] = (
                "I didn’t change the inventory. "
                f"This request requires {approval_role} approval, so I created Okta request "
                f"{pa['request_id']} for {pa['approver_group']}. Once an eligible "
                f"{approval_role} approves it, the change will execute automatically."
            )
            state["agent_flow"].append({
                "step": "generate_response",
                "action": "Returned pending-approval message",
                "status": "pending",
            })
            return state

        # Short-circuit when approval-gate errored.
        last_flow = state.get("agent_flow", [])
        if last_flow and last_flow[-1].get("step") == "approval_gate" and last_flow[-1].get("status") == "error":
            state["final_response"] = (
                "I wasn't able to submit the approval request because the approval service "
                "is temporarily unavailable. Please try again shortly."
            )
            return state

        agent_results = state["agent_results"]

        # Collect successful responses, authorization denials, and system errors.
        # These cases must stay distinguishable in the final
        # response - collapsing "system error" into the generic fallback is what
        # made real backend/Okta failures look like the AI misunderstanding the
        # prompt.
        responses = []
        final_responses = []
        denied_requests = []
        system_error_agents = []

        for agent_type, result in agent_results.items():
            if result["success"] and "response" in result:
                responses.append(result["response"])
                if result.get("response_is_final"):
                    final_responses.append(result["response"])
            elif result.get("access_denied"):
                denied_requests.append({
                    "agent_type": agent_type,
                    "requested_scopes": result.get("requested_scopes", []),
                })
            elif not result["success"]:
                system_error_agents.append((result["agent_info"]["name"], result.get("error", "Unknown error")))

        inventory_write_denied = any(
            denial["agent_type"] == AGENT_INVENTORY
            and "inventory:write" in denial["requested_scopes"]
            for denial in denied_requests
        )
        inventory_fga = next(
            (check for check in state.get("fga_checks", []) if check.get("agent") == AGENT_INVENTORY),
            {},
        )
        inventory_policy = inventory_fga.get("policy") or {}
        hard_denial = inventory_policy.get("hard_denial_reason")
        simple_denial_message = (
            agent_results.get(AGENT_INVENTORY, {}).get("authorization_reason")
        )
        if inventory_write_denied and simple_denial_message:
            permission_message = simple_denial_message
        elif inventory_write_denied and hard_denial:
            permission_message = f"I didn’t change the inventory. {hard_denial}"
        elif inventory_write_denied:
            permission_message = (
                "I didn’t change the inventory because the live FGA check denied direct execution. "
                "Review the role level and requested quantity on the FGA page."
            )
        else:
            permission_message = "I can’t complete that request with your current permissions."

        # Generate combined response
        if responses:
            combined_data = "\n\n".join(responses)
            if len(final_responses) == len(responses):
                # Structured resource operations already produced the exact
                # user-facing answer. Preserve it byte-for-byte so an LLM
                # cannot change counts or imply a write that did not occur.
                final_response = combined_data
            else:
                synthesis_prompt = f"""Based on the following agent responses, provide a helpful, natural answer
to the user's question: "{state['user_message']}"

Agent responses:
{combined_data}

{"Note: A requested action was blocked by the user's current permissions." if denied_requests else ""}

Provide a concise, helpful response that combines the available information. Do not mention
internal agents, MCP servers, policy names, or permission errors; permission guidance is added separately."""

                try:
                    # Use raw async Anthropic SDK for response synthesis.
                    response = await self.anthropic_client.messages.create(
                        model=LLM_MODEL_NAME,
                        max_tokens=1024,
                        system="You are a helpful AI assistant for ProGear Sporting Goods.",
                        messages=[{"role": "user", "content": synthesis_prompt}]
                    )
                    final_response = response.content[0].text
                except Exception as e:
                    logger.error(f"Response synthesis failed: {e}")
                    final_response = combined_data

            if denied_requests:
                final_response += f"\n\n{permission_message}"

        elif system_error_agents:
            # Real infrastructure/Okta failure - the router understood the request
            # and picked the right agent(s), the token exchange itself failed.
            # Say so explicitly instead of falling through to the generic
            # "I'm not sure how to help" message, which reads as an LLM
            # comprehension failure when it's actually a backend/Okta problem.
            names = ", ".join(name for name, _ in system_error_agents)
            details = "; ".join(f"{name}: {err}" for name, err in system_error_agents)
            final_response = (
                f"I understood you're asking about {names}, but hit a system error "
                f"reaching that service - this is a backend/Okta connectivity issue, "
                f"not a misunderstanding of your request. Please try again in a moment.\n\n"
                f"Details: {details}"
            )
            if denied_requests:
                final_response += f"\n\n{permission_message}"
        elif denied_requests:
            final_response = permission_message
        else:
            final_response = (
                "I'm not sure how to help with that request. "
                "Try asking about orders, inventory, pricing, or customer information."
            )

        state["final_response"] = final_response

        state["agent_flow"].append({
            "step": "generate_response",
            "action": "Generated combined response",
            "status": "completed"
        })

        return state

    async def process(self, message: str, simulate_fga: bool = False) -> Dict[str, Any]:
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
            "authorization_decisions": [],
            "simulate_fga": simulate_fga,
            "final_response": None,
            "pending_approval": None,
            "parsed_intent": None,
            "delegation_denial_reason": None,
        }

        # Run the workflow
        final_state = await self.workflow.ainvoke(initial_state)

        return {
            "content": final_state["final_response"],
            "agent_flow": final_state["agent_flow"],
            "token_exchanges": final_state["token_exchanges"],
            "fga_checks": final_state["fga_checks"],
            "authorization_decisions": final_state["authorization_decisions"],
            "pending_approval": final_state.get("pending_approval"),
        }
