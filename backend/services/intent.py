"""Shape of the intent payload encoded in OIG request justification."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
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


_QTY_RE = re.compile(r"(\d+)")
# Order matters: longer/more-specific matches come first so "basketball" wins
# over any bare "ball" substring. Bare "ball" is intentionally absent — this is
# a basketball-equipment demo, so "balls"/"ball" should canonicalize to the
# default "basketball" below, keeping the inventory-agent and approval-gate
# paths resolving the same SKU.
_PRODUCT_KEYWORDS = (
    "basketball", "treadmill", "helmet", "glove", "shoe", "jersey",
    "racket", "bat",
)


def parse_inventory_intent(task: str) -> dict | None:
    """Parse quantity + product from a natural-language inventory task.

    Returns None if quantity can't be determined. `product_name` defaults
    to "basketball" when no keyword matches, matching current inventory
    agent behavior — callers that care should check the returned product.
    """
    if not task:
        return None
    m = _QTY_RE.search(task)
    if not m:
        return None
    try:
        quantity = int(m.group(1))
    except ValueError:
        return None
    task_lower = task.lower()
    product = next((p for p in _PRODUCT_KEYWORDS if p in task_lower), "basketball")
    return {"quantity_delta": quantity, "product_name": product}
