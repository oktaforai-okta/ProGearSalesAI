"""
Inventory Agent - Handles stock levels and products.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
Calls the protected ProGear Inventory MCP for actual data operations.

IMPORTANT: This agent has optional FGA (Fine-Grained Authorization) integration.
- Role level is supplied to FGA as a contextual tuple
- Sales is read-only and never creates an approval request
- With FGA on, Managers execute 1-600 and writes above 600 route to AI Agent Owner approval
- With FGA off, a validated Manager or VP inventory:write scope permits any positive quantity
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from auth.agent_config import AGENT_INVENTORY, get_agent_config
from mcp.client import MCPToolError, get_mcp_client
from services.intent import parse_inventory_intent


class InventoryAgent(BaseAgent):
    """
    Inventory Agent handles all inventory-related operations.

    Capabilities:
    - Check stock levels (inventory:read)
    - List products (inventory:read)
    - Add/update inventory (inventory:write) - FGA protected
    - View inventory alerts (inventory:read)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: inventory:read, inventory:write
    - FGA action check using role and quantity
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Inventory Agent",
            agent_type="inventory",
            scopes=["inventory:read", "inventory:write"],
            user_token=user_token,
            color="#10b981",  # Green
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Inventory Agent, an AI assistant specialized in inventory management.

Your capabilities:
- Check real-time stock levels for any product
- List available products by category
- Add or update inventory quantities (if authorized)
- Track warehouse and fulfillment status
- Manage low-stock alerts

You work for ProGear, a sporting goods company. Provide accurate inventory information.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- Your access is controlled by scopes: inventory:read, inventory:write
- WRITE operations can be additionally protected by FGA (Fine-Grained Authorization)
- FGA maps Okta clearance_level to Sales (0), Manager (1), or VP (2)
- Sales is always read-only
- With FGA enabled, Managers may write 1-600 units and 601+ requires AI Agent Owner approval
- With FGA off, a validated Manager or VP inventory:write scope permits any positive quantity
- VPs may write any quantity in either mode
- All your actions are audited through Okta

