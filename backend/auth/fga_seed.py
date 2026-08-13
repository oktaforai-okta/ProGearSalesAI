"""
Seed FGA store with initial relationship tuples for the ProGear demo.

Run: python -m auth.fga_seed

This seeds `manager` tuples for inventory_system. The vacation check
uses contextual tuples passed at check time from Okta claims.

FGA Model:
  type inventory_system
    relations
      define manager: [user]
      define on_vacation: [user]
      define can_increase_inventory: manager but not on_vacation

Tuple format uses Okta email/login (not UID) for readability:
  user:bob.manager@atko.email  manager  inventory_system:main_db
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Define manager users by their Okta email/login
# Add users here who should have inventory manager access
INVENTORY_MANAGERS = [
    "bob.manager@atko.email",      # Bob - warehouse manager
    "mike.manager@atko.email",     # Mike - warehouse manager (may be on vacation)
    # Add more managers as needed:
    # "jane.warehouse@atko.email",
]


async def seed():
    """Seed FGA store with manager relationship tuples."""
    try:
        from openfga_sdk import ClientConfiguration, OpenFgaClient
        from openfga_sdk.credentials import Credentials, CredentialConfiguration
        from openfga_sdk.client.models import ClientTuple, ClientWriteRequest
    except ImportError:
        print("ERROR: openfga_sdk not installed. Run: pip install openfga-sdk")
        return

    api_url = os.getenv("FGA_API_URL")
    store_id = os.getenv("FGA_STORE_ID")
    client_id = os.getenv("FGA_CLIENT_ID")
    client_secret = os.getenv("FGA_CLIENT_SECRET")

    if not all([api_url, store_id, client_id, client_secret]):
        print("ERROR: Missing FGA environment variables. Check .env file.")
        print("Required: FGA_API_URL, FGA_STORE_ID, FGA_CLIENT_ID, FGA_CLIENT_SECRET")
        return

    configuration = ClientConfiguration(
        api_url=api_url,
        store_id=store_id,
        authorization_model_id=os.getenv("FGA_MODEL_ID", ""),
        credentials=Credentials(
            method='client_credentials',
            configuration=CredentialConfiguration(
                api_issuer=os.getenv("FGA_API_TOKEN_ISSUER", "fga.us.auth0.com"),
                api_audience=os.getenv("FGA_API_AUDIENCE", "https://api.us1.fga.dev/"),
                client_id=client_id,
                client_secret=client_secret,
            )
        )
    )

    async with OpenFgaClient(configuration) as fga:
        # Build manager tuples from the list
        # No conditions - vacation is checked via contextual tuples at runtime
        tuples = [
            ClientTuple(
                user=f"user:{email}",
                relation="manager",
                object="inventory_system:main_db",
            )
            for email in INVENTORY_MANAGERS
        ]

        print(f"Seeding {len(tuples)} manager tuples...")
        for t in tuples:
            print(f"  - {t.user} -> {t.relation} -> {t.object}")

        try:
            body = ClientWriteRequest(writes=tuples)
            await fga.write(body)
            print(f"\nSUCCESS: Seeded {len(tuples)} FGA tuples")
        except Exception as e:
            if "cannot write a tuple which already exists" in str(e).lower():
                print("\nINFO: Some tuples already exist in FGA store (this is fine)")
            else:
                print(f"\nERROR: Failed to write tuples: {e}")


async def verify():
    """Verify FGA checks work as expected."""
    from auth.fga_client import check_inventory_access_via_fga

    print("\n--- Verification Checks ---")

    # Test 1: Manager not on vacation -> should be ALLOWED
    result = await check_inventory_access_via_fga(
        user_email="bob.manager@atko.email",
        is_on_vacation=False,
    )
    print(f"bob.manager (not on vacation): allowed={result.allowed}")
    print(f"  Reason: {result.reason}")

    # Test 2: Manager on vacation -> should be DENIED
    result = await check_inventory_access_via_fga(
        user_email="bob.manager@atko.email",
        is_on_vacation=True,
    )
    print(f"bob.manager (on vacation): allowed={result.allowed}")
    print(f"  Reason: {result.reason}")

    # Test 3: Non-manager -> should be DENIED
    result = await check_inventory_access_via_fga(
        user_email="sales.user@atko.email",
        is_on_vacation=False,
    )
    print(f"sales.user (not a manager): allowed={result.allowed}")
    print(f"  Reason: {result.reason}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        asyncio.run(verify())
    else:
        asyncio.run(seed())
        print("\nTo verify: python -m auth.fga_seed --verify")
