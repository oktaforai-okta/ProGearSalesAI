"""
Sales Agent - The orchestrator for ProGear sales operations.

Registered as a first-class identity in Okta's AI Agent Directory.
Uses raw Anthropic SDK for LLM calls.
Uses demo_store for customer and pricing data.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from data.demo_store import demo_store


class SalesAgent(BaseAgent):
    """
    Sales Agent - The primary agent for ProGear sales.

    Capabilities:
    - Create and manage sales quotes
    - Process customer orders
    - Track deals and pipeline
    - Provide sales analytics

    Security:
    - Registered in Okta AI Agent Directory
    - Uses ID-JAG (Cross App Access) for token exchange
    - Scopes: sales:read, sales:quote, sales:order
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Sales Agent",
            agent_type="sales",
            scopes=["sales:read", "sales:quote", "sales:order"],
            user_token=user_token,
            color="#3b82f6",  # Blue
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Sales Agent, an AI assistant specialized in sales operations for ProGear Sporting Goods.

Your capabilities:
- Create and manage sales quotes for sporting goods equipment
- Process customer orders
- Track deals in the sales pipeline
- Provide sales analytics and insights

You work for ProGear, a B2B sporting goods company serving retailers and sports teams.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- You authenticate using a JWK private key (JWT Bearer)
- Your access to data is controlled by scopes: sales:read, sales:quote, sales:order
- All your actions are audited through Okta
- You are acting ON BEHALF OF the logged-in user - their permissions apply

When responding, be helpful, professional, and accurate. Focus on sales-related information."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a sales-related task with real data."""
        context = context or {}

        # Get data from demo_store
        data = self._get_data(task)

        # Augment the task with data
        augmented_task = f"""{task}

Available data to reference:
{data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    def _get_data(self, task: str) -> str:
        """Get sales-related data from demo_store."""
        task_lower = task.lower()

        # Get customer summary for sales context
        customer_summary = demo_store.get_customer_summary()

        if "order" in task_lower or "recent" in task_lower:
            # Simulate recent orders using top customers
            platinum_customers = demo_store.get_customers_by_tier("Platinum")
            lines = ["Recent Orders:\n"]
            for i, cust in enumerate(platinum_customers[:4], 1):
                # Simulate order data
                order_value = cust['total_spent'] * 0.05  # ~5% of lifetime as recent order
                status = ["shipped", "processing", "pending", "shipped"][i-1]
                lines.append(f"- ORD-2024-{i:03d}: {cust['name']} - ${order_value:,.2f} ({status})")

            total_pipeline = sum(c['total_spent'] * 0.05 for c in platinum_customers[:4])
            lines.append(f"\nPipeline Value: ${total_pipeline:,.2f} this week")
            return "\n".join(lines)

        if "quote" in task_lower:
            # Get pricing for quote context
            discounts = demo_store.get_discount_structure()
            return f"""Quote Information:
- Volume Discounts: {', '.join(f'{qty}+ units: {disc}%' for qty, disc in sorted(discounts['volume_discounts'].items(), key=lambda x: int(x[0])))}
- Tier Discounts: {', '.join(f'{tier}: {disc}%' for tier, disc in discounts['tier_discounts'].items())}
- Top customer (Platinum): {demo_store.get_customers_by_tier('Platinum')[0]['name']}"""

        # Default: sales summary
        return f"""Sales Summary:
- Total Customers: {customer_summary['total_customers']}
- Total Revenue: ${customer_summary['total_revenue']:,}
- Platinum Accounts: {customer_summary['by_tier'].get('Platinum', {}).get('count', 0)}
- Gold Accounts: {customer_summary['by_tier'].get('Gold', {}).get('count', 0)}
- Top Customer: {demo_store.get_customers_by_tier('Platinum')[0]['name']} (${demo_store.get_customers_by_tier('Platinum')[0]['total_spent']:,} lifetime)"""
