"""
ProGear Basketball - Agent Tools

LangChain tools for inventory, pricing, and customer operations.
These tools interact with the demo data store.
"""

from .inventory_tools import (
    get_inventory,
    search_inventory,
    update_inventory,
    update_inventory_by_percentage,
    get_low_stock_alerts,
    get_inventory_summary,
    INVENTORY_TOOLS
)

from .pricing_tools import (
    get_price,
    get_pricing_by_category,
    update_price,
    calculate_discount,
    get_pricing_summary,
    PRICING_TOOLS
)

from .customer_tools import (
    get_customer,
    search_customers,
    get_customers_by_tier,
    get_customer_summary,
    CUSTOMER_TOOLS
)

ALL_TOOLS = INVENTORY_TOOLS + PRICING_TOOLS + CUSTOMER_TOOLS
