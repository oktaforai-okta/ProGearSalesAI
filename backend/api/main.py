"""
ProGear Sales AI - FastAPI Backend
Main entry point for the API server.

Features:
- Multi-agent orchestration with 4 specialized agents
- ID-JAG token exchange for each agent
- Access control based on user's Okta groups
- Agent flow visualization data for UI
"""

import os
import logging
from pathlib import Path

# Load environment variables BEFORE importing modules that read env at import time
# (fga_client reads FGA_STORE_ID etc. at module level). The repo-root .env is one
# directory above backend/, so find it explicitly so cwd doesn't matter.
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

import httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from auth.okta_auth import get_okta_auth
from auth.agent_config import get_all_agent_configs, DEMO_AGENTS
from auth.fga_client import close_fga_client
from auth.demo_admin import toggle_demo_attribute, reset_demo_attributes, get_demo_status, ALLOWED_ATTRIBUTES
from orchestrator.orchestrator import Orchestrator
from dataclasses import asdict
from data.demo_store import demo_store
from services.factory import build_approval_service
from services.okta_role_resolver import OktaRoleResolver

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ProGear AI Sales API",
    description="Multi-agent AI sales assistant with Okta governance",
    version="0.2.0",
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Approval Service (lazy; constructed on first use) ---

_approval_service_singleton = None


def _get_approval_service():
    """Return the process-wide ApprovalService, constructing on first call."""
    global _approval_service_singleton
    if _approval_service_singleton is None:
        _approval_service_singleton = build_approval_service(demo_store)
    return _approval_service_singleton


def _approval_status_to_json(status) -> Dict[str, Any]:
    """Serialize an ApprovalStatus dataclass (including nested dataclasses) to a JSON-safe dict."""
    data = asdict(status)
    # asdict() already recurses into nested dataclasses (Intent, ExecutionResult),
    # so this is primarily just converting to a plain dict. Explicit round-trip
    # keeps the shape stable even if ApprovalStatus grows new nested fields.
    return data


# --- Background Approval Poller ---

import asyncio as _approval_asyncio

_approval_poll_task: Optional[_approval_asyncio.Task] = None


async def _approval_poller_loop():
    """Periodically drain newly-approved OIG requests.

    Only resolves; idempotency is enforced inside ApprovalService.execute_if_approved.
    Never raises — swallows every error so the loop body can't take down the task.

    Backs off on consecutive errors (429/500 from Okta's governance API were
    observed hitting this loop every ~60s in production logs) instead of
    retrying at a fixed interval regardless of Okta's health.
    """
    base_interval = int(os.getenv("APPROVAL_POLL_INTERVAL_SECONDS", "120"))
    max_interval = base_interval * 8
    interval = base_interval
    req_type_id = os.environ.get("OKTA_OIG_INVENTORY_REQUEST_TYPE_ID")
    if not req_type_id:
        logger.warning("OKTA_OIG_INVENTORY_REQUEST_TYPE_ID not set; approval poller disabled")
        return
    bootstrapped = False
    while True:
        try:
            svc = _get_approval_service()
            # Recover this service's open requests once after startup. New
            # requests register themselves in the persistent ledger. From then
            # on, poll only those IDs; repeatedly listing every historical OPEN
            # and RESOLVED tenant request caused avoidable OIG rate limiting.
            if not bootstrapped:
                raw_open = await svc._oig.list_requests(request_status="OPEN")
                for raw in raw_open:
                    if raw.get("requestTypeId") == req_type_id and raw.get("id"):
                        svc.track_request(raw["id"])
                bootstrapped = True

            for rid in svc.pending_request_ids():
                try:
                    await svc.execute_if_approved(rid)
                except Exception as exc:
                    logger.warning(f"Approval poller: execute failed for {rid}: {exc}")
            interval = base_interval
        except Exception as exc:
            interval = min(interval * 2, max_interval)
            logger.warning(f"Approval poller: loop error, backing off to {interval}s: {exc}")
        await _approval_asyncio.sleep(interval)