When processing inventory updates, confirm the action clearly."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process an inventory task through the native protected MCP server."""
        context = context or {}
        scopes = context.get("scopes", self.scopes)
        task_lower = task.lower()
        is_write_request = "inventory:write" in scopes and any(
            keyword in task_lower
            for keyword in ("add", "update", "increase", "set", "put", "remove", "decrease")
        )

        if is_write_request:
            decision = context.get("authorization_decision") or {}
            if not context.get("resource_token_validated"):
                return {
                    "agent": self.agent_type,
                    "agent_name": self.agent_name,
                    "color": self.color,
                    "result": "Inventory write blocked: the resource token was not validated.",
                    "success": False,
                    "error": "The inventory resource requires a validated access token.",
                    "scopes": scopes,
                }
            if decision.get("decision") != "allow":
                return {
                    "agent": self.agent_type,
                    "agent_name": self.agent_name,
                    "color": self.color,
                    "result": "Inventory write blocked: the final business policy did not allow execution.",
                    "success": False,
                    "error": "The final authorization decision did not allow this write.",
                    "scopes": scopes,
                }

        access_token = str(context.get("mcp_access_token") or "")
        if not context.get("resource_token_validated") or not access_token:
            return {
                "agent": self.agent_type,
                "agent_name": self.agent_name,
                "color": self.color,
                "result": "The Inventory MCP request was blocked because no validated resource token was available.",
                "success": False,
                "error": "The Inventory MCP requires a validated access token.",
                "scopes": scopes,
            }

        try:
            data = await self._get_data(task, scopes, access_token)
        except MCPToolError as exc:
            return {
                "agent": self.agent_type,
                "agent_name": self.agent_name,
                "color": self.color,
                "result": f"Inventory MCP operation failed: {exc}",
                "success": False,
                "error": str(exc),
                "scopes": scopes,
            }

        # Writes are deterministic resource operations. Return the exact store
        # result instead of asking an LLM to paraphrase success after mutation.
        if is_write_request:
            return {
                "agent": self.agent_type,
                "agent_name": self.agent_name,
                "color": self.color,
                "result": data,
                "success": not data.startswith("INVENTORY UPDATE FAILED") and data != "Product not found for update",
                "error": None if data.startswith("INVENTORY UPDATE SUCCESSFUL") else data,
                "scopes": scopes,
                "response_is_final": True,
            }

        # Inventory is structured business data. Return the exact store answer
        # instead of passing it through one LLM here and another in the
        # orchestrator; those extra hops previously produced conflicting
        # product counts and totals for identical questions.
        return {
            "agent": self.agent_type,
            "agent_name": self.agent_name,
            "color": self.color,
            "result": data,
            "success": True,
            "error": None,
            "scopes": scopes,
            "response_is_final": True,
        }

    async def _get_data(self, task: str, scopes: list, access_token: str) -> str:
        """Call a native Inventory MCP tool and render its structured result."""
        task_lower = task.lower()
        scopes = scopes or []
        config = get_agent_config(AGENT_INVENTORY)
        if config is None:
            raise MCPToolError("The Inventory MCP resource is not configured.")
        client = get_mcp_client()

        async def call(tool_name: str, arguments: dict | None = None):
            return await client.call_tool(
                resource_url=config.mcp_url,
                access_token=access_token,
                tool_name=tool_name,
                arguments=arguments or {},
            )

        # Check if this is a WRITE operation
        has_write_scope = "inventory:write" in scopes
        is_write_request = any(kw in task_lower for kw in [
            "add", "update", "increase", "set", "put", "remove", "decrease"
        ])

        if has_write_scope and is_write_request:
            # Parse quantity + product using the shared helper so orchestrator
            # and agent see the same intent.
            parsed = parse_inventory_intent(task)
            quantity = parsed["quantity_delta"] if parsed else 30
            product_name = parsed["product_name"] if parsed else "basketball"

            result = await call(
                "update_inventory_quantity",
                {"sku": product_name, "quantity": quantity, "operation": "increase"},
            )
            if isinstance(result, dict) and "error" not in result:
                return f"""INVENTORY UPDATE SUCCESSFUL:
- Action: Added {quantity} units to inventory
- Product: {result['name']} (SKU: {result['sku']})
- Previous count: {result['previous_quantity']:,} units
- New count: {result['new_quantity']:,} units
- Status: {result['status'].upper()}
- Change: {'+' if result['change'] > 0 else ''}{result['change']} units"""
            raise MCPToolError(str(result))

        # Read operations - search or list
        if "low stock" in task_lower or "alert" in task_lower:
            response = await call("get_low_stock_alerts")
            low_stock = response.get("items", []) if isinstance(response, dict) else []
            if not low_stock:
                return "No low stock alerts - all inventory levels are good!"

            lines = [f"LOW STOCK ALERT - {len(low_stock)} items need attention:\n"]
            for item in low_stock:
                lines.append(f"- {item['name']}: {item['quantity']} units (reorder at {item['reorder_point']})")
            return "\n".join(lines)

        if "summary" in task_lower or "overview" in task_lower:
            summary = await call("get_inventory_summary")
            return f"""Inventory Summary:
- Total Products: {summary['total_products']}
- Total Items in Stock: {summary['total_items']:,}
- Total Inventory Value: ${summary['total_value']:,.2f}
- Low Stock Alerts: {summary['low_stock_count']}"""

        # Search for specific product or category. Check the more specific
        # category words FIRST: this store's whole vertical is basketball
        # equipment, so "basketball" appears in almost every query (e.g.
        # "basketball hoops", "basketball shoes") — matching it first, as a
        # prior version of this code did, meant those more specific words
        # were never even checked, and every category-specific question
        # silently fell back to just the "Basketballs" category.
        # "goal" and "sneaker" are real synonyms customers use but never
        # appear literally in an item name, so they're mapped to the term
        # that actually is -- otherwise they'd silently match zero results
        # and fall through to a generic summary instead of the real answer.
        synonym_map = {"goal": "hoop", "sneaker": "shoe"}
        search_term = None
        for word in [
            "goal", "hoop", "backboard", "rim",
            "scoreboard", "clock", "whistle", "arrow", "horn", "tape",
            "bag", "backpack", "duffel", "cart", "rack",
            "net", "accessor", "pump", "needle", "clip",
            "uniform", "jersey", "apparel", "sock", "compression", "headband", "wristband",
            "sneaker", "shoe", "footwear",
            "training", "vest", "ladder", "cone", "plyo", "rope", "goggles", "resistance", "shooting machine",
        ]:
            if word in task_lower:
                search_term = synonym_map.get(word, word)
                break
        if not search_term and "basketball" in task_lower:
            search_term = "basketball"

        if search_term:
            # "Basketballs" is a real product category. A broad substring
            # search also matches basketball shoes, hoops, and accessories,
            # which made a plain stock question report an inflated total.
            if search_term == "basketball":
                response = await call("list_products", {"category": "Basketballs"})
                results = response.get("products", []) if isinstance(response, dict) else []
            else:
                response = await call("search_inventory", {"query": search_term})
                results = response.get("results", []) if isinstance(response, dict) else []
            if results:
                total_qty = sum(item['quantity'] for item in results)
                noun = "basketballs" if search_term == "basketball" else f"items matching “{search_term}”"
                lines = [
                    f"ProGear currently has **{total_qty:,} {noun} in stock across {len(results)} products**.",
                    "",
                    "| Product | SKU | Units in stock |",
                    "|---|---|---:|",
                ]
                for item in results:
                    lines.append(f"| {item['name']} | {item['sku']} | {item['quantity']:,} |")
                return "\n".join(lines)

        # Default: show summary
        summary = await call("get_inventory_summary")
        lines = ["Inventory Overview:\n"]
        for category, data in summary['by_category'].items():
            lines.append(f"- {category}: {data['total_quantity']:,} units ({data['count']} SKUs)")
        lines.append(f"\nLow stock alerts: {summary['low_stock_count']}")
        return "\n".join(lines)
