"""
Pricing Agent - Handles pricing, discounts, and margins.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
Uses demo_store for pricing data.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from data.demo_store import demo_store


class PricingAgent(BaseAgent):
    """
    Pricing Agent handles all pricing-related operations.

    Capabilities:
    - Get product pricing (pricing:read)
    - View profit margins (pricing:margin)
    - Apply/view discounts (pricing:discount)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: pricing:read, pricing:margin, pricing:discount
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Pricing Agent",
            agent_type="pricing",
            scopes=["pricing:read", "pricing:margin", "pricing:discount"],
            user_token=user_token,
            color="#f59e0b",  # Orange
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Pricing Agent, an AI assistant specialized in pricing operations.

Your capabilities:
- Look up product pricing
- Apply volume and promotional discounts
- Calculate profit margins
- Enforce pricing rules and approval thresholds

You work for ProGear, a sporting goods company. Be precise with all pricing calculations.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- Your access is controlled by scopes: pricing:read, pricing:margin, pricing:discount
- All your actions are audited through Okta

Always show pricing calculations clearly."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a pricing-related task with real data."""
        context = context or {}

        # Get data from demo_store
        data = self._get_data(task)

        # Augment the task with data
        augmented_task = f"""{task}

Available pricing data:
{data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    def _get_data(self, task: str) -> str:
        """Get pricing data from demo_store."""
        task_lower = task.lower()

        if "basketball" in task_lower or "margin" in task_lower:
            # Get basketball pricing
            basketball_pricing = demo_store.get_pricing_by_category("Basketballs")
            if basketball_pricing:
                lines = ["Basketball Pricing:\n"]
                total_margin = 0
                for item in basketball_pricing[:6]:
                    lines.append(f"- {item['name']}: ${item['price']:.2f} (cost ${item['cost']:.2f}, margin {item['margin']}%)")
                    total_margin += item['margin']

                avg_margin = total_margin / len(basketball_pricing[:6])
                lines.append(f"\nAverage basketball margin: {avg_margin:.1f}%")
                return "\n".join(lines)

        if "bulk" in task_lower or "discount" in task_lower:
            discounts = demo_store.get_discount_structure()
            volume = discounts.get('volume_discounts', {})
            tier = discounts.get('tier_discounts', {})

            return f"""Bulk Discounts:
- {', '.join(f'{qty}+ units: {disc}%' for qty, disc in sorted(volume.items(), key=lambda x: int(x[0])))}

Customer Tier Bonuses:
- {', '.join(f'{t}: {d}%' for t, d in tier.items())}

Example: 1,500 units @ Platinum = {volume.get('500', 20) + tier.get('Platinum', 5)}% total discount"""

        if "hoop" in task_lower:
            hoop_pricing = demo_store.get_pricing_by_category("Hoops & Backboards")
            if hoop_pricing:
                lines = ["Hoops & Backboards Pricing:\n"]
                for item in hoop_pricing:
                    lines.append(f"- {item['name']}: ${item['price']:.2f} (margin {item['margin']}%)")
                return "\n".join(lines)

        # Default: pricing overview
        all_pricing = demo_store.get_all_pricing()
        all_inventory = demo_store.get_all_inventory()

        # Calculate average margin by category
        category_margins = {}
        for sku, pricing in all_pricing.items():
            if sku in all_inventory:
                category = all_inventory[sku].get('category', 'Other')
                if category not in category_margins:
                    category_margins[category] = []
                category_margins[category].append(pricing['margin'])

        lines = ["Pricing Overview:\n"]
        all_margins = []
        for category, margins in category_margins.items():
            avg = sum(margins) / len(margins)
            all_margins.extend(margins)
            lines.append(f"- {category}: avg margin {avg:.1f}%")

        overall_avg = sum(all_margins) / len(all_margins) if all_margins else 0
        lines.append(f"\nOverall Average Margin: {overall_avg:.1f}%")

        discounts = demo_store.get_discount_structure()
        lines.append(f"\nVolume discounts: 5-20% based on quantity")
        lines.append(f"Tier discounts: 0-5% based on customer status")

        return "\n".join(lines)