@app.on_event("startup")
async def _start_approval_poller():
    global _approval_poll_task
    if os.getenv("OKTA_OIG_INVENTORY_REQUEST_TYPE_ID"):
        try:
            await _get_approval_service().preflight_execution()
            logger.info("Approval execution-token preflight passed")
        except Exception as exc:
            # The app remains available for reads and direct writes, but every
            # approval request also repeats this preflight and therefore fails
            # before creating an OIG request until configuration is repaired.
            logger.error("Approval execution-token preflight failed: %s", exc)
    _approval_poll_task = _approval_asyncio.create_task(_approval_poller_loop())
    logger.info("Approval poller started")


# --- Lifecycle Events ---

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    global _approval_poll_task
    if _approval_poll_task is not None:
        _approval_poll_task.cancel()
        try:
            await _approval_poll_task
        except _approval_asyncio.CancelledError:
            pass
        logger.info("Approval poller stopped")
    logger.info("Shutting down - closing FGA client...")
    await close_fga_client()
    logger.info("FGA client closed")


# --- Request/Response Models ---

class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    session_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = []
    # False is the deliberately simple Sarah/Mike experience. True enables
    # hosted FGA checks and OIG approval routing; it never weakens a direct
    # role requirement because simple mode denies instead of routing upward.
    simulate_fga: bool = False
    # Opaque id generated in browser sessionStorage. It selects an isolated,
    # server-side FGA demo context and is ignored when simulation is off.
    demo_session_id: Optional[str] = None


class AgentInfo(BaseModel):
    """Information about an agent."""
    name: str
    type: str
    color: str
    status: str  # "granted", "denied", "pending"
    scopes: List[str] = []


class TokenExchange(BaseModel):
    """Token exchange result."""
    agent: str
    agent_name: str
    color: str
    success: bool
    access_denied: bool = False
    status: str  # "granted", "denied", "error"
    scopes: List[str] = []
    error: Optional[str] = None
    demo_mode: bool = False
    token_claims: Optional[Dict[str, Any]] = None  # Decoded access token claims
    access_token: Optional[str] = None  # Raw access token JWT
    id_jag_token: Optional[str] = None  # Raw ID-JAG token (intermediate)
    id_jag_claims: Optional[Dict[str, Any]] = None  # Decoded ID-JAG claims
    resource_token_validated: bool = False
    resource_token_kid: Optional[str] = None
    resource_validation_error: Optional[str] = None
    business_decision: Optional[str] = None
    business_reason: Optional[str] = None


class AgentFlowStep(BaseModel):
    """A step in the agent flow."""
    step: str
    action: str
    status: str
    color: Optional[str] = None
    agents: Optional[List[str]] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    content: str
    session_id: str
    agent_flow: List[AgentFlowStep]
    token_exchanges: List[TokenExchange]
    fga_checks: List[Dict[str, Any]]
    authorization_decisions: List[Dict[str, Any]]
    user_info: Optional[Dict[str, Any]] = None
    # Populated when a Manager's 601+ inventory write awaits VP approval.
    # Null for direct execution and hard denials.
    pending_approval: Optional[Dict[str, Any]] = None


# --- Health Check ---

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "progear-ai-api",
        "version": "0.2.0",
        "agents": list(DEMO_AGENTS.keys())
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "ProGear AI Sales API",
        "version": "0.2.0",
        "docs": "/docs",
        "health": "/health",
        "agents": 4
    }


