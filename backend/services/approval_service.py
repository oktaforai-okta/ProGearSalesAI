"""Business logic for the OIG approval flow.

Depends on:
- OktaOIGClient   (HTTP)
- A demo_store-like object supporting update_inventory_quantity(sku, qty, op, idempotency_key)
- A service-token minter: callable(scope: str) -> str returning an access token
- A clock:  callable() -> datetime.datetime (UTC)
- A file path for the idempotency ledger (survives restarts; see ledger_path)

All external I/O lives in those dependencies; the service itself is pure orchestration.
"""
from __future__ import annotations

import asyncio
import copy
import datetime as dt
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from .intent import (
    Intent,
    decode_intent,
    encode_justification,
)
from .okta_oig_client import OktaOIGClient, OIGAuthError, OIGUnavailable

logger = logging.getLogger(__name__)

MAX_EXECUTION_ATTEMPTS = 3


@dataclass
class ExecutionResult:
    txn_id: str
    previous_quantity: int
    new_quantity: int


@dataclass
class ApprovalStatus:
    request_id: str
    status: str  # 'pending' | 'approved' | 'executed' | 'denied'
    intent: Intent | None
    submitted_at: str | None = None
    approved_at: str | None = None
    executed_at: str | None = None
    approver: dict | None = None
    execution_result: ExecutionResult | None = None
    denial_reason: str | None = None
    poll_error: bool = False


@dataclass
class _LedgerEntry:
    """Per-request persistent state for the idempotency ledger."""
    executed: bool = False
    executed_at: str | None = None
    txn_id: str | None = None
    previous_quantity: int | None = None
    new_quantity: int | None = None
    failed_attempts: int = 0
    abandoned: bool = False
    last_error: str | None = None
    terminal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "executed": self.executed,
            "executed_at": self.executed_at,
            "txn_id": self.txn_id,
            "previous_quantity": self.previous_quantity,
            "new_quantity": self.new_quantity,
            "failed_attempts": self.failed_attempts,
            "abandoned": self.abandoned,
            "last_error": self.last_error,
            "terminal": self.terminal,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "_LedgerEntry":
        return cls(
            executed=bool(data.get("executed")),
            executed_at=data.get("executed_at"),
            txn_id=data.get("txn_id"),
            previous_quantity=data.get("previous_quantity"),
            new_quantity=data.get("new_quantity"),
            failed_attempts=int(data.get("failed_attempts") or 0),
            abandoned=bool(data.get("abandoned")),
            last_error=data.get("last_error"),
            terminal=bool(data.get("terminal")),
        )


class _Ledger:
    """File-backed idempotency ledger keyed by OIG request_id.

    Lives next to backend/data/live_data.json so it survives FastAPI restarts
    on Render's persistent disk. Not multi-replica-safe; the demo runs on a
    single process.
    """

    def __init__(self, path: str | os.PathLike[str]):
        self._path = Path(path)
        self._data: dict[str, _LedgerEntry] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = self._path.read_text()
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.warning("Approvals ledger read failed: %s", exc)
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Approvals ledger parse failed: %s", exc)
            return
        self._data = {
            rid: _LedgerEntry.from_dict(entry)
            for rid, entry in payload.items()
            if isinstance(entry, dict)
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {rid: entry.to_dict() for rid, entry in self._data.items()}
        # Atomic write
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=self._path.parent,
            prefix=self._path.name,
            suffix=".tmp",
            delete=False,
        ) as fp:
            json.dump(payload, fp, indent=2, default=str)
            tmp_name = fp.name
        os.replace(tmp_name, self._path)

    def get(self, request_id: str) -> _LedgerEntry:
        return self._data.get(request_id) or _LedgerEntry()

    def put(self, request_id: str, entry: _LedgerEntry) -> None:
        self._data[request_id] = entry
        self._save()

    def contains(self, request_id: str) -> bool:
        return request_id in self._data

    def pending_request_ids(self) -> list[str]:
        return [
            request_id
            for request_id, entry in self._data.items()
            if not entry.executed and not entry.abandoned and not entry.terminal
        ]


