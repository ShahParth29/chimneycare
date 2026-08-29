"""
create_admin.py — Securely creates or updates the administrator account in Supabase.
Credentials are read strictly from environment variables (ADMIN_EMAIL, ADMIN_PASSWORD).
"""

import os
import secrets
import string
from dotenv import load_dotenv
from supabase_client import get_admin_client

load_dotenv()

def generate_secure_password(length=16):
    """Generate a high-entropy password if none is provided via environment."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    return "".join(secrets.choice(alphabet) for _ in range(length))

def create_or_update_admin(email=None, password=None, name="ChimneyCare Admin"):
    sb = get_admin_client()
    
    # Read credentials strictly from environment variables
    admin_email = email or os.environ.get("ADMIN_EMAIL", "admin.chimneycare@gmail.com")
    admin_password = password or os.environ.get("ADMIN_PASSWORD")
    
    if not admin_password:
        admin_password = generate_secure_password(20)
        print("  [Notice] No ADMIN_PASSWORD set in environment. Generated random password.")

    print(f"Configuring admin user for: {admin_email}...")

    try:
        # Check if user exists in Supabase Auth
        user_list = sb.auth.admin.list_users()
        existing_user = None
        for u in user_list:
            if getattr(u, "email", None) == admin_email:
                existing_user = u
                break

        if not existing_user:
            # Create user in Supabase Auth
            created = sb.auth.admin.create_user({
                "email": admin_email,
                "password": admin_password,
                "email_confirm": True,
                "user_metadata": {"name": name, "role": "admin"}
            })
            user_id = created.user.id
            print(f"  + Created Supabase Auth user: {admin_email}")
        else:
            user_id = existing_user.id
            # Update password
            sb.auth.admin.update_user_by_id(user_id, {"password": admin_password, "email_confirm": True})
            print(f"  + Updated admin password in Supabase Auth.")

        # Ensure profile exists with role = 'admin'
        prof = sb.table("profiles").select("*").eq("id", user_id).execute()
        if not prof.data:
            sb.table("profiles").insert({
                "id": user_id,
                "role": "admin",
                "name": name,
                "email": admin_email,
                "phone": "+918734002200",
                "whatsapp_number": "+918734002200",
                "address": "Corporate HQ, Ahmedabad"
            }).execute()
            print("  + Inserted admin profile record.")
        else:
            sb.table("profiles").update({"role": "admin", "name": name}).eq("id", user_id).execute()
            print("  + Profile role verified as 'admin'.")

        print("\n[OK] Admin account is configured and ready.")

    except Exception as e:
        print(f"Error configuring admin: {e}")

if __name__ == "__main__":
    create_or_update_admin()
