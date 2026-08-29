"""
blueprints/auth.py — Authentication routes for ChimneyCare.

Handles customer login/register, admin login with optional OTP,
and session management via Supabase Auth.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_supabase_client, get_admin_client
from utils import sanitize_string, validate_email, validate_phone

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    email = sanitize_string(request.form.get("email", ""))
    password = request.form.get("password", "")

    if not email or not password:
        flash("Email and password are required.", "error")
        return render_template("auth/login.html"), 400

    if not validate_email(email):
        flash("Please enter a valid email address.", "error")
        return render_template("auth/login.html"), 400

    try:
        sb = get_supabase_client()
        auth_response = sb.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

        user_id = auth_response.user.id

        # Fetch profile to get role
        profile = sb.table("profiles").select("*").eq("id", user_id).execute()

        if not profile.data:
            flash("Profile not found. Please contact support.", "error")
            return render_template("auth/login.html"), 400

        user_data = profile.data[0]

        # Block admin accounts from customer login
        if user_data.get("role") == "admin":
            flash("Admin accounts must use the admin login.", "warning")
            sb.auth.sign_out()
            return redirect(url_for("auth.admin_login"))

        session["user"] = {
            "id": user_id,
            "email": email,
            "name": user_data.get("name", ""),
            "role": user_data.get("role", "customer"),
            "phone": user_data.get("phone", ""),
        }
        if hasattr(auth_response, 'session') and auth_response.session:
            session["access_token"] = auth_response.session.access_token

        flash(f"Welcome back, {user_data.get('name', 'there')}!", "success")
        next_url = request.args.get("next", url_for("services.dashboard"))
        return redirect(next_url)

    except Exception as e:
        error_msg = str(e)
        if "Invalid login" in error_msg or "invalid" in error_msg.lower():
            flash("Invalid email or password.", "error")
        else:
            flash("Login failed. Please try again.", "error")
        return render_template("auth/login.html"), 401


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth/register.html")

    name = sanitize_string(request.form.get("name", ""))
    email = sanitize_string(request.form.get("email", ""))
    phone = sanitize_string(request.form.get("phone", ""))
    whatsapp = sanitize_string(request.form.get("whatsapp_number", ""))
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    address = sanitize_string(request.form.get("address", ""), max_length=500)

    # ── Validation ──
    errors = []
    if not name:
        errors.append("Name is required.")
    if not email or not validate_email(email):
        errors.append("A valid email address is required.")
    if not phone or not validate_phone(phone):
        errors.append("A valid Indian phone number is required.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("auth/register.html"), 400

    try:
        sb = get_supabase_client()

        # Create user via Supabase Auth (bcrypt password hashing)
        auth_response = sb.auth.sign_up({
            "email": email,
            "password": password,
        })

        user_id = auth_response.user.id

        # Create profile record
        admin_sb = get_admin_client()
        admin_sb.table("profiles").insert({
            "id": user_id,
            "role": "customer",
            "name": name,
            "phone": phone,
            "whatsapp_number": whatsapp or phone,
            "email": email,
            "address": address,
        }).execute()

        session["user"] = {
            "id": user_id,
            "email": email,
            "name": name,
            "role": "customer",
            "phone": phone,
        }

        flash("Account created successfully! Welcome to ChimneyCare.", "success")
        return redirect(url_for("services.dashboard"))

    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower() or "duplicate" in error_msg.lower():
            flash("An account with this email already exists.", "error")
        else:
            flash(f"Registration failed: {error_msg}", "error")
        return render_template("auth/register.html"), 400


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin/login.html")

    email = sanitize_string(request.form.get("email", ""))
    password = request.form.get("password", "")

    if not email or not password:
        flash("Email and password are required.", "error")
        return render_template("admin/login.html"), 400

    try:
        sb = get_supabase_client()
        auth_response = sb.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

        user_id = auth_response.user.id

        # Verify admin role
        admin_sb = get_admin_client()
        profile = admin_sb.table("profiles").select("*").eq("id", user_id).execute()

        if not profile.data or profile.data[0].get("role") != "admin":
            flash("Access denied. Admin accounts only.", "error")
            sb.auth.sign_out()
            return render_template("admin/login.html"), 403

        user_data = profile.data[0]
        session["user"] = {
            "id": user_id,
            "email": email,
            "name": user_data.get("name", "Admin"),
            "role": "admin",
        }

        flash("Welcome to the Admin Portal.", "success")
        return redirect(url_for("admin.dashboard"))

    except Exception as e:
        flash("Invalid credentials.", "error")
        return render_template("admin/login.html"), 401


@auth_bp.route("/admin/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """2FA OTP verification step for admin login."""
    if request.method == "GET":
        return render_template("admin/verify_otp.html")

    otp = sanitize_string(request.form.get("otp", ""))
    if not otp or len(otp) != 6:
        flash("Please enter a valid 6-digit OTP.", "error")
        return render_template("admin/verify_otp.html"), 400

    # STUB: In production, verify via Supabase Auth phone OTP
    # sb.auth.verify_otp({"phone": phone, "token": otp, "type": "sms"})
    flash("OTP verification is not yet configured. Contact your system administrator.", "warning")
    return redirect(url_for("admin.dashboard"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    try:
        sb = get_supabase_client()
        sb.auth.sign_out()
    except Exception:
        pass
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
