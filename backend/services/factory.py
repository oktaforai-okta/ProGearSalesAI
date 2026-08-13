"""Build ApprovalService from env vars.

Called from api/main.py on first request (lazy construction).
"""
from __future__ import annotations

import os
from pathlib import Path

from .approval_service import ApprovalService
from .okta_oig_client import OktaOIGClient
from .service_token import mint_service_token


def _default_ledger_path() -> Path:
    """Place the ledger beside backend/data/live_data.json by default."""
    return Path(__file__).resolve().parent.parent / "data" / "approvals_ledger.json"


def build_approval_service(store) -> ApprovalService:
    base_url = os.environ["OKTA_OIG_BASE_URL"]
    api_token = os.environ["OKTA_OIG_API_TOKEN"]
    request_type_id = os.environ["OKTA_OIG_INVENTORY_REQUEST_TYPE_ID"]
    justification_field_id = os.environ["OKTA_OIG_JUSTIFICATION_FIELD_ID"]
    threshold = int(os.environ.get("APPROVAL_QUANTITY_THRESHOLD", "500"))
    ledger_path = os.environ.get("APPROVALS_LEDGER_PATH") or str(_default_ledger_path())
    oig = OktaOIGClient(base_url=base_url, api_token=api_token)
    return ApprovalService(
        oig=oig,
        demo_store=store,
        mint_service_token=mint_service_token,
        request_type_id=request_type_id,
        justification_field_id=justification_field_id,
        ledger_path=ledger_path,
        quantity_threshold=threshold,
    )
