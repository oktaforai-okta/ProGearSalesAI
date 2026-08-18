"""Secret-free view of the planned and configured O4AA agent mesh."""

from __future__ import annotations

import os
from typing import Any, Mapping


def registry_snapshot(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = environ or os.environ

    def status(variable: str) -> str:
        return "configured" if env.get(variable, "").strip() else "planned"

    return {
        "enabled": env.get("PROGEAR_A2A_ENABLED", "false").lower() == "true",
        "control_plane": "Okta for AI Agents",
        "agents": [
            {
                "key": "coordinator",
                "name": "ProGear Coordinator",
                "platform": "ProGear",
                "role": "Routes typed work and performs one exchange per target",
                "status": status("A2A_COORDINATOR_AGENT_ID"),
                "dual_citizen": True,
                "inbound": ["ProGear OIDC application"],
                "outbound": ["AWS Inventory + Pricing Agent", "Google Customer Agent"],
            },
            {
                "key": "aws_inventory",
                "name": "AWS Inventory + Pricing Agent",
                "platform": "AWS Bedrock AgentCore",
                "role": "Receives inventory and returns an authoritative price receipt",
                "status": status("A2A_AWS_INVENTORY_AGENT_ID"),
                "dual_citizen": True,
                "inbound": ["ProGear Coordinator"],
                "outbound": ["Inventory MCP · inventory:write"],
            },
            {
                "key": "google_customer",
                "name": "Google Customer Agent",
                "platform": "Google Cloud / ADK",
                "role": "Reads consent and sends receipt-bound notifications",
                "status": status("A2A_GOOGLE_CUSTOMER_AGENT_ID"),
                "dual_citizen": True,
                "inbound": ["ProGear Coordinator"],
                "outbound": ["Customer MCP · customer:read, customer:notify"],
            },
        ],
        "resources": [
            {
                "name": "Inventory MCP",
                "scopes": ["inventory:write"],
                "expected_actor": "AWS Inventory + Pricing Agent",
                "enforcement": "JWT + resource-side Agent Authorization + idempotency",
            },
            {
                "name": "Customer MCP",
                "scopes": ["customer:read", "customer:notify"],
                "expected_actor": "Google Customer Agent",
                "enforcement": "JWT + consent + authoritative receipt binding",
            },
        ],
    }

