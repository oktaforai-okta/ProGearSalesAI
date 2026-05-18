"""Async HTTP wrapper around Okta OIG Access Requests API.

Verified endpoint behavior (probed 2026-05-11):

- POST   /governance/api/v1/requests
    Body: {requestTypeId, subject, requesterFieldValues: [{id, value}]}
    `requesterId` is inferred from the API token's owner and is NOT sent.
    Returns: {id, subject, requestStatus, approvals: [...], ...}

- GET    /governance/api/v1/requests/{id}
    Returns the full request including requesterFieldValues, approvals, actions.

- GET    /governance/api/v1/requests
    Only supports `filter=requeststatus eq "<OPEN|PENDING|RESOLVED|...>"` and
    `filter=lastupdated ...`. Server-side filter by requestTypeId is NOT
    supported despite Okta's own `_links.requests.href` suggesting otherwise.
    Callers must filter by request type client-side.

There is no comments endpoint on this API; the earlier design's
[EXECUTED:]/[EXECUTION_FAILED:] comment-based idempotency ledger has been
moved to a backend-side JSON file (see approval_service.py).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OIGAuthError(RuntimeError):
    """Raised when Okta returns 401 — API token expired/invalid."""


class OIGUnavailable(RuntimeError):
    """Raised when Okta returns 5xx or times out."""


class OktaOIGClient:
    def __init__(self, base_url: str, api_token: str, http: httpx.AsyncClient | None = None):
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._http = http or httpx.AsyncClient(timeout=10.0)
        self._owns_http = http is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"SSWS {self._api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._base_url}/governance/api/v1{path}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = self._url(path)
        try:
            resp = await self._http.request(method, url, headers=self._headers(), **kwargs)
        except httpx.RequestError as exc:
            logger.warning("OIG transport error on %s %s: %s", method, url, exc)
            raise OIGUnavailable(f"OIG unreachable: {exc}") from exc

        if resp.status_code == 401:
            raise OIGAuthError(f"OIG auth failed on {method} {url}")
        if resp.status_code >= 500:
            raise OIGUnavailable(f"OIG {resp.status_code} on {method} {url}")
        if resp.status_code >= 400:
            raise ValueError(f"OIG {resp.status_code} on {method} {url}: {resp.text}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    async def create_request(
        self,
        *,
        request_type_id: str,
        subject: str,
        justification_field_id: str,
        justification_value: str,
    ) -> dict[str, Any]:
        """Create an OIG Access Request.

        The justification lives inside requesterFieldValues, keyed by the
        Request Type's custom field ID (see OKTA_OIG_JUSTIFICATION_FIELD_ID).
        The requester identity is inferred from the API token owner.
        """
        payload = {
            "requestTypeId": request_type_id,
            "subject": subject,
            "requesterFieldValues": [
                {"id": justification_field_id, "value": justification_value},
            ],
        }
        return await self._request("POST", "/requests", json=payload)

    async def get_request(self, request_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/requests/{request_id}")

    async def list_requests(
        self, *, request_status: str | None = None
    ) -> list[dict[str, Any]]:
        """List Access Requests.

        `request_status` maps to Okta's top-level requestStatus values:
        OPEN, PENDING, RESOLVED, CANCELED, EXPIRED. When omitted, returns all.
        Callers filter by requestTypeId client-side.
        """
        params: dict[str, str] = {}
        if request_status:
            params["filter"] = f'requeststatus eq "{request_status}"'
        data = await self._request("GET", "/requests", params=params)
        if isinstance(data, list):
            return data
        # Okta returns list responses as a bare array in this envelope; keep
        # both shapes supported defensively.
        return data.get("data") or data.get("items") or data.get("requests") or []
