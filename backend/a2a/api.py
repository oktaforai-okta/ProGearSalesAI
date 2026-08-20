"""Authenticated, token-free HTTP surface for the ProGear A2A story."""

from __future__ import annotations

from dataclasses import asdict
import os
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .models import A2AAccessDenied
from .registry import registry_snapshot
from .user_token import A2AUserTokenVerifier
from .workflow import ProGearA2AWorkflow


router = APIRouter(prefix="/api/a2a", tags=["cross-platform-a2a"])


class A2AExecuteRequest(BaseModel):
    """One deterministic cross-platform business request."""

    message: str = Field(min_length=1, max_length=4_000)


def _bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    scheme, separator, token = authorization.strip().partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Expected a bearer access token")
    return token.strip()


def _enabled() -> bool:
    return os.getenv("PROGEAR_A2A_ENABLED", "false").strip().lower() == "true"


def _serialize_result(result: Any) -> dict[str, Any]:
    """Expose business receipts and trace evidence, never credential material."""

    return {
        "ok": result.ok,
        "content": result.content,
        "events": result.trace(),
        "inventory_receipt": (
            asdict(result.inventory_receipt) if result.inventory_receipt is not None else None
        ),
        "notification_receipt": (
            asdict(result.notification_receipt) if result.notification_receipt is not None else None
        ),
        "registry": registry_snapshot(),
    }


async def execute_request(
    request: A2AExecuteRequest,
    authorization: str | None,
    *,
    verifier_factory: Callable[[], A2AUserTokenVerifier] = A2AUserTokenVerifier,
    workflow_factory: Callable[[], ProGearA2AWorkflow] = ProGearA2AWorkflow,
) -> dict[str, Any]:
    """Core handler kept injectable so auth and no-side-effect behavior are testable."""

    if not _enabled():
        raise HTTPException(status_code=503, detail="Cross-platform A2A is not enabled")

    token = _bearer(authorization)
    try:
        verifier = verifier_factory()
        verifier.verify(token)
    except A2AAccessDenied as exc:
        # Configuration failures are a service-readiness concern; a configured
        # verifier rejecting a caller is an authentication failure.
        if not os.getenv("A2A_USER_ISSUER") or not os.getenv("A2A_COORDINATOR_RESOURCE"):
            raise HTTPException(status_code=503, detail="A2A token verification is not configured") from exc
        raise HTTPException(status_code=401, detail="A2A user access token was rejected") from exc

    workflow = workflow_factory()
    if not workflow.matches(request.message):
        raise HTTPException(
            status_code=422,
            detail="Request does not match the ProGear receive, reprice, and notify workflow",
        )
    result = await workflow.execute(request.message, user_access_token=token)
    return _serialize_result(result)


@router.get("/registry")
async def a2a_registry() -> dict[str, Any]:
    """Return mesh readiness and relationships without IDs, URLs, or secrets."""

    return registry_snapshot()


@router.post("/execute")
async def a2a_execute(
    request: A2AExecuteRequest,
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict[str, Any]:
    """Verify the Custom-AS token, run the workflow, and return token-free evidence."""

    return await execute_request(request, authorization)
