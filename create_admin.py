"""
create_admin.py — Creates or configures the official admin user in Supabase.
"""

from supabase_client import get_admin_client

def create_or_update_admin(email="admin.chimneycare@gmail.com", password="Admin.ChimneyCare@291302", name="ChimneyCare Admin"):
    sb = get_admin_client()
    print(f"Setting up admin user: {email}...")

    try:
        # Check if user exists in auth
        user_list = sb.auth.admin.list_users()
        existing_user = None
        for u in user_list:
            if u.email == email:
                existing_user = u
                break

        if not existing_user:
            # Create user in Supabase Auth
            created = sb.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name, "role": "admin"}
            })
            user_id = created.user.id
            print(f"  + Created Supabase Auth user: {email} (ID: {user_id})")
        else:
            user_id = existing_user.id
            # Update password
            sb.auth.admin.update_user_by_id(user_id, {"password": password, "email_confirm": True})
            print(f"  + Updated existing user password: {email}")

        # Ensure profile exists with role = 'admin'
        prof = sb.table("profiles").select("*").eq("id", user_id).execute()
        if not prof.data:
            sb.table("profiles").insert({
                "id": user_id,
                "role": "admin",
                "name": name,
                "email": email,
                "phone": "+918734002200",
                "whatsapp_number": "+918734002200",
                "address": "Corporate HQ, Ahmedabad"
            }).execute()
            print("  + Inserted admin profile record.")
        else:
            sb.table("profiles").update({"role": "admin", "name": name}).eq("id", user_id).execute()
            print("  + Updated profile role to 'admin'.")

        print("\nADMIN USER READY:")
        print(f"  URL:      http://localhost:5000/admin/login")
        print(f"  Email:    {email}")
        print(f"  Password: {password}")

    except Exception as e:
        print(f"Error creating admin: {e}")

if __name__ == "__main__":
    create_or_update_admin()