# --- Chat Endpoint ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    Main chat endpoint.

    This will:
    1. Authenticate the user (via Okta token)
    2. Route to appropriate agent(s) via orchestrator
    3. Perform ID-JAG token exchange for each agent
    4. Return response with agent flow and token exchanges
    """
    logger.info(f"=== Chat Request ===")
    logger.info(f"Message: {request.message[:50]}...")
    logger.info(f"Has auth header: {authorization is not None}")

    okta_auth = get_okta_auth()
    user_info = None

    # Extract user token
    user_token = None
    if authorization and authorization.startswith("Bearer "):
        user_token = authorization[7:]

    # Validate the employee token separately from authorization-context
    # resolution so an Okta profile API failure is never mislabeled as either
    # an authentication failure or an unassigned role.
    if not user_token:
        raise HTTPException(status_code=401, detail="Missing Okta bearer token")
    try:
        user_claims = await okta_auth.validate_token(user_token)
    except Exception as exc:
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(
            status_code=401,
            detail="Your sign-in token could not be verified. Please sign out and sign back in.",
        ) from exc

    # The ID token authenticates the employee. Authorization uses the
    # employee's live Okta profile, identified by subject rather than by a
    # persona name, so any user assigned level 0, 1, or 2 follows the same
    # policy dynamically on their next request.
    role_identifier = user_claims.get("sub") or user_claims.get("email")
    try:
        resolved_user = await OktaRoleResolver(
            base_url=os.environ["OKTA_DOMAIN"],
            api_token=os.environ["OKTA_API_TOKEN"],
        ).resolve_identity(role_identifier or "")
        clearance_level = resolved_user.clearance_level
    except (KeyError, httpx.HTTPError, ValueError) as exc:
        logger.error(
            "Live Okta authorization-context lookup failed (%s): %r",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "I couldn't verify your current Okta role and delegation context, so no "
                "agent action was attempted. Please try again."
            ),
        ) from exc

    user_info = {
        "sub": user_claims.get("sub"),
        "email": user_claims.get("email"),
        "name": user_claims.get("name"),
        "groups": user_claims.get("groups", []),
        "clearance_level": clearance_level,
        "is_a_manager": resolved_user.is_a_manager,
        "is_on_vacation": resolved_user.is_on_vacation,
        "okta_user_id": resolved_user.user_id,
        "authorization_context_source": "live_okta_profile",
    }

    # Shared Sarah/Mike accounts are used by multiple demo engineers. FGA
    # controls therefore layer a short-lived, server-side context over the
    # live Okta baseline for this authenticated browser session only. They do
    # not mutate Okta and cannot grant a scope that Okta refused to issue.
    if request.simulate_fga:
        if not request.demo_session_id:
            raise HTTPException(status_code=400, detail="FGA simulation session is missing. Refresh the page and try again.")
        try:
            demo_context = await get_demo_status(
                resolved_user.user_id or role_identifier or "",
                request.demo_session_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            logger.error("FGA demo context lookup failed: %s", exc)
            raise HTTPException(status_code=502, detail="FGA demo context could not be loaded") from exc

        user_info.update({
            "clearance_level": demo_context["clearance_level"],
            "is_a_manager": demo_context["is_a_manager"],
            "is_on_vacation": demo_context["is_on_vacation"],
            "authorization_context_source": "isolated_demo_session",
        })

    # Log sanitized ID token metadata only - never the raw JWT or the full
    # decoded claim body (deployed on Render; logs are not a place for token
    # material).
    logger.info("=== ID Token (User) ===")
    logger.info("User: %s", user_info.get("email"))
    logger.info("Subject (sub): %s", user_claims.get("sub"))
    logger.info("Groups: %s", user_claims.get("groups", []))
    logger.info("Resolved live clearance_level: %s", clearance_level)
    logger.info("Resolved manager/vacation context: manager=%s vacation=%s", resolved_user.is_a_manager, resolved_user.is_on_vacation)
    logger.info("Claim keys present: %s", list(user_claims.keys()))

    # Create orchestrator and process request
    try:
        orchestrator = Orchestrator(
            user_token=user_token or "",
            user_info=user_info,
            approval_service=_get_approval_service(),
        )
        result = await orchestrator.process(
            request.message,
            simulate_fga=request.simulate_fga,
        )

        return ChatResponse(
            content=result["content"],
            session_id=request.session_id or "session-1",
            agent_flow=[AgentFlowStep(**step) for step in result["agent_flow"]],
            token_exchanges=[TokenExchange(**ex) for ex in result["token_exchanges"]],
            fga_checks=result.get("fga_checks", []),
            authorization_decisions=result.get("authorization_decisions", []),
            user_info=user_info,
            pending_approval=result.get("pending_approval"),
        )

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")

        # Return error response with empty flows
        return ChatResponse(
            content=f"I encountered an error processing your request: {str(e)}",
            session_id=request.session_id or "session-1",
            agent_flow=[
                AgentFlowStep(step="error", action=str(e), status="error")
            ],
            token_exchanges=[],
            fga_checks=[],
            authorization_decisions=[],
            user_info=user_info
        )


# --- Agent Status Endpoint ---

@app.get("/api/agents/status")
async def agent_status():
    """Get status of all agents and their configuration."""
    agents = []
    configs = get_all_agent_configs()

    for agent_type, config in configs.items():
        if config:
            agents.append({
                "name": config.name,
                "type": config.agent_type,
                "description": config.description,
                "color": config.color,
                "configured": bool(config.agent_id),
                "has_private_key": config.private_key is not None,
                "scopes": config.scopes,
            })
        else:
            # Use demo config
            demo = DEMO_AGENTS.get(agent_type, {})
            agents.append({
                "name": demo.get("name", f"{agent_type.title()} Agent"),
                "type": agent_type,
                "description": "Demo mode",
                "color": demo.get("color", "#888"),
                "configured": False,
                "has_private_key": False,
                "scopes": demo.get("scopes", []),
            })

    return {
        "agents": agents,
        "count": len(agents),
        "orchestrator": "langgraph",
    }


# --- Okta Config Endpoint (for frontend) ---

@app.get("/api/config/okta")
async def okta_config():
    """
    Return Okta configuration for frontend.
    Only returns public information.
    """
    return {
        "domain": os.getenv("OKTA_DOMAIN", ""),
        "clientId": os.getenv("OKTA_CLIENT_ID", ""),
        "issuer": os.getenv("OKTA_ISSUER", ""),
        # Never return secrets!
    }


# --- Agent Config Endpoint (for UI visualization) ---

@app.get("/api/agents/config")
async def agent_config():
    """
    Resource-domain metadata for UI display.

    Okta governs a single AI Agent workload identity for this demo, the
    ProGear Sales Agent. The four entries below are internal resource
    domains - each with its own Custom Authorization Server and scope
    boundary - that the one governed agent performs token exchanges
    against. They are not four separate registered Okta AI Agent
    identities, so this response intentionally avoids labeling each domain
    as its own "Agent".
    """
    domains = [
        {
            "type": "sales",
            "domain": "Sales",
            "description": "Orders, quotes, and sales pipeline",
            "color": "#3b82f6",
            "icon": "ShoppingCart",
        },
        {
            "type": "inventory",
            "domain": "Inventory",
            "description": "Stock levels, products, and warehouse",
            "color": "#10b981",
            "icon": "Package",
        },
        {
            "type": "customer",
            "domain": "Customer",
            "description": "Accounts, contacts, and purchase history",
            "color": "#8b5cf6",
            "icon": "Users",
        },
        {
            "type": "pricing",
            "domain": "Pricing",
            "description": "Pricing, margins, and discounts",
            "color": "#f59e0b",
            "icon": "DollarSign",
        },
    ]
    identity_note = (
        "One Okta AI Agent identity (the ProGear Sales Agent) performs "
        "token exchanges across these four resource domains. Each domain "
        "has its own Custom Authorization Server and scope boundary, not "
        "its own Okta agent identity."
    )

    return {
        "governed_agent": "ProGear Sales Agent",
        "identity_note": identity_note,
        "domains": domains,
        # Keep the old collection name during the API transition. Entries use
        # domain labels and do not imply separate registered agent identities.
        "agents": domains,
    }


# --- Okta System Logs Endpoint (for governance demo) ---

@app.get("/api/okta/logs")
async def okta_system_logs(
    minutes: int = Query(default=10, description="Look back this many minutes"),
    limit: int = Query(default=20, description="Max number of logs to return")
):
    """
    Fetch recent Okta system logs for token exchange events.
    Shows both the AI agent (actor) and the user (on behalf of).

    This demonstrates Okta's governance in action.
    """
    okta_domain = os.getenv("OKTA_DOMAIN", "").strip()
    if okta_domain and not okta_domain.startswith("http"):
        okta_domain = f"https://{okta_domain}"

    okta_api_token = os.getenv("OKTA_API_TOKEN", "").strip()

    if not okta_domain or not okta_api_token:
        return {
            "logs": [],
            "error": "Okta API not configured",
            "demo_mode": True
        }

    # Calculate time range
    since = (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        async with httpx.AsyncClient() as client:
            # Fetch token exchange related events
            response = await client.get(
                f"{okta_domain}/api/v1/logs",
                params={
                    "since": since,
                    "limit": limit,
                    "q": "token"  # Search for token-related events
                },
                headers={
                    "Authorization": f"SSWS {okta_api_token}",
                    "Accept": "application/json"
                },
                timeout=10.0
            )

            if response.status_code != 200:
                logger.error(f"Okta API error: {response.status_code} - {response.text}")
                return {
                    "logs": [],
                    "error": f"Okta API error: {response.status_code}"
                }

            raw_logs = response.json()

            # Filter and format relevant logs
            formatted_logs = []
            for log in raw_logs:
                event_type = log.get("eventType", "")

                # Focus on token grant events (both success and failure)
                if "token.grant" in event_type or "token_exchange" in event_type:
                    outcome = log.get("outcome", {})
                    actor = log.get("actor", {})
                    targets = log.get("target", [])
                    debug_data = log.get("debugContext", {}).get("debugData", {})

                    # Extract user from targets (the "on behalf of" user)
                    user_info = None
                    id_jag_info = None
                    for target in targets:
                        if target.get("type") == "User":
                            user_info = {
                                "id": target.get("id"),
                                "email": target.get("alternateId"),
                                "name": target.get("displayName")
                            }
                        elif target.get("type") == "id_jag":
                            id_jag_info = target.get("detailEntry", {})

                    formatted_log = {
                        "timestamp": log.get("published"),
                        "event_type": event_type,
                        "display_message": log.get("displayMessage"),
                        "outcome": {
                            "result": outcome.get("result"),
                            "reason": outcome.get("reason")
                        },
                        "actor": {
                            "id": actor.get("id"),
                            "type": actor.get("type"),
                            "name": actor.get("displayName"),
                            "alternate_id": actor.get("alternateId")
                        },
                        "user_on_behalf_of": user_info,
                        "id_jag": id_jag_info,
                        "details": {
                            "auth_server": debug_data.get("authorizationServerName"),
                            "requested_scopes": debug_data.get("requestedScopes"),
                            "granted_scopes": debug_data.get("grantedScopes"),
                            "grant_type": debug_data.get("grantType")
                        },
                        "severity": log.get("severity")
                    }
                    formatted_logs.append(formatted_log)

            return {
                "logs": formatted_logs,
                "count": len(formatted_logs),
                "time_range": {
                    "since": since,
                    "minutes": minutes
                }
            }

    except httpx.TimeoutException:
        logger.error("Okta API timeout")
        return {
            "logs": [],
            "error": "Okta API timeout"
        }
    except Exception as e:
        logger.error(f"Error fetching Okta logs: {e}")
        return {
            "logs": [],
            "error": str(e)
        }


# --- Demo FGA Controls (isolated by authenticated browser session) ---

class DemoToggleRequest(BaseModel):
    """Body for POST /api/admin/demo-toggle."""
    attribute: str
    value: Any


async def _resolve_caller_user_id(authorization: Optional[str]) -> str:
    """Validate the caller's bearer token and return its immutable Okta subject.

    Never trust a user id from the request body for demo-admin endpoints.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    okta_auth = get_okta_auth()
    try:
        user_claims = await okta_auth.validate_token(authorization[7:])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    user_id = user_claims.get("sub") or user_claims.get("email")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject/email")
    return user_id


