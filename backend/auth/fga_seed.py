"""Verify the contextual three-tier Inventory FGA model.

Run:
    python -m auth.fga_seed --verify

The current model does not seed role tuples. Okta is the source of truth for
``clearance_level`` (1 Sales, 2 Manager, 3 VP), and the backend supplies the
matching role plus vacation status as contextual tuples on every check.
"""

import asyncio


async def verify() -> None:
    """Run a small decision matrix against the configured live FGA model."""
    from auth.fga_client import close_fga_client, check_inventory_access_via_fga

    checks = [
        ("Sales read", 1, False, "can_read", True),
        ("Sales request", 1, False, "can_request_change", True),
        ("Sales standard write", 1, False, "can_update_standard", False),
        ("Manager standard write", 2, False, "can_update_standard", True),
        ("Manager large write", 2, False, "can_update_large", False),
        ("VP large write", 3, False, "can_update_large", True),
        ("Manager vacation write", 2, True, "can_update_standard", False),
        ("Manager vacation read", 2, True, "can_read", True),
    ]

    print("--- ProGear Inventory FGA verification ---")
    failed = 0
    try:
        for label, role_level, vacation, relation, expected in checks:
            result = await check_inventory_access_via_fga(
                user_email="fga.verification@example.com",
                is_on_vacation=vacation,
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
