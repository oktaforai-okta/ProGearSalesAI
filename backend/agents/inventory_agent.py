"""
Inventory Agent - Handles stock levels and products.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
Uses demo_store for actual data operations.

IMPORTANT: This agent has FGA (Fine-Grained Authorization) integration.
- Role level and vacation are supplied to FGA as contextual tuples
- Sales writes route to Manager or VP approval
- Managers execute 1-600; VPs execute any quantity
- Vacation blocks writes but not reads
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from data.demo_store import demo_store
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
    - FGA action check using role, quantity, and contextual vacation status
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
- WRITE operations are additionally protected by Auth0 FGA (Fine-Grained Authorization)
- FGA maps Okta clearance_level to Sales (1), Manager (2), or VP (3)
- Sales writes require approval; 601+ requires VP unless the requester is a VP
- Vacation blocks every write, including approval submission, but does not block reads
- All your actions are audited through Okta

When processing inventory updates, confirm the action clearly."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process an inventory-related task with real data from demo_store."""
        context = context or {}
        scopes = context.get("scopes", self.scopes)

        # Get data from demo_store based on task and scopes
        data = self._get_data(task, scopes)

        # Augment the task with data
        augmented_task = f"""{task}

Available data and action result:
{data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    def _get_data(self, task: str, scopes: list = None) -> str:
        """Get data from demo_store based on the task and scopes."""
        task_lower = task.lower()
        scopes = scopes or []

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

            product = demo_store.get_inventory_by_name(product_name)
            if not product:
                # Preserve the existing fallback: some demo data uses the full product name.
                product = demo_store.get_inventory_by_name("Pro Game Basketball")

            if product:
                # Perform the update
                result = demo_store.update_inventory_quantity(
                    product["sku"],
                    quantity,
                    operation="increase"
                )

                if "error" not in result:
                    return f"""INVENTORY UPDATE SUCCESSFUL:
- Action: Added {quantity} units to inventory
- Product: {result['name']} (SKU: {result['sku']})
- Previous count: {result['previous_quantity']:,} units
- New count: {result['new_quantity']:,} units
- Status: {result['status'].upper()}
- Change: {'+' if result['change'] > 0 else ''}{result['change']} units"""
                else:
                    return f"INVENTORY UPDATE FAILED: {result['error']}"

            return "Product not found for update"

        # Read operations - search or list
        if "low stock" in task_lower or "alert" in task_lower:
            low_stock = demo_store.get_low_stock_items()
            if not low_stock:
                return "No low stock alerts - all inventory levels are good!"

            lines = [f"LOW STOCK ALERT - {len(low_stock)} items need attention:\n"]
            for item in low_stock:
                lines.append(f"- {item['name']}: {item['quantity']} units (reorder at {item['reorder_point']})")
            return "\n".join(lines)

        if "summary" in task_lower or "overview" in task_lower:
            summary = demo_store.get_inventory_summary()
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
            results = demo_store.search_inventory(search_term)
            if results:
                lines = [f"Found {len(results)} products matching '{search_term}':\n"]
                for item in results[:10]:
                    status_icon = "LOW" if item['status'] == 'low' else "GOOD"
                    lines.append(f"- {item['name']}: {item['quantity']:,} units - {status_icon}")

                total_qty = sum(item['quantity'] for item in results)
                lines.append(f"\nTotal {search_term} inventory: {total_qty:,} units")
                return "\n".join(lines)

        # Default: show summary
        summary = demo_store.get_inventory_summary()
        lines = ["Inventory Overview:\n"]
        for category, data in summary['by_category'].items():
            lines.append(f"- {category}: {data['total_quantity']:,} units ({data['count']} SKUs)")
        lines.append(f"\nLow stock alerts: {summary['low_stock_count']}")
        return "\n".join(lines)