@app.get("/api/admin/demo-status")
async def demo_status(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    demo_session_id: Optional[str] = Header(None, alias="X-Demo-Session-ID"),
):
    """
    Return the signed-in user's browser-session FGA simulation context.
    """
    user_id = await _resolve_caller_user_id(authorization)

    try:
        return await get_demo_status(user_id, demo_session_id or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"demo_status failed: {e}")
        raise HTTPException(status_code=502, detail=f"Okta lookup failed: {e}")


@app.post("/api/admin/demo-toggle")
async def demo_toggle(
    request: DemoToggleRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    demo_session_id: Optional[str] = Header(None, alias="X-Demo-Session-ID"),
):
    """
    Change only this signed-in browser session's simulated role or vacation
    context. The employee's live Okta profile is never modified.
    """
    user_id = await _resolve_caller_user_id(authorization)

    if request.attribute not in ALLOWED_ATTRIBUTES:
        raise HTTPException(status_code=400, detail=f"Attribute must be one of {sorted(ALLOWED_ATTRIBUTES)}")

    try:
        return await toggle_demo_attribute(
            user_id,
            demo_session_id or "",
            request.attribute,
            request.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"demo_toggle failed: {e}")
        raise HTTPException(status_code=502, detail=f"Demo context update failed: {e}")


