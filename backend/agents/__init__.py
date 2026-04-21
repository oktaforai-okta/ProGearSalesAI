"""
ProGear Sales AI - Agent Classes

Each agent is a first-class identity registered in Okta.
Agents handle specific domains:
- SalesAgent: Orders, quotes, deals
- InventoryAgent: Stock levels, products (with FGA check)
- PricingAgent: Discounts, margins
- CustomerAgent: Accounts, contacts
"""

from .sales_agent import SalesAgent
from .inventory_agent import InventoryAgent
from .pricing_agent import PricingAgent
from .customer_agent import CustomerAgent

__all__ = [
    "SalesAgent",
    "InventoryAgent",
    "PricingAgent",
    "CustomerAgent",
]
