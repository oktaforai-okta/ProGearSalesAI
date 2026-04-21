"""
Customer Agent - Handles accounts, contacts, and customer data.

Registered as a first-class identity in Okta.
Uses raw Anthropic SDK for LLM calls.
Uses demo_store for customer data.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from data.demo_store import demo_store


class CustomerAgent(BaseAgent):
    """
    Customer Agent handles all customer-related operations.

    Capabilities:
    - Look up customer accounts (customer:read)
    - Search/find customers (customer:lookup)
    - View purchase history (customer:history)

    Security:
    - Registered as Okta AI Agent
    - Uses ID-JAG token exchange for MCP access
    - Scopes: customer:read, customer:lookup, customer:history
    """

    def __init__(self, user_token: str):
        super().__init__(
            agent_name="Customer Agent",
            agent_type="customer",
            scopes=["customer:read", "customer:lookup", "customer:history"],
            user_token=user_token,
            color="#8b5cf6",  # Purple
        )

    def get_system_prompt(self) -> str:
        return """You are the ProGear Customer Agent, an AI assistant specialized in customer management.

Your capabilities:
- Look up customer accounts and profiles
- Search for customers by name, email, or account number
- View purchase and order history
- Check customer tier, loyalty status, and preferences

You work for ProGear, a sporting goods company. Protect customer privacy and only share relevant info.

IMPORTANT SECURITY CONTEXT:
You are operating with Okta AI Agent governance:
- Your identity is registered in Okta's AI Agent Directory
- Your access is controlled by scopes: customer:read, customer:lookup, customer:history
- All your actions are audited through Okta

Be helpful while respecting customer data privacy."""

    async def process(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a customer-related task with real data."""
        context = context or {}

        # Get data from demo_store
        data = self._get_data(task)

        # Augment the task with data
        augmented_task = f"""{task}

Available customer data:
{data}

Provide a helpful response using this data."""

        return await super().process(augmented_task, context)

    def _get_data(self, task: str) -> str:
        """Get customer data from demo_store."""
        task_lower = task.lower()

        # Search for specific customer
        if "state" in task_lower or "university" in task_lower:
            customer = demo_store.get_customer_by_name("State University")
            if customer:
                return f"""Customer: {customer['name']}
- Customer ID: {customer['id']}
- Tier: {customer['tier']}
- Contact: {customer['contact']}
- Email: {customer['email']}
- Location: {customer['location']}
- Total Spent: ${customer['total_spent']:,}"""

        if "metro" in task_lower:
            customer = demo_store.get_customer_by_name("Metro")
            if customer:
                return f"""Customer: {customer['name']}
- Tier: {customer['tier']}
- Contact: {customer['contact']}
- Location: {customer['location']}
- Total Spent: ${customer['total_spent']:,}"""

        if "platinum" in task_lower or "tier" in task_lower:
            platinum = demo_store.get_customers_by_tier("Platinum")
            if platinum:
                lines = [f"Platinum Tier Customers ({len(platinum)}):\n"]
                total = 0
                for cust in sorted(platinum, key=lambda x: x['total_spent'], reverse=True):
                    lines.append(f"- {cust['name']} - ${cust['total_spent']:,} lifetime")
                    lines.append(f"  Contact: {cust['contact']} | {cust['location']}")
                    total += cust['total_spent']
                lines.append(f"\nTotal Platinum Revenue: ${total:,}")
                lines.append("Platinum benefits: 5% discount, Net 45-60 terms")
                return "\n".join(lines)

        if "gold" in task_lower:
            gold = demo_store.get_customers_by_tier("Gold")
            if gold:
                lines = [f"Gold Tier Customers ({len(gold)}):\n"]
                for cust in sorted(gold, key=lambda x: x['total_spent'], reverse=True)[:5]:
                    lines.append(f"- {cust['name']} - ${cust['total_spent']:,}")
                return "\n".join(lines)

        # Search by location or name
        for term in ["chicago", "los angeles", "atlanta", "boston", "dallas"]:
            if term in task_lower:
                results = demo_store.search_customers(term)
                if results:
                    lines = [f"Customers in {term.title()}:\n"]
                    for cust in results:
                        lines.append(f"- {cust['name']} ({cust['tier']}) - ${cust['total_spent']:,}")
                    return "\n".join(lines)

        # Default: customer overview
        summary = demo_store.get_customer_summary()
        by_tier = summary.get('by_tier', {})

        lines = ["Customer Overview:\n"]
        for tier in ["Platinum", "Gold", "Silver", "Bronze"]:
            if tier in by_tier:
                data = by_tier[tier]
                lines.append(f"- {tier}: {data['count']} accounts (${data['total_spent']:,} combined)")

        top_customer = demo_store.get_customers_by_tier("Platinum")
        if top_customer:
            top = max(top_customer, key=lambda x: x['total_spent'])
            lines.append(f"\nTop Customer: {top['name']} (${top['total_spent']:,})")

        return "\n".join(lines)
