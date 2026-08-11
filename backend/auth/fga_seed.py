"""Verify the contextual three-tier Inventory FGA model.

Run:
    python -m auth.fga_seed --verify

The current model does not seed role tuples. Okta is the source of truth for
``clearance_level`` (0 Sales, 1 Manager, 2 VP), and the backend supplies the
matching role as a contextual tuple on every check.
"""

import asyncio


async def verify() -> None:
    """Run a small decision matrix against the configured live FGA model."""
    from auth.fga_client import close_fga_client, check_inventory_access_via_fga

    checks = [
        ("Sales read", 0, "can_read", True),
        ("Sales request", 0, "can_request_change", False),
        ("Sales standard write", 0, "can_update_standard", False),
        ("Manager request", 1, "can_request_change", True),
        ("Manager standard write", 1, "can_update_standard", True),
        ("Manager large write", 1, "can_update_large", False),
        ("VP large write", 2, "can_update_large", True),
    ]

    print("--- ProGear Inventory FGA verification ---")
    failed = 0
    try:
        for label, role_level, relation, expected in checks:
            result = await check_inventory_access_via_fga(
                user_email="fga.verification@example.com",
                role_level=role_level,
                relation=relation,
            )
            passed = result.allowed is expected
            failed += int(not passed)
            print(
                f"{'PASS' if passed else 'FAIL'} {label}: "
                f"allowed={result.allowed}, expected={expected}"
            )
    finally:
        await close_fga_client()

    if failed:
        raise SystemExit(f"{failed} FGA verification check(s) failed")


if __name__ == "__main__":
    asyncio.run(verify())
