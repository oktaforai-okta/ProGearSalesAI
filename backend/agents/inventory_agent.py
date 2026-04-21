"""
Inventory Agent - Handles stock levels and products.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
Uses demo_store for actual data operations.

IMPORTANT: This agent has FGA (Fine-Grained Authorization) integration.
- Write operations require FGA check with contextual tuples
- Users on vacation are denied write access via FGA
- FGA model: can_increase_inventory = manager but not on_vacation
"""

import re
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from data.demo_store import demo_store


class InventoryAgent(BaseAgent):
    """
    Inventory Agent handles all inventory-related operations.

    Capabilities:
    - Check stock levels (inventory:read)
    - List products (inventory:read)
    - Add/update inventory (inventory:write) - FGA protected
    - Manage inventory alerts (inventory:alert)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: inventory:read, inventory:write, inventory:alert
    - FGA check for write operations (vacation check via contextual tuples)
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Inventory Agent",
            agent_type="inventory",
            scopes=["inventory:read", "inventory:write", "inventory:alert"],
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
- Your access is controlled by scopes: inventory:read, inventory:write, inventory:alert
- WRITE operations are additionally protected by Auth0 FGA (Fine-Grained Authorization)
- FGA checks if the user is on vacation - managers on vacation cannot modify inventory
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
            # Extract quantity and product from task
            qty_match = re.search(r'(\d+)\s*(basket|ball|unit|item)', task_lower)
            quantity = int(qty_match.group(1)) if qty_match else 30

            # Find product - default to Pro Game Basketball
            product = demo_store.get_inventory_by_name("basketball")
            if not product:
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

        # Search for specific product or category
        search_term = "basketball" if "basketball" in task_lower else None
        if not search_term:
            # Try to extract search term
            for word in ["hoop", "net", "uniform", "training", "shoe", "footwear"]:
                if word in task_lower:
                    search_term = word
                    break

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
