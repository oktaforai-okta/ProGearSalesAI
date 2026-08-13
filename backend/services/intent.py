"""Shape of the intent payload encoded in OIG request justification."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

INTENT_FENCE_START = "[INTENT_JSON]"
INTENT_FENCE_END = "[/INTENT_JSON]"
_INTENT_FENCE_RE = re.compile(
    re.escape(INTENT_FENCE_START) + r"\s*(\{.*?\})\s*" + re.escape(INTENT_FENCE_END),
    re.DOTALL,
)


@dataclass
class Intent:
    user_email: str
    agent: str            # e.g. "inventory"
    scope: str            # e.g. "inventory:write"
    product_name: str
    quantity_delta: int
    original_task: str
    submitted_at: str     # ISO8601
    fga_check_id: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "Intent":
        data = json.loads(raw)
        return cls(**data)


def encode_justification(human_text: str, intent: Intent) -> str:
    """Return a justification string with human text plus a fenced JSON block."""
    return f"{human_text}\n\n{INTENT_FENCE_START}\n{intent.to_json()}\n{INTENT_FENCE_END}"


def decode_intent(justification: str) -> Intent | None:
    """Extract the Intent from a justification that was built with encode_justification."""
    match = _INTENT_FENCE_RE.search(justification or "")
    if not match:
        return None
    return Intent.from_json(match.group(1))


def find_comment(comments: list[dict[str, Any]], prefix: str) -> dict[str, Any] | None:
    """Return the first comment whose text starts with prefix, or None."""
    for c in comments or []:
        if (c.get("text") or "").startswith(prefix):
            return c
    return None


_NUMBER = r"(?P<quantity>\d[\d,]*)"

# Prefer an explicitly requested delta over unrelated numbers that may be
# copied from a prior inventory response. For example, in
# "Youth Adjustable Hoop – 823 units - increase this by 50", 823 is the
# current stock level and 50 is the requested change.
_QTY_PATTERNS = (
    re.compile(
        rf"\b(?:increase|raise|boost|restock|decrease|reduce)\b[^\n]{{0,100}}?\bby\s+{_NUMBER}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:add|increase|raise|boost|restock|remove|decrease|reduce)\s+{_NUMBER}\b",
        re.IGNORECASE,
    ),
)
_QTY_RE = re.compile(r"(?P<quantity>\d[\d,]*)")
_DISPLAYED_PRODUCT_RE = re.compile(
    r"^\s*(?P<product>.+?)\s+[–—-]\s*\d[\d,]*\s+units?\b",
    re.IGNORECASE,
)
# Order matters: longer/more-specific matches come first so "basketball" wins
# over any bare "ball" substring. Bare "ball" is intentionally absent — this is
# a basketball-equipment demo, so "balls"/"ball" should canonicalize to the
# default "basketball" below, keeping the inventory-agent and approval-gate
# paths resolving the same SKU.
_PRODUCT_KEYWORDS = (
    "basketball", "treadmill", "helmet", "glove", "shoe", "jersey", "hoop",
    "racket", "bat",
)


@lru_cache(maxsize=1)
def _catalog_product_names() -> tuple[str, ...]:
    """Return known demo product names, longest first, without live-data state."""
    catalog_path = Path(__file__).resolve().parent.parent / "data" / "initial_data.json"
    try:
        payload = json.loads(catalog_path.read_text())
    except (OSError, json.JSONDecodeError):
        return ()
    names = {
        str(item.get("name") or "").strip()
        for item in (payload.get("inventory") or {}).values()
        if item.get("name")
    }
    return tuple(sorted(names, key=len, reverse=True))


def _parse_quantity(task: str) -> int | None:
    for pattern in _QTY_PATTERNS:
        match = pattern.search(task)
        if match:
            return int(match.group("quantity").replace(",", ""))
    match = _QTY_RE.search(task)
    if not match:
        return None
    return int(match.group("quantity").replace(",", ""))


def _parse_product(task: str) -> str:
    task_lower = task.lower()

    # A copied inventory row often contains the exact catalog name. Resolve it
    # before generic words such as "basketball" or "hoop".
    for name in _catalog_product_names():
        if name.lower() in task_lower:
            return name

    displayed = _DISPLAYED_PRODUCT_RE.search(task)
    if displayed:
        product = displayed.group("product").strip(" -–—:\t")
        if product:
            return product

    return next((p for p in _PRODUCT_KEYWORDS if p in task_lower), "basketball")


def parse_inventory_intent(task: str) -> dict | None:
    """Parse quantity + product from a natural-language inventory task.

    Returns None if quantity can't be determined. `product_name` defaults
    to "basketball" when no keyword matches, matching current inventory
    agent behavior — callers that care should check the returned product.
    """
    if not task:
        return None
    try:
        quantity = _parse_quantity(task)
    except ValueError:
        return None
    if quantity is None or quantity <= 0:
        return None
    product = _parse_product(task)
    return {"quantity_delta": quantity, "product_name": product}