class ApprovalService:
    def __init__(
        self,
        *,
        oig: OktaOIGClient,
        demo_store: Any,
        mint_service_token: Callable[[str], Awaitable[str]],
        validate_service_token: Callable[[str, str], Awaitable[Any]],
        request_type_id: str,
        justification_field_id: str,
        ledger_path: str | os.PathLike[str],
        quantity_threshold: int = 601,
        status_cache_ttl_seconds: float = 8.0,
        resolve_approver_level: Callable[[dict], Awaitable[int]] | None = None,
        clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
    ):
        self._oig = oig
        self._store = demo_store
        self._mint_token = mint_service_token
        self._validate_token = validate_service_token
        self._request_type_id = request_type_id
        self._justification_field_id = justification_field_id
        self._threshold = quantity_threshold
        self._status_cache_ttl = max(0.0, status_cache_ttl_seconds)
        self._resolve_approver_level = resolve_approver_level
        self._now = clock
        self._locks: dict[str, asyncio.Lock] = {}
        self._status_cache: dict[str, tuple[float, ApprovalStatus]] = {}
        self._ledger = _Ledger(ledger_path)

    # ---------- gating ----------

    def should_gate(self, scope: str, parsed_intent: dict | None) -> bool:
        if scope != "inventory:write":
            return False
        if not parsed_intent:
            return False
        qty = parsed_intent.get("quantity_delta")
        return isinstance(qty, int) and qty >= self._threshold

    async def preflight_execution(self, scope: str = "inventory:write") -> None:
        """Prove that the approved-action token path is currently usable."""
        execution_token = await self._mint_token(scope)
        await self._validate_token(execution_token, scope)

    # ---------- creation ----------

    async def create_request(
        self,
        *,
        user_email: str,
        requester_id: str,
        approver_group_name: str,
        agent: str,
        scope: str,
        parsed_intent: dict,
        original_task: str,
        agent_id: str | None = None,
        fga_check_id: str | None = None,
        required_approver_role: str | None = None,
        required_approver_level: int | None = None,
    ) -> tuple[str, Intent]:
        """Create an OIG Access Request and return (request_id, intent)."""
        if not requester_id:
            raise ValueError("The signed-in employee is missing an Okta user ID")

        # Fail before creating a human approval task if the approved action
        # could not actually execute. This preflight uses the same real Okta
        # client-credentials token and resource validation as the post-approval
        # write path; an OIG card is never used to mask broken credentials.
        await self.preflight_execution(scope)

        qty = int(parsed_intent["quantity_delta"])
        product = str(parsed_intent["product_name"])
        intent = Intent(
            user_email=user_email,
            agent=agent,
            scope=scope,
            product_name=product,
            quantity_delta=qty,
            original_task=original_task,
            submitted_at=self._now().isoformat().replace("+00:00", "Z"),
            agent_id=agent_id,
            fga_check_id=fga_check_id,
            required_approver_role=required_approver_role,
            required_approver_level=required_approver_level,
        )
        subject = f"Inventory write: +{qty} {product}"
        human = (
            f"AI agent requests inventory write on behalf of {user_email}.\n"
            f"Governed agent: {agent_id or agent}.\n"
            f"Action: Add {qty} units of {product} (scope: {scope}).\n"
            f"Original task: \"{original_task}\".\n"
            f"Required approval: {required_approver_role or 'VP'} "
            f"(level {required_approver_level or 2}+).\n"
            f"Approver group: {approver_group_name}."
        )
        justification = encode_justification(human, intent)

        try:
            created = await self._oig.create_request(
                request_type_id=self._request_type_id,
                subject=subject,
                requester_id=requester_id,
                justification_field_id=self._justification_field_id,
                justification_value=justification,
            )
        except (OIGUnavailable, OIGAuthError) as exc:
            logger.error("OIG create_request failed: %s", exc)
            raise

        request_id = created.get("id") or created.get("requestId")
        if not request_id:
            raise RuntimeError(f"OIG response missing request id: {created!r}")
        # Persist newly-created request IDs so the background worker polls only
        # this service's active approvals instead of repeatedly scanning every
        # historical request in the tenant.
        self._ledger.put(request_id, _LedgerEntry())
        return request_id, intent

    # ---------- status ----------

    async def get_status(self, request_id: str) -> ApprovalStatus:
        try:
            raw = await self._oig.get_request(request_id)
        except OIGUnavailable:
            return ApprovalStatus(request_id=request_id, status="pending", intent=None, poll_error=True)
        return self._status_from_raw(request_id, raw)

    def track_request(self, request_id: str) -> None:
        """Register an existing open request for background resolution."""
        if request_id and not self._ledger.contains(request_id):
            self._ledger.put(request_id, _LedgerEntry())

    def pending_request_ids(self) -> list[str]:
        return self._ledger.pending_request_ids()

    def _cached_status(self, request_id: str, *, allow_stale: bool = False) -> ApprovalStatus | None:
        cached = self._status_cache.get(request_id)
        if cached is None:
            return None
        cached_at, status = cached
        if not allow_stale and time.monotonic() - cached_at >= self._status_cache_ttl:
            return None
        return copy.deepcopy(status)

    def _cache_status(self, status: ApprovalStatus) -> None:
        status.poll_error = False
        self._status_cache[status.request_id] = (time.monotonic(), copy.deepcopy(status))

    def _extract_intent(self, raw: dict) -> Intent | None:
        """Pull the [INTENT_JSON] fence out of the Justification field."""
        for fv in raw.get("requesterFieldValues") or []:
            value = fv.get("value")
            if value and isinstance(value, str):
                decoded = decode_intent(value)
                if decoded is not None:
                    return decoded
        return None

    def _derive_approval_decision(self, raw: dict) -> tuple[str, dict | None, str | None, str | None]:
        """Inspect the `approvals` array to determine the decision.

        Returns (decision, approver_summary, approved_at, denial_reason).
        decision ∈ {'pending', 'approved', 'denied'}.
        """
        approvals = raw.get("approvals") or []
        if not approvals:
            return ("pending", None, None, None)

        any_denied = False
        any_pending = False
        approver_summary: dict | None = None
        approved_at: str | None = None
        denial_reason: str | None = None

        for step in approvals:
            # Okta uses `decision` (APPROVED/DENIED) once an approver acts, and a
            # lifecycle `status` (PENDING/COMPLETED/…). Prefer `decision`; fall back
            # to `status` for schemas that surface terminal state there directly.
            decision = (step.get("decision") or "").upper()
            step_status = (step.get("status") or "").upper()

            resolver = step.get("resolvedBy") or step.get("approver") or {}
            resolver_summary = {
                "id": resolver.get("id") or step.get("approverId"),
                "email": resolver.get("email") or resolver.get("login"),
                "display_name": resolver.get("displayName")
                or resolver.get("name")
                or step.get("approverName"),
            }
            if not resolver_summary["email"] and not resolver_summary["display_name"]:
                # Fall back to the approver* fields Okta returns on each step.
                approver_id = step.get("approverId")
                if approver_id or step.get("approverName"):
                    resolver_summary = {
                        "id": approver_id,
                        "email": None,
                        "display_name": step.get("approverName"),
                    }
            decided_at = (
                step.get("decided")
                or step.get("resolvedAt")
                or step.get("updatedAt")
            )

            if decision in ("DENIED", "REJECTED") or step_status in ("DENIED", "REJECTED"):
                any_denied = True
                denial_reason = step.get("reason") or step.get("comment") or denial_reason
                if approver_summary is None and any(resolver_summary.values()):
                    approver_summary = resolver_summary
                if approved_at is None:
                    approved_at = decided_at
            elif decision == "APPROVED" or step_status == "APPROVED":
                if approver_summary is None and any(resolver_summary.values()):
                    approver_summary = resolver_summary
                if approved_at is None:
                    approved_at = decided_at
            elif step_status in ("COMPLETED", "RESOLVED") and not decision:
                # Terminal lifecycle with no explicit decision — treat as approved
                # only if the enclosing requestStatus is RESOLVED; otherwise pending.
                # We can't see requestStatus here, so be conservative and pend.
                any_pending = True
            else:  # PENDING, OPEN, anything else
                any_pending = True

        if any_denied:
            return ("denied", approver_summary, approved_at, denial_reason)
        if any_pending:
            return ("pending", None, None, None)
        return ("approved", approver_summary, approved_at, None)

    def _status_from_raw(self, request_id: str, raw: dict) -> ApprovalStatus:
        intent = self._extract_intent(raw)
        submitted_at = raw.get("created") or raw.get("createdAt")
        oig_request_status = (raw.get("requestStatus") or "").upper()

        # Ledger short-circuit: if we've already executed this request, that's the
        # authoritative state.
        ledger_entry = self._ledger.get(request_id)
        if ledger_entry.executed:
            approver_info = self._derive_approval_decision(raw)[1]
            return ApprovalStatus(
                request_id=request_id,
                status="executed",
                intent=intent,
                submitted_at=submitted_at,
                approved_at=ledger_entry.executed_at,
                executed_at=ledger_entry.executed_at,
                approver=approver_info,
                execution_result=ExecutionResult(
                    txn_id=ledger_entry.txn_id or "",
                    previous_quantity=ledger_entry.previous_quantity if ledger_entry.previous_quantity is not None else -1,
                    new_quantity=ledger_entry.new_quantity if ledger_entry.new_quantity is not None else -1,
                ),
            )

        # Terminal OIG states that aren't normal approval outcomes
        if oig_request_status in ("CANCELED", "EXPIRED"):
            return ApprovalStatus(
                request_id=request_id,
                status="denied",
                intent=intent,
                submitted_at=submitted_at,
                denial_reason=f"OIG request {oig_request_status.lower()}",
            )

        decision, approver, approved_at, denial_reason = self._derive_approval_decision(raw)

        return ApprovalStatus(
            request_id=request_id,
            status=decision,   # pending | approved | denied
            intent=intent,
            submitted_at=submitted_at,
            approved_at=approved_at,
            approver=approver,
            denial_reason=denial_reason,
        )

    # ---------- execution ----------

    def _lock_for(self, request_id: str) -> asyncio.Lock:
        lock = self._locks.get(request_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[request_id] = lock
        return lock

    async def execute_if_approved(self, request_id: str) -> ApprovalStatus:
        lock = self._lock_for(request_id)
        async with lock:
            cached = self._cached_status(request_id)
            if cached is not None:
                return cached

            try:
                raw = await self._oig.get_request(request_id)
            except OIGUnavailable:
                stale = self._cached_status(request_id, allow_stale=True)
                if stale is not None:
                    stale.poll_error = True
                    return stale
                return ApprovalStatus(
                    request_id=request_id,
                    status="pending",
                    intent=None,
                    poll_error=True,
                )
            status = self._status_from_raw(request_id, raw)

            # Already executed (ledger short-circuit handled inside _status_from_raw).
            if status.status == "executed":
                self._cache_status(status)
                return status

            # Nothing to do unless approvers have said yes.
            if status.status != "approved":
                if status.status == "denied":
                    ledger_entry = self._ledger.get(request_id)
                    ledger_entry.terminal = True
                    self._ledger.put(request_id, ledger_entry)
                self._cache_status(status)
                return status

            ledger_entry = self._ledger.get(request_id)
            if ledger_entry.abandoned:
                status.denial_reason = (
                    ledger_entry.last_error
                    or "execution abandoned after repeated failures"
                )
                self._cache_status(status)
                return status

            intent = status.intent
            if intent is None:
                msg = "intent could not be decoded from justification"
                logger.error("%s: %s", request_id, msg)
                ledger_entry.failed_attempts += 1
                ledger_entry.last_error = msg
                ledger_entry.abandoned = True
                self._ledger.put(request_id, ledger_entry)
                status.denial_reason = msg
                self._cache_status(status)
                return status

            required_level = intent.required_approver_level
            if required_level:
                if self._resolve_approver_level is None:
                    status.status = "denied"
                    status.denial_reason = "The approver role could not be verified in Okta."
                    ledger_entry.terminal = True
                    self._ledger.put(request_id, ledger_entry)
                    self._cache_status(status)
                    return status
                try:
                    actual_level = await self._resolve_approver_level(status.approver or {})
                except Exception as exc:  # fail closed on an Okta lookup error
                    logger.warning("Approver role lookup failed for %s: %s", request_id, exc)
                    status.status = "approved"
                    status.poll_error = True
                    status.denial_reason = "The approver role could not be verified in Okta yet."
                    # A temporary Okta lookup failure remains non-executable
                    # and non-terminal so a later poll can retry the live role.
                    return status
                if actual_level < required_level:
                    status.status = "denied"
                    status.denial_reason = (
                        f"Approval requires {intent.required_approver_role or 'role'} "
                        f"level {required_level}; the Okta approver has level {actual_level}."
                    )
                    ledger_entry.terminal = True
                    self._ledger.put(request_id, ledger_entry)
                    self._cache_status(status)
                    return status

            if ledger_entry.failed_attempts >= MAX_EXECUTION_ATTEMPTS:
                ledger_entry.abandoned = True
                self._ledger.put(request_id, ledger_entry)
                status.denial_reason = "execution abandoned after repeated failures"
                self._cache_status(status)
                return status

            attempt_num = ledger_entry.failed_attempts + 1
            try:
                service_token = await self._mint_token(intent.scope)
                await self._validate_token(service_token, intent.scope)
                result = self._store.update_inventory_quantity(
                    sku=intent.product_name,
                    quantity_change=intent.quantity_delta,
                    operation="increase",
                    idempotency_key=request_id,
                )
                if "error" in result:
                    raise RuntimeError(result["error"])
            except Exception as exc:  # noqa: BLE001 — we want to persist any failure to the ledger
                logger.warning(
                    "execute_if_approved attempt %d failed for %s: %s",
                    attempt_num, request_id, exc,
                )
                ledger_entry.failed_attempts = attempt_num
                ledger_entry.last_error = str(exc)
                self._ledger.put(request_id, ledger_entry)
                self._cache_status(status)
                return status  # still status='approved'; will retry on next poll

            txn_id = f"inv_txn_{request_id[-8:]}_{attempt_num}"
            executed_at = self._now().isoformat().replace("+00:00", "Z")
            ledger_entry.executed = True
            ledger_entry.executed_at = executed_at
            ledger_entry.txn_id = txn_id
            ledger_entry.previous_quantity = result.get("previous_quantity")
            ledger_entry.new_quantity = result.get("new_quantity")
            self._ledger.put(request_id, ledger_entry)

            status.status = "executed"
            status.executed_at = executed_at
            status.execution_result = ExecutionResult(
                txn_id=txn_id,
                previous_quantity=result.get("previous_quantity", -1),
                new_quantity=result.get("new_quantity", -1),
            )
            self._cache_status(status)
            return status
