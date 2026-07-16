"""Reset test data in the database."""

import asyncio
import sys

from pliris.database.supabase_client import get_client


async def main():
    """Reset test data."""
    print("Resetting test data...")

    try:
        client = get_client()

        # Delete test conversations
        print("Deleting test conversations...")
        client.table("conversations").delete().eq("user_id", "demo_user").execute()

        # Delete test documents
        print("Deleting test documents...")
        client.table("documents").delete().in_(
            "title",
            [
                "Annual Report 2024",
                "Employee Handbook 2024",
                "Strategic Plan 2025",
                "Q1 2024 Financial Results",
            ],
        ).execute()

        print("✓ Test data reset successfully")

        # Re-run seed data
        print("\nRe-seeding test data...")
        from pathlib import Path

        seed_path = Path(__file__).parent.parent / "supabase" / "seed.sql"

        # if seed_path.exists():
        # Read and execute seed SQL
        # with open(seed_path) as f:
        #  seed_sql = f.read()

        # This would need to be executed via the database connection
        # For now, we'll just note it
        print("Note: Seed SQL needs to be executed manually via Supabase dashboard")

        print("\nReset complete!")

    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
