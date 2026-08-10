#!/usr/bin/env python3
"""
Lightweight static verification for the "one governed agent" auth changes.

This repo has no pytest/jest harness wired up (no test files, no pytest.ini,
no jest config), so this is a grep-based guard rail instead of a proper
test suite. Run it after touching auth logging, the debug route, or the
agents/config endpoint:

    python3 scripts/verify_no_secret_logging.py

It checks, by reading source text (no imports, no server needed):

1. backend/api/main.py and backend/auth/multi_agent_auth.py never log a
   raw ID token / ID-JAG / access token, or a full decoded claim body
   (json.dumps of a claims dict). Sanitized single-claim metadata logging
   (sub, aud, scopes, etc.) is fine and expected.
2. The Next.js debug route never returns a full client ID or a full
   config URL - only booleans and/or a short, truncated prefix.
3. The FastAPI /api/agents/config response describes one governed
   ProGear Sales Agent across four resource domains, not four separately
   branded "ProGear <Domain> Agent" identities.

Exits non-zero on any finding.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_no_raw_token_logging() -> None:
    """Backend logs must never contain a raw token or a full claims dump."""
    targets = {
        REPO_ROOT / "backend" / "api" / "main.py": [
            r'logger\.\w+\(\s*f?"?\{?user_token\}?"?\s*\)',
            r"json\.dumps\(\s*user_claims",
        ],
        REPO_ROOT / "backend" / "auth" / "multi_agent_auth.py": [
            r'logger\.\w+\(\s*f?"?\{?id_jag_token\}?"?\s*\)',
            r'logger\.\w+\(\s*f?"?\{?token_result\.access_token\}?"?\s*\)',
            r"json\.dumps\(\s*id_jag_claims",
            r"json\.dumps\(\s*auth_token_claims",
            r"RAW ID-JAG TOKEN",
            r"RAW ACCESS TOKEN",
        ],
    }
    for path, patterns in targets.items():
        if not path.exists():
            fail(f"missing expected file: {path}")
            continue
        text = read(path)
        for pattern in patterns:
            if re.search(pattern, text):
                fail(f"{path}: found raw-token/full-claims logging pattern: {pattern!r}")

    # main.py should also no longer log the raw ID token banner.
    main_py = REPO_ROOT / "backend" / "api" / "main.py"
    if main_py.exists() and "RAW ID TOKEN" in read(main_py):
        fail(f"{main_py}: found raw ID token log banner")


def check_debug_route_is_sanitized() -> None:
    """The Next.js debug route must not echo full client IDs or URLs."""
    path = (
        REPO_ROOT
        / "packages"
        / "progear-sales-agent"
        / "src"
        / "app"
        / "api"
        / "debug"
        / "route.ts"
    )
    if not path.exists():
        fail(f"missing expected file: {path}")
        return

    text = read(path)

    leaky_patterns = [
        r"oktaClientId:\s*OKTA_CLIENT_ID\b",
        r"oktaDomain:\s*OKTA_DOMAIN\b",
        r"oktaIssuer:\s*OKTA_ISSUER\b",
        r"appUrl:\s*APP_URL\b",
        r"apiBaseUrl:\s*API_BASE_URL\b",
        r"clientIdLength",
    ]
    for pattern in leaky_patterns:
        if re.search(pattern, text):
            fail(f"{path}: debug route returns a full/raw config value: {pattern!r}")

    required_markers = ["hasClientId", "clientIdPrefix", "safePrefix("]
    for marker in required_markers:
        if marker not in text:
            fail(f"{path}: expected sanitized marker {marker!r} not found")


def check_agents_config_labels() -> None:
    """/api/agents/config must not brand four domains as four Okta agents."""
    path = REPO_ROOT / "backend" / "api" / "main.py"
    if not path.exists():
        fail(f"missing expected file: {path}")
        return

    text = read(path)

    disallowed_labels = [
        "ProGear Inventory Agent",
        "ProGear Customer Agent",
        "ProGear Pricing Agent",
    ]
    for label in disallowed_labels:
        if label in text:
            fail(f"{path}: found per-domain agent-identity label {label!r}")

    required_markers = ["governed_agent", "identity_note"]
    for marker in required_markers:
        if marker not in text:
            fail(f"{path}: expected clarifying field {marker!r} not found in agents/config")


def check_naming_alignment() -> None:
    """agent_config.py / multi_agent_auth.py should describe one governed agent."""
    for rel_path in ("backend/auth/agent_config.py", "backend/auth/multi_agent_auth.py"):
        path = REPO_ROOT / rel_path
        if not path.exists():
            fail(f"missing expected file: {path}")
            continue
        text = read(path)
        if "governed" not in text.lower():
            fail(f"{path}: expected 'governed' ProGear agent framing not found")
        if "resource domain" not in text.lower():
            fail(f"{path}: expected 'resource domain' framing not found")


def main() -> int:
    check_no_raw_token_logging()
    check_debug_route_is_sanitized()
    check_agents_config_labels()
    check_naming_alignment()

    if FAILURES:
        print("FAIL - verify_no_secret_logging.py found issues:\n")
        for item in FAILURES:
            print(f"  - {item}")
        print(f"\n{len(FAILURES)} issue(s) found.")
        return 1

    print("PASS - no raw token/claims logging, debug route is sanitized, "
          "agents/config reflects one governed agent across four domains.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
