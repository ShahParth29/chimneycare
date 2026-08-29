"""
reset_db.py — Resets and cleans all database entries (bookings, repairs, orders, test users)
and seeds fresh initial catalog and admin data.
"""

from supabase_client import get_admin_client
from seed_data import seed
from create_admin import create_or_update_admin

def reset_database():
    sb = get_admin_client()
    print("Resetting Database -- Clearing test entries and transactions...\n")

    # 1. Clear Services (Bookings)
    try:
        sb.table("services").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  + Cleared all bookings from 'services' table.")
    except Exception as e:
        print(f"  * Services table reset note: {e}")

    # 2. Clear Repair Jobs
    try:
        sb.table("repair_jobs").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  + Cleared all repair jobs from 'repair_jobs' table.")
    except Exception as e:
        print(f"  * Repair jobs table reset note: {e}")

    # 3. Clear Orders
    try:
        sb.table("orders").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  + Cleared all orders from 'orders' table.")
    except Exception as e:
        print(f"  * Orders table reset note: {e}")

    # 4. Clear Non-Admin Profiles and Test Auth Users
    try:
        admin_email = "admin.chimneycare@gmail.com"
        users = sb.auth.admin.list_users()
        for u in users:
            if u.email != admin_email and getattr(u, 'email', None) != admin_email:
                try:
                    sb.table("profiles").delete().eq("id", u.id).execute()
                    sb.auth.admin.delete_user(u.id)
                    print(f"  + Removed test user & profile: {u.email}")
                except Exception as ex:
                    print(f"  * Could not delete test user {u.email}: {ex}")
    except Exception as e:
        print(f"  * Auth users cleanup note: {e}")

    # 5. Reset Promo Code Usages
    try:
        sb.table("promo_codes").update({"current_uses": 0}).neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  + Reset promo code counters to 0.")
    except Exception as e:
        print(f"  * Promo codes counter reset note: {e}")

    # 6. Seed Fresh Catalog Data
    print("\nSeeding fresh catalog data (AMC Plans, Parts, Products, Promos)...")
    seed()

    # 7. Ensure Admin Account
    print("\nVerifying admin account...")
    create_or_update_admin()

    print("\nDatabase reset complete! The website is fresh and ready for production.")

if __name__ == "__main__":
    reset_database()