@app.post("/api/admin/demo-reset")
async def demo_reset(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    demo_session_id: Optional[str] = Header(None, alias="X-Demo-Session-ID"),
):
    """Restore this browser session's starting simulation values."""
    user_id = await _resolve_caller_user_id(authorization)

    try:
        return await reset_demo_attributes(user_id, demo_session_id or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"demo_reset failed: {e}")
        raise HTTPException(status_code=502, detail=f"Demo context reset failed: {e}")


# --- Approval Resolver Endpoint ---

@app.get("/api/approvals/{request_id}")
async def get_approval(request_id: str):
    """Resolve an OIG approval request.

    Foreground fast-path: if the request is APPROVED and not yet executed,
    the call synchronously executes the inventory write. Otherwise returns
    current status without side effects. Short-lived per-request caching
    collapses duplicate polling from multiple browser tabs.
    """
    try:
        svc = _get_approval_service()
        status = await svc.execute_if_approved(request_id)
        return _approval_status_to_json(status)
    except Exception as exc:
        logger.error(f"Approval resolve failed for {request_id}: {exc}")
        # Return a JSON error rather than leak a stack trace to the client.
        raise HTTPException(status_code=502, detail=f"Approval service error: {exc}")


# --- Approval List Endpoint ---

@app.get("/api/approvals")
async def list_approvals(user: Optional[str] = None):
    """List OIG approval requests of the inventory-write type.

    Filters by `intent.user_email == user` when the query param is supplied.
    Returns items in OIG's native order; caller may sort/paginate client-side.
    """
    svc = _get_approval_service()
    req_type_id = os.environ["OKTA_OIG_INVENTORY_REQUEST_TYPE_ID"]
    try:
        raw_list = await svc._oig.list_requests(request_status=None)
    except Exception as exc:
        logger.warning(f"OIG list_requests failed: {exc}")
        return {"items": [], "error": str(exc)}

    items: List[Dict[str, Any]] = []
    for raw in raw_list:
        if raw.get("requestTypeId") != req_type_id:
            continue
        status = svc._status_from_raw(raw.get("id") or "", raw)
        if user and status.intent and status.intent.user_email != user:
            continue
        items.append(_approval_status_to_json(status))
    return {"items": items}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)
