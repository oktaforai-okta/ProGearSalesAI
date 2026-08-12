"""Build ApprovalService from env vars.

Called from api/main.py on first request (lazy construction).
"""
from __future__ import annotations

import os
from pathlib import Path

from .approval_service import ApprovalService
from .okta_oig_client import OktaOIGClient
from .okta_role_resolver import OktaRoleResolver
from .service_token import mint_service_token
from auth.agent_config import AGENT_INVENTORY
from auth.resource_token import get_resource_token_validator
from mcp.client import get_mcp_client


def _default_ledger_path() -> Path:
    """Place the ledger beside backend/data/live_data.json by default."""
    return Path(__file__).resolve().parent.parent / "data" / "approvals_ledger.json"


def build_approval_service() -> ApprovalService:
    base_url = os.environ["OKTA_OIG_BASE_URL"]
    api_token = os.environ["OKTA_OIG_API_TOKEN"]
    request_type_id = os.environ["OKTA_OIG_INVENTORY_REQUEST_TYPE_ID"]
    justification_field_id = os.environ["OKTA_OIG_JUSTIFICATION_FIELD_ID"]
    threshold = int(os.environ.get("APPROVAL_QUANTITY_THRESHOLD", "601"))
    status_cache_ttl = float(os.environ.get("APPROVAL_STATUS_CACHE_TTL_SECONDS", "8"))
    ledger_path = os.environ.get("APPROVALS_LEDGER_PATH") or str(_default_ledger_path())
    oig = OktaOIGClient(base_url=base_url, api_token=api_token)
    role_resolver = OktaRoleResolver(
        base_url=os.environ["OKTA_DOMAIN"],
        api_token=os.environ["OKTA_API_TOKEN"],
    )

    async def validate_service_token(token: str, scope: str):
        executor_client_id = os.environ.get("OKTA_APPROVAL_EXECUTOR_CLIENT_ID", "").strip()
        return await get_resource_token_validator().validate(
            token,
            agent_type=AGENT_INVENTORY,
            required_scopes=[scope],
            expected_client_ids=[executor_client_id],
        )

    async def execute_inventory_write(
        *,
        sku: str,
        quantity: int,
        operation: str,
        idempotency_key: str,
        access_token: str,
    ):
        # OIG's request id remains in the local execution ledger. The current
        # MCP tool schema does not accept an idempotency field, so only standard
        # tool arguments are sent over the wire.
        del idempotency_key
        config = get_agent_config(AGENT_INVENTORY)
        if config is None:
            raise RuntimeError("The Inventory MCP resource is not configured.")
        return await get_mcp_client().call_tool(
            resource_url=config.mcp_url,
            access_token=access_token,
            tool_name="update_inventory_quantity",
            arguments={"sku": sku, "quantity": quantity, "operation": operation},
        )

    return ApprovalService(
        oig=oig,
        mint_service_token=mint_service_token,
        validate_service_token=validate_service_token,
        execute_inventory_write=execute_inventory_write,
        request_type_id=request_type_id,
        justification_field_id=justification_field_id,
        ledger_path=ledger_path,
        quantity_threshold=threshold,
        status_cache_ttl_seconds=status_cache_ttl,
        resolve_approver_level=role_resolver,
        verify_approver_group=role_resolver.is_group_member,
    )
