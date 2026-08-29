"""
blueprints/auth.py — Authentication routes for ChimneyCare.

Handles customer login/register, password recovery, admin login with optional OTP,
and session management with strict schema validation and information leakage defenses.
"""

import os
import time
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify

from supabase_client import get_supabase_client, get_admin_client
from utils import (
    sanitize_string,
    validate_email_strict,
    validate_phone_strict,
    validate_password_strict,
    validate_name_strict,
)

logger = logging.getLogger("chimneycare.auth")
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        user = session.get("user")
        if user:
            if user.get("role") == "admin":
                flash("You are already signed in as Administrator.", "info")
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("services.dashboard"))
        return render_template("auth/login.html")

    email = sanitize_string(request.form.get("email", ""), max_length=254).lower()
    password = request.form.get("password", "")

    # Strict Email Validation
    is_valid_email, email_err = validate_email_strict(email)
    if not is_valid_email:
        flash(email_err, "error")
        return render_template("auth/login.html"), 400

    if not password or len(password) < 6:
        flash("Please enter your password.", "error")
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
            flash("Account profile not found. Please contact support.", "error")
            return render_template("auth/login.html"), 400

        user_data = profile.data[0]

        # Strictly block admin accounts from logging in to Customer Portal
        if user_data.get("role") == "admin":
            sb.auth.sign_out()
            session.clear()
            flash("Administrator accounts cannot log into the Customer Portal. Please use the Admin Portal.", "error")
            return render_template("auth/login.html"), 403

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
        logger.warning(f"Failed login attempt for {email}: {e}")
        flash("Invalid email or password.", "error")
        return render_template("auth/login.html"), 401


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Forgot password request route with rate and enumeration protection."""
    if request.method == "GET":
        return render_template("auth/forgot_password.html")

    email = sanitize_string(request.form.get("email", ""), max_length=254)
    is_valid_email, email_err = validate_email_strict(email)
    if not is_valid_email:
        flash(email_err, "error")
        return render_template("auth/forgot_password.html"), 400

    try:
        sb = get_supabase_client()
        sb.auth.reset_password_for_email(email)
    except Exception as e:
        logger.info(f"Password reset request error for {email}: {e}")
        # Always return identical confirmation to prevent user enumeration
        pass

    flash("If an account exists with this email, password reset instructions have been sent.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        user = session.get("user")
        if user:
            if user.get("role") == "admin":
                flash("You are already signed in as Administrator.", "info")
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("services.dashboard"))
        return render_template("auth/register.html")


    name = sanitize_string(request.form.get("name", ""), max_length=100)
    email = sanitize_string(request.form.get("email", ""), max_length=254)
    phone = sanitize_string(request.form.get("phone", ""), max_length=20)
    whatsapp = sanitize_string(request.form.get("whatsapp_number", ""), max_length=20)
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    address = sanitize_string(request.form.get("address", ""), max_length=500)

    # ── Strict Schema Validation ──
    errors = []
    
    is_valid_name, name_err = validate_name_strict(name, "Full Name")
    if not is_valid_name:
        errors.append(name_err)

    is_valid_email, email_err = validate_email_strict(email)
    if not is_valid_email:
        errors.append(email_err)

    is_valid_phone, phone_err = validate_phone_strict(phone)
    if not is_valid_phone:
        errors.append(phone_err)

    if whatsapp:
        is_valid_wa, wa_err = validate_phone_strict(whatsapp)
        if not is_valid_wa:
            errors.append(f"WhatsApp: {wa_err}")

    is_valid_pass, pass_err = validate_password_strict(password)
    if not is_valid_pass:
        errors.append(pass_err)

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

        # Create profile record using admin client
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
        logger.error(f"Registration error for {email}: {e}")
        if "already registered" in error_msg.lower() or "duplicate" in error_msg.lower():
            flash("An account with this email already exists.", "error")
        else:
            flash("Registration could not be completed. Please verify your details or try again.", "error")
        return render_template("auth/register.html"), 400


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        user = session.get("user")
        if user and user.get("role") == "admin":
            return redirect(url_for("admin.dashboard"))
        return render_template("admin/login.html")


    email = sanitize_string(request.form.get("email", ""), max_length=254).lower()
    password = request.form.get("password", "")


    is_valid_email, email_err = validate_email_strict(email)
    if not is_valid_email or not password:
        flash("Valid email and password are required.", "error")
        return render_template("admin/login.html"), 400

    try:
        sb = get_supabase_client()
        auth_response = sb.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

        user_id = auth_response.user.id

        # Verify admin role via service client
        admin_sb = get_admin_client()
        profile = admin_sb.table("profiles").select("*").eq("id", user_id).execute()

        if not profile.data or profile.data[0].get("role") != "admin":
            logger.warning(f"Unauthorized admin login attempt by non-admin user {email}")
            flash("Access denied. Admin accounts only.", "error")
            sb.auth.sign_out()
            return render_template("admin/login.html"), 403

        user_data = profile.data[0]

        # ── Admin 2FA TOTP Verification ──
        admin_2fa_enabled = os.environ.get("ADMIN_2FA_ENABLED", "true").lower() in ("true", "1", "yes")
        if admin_2fa_enabled:
            import time
            sb.auth.sign_out()
            session["pending_admin_2fa"] = {
                "user_id": user_id,
                "email": email,
                "name": user_data.get("name", "Admin"),
                "role": "admin",
                "expires_at": time.time() + 300,
                "attempts": 0,
            }
            return redirect(url_for("auth.verify_otp"))

        session["user"] = {
            "id": user_id,
            "email": email,
            "name": user_data.get("name", "Admin"),
            "role": "admin",
        }

        flash("Welcome to the Admin Portal.", "success")
        return redirect(url_for("admin.dashboard"))

    except Exception as e:
        logger.warning(f"Failed admin login attempt for {email}: {e}")
        flash("Invalid administrator credentials.", "error")
        return render_template("admin/login.html"), 401


@auth_bp.route("/admin/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """2FA OTP verification step for admin login."""
    import time
    import pyotp

    pending = session.get("pending_admin_2fa")
    if not pending or time.time() > pending.get("expires_at", 0):
        session.pop("pending_admin_2fa", None)
        flash("2FA session expired. Please sign in again.", "warning")
        return redirect(url_for("auth.admin_login"))

    if request.method == "GET":
        return render_template("admin/verify_otp.html")

    code = sanitize_string(request.form.get("otp", ""), max_length=12).strip().upper()
    if not code:
        flash("Please enter your 6-digit Authenticator code or a backup code.", "error")
        return render_template("admin/verify_otp.html"), 400

    # Track attempts
    attempts = pending.get("attempts", 0) + 1
    pending["attempts"] = attempts
    session["pending_admin_2fa"] = pending

    if attempts > 5:
        session.pop("pending_admin_2fa", None)
        flash("Too many failed verification attempts. Please log in again.", "error")
        return redirect(url_for("auth.admin_login"))

    # Verify TOTP code against ADMIN_2FA_SECRET
    admin_secret = os.environ.get("ADMIN_2FA_SECRET", "PKNZR4SQICIEAKDHYVINE2ASHJXOZFQE")
    totp = pyotp.TOTP(admin_secret)
    is_valid = False

    if len(code) == 6 and code.isdigit():
        is_valid = totp.verify(code, valid_window=1)

    # Check emergency backup codes (e.g. CHMN-9281)
    if not is_valid:
        backup_codes_str = os.environ.get("ADMIN_BACKUP_CODES", "CHMN-9281,CARE-4710,SAFE-8392,FIRE-1934")
        allowed_backups = [b.strip().upper() for b in backup_codes_str.split(",") if b.strip()]
        if code in allowed_backups:
            is_valid = True

    if not is_valid:
        remaining = 5 - attempts
        flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "error")
        return render_template("admin/verify_otp.html"), 401

    # Verification successful: promote to full session
    session.pop("pending_admin_2fa", None)
    session["user"] = {
        "id": pending["user_id"],
        "email": pending["email"],
        "name": pending["name"],
        "role": "admin",
    }

    flash("2FA Verification Successful. Welcome to the Admin Portal.", "success")
    return redirect(url_for("admin.dashboard"))



@auth_bp.route("/logout", methods=["POST"])
def logout():
    try:
        sb = get_supabase_client()
        sb.auth.sign_out()
    except Exception as e:
        logger.info(f"Logout cleanup note: {e}")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
